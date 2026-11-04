"""映射后的空业务对象与字段校验保持独立，不推断上游调用类型。"""

import pytest
from pydantic import ValidationError

from api.routes import StringifiedToolArgumentsError, _normalize_payload
from api.schemas import GenerateWidgetCardRequest
from services.agent_error_view import agent_error_view
from services.agent_feedback import request_validation_feedback


@pytest.mark.parametrize("content", [{}, {"functionName": "generateWidgetCardCompactDsl"},
                                      {"bundleName": "test", "romVersion": "7.0"}])
def test_missing_business_does_not_guess_string_type(content):
    with pytest.raises(StringifiedToolArgumentsError) as caught:
        _normalize_payload({"content": content}, "generateWidgetCardCompactDsl")
    details = caught.value.details()
    issues = details.get("issues")
    assert isinstance(issues, list)
    assert issues[0].get("actualType") == "unknown"
    result = agent_error_view({"details": details}, "参数错误")
    assert result.get("retryable") is True
    assert "不重复询问" in str(result)


def test_utterance_fallback_remains_available():
    _, arguments = _normalize_payload({
        "content": {"functionName": "generateWidgetCardCompactDsl"},
        "utterance": {"original": "生成卡片"},
    }, "generateWidgetCardCompactDsl")
    assert arguments.get("userQuery") == "生成卡片"


@pytest.mark.parametrize("query", [None, ""])
def test_partial_business_preserves_all_diagnostics(query):
    arguments = {"uid": "test", "device": {"romVersion": "7.0"}, "size": "invalid"}
    if query is not None:
        arguments["userQuery"] = query
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    feedback = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": feedback}, "参数错误")
    issues = result.get("issues")
    assert isinstance(issues, list)
    paths = [issue.get("path") for issue in issues]
    assert set(paths) == {"/userQuery", "/size", "/title", "/description"}
    assert "不代表用户原始需求文字太短" in str(result)
    assert "保留模式" in str(result)


def test_unknown_business_field_is_not_classified_as_empty_transport():
    _, arguments = _normalize_payload({"content": {"data": []}}, "generateWidgetCardCompactDsl")
    assert "data" in arguments
