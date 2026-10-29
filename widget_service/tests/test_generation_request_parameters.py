"""生成入口不得把错传的能力 ID 列表静默当作空候选。"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.schemas import (
    CandidateEventCandidate,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    GenerateWidgetCardResponse,
    WidgetCardServiceRequest,
)
from services.capability_registry import CapabilityRegistry
from services.generation_preflight import GenerationPreflight, _closed_argument_schema
from services.widget_generation_service import WidgetGenerationService
from start_websocket_server import app
from ws_response_parser import parse_legacy_stream_content


def _generation_arguments():
    return {
        "uid": "parameter-validation",
        "device": {"romVersion": "7.0"},
        "userQuery": "展示今天的日程",
        "title": "今日日程",
        "description": "日程安排",
    }


@pytest.mark.parametrize("operation", [
    None, "generateWidgetCard", "generateWidgetCardCompactDsl", "generateWidgetCardTerseDslNested2",
])
@pytest.mark.parametrize("is_edit", [False, True])
@pytest.mark.parametrize("name,replacement", [
    ("dataCapabilityIds", "candidateDataBindings"),
    ("eventCapabilityIds", "candidateEventCandidates"),
])
@pytest.mark.parametrize("value", [[], None, ["test-capability"]])
def test_generation_rejects_explicit_id_lists(operation, is_edit, name, replacement, value):
    arguments = _generation_arguments()
    arguments[name] = value
    if is_edit:
        arguments["sourceArtifactUrl"] = "https://artifact.test/source"
    request_type = GenerateWidgetCardRequest
    if operation is not None:
        arguments["operation"] = operation
        request_type = WidgetCardServiceRequest
    with pytest.raises(ValidationError) as caught:
        request_type(**arguments)
    assert name in str(caught.value)
    assert replacement in str(caught.value)


def test_generation_reports_both_misplaced_fields_with_valid_candidates():
    arguments = _generation_arguments()
    arguments.update({
        "dataCapabilityIds": ["GetCalendarEvents"],
        "eventCapabilityIds": ["event.viewCalendarEvent"],
        "candidateDataBindings": [{
            "capabilityId": "GetCalendarEvents",
            "arguments": {},
            "writeResultTo": "/data/calendar",
        }],
        "candidateEventCandidates": [],
    })
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**arguments)
    assert "dataCapabilityIds" in str(caught.value)
    assert "eventCapabilityIds" in str(caught.value)


def test_schema_query_still_accepts_data_capability_ids():
    arguments = _generation_arguments()
    arguments["dataCapabilityIds"] = ["GetCalendarEvents"]
    arguments.update({
        "skillName": "harmony-card-generation-online", "functionName": "getDataCapabilitySchemas",
        "bundleName": "com.omega_w_0823.hmservice", "requestId": "correlation-only",
    })
    direct = DataCapabilitySchemasRequest(**arguments)
    unified = WidgetCardServiceRequest(operation="getDataCapabilitySchemas", **arguments)
    assert direct.dataCapabilityIds == ["GetCalendarEvents"]
    assert unified.dataCapabilityIds == direct.dataCapabilityIds
    assert unified.operation == "getDataCapabilitySchemas"
    assert "skillName" not in unified.model_dump(mode="json")


@pytest.mark.parametrize("operation", [None, "generateWidgetCardCompactDsl"])
@pytest.mark.parametrize("has_data", [False, True])
def test_legal_static_and_dynamic_generation_requests_remain_valid(operation, has_data):
    arguments = _generation_arguments()
    arguments["bundleName"] = "com.omega_w_0823.hmservice"
    arguments["functionName"] = "getDataCapabilitySchemas"
    arguments["candidateDataBindings"] = []
    if has_data:
        arguments["candidateDataBindings"] = [{
            "capabilityId": "GetCalendarEvents",
            "arguments": {},
            "writeResultTo": "/data/calendar",
        }]
    request_type = GenerateWidgetCardRequest
    if operation is not None:
        arguments["operation"] = operation
        request_type = WidgetCardServiceRequest
    request = request_type(**arguments)
    assert bool(request.candidateDataBindings) is has_data
    assert "functionName" not in request.model_dump(mode="json")
    if operation is not None:
        assert request.operation == operation


@pytest.mark.parametrize("operation", [
    None, "generateWidgetCard", "generateWidgetCardCompactDsl", "generateWidgetCardTerseDslNested2",
])
@pytest.mark.parametrize("value", ["generateWidgetCardCompactDsl", "otherRoute", None, []])
@pytest.mark.parametrize("name", ["bundleName", "functionName", "skillName", "requestId"])
def test_route_metadata_is_discarded_without_mutating_original_arguments(operation, value, name):
    arguments = _generation_arguments()
    arguments[name] = value
    request_type = GenerateWidgetCardRequest
    if operation is not None:
        arguments["operation"] = operation
        request_type = WidgetCardServiceRequest
    request = request_type(**arguments)
    assert name not in request.model_dump(mode="json")
    assert arguments.get(name) == value
    assert request.userQuery == arguments.get("userQuery")
    if operation is not None:
        assert request.operation == operation


@pytest.mark.parametrize("shape", ["enveloped", "arguments", "flat"])
def test_websocket_ignores_route_metadata_and_uses_actual_endpoint(monkeypatch, shape):
    calls = []

    async def generate(_service, request, **_kwargs):
        calls.append(request)
        return GenerateWidgetCardResponse(
            status="success", suggestSize="2x2", message="成功",
            artifactUrl="https://artifact.test/route-metadata",
        )

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    arguments = _generation_arguments()
    arguments.update({
        "functionName": "getDataCapabilitySchemas", "skillName": "another-skill",
        "bundleName": "com.omega_w_0823.hmservice", "requestId": "embedded-ignored",
    })
    expected_request_id = "actual-request"
    if shape == "enveloped":
        payload = {
            "content": arguments, "deviceInfo": {"romVersion": "7.0"},
            "session": {"sessionId": "actual-session", "interactionId": "actual-turn"},
        }
        expected_request_id = "actual-session&actual-turn"
    elif shape == "arguments":
        payload = {"requestId": expected_request_id, "arguments": arguments}
    else:
        arguments["requestId"] = expected_request_id
        payload = arguments
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(payload)
        while True:
            response = websocket.receive_json()
            reply = response.get("reply")
            assert isinstance(reply, dict)
            stream = reply.get("streamInfo")
            assert isinstance(stream, dict)
            if stream.get("streamType") == "final":
                break
    content = stream.get("streamContent")
    assert isinstance(content, str)
    result = parse_legacy_stream_content(content)
    assert result.get("status") == "success"
    assert result.get("operation") == "generateWidgetCardCompactDsl"
    assert result.get("requestId") == expected_request_id
    assert len(calls) == 1
    assert not {"bundleName", "functionName", "skillName", "requestId"}.intersection(
        calls[0].model_dump(mode="json")
    )


@pytest.mark.parametrize("enveloped", [False, True])
@pytest.mark.parametrize("name", [
    "dataCapabilityIds", "eventCapabilityIds", "unexpectedField", "dataCapabilities",
])
@pytest.mark.parametrize("value", [[], None, ["test-capability"]])
def test_websocket_rejects_undeclared_fields_before_preflight(
    monkeypatch, enveloped, name, value,
):
    def unexpected_preflight(*_args, **_kwargs):
        pytest.fail("未声明字段不得进入预检或静态生成")

    monkeypatch.setattr(GenerationPreflight, "run", unexpected_preflight)
    arguments = _generation_arguments()
    arguments[name] = value
    if enveloped:
        payload = {
            "content": arguments,
            "deviceInfo": {"romVersion": "7.0"},
        }
    else:
        payload = {"arguments": arguments}
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json(payload)
        response = websocket.receive_json()
    reply = response.get("reply")
    assert isinstance(reply, dict)
    stream = reply.get("streamInfo")
    assert isinstance(stream, dict)
    assert stream.get("streamType") == "final"
    content = stream.get("streamContent")
    assert isinstance(content, str)
    error = parse_legacy_stream_content(content)
    assert name in content
    details = error
    assert details.get("retryable") is True
    assert details.get("requiredActions") == ["FIX_AND_RETRY"]
    issues = details.get("issues")
    assert isinstance(issues, list)
    assert any(issue.get("path") == f"/{name}" for issue in issues)
    assert all(issue.get("message") for issue in issues)


@pytest.mark.parametrize("operation", [None, "generateWidgetCardCompactDsl"])
@pytest.mark.parametrize("is_edit", [False, True])
@pytest.mark.parametrize("name", ["mysteryFlag", "dataCapabilities", "candidateDataBinding"])
def test_generation_rejects_unknown_fields(operation, is_edit, name):
    arguments = _generation_arguments()
    arguments.update({
        "bundleName": "tool-bundle", "functionName": "tool-name",
        "skillName": "skill-name", "requestId": "correlation-only",
    })
    arguments[name] = None
    if is_edit:
        arguments["sourceArtifactUrl"] = "https://artifact.test/source"
    request_type = GenerateWidgetCardRequest
    if operation is not None:
        arguments["operation"] = operation
        request_type = WidgetCardServiceRequest
    with pytest.raises(ValidationError) as caught:
        request_type(**arguments)
    errors = caught.value.errors(include_context=False, include_input=False)
    assert any(error.get("loc") == (name,) for error in errors)
    assert any(error.get("type") == "extra_forbidden" for error in errors)


def test_candidate_action_rejects_unknown_fields_without_changing_artifact_model():
    from models.generation import EventAction

    action = {"call": "testCall", "args": {}, "mysteryFlag": True}
    with pytest.raises(ValidationError, match="mysteryFlag"):
        CandidateEventCandidate(capabilityId="test-event", action=action)
    # 来源产物仍使用原兼容模型，不因本轮请求校验收紧而无法读取。
    assert EventAction(**action).call == "testCall"


@pytest.mark.parametrize("name", [
    "unknownFilter", "bundleName", "functionName", "skillName", "requestId",
])
def test_unknown_data_argument_reports_exact_location(name):
    request = GenerateWidgetCardRequest(
        **_generation_arguments(),
        candidateDataBindings=[{
            "capabilityId": "GetCalendarEvents",
            "arguments": {name: "today"},
            "writeResultTo": "/data/calendar",
        }],
    )
    from services.edit_request_normalizer import EditRequestNormalizer

    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    result = GenerationPreflight(registry).run(EditRequestNormalizer.normalize_create(request))
    assert result.blocking_issues
    issue = result.blocking_issues[0].model_dump(mode="json")
    assert issue.get("code") == "DATA_ARGUMENT_SCHEMA_INVALID"
    assert issue.get("path") == f"/candidateDataBindings/0/arguments/{name}"


@pytest.mark.parametrize("extensions", [None, True, {"type": "string"}])
def test_argument_schema_closes_nested_objects_without_mutating_registry(extensions):
    from copy import deepcopy

    from jsonschema import Draft202012Validator

    nested = {"type": "object", "properties": {"name": {"type": "string"}}}
    if extensions is not None:
        nested["additionalProperties"] = extensions
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": nested}},
    }
    original = deepcopy(schema)
    closed = _closed_argument_schema(schema)
    validator = Draft202012Validator(closed)
    unknown = {"items": [{"name": "item", "unknown": "value"}]}
    assert validator.is_valid(unknown) is (extensions is not None)
    assert not validator.is_valid({"unknown": True})
    assert validator.is_valid({"items": [{"name": "item"}]})
    assert schema == original
