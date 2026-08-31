# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""将原始异常统一包装并映射为处理级别。"""

import json

import httpx

from errors.codes import StatusCode
from errors.errors import (
    AgentError,
    BaseError,
    ConfigurationError,
    ExecutionError,
    FlowConfigurationError,
    FlowDataError,
    FlowDependencyError,
    FlowError,
    FlowExecutionError,
    FlowResourceError,
    FlowStateError,
    FlowTimeoutError,
    FrameworkError,
    LLMConfigurationError,
    LLMDataError,
    LLMDependencyError,
    LLMError,
    LLMExecutionError,
    LLMResourceError,
    LLMTimeoutError,
    RunnerTermination,
    Termination,
    ToolConfigurationError,
    ToolDataError,
    ToolDependencyError,
    ToolError,
    ToolExecutionError,
    ToolFileError,
    ToolInvalidArgumentsError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolResourceError,
    ToolTimeoutError,
    ValidationError,
)
from errors.severity import ErrorSeverity


class ErrorClassifier:
    """将任意异常转换为项目异常，并确定后续处理策略。"""

    _SEVERITY_MAP: dict[type[BaseError], ErrorSeverity] = {
        FrameworkError: ErrorSeverity.FATAL,
        ConfigurationError: ErrorSeverity.FATAL,
        ValidationError: ErrorSeverity.RECOVERABLE,
        ExecutionError: ErrorSeverity.RETRYABLE,
        Termination: ErrorSeverity.FATAL,
        RunnerTermination: ErrorSeverity.FATAL,
        LLMError: ErrorSeverity.RETRYABLE,
        LLMTimeoutError: ErrorSeverity.RETRYABLE,
        LLMExecutionError: ErrorSeverity.RETRYABLE,
        LLMResourceError: ErrorSeverity.RETRYABLE,
        LLMDependencyError: ErrorSeverity.RETRYABLE,
        LLMDataError: ErrorSeverity.RETRYABLE,
        LLMConfigurationError: ErrorSeverity.FATAL,
        ToolError: ErrorSeverity.RECOVERABLE,
        ToolNotFoundError: ErrorSeverity.RECOVERABLE,
        ToolExecutionError: ErrorSeverity.RECOVERABLE,
        ToolInvalidArgumentsError: ErrorSeverity.RECOVERABLE,
        ToolDataError: ErrorSeverity.RECOVERABLE,
        ToolFileError: ErrorSeverity.RECOVERABLE,
        ToolTimeoutError: ErrorSeverity.RETRYABLE,
        ToolDependencyError: ErrorSeverity.RETRYABLE,
        ToolResourceError: ErrorSeverity.RETRYABLE,
        ToolPermissionDeniedError: ErrorSeverity.FATAL,
        ToolConfigurationError: ErrorSeverity.FATAL,
        FlowError: ErrorSeverity.RETRYABLE,
        FlowDependencyError: ErrorSeverity.RETRYABLE,
        FlowTimeoutError: ErrorSeverity.RETRYABLE,
        FlowResourceError: ErrorSeverity.RETRYABLE,
        FlowDataError: ErrorSeverity.RECOVERABLE,
        FlowExecutionError: ErrorSeverity.FATAL,
        FlowConfigurationError: ErrorSeverity.FATAL,
        FlowStateError: ErrorSeverity.FATAL,
    }

    @classmethod
    def classify(cls, error: Exception) -> tuple[BaseError, ErrorSeverity]:
        """返回标准化后的异常及其处理级别。"""
        wrapped = error if isinstance(error, BaseError) else cls._wrap_external_exception(error)
        return wrapped, cls._resolve_severity(wrapped)

    @classmethod
    def _resolve_severity(cls, error: BaseError) -> ErrorSeverity:
        """按最具体的异常类型查找级别，再使用异常自身的语义兜底。"""
        for error_type in type(error).__mro__:
            if error_type in (AgentError, ExecutionError, BaseError):
                break
            severity = cls._SEVERITY_MAP.get(error_type)
            if severity is not None:
                return severity

        if isinstance(error, AgentError):
            if error.retryable:
                return ErrorSeverity.RETRYABLE
            if getattr(error, "user_message", None):
                return ErrorSeverity.USER_FACING
        severity = cls._SEVERITY_MAP.get(type(error))
        if severity is not None:
            return severity
        if error.fatal:
            return ErrorSeverity.FATAL
        if error.recoverable:
            return ErrorSeverity.RECOVERABLE
        return ErrorSeverity.FATAL

    @staticmethod
    def _wrap_external_exception(error: Exception) -> BaseError:
        """将标准库或第三方异常转换为项目异常。"""
        if isinstance(error, json.JSONDecodeError):
            return ValidationError(
                StatusCode.FLOW_PARSE_JSON_PROCESS_ERROR,
                msg=f"JSON parse error: {error}",
                cause=error,
            )

        if isinstance(error, (TimeoutError, httpx.TimeoutException)):
            return ExecutionError(
                StatusCode.ERROR,
                msg=f"Request timeout: {error}",
                cause=error,
            )

        if isinstance(error, httpx.HTTPStatusError):
            return ErrorClassifier._wrap_http_status_error(error)

        if isinstance(error, (ConnectionError, OSError)):
            return FrameworkError(
                StatusCode.ERROR,
                msg=f"Connection error: {error}",
                cause=error,
            )

        return AgentError(
            StatusCode.ERROR,
            msg=f"Unexpected error: {type(error).__name__}: {error}",
            cause=error,
        )

    @staticmethod
    def _wrap_http_status_error(error: httpx.HTTPStatusError) -> BaseError:
        """根据 HTTP 状态码确定错误是否适合重试。"""
        status = error.response.status_code
        if status == 429 or 500 <= status < 600:
            wrapped = ExecutionError(
                StatusCode.ERROR,
                msg=f"Remote service unavailable ({status})",
                cause=error,
            )
            retry_after = error.response.headers.get("retry-after")
            if retry_after is not None:
                wrapped.retry_after = retry_after
            return wrapped

        if status in (401, 403):
            return FrameworkError(
                StatusCode.ERROR,
                msg=f"Authentication or authorization failed ({status})",
                cause=error,
            )

        return AgentError(
            StatusCode.ERROR,
            msg=f"HTTP request failed ({status})",
            cause=error,
        )
