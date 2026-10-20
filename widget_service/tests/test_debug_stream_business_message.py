"""真实 Debug Tools 入口须兼容服务端 JSON 和历史响应。"""

import asyncio
import json

import pytest
from debug_tools.batch_testing import runner
from debug_tools.end_to_end_debug.backend.debug_agent.upstream_ws_client import (
    UpstreamToolError,
    UpstreamWebSocketClient,
    parse_legacy_stream_content,
)

from api.routes import _build_plugin_stream_response
from models.service import WidgetWebSocketErrorMessage, WidgetWebSocketResultMessage


def _message(status: str):
    if status == "failed":
        return WidgetWebSocketErrorMessage(
            operation="generateWidgetCardCompactDsl", requestId="session&1",
            errorCode="VALIDATION_FAILED", error={"message": "完整校验未通过"},
        )
    return WidgetWebSocketResultMessage(
        operation="generateWidgetCardCompactDsl", requestId="session&1", status=status,
        data={"status": status, "nested": {"enabled": True, "value": None},
              "text": "中文、引号'和\"、换行\n及 type= 业务正文"},
    )


@pytest.mark.parametrize("prefix", ["", "参数错误：", "  参数错误：  "])
@pytest.mark.parametrize("status", ["success", "degraded", "failed", "unsupported"])
def test_debug_parser_accepts_actual_service_response(status: str, prefix: str) -> None:
    message = _message(status)
    content = _build_plugin_stream_response(message).reply.streamInfo.streamContent
    assert parse_legacy_stream_content(content) == message.model_dump(mode="json")
    assert parse_legacy_stream_content(prefix + message.model_dump_json()) == message.model_dump(
        mode="json",
    )
    assert parse_legacy_stream_content(str(message)) == message.model_dump(mode="python")


@pytest.mark.parametrize("source", [
    '{"type":"result",', '[]', '参数错误：[]', '{"type":"result"}',
    '无关正文 {"type":"result"}',
])
def test_debug_parser_rejects_invalid_business_message(source: str) -> None:
    with pytest.raises(UpstreamToolError):
        parse_legacy_stream_content(source)


_TERMINAL_CASES = [
    ("success", "final"), ("degraded", "final"), ("unsupported", "final"),
    ("failed", "final"), ("failed", "final_error"),
]


def _frame(status: str, stream_type: str) -> dict:
    frame = _build_plugin_stream_response(_message(status)).model_dump(mode="json")
    reply = frame.get("reply")
    assert isinstance(reply, dict)
    stream_info = reply.get("streamInfo")
    assert isinstance(stream_info, dict)
    stream_info["streamType"] = stream_type
    return frame


@pytest.mark.parametrize("status,stream_type", _TERMINAL_CASES)
def test_batch_invocation_preserves_service_business_status(
    monkeypatch, status: str, stream_type: str,
) -> None:
    frame = _frame(status, stream_type)

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def send(self, payload):
            session = json.loads(payload).get("session")
            assert session == {"sessionId": "session", "interactionId": "1"}

        async def recv(self):
            return json.dumps(frame, ensure_ascii=False)

    monkeypatch.setattr(runner.websockets, "connect", lambda *_args, **_kwargs: Socket())
    result = asyncio.run(runner.invoke_generate(
        "ws://localhost/test",
        {"session": {"sessionId": "session", "interactionId": "1"}}, 1.0,
    ))
    assert result.get("status") == status
    expected_error = "VALIDATION_FAILED" if status == "failed" else ""
    assert result.get("errorCode") == expected_error


@pytest.mark.parametrize("name,value", [
    ("data", []), ("error", None), ("status", True), ("status", "unknown"),
    ("type", "unknown"), ("type", True), ("tool", None), ("operation", 1),
    ("errorCode", 0), ("requestId", False),
])
def test_debug_parser_does_not_coerce_invalid_field_types(name, value) -> None:
    message = _message("success").model_dump(mode="json")
    message[name] = value
    with pytest.raises(UpstreamToolError):
        parse_legacy_stream_content(json.dumps(message))


@pytest.mark.parametrize("name", [
    "type", "tool", "operation", "requestId", "data", "status", "errorCode", "error",
])
def test_debug_parser_rejects_each_missing_business_field(name: str) -> None:
    message = _message("success").model_dump(mode="json")
    message.pop(name)
    with pytest.raises(UpstreamToolError, match=f"缺少业务字段: {name}"):
        parse_legacy_stream_content(json.dumps(message))


def test_debug_parser_preserves_nullable_request_id() -> None:
    message = _message("success").model_dump(mode="json")
    message["requestId"] = None
    assert parse_legacy_stream_content(json.dumps(message)) == message


@pytest.mark.parametrize("status,stream_type", _TERMINAL_CASES)
def test_end_to_end_frame_parser_preserves_terminal_business_status(
    status: str, stream_type: str,
) -> None:
    frame = _frame(status, stream_type)
    result = UpstreamWebSocketClient._parse_frame(
        frame, "generateWidgetCardCompactDsl", "session&1",
    )
    assert isinstance(result, dict)
    assert result.get("status") == status
    expected_error = "VALIDATION_FAILED" if status == "failed" else ""
    assert result.get("errorCode") == expected_error
    assert result.get("data") == _message(status).data


@pytest.mark.parametrize("operation,request_id,reason", [
    ("otherOperation", "session&1", "operation"),
    ("generateWidgetCardCompactDsl", "otherSession&1", "requestId"),
])
def test_end_to_end_frame_parser_still_checks_invocation_identity(
    operation: str, request_id: str, reason: str,
) -> None:
    with pytest.raises(UpstreamToolError, match=reason):
        UpstreamWebSocketClient._parse_frame(_frame("success", "final"), operation, request_id)


def test_upstream_error_keeps_frame_summary_after_conflict_resolution() -> None:
    frames = ({"streamType": "final_error", "contentChars": 12},)
    error = UpstreamToolError("解析失败", frames=frames)
    assert error.frames == frames
    assert str(error) == "解析失败"


@pytest.mark.parametrize("content", ['{"status":"success"}', '[]', '{"type":'])
def test_batch_keeps_failed_frames_when_business_message_is_invalid(monkeypatch, content: str):
    frame = {"reply": {"streamInfo": {"streamType": "final", "streamContent": content}}}

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def send(self, payload):
            assert json.loads(payload).get("session") is not None

        async def recv(self):
            return json.dumps(frame)

    monkeypatch.setattr(runner.websockets, "connect", lambda *_args, **_kwargs: Socket())
    with pytest.raises(UpstreamToolError) as failure:
        asyncio.run(runner.invoke_generate(
            "ws://localhost/test",
            {"session": {"sessionId": "session", "interactionId": "1"}}, 1.0,
        ))
    assert failure.value.frames == (frame,)
