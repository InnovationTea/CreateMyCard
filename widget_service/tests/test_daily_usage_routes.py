"""公共 WebSocket 路由的计次边界，不调用真实模型。"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.websockets import WebSocketDisconnect

from api import routes
from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from test_compact_dsl_interface_retry import make_response
from test_daily_usage_limiter import make_limiter
from ws_response_parser import parse_legacy_stream_content

OPERATION = "generateWidgetCardCompactDsl"


def payload(*, uid="user", interaction="1"):
    return {
        "content": {
            "uid": uid,
            "title": "天气",
            "description": "天气卡片",
            "userQuery": "生成天气卡片",
        },
        "session": {"sessionId": "session", "interactionId": interaction},
    }


def frame_info(frame):
    reply = frame.get("reply")
    assert isinstance(reply, dict)
    info = reply.get("streamInfo")
    assert isinstance(info, dict)
    return info


def final_message(frames):
    content = frame_info(frames[-1]).get("streamContent")
    assert isinstance(content, str)
    return parse_legacy_stream_content(content)


@pytest.fixture
def setup_route(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", True)
    monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
    monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", False)
    monkeypatch.setattr(routes, "get_service", lambda _runtime: Mock())
    return settings


async def run_route(
    monkeypatch,
    limiter,
    *,
    status="success",
    requests=None,
    operation=OPERATION,
    fail_frame=None,
    artifact=True,
    handler=None,
):
    if requests is None:
        requests = [payload()]
    frames = []
    calls = []
    original_send = routes._send_websocket_json

    async def send(websocket, body, op, request_id, frame_type):
        if frame_type == fail_frame:
            return False
        return await original_send(websocket, body, op, request_id, frame_type)

    monkeypatch.setattr(routes, "_send_websocket_json", send)
    websocket = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(daily_usage_limiter=limiter)),
        accept=AsyncMock(),
        receive_text=AsyncMock(
            side_effect=[*[json.dumps(item) for item in requests], WebSocketDisconnect()]
        ),
        send_json=AsyncMock(side_effect=frames.append),
    )

    async def generate(_service, request, on_start):
        calls.append(request)
        await on_start("2x2")
        if handler is not None:
            return await handler(len(calls))
        result = make_response(GenerationStatus(status))
        if not artifact:
            result = result.model_copy(update={"artifactUrl": None})
        return result

    await routes._serve_operation_websocket(
        websocket, operation, GenerateWidgetCardRequest, generate, handler_in_threadpool=False
    )
    return frames, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", sorted(routes.GENERATION_OPERATIONS))
async def test_three_generation_operations_count_only_once(monkeypatch, setup_route, operation):
    limiter = make_limiter(limit=1)
    frames, calls = await run_route(
        monkeypatch, limiter, operation=operation, requests=[payload(), payload()]
    )
    assert len(calls) == 2
    assert len(limiter.repository.records) == 1
    assert limiter.repository.writes == 1
    assert final_message(frames).get("status") == "success"


@pytest.mark.asyncio
async def test_new_round_rejected_before_argument_repair(monkeypatch, setup_route):
    limiter = make_limiter(limit=1)
    record = await limiter.check("user", "session&previous")
    assert record is not None
    await limiter.record_success(record)
    repair = AsyncMock(side_effect=AssertionError("must not repair"))
    monkeypatch.setattr(routes, "_repair_compact_dsl_content_if_needed", repair)
    bad_payload = payload()
    content = bad_payload.get("content")
    assert isinstance(content, dict)
    content["arguments"] = '{"title":"broken"'
    frames, calls = await run_route(monkeypatch, limiter, requests=[bad_payload])
    assert not calls
    assert len(frames) == 1
    assert final_message(frames).get("errorCode") == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
    repair.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["degraded", "failed", "unsupported", "unchanged"])
async def test_non_success_results_do_not_count(monkeypatch, setup_route, status):
    limiter = make_limiter()
    frames, calls = await run_route(monkeypatch, limiter, status=status)
    assert len(calls) == 1
    assert final_message(frames).get("status") == status
    assert not limiter.repository.records


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_frame", ["start", "command_start", "command_success", "final"])
async def test_send_failure_boundary(monkeypatch, setup_route, fail_frame):
    limiter = make_limiter()
    await run_route(monkeypatch, limiter, fail_frame=fail_frame)
    assert len(limiter.repository.records) == (1 if fail_frame == "final" else 0)


@pytest.mark.asyncio
async def test_success_without_artifact_does_not_count(monkeypatch, setup_route):
    limiter = make_limiter()
    await run_route(monkeypatch, limiter, artifact=False)
    assert not limiter.repository.records


@pytest.mark.asyncio
async def test_commands_disabled_do_not_count(monkeypatch, setup_route):
    monkeypatch.setattr(setup_route, "enable_widget_directive_commands", False)
    limiter = make_limiter()
    await run_route(monkeypatch, limiter)
    assert not limiter.repository.records


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["uid", "requestId"])
async def test_missing_identity_bypasses_even_without_repository(monkeypatch, setup_route, missing):
    request = payload(uid="" if missing == "uid" else "user")
    if missing == "requestId":
        request.pop("session")
    frames, calls = await run_route(monkeypatch, None, requests=[request])
    assert len(calls) == 1
    assert final_message(frames).get("status") == "success"


@pytest.mark.asyncio
async def test_disabled_limit_never_reads_repository(monkeypatch, setup_route):
    monkeypatch.setattr(setup_route, "enable_daily_usage_limit", False)
    limiter = make_limiter()
    await run_route(monkeypatch, limiter)
    assert limiter.repository.reads == 0
    assert limiter.repository.writes == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["getWidgetCapabilityOverview", "getDataCapabilitySchemas"])
async def test_query_operations_skip_quota(setup_route, operation):
    assert await routes._check_daily_usage(operation, payload(), "session&1", None) is None


@pytest.mark.asyncio
async def test_usage_api_unavailable_is_not_reported_as_parameter_error(monkeypatch, setup_route):
    limiter = make_limiter()
    limiter.repository.snapshot = AsyncMock(side_effect=OSError("offline"))
    report = Mock()
    monkeypatch.setattr(routes, "report_ops_metrics", report)
    frames, calls = await run_route(monkeypatch, limiter)
    assert not calls
    assert final_message(frames).get("errorCode") == ErrorCode.DAILY_USAGE_LIMIT_UNAVAILABLE
    report.assert_not_called()


@pytest.mark.asyncio
async def test_retry_shares_one_check_and_records_final_success(monkeypatch, setup_route):
    monkeypatch.setattr(setup_route, "enable_compact_dsl_interface_retry", True)
    monkeypatch.setattr(setup_route, "compact_dsl_interface_retry_count", 1)

    async def handler(attempt):
        if attempt == 1:
            return make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)
        return make_response()

    limiter = make_limiter()
    _frames, calls = await run_route(monkeypatch, limiter, handler=handler)
    assert len(calls) == 2
    assert limiter.repository.reads == 1
    assert limiter.repository.writes == 1


@pytest.mark.asyncio
async def test_argument_repair_cannot_change_quota_identity(monkeypatch, setup_route):
    async def repair(body, *_args):
        content = body.get("content")
        assert isinstance(content, dict)
        content["uid"] = "model-user"
        return True

    monkeypatch.setattr(routes, "_repair_compact_dsl_content_if_needed", repair)
    limiter = make_limiter()
    await run_route(monkeypatch, limiter)
    assert await limiter.check("user", "session&1") is None
    assert await limiter.check("model-user", "session&1") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["repair", "handler"])
async def test_exception_before_success_does_not_count(monkeypatch, setup_route, failure_stage):
    async def failing_handler(_attempt):
        raise ValueError("invalid generation input")

    if failure_stage == "repair":
        monkeypatch.setattr(
            routes,
            "_repair_compact_dsl_content_if_needed",
            AsyncMock(side_effect=ValueError("repair failed")),
        )
    limiter = make_limiter()
    frames, _calls = await run_route(monkeypatch, limiter, handler=failing_handler)
    assert final_message(frames).get("status") == "failed"
    assert not limiter.repository.records


@pytest.mark.asyncio
async def test_count_write_failure_does_not_replace_success_with_error(monkeypatch, setup_route):
    limiter = make_limiter()
    limiter.repository.insert_success = AsyncMock(side_effect=OSError("offline"))
    frames, calls = await run_route(monkeypatch, limiter)
    assert len(calls) == 1
    assert final_message(frames).get("status") == "success"
    assert limiter.repository.insert_success.await_count == 3


@pytest.mark.asyncio
async def test_failed_then_successful_same_request_counts_once(monkeypatch, setup_route):
    async def handler(attempt):
        if attempt == 1:
            return make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)
        return make_response()

    limiter = make_limiter()
    frames, calls = await run_route(
        monkeypatch, limiter, handler=handler, requests=[payload(), payload()]
    )
    assert len(calls) == 2
    assert final_message(frames).get("status") == "success"
    assert limiter.repository.writes == 1


@pytest.mark.asyncio
async def test_edit_is_counted_like_create(monkeypatch, setup_route):
    request = payload()
    content = request.get("content")
    assert isinstance(content, dict)
    content["sourceArtifactUrl"] = "https://example.test/source.md"
    limiter = make_limiter()
    frames, _calls = await run_route(monkeypatch, limiter, requests=[request])
    assert final_message(frames).get("status") == "success"
    assert limiter.repository.writes == 1


@pytest.mark.asyncio
async def test_enabled_without_initialized_client_fails_closed(monkeypatch, setup_route):
    frames, calls = await run_route(monkeypatch, None)
    assert not calls
    assert final_message(frames).get("errorCode") == ErrorCode.DAILY_USAGE_LIMIT_UNAVAILABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"content": {"uid": "content"}, "userAuth": {"user": {"userId": "auth"}}}, "content"),
        ({"content": {"uid": " "}, "userAuth": {"user": {"userId": "auth"}}}, "auth"),
        ({"content": {"arguments": '{"uid":"inner"}'}}, "inner"),
        ({"content": {"arguments": '{"uid":"broken"'}, "uid": "outer"}, "outer"),
        ({"arguments": {"uid": "legacy"}, "uid": "outer"}, "legacy"),
        ({"uid": "outer"}, "outer"),
    ],
)
async def test_quota_uid_uses_raw_payload_priority(setup_route, raw, expected):
    limiter = Mock(check=AsyncMock(return_value=None))
    await routes._check_daily_usage(OPERATION, raw, "s&1", limiter)
    limiter.check.assert_awaited_once_with(expected, "s&1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"session": {"sessionId": "s", "interactionId": "2"}}, "s&2"),
        ({"session": {"sessionId": "s"}}, "s"),
        ({"requestId": "legacy-id"}, "legacy-id"),
        ({"requestId": " "}, None),
    ],
)
async def test_quota_preserves_existing_request_id_fallbacks(setup_route, raw, expected):
    raw["uid"] = "user"
    limiter = Mock(check=AsyncMock(return_value=None))
    resolved = routes._request_id_from_raw_payload(raw)
    assert resolved == expected
    await routes._check_daily_usage(OPERATION, raw, resolved, limiter)
    if expected is None:
        limiter.check.assert_not_called()
    else:
        limiter.check.assert_awaited_once_with("user", expected)
