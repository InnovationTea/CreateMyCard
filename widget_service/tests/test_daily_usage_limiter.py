"""每日次数业务语义；内存仓库仅用于单元测试，不是生产降级实现。"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from core.errors import ErrorCode
from services.daily_usage_limiter import DailyUsageError, DailyUsageLimiter, DailyUsageSnapshot

NOW = datetime(2026, 10, 22, 15, 59, tzinfo=UTC)


class MemoryUsageRepository:
    def __init__(self):
        self.records = {}
        self.reads = 0
        self.writes = 0
        self.closed = False

    async def snapshot(self, record):
        self.reads += 1
        requests = self.records.get((record.uid_hash, record.usage_date), [])
        return DailyUsageSnapshot(record.request_id_hash in requests, len(requests))

    async def insert_success(self, record):
        self.writes += 1
        requests = self.records.setdefault((record.uid_hash, record.usage_date), [])
        if record.request_id_hash not in requests:
            requests.append(record.request_id_hash)

    async def aclose(self):
        self.closed = True


def make_limiter(repository=None, *, limit=20, clock=lambda: NOW):
    if repository is None:
        repository = MemoryUsageRepository()
    return DailyUsageLimiter(repository, limit, 0.1, clock=clock)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 19, 20, 21])
async def test_daily_limit_boundaries_and_existing_request(count):
    limiter = make_limiter()
    for number in range(count):
        record = await make_limiter(limiter.repository, limit=100).check("user", f"s&{number}")
        assert record is not None
        await limiter.record_success(record)
    if count >= 20:
        with pytest.raises(DailyUsageError) as captured:
            await limiter.check("user", "s&new")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
    else:
        assert await limiter.check("user", "s&new") is not None
    if count:
        assert await limiter.check("user", "s&0") is None
    assert await limiter.check("different-user", "s&0") is not None


@pytest.mark.asyncio
async def test_limit_exception_uses_configured_message(monkeypatch):
    monkeypatch.setattr(get_settings(), "daily_usage_limit_exceeded_message", "自定义额度提示。")
    repository = AsyncMock()
    repository.snapshot.return_value = DailyUsageSnapshot(False, 20)
    with pytest.raises(DailyUsageError) as captured:
        await make_limiter(repository).check("user", "s&new")
    assert str(captured.value) == "自定义额度提示。"
    assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED


@pytest.mark.asyncio
@pytest.mark.parametrize("uid,request_id", [("", "s&1"), (" ", "s&1"), ("u", None), ("u", " ")])
async def test_missing_identity_never_calls_repository(uid, request_id):
    repository = AsyncMock()
    assert await make_limiter(repository).check(uid, request_id) is None
    repository.snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_cross_midnight_keeps_entry_date_but_new_day_can_count_same_request():
    clock = NOW
    limiter = make_limiter(limit=1, clock=lambda: clock)
    record = await limiter.check("user", "s&1")
    assert record is not None
    assert str(record.usage_date) == "2026-10-22"
    clock += timedelta(minutes=2)
    await limiter.record_success(record)
    next_record = await limiter.check("user", "s&1")
    assert next_record is not None
    assert str(next_record.usage_date) == "2026-10-23"
    await limiter.record_success(next_record)
    assert await limiter.check("user", "s&1") is None
    await limiter.record_success(record)
    assert len(limiter.repository.records) == 2
    assert all(len(requests) == 1 for requests in limiter.repository.records.values())
    with pytest.raises(DailyUsageError):
        await limiter.check("user", "s&2")


@pytest.mark.asyncio
async def test_duplicate_checks_and_writes_do_not_duplicate_success():
    limiter = make_limiter()
    first = await limiter.check("user", "s&1")
    duplicate = await limiter.check("user", "s&1")
    assert first is not None
    assert duplicate is not None
    await limiter.record_success(first)
    await limiter.record_success(first)
    await limiter.record_success(duplicate)
    assert len(limiter.repository.records) == 1
    assert first.uid_hash == hashlib.sha256(b"user").hexdigest()
    assert first.request_id_hash == hashlib.sha256(b"s&1").hexdigest()
    assert "user" not in repr(first)


@pytest.mark.asyncio
async def test_multiple_requests_share_daily_row_and_users_are_isolated():
    limiter = make_limiter()
    for request_id in ("s&1", "s&2", "s&3"):
        saved = await limiter.check("user", request_id)
        assert saved is not None
        await limiter.record_success(saved)
        await limiter.record_success(saved)
    assert len(limiter.repository.records) == 1
    requests = next(iter(limiter.repository.records.values()))
    assert len(requests) == 3
    assert len(set(requests)) == 3
    other = await limiter.check("other-user", "s&1")
    assert other is not None
    await limiter.record_success(other)
    assert len(limiter.repository.records) == 2
    snapshot = await limiter.repository.snapshot(other)
    assert snapshot.already_counted is True
    assert snapshot.used_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [OSError("offline"), TimeoutError("timeout")])
async def test_read_failure_bypasses_without_counting_and_next_request_recovers(exception):
    repository = AsyncMock()
    repository.snapshot.side_effect = exception
    limiter = make_limiter(repository)
    assert await limiter.check("user", "s&1") is None
    repository.insert_success.assert_not_awaited()
    repository.snapshot.side_effect = None
    repository.snapshot.return_value = DailyUsageSnapshot(False, 0)
    assert await limiter.check("user", "s&2") is not None
    repository.snapshot.return_value = DailyUsageSnapshot(False, 20)
    with pytest.raises(DailyUsageError) as captured:
        await limiter.check("user", "s&3")
    assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_usage_api_check_has_bounded_timeout():
    repository = AsyncMock()
    repository.snapshot.side_effect = lambda _record: None

    async def slow_read(_record):
        await asyncio.sleep(10)

    repository.snapshot.side_effect = slow_read
    limiter = DailyUsageLimiter(repository, 20, 0.001)
    assert await limiter.check("user", "s&1") is None
    repository.insert_success.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_count", [1, 2, 3])
async def test_write_failure_stops_without_retry_or_failing_delivered_result(failure_count):
    repository = AsyncMock()
    repository.snapshot.return_value = DailyUsageSnapshot(False, 0)
    outcomes = [OSError("offline")] * failure_count + [None]
    repository.insert_success.side_effect = outcomes
    limiter = make_limiter(repository)
    record = await limiter.check("user", "s&1")
    assert record is not None
    await limiter.record_success(record)
    assert repository.insert_success.await_count == 1
    for call in repository.insert_success.call_args_list:
        assert call.args == (record,)


@pytest.mark.asyncio
async def test_cancellation_is_not_swallowed_and_close_is_forwarded():
    repository = AsyncMock()
    repository.snapshot.side_effect = asyncio.CancelledError
    limiter = make_limiter(repository)
    with pytest.raises(asyncio.CancelledError):
        await limiter.check("user", "s&1")
    await limiter.aclose()
    repository.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_timeout_is_bounded_and_cancellation_is_not_swallowed():
    repository = AsyncMock()
    repository.snapshot.return_value = DailyUsageSnapshot(False, 0)
    limiter = DailyUsageLimiter(repository, 20, 0.001)
    record = await limiter.check("user", "s&1")
    assert record is not None

    async def slow_write(_record):
        await asyncio.sleep(10)

    repository.insert_success.side_effect = slow_write
    await asyncio.wait_for(limiter.record_success(record), timeout=0.5)
    repository.insert_success.assert_awaited_once_with(record)
    repository.insert_success.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await limiter.record_success(record)


@pytest.mark.parametrize("limit,timeout", [(0, 1.0), (-1, 1.0), (20, 0.0)])
def test_invalid_service_configuration(limit, timeout):
    with pytest.raises(ValueError):
        DailyUsageLimiter(MemoryUsageRepository(), limit, timeout)
