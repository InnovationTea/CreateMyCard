"""每日成功记录：按用户和 requestId 去重，不预占并发额度。"""

import asyncio
import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from app.logger import logger
from core.errors import ErrorCode

_BEIJING = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class DailyUsageSnapshot:
    already_counted: bool
    used_count: int


@dataclass(frozen=True)
class DailyUsageRecord:
    record_id: str
    uid_hash: str
    request_id_hash: str
    usage_date: date


class DailyUsageRepository(Protocol):
    async def snapshot(self, record: DailyUsageRecord) -> DailyUsageSnapshot:
        """查询同轮成功记录及当天使用次数。"""
        ...

    async def insert_success(self, record: DailyUsageRecord) -> None:
        """幂等写入成功记录。"""
        ...

    async def aclose(self) -> None:
        """关闭底层资源。"""
        ...


class DailyUsageError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _beijing_now() -> datetime:
    return datetime.now(_BEIJING)


class DailyUsageLimiter:
    def __init__(
        self,
        repository: DailyUsageRepository,
        limit: int,
        timeout_seconds: float,
        *,
        clock: Callable[[], datetime] = _beijing_now,
    ) -> None:
        if limit <= 0 or timeout_seconds <= 0:
            raise ValueError("daily usage limit and timeout must be positive")
        self.repository = repository
        self.limit = limit
        self.timeout_seconds = timeout_seconds
        self.clock = clock

    async def check(self, uid: str, request_id: str | None) -> DailyUsageRecord | None:
        record: DailyUsageRecord | None = None
        if not uid.strip() or not request_id:
            logger.info("[Daily Usage] bypass reason=missing_identity")
            return record
        if not request_id.strip():
            logger.info("[Daily Usage] bypass reason=missing_request_id")
            return record
        record = DailyUsageRecord(
            record_id=uuid.uuid4().hex,
            uid_hash=hashlib.sha256(uid.encode("utf-8")).hexdigest(),
            request_id_hash=hashlib.sha256(request_id.encode("utf-8")).hexdigest(),
            usage_date=self.clock().astimezone(_BEIJING).date(),
        )
        try:
            async with asyncio.timeout(self.timeout_seconds):
                snapshot = await self.repository.snapshot(record)
        except Exception as exc:
            logger.error(
                f"[Daily Usage] check_failed uid_hash={record.uid_hash} "
                f"exception_type={type(exc).__name__} reason=usage_api_check_failed"
            )
            raise DailyUsageError(
                ErrorCode.DAILY_USAGE_LIMIT_UNAVAILABLE,
                "暂时无法检查今日卡片生成次数，请稍后重试。",
            ) from exc
        logger.info(
            f"[Daily Usage] checked uid_hash={record.uid_hash} "
            f"request_id_hash={record.request_id_hash} date={record.usage_date} "
            f"used_count={snapshot.used_count} limit={self.limit} "
            f"already_counted={snapshot.already_counted}"
        )
        if snapshot.already_counted:
            record = None
        elif snapshot.used_count >= self.limit:
            raise DailyUsageError(
                ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED,
                "今日 AI 卡片生成次数已达上限，请明天再尝试。",
            )
        return record

    async def record_success(self, record: DailyUsageRecord) -> None:
        """交付后有限重试；唯一键保证提交响应丢失后重试仍只记录一次。"""
        delays = (0.0, 0.1, 0.3)
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                await asyncio.sleep(delay)
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    await self.repository.insert_success(record)
            except Exception as exc:
                logger.error(
                    f"[Daily Usage] record_failed uid_hash={record.uid_hash} "
                    f"request_id_hash={record.request_id_hash} date={record.usage_date} "
                    f"attempt={attempt} exception_type={type(exc).__name__} "
                    "reason=usage_api_record_failed"
                )
            else:
                logger.info(
                    f"[Daily Usage] recorded uid_hash={record.uid_hash} "
                    f"request_id_hash={record.request_id_hash} date={record.usage_date}"
                )
                return
        logger.error(
            f"[Daily Usage] record_exhausted uid_hash={record.uid_hash} "
            f"request_id_hash={record.request_id_hash} reason=delivered_but_not_confirmed_by_api"
        )

    async def aclose(self) -> None:
        await self.repository.aclose()
