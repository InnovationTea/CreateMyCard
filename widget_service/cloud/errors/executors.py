# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional, Any

from errors.error_handler import ErrorResult
from errors.errors import AgentError
from errors.severity import ErrorSeverity
from errors.retry import RetryContext, RetryExecutor, RetryConfig, RetryExhaustedError, RETRY_CONFIGS

from app.logger import logger

# Callback type: receives a structured message dict, sends it to the client.
SendMessageCallback = Callable[[dict], Awaitable[None]]


class BaseExecutor(ABC):
    """Abstract base for severity-specific error executors."""

    @abstractmethod
    async def execute(self, error: BaseExecutor, severity: ErrorSeverity, **kwargs) -> "ErrorResult":
        ...

    @staticmethod
    def _build_log_entry(error: AgentError, severity: ErrorSeverity) -> dict:
        return {
            "severity": severity.value,
            "error_type": type(error).__name__
        }


class FatalExecutor(BaseExecutor):
    """FATAL: send fixed error message to client, signal abort."""

    MESSAGE = "服务内部异常，请稍后再试"

    def __init__(self, send_message: Optional[SendMessageCallback] = None):
        self._send_message = send_message

    async def execute(self, error: AgentError, severity: ErrorSeverity, **kwargs) -> "ErrorResult":

        log_entry = self._build_log_entry(error, severity)
        logger.error("Fatal error: %s", log_entry)

        if self._send_message:
            await self._send_message({
                "type": "task_error",
                "error": self.MESSAGE,
                "recoverable": False,
            })

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
    """USER_FACING: send error.user_message to client, signal abort.

    The message comes from error.user_message (set by business code when
    raising the exception). A class-level fallback is used only when
    user_message is empty.
    """

    FALLBACK_MESSAGE = "任务执行遇到问题，请稍后再试"

    def __init__(self, send_message: Optional[SendMessageCallback] = None):
        self._send_message = send_message

    async def execute(
        self, error: AgentError, severity: ErrorSeverity, *, retry: Optional[RetryContext] = None,
            **kwargs: Any,
    ) -> "ErrorResult":
        from errors.error_handler import ErrorResult as _ErrorResult

        log_entry = self._build_log_entry(error, severity)
        logger.warning("User-facing error: %s", log_entry)

        message = error.user_message or self.FALLBACK_MESSAGE

        if self._send_message:
            await self._send_message({
                "type": "task_error",
                "error": message,
                "recoverable": False,
            })

        return _ErrorResult(
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
    """RETRYABLE: send retry status to client, execute RetryExecutor.

    Accepts RetryContext via retry parameter from ErrorHandler.handle().
    If retry succeeds, ErrorResult.retry_result holds the business value.
    If retry exhausts, ErrorResult.should_abort = True.
    """

    MESSAGE = "服务暂时繁忙，正在重试中..."
    EXHAUSTED_MESSAGE = "服务暂时繁忙，请稍后再试"

    def __init__(
        self,
        send_message: Optional[SendMessageCallback] = None,
        default_config: Optional[RetryConfig] = None,
    ):
        self._send_message = send_message
        self._default_config = default_config or RetryConfig()

    async def execute(
        self, error: AgentError, severity: ErrorSeverity, *, retry: Optional[RetryContext] = None,
            **kwargs: Any,
    ) -> "ErrorResult":
        from errors.error_handler import ErrorResult as _ErrorResult

        log_entry = self._build_log_entry(error, severity)
        logger.warning("Retryable error: %s", log_entry)

        # No function to retry — just report and let caller decide
        if retry is None or retry.func is None:
            if self._send_message:
                await self._send_message({
                    "type": "status",
                    "status": "retrying",
                    "message": self.MESSAGE,
                })
            return _ErrorResult(
                error=error,
                severity=severity,
                should_retry=True,
                should_abort=False,
                should_notify_user=True,
                user_message=self.MESSAGE,
                can_recover=False,
                log_entry=log_entry,
            )

        # Build per-attempt callback: send retry status to client
        async def on_retry(attempt: int, delay: float, err: AgentError) -> None:
            if self._send_message:
                await self._send_message({
                    "type": "status",
                    "status": "retrying",
                    "message": f"正在重试 ({attempt})...",
                })

        # Resolve config: explicit name > default_config from constructor
        if retry.config_name and retry.config_name in RETRY_CONFIGS:
            config = RETRY_CONFIGS[retry.config_name]
        else:
            config = self._default_config

        retry_executor = RetryExecutor(config=config, config_name=retry.config_name or "default")

        try:
            result = await retry_executor.execute(
                retry.func, *retry.args,
                on_retry=on_retry,
                **retry.kwargs,
            )
            # Retry succeeded
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
        except RetryExhaustedError as exhausted:
            # All retries failed
            log_entry = self._build_log_entry(exhausted.last_error, severity)
            logger.error("Retry exhausted: %s", log_entry)

            if self._send_message:
                await self._send_message({
                    "type": "task_error",
                    "error": self.EXHAUSTED_MESSAGE,
                    "recoverable": False,
                })

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
    """RECOVERABLE: no client notification, signal recovery."""

    async def execute(self, error: AgentError, severity: ErrorSeverity, **kwargs) -> "ErrorResult":

        log_entry = self._build_log_entry(error, severity)
        logger.info("Recoverable error: %s", log_entry)

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