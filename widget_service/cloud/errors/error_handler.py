# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

from __future__ import annotations

from typing import Optional, Dict, Any

from errors.classifier import ErrorClassifier
from errors.codes import StatusCode
from errors.errors import AgentError, raise_error
from errors.severity import ErrorSeverity
from errors.retry import RetryContext
from errors.executors import (
    BaseExecutor,
    SendMessageCallback,
    FatalExecutor,
    UserFacingExecutor,
    RetryableExecutor,
    RecoverableExecutor,
)


class ErrorResult:
    """Return value of ErrorHandler.handle(), tells the caller what to do next."""

    def __init__(
        self,
        error: AgentError,
        severity: ErrorSeverity,
        should_retry: bool,
        should_abort: bool,
        should_notify_user: bool,
        user_message: Optional[str],
        can_recover: bool,
        log_entry: dict,
        retry_result: Any = None,
    ):
        self.error = error
        self.severity = severity
        self.should_retry = should_retry
        self.should_abort = should_abort
        self.should_notify_user = should_notify_user
        self.user_message = user_message
        self.can_recover = can_recover
        self.log_entry = log_entry
        self.retry_result = retry_result

    def to_tool_error_message(self) -> str:
        """Generate a description suitable for a tool message so the LLM can see it."""
        return (
            f"[Error] {type(self.error).__name__}: {self.error}\n"
            f"This error is {self.severity.value}. "
            f"{'Please try a different approach.' if self.can_recover else 'The task cannot continue.'}"
        )


class ErrorHandler:
    """Central error handler.

    Responsibilities:
      1. Classify the exception via ErrorClassifier
      2. Dispatch to the executor matching the severity
      3. Return an ErrorResult describing the recommended action
    """

    def __init__(
        self,
        send_message: Optional[SendMessageCallback] = None,
    ):
        self._executors: Dict[ErrorSeverity, BaseExecutor] = {
            ErrorSeverity.FATAL: FatalExecutor(send_message),
            ErrorSeverity.USER_FACING: UserFacingExecutor(send_message),
            ErrorSeverity.RETRYABLE: RetryableExecutor(send_message),
            ErrorSeverity.RECOVERABLE: RecoverableExecutor(),
        }

    async def handle(
        self,
        error: Exception,
        *,
        retry: Optional[RetryContext] = None,
    ) -> ErrorResult:
        """Classify *error* and delegate to the matching executor.

        Args:
            error: the caught exception.
            retry: optional RetryContext carrying the callable and its
                   arguments for automatic retry when severity is RETRYABLE.
        """
        agent_error, severity = ErrorClassifier.classify(error)

        if not isinstance(severity, ErrorSeverity):
            raise_error(
                StatusCode.FLOW_EXECUTION_ERROR,
                error_msg=f"Invalid error severity: {severity!r}. "
                f"Must be one of {list(ErrorSeverity)}"
            )

        executor = self._executors[severity]
        return await executor.execute(agent_error, severity, retry=retry)