# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest
from fastapi.testclient import TestClient

from api import routes
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from services import artifact_store
from services.artifact_store import ArtifactStore, ArtifactUploadError
from services.compact_dsl_argument_repair import compact_dsl_argument_issue_tracker
from services.widget_generation_service import WidgetGenerationService
from test_compact_dsl_interface_retry import make_response
from test_tool_dispatch_routes import (
    _command_content,
    _receive_frames_until_final,
    _request_id,
    _tool_payload,
    app,
)
from ws_response_parser import parse_legacy_stream_content

_OPERATION = "generateWidgetCardCompactDsl"
_PATH = f"/api/v1/ws/tools/{_OPERATION}"
_CONTENT = {
    "userQuery": "生成天气卡片",
    "title": "天气",
    "description": "天气卡片",
    "size": "2x2",
    "romVersion": "VYG-AL00 7.0.0.105",
}


@pytest.fixture(autouse=True)
def retry_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", True)
    monkeypatch.setattr(settings, "compact_dsl_interface_retry_count", 1)
    monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
    compact_dsl_argument_issue_tracker.clear()
    yield
    compact_dsl_argument_issue_tracker.clear()


def stream_info(frame):
    reply = frame.get("reply")
    assert isinstance(reply, dict)
    info = reply.get("streamInfo")
    assert isinstance(info, dict)
    return info


def final_result(frames):
    content = stream_info(frames[-1]).get("streamContent")
    assert isinstance(content, str)
    return parse_legacy_stream_content(content)


def command_params(frame):
    directives = _command_content(frame).get("directives")
    assert isinstance(directives, list)
    assert len(directives) == 1
    payload = directives[0].get("payload")
    assert isinstance(payload, dict)
    params = payload.get("executeParam")
    assert isinstance(params, dict)
    return params


def assert_single_directive_pair(frames, *, succeeded):
    assert [stream_info(frame).get("streamType") for frame in frames] == [
        "start",
        "command",
        "command",
        "final",
    ]
    start = command_params(frames[1])
    end = command_params(frames[2])
    assert start.get("intentName") == "AIWidgetStart"
    assert end.get("intentName") == "AIWidgetEnd"
    assert end.get("status") is succeeded
    card_id = start.get("cardId")
    assert isinstance(card_id, str)
    assert end.get("cardId") == card_id


@pytest.mark.parametrize("failure_kind", ["result", "model", "upload", "timeout"])
@pytest.mark.parametrize("recovers", [True, False])
def test_route_retries_generation_with_one_directive_pair(monkeypatch, failure_kind, recovers):
    calls = []

    async def generate(_service, request, *, before_model_call):
        calls.append(request)
        await before_model_call("2x2")
        if recovers and len(calls) == 2:
            return make_response()
        if failure_kind == "model":
            raise A2UIModelGenerationError("model unavailable")
        if failure_kind == "upload":
            raise ArtifactUploadError("upload failed")
        if failure_kind == "timeout":
            raise TimeoutError("timeout")
        return make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    interaction_id = "retry-directives"
    with TestClient(app).websocket_connect(_PATH) as websocket:
        websocket.send_json(_tool_payload(_CONTENT, interaction_id))
        frames = _receive_frames_until_final(websocket, _request_id(interaction_id))

    assert len(calls) == 2
    assert_single_directive_pair(frames, succeeded=recovers)
    result = final_result(frames)
    assert result.get("status") == ("success" if recovers else "failed")


def test_stringified_arguments_repaired_once_before_generation_retries(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_compact_dsl_argument_repair_fallback", True)
    monkeypatch.setattr(settings, "compact_dsl_argument_repair_reminder_count", 1)
    model_calls = []
    generation_calls = []
    recorded_issues = []
    original_record = compact_dsl_argument_issue_tracker.record

    def record(request_id, reminder_count):
        recorded_issues.append(request_id)
        return original_record(request_id, reminder_count)

    async def repair(_client, _prompt, profile, **_kwargs):
        model_calls.append(profile.get("format"))
        return json.dumps(_CONTENT, ensure_ascii=False)

    async def generate(_service, request, *, before_model_call):
        generation_calls.append(request)
        await before_model_call("2x2")
        assert request.title == "天气"
        assert request.device._source_rom_version == _CONTENT.get("romVersion")
        assert request._model_request_context is not None
        body = json.loads(request._raw_request_body)
        content = body.get("content")
        assert isinstance(content, dict)
        assert "arguments" not in content
        if len(generation_calls) == 1:
            request.title = "前次运行修改的标题"
            return make_response(GenerationStatus.FAILED, ErrorCode.A2UI_GENERATION_FAILED)
        return make_response()

    monkeypatch.setattr(compact_dsl_argument_issue_tracker, "record", record)
    monkeypatch.setattr(A2UIModelClient, "generate", repair)
    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    interaction_id = "repair-once"
    malformed = _tool_payload(
        {"arguments": '{"title":"天气","userQuery":"生成天气卡片"'}, interaction_id
    )
    request_id = _request_id(interaction_id)
    with TestClient(app).websocket_connect(_PATH) as websocket:
        websocket.send_json(malformed)
        first = _receive_frames_until_final(websocket, request_id)
        assert final_result(first).get("errorCode") == ErrorCode.INVALID_ARGUMENTS
        assert not model_calls
        assert not generation_calls

        websocket.send_json(malformed)
        second = _receive_frames_until_final(websocket, request_id)
        assert_single_directive_pair(second, succeeded=True)

        # 生成的内部重试不累计 arguments 异常次数；收口后新请求从提醒重新开始。
        websocket.send_json(malformed)
        third = _receive_frames_until_final(websocket, request_id)
        assert final_result(third).get("errorCode") == ErrorCode.INVALID_ARGUMENTS

    assert model_calls == ["raw-json"]
    assert len(generation_calls) == 2
    assert recorded_issues == [request_id, request_id, request_id]


@pytest.mark.parametrize("bad_input", ["invalid-json", "missing-title", "repair-failed"])
def test_bad_parameters_never_enter_generation_retry(monkeypatch, bad_input):
    repair_calls = []

    async def unexpected_retry(*_args, **_kwargs):
        pytest.fail("invalid arguments must not enter interface retry")

    async def fail_repair(*_args, **_kwargs):
        repair_calls.append(True)
        raise ValueError("unable to recover content")

    monkeypatch.setattr(routes, "run_compact_dsl_with_retry", unexpected_retry)
    monkeypatch.setattr(routes, "recover_compact_dsl_content", fail_repair)
    monkeypatch.setattr(get_settings(), "enable_compact_dsl_argument_repair_fallback", True)
    monkeypatch.setattr(get_settings(), "compact_dsl_argument_repair_reminder_count", 0)
    with TestClient(app).websocket_connect(_PATH) as websocket:
        if bad_input == "invalid-json":
            websocket.send_text("{")
        elif bad_input == "missing-title":
            websocket.send_json(_tool_payload({"userQuery": "生成卡片"}, "invalid"))
        else:
            websocket.send_json(_tool_payload({"arguments": "broken"}, "repair-failure"))
        response = websocket.receive_json()
    assert final_result([response]).get("errorCode") == ErrorCode.INVALID_ARGUMENTS
    assert len(repair_calls) == (1 if bad_input == "repair-failed" else 0)


@pytest.mark.parametrize("enabled,retry_count", [(False, 1), (True, 0)])
def test_route_disabled_or_zero_retry_preserves_single_attempt(monkeypatch, enabled, retry_count):
    monkeypatch.setattr(get_settings(), "enable_compact_dsl_interface_retry", enabled)
    monkeypatch.setattr(get_settings(), "compact_dsl_interface_retry_count", retry_count)
    calls = []

    async def generate(_service, request, *, before_model_call):
        calls.append(request)
        await before_model_call("2x2")
        return make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)

    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    with TestClient(app).websocket_connect(_PATH) as websocket:
        websocket.send_json(_tool_payload(_CONTENT, "disabled"))
        frames = _receive_frames_until_final(websocket, _request_id("disabled"))
    assert len(calls) == 1
    assert_single_directive_pair(frames, succeeded=False)


@pytest.mark.parametrize(
    ("operation", "method"),
    [
        ("generateWidgetCard", "generate_widget_card_a2ui_form"),
        ("generateWidgetCardTerseDslNested2", "generate_widget_card_terse_dsl_nested2"),
    ],
)
def test_other_generation_routes_do_not_use_interface_retry(monkeypatch, operation, method):
    calls = []

    async def unexpected_retry(*_args, **_kwargs):
        pytest.fail("other routes must not enter Compact DSL interface retry")

    async def generate(_service, request, *, before_model_call):
        calls.append(request)
        await before_model_call("2x2")
        return make_response(GenerationStatus.FAILED, ErrorCode.A2UI_GENERATION_FAILED)

    monkeypatch.setattr(routes, "run_compact_dsl_with_retry", unexpected_retry)
    monkeypatch.setattr(WidgetGenerationService, method, generate)
    with TestClient(app).websocket_connect(f"/api/v1/ws/tools/{operation}") as websocket:
        websocket.send_json(_tool_payload(_CONTENT, "other-route"))
        frames = _receive_frames_until_final(websocket, _request_id("other-route"))
    assert len(calls) == 1
    assert_single_directive_pair(frames, succeeded=False)


@pytest.mark.parametrize("failure_kind", ["model", "validation", "upload"])
def test_real_generation_pipeline_retries_to_valid_artifact(monkeypatch, tmp_path, failure_kind):
    monkeypatch.setattr(get_settings(), "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(get_settings(), "enable_model_failure_retry", False)
    monkeypatch.setattr(get_settings(), "enable_validation_failure_retry", False)
    calls = []
    uploads = []
    upload_calls = []
    original_save = ArtifactStore.save
    original_upload = artifact_store.file_obs.upload_file
    token_rows = [
        ["root", "Column", {"padding": 12, "backgroundColor": "#FFFFFFFF"}, ["title"]],
        ["title", "Text", {"content": "天气", "fontSize": 16, "fontColor": "#FF000000"}],
        ["/ui/state", "ready"],
    ]
    token = "\n".join(json.dumps(row, ensure_ascii=False) for row in token_rows)

    async def generate(_client, _prompt, profile, **_kwargs):
        calls.append(profile.get("format"))
        if len(calls) == 1:
            if failure_kind == "model":
                raise A2UIModelGenerationError("model unavailable")
            if failure_kind == "validation":
                return "invalid model output"
        return token

    async def save(store, artifact):
        uploads.append(artifact)
        return await original_save(store, artifact)

    async def upload(path):
        upload_calls.append(path)
        if failure_kind == "upload" and len(upload_calls) == 1:
            raise TimeoutError("upload timed out")
        return await original_upload(path)

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    monkeypatch.setattr(artifact_store.file_obs, "upload_file", upload)
    with TestClient(app).websocket_connect(_PATH) as websocket:
        websocket.send_json(_tool_payload(_CONTENT, "pipeline"))
        frames = _receive_frames_until_final(websocket, _request_id("pipeline"))

    assert_single_directive_pair(frames, succeeded=True)
    assert calls == ["compact-dsl", "compact-dsl"]
    expected_saves = 2 if failure_kind == "upload" else 1
    assert len(uploads) == expected_saves
    assert len(upload_calls) == expected_saves
    assert len(list(tmp_path.glob("artifact_*.md"))) == expected_saves
    assert len(list((tmp_path / "mock_obs").glob("artifact_*.md"))) == 1


@pytest.mark.parametrize("commands_enabled", [True, False])
def test_start_not_resent_when_delivery_failed_or_commands_disabled(monkeypatch, commands_enabled):
    monkeypatch.setattr(get_settings(), "enable_widget_directive_commands", commands_enabled)
    attempts = []
    start_calls = []
    original_send = routes._send_widget_directive_command

    async def send(*args):
        start_calls.append(args)
        if commands_enabled:
            return False
        return await original_send(*args)

    async def generate(_service, request, *, before_model_call):
        attempts.append(request)
        await before_model_call("2x2")
        if len(attempts) == 1:
            return make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)
        return make_response()

    monkeypatch.setattr(routes, "_send_widget_directive_command", send)
    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    with TestClient(app).websocket_connect(_PATH) as websocket:
        websocket.send_json(_tool_payload(_CONTENT, "start-failure"))
        frames = _receive_frames_until_final(websocket, _request_id("start-failure"))
    assert len(attempts) == 2
    assert len(start_calls) == 1
    assert [stream_info(frame).get("streamType") for frame in frames] == ["start", "final"]
    assert final_result(frames).get("status") == "success"


def test_final_delivery_failure_does_not_repeat_successful_generation(monkeypatch):
    calls = []
    original_send = routes._send_websocket_json

    async def send(websocket, payload, operation, request_id, phase):
        sent = await original_send(websocket, payload, operation, request_id, phase)
        return False if phase == "final" else sent

    async def generate(_service, request, *, before_model_call):
        calls.append(request)
        await before_model_call("2x2")
        return make_response()

    monkeypatch.setattr(routes, "_send_websocket_json", send)
    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card_compact_dsl", generate)
    with TestClient(app).websocket_connect(_PATH) as websocket:
        websocket.send_json(_tool_payload(_CONTENT, "final-failure"))
        frames = _receive_frames_until_final(websocket, _request_id("final-failure"))
    assert len(calls) == 1
    assert_single_directive_pair(frames, succeeded=True)
