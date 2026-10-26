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
        caught.value, "generateWidgetCardCompactDsl", request_validated=True,
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
            status="success", suggestSize="2x2", message="成功",
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
        error = rejected.get("error")
        assert isinstance(error, dict)
        details = error.get("details")
        assert isinstance(details, dict)
        assert details.get("retryable") is True
        assert "candidateDataBindings" in json.dumps(details)
        assert not calls
        arguments.pop("dataCapabilityIds")
        arguments["candidateDataBindings"] = [{
            "capabilityId": "GetCalendarEvents", "arguments": {},
            "writeResultTo": "/data/calendar",
        }]
        websocket.send_json({"arguments": arguments})
        accepted = _receive_result(websocket)
    assert accepted.get("status") == "success"
    assert len(calls) == 1
    assert calls[0].candidateDataBindings


@pytest.mark.parametrize("status,code", [
    ("failed", "VALIDATION_FAILED"), ("unsupported", "WIDGET_EDIT_UNSUPPORTED"),
])
def test_business_failure_has_explicit_stop_feedback(monkeypatch, status, code):
    async def generate(_service, _request, **_kwargs):
        return GenerateWidgetCardResponse(
            status=status, errorCode=code, suggestSize="2x2", message="内部说明",
        )

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    with TestClient(app).websocket_connect(
        "/api/v1/ws/tools/generateWidgetCardCompactDsl"
    ) as websocket:
        websocket.send_json({"arguments": _arguments()})
        result = _receive_result(websocket)
    assert result.get("status") == status
    error = result.get("error")
    assert isinstance(error, dict)
    details = error.get("details")
    assert isinstance(details, dict)
    assert details.get("retryable") is False
    assert details.get("requiredActions") == ["STOP"]


@pytest.mark.parametrize("code", [
    "TIMEOUT", "ARTIFACT_UPLOAD_FAILED", "PROTOCOL_CAPABILITY_UNSUPPORTED",
    "WIDGET_EDIT_DISABLED", "SOURCE_ARTIFACT_INVALID", "SOURCE_ARTIFACT_NOT_FOUND", "FAILED",
])
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
