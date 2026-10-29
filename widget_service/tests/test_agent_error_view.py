"""真实主 Agent 的简版错误合同；详细诊断仍留在内部。"""

import copy
import json

import pytest

from api.routes import _build_plugin_stream_response
from models.service import WidgetWebSocketErrorMessage, WidgetWebSocketResultMessage
from services.agent_error_view import agent_error_view

_FIELDS = {"message", "retryable", "requiredActions", "agentInstruction", "issues"}


@pytest.mark.parametrize(
    "operation",
    [
        "getWidgetCapabilityOverview",
        "getDataCapabilitySchemas",
        "generateWidgetCard",
        "generateWidgetCardCompactDsl",
        "generateWidgetCardTerseDslNested2",
    ],
)
@pytest.mark.parametrize(
    "path,message,expected",
    [
        ("/size", "取值不合法。", "2x2 或 2x4"),
        ("/candidateDataBindings/0/arguments/limit", "类型不符合要求。", "整数，范围 1 至 5"),
        ("/candidateEventCandidates/0/action", "动作结构不合法。", "对象 {call,args}"),
    ],
)
def test_error_projection_keeps_paths_constraints_and_internal_diagnostics(
    operation,
    path,
    message,
    expected,
):
    issue = {
        "path": path,
        "message": message,
        "expected": expected,
        "repairInstruction": "按 expected 修正本项。",
        "actualType": "string",
        "code": "INVALID",
        "referenceSource": "本轮定义",
    }
    internal = WidgetWebSocketErrorMessage(
        operation=operation,
        errorCode="INVALID_ARGUMENTS",
        error={
            "message": "参数不合法。",
            "details": {
                "stage": "requestValidation",
                "modelCalled": False,
                "retryable": True,
                "requiredActions": ["FIX_AND_RETRY"],
                "agentInstruction": "修正后提交完整参数。",
                "issues": [issue],
            },
        },
    )
    original = internal.model_copy(deep=True)
    response = _build_plugin_stream_response(internal)
    view = json.loads(response.reply.streamInfo.streamContent)
    assert set(view) == _FIELDS
    assert view.get("retryable") is True
    assert view.get("requiredActions") == ["FIX_AND_RETRY"]
    issues = view.get("issues")
    assert isinstance(issues, list) and len(issues) == 1
    assert set(issues[0]) == {"path", "message"}
    assert issues[0].get("path") == path
    assert expected in issues[0].get("message", "")
    assert "按上述要求修正" not in issues[0].get("message", "")
    assert response.errorCode == "0"
    assert internal == original


def test_all_issues_and_present_warnings_are_kept_in_order():
    details = {
        "retryable": True,
        "requiredActions": ["REFRESH_CAPABILITIES", "FIX_AND_RETRY"],
        "issues": [
            {"path": "/candidateDataBindings/0", "message": "缺少本轮可用动态绑定。"},
            {"path": "/candidateDataBindings/1", "message": "未知数据能力。"},
        ],
        "diagnostic": {"issues": [{"path": "/title", "message": "标题为空。"}]},
        "warnings": [
            {"path": "/candidateEventCandidates/0", "message": "依赖缺失，移除可选事件。"},
        ],
    }
    original = copy.deepcopy(details)
    view = agent_error_view({"message": "预检未通过。", "details": details}, "失败")
    issues = view.get("issues")
    assert isinstance(issues, list)
    assert [issue.get("path") for issue in issues] == [
        "/candidateDataBindings/0",
        "/candidateDataBindings/1",
        "/title",
    ]
    assert view.get("message") == "预检未通过。"
    assert view.get("warnings") == details.get("warnings")
    assert details == original


@pytest.mark.parametrize(
    "details",
    [
        {},
        {"retryable": "true", "requiredActions": ["FIX_AND_RETRY"]},
        {"retryable": True, "requiredActions": ["UNKNOWN"]},
        {"retryable": True, "requiredActions": ["STOP", "FIX_AND_RETRY"]},
        {"retryable": True, "requiredActions": ["NOTIFY_USER"]},
    ],
)
def test_missing_or_stopping_controls_never_grant_retry(details):
    view = agent_error_view({"details": details}, "处理失败。")
    assert set(view) == _FIELDS
    assert view.get("retryable") is False
    assert view.get("requiredActions") in (["STOP"], ["NOTIFY_USER"])
    assert "停止本轮自动调用" in view.get("agentInstruction", "")


@pytest.mark.parametrize("status", ["failed", "unsupported"])
def test_failed_result_excludes_artifact_urls_and_generated_content(status):
    internal = WidgetWebSocketResultMessage(
        operation="generateWidgetCardCompactDsl",
        status=status,
        errorCode="VALIDATION_FAILED",
        data={"artifactUrl": "secret-url", "dsl": "secret-dsl", "status": status},
        error={"message": "生成结果无效。"},
    )
    response = _build_plugin_stream_response(internal)
    raw = response.reply.streamInfo.streamContent
    view = json.loads(raw)
    assert set(view) == _FIELDS
    assert view.get("retryable") is False
    assert "secret-url" not in raw and "secret-dsl" not in raw
    if status == "unsupported":
        assert "不支持流程" in view.get("agentInstruction", "")


@pytest.mark.parametrize(
    "path,code,message,expected",
    [
        (
            "/debugMode",
            "REQUEST_EXTRA_FORBIDDEN",
            "此位置包含未声明字段。",
            "不支持字段 debugMode，请移除该字段。",
        ),
        (
            "/options/debugMode",
            "REQUEST_EXTRA_FORBIDDEN",
            "此位置包含未声明字段。",
            "不支持字段 debugMode，请移除该字段。",
        ),
        (
            "/arguments",
            "REQUEST_EXTRA_FORBIDDEN",
            "此位置包含未声明字段。",
            "请将其中的业务字段直接放入 arguments 对象",
        ),
        (
            "/candidateEventCandidates/0/id",
            "REQUEST_EXTRA_FORBIDDEN",
            "此位置包含未声明字段。",
            "事件 ID 放到候选项的 capabilityId",
        ),
        (
            "/candidateEventCandidates/0/actionTemplate",
            "REQUEST_EXTRA_FORBIDDEN",
            "此位置包含未声明字段。",
            "将 call、args 放入 action",
        ),
        (
            "/candidateDataBindings/0/arguments/size",
            "DATA_ARGUMENT_SCHEMA_INVALID",
            "包含 schema 未声明的字段。",
            "按本轮 inputSchema 填写合法业务参数",
        ),
    ],
)
def test_unsupported_fields_name_the_field_and_give_a_concrete_action(
    path, code, message, expected
):
    issue = {
        "path": path,
        "code": code,
        "message": message,
        "expected": "当前工具 Schema 在该位置声明的字段",
        "repairInstruction": "核对字段归属；核对字段名和层级。",
    }
    view = agent_error_view({"details": {"issues": [issue]}}, "失败")
    issues = view.get("issues")
    assert isinstance(issues, list) and len(issues) == 1
    text = issues[0].get("message", "")
    assert expected in text
    assert "要求：" not in text and "核对字段归属" not in text
    if path.endswith("/size"):
        assert "2x2" not in text


@pytest.mark.parametrize(
    "path,code,reason,expected",
    [
        ("/size", "REQUEST_LITERAL_ERROR", "取值不在当前工具允许的枚举范围内。", "2x2 或 2x4"),
        (
            "/title",
            "REQUEST_STRING_TYPE",
            "字段的 JSON 类型不符合要求。",
            "JSON 字符串；非空字符串",
        ),
        (
            "/candidateDataBindings/0/arguments/limit",
            "DATA_ARGUMENT_SCHEMA_INVALID",
            "字段类型不符合 schema。",
            "JSON 类型 integer；取值范围 1 至 5",
        ),
        (
            "/candidateEventCandidates/0/action/args/intentName",
            "EVENT_ARGUMENT_SCHEMA_INVALID",
            "固定事件参数与注册表动作模板不一致。",
            "固定值 CallPhone",
        ),
    ],
)
def test_type_enum_and_fixed_value_errors_only_state_the_effective_constraint(
    path,
    code,
    reason,
    expected,
):
    issue = {
        "path": path,
        "code": code,
        "message": reason,
        "expected": expected,
        "repairInstruction": "按 expected 和本轮 Schema 修正该字段。",
    }
    view = agent_error_view({"details": {"issues": [issue]}}, "失败")
    issues = view.get("issues")
    assert isinstance(issues, list) and len(issues) == 1
    text = issues[0].get("message", "")
    assert "要求：" not in text and "按上述要求" not in text
    assert expected.removeprefix("JSON 字符串；") in text
    assert len(text) < 90


def test_range_feedback_keeps_bounds_and_core_requirement_boundary_without_repeating_action():
    issue = {
        "path": "/candidateDataBindings/0/arguments/limit",
        "code": "DATA_ARGUMENT_SCHEMA_INVALID",
        "message": "数值大于 schema 允许的最大值。",
        "expected": "JSON 类型 integer；取值范围 1 至 5",
        "repairInstruction": (
            "将参数调整到 expected 范围；若这会改变用户核心要求，"
            "停止生成并说明当前能力范围，不要静默降级。"
        ),
    }
    view = agent_error_view({"details": {"issues": [issue]}}, "失败")
    issues = view.get("issues")
    assert isinstance(issues, list) and len(issues) == 1
    text = issues[0].get("message", "")
    assert "取值范围 1 至 5" in text
    assert "停止生成" in text and "不要静默降级" in text
    assert "expected" not in text and "将参数调整到" not in text


def test_unsupported_title_on_another_tool_is_not_mistaken_for_create_metadata_null():
    issue = {
        "path": "/title", "code": "REQUEST_EXTRA_FORBIDDEN",
        "actualType": "null", "message": "此位置包含未声明字段。",
    }
    view = agent_error_view({"details": {"issues": [issue]}}, "失败")
    issues = view.get("issues")
    assert isinstance(issues, list) and len(issues) == 1
    assert issues[0].get("message") == "不支持字段 title，请移除该字段。"
