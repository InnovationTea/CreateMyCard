"""验证主 Agent 获得可执行的纠错依据及明确的终态边界。"""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.routes import _error_details, _error_explanation
from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from services.agent_feedback import request_validation_feedback
from services.widget_generation_service import WidgetGenerationService
from start_websocket_server import app
from ws_response_parser import parse_legacy_stream_content


def _arguments():
    return {
        "uid": "agent-feedback-test",
        "device": {"romVersion": "7.0"},
        "userQuery": "展示我的日程",
        "title": "日程",
        "description": "日程安排",
    }


def _receive_result(websocket):
    while True:
        response = websocket.receive_json()
        reply = response.get("reply")
        assert isinstance(reply, dict)
        stream = reply.get("streamInfo")
        assert isinstance(stream, dict)
        if stream.get("streamType") != "final":
            continue
        content = stream.get("streamContent")
        assert isinstance(content, str)
        return parse_legacy_stream_content(content)


def test_missing_create_metadata_reports_both_field_paths():
    arguments = _arguments()
    arguments.pop("title")
    arguments.pop("description")
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    feedback = request_validation_feedback(caught.value, "generateWidgetCardCompactDsl")
    issues = feedback.get("issues")
    assert isinstance(issues, list)
    assert {issue.get("path") for issue in issues} == {"/title", "/description"}
    assert all(issue.get("repairInstruction") for issue in issues)


def test_feedback_excludes_raw_values_and_preserves_enum_constraint():
    arguments = _arguments()
    arguments.update(size="secret-invalid-size", unknownValue="secret-token")
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    feedback = request_validation_feedback(caught.value, "generateWidgetCardCompactDsl")
    serialized = json.dumps(feedback, ensure_ascii=False)
    assert "secret-invalid-size" not in serialized
    assert "secret-token" not in serialized
    assert "2x2" in serialized and "2x4" in serialized
    assert feedback.get("retryable") is True


def test_missing_transport_context_is_not_an_instruction_to_guess_identity():
    arguments = _arguments()
    arguments.pop("uid")
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    feedback = request_validation_feedback(caught.value, "generateWidgetCardCompactDsl")
    assert feedback.get("retryable") is False
    assert feedback.get("requiredActions") == ["STOP"]


def test_internal_validation_is_not_presented_as_correctable_request_error():
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**_arguments(), size="invalid")
    details = _error_details(
        caught.value,
        "generateWidgetCardCompactDsl",
        request_validated=True,
    )
    assert isinstance(details, dict)
    assert details.get("stage") == "serviceValidation"
    assert details.get("retryable") is False
    assert "issues" not in details


def test_corrected_request_can_be_retried_without_reaching_generation_on_first_call(monkeypatch):
    calls = []

    async def generate(_service, request, **_kwargs):
        calls.append(request)
        return GenerateWidgetCardResponse(
            status="success",
            suggestSize="2x2",
            message="成功",
            artifactUrl="https://artifact.test/corrected",
        )

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    arguments = _arguments()
    arguments["dataCapabilityIds"] = ["GetCalendarEvents"]
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({"arguments": arguments})
        rejected = _receive_result(websocket)
        details = rejected
        assert details.get("retryable") is True
        assert "candidateDataBindings" in json.dumps(details)
        assert not calls
        arguments.pop("dataCapabilityIds")
        arguments["candidateDataBindings"] = [
            {
                "capabilityId": "GetCalendarEvents",
                "arguments": {},
                "writeResultTo": "/data/calendar",
            }
        ]
        websocket.send_json({"arguments": arguments})
        accepted = _receive_result(websocket)
    assert accepted.get("status") == "success"
    assert len(calls) == 1
    assert calls[0].candidateDataBindings


@pytest.mark.parametrize(
    "status,code",
    [
        ("failed", "VALIDATION_FAILED"),
        ("unsupported", "WIDGET_EDIT_UNSUPPORTED"),
    ],
)
def test_business_failure_has_explicit_stop_feedback(monkeypatch, status, code):
    async def generate(_service, _request, **_kwargs):
        return GenerateWidgetCardResponse(
            status=status,
            errorCode=code,
            suggestSize="2x2",
            message="内部说明",
        )

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({"arguments": _arguments()})
        result = _receive_result(websocket)
    details = result
    assert details.get("retryable") is False
    assert details.get("requiredActions") == ["STOP"]


@pytest.mark.parametrize(
    "code",
    [
        "TIMEOUT",
        "ARTIFACT_UPLOAD_FAILED",
        "PROTOCOL_CAPABILITY_UNSUPPORTED",
        "WIDGET_EDIT_DISABLED",
        "SOURCE_ARTIFACT_INVALID",
        "SOURCE_ARTIFACT_NOT_FOUND",
        "FAILED",
    ],
)
def test_terminal_explanations_do_not_authorize_automatic_retry_or_new_creation(code):
    explanation = _error_explanation(code)
    assert "停止" in explanation
    assert "建议稍后重试" not in explanation
    assert "请重新创建" not in explanation


def test_omitted_requirements_are_only_present_when_there_are_real_omissions():
    common = {"status": "degraded", "suggestSize": "2x2", "message": "部分满足"}
    response = GenerateWidgetCardResponse(**common, omittedRequirements=["补充背景"])
    assert response.model_dump(mode="json").get("omittedRequirements") == ["补充背景"]
    assert "omittedRequirements" not in GenerateWidgetCardResponse(**common).model_dump(mode="json")


def _feedback(patch):
    arguments = _arguments()
    arguments.update(patch)
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    return request_validation_feedback(caught.value, "generateWidgetCardCompactDsl")


def _issue_at(feedback, path):
    issues = feedback.get("issues")
    assert isinstance(issues, list)
    matches = []
    for issue in issues:
        if issue.get("path") == path:
            matches.append(issue)
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(
    "patch,path,actual_type,expected,source",
    [
        (
            {"candidateDataBindings": "[]"},
            "/candidateDataBindings",
            "string",
            "数组",
            "getDataCapabilitySchemas",
        ),
        (
            {"candidateDataBindings": ["a"]},
            "/candidateDataBindings/0",
            "string",
            "对象",
            "getDataCapabilitySchemas",
        ),
        (
            {"candidateDataBindings": [{}]},
            "/candidateDataBindings/0/capabilityId",
            "missing",
            "ID",
            "getWidgetCapabilityOverview.dataCapabilities",
        ),
        (
            {
                "candidateDataBindings": [
                    {"capabilityId": "a", "writeResultTo": "/data/a", "arguments": "{}"}
                ]
            },
            "/candidateDataBindings/0/arguments",
            "string",
            "对象",
            "inputSchema",
        ),
        (
            {
                "candidateDataBindings": [
                    {
                        "capabilityId": "a",
                        "writeResultTo": "/data/a",
                        "candidateOutputFields": [123],
                    }
                ]
            },
            "/candidateDataBindings/0/candidateOutputFields/0",
            "integer",
            "字符串",
            "outputSchema",
        ),
        (
            {"candidateEventCandidates": {}},
            "/candidateEventCandidates",
            "object",
            "数组",
            "getWidgetCapabilityOverview.eventCapabilities",
        ),
        (
            {"candidateEventCandidates": ["a"]},
            "/candidateEventCandidates/0",
            "string",
            "对象",
            "getWidgetCapabilityOverview.eventCapabilities",
        ),
        (
            {"candidateEventCandidates": [{"capabilityId": "a", "action": {"args": {}}}]},
            "/candidateEventCandidates/0/action/call",
            "missing",
            "call",
            "actionTemplate",
        ),
        (
            {
                "candidateEventCandidates": [
                    {"capabilityId": "a", "action": {"call": "a", "args": []}}
                ]
            },
            "/candidateEventCandidates/0/action/args",
            "array",
            "对象",
            "dynamicArguments",
        ),
        (
            {"candidateAssetIds": [{"id": "a"}]},
            "/candidateAssetIds/0",
            "object",
            "字符串",
            "getWidgetCapabilityOverview.assetCandidates",
        ),
        ({"title": True}, "/title", "boolean", "字符串", "当前工具 Schema"),
        (
            {"options": {"allowDegradation": "secret-not-a-bool"}},
            "/options/allowDegradation",
            "string",
            "布尔",
            "当前工具 Schema",
        ),
    ],
)
def test_feedback_explains_structure_type_and_authoritative_source(
    patch,
    path,
    actual_type,
    expected,
    source,
):
    feedback = _feedback(patch)
    issue = _issue_at(feedback, path)
    assert issue.get("actualType") == actual_type
    assert expected in issue.get("expected", "")
    assert source in issue.get("referenceSource", "")
    assert "invoke.arguments" in feedback.get("agentInstruction", "")
    assert issue.get("retryable") is True
    assert "secret-not-a-bool" not in json.dumps(feedback)


@pytest.mark.parametrize(
    "name,replacement",
    [
        ("dataCapabilityIds", "candidateDataBindings"),
        ("eventCapabilityIds", "candidateEventCandidates"),
    ],
)
def test_id_list_error_names_the_complete_replacement_object(name, replacement):
    feedback = _feedback({name: ["a"]})
    issue = _issue_at(feedback, f"/{name}")
    assert replacement in issue.get("repairInstruction", "")
    assert "capabilityId" in issue.get("expected", "")
    instruction = feedback.get("agentInstruction", "")
    assert ("权限" in instruction) is (name == "dataCapabilityIds")


@pytest.mark.parametrize(
    "path,source,forbidden",
    [
        (("candidateDataBindings", 0, "arguments", "actionTemplate"), "inputSchema", "放入 action"),
        (("candidateDataBindings", 0, "arguments", "size"), "inputSchema", "2x2"),
        (
            ("candidateEventCandidates", 0, "action", "args", "capabilityId"),
            "dynamicArguments",
            "放回候选项外层",
        ),
        (
            ("candidateEventCandidates", 0, "action", "args", "sourceArtifactUrl"),
            "dynamicArguments",
            "切换创建",
        ),
    ],
)
def test_identical_business_keys_do_not_receive_top_level_repair_rules(path, source, forbidden):
    error = ValidationError.from_exception_data(
        "Scope",
        [
            {
                "type": "extra_forbidden",
                "loc": path,
                "input": "secret-business-value",
            }
        ],
    )
    feedback = request_validation_feedback(error, "generateWidgetCardCompactDsl")
    issue = _issue_at(feedback, "/" + "/".join(str(part) for part in path))
    assert source in issue.get("referenceSource", "")
    assert forbidden not in issue.get("repairInstruction", "")
    assert "secret-business-value" not in json.dumps(feedback)


def test_misplaced_event_definition_has_complete_non_destructive_repair_guidance():
    feedback = _feedback(
        {
            "candidateEventCandidates": [
                {
                    "actionTemplate": {"id": "a", "call": "b", "args": {}, "dynamicArguments": []},
                }
            ]
        }
    )
    identifier = _issue_at(feedback, "/candidateEventCandidates/0/capabilityId")
    action = _issue_at(feedback, "/candidateEventCandidates/0/action")
    definition = _issue_at(feedback, "/candidateEventCandidates/0/actionTemplate")
    assert identifier.get("referenceSource") == "getWidgetCapabilityOverview.eventCapabilities[].id"
    assert "核对" in identifier.get("repairInstruction", "")
    assert "call、args" in action.get("repairInstruction", "")
    assert "不把整个事件定义" in definition.get("repairInstruction", "")
    instruction = feedback.get("agentInstruction", "")
    assert "完整 invoke.arguments" in instruction
    assert "先修外层结构" in instruction
    assert "未列出的问题不代表已通过后续检查" in instruction


def test_custom_validator_message_and_context_are_not_echoed_to_agent():
    error = ValidationError.from_exception_data(
        "Private",
        [
            {
                "type": "value_error",
                "loc": ("title",),
                "input": "secret-input",
                "ctx": {"error": ValueError("secret-validator-value")},
            }
        ],
    )
    feedback = request_validation_feedback(error, "generateWidgetCardCompactDsl")
    serialized = json.dumps(feedback, ensure_ascii=False)
    assert "secret-input" not in serialized
    assert "secret-validator-value" not in serialized
    assert "ctx" not in serialized
    issue = _issue_at(feedback, "/title")
    assert issue.get("actualType") == "string"
    assert issue.get("repairInstruction")


def test_edit_source_null_never_advises_omitting_source_to_create():
    feedback = _feedback({"sourceArtifactUrl": None})
    issue = _issue_at(feedback, "/sourceArtifactUrl")
    assert "省略继承" not in issue.get("repairInstruction", "")
    assert "不猜地址" in issue.get("repairInstruction", "")
    assert "切换创建" in issue.get("repairInstruction", "")


def test_transport_failure_is_not_an_instruction_to_rebuild_a_packet():
    error = ValidationError.from_exception_data(
        "Transport",
        [
            {
                "type": "missing",
                "loc": ("session", "sessionId"),
                "input": {},
            }
        ],
    )
    feedback = request_validation_feedback(error, "generateWidgetCardCompactDsl")
    assert feedback.get("retryable") is False
    assert feedback.get("requiredActions") == ["STOP"]
    issue = _issue_at(feedback, "/session/sessionId")
    assert "不要手工填写" in issue.get("repairInstruction", "")


@pytest.mark.parametrize("wrapper", ["arguments", "params", "content"])
def test_business_object_wrappers_are_correctable_without_rebuilding_transport(wrapper):
    feedback = _feedback({wrapper: {"userQuery": "secret-nested-query"}})
    issue = _issue_at(feedback, f"/{wrapper}")
    assert feedback.get("retryable") is True
    assert "invoke.arguments 直接包含" in issue.get("expected", "")
    assert "不要再次包" in issue.get("repairInstruction", "")
    assert "secret-nested-query" not in json.dumps(feedback)


def test_logged_envelope_errors_guide_agent_to_resubmit_business_object(monkeypatch):
    from services.capability_registry import CapabilityRegistry

    calls = []

    async def generate(_service, request, **_kwargs):
        calls.append(request)
        return GenerateWidgetCardResponse(
            status="success",
            suggestSize="2x2",
            message="成功",
            artifactUrl="https://artifact.test/fixed-envelope",
        )

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    event = registry.get_event_capability("event.open.clock.alarm")
    assert event is not None
    action = event.actionTemplate.model_dump(mode="json")
    content = {
        "userQuery": "闹钟入口卡片",
        "title": "闹钟",
        "description": "打开闹钟",
        "candidateEventCandidates": [{"actionTemplate": {"id": event.id, **action}}],
    }
    payload = {
        **content,
        "content": content,
        "deviceInfo": {"prdVer": "11.7.8.353", "romVersion": "7.0", "locale": "zh-CN"},
        "session": {"sessionId": "agent-feedback", "interactionId": "1"},
        "userAuth": {"user": {"userId": "test"}},
        "utterance": {"original": ""},
    }
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(payload)
        rejected = _receive_result(websocket)
        details = rejected
        assert not calls
        issue = _issue_at(details, "/candidateEventCandidates/0/capabilityId")
        assert "本轮事件概述" in issue.get("message", "")
        content["candidateEventCandidates"] = [{"capabilityId": event.id, "action": action}]
        payload["content"] = content
        # 外层旧镜像不覆盖已修正的 content；主 Agent 不需要承担镜像构造职责。
        websocket.send_json(payload)
        accepted = _receive_result(websocket)
    assert accepted.get("status") == "success"
    assert len(calls) == 1
    assert calls[0].candidateEventCandidates


@pytest.mark.parametrize("transport_only", [False, True])
def test_stringified_feedback_targets_agent_call_not_internal_packet(transport_only):
    from api.routes import StringifiedToolArgumentsError

    details = StringifiedToolArgumentsError(transport_only=transport_only).details()
    assert details.get("modelCalled") is False
    assert details.get("retryable") is True
    instruction = details.get("agentInstruction", "")
    assert "invoke.arguments" in instruction
    assert "当前工具" in instruction or "运行时约定" in instruction
    assert "functionName、skillName 同层" not in instruction
    issues = details.get("issues")
    assert isinstance(issues, list)
    assert len(issues) == 1
    repair = issues[0].get("repairInstruction", "")
    assert "提升到 content" not in repair
    assert "完整业务" in repair


def test_malformed_transport_does_not_authorize_agent_to_patch_wire_json(monkeypatch):
    async def unexpected_generate(*_args, **_kwargs):
        pytest.fail("malformed transport must not reach generation")

    monkeypatch.setattr(
        WidgetGenerationService,
        "generate_widget_card_compact_dsl",
        unexpected_generate,
    )
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_text('{"secret-request-value":')
        result = _receive_result(websocket)
    details = result
    assert details.get("retryable") is False
    assert details.get("requiredActions") == ["STOP"]
    assert "停止本轮自动调用" in details.get("agentInstruction", "")
    assert "secret-request-value" not in json.dumps(result)


@pytest.mark.parametrize("name", ["title", "description"])
@pytest.mark.parametrize(
    "kind,actual_type,message",
    [
        ("missing", "missing", "缺少必填字段"),
        ("null", "null", "不能为 null"),
        ("empty", "string", "字符串长度不足"),
        ("object", "object", "JSON 类型不符合要求"),
    ],
)
def test_create_metadata_feedback_distinguishes_missing_null_empty_and_type(
    name, kind, actual_type, message,
):
    arguments = _arguments()
    if kind == "missing":
        arguments.pop(name)
    elif kind == "null":
        arguments[name] = None
    elif kind == "empty":
        arguments[name] = ""
    else:
        arguments[name] = {"private": "secret-value"}
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = _error_details(
        caught.value, "generateWidgetCardCompactDsl", request_arguments=arguments,
    )
    assert isinstance(details, dict)
    issue = _issue_at(details, f"/{name}")
    assert issue.get("actualType") == actual_type
    assert message in issue.get("message", "")
    assert "secret-value" not in json.dumps(details)
    assert details.get("retryable") is True


def test_custom_missing_metadata_without_original_request_does_not_claim_explicit_null():
    arguments = _arguments()
    arguments.pop("title")
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    details = request_validation_feedback(caught.value, "generateWidgetCardCompactDsl")
    issue = _issue_at(details, "/title")
    assert issue.get("actualType") == "unknown"
    assert "非空 title 字符串" in issue.get("message", "")


def test_websocket_missing_create_metadata_has_precise_diagnosis(monkeypatch):
    async def unexpected_generate(*_args, **_kwargs):
        pytest.fail("incomplete metadata must not reach generation")

    monkeypatch.setattr(
        WidgetGenerationService, "generate_widget_card_compact_dsl", unexpected_generate,
    )
    arguments = _arguments()
    arguments.pop("title")
    arguments.pop("description")
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({"arguments": arguments})
        result = _receive_result(websocket)
    details = result
    for name in ("title", "description"):
        issue = _issue_at(details, f"/{name}")
        assert "须填写非空字符串" in issue.get("message", "")


def test_stringified_request_reports_confirmed_inner_issues_without_trace(monkeypatch):
    from api import routes
    from config.config import get_settings

    logs = []
    monkeypatch.setattr(get_settings(), "enable_compact_dsl_argument_repair_fallback", False)
    monkeypatch.setattr(routes.logger, "info", logs.append)
    monkeypatch.setattr(routes, "trace_record", lambda *_args, **_kwargs: None)
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({
            "content": {"arguments": json.dumps({"userQuery": "secret-original-query"})},
            "deviceInfo": {"prdVer": "11.7.8.353", "romVersion": "7.0"},
        })
        result = _receive_result(websocket)
    details = result
    assert details.get("retryable") is True
    assert details.get("requiredActions") == ["FIX_AND_RETRY"]
    assert "diagnostic" not in details
    for name in ("title", "description"):
        issue = _issue_at(details, f"/{name}")
        assert "须填写非空字符串" in issue.get("message", "")
        assert "agentAction" not in issue and "retryable" not in issue
    assert "secret-original-query" not in json.dumps(details)
    rejection_logs = [entry for entry in logs if "deterministic_argument_repair_rejected" in entry]
    assert len(rejection_logs) == 1
    assert "/title" in rejection_logs[0] and "/description" in rejection_logs[0]
    assert "\n" not in rejection_logs[0]


def test_model_recovery_exhaustion_preserves_diagnosis_and_does_not_authorize_retry(monkeypatch):
    from api import routes
    from config.config import get_settings
    from services.compact_dsl_argument_repair import CompactDslArgumentRepairExhaustedError

    diagnostic = {
        "stage": "requestValidation",
        "issues": [{"code": "REQUEST_VALUE_ERROR", "path": "/title", "message": "缺少标题"}],
    }

    async def exhausted(*_args, **_kwargs):
        raise CompactDslArgumentRepairExhaustedError(
            "secret-internal-exception", diagnostic=diagnostic, attempts=2,
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_compact_dsl_argument_repair_fallback", True)
    monkeypatch.setattr(settings, "compact_dsl_argument_repair_reminder_count", 0)
    monkeypatch.setattr(routes, "recover_compact_dsl_content", exhausted)
    logs = []
    monkeypatch.setattr(routes.logger, "error", logs.append)
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({
            "content": {"arguments": "broken"},
            "deviceInfo": {"prdVer": "11.7.8.353", "romVersion": "7.0"},
            "session": {"sessionId": "feedback-exhausted", "interactionId": "1"},
        })
        result = _receive_result(websocket)
    details = result
    assert "diagnostic" not in details
    assert "repairAttempts" not in details
    assert details.get("retryable") is False
    assert details.get("requiredActions") == ["NOTIFY_USER"]
    assert "停止本轮自动调用" in details.get("agentInstruction", "")
    assert "secret-internal-exception" not in json.dumps(result)
    failure_logs = [entry for entry in logs if "compact_dsl_argument_repair_failed" in entry]
    assert len(failure_logs) == 1
    assert '"repairAttempts":2' in failure_logs[0]
    assert "will_retry=false" in failure_logs[0]
    assert "\n" not in failure_logs[0]


def test_preflight_keeps_precise_constraint_and_points_to_agent_business_object():
    from models.preflight import GenerationPreflightError
    from services.capability_registry import CapabilityRegistry
    from services.edit_request_normalizer import EditRequestNormalizer
    from services.generation_preflight import GenerationPreflight

    request = GenerateWidgetCardRequest(
        **_arguments(),
        candidateDataBindings=[
            {
                "capabilityId": "ViewWeather",
                "arguments": {"forecastDays": "secret-number"},
                "writeResultTo": "/data/weather",
            }
        ],
    )
    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    preflight = GenerationPreflight(registry).run(EditRequestNormalizer.normalize_create(request))
    assert preflight.blocking_issues
    details = GenerationPreflightError(preflight).details()
    issue = _issue_at(details, "/candidateDataBindings/0/arguments/forecastDays")
    assert issue.get("actualType") == "string"
    assert "integer" in issue.get("expected", "")
    assert "inputSchema" in issue.get("referenceSource", "")
    assert details.get("requiredActions") == ["FIX_AND_RETRY"]
    assert "invoke.arguments" in details.get("agentInstruction", "")
    assert "完整 invoke.arguments" in details.get("agentInstruction", "")
    assert "secret-number" not in json.dumps(details)


def test_mother_care_feedback_is_concise_and_keeps_all_control_fields(monkeypatch):
    async def unexpected_generate(*_args, **_kwargs):
        pytest.fail("missing metadata must stop before generation")

    monkeypatch.setattr(
        WidgetGenerationService, "generate_widget_card_compact_dsl", unexpected_generate,
    )
    arguments = {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": (
            "创建一个妈妈关怀卡片，常驻地在深圳，显示实时温度与空气质量，还能一键打电话给妈妈"
        ),
        "candidateEventCandidates": [
            {
                "capabilityId": "event.call.phone",
                "action": {
                    "call": "clickToApi",
                    "args": {"intentName": "CallPhone", "params": {"phoneNumber": ""}},
                },
            },
            {
                "capabilityId": "event.open.weather",
                "action": {
                    "call": "clickToDeeplink",
                    "args": {
                        "intentName": "Weather_CityCode", "bundleName": "", "abilityName": "",
                        "uri": (
                            "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode='"
                            " + ${/data/weather/location/cityCode} }}"
                        ),
                    },
                },
            },
        ],
    }
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({
            "content": arguments,
            "deviceInfo": {"prdVer": "11.7.8.353", "romVersion": "7.0", "locale": "zh-CN"},
            "session": {"sessionId": "mother-care-replay", "interactionId": "1"},
            "userAuth": {"user": {"userId": "local-replay-user"}},
        })
        response = websocket.receive_json()
    assert response.get("errorCode") == "0"
    reply = response.get("reply")
    assert isinstance(reply, dict)
    stream_info = reply.get("streamInfo")
    assert isinstance(stream_info, dict)
    content = stream_info.get("streamContent")
    assert isinstance(content, str)
    assert len(content) < 350
    details = json.loads(content)
    assert set(details) == {
        "message", "retryable", "requiredActions", "agentInstruction", "issues",
    }
    assert details.get("retryable") is True
    assert details.get("requiredActions") == ["FIX_AND_RETRY"]
    assert len(details.get("agentInstruction", "")) < 80
    for name in ("title", "description"):
        issue = _issue_at(details, f"/{name}")
        assert set(issue) == {
            "path", "message",
        }
        assert "须填写非空字符串" in issue.get("message", "")
        assert "编辑" not in issue.get("message", "")
    instruction = details.get("agentInstruction", "")
    assert "权限" not in instruction and "传输" not in instruction


@pytest.mark.parametrize("has_warning", [False, True])
@pytest.mark.parametrize("retryable", [False, True])
def test_preflight_text_matches_actions_and_only_explains_present_warnings(has_warning, retryable):
    from models.preflight import (
        AgentAction,
        GenerationPreflightError,
        GenerationPreflightResult,
        PreflightIssue,
    )

    issue = PreflightIssue(
        code="TEST", path="/candidateAssetIds/0", message="素材不可用",
        agentAction=AgentAction.FIX_AND_RETRY if retryable else AgentAction.STOP,
        retryable=retryable,
    )
    result = GenerationPreflightResult(
        effective_bindings=(), effective_data_capabilities=(), effective_events=(),
        effective_assets=(), removed_capabilities=(), blocking_issues=(issue,),
        warnings=(issue,) if has_warning else (), card_spec=None, task_spec=None,
    )
    details = GenerationPreflightError(result).details()
    assert details.get("retryable") is retryable
    assert details.get("requiredActions") == ["FIX_AND_RETRY" if retryable else "STOP"]
    assert details.get("issues") == [issue.model_dump(mode="json")]
    instruction = details.get("agentInstruction", "")
    assert ("重试" in instruction) is retryable
    assert ("停止" in instruction) is not retryable
    assert ("warnings" in instruction) is has_warning
    assert "权限" not in instruction
    assert len(instruction) < 110
