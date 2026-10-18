# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import json
from unittest.mock import Mock

import pytest

from api import routes
from services.widget_directive import WidgetDirectiveState


@pytest.mark.parametrize("state", list(WidgetDirectiveState))
@pytest.mark.parametrize("outcome", ["sent", "disconnect", "runtime_error"])
def test_widget_directive_logs_send_outcome(monkeypatch, state, outcome):
    captured_logger = Mock()
    monkeypatch.setattr(routes, "logger", captured_logger)
    monkeypatch.setattr(routes, "_widget_directive_commands_enabled", lambda: True)
    frames = []

    class WebSocketStub:
        async def send_json(self, payload):
            frames.append(payload)
            if outcome == "disconnect":
                raise routes.WebSocketDisconnect(code=1006)
            if outcome == "runtime_error":
                raise RuntimeError("connection closed")

    sent = asyncio.run(
        routes._send_widget_directive_command(
            WebSocketStub(),
            {"userAuth": {"user": {"userId": "private-user-id"}}},
            "generateWidgetCardCompactDsl",
            "request-1",
            "stream-1",
            state,
            "card-1",
            "2x4",
            "https://example.invalid/artifact.json",
        )
    )

    assert sent is (outcome == "sent")
    assert len(frames) == 1
    info_logs = [call.args[0] for call in captured_logger.info.call_args_list]
    error_logs = [call.args[0] for call in captured_logger.error.call_args_list]
    assert "widget_directive_sending " in info_logs[0]
    logged_command = json.loads(info_logs[0].split(" command=", 1)[1])
    reply = frames[0].get("reply")
    assert isinstance(reply, dict)
    stream_info = reply.get("streamInfo")
    assert isinstance(stream_info, dict)
    stream_content = stream_info.get("streamContent")
    assert isinstance(stream_content, str)
    sent_command = json.loads(stream_content)
    sent_content = sent_command.get("content")
    assert isinstance(sent_content, str)
    sent_directive = json.loads(sent_content)
    session = sent_directive.get("session")
    assert isinstance(session, dict)
    assert session.pop("uid") == "private-user-id"
    sent_command["content"] = sent_directive
    assert logged_command == sent_command
    if sent:
        assert len(info_logs) == 2
        assert "widget_directive_sent " in info_logs[1]
        assert not error_logs
    else:
        assert len(info_logs) == 1
        assert len(error_logs) == 2
        assert "widget_operation_ws_send_failed " in error_logs[0]
        assert "widget_directive_send_failed " in error_logs[1]
    intent_name = "AIWidgetStart" if state is WidgetDirectiveState.START else "AIWidgetEnd"
    directive_logs = [info_logs[0], info_logs[-1] if sent else error_logs[-1]]
    for message in directive_logs:
        assert f"intent_name={intent_name}" in message
        assert f"state={state.value}" in message
        assert "request_id=request-1" in message
        assert "operation=generateWidgetCardCompactDsl" in message
        assert "card_id=card-1 size=2x4 streaming_text_id=stream-1" in message
    assert "private-user-id" not in "\n".join(info_logs + error_logs)


@pytest.mark.parametrize("state", list(WidgetDirectiveState))
def test_widget_directive_logs_disabled_without_sending(monkeypatch, state):
    captured_logger = Mock()
    websocket = Mock()
    monkeypatch.setattr(routes, "logger", captured_logger)
    monkeypatch.setattr(routes, "_widget_directive_commands_enabled", lambda: False)

    sent = asyncio.run(
        routes._send_widget_directive_command(
            websocket, {}, "generateWidgetCardCompactDsl", "request-1",
            "stream-1", state, "card-1", "2x2",
        )
    )

    assert sent is True
    websocket.send_json.assert_not_called()
    captured_logger.info.assert_called_once()
    message = captured_logger.info.call_args.args[0]
    assert "widget_directive_skipped " in message
    assert "reason=commands_disabled" in message
    assert f"state={state.value}" in message
    captured_logger.error.assert_not_called()
