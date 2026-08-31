# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Retry executor with exponential backoff + jitter."""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import TypeVar, Callable, Awaitable, Optional

from errors.classifier import ErrorClassifier
from errors.codes import StatusCode
from errors.errors import AgentError, BaseError
from errors.severity import ErrorSeverity
from app.logger import logger

T = TypeVar("T")


@dataclass
class RetryContext:
    """重试请求上下文，封装 handle() 所需的重试参数。"""

    func: Optional[Callable[..., Awaitable]] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    config_name: Optional[str] = None


@dataclass
class RetryConfig:
    """重试策略配置。"""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    total_timeout: float = 300.0  # 5 分钟总超时

    def compute_delay(self, attempt: int, rate_limit_hint: Optional[float] = None) -> float:
        """计算第 attempt 次重试前的等待时间。"""
        # 如果服务端给了 retry-after，优先使用
        if rate_limit_hint and rate_limit_hint > 0:
            return min(rate_limit_hint, self.max_delay)
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.5 + random.random())  # [50%, 150%) 随机

        return delay


# 预置重试策略
RETRY_CONFIGS = {
    "llm_call": RetryConfig(max_attempts=3, base_delay=2.0, max_delay=60.0, total_timeout=300.0),
    "tool_call": RetryConfig(max_attempts=2, base_delay=1.0, max_delay=30.0, total_timeout=1200.0),
    "network": RetryConfig(max_attempts=3, base_delay=0.5, max_delay=30.0, total_timeout=180.0),
}


class RetryExhaustedError(AgentError):
    """所有重试用完后抛出。"""

    def __init__(self, attempts: int, last_error: AgentError, config_name: str = ""):
        super().__init__(
            StatusCode.ERROR,
            msg=(
                f"Retry exhausted after {attempts} attempts (config={config_name}). "
                f"Last error: {last_error}"
            ),
            retryable=False,
            cause=last_error,
        )
        self.attempts = attempts
        self.last_error = last_error
        self.user_message = getattr(last_error, "user_message", None)


class RetryExecutor:
    """执行一个 async 函数，遇到 RETRYABLE 错误时自动重试。"""

    def __init__(self, config: Optional[RetryConfig] = None, config_name: str = "default"):
        self.config = config or RetryConfig()
        self.config_name = config_name

    async def execute(
            self,
            func: Callable[..., Awaitable[T]],
            *args,
            on_retry: Optional[Callable[[int, float, AgentError], Awaitable[None]]] = None,
            **kwargs,
    ) -> T:
        """
        Args:
            func:       要执行的异步函数
            on_retry:   每次重试前的回调 (attempt, delay, error)
        """
        start_time = time.monotonic()
        last_error: Optional[BaseError] = None

        for attempt in range(self.config.max_attempts):
            # 检查总超时
            elapsed = time.monotonic() - start_time
            if attempt > 0 and elapsed >= self.config.total_timeout:
                break

            try:
                return await func(*args, **kwargs)
            except Exception as raw_error:
                wrapped, severity = ErrorClassifier.classify(raw_error)
                last_error = wrapped
                logger.warning("Classified error [%s]: %s", severity.value, wrapped)
                # 不可重试 → 直接抛出
                if severity != ErrorSeverity.RETRYABLE:
                    raise wrapped from raw_error

                # 最后一次尝试 → 不再等待
                if attempt == self.config.max_attempts - 1:
                    break
                logger.warning(f"第{attempt}次尝试重新调用..")
                # 计算等待时间
                rate_hint = getattr(wrapped, "retry_after", None)
                delay = self.config.compute_delay(attempt, rate_hint)

                # 确保等待后不超总超时
                remaining = self.config.total_timeout - (time.monotonic() - start_time)
                if delay > remaining:
                    break

                # 回调通知
                if on_retry:
                    await on_retry(attempt + 1, delay, wrapped)

                await asyncio.sleep(delay)

        # 所有重试用完
        raise RetryExhaustedError(
            attempts=self.config.max_attempts,
            last_error=last_error,
            config_name=self.config_name,
        )