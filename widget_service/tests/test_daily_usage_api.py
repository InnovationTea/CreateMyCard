"""次数 API 契约与生命周期测试；不依赖真实 API 或数据库。"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import start_websocket_server
from config.config import Settings, get_settings
from services import daily_usage_api
from services.daily_usage_limiter import DailyUsageError, DailyUsageLimiter, DailyUsageRecord
from test_daily_usage_limiter import NOW


def record():
    return DailyUsageRecord("record-id", "a" * 64, "b" * 64, NOW.date())


def make_repository(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return daily_usage_api.APIDailyUsageRepository(
        client,
        httpx.URL("http://usage.test:8080/snapshot"),
        httpx.URL("http://usage.test:8080/record"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("session", ["session-from-context", None])
async def test_post_envelope_and_strict_snapshot(monkeypatch, session):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, json={"success": True, "data": {"alreadyCounted": False, "usedCount": 19}}
        )

    monkeypatch.setattr(daily_usage_api.task_logger, "get_session_id", lambda: session)
    repository = make_repository(handler)
    try:
        snapshot = await repository.snapshot(record())
        assert snapshot.used_count == 19
        assert snapshot.already_counted is False
        await repository.insert_success(record())
        assert [request.url.path for request in requests] == ["/snapshot", "/record"]
        for request in requests:
            assert request.method == "POST"
            assert request.headers.get("content-type") == "application/json"
            assert json.loads(request.content) == {
                "sessionId": session or "record-id",
                "body": {
                    "recordId": "record-id",
                    "uidHash": "a" * 64,
                    "requestIdHash": "b" * 64,
                    "usageDate": "2026-10-22",
                },
            }
    finally:
        await repository.aclose()
    assert repository.client.is_closed


@pytest.mark.asyncio
async def test_record_waits_for_api_confirmation_instead_of_background_scheduling():
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(_request):
        started.set()
        await release.wait()
        return httpx.Response(200, json={"success": True})

    repository = make_repository(handler)
    pending = asyncio.create_task(repository.insert_success(record()))
    try:
        await asyncio.wait_for(started.wait(), timeout=1.0)
        assert not pending.done()
        release.set()
        await pending
    finally:
        release.set()
        await pending
        await repository.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["snapshot", "insert_success"])
@pytest.mark.parametrize("response", [None, [], {}, {"success": False}, {"success": 1}])
async def test_unconfirmed_response_is_rejected(method, response):
    repository = make_repository(lambda _request: httpx.Response(200, json=response))
    try:
        with pytest.raises(ValueError):
            await getattr(repository, method)(record())
    finally:
        await repository.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"alreadyCounted": "false", "usedCount": 0},
        {"alreadyCounted": 0, "usedCount": 0},
        {"alreadyCounted": False},
        {"alreadyCounted": False, "usedCount": True},
        {"alreadyCounted": False, "usedCount": "0"},
        {"alreadyCounted": False, "usedCount": 0.0},
        {"alreadyCounted": False, "usedCount": -1},
    ],
)
async def test_invalid_snapshot_does_not_default_to_zero(data):
    repository = make_repository(
        lambda _request: httpx.Response(200, json={"success": True, "data": data})
    )
    try:
        with pytest.raises(ValueError):
            await repository.snapshot(record())
    finally:
        await repository.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["snapshot", "insert_success"])
@pytest.mark.parametrize("status", [202, 204, 302, 400, 500])
async def test_non_200_is_not_confirmation_and_redirect_is_not_followed(method, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"success": True}, headers={"Location": "/other"})

    repository = make_repository(handler)
    try:
        with pytest.raises((ValueError, httpx.HTTPStatusError)):
            await getattr(repository, method)(record())
        assert len(requests) == 1
    finally:
        await repository.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["snapshot", "insert_success"])
async def test_invalid_json_is_rejected(method):
    repository = make_repository(lambda _request: httpx.Response(200, text="not JSON"))
    try:
        with pytest.raises(ValueError):
            await getattr(repository, method)(record())
    finally:
        await repository.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError])
async def test_network_failure_rejects_generation(exception):
    def handler(request):
        raise exception("test offline", request=request)

    repository = make_repository(handler)
    limiter = DailyUsageLimiter(repository, 20, 1.0)
    try:
        with pytest.raises(DailyUsageError):
            await limiter.check("user", "s&1")
    finally:
        await limiter.aclose()


@pytest.mark.asyncio
async def test_api_total_timeout_and_cancellation_are_preserved():
    async def handler(_request):
        await asyncio.sleep(10)
        return httpx.Response(200, json={"success": True})

    repository = make_repository(handler)
    limiter = DailyUsageLimiter(repository, 20, 0.001)
    try:
        with pytest.raises(DailyUsageError):
            await limiter.check("user", "s&1")
        pending = asyncio.create_task(repository.snapshot(record()))
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    finally:
        await limiter.aclose()


@pytest.mark.asyncio
async def test_disabled_factory_never_creates_client_or_validates_url(monkeypatch):
    factory = Mock(side_effect=AssertionError("must not create client"))
    build_url = Mock(side_effect=AssertionError("must not validate URL"))
    monkeypatch.setattr(daily_usage_api.httpx, "AsyncClient", factory)
    monkeypatch.setattr(daily_usage_api, "_api_url", build_url)
    assert (
        await daily_usage_api.create_daily_usage_limiter(
            Settings(enable_daily_usage_limit=False, daily_usage_slb="")
        )
        is None
    )
    factory.assert_not_called()
    build_url.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configured,expected",
    [
        ("http://usage.test:8090", "http://usage.test:8090"),
        ("https://usage.test:8443/", "https://usage.test:8443"),
        ("https://usage.test", "https://usage.test"),
        ("http://usage.test/old/prefix/", "http://usage.test"),
        ("http://[::1]:8080/", "http://[::1]:8080"),
        ("  https://usage.test:8443/  ", "https://usage.test:8443"),
    ],
)
async def test_factory_address_timeout_and_no_startup_request(monkeypatch, configured, expected):
    client = Mock(post=AsyncMock(), aclose=AsyncMock())
    factory = Mock(return_value=client)
    monkeypatch.setattr(daily_usage_api.httpx, "AsyncClient", factory)
    limiter = await daily_usage_api.create_daily_usage_limiter(
        Settings(
            enable_daily_usage_limit=True,
            daily_usage_slb=configured,
            hag_slb_url="https://unrelated-hag.test:9443",
            daily_usage_api_snapshot_path="/custom/query",
            daily_usage_api_record_path="/custom/record",
            daily_usage_api_timeout_seconds=2.0,
        )
    )
    assert limiter is not None
    assert str(limiter.repository.snapshot_url) == f"{expected}/custom/query"
    assert str(limiter.repository.record_url) == f"{expected}/custom/record"
    factory.assert_called_once_with(timeout=2.0, follow_redirects=False, trust_env=False)
    client.post.assert_not_called()
    await limiter.aclose()
    client.aclose.assert_awaited_once()


@pytest.mark.parametrize("path", ["", "relative", "//other/path", "/path?q=1", "/path#x"])
def test_invalid_api_path_rejected(path):
    with pytest.raises(ValueError):
        daily_usage_api._api_url("https://usage.test:8443", path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "",
        " ",
        "usage.test:8080",
        "/relative",
        "ftp://usage.test",
        "http:///",
        "http://user:password@usage.test",
        "http://usage.test?q=1",
        "http://usage.test#x",
    ],
)
async def test_invalid_slb_url_rejected_before_client_creation(monkeypatch, base_url):
    factory = Mock()
    monkeypatch.setattr(daily_usage_api.httpx, "AsyncClient", factory)
    with pytest.raises(ValueError):
        await daily_usage_api.create_daily_usage_limiter(
            Settings(
                enable_daily_usage_limit=True,
                daily_usage_slb=base_url,
                hag_slb_url="https://unrelated-hag.test:9443",
            )
        )
    factory.assert_not_called()


@pytest.mark.parametrize(
    "option,value",
    [
        ("daily_usage_limit", 0),
        ("daily_usage_limit", True),
        ("daily_usage_limit", 2.0),
        ("daily_usage_api_timeout_seconds", 0),
    ],
)
def test_invalid_configuration_rejected(option, value):
    with pytest.raises(ValidationError):
        Settings(**{option: value})


def test_environment_overrides_and_mysql_settings_removed(monkeypatch):
    monkeypatch.setenv("WIDGET_SERVICE_DAILY_USAGE_SLB", "https://usage.test:8443")
    monkeypatch.setenv("WIDGET_SERVICE_HAG_SLB_URL", "https://unrelated-hag.test:9443")
    monkeypatch.setenv("WIDGET_SERVICE_DAILY_USAGE_API_HOST", "ignored.test")
    monkeypatch.setenv("WIDGET_SERVICE_DAILY_USAGE_API_PORT", "8091")
    monkeypatch.setenv("WIDGET_SERVICE_DAILY_USAGE_MYSQL_PASSWORD", "ignored-secret")
    settings = Settings()
    assert settings.daily_usage_slb == "https://usage.test:8443"
    assert settings.hag_slb_url == "https://unrelated-hag.test:9443"
    assert "daily_usage_api_host" not in settings.model_dump()
    assert "daily_usage_api_port" not in settings.model_dump()
    assert "ignored-secret" not in repr(settings)
    assert not any(name.startswith("daily_usage_mysql_") for name in settings.model_dump())


def test_lifespan_closes_api_client_and_preserves_query_health(monkeypatch):
    limiter = Mock(aclose=AsyncMock())
    factory = AsyncMock(return_value=limiter)
    monkeypatch.setattr(start_websocket_server, "create_daily_usage_limiter", factory)
    application = start_websocket_server.create_app()
    with TestClient(application) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert application.state.daily_usage_limiter is limiter
    limiter.aclose.assert_awaited_once()
    assert application.state.daily_usage_limiter is None
    factory.assert_awaited_once_with(get_settings())
