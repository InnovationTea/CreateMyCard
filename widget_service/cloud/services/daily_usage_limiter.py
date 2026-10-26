"""每日成功记录：按用户、入口日期和 requestId 去重，不预占并发额度。"""

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
        """查询指定入口日期的同轮成功记录及使用次数。"""
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
        if not uid.strip():
            logger.info("[Daily Usage] bypass reason=missing_uid")
            return record
        if not request_id or not request_id.strip():
            logger.info("[Daily Usage] bypass reason=missing_request_id")
            return record
        record = DailyUsageRecord(
            record_id=uuid.uuid4().hex,
            uid_hash=hashlib.sha256(uid.encode("utf-8")).hexdigest(),
            request_id_hash=hashlib.sha256(request_id.encode("utf-8")).hexdigest(),
            usage_date=self.clock().astimezone(_BEIJING).date(),
        )
        logger.info(
            f"[Daily Usage] check_started record_id={record.record_id} "
            f"uid_hash={record.uid_hash} request_id_hash={record.request_id_hash} "
            f"date={record.usage_date} limit={self.limit}"
        )
        try:
            async with asyncio.timeout(self.timeout_seconds):
                snapshot = await self.repository.snapshot(record)
        except Exception as exc:
            logger.error(
                f"[Daily Usage] check_failed record_id={record.record_id} "
                f"uid_hash={record.uid_hash} request_id_hash={record.request_id_hash} "
                f"exception_type={type(exc).__name__} reason=usage_api_check_failed "
                "action=bypass record_required=False"
            )
            record = None
            return record
        remaining_count = max(self.limit - snapshot.used_count, 0)
        logger.info(
            f"[Daily Usage] checked record_id={record.record_id} uid_hash={record.uid_hash} "
            f"request_id_hash={record.request_id_hash} date={record.usage_date} "
            f"used_count={snapshot.used_count} limit={self.limit} "
            f"already_counted={snapshot.already_counted} remaining_count={remaining_count}"
        )
        if snapshot.already_counted:
            logger.info(
                f"[Daily Usage] allowed record_id={record.record_id} "
                f"reason=already_counted record_required=False remaining_count={remaining_count}"
            )
            record = None
        elif snapshot.used_count >= self.limit:
            logger.warning(
                f"[Daily Usage] rejected record_id={record.record_id} "
                f"reason=limit_exceeded used_count={snapshot.used_count} limit={self.limit} "
                f"remaining_count={remaining_count}"
            )
            raise DailyUsageError(
                ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED,
                "今日 AI 卡片生成次数已达上限，请明天再尝试。",
            )
        else:
            logger.info(
                f"[Daily Usage] allowed record_id={record.record_id} "
                f"reason=within_limit record_required=True remaining_count={remaining_count}"
            )
        return record

    async def record_success(self, record: DailyUsageRecord) -> None:
        """交付后尝试一次；失败降级，不累积重试等待或改变生成结果。"""
        logger.info(
            f"[Daily Usage] record_started record_id={record.record_id} "
            "attempt=1 max_attempts=1"
        )
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await self.repository.insert_success(record)
        except Exception as exc:
            logger.error(
                f"[Daily Usage] record_failed record_id={record.record_id} "
                f"uid_hash={record.uid_hash} "
                f"request_id_hash={record.request_id_hash} date={record.usage_date} "
                f"attempt=1 exception_type={type(exc).__name__} "
                "reason=usage_api_record_failed action=continue_without_confirmation"
            )
        else:
            logger.info(
                f"[Daily Usage] recorded record_id={record.record_id} attempt=1 "
                f"uid_hash={record.uid_hash} "
                f"request_id_hash={record.request_id_hash} date={record.usage_date}"
            )

    async def aclose(self) -> None:
        await self.repository.aclose()
