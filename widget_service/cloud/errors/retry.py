# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""带指数退避和抖动的异步重试执行器。"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from app.logger import logger
from errors.classifier import ErrorClassifier
from errors.codes import StatusCode
from errors.errors import BaseError
from errors.severity import ErrorSeverity

T = TypeVar("T")
RetryCallback = Callable[[int, float, BaseError], Awaitable[None]]


@dataclass
class RetryContext:
    """封装异常处理入口执行自动重试所需的参数。"""

    func: Callable[..., Awaitable[Any]] | None = None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    config_name: str | None = None


@dataclass(frozen=True)
class RetryConfig:
    """定义尝试次数、退避间隔和总超时。"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    total_timeout: float = 300.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("retry delays must not be negative")
        if self.exponential_base <= 0:
            raise ValueError("exponential_base must be greater than 0")
        if self.total_timeout <= 0:
            raise ValueError("total_timeout must be greater than 0")

    def compute_delay(
        self,
        attempt: int,
        rate_limit_hint: object = None,
    ) -> float:
        """计算指定重试次数执行前的等待时间。"""
        parsed_hint = self._parse_rate_limit_hint(rate_limit_hint)
        if parsed_hint is not None and parsed_hint > 0:
            return min(parsed_hint, self.max_delay)

        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay *= 0.5 + random.random()
        return delay

    @staticmethod
    def _parse_rate_limit_hint(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            logger.warning("Ignoring invalid retry-after value: {}", type(error).__name__)
            return None


RETRY_CONFIGS = {
    "llm_call": RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=60.0,
        total_timeout=300.0,
    ),
    "tool_call": RetryConfig(
        max_attempts=2,
        base_delay=1.0,
        max_delay=30.0,
        total_timeout=1200.0,
    ),
    "network": RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=30.0,
        total_timeout=180.0,
    ),
}


class RetryExhaustedError(BaseError):
    """重试次数用尽或总超时耗尽。"""

    def __init__(self, attempts: int, last_error: BaseError, config_name: str = ""):
        super().__init__(
            StatusCode.ERROR,
            msg=(
                f"Retry exhausted after {attempts} attempts (config={config_name}). "
                f"Last error: {last_error}"
            ),
            cause=last_error,
        )
        self.attempts = attempts
        self.last_error = last_error


class RetryExecutor:
    """执行异步函数，并自动重试被分类为可重试的异常。"""

    def __init__(self, config: RetryConfig | None = None, config_name: str = "default"):
        self.config = config or RetryConfig()
        self.config_name = config_name

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        on_retry: RetryCallback | None = None,
        **kwargs: Any,
    ) -> T:
        """执行函数，成功则返回结果，失败则抛出最后一次标准化异常。"""
        start_time = time.monotonic()
        last_error: BaseError | None = None
        completed_attempts = 0

        for attempt in range(self.config.max_attempts):
            if self._total_timeout_reached(start_time, attempt):
                break
            completed_attempts += 1

            try:
                return await func(*args, **kwargs)
            except Exception as raw_error:
                wrapped, severity = ErrorClassifier.classify(raw_error)
                last_error = wrapped
                logger.warning("Classified error [{}]: {}", severity.value, wrapped)
                if severity != ErrorSeverity.RETRYABLE:
                    raise wrapped from raw_error
                if attempt == self.config.max_attempts - 1:
                    break

                delay = self.config.compute_delay(
                    attempt,
                    getattr(wrapped, "retry_after", None),
                )
                remaining = self.config.total_timeout - (time.monotonic() - start_time)
                if delay > remaining:
                    break
                if on_retry is not None:
                    await on_retry(attempt + 1, delay, wrapped)
                await asyncio.sleep(delay)

        if last_error is None:
            last_error = ErrorClassifier.classify(TimeoutError("Retry timeout reached"))[0]
        raise RetryExhaustedError(
            attempts=completed_attempts,
            last_error=last_error,
            config_name=self.config_name,
        )

    def _total_timeout_reached(self, start_time: float, attempt: int) -> bool:
        elapsed = time.monotonic() - start_time
        return attempt > 0 and elapsed >= self.config.total_timeout
