# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""各异常级别对应的处理执行器。"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from app.logger import logger
from errors.errors import BaseError
from errors.result import ErrorResult
from errors.retry import (
    RETRY_CONFIGS,
    RetryConfig,
    RetryContext,
    RetryExecutor,
    RetryExhaustedError,
)
from errors.severity import ErrorSeverity

SendMessageCallback = Callable[[dict[str, Any]], Awaitable[None]]


class BaseExecutor(ABC):
    """异常执行器的统一接口。"""

    @abstractmethod
    async def execute(
        self,
        error: BaseError,
        severity: ErrorSeverity,
        **kwargs: Any,
    ) -> ErrorResult:
        """处理异常并返回统一结果。"""

    @staticmethod
    def _build_log_entry(error: BaseError, severity: ErrorSeverity) -> dict[str, str]:
        return {
            "severity": severity.value,
            "error_type": type(error).__name__,
        }


class FatalExecutor(BaseExecutor):
    """中断任务，并向客户端发送固定错误提示。"""

    MESSAGE = "服务内部异常，请稍后再试"

    def __init__(self, send_message: SendMessageCallback | None = None):
        self._send_message = send_message

    async def execute(
        self,
        error: BaseError,
        severity: ErrorSeverity,
        **kwargs: Any,
    ) -> ErrorResult:
        log_entry = self._build_log_entry(error, severity)
        logger.error("Fatal error: {}", log_entry)

        if self._send_message is not None:
            await self._send_message(
                {
                    "type": "task_error",
                    "error": self.MESSAGE,
                    "recoverable": False,
                }
            )

        return ErrorResult(
            error=error,
            severity=severity,
            should_retry=False,
            should_abort=True,
            should_notify_user=True,
            user_message=self.MESSAGE,
            can_recover=False,
            log_entry=log_entry,
        )


class UserFacingExecutor(BaseExecutor):
    """中断任务，并向客户端发送异常携带的用户提示。"""

    FALLBACK_MESSAGE = "任务执行遇到问题，请稍后再试"

    def __init__(self, send_message: SendMessageCallback | None = None):
        self._send_message = send_message

    async def execute(
        self,
        error: BaseError,
        severity: ErrorSeverity,
        **kwargs: Any,
    ) -> ErrorResult:
        log_entry = self._build_log_entry(error, severity)
        logger.warning("User-facing error: {}", log_entry)
        message = getattr(error, "user_message", None) or self.FALLBACK_MESSAGE

        if self._send_message is not None:
            await self._send_message(
                {
                    "type": "task_error",
                    "error": message,
                    "recoverable": False,
                }
            )

        return ErrorResult(
            error=error,
            severity=severity,
            should_retry=False,
            should_abort=True,
            should_notify_user=True,
            user_message=message,
            can_recover=False,
            log_entry=log_entry,
        )


class RetryableExecutor(BaseExecutor):
    """根据重试上下文自动重试，或提示调用方稍后重试。"""

    MESSAGE = "服务暂时繁忙，正在重试中..."
    EXHAUSTED_MESSAGE = "服务暂时繁忙，请稍后再试"

    def __init__(
        self,
        send_message: SendMessageCallback | None = None,
        default_config: RetryConfig | None = None,
    ):
        self._send_message = send_message
        self._default_config = default_config or RetryConfig()

    async def execute(
        self,
        error: BaseError,
        severity: ErrorSeverity,
        *,
        retry: RetryContext | None = None,
        **kwargs: Any,
    ) -> ErrorResult:
        log_entry = self._build_log_entry(error, severity)
        logger.warning("Retryable error: {}", log_entry)

        if retry is None or retry.func is None:
            await self._notify_retrying(self.MESSAGE)
            return ErrorResult(
                error=error,
                severity=severity,
                should_retry=True,
                should_abort=False,
                should_notify_user=True,
                user_message=self.MESSAGE,
                can_recover=False,
                log_entry=log_entry,
            )

        async def on_retry(attempt: int, delay: float, retry_error: BaseError) -> None:
            logger.info(
                "Retrying after error: attempt={}, delay={}, error_type={}",
                attempt,
                delay,
                type(retry_error).__name__,
            )
            await self._notify_retrying(f"正在重试 ({attempt})...")

        config = self._resolve_config(retry)
        retry_executor = RetryExecutor(
            config=config,
            config_name=retry.config_name or "default",
        )

        try:
            result = await retry_executor.execute(
                retry.func,
                *retry.args,
                on_retry=on_retry,
                **retry.kwargs,
            )
        except RetryExhaustedError as exhausted:
            return await self._handle_exhausted(exhausted, severity)

        return ErrorResult(
            error=error,
            severity=severity,
            should_retry=False,
            should_abort=False,
            should_notify_user=False,
            user_message=None,
            can_recover=False,
            log_entry=log_entry,
            retry_result=result,
        )

    def _resolve_config(self, retry: RetryContext) -> RetryConfig:
        if retry.config_name is None:
            return self._default_config
        return RETRY_CONFIGS.get(retry.config_name, self._default_config)

    async def _notify_retrying(self, message: str) -> None:
        if self._send_message is None:
            return
        await self._send_message(
            {
                "type": "status",
                "status": "retrying",
                "message": message,
            }
        )

    async def _handle_exhausted(
        self,
        exhausted: RetryExhaustedError,
        severity: ErrorSeverity,
    ) -> ErrorResult:
        log_entry = self._build_log_entry(exhausted.last_error, severity)
        logger.error("Retry exhausted: {}", log_entry)

        if self._send_message is not None:
            await self._send_message(
                {
                    "type": "task_error",
                    "error": self.EXHAUSTED_MESSAGE,
                    "recoverable": False,
                }
            )

        return ErrorResult(
            error=exhausted.last_error,
            severity=severity,
            should_retry=False,
            should_abort=True,
            should_notify_user=True,
            user_message=self.EXHAUSTED_MESSAGE,
            can_recover=False,
            log_entry=log_entry,
        )


class RecoverableExecutor(BaseExecutor):
    """不通知客户端，将错误交回调用方继续恢复。"""

    async def execute(
        self,
        error: BaseError,
        severity: ErrorSeverity,
        **kwargs: Any,
    ) -> ErrorResult:
        log_entry = self._build_log_entry(error, severity)
        logger.info("Recoverable error: {}", log_entry)
        return ErrorResult(
            error=error,
            severity=severity,
            should_retry=False,
            should_abort=False,
            should_notify_user=False,
            user_message=None,
            can_recover=True,
            log_entry=log_entry,
        )
