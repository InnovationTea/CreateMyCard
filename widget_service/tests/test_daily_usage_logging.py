"""每日次数日志覆盖：跳过、查询、交付边界、写入重试及隐私保护。"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from api import routes
from config.config import get_settings
from services import daily_usage_api, daily_usage_limiter
from services.daily_usage_limiter import DailyUsageError
from test_daily_usage_api import make_repository, record
from test_daily_usage_limiter import make_limiter
from test_daily_usage_routes import OPERATION, payload, run_route

pytestmark = pytest.mark.usefixtures("daily_usage_auth")


@pytest.fixture
def usage_logs(monkeypatch):
    messages = []

    def capture(message, *args, **kwargs):
        if "[Daily Usage]" in message:
            messages.append(message)

    log = Mock(info=capture, warning=capture, error=capture)
    for module in (routes, daily_usage_api, daily_usage_limiter):
        monkeypatch.setattr(module, "logger", log)
    return messages


@pytest.fixture
def route_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", True)
    monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
    monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", False)
    monkeypatch.setattr(routes, "get_service", lambda _runtime: Mock())
    return settings


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_initialization_logs_effective_switch(monkeypatch, usage_logs, enabled):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", enabled)
    monkeypatch.setattr(settings, "daily_usage_slb", "https://usage.test:8443")
    limiter = await daily_usage_api.create_daily_usage_limiter(settings)
    try:
        assert f"initializing enabled={enabled}" in usage_logs[0]
        assert f"initialized client_ready={enabled}" in usage_logs[-1]
    finally:
        if limiter is not None:
            await limiter.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason", ["disabled", "non_generation", "missing_uid", "missing_request_id"]
)
async def test_check_bypass_logs_reason(monkeypatch, route_settings, usage_logs, reason):
    operation = OPERATION
    request = payload()
    request_id = "session&1"
    if reason == "disabled":
        monkeypatch.setattr(route_settings, "enable_daily_usage_limit", False)
    elif reason == "non_generation":
        operation = "getWidgetCapabilityOverview"
    elif reason == "missing_uid":
        request = payload(uid="")
    else:
        request_id = None
    assert await routes._check_daily_usage(operation, request, request_id, None) is None
    assert f"reason={reason}" in usage_logs[-1]


@pytest.mark.asyncio
async def test_missing_client_is_logged(route_settings, usage_logs):
    with pytest.raises(DailyUsageError):
        await routes._check_daily_usage(OPERATION, payload(), "s&1", None)
    assert "reason=client_not_initialized" in usage_logs[-1]


@pytest.mark.asyncio
async def test_quota_decisions_and_no_raw_identity(usage_logs):
    limiter = make_limiter(limit=1)
    saved = await limiter.check("private-user", "private-request")
    assert saved is not None
    assert "check_started" in usage_logs[0]
    assert "used_count=0 limit=1 already_counted=False" in usage_logs[1]
    assert "reason=within_limit record_required=True" in usage_logs[-1]
    await limiter.record_success(saved)
    assert "recorded" in usage_logs[-1]
    assert await limiter.check("private-user", "private-request") is None
    assert "reason=already_counted record_required=False" in usage_logs[-1]
    with pytest.raises(DailyUsageError):
        await limiter.check("private-user", "another-request")
    assert "reason=limit_exceeded used_count=1 limit=1" in usage_logs[-1]
    text = "\n".join(usage_logs)
    assert "private-user" not in text
    assert "private-request" not in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "used_count,already_counted,remaining",
    [(0, False, 20), (19, False, 1), (20, False, 0), (21, False, 0), (21, True, 0)],
)
async def test_remaining_count_logs_actual_snapshot(
    usage_logs, used_count, already_counted, remaining
):
    repository = AsyncMock()
    repository.snapshot.return_value = daily_usage_limiter.DailyUsageSnapshot(
        already_counted, used_count
    )
    limiter = make_limiter(repository)
    if used_count >= 20 and not already_counted:
        with pytest.raises(DailyUsageError):
            await limiter.check("user", "s&1")
    else:
        await limiter.check("user", "s&1")
    checked = [message for message in usage_logs if "[Daily Usage] checked " in message]
    assert len(checked) == 1
    assert f"used_count={used_count} limit=20" in checked[0]
    assert f"remaining_count={remaining}" in checked[0]
    assert f"remaining_count={remaining}" in usage_logs[-1]
    repository.insert_success.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failures", [1, 3])
async def test_record_retry_logs_attempts_and_final_outcome(usage_logs, failures):
    limiter = make_limiter()
    saved = await limiter.check("user", "s&1")
    assert saved is not None
    limiter.repository.insert_success = AsyncMock(
        side_effect=[OSError("private-error-detail")] * failures + [None]
    )
    usage_logs.clear()
    await limiter.record_success(saved)
    for attempt in range(1, min(failures + 1, 3) + 1):
        expected = f"record_started record_id={saved.record_id} attempt={attempt} max_attempts=3"
        assert any(expected in message for message in usage_logs)
    outcome = "record_exhausted" if failures == 3 else "recorded"
    assert outcome in usage_logs[-1]
    assert "private-error-detail" not in "\n".join(usage_logs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options,skipped",
    [
        ({}, False),
        ({"status": "failed"}, True),
        ({"status": "degraded"}, True),
        ({"artifact": False}, True),
        ({"fail_frame": "command_start"}, True),
        ({"fail_frame": "command_success"}, True),
        ({"fail_frame": "final"}, False),
    ],
)
async def test_delivery_skips_are_visible(
    monkeypatch, route_settings, usage_logs, options, skipped
):
    limiter = make_limiter()
    await run_route(monkeypatch, limiter, **options)
    skip_logs = [message for message in usage_logs if "record_skipped" in message]
    assert bool(skip_logs) is skipped
    if skipped:
        assert "reason=success_delivery_not_confirmed" in skip_logs[-1]
        assert limiter.repository.writes == 0
    else:
        assert any("recorded" in message for message in usage_logs)
        assert limiter.repository.writes == 1


@pytest.mark.asyncio
async def test_commands_disabled_skip_is_visible(monkeypatch, route_settings, usage_logs):
    monkeypatch.setattr(route_settings, "enable_widget_directive_commands", False)
    await run_route(monkeypatch, make_limiter())
    assert any("record_skipped" in message for message in usage_logs)


@pytest.mark.asyncio
async def test_generation_exception_logs_skipped_record(monkeypatch, route_settings, usage_logs):
    async def fail(_attempt):
        raise ValueError("invalid generation")

    limiter = make_limiter()
    await run_route(monkeypatch, limiter, handler=fail)
    assert any("record_skipped" in message for message in usage_logs)
    assert limiter.repository.writes == 0


@pytest.mark.asyncio
async def test_failed_record_is_not_misreported_as_skipped(monkeypatch, route_settings, usage_logs):
    limiter = make_limiter()
    limiter.repository.insert_success = AsyncMock(side_effect=OSError("offline"))
    await run_route(monkeypatch, limiter)
    text = "\n".join(usage_logs)
    assert "record_exhausted" in text
    assert "record_skipped" not in text
    assert "[Daily Usage] recorded " not in text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 503])
async def test_api_logs_status_and_duration_without_body(usage_logs, status):
    repository = make_repository(
        lambda _request: httpx.Response(status, json={"success": True, "secret": "private-body"})
    )
    try:
        if status == 200:
            await repository.insert_success(record())
        else:
            with pytest.raises(httpx.HTTPStatusError):
                await repository.insert_success(record())
    finally:
        await repository.aclose()
    assert "api_started operation=record_success record_id=record-id" in usage_logs[0]
    assert f"http_status={status}" in usage_logs[-1]
    assert "duration_ms=" in usage_logs[-1]
    assert "private-body" not in "\n".join(usage_logs)


@pytest.mark.asyncio
async def test_api_transport_failure_is_logged_without_exception_text(usage_logs):
    def fail(_request):
        raise httpx.ConnectError("private-network-detail")

    repository = make_repository(fail)
    limiter = make_limiter(repository)
    try:
        with pytest.raises(DailyUsageError):
            await limiter.check("private-user", "private-request")
    finally:
        await limiter.aclose()
    text = "\n".join(usage_logs)
    assert "api_failed operation=snapshot" in text
    assert "exception_type=ConnectError" in text
    assert "check_failed" in usage_logs[-1]
    assert "private-network-detail" not in text
