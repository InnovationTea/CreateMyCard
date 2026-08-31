# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""统一异常处理和重试行为测试。"""

import json
from typing import Any

import httpx
import pytest

from errors.classifier import ErrorClassifier
from errors.codes import StatusCode
from errors.error_handler import ErrorHandler
from errors.errors import (
    AgentError,
    ExecutionError,
    ToolInvalidArgumentsError,
    ToolTimeoutError,
    ValidationError,
)
from errors.retry import RetryConfig, RetryContext, RetryExecutor, RetryExhaustedError
from errors.severity import ErrorSeverity


class UserActionError(AgentError):
    """测试未注册但带用户提示的业务异常。"""

    user_message = "请修改输入后重试"


def build_tool_timeout() -> ToolTimeoutError:
    return ToolTimeoutError(
        StatusCode.TOOL_EXECUTE_TIMEOUT,
        error_msg="timeout",
        timeout=1,
    )


def test_classifier_preserves_registered_error() -> None:
    error = build_tool_timeout()

    wrapped, severity = ErrorClassifier.classify(error)

    assert wrapped is error
    assert severity is ErrorSeverity.RETRYABLE


def test_classifier_uses_user_facing_fallback() -> None:
    error = UserActionError(StatusCode.ERROR)

    wrapped, severity = ErrorClassifier.classify(error)

    assert wrapped is error
    assert severity is ErrorSeverity.USER_FACING


def test_classifier_wraps_json_error_as_recoverable() -> None:
    error = json.JSONDecodeError("invalid", "{", 1)

    wrapped, severity = ErrorClassifier.classify(error)

    assert isinstance(wrapped, ValidationError)
    assert severity is ErrorSeverity.RECOVERABLE
    assert wrapped.cause is error


def test_classifier_marks_rate_limit_as_retryable() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(429, request=request, headers={"retry-after": "2.5"})
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)

    wrapped, severity = ErrorClassifier.classify(error)

    assert isinstance(wrapped, ExecutionError)
    assert severity is ErrorSeverity.RETRYABLE
    assert getattr(wrapped, "retry_after", None) == "2.5"


def test_retry_config_validates_attempt_count() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryConfig(max_attempts=0)


@pytest.mark.asyncio
async def test_retry_executor_returns_after_retry() -> None:
    attempts = 0
    callbacks: list[tuple[int, float]] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise build_tool_timeout()
        return "done"

    async def on_retry(attempt: int, delay: float, error: Any) -> None:
        assert isinstance(error, ToolTimeoutError)
        callbacks.append((attempt, delay))

    config = RetryConfig(max_attempts=2, base_delay=0.0, jitter=False)
    result = await RetryExecutor(config).execute(operation, on_retry=on_retry)

    assert result == "done"
    assert attempts == 2
    assert callbacks == [(1, 0.0)]


@pytest.mark.asyncio
async def test_retry_executor_does_not_retry_recoverable_error() -> None:
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise ToolInvalidArgumentsError(
            StatusCode.TOOL_ARGUMENTS_INVALID,
            error_msg="bad arguments",
        )

    with pytest.raises(ToolInvalidArgumentsError):
        await RetryExecutor(RetryConfig(base_delay=0.0)).execute(operation)

    assert attempts == 1


@pytest.mark.asyncio
async def test_retry_executor_reports_exhaustion() -> None:
    async def operation() -> None:
        raise build_tool_timeout()

    config = RetryConfig(max_attempts=2, base_delay=0.0, jitter=False)
    with pytest.raises(RetryExhaustedError) as caught:
        await RetryExecutor(config).execute(operation)

    assert caught.value.attempts == 2
    assert isinstance(caught.value.last_error, ToolTimeoutError)


@pytest.mark.asyncio
async def test_error_handler_returns_recoverable_result() -> None:
    error = ToolInvalidArgumentsError(
        StatusCode.TOOL_ARGUMENTS_INVALID,
        error_msg="bad arguments",
    )

    result = await ErrorHandler().handle(error)

    assert result.can_recover
    assert not result.should_abort
    assert not result.should_notify_user


@pytest.mark.asyncio
async def test_error_handler_retries_and_notifies() -> None:
    messages: list[dict[str, Any]] = []
    attempts = 0

    async def send_message(message: dict[str, Any]) -> None:
        messages.append(message)

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        return "done"

    retry = RetryContext(func=operation)
    handler = ErrorHandler(send_message)
    result = await handler.handle(build_tool_timeout(), retry=retry)

    assert result.retry_result == "done"
    assert not result.should_abort
    assert attempts == 1
    assert messages == []
