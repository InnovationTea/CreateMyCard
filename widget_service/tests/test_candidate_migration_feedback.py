"""候选字段错用时保留业务意图并一次反馈可独立确认的问题。"""

import json

import pytest
from pydantic import ValidationError

from api.schemas import GenerateWidgetCardRequest
from services.agent_error_view import agent_error_view
from services.agent_feedback import request_validation_feedback


@pytest.mark.parametrize("editing", [False, True])
@pytest.mark.parametrize("metadata", [{}, {"title": None, "description": None}])
def test_candidate_migration_and_metadata(editing, metadata):
    arguments = {
        "uid": "test", "device": {"romVersion": "7.0"}, "userQuery": "生日倒计时",
        "size": "bad-size", "dataCapabilities": [{"id": "secret-id"}],
        "assetCandidates": ["secret-asset"], "eventCapabilities": [], **metadata,
    }
    if editing:
        arguments["sourceArtifactUrl"] = "https://example.test/source"
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    issues = result.get("issues")
    assert isinstance(issues, list)
    paths = [item.get("path") for item in issues]
    assert len(paths) == len(set(paths))
    assert "/size" in paths
    assert ("/title" in paths) is (not editing)
    assert ("/description" in paths) is (not editing)
    text = json.dumps(result, ensure_ascii=False)
    for expected in ("candidateDataBindings", "candidateEventCandidates", "candidateAssetIds"):
        assert expected in text
    assert "不得仅删除" in text
    assert "secret-id" not in text and "secret-asset" not in text
    assert result.get("retryable") is True


def test_nested_business_field_does_not_receive_top_level_migration():
    result = agent_error_view({"details": {
        "retryable": True, "requiredActions": ["FIX_AND_RETRY"],
        "issues": [{"code": "REQUEST_EXTRA_FORBIDDEN",
                    "path": "/candidateDataBindings/0/arguments/dataCapabilities"}],
    }}, "参数错误")
    assert "重构为" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("alias,target", [
    ("assetCandidateIds", "candidateAssetIds"),
    ("assetCandidates", "candidateAssetIds"),
    ("candidateAssets", "candidateAssetIds"),
    ("assetIds", "candidateAssetIds"),
    ("dataCandidates", "candidateDataBindings"),
    ("dataBindings", "candidateDataBindings"),
    ("candidateDataCapabilities", "candidateDataBindings"),
    ("eventCandidates", "candidateEventCandidates"),
    ("candidateEvents", "candidateEventCandidates"),
])
def test_registered_alias_preserves_values_and_does_not_apply_inside_arguments(alias, target):
    from services.agent_error_view import _extra_field_message

    message = _extra_field_message("/" + alias)
    assert alias in message and target in message
    assert "0、false、空字符串" in message
    assert "先核对冲突" in message
    nested = _extra_field_message("/candidateDataBindings/0/arguments/" + alias)
    assert "重构为" not in nested
    assert "改为" not in nested


def test_call_record_retry_keeps_parameters_and_reports_all_visible_problems():
    arguments = {
        "uid": "test", "device": {"romVersion": "7.0"}, "userQuery": "最近通话",
        "action": "create", "assetCandidateIds": ["secret-asset"],
        "candidateDataBindings": [{
            "dataCapabilityId": "GetPhoneCallRecords", "inputParams": {"callRecordType": 0},
        }],
    }
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    text = json.dumps(result, ensure_ascii=False)
    assert "同一候选项的 arguments" in text
    assert "保留真实类型及零值" in text
    assert "candidateAssetIds" in text
    assert "顶层 action" in text
    issues = result.get("issues")
    assert isinstance(issues, list)
    paths = [issue.get("path") for issue in issues]
    assert "/title" in paths and "/description" in paths
    bindings = arguments.get("candidateDataBindings")
    assert isinstance(bindings, list)
    assert bindings[0].get("inputParams") == {"callRecordType": 0}
    assert "secret-asset" not in text


@pytest.mark.parametrize("value,recognized", [
    ([{"capabilityId": "example", "arguments": {"count": 0, "enabled": False, "text": ""},
       "writeResultTo": "/data/example", "candidateOutputFields": ["/value"]}], True),
    ([], False), ({"value": 1}, False), (["example"], False),
    ([{"capabilityId": "example"}], False),
    ([{"capabilityId": "example", "arguments": {}, "writeResultTo": "/data/example"},
      {"value": 1}], False),
])
@pytest.mark.parametrize("has_target", [False, True])
def test_data_structure_feedback_preserves_input(value, recognized, has_target):
    import copy

    arguments = {
        "uid": "test", "device": {"romVersion": "7.0"}, "userQuery": "测试需求",
        "title": "标题", "description": "说明", "data": value,
    }
    if has_target:
        arguments["candidateDataBindings"] = []
    original = copy.deepcopy(arguments)
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    text = json.dumps(result, ensure_ascii=False)
    has_string_items = isinstance(value, list) and any(isinstance(item, str) for item in value)
    if has_string_items:
        assert "若为候选 JSON" in text
        assert "无法还原时核对原始调用" in text
    else:
        assert ("将完整数组迁移到 candidateDataBindings" in text) is recognized
        assert ("现有结构无法确认" in text) is (not recognized)
    assert "请移除该字段" not in text
    assert arguments == original
    assert result.get("retryable") is True
    if recognized:
        assert "先核对冲突" in text
        assert "不表示能力或参数合法" in text
        assert "保留参数类型及 0、false、合法空字符串" in text


def test_data_inside_call_arguments_is_not_a_top_level_alias():
    from services.agent_error_view import _extra_field_message

    message = _extra_field_message("/candidateDataBindings/0/arguments/data")
    assert "迁移" not in message


@pytest.mark.parametrize("name,target", [
    ("candidateAssetCandidates", "candidateAssetIds"),
    ("ASSET_LIST", "candidateAssetIds"),
    ("myAsSeTs", "candidateAssetIds"),
    ("EVENT_LIST", "candidateEventCandidates"),
    ("myEvEnTs", "candidateEventCandidates"),
])
def test_keyword_feedback_is_top_level_only_and_keeps_request(name, target):
    import copy

    from services.agent_error_view import _extra_field_message

    arguments = {
        "uid": "test", "device": {"romVersion": "7.0"}, "userQuery": "测试",
        "title": "标题", "description": "说明", name: ["secret-value"],
    }
    original = copy.deepcopy(arguments)
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    text = json.dumps(result, ensure_ascii=False)
    assert target in text
    assert "先核对冲突" in text
    assert "secret-value" not in text
    assert result.get("retryable") is True
    assert arguments == original
    for root in ("/candidateDataBindings/0/arguments/", "/candidateEventCandidates/0/action/args/"):
        nested = _extra_field_message(root + name)
        assert "若为" not in nested
        assert "改用" not in nested


def test_ambiguous_keyword_and_unrelated_fields_do_not_guess_target():
    from services.agent_error_view import _extra_field_message

    message = _extra_field_message("/myEVENTAssetList")
    assert "candidateEventCandidates" in message
    assert "candidateAssetIds" in message
    assert "不将混合内容直接改名" in message
    assert _extra_field_message("/unrelated") == "不支持字段 unrelated，请移除该字段。"


def test_stringified_data_feedback_is_concise_and_preserves_retry_control():
    arguments = {
        "uid": "test", "device": {"romVersion": "7.0"}, "userQuery": "测试",
        "title": "标题", "description": "说明",
        "data": ['{"capabilityId":"secret","arguments":{"count":0},"writeResultTo":"/data/x"}'],
    }
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    issues = result.get("issues")
    assert isinstance(issues, list) and len(issues) == 1
    message = issues[0].get("message")
    assert isinstance(message, str)
    assert len(message) < 260
    assert "还原为对象" in message
    assert "candidateDataBindings" in message
    assert "绑定变化后复查权限" in message
    assert "要求：" not in message
    assert "secret" not in message
    assert result.get("retryable") is True
    assert result.get("requiredActions") == ["FIX_AND_RETRY"]
