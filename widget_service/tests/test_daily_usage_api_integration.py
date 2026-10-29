"""HTTP 模拟服务与真实路由组合验证；不代表真实 API 服务端已完成联调。"""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from api import routes
from config.config import get_settings
from core.errors import ErrorCode
from services import daily_usage_api
from services.daily_usage_limiter import DailyUsageError, DailyUsageLimiter
from start_websocket_server import create_app
from test_compact_dsl_interface_retry import make_response
from test_daily_usage_api import make_repository
from test_daily_usage_limiter import NOW
from test_daily_usage_routes import final_message, frame_info, payload, run_route

pytestmark = pytest.mark.usefixtures("daily_usage_auth")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", sorted(routes.GENERATION_OPERATIONS))
@pytest.mark.parametrize(
    "failure",
    ["network", "timeout", "sts", "401", "403", "404", "500", "202", "json", "data", "false"],
)
async def test_api_failure_bypasses_without_counting_and_recovery_enforces_limit(
    monkeypatch, operation, failure
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", True)
    monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
    monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", False)
    monkeypatch.setattr(routes, "get_service", lambda _runtime: Mock())
    calls = []
    if failure == "sts":
        monkeypatch.setattr(
            daily_usage_api.sts_config,
            "get_sts_config",
            Mock(side_effect=[KeyError("private-sts-detail"), b"usage-test-secret"]),
        )

    async def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1 and failure != "sts":
            if failure == "network":
                raise httpx.ConnectError("offline", request=request)
            if failure == "timeout":
                await asyncio.sleep(10)
            if failure == "json":
                return httpx.Response(200, text="invalid JSON")
            if failure == "data":
                return httpx.Response(200, json={"success": True, "data": {"usedCount": "0"}})
            if failure == "false":
                return httpx.Response(200, json={"success": False})
            return httpx.Response(int(failure), json={"success": True})
        return httpx.Response(
            200, json={"success": True, "data": {"alreadyCounted": False, "usedCount": 20}}
        )

    limiter = DailyUsageLimiter(make_repository(handler), 20, 0.05)
    try:
        frames, generated = await run_route(
            monkeypatch, limiter, operation=operation,
            requests=[payload(interaction="1"), payload(interaction="2")],
        )
        finals = [frame for frame in frames if frame_info(frame).get("streamType") == "final"]
        assert len(finals) == 2
        assert final_message([finals[0]]).get("status") == "success"
        assert final_message([finals[1]]).get("errorCode") == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
        assert len(generated) == 1
        assert calls == (["/snapshot"] if failure == "sts" else ["/snapshot", "/snapshot"])
        assert settings.enable_daily_usage_limit is True
    finally:
        await limiter.aclose()


class FakeUsageAPI:
    """仅供测试的幂等 API，不作为生产回退。"""

    def __init__(self, *, lose_first_write_response=False):
        self.records = {}
        self.writes = []
        self.queries = []
        self.lose_first_write_response = lose_first_write_response

    def __call__(self, request):
        envelope = json.loads(request.content)
        body = envelope.get("body")
        assert isinstance(body, dict)
        uid_hash = body.get("uidHash")
        request_hash = body.get("requestIdHash")
        assert isinstance(uid_hash, str)
        assert isinstance(request_hash, str)
        key = (uid_hash, body.get("usageDate"))
        requests = self.records.get(key, [])
        if request.url.path.endswith("snapshot"):
            self.queries.append(body)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "alreadyCounted": request_hash in requests,
                        "usedCount": len(requests),
                    },
                },
            )
        self.writes.append(body)
        requests = self.records.setdefault(key, [])
        if request_hash not in requests:
            requests.append(request_hash)
        if self.lose_first_write_response and len(self.writes) == 1:
            raise httpx.ReadTimeout("committed but response lost", request=request)
        return httpx.Response(200, json={"success": True})


@pytest.mark.asyncio
async def test_lost_record_response_is_not_retried_and_duplicate_still_deduplicates():
    api = FakeUsageAPI(lose_first_write_response=True)
    limiter = DailyUsageLimiter(make_repository(api), 1, 1.0, clock=lambda: NOW)
    try:
        record = await limiter.check("user", "s&1")
        duplicate = await limiter.check("user", "s&1")
        assert record is not None
        assert duplicate is not None
        await limiter.record_success(record)
        assert len(api.writes) == 1
        await limiter.record_success(duplicate)
        assert len(api.writes) == 2
        assert len(api.records) == 1
        assert await limiter.check("user", "s&1") is None
        with pytest.raises(DailyUsageError) as captured:
            await limiter.check("user", "s&2")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
    finally:
        await limiter.aclose()


@pytest.mark.asyncio
async def test_cross_day_uses_entry_date_and_new_day_counts_same_request_again():
    api = FakeUsageAPI()
    limiter = DailyUsageLimiter(make_repository(api), 1, 1.0, clock=lambda: NOW)
    try:
        record = await limiter.check("user", "s&1")
        assert record is not None
        limiter.clock = lambda: NOW + timedelta(minutes=2)
        await limiter.record_success(record)
        assert api.writes[0].get("usageDate") == "2026-10-22"
        next_record = await limiter.check("user", "s&1")
        assert next_record is not None
        assert str(next_record.usage_date) == "2026-10-23"
        await limiter.record_success(next_record)
        await limiter.record_success(record)
        assert await limiter.check("user", "s&1") is None
        assert len(api.records) == 2
        assert all(len(requests) == 1 for requests in api.records.values())
    finally:
        await limiter.aclose()


@pytest.mark.asyncio
async def test_api_daily_row_appends_only_new_requests():
    api = FakeUsageAPI()
    limiter = DailyUsageLimiter(make_repository(api), 20, 1.0, clock=lambda: NOW)
    try:
        for request_id in ("s&1", "s&2", "s&3"):
            record = await limiter.check("user", request_id)
            assert record is not None
            await limiter.record_success(record)
            await limiter.record_success(record)
            snapshot = await limiter.repository.snapshot(record)
            assert snapshot.already_counted is True
        assert snapshot.used_count == 3
        assert len(api.records) == 1
        assert len(next(iter(api.records.values()))) == 3
    finally:
        await limiter.aclose()


def test_real_app_lifespan_websocket_and_http_adapter(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", True)
    monkeypatch.setattr(settings, "daily_usage_limit", 1)
    monkeypatch.setattr(settings, "hag_osms_ak", "usage-test-access-key")
    monkeypatch.setattr(settings, "daily_usage_slb", "https://usage.test:8443")
    monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
    monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", False)
    monkeypatch.setattr(settings, "ai_widget_data_huashan_enable", False)
    api = FakeUsageAPI()
    client_class = httpx.AsyncClient
    clients = []

    def client_factory(**options):
        client = client_class(transport=httpx.MockTransport(api), **options)
        clients.append(client)
        return client

    monkeypatch.setattr(daily_usage_api.httpx, "AsyncClient", client_factory)
    calls = []

    async def generate(request, *, before_model_call):
        calls.append(request)
        await before_model_call("2x2")
        return make_response()

    service = SimpleNamespace(trace_recorder=Mock(), generate_widget_card_compact_dsl=generate)
    monkeypatch.setattr(routes, "get_service", lambda _runtime: service)
    application = create_app()
    results = []
    with TestClient(application) as client:
        with client.websocket_connect("/api/v1/ws/tools/generateWidgetCardCompactDsl") as websocket:
            for interaction in ("1", "1", "2"):
                websocket.send_json(payload(interaction=interaction))
                frames = []
                while True:
                    received = websocket.receive_json()
                    frames.append(received)
                    if frame_info(received).get("streamType") == "final":
                        break
                results.append(final_message(frames))
    assert len(calls) == 2
    assert len(api.records) == 1
    assert len(api.writes) == 1
    assert len(api.queries) == 3
    assert results[0].get("status") == "success"
    assert results[1].get("status") == "success"
    assert results[2].get("errorCode") == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
    assert application.state.daily_usage_limiter is None
    assert clients
    assert clients[0].is_closed
