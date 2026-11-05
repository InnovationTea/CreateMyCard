"""请求必填字段与历史绑定兼容边界。"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.schemas import (
    GenerateWidgetCardRequest,
    GenerateWidgetCardResponse,
    WidgetCardServiceRequest,
)
from models.generation import CandidateDataBinding
from services import compact_dsl_argument_repair as repair
from services.agent_error_view import agent_error_view
from services.agent_feedback import request_validation_feedback
from services.capability_registry import CapabilityRegistry
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_preflight import GenerationPreflight
from services.widget_generation_service import WidgetGenerationService
from start_websocket_server import app
from ws_response_parser import parse_legacy_stream_content


def _binding():
    return {
        "capabilityId": "ViewWeather",
        "arguments": {},
        "writeResultTo": "/data/weather",
        "candidateOutputFields": ["/current/temperatureText", "/current/uvIndex"],
    }


def _request(binding):
    return {
        "uid": "binding-test",
        "device": {"romVersion": "7.0"},
        "userQuery": "显示当前温度和紫外线等级",
        "title": "天气",
        "description": "当前天气",
        "candidateDataBindings": [binding],
    }


@pytest.mark.parametrize("model", [GenerateWidgetCardRequest, WidgetCardServiceRequest])
@pytest.mark.parametrize("is_edit", [False, True])
@pytest.mark.parametrize("name", [
    "capabilityId", "arguments", "writeResultTo", "candidateOutputFields",
])
def test_missing_binding_field_has_actionable_feedback(model, is_edit, name):
    binding = _binding()
    binding.pop(name)
    arguments = _request(binding)
    if model is WidgetCardServiceRequest:
        arguments["operation"] = "generateWidgetCardCompactDsl"
    if is_edit:
        arguments["sourceArtifactUrl"] = "https://artifact.test/original"
    with pytest.raises(ValidationError) as caught:
        model(**arguments)
    details = request_validation_feedback(
        caught.value, "generateWidgetCardCompactDsl", arguments=arguments,
    )
    result = agent_error_view({"details": details}, "参数错误")
    assert result.get("retryable") is True
    issues = result.get("issues")
    assert isinstance(issues, list)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.get("path") == f"/candidateDataBindings/0/{name}"
    assert "缺少" in issue.get("message", "")
    assert "referenceSource" in str(details)
    assert "binding-test" not in str(result)


@pytest.mark.parametrize("name,value", [
    ("arguments", None), ("arguments", []), ("arguments", "{}"),
    ("candidateOutputFields", None), ("candidateOutputFields", []),
    ("candidateOutputFields", "/current/temperatureText"),
])
def test_invalid_required_binding_values_are_rejected(name, value):
    binding = _binding()
    binding[name] = value
    with pytest.raises(ValidationError) as caught:
        GenerateWidgetCardRequest(**_request(binding))
    locations = [error.get("loc") for error in caught.value.errors()]
    assert ("candidateDataBindings", 0, name) in locations


@pytest.mark.parametrize("path", ["", " ", "/current/notRegistered"])
def test_nonempty_but_invalid_paths_are_still_checked_by_preflight(path):
    binding = _binding()
    binding["candidateOutputFields"] = [path]
    request = EditRequestNormalizer.normalize_create(GenerateWidgetCardRequest(**_request(binding)))
    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    result = GenerationPreflight(registry).run(request)
    assert any(issue.code == "OUTPUT_FIELD_PATH_INVALID" for issue in result.blocking_issues)


def test_static_and_omitted_edit_bindings_remain_legal():
    arguments = _request(_binding())
    arguments["candidateDataBindings"] = []
    assert GenerateWidgetCardRequest(**arguments).candidateDataBindings == []
    arguments.pop("candidateDataBindings")
    arguments["sourceArtifactUrl"] = "https://artifact.test/original"
    request = GenerateWidgetCardRequest(**arguments)
    assert "candidateDataBindings" not in request.model_fields_set
    assert request.candidateDataBindings is None
    # 旧产物读取仍允许省略；新请求的收紧不修改历史数据模型。
    binding = CandidateDataBinding(capabilityId="ViewWeather", writeResultTo="/data/weather")
    assert binding.arguments == {}
    assert binding.candidateOutputFields == []
    source = SimpleNamespace(
        cardSpec={"title": "天气", "description": "原卡", "suggestSize": "2x2"},
        generationPlan=SimpleNamespace(
            candidateDataBindings=[binding], candidateEventCandidates=[], candidateAssetIds=[],
        ),
    )
    normalized = EditRequestNormalizer().normalize_edit(request, source)
    assert normalized.request.candidateDataBindings == [binding]
    assert "candidateDataBindings" in normalized.inherited_categories


@pytest.mark.parametrize("name", ["arguments", "candidateOutputFields"])
def test_recovery_does_not_consider_incomplete_binding_valid(name):
    binding = _binding()
    binding.pop(name)
    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    assert repair._fragment_is_valid("candidateDataBindings", binding, registry) is False
    arguments = _request(binding)
    arguments.pop("device")
    payload = {
        "content": {"arguments": json.dumps(arguments)},
        "deviceInfo": {"prdVer": "11.7.7.330", "romVersion": "7.0"},
    }
    with pytest.raises(ValueError, match=name):
        repair.recover_deterministic_content(payload)


def _receive_final(websocket):
    while True:
        response = websocket.receive_json()
        reply = response.get("reply")
        assert isinstance(reply, dict)
        stream = reply.get("streamInfo")
        assert isinstance(stream, dict)
        if stream.get("streamType") == "final":
            content = stream.get("streamContent")
            assert isinstance(content, str)
            return parse_legacy_stream_content(content)


def test_user_example_reports_all_missing_fields_before_service_and_can_be_corrected(monkeypatch):
    calls = []

    async def generate(_service, request, **_kwargs):
        calls.append(request)
        return GenerateWidgetCardResponse(
            status="success", suggestSize="2x2", message="成功",
            artifactUrl="https://artifact.test/corrected",
        )

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    arguments = _request({"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"})
    bindings = arguments.get("candidateDataBindings")
    assert isinstance(bindings, list)
    bindings.append({
        "capabilityId": "GetHealthAndSportSummary", "writeResultTo": "/data/healthSport",
    })
    with TestClient(app).websocket_connect("/api/v1/ws/tools/generateWidgetCardCompactDsl") as ws:
        ws.send_json({"arguments": arguments})
        rejected = _receive_final(ws)
        assert not calls
        assert rejected.get("retryable") is True
        issues = rejected.get("issues")
        assert isinstance(issues, list)
        paths = {issue.get("path") for issue in issues}
        assert paths == {
            "/candidateDataBindings/0/arguments",
            "/candidateDataBindings/0/candidateOutputFields",
            "/candidateDataBindings/1/arguments",
            "/candidateDataBindings/1/candidateOutputFields",
        }
        bindings[0] = _binding()
        bindings[1].update(arguments={}, candidateOutputFields=["/dailySteps"])
        ws.send_json({"arguments": arguments})
        assert _receive_final(ws).get("status") == "success"
    assert len(calls) == 1


def test_tool_snapshot_declares_required_projection():
    root = Path(__file__).resolve().parents[2]
    path = root / "skills/harmony-card-generation-online/references/tools"
    tool = json.loads((path / "com.omega_w_0823.hmservice__generateWidgetCardCompactDsl.json")
                      .read_text(encoding="utf-8"))
    arguments = tool.get("arguments")
    assert isinstance(arguments, dict)
    properties = arguments.get("properties")
    assert isinstance(properties, dict)
    binding = properties.get("candidateDataBindings")
    assert isinstance(binding, dict)
    properties = binding.get("properties")
    assert isinstance(properties, dict)
    item = properties.get("ArrayItem")
    assert isinstance(item, dict)
    assert set(item.get("required", [])) == {
        "capabilityId", "arguments", "writeResultTo", "candidateOutputFields",
    }
    properties = item.get("properties")
    assert isinstance(properties, dict)
    projection = properties.get("candidateOutputFields")
    assert isinstance(projection, dict)
    assert projection.get("minItems") == 1
