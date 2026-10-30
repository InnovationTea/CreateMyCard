"""每日次数打点口径及打点失败隔离。"""

import asyncio
import hashlib
from unittest.mock import AsyncMock, Mock, call

import pytest

from api import routes
from config.config import get_settings
from core.errors import ErrorCode
from services import daily_usage_limiter
from services.daily_usage_limiter import DailyUsageError, DailyUsageSnapshot
from test_daily_usage_limiter import make_limiter
from test_daily_usage_routes import OPERATION, payload, run_route
from utils import ops_metrics


@pytest.fixture
def metric_report(monkeypatch):
    report = Mock()
    monkeypatch.setattr(daily_usage_limiter, "report_ops_metrics", report)
    return report


@pytest.mark.asyncio
@pytest.mark.parametrize("used_count", [20, 21])
async def test_each_rejection_reports_even_for_same_request(metric_report, used_count):
    repository = AsyncMock()
    repository.snapshot.return_value = DailyUsageSnapshot(False, used_count)
    limiter = make_limiter(repository)
    for _ in range(2):
        with pytest.raises(DailyUsageError) as captured:
            await limiter.check("user", "same-request")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
    assert metric_report.call_args_list == [
        call(body={"dailyUsageLimitExceeded": 1}),
        call(body={"dailyUsageLimitExceeded": 1}),
    ]
    repository.insert_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_each_write_confirmation_reports_including_idempotent_success(metric_report):
    limiter = make_limiter(limit=1)
    record = await limiter.check("user", "request")
    assert record is not None
    metric_report.assert_not_called()
    await limiter.record_success(record)
    await limiter.record_success(record)
    assert metric_report.call_args_list == [
        call(body={"dailyUsageDeductSuccess": 1}),
        call(body={"dailyUsageDeductSuccess": 1}),
    ]
    # 数据库模拟仓库只记一次；后续前置查询命中已计次不再上报。
    assert await limiter.repository.snapshot(record) == DailyUsageSnapshot(True, 1)
    assert await limiter.check("user", "request") is None
    assert metric_report.call_count == 2


@pytest.mark.asyncio
async def test_write_reports_only_after_confirmation(metric_report):
    limiter = make_limiter()
    record = await limiter.check("user", "request")
    assert record is not None
    started = asyncio.Event()
    release = asyncio.Event()

    async def write(_record):
        started.set()
        await release.wait()

    limiter.repository.insert_success = write
    task = asyncio.create_task(limiter.record_success(record))
    try:
        await started.wait()
        metric_report.assert_not_called()
    finally:
        release.set()
        await task
    metric_report.assert_called_once_with(body={"dailyUsageDeductSuccess": 1})


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [OSError("offline"), TimeoutError("timeout")])
async def test_api_failures_do_not_report(metric_report, failure):
    repository = AsyncMock()
    repository.snapshot.side_effect = failure
    limiter = make_limiter(repository)
    assert await limiter.check("user", "request") is None
    repository.snapshot.side_effect = None
    repository.snapshot.return_value = DailyUsageSnapshot(False, 0)
    record = await limiter.check("user", "request")
    assert record is not None
    repository.insert_success.side_effect = failure
    await limiter.record_success(record)
    metric_report.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["reject", "record"])
async def test_metric_dispatch_failure_preserves_business_result(
    monkeypatch, metric_report, operation
):
    metric_report.side_effect = RuntimeError("dispatch\nfailed")
    log = Mock()
    monkeypatch.setattr(daily_usage_limiter, "logger", log)
    repository = AsyncMock()
    limiter = make_limiter(repository)
    if operation == "reject":
        repository.snapshot.return_value = DailyUsageSnapshot(False, 20)
        with pytest.raises(DailyUsageError) as captured:
            await limiter.check("user", "request")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
    else:
        repository.snapshot.return_value = DailyUsageSnapshot(False, 0)
        record = await limiter.check("user", "request")
        assert record is not None
        await limiter.record_success(record)
        repository.insert_success.assert_awaited_once_with(record)
    metric_report.assert_called_once()
    message = log.warning.call_args_list[0].args[0]
    assert "metric_dispatch_failed" in message
    assert "RuntimeError" in message
    assert "dispatch\\nfailed" in message
    assert "\n" not in message


@pytest.mark.asyncio
@pytest.mark.parametrize("bypass", ["disabled", "whitelist", "missing_uid", "missing_request"])
async def test_route_bypasses_do_not_report(monkeypatch, metric_report, bypass):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", bypass != "disabled")
    whitelist = hashlib.sha256(b"user").hexdigest() if bypass == "whitelist" else ""
    monkeypatch.setattr(settings, "daily_usage_uid_whitelist", whitelist)
    request = payload(uid="" if bypass == "missing_uid" else "user")
    request_id = None if bypass == "missing_request" else "request"
    assert await routes._check_daily_usage(OPERATION, request, request_id, make_limiter()) is None
    metric_report.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["success", "degraded", "failed"])
async def test_generation_delivery_controls_success_metric(monkeypatch, metric_report, status):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_daily_usage_limit", True)
    monkeypatch.setattr(settings, "daily_usage_uid_whitelist", "")
    monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
    monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", False)
    monkeypatch.setattr(routes, "get_service", lambda _runtime: Mock())
    await run_route(monkeypatch, make_limiter(), status=status)
    if status == "success":
        metric_report.assert_called_once_with(body={"dailyUsageDeductSuccess": 1})
    else:
        metric_report.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_existing_metrics_switch_and_session_are_reused(monkeypatch, enabled):
    monkeypatch.setattr(get_settings(), "ai_widget_data_huashan_enable", enabled)
    monkeypatch.setattr(ops_metrics.task_logger, "get_session_id", lambda: "usage-session")
    send = AsyncMock()
    monkeypatch.setattr(ops_metrics, "_report_ops_metrics_async", send)
    limiter = make_limiter()
    record = await limiter.check("user", "request")
    assert record is not None
    await limiter.record_success(record)
    await asyncio.sleep(0)
    if enabled:
        send.assert_awaited_once()
        assert send.call_args.args[1] == {
            "sessionId": "usage-session", "body": {"dailyUsageDeductSuccess": 1}
        }
    else:
        send.assert_not_called()
