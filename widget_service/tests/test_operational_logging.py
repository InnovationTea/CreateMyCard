"""关闭 Trace 时的关键诊断及日志脱敏回归。"""

import copy
import json
from types import SimpleNamespace

import pytest

from api.routes import _build_plugin_stream_response, _send_websocket_json
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from models.service import WidgetWebSocketResultMessage
from services import operational_logging, post_layout_theme
from services.operational_logging import exception_summary, service_fingerprints


class CaptureLogger:
    def __init__(self):
        self.messages = []

    def log(self, _level, message):
        self.messages.append(message)

    def info(self, message):
        self.messages.append(message)

    def warning(self, message):
        self.messages.append(message)

    def error(self, message):
        self.messages.append(message)


@pytest.mark.parametrize("message", [
    "fetch https://example.test/card?signature=private-url uid=private-user",
    'odid="private-device" token=private-token',
])
def test_exception_summary_redacts_identity_credentials_and_addresses(message):
    cause = OSError(message)
    error = ValueError("读取失败")
    error.__cause__ = cause
    summary = exception_summary(error)
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "private-" not in serialized
    assert "OSError" in serialized
    assert "读取失败" in serialized


def test_fingerprints_are_stable_and_separate_code_from_resources(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    source = tmp_path / "entry.py"
    source.write_text("pass", encoding="utf-8")
    (data / "protocol.json").write_text("{}", encoding="utf-8")
    first = service_fingerprints(tmp_path)
    assert first == service_fingerprints(tmp_path)
    source.write_text("value = 1", encoding="utf-8")
    second = service_fingerprints(tmp_path)
    assert first.get("code") != second.get("code")
    assert first.get("resources") == second.get("resources")


def test_fingerprint_read_failure_does_not_block_startup(monkeypatch):
    def fail(_root):
        raise OSError("资源不可读")

    capture = CaptureLogger()
    monkeypatch.setattr(operational_logging, "service_fingerprints", fail)
    monkeypatch.setattr(operational_logging, "logger", capture)
    operational_logging.log_service_fingerprints(None)
    assert "service_build_unavailable" in capture.messages[0]
    assert "资源不可读" in capture.messages[0]


def test_agent_feedback_logs_projected_controls_without_internal_artifact(monkeypatch):
    from api import routes

    capture = CaptureLogger()
    monkeypatch.setattr(routes, "logger", capture)
    message = WidgetWebSocketResultMessage(
        operation="generateWidgetCardCompactDsl", status="failed",
        errorCode="A2UI_GENERATION_FAILED",
        data={"artifactUrl": "private-artifact", "removedCapabilities": ["private-data"]},
        error={"message": "生成失败", "details": {
            "retryable": False, "requiredActions": ["STOP"],
        }},
    )
    original = message.model_copy(deep=True)
    response = _build_plugin_stream_response(message)
    payload = json.loads(response.reply.streamInfo.streamContent)
    logs = " ".join(capture.messages)
    assert payload.get("retryable") is False
    assert "STOP" in logs and "agent_feedback" in logs
    assert "private-artifact" not in logs and "private-data" not in logs
    assert message == original


@pytest.mark.asyncio
@pytest.mark.parametrize("frame_type", ["final", "final_error", "heartbeat"])
async def test_final_send_logging_does_not_log_payload_or_heartbeats(monkeypatch, frame_type):
    from api import routes

    capture = CaptureLogger()
    monkeypatch.setattr(routes, "logger", capture)

    class Socket:
        async def send_json(self, _payload):
            return None

    assert await _send_websocket_json(Socket(), {"secret": "private"}, "test", "req", frame_type)
    assert bool(capture.messages) == (frame_type != "heartbeat")
    assert "private" not in " ".join(capture.messages)


@pytest.mark.asyncio
async def test_empty_model_output_has_reason_in_normal_log(monkeypatch):
    from custom import a2ui_model_client

    capture = CaptureLogger()
    monkeypatch.setattr(a2ui_model_client, "logger", capture)
    client = A2UIModelClient(use_mock=True)
    monkeypatch.setattr(client, "_load_mock_data", lambda *_args: "")
    with pytest.raises(A2UIModelGenerationError):
        await client.generate([], {"id": "test"}, phase="plan")
    logs = " ".join(capture.messages)
    assert "model_output_failed phase=plan" in logs
    assert "empty DSL" in logs


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_fails", [False, True])
async def test_theme_validation_fallback_is_visible_without_trace(monkeypatch, fallback_fails):
    capture = CaptureLogger()
    monkeypatch.setattr(post_layout_theme, "logger", capture)

    class Artifact:
        genui = "original"
        meta = SimpleNamespace(generationMode="create")

        def model_copy(self, **_kwargs):
            return copy.deepcopy(self)

    async def select(*_args, **_kwargs):
        return "themed", {"themeId": "chosen", "theme": {"kind": "gradient"}}

    validations = iter([["chosen-invalid"], ["fallback-invalid"] if fallback_fails else []])
    monkeypatch.setattr(post_layout_theme, "select_theme", select)
    monkeypatch.setattr(post_layout_theme, "_validate_theme", lambda *_a, **_k: next(validations))
    monkeypatch.setattr(post_layout_theme, "preference_fallback", lambda *_a: {"id": "fallback"})
    monkeypatch.setattr(post_layout_theme, "apply_theme", lambda *_a: "fallback-output")
    monkeypatch.setattr(post_layout_theme, "record_unmet_fusion_preference", lambda *_a: None)
    if fallback_fails:
        with pytest.raises(ValueError, match="Final gradient"):
            await post_layout_theme.theme_artifact(Artifact(), {}, None, None, {})
        assert "fallback_failed" in " ".join(capture.messages)
    else:
        result = await post_layout_theme.theme_artifact(Artifact(), {}, None, None, {})
        assert result.genui == "fallback-output"
        assert "completed theme_id=fallback" in " ".join(capture.messages)
    assert "chosen-invalid" in " ".join(capture.messages)


@pytest.mark.asyncio
async def test_edit_source_failure_keeps_cause_without_signed_url(monkeypatch):
    from core.errors import ErrorCode
    from services import widget_edit_service
    from services.source_artifact_repository import SourceArtifactError

    capture = CaptureLogger()
    monkeypatch.setattr(widget_edit_service, "logger", capture)
    monkeypatch.setattr(widget_edit_service, "get_settings", lambda: SimpleNamespace(
        enable_widget_edit=True,
    ))

    def fail_load(_self, _url):
        raise SourceArtifactError(
            ErrorCode.SOURCE_ARTIFACT_DOWNLOAD_FAILED, "来源读取失败",
        ) from OSError("超时 https://example.test/card?signature=private-signature")

    monkeypatch.setattr(widget_edit_service.SourceArtifactRepository, "load", fail_load)
    request = SimpleNamespace(sourceArtifactUrl="https://example.test/source", size="2x2")
    result = await widget_edit_service.WidgetEditService(None).generate(
        request, SimpleNamespace(supports_edit=True),
    )
    assert result.errorCode == "SOURCE_ARTIFACT_DOWNLOAD_FAILED"
    logs = " ".join(capture.messages)
    assert "source_load_failed" in logs and "OSError" in logs and "超时" in logs
    assert "private-signature" not in logs
