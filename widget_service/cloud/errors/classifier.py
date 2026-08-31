# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

"""Maps raw exceptions to ErrorSeverity and wraps them in AgentError if needed."""
import asyncio
import json

import httpx

from errors.errors import LLMTimeoutError, LLMExecutionError, LLMResourceError, LLMDependencyError, \
    LLMDataError, LLMConfigurationError, ToolNotFoundError, ToolInvalidArgumentsError, ToolPermissionDeniedError, \
    ToolTimeoutError, ToolExecutionError, ToolDependencyError, ToolDataError, ToolConfigurationError, \
    ToolResourceError, ToolFileError, FlowExecutionError, FlowConfigurationError, FlowDataError, FlowResourceError, \
    FlowDependencyError, FlowTimeoutError, FlowStateError, AgentError, ExecutionError, BaseError, FrameworkError, \
    ValidationError, LLMError, ToolError, FlowError, ConfigurationError, Termination, RunnerTermination
from errors.severity import ErrorSeverity


class ErrorClassifier:
    """将任意异常映射为 (AgentError, ErrorSeverity)。

    分类逻辑集中在这一个地方，方便统一维护。
    """

    # ── 异常类 → 严重级别 的静态映射 ──
    _SEVERITY_MAP: dict[type, ErrorSeverity] = {
        FrameworkError: ErrorSeverity.FATAL,
        ConfigurationError: ErrorSeverity.FATAL,
        ValidationError: ErrorSeverity.RECOVERABLE,
        ExecutionError: ErrorSeverity.RETRYABLE,
        Termination: ErrorSeverity.FATAL,
        RunnerTermination: ErrorSeverity.FATAL,

        # =====================================================================
        # LLM
        # =====================================================================

        LLMError: ErrorSeverity.RETRYABLE,
        # LLM — 可重试
        LLMTimeoutError: ErrorSeverity.RETRYABLE,
        LLMExecutionError: ErrorSeverity.RETRYABLE,
        LLMResourceError: ErrorSeverity.RETRYABLE,
        LLMDependencyError: ErrorSeverity.RETRYABLE,
        LLMDataError: ErrorSeverity.RETRYABLE,

        # LLM — 面向用户

        # LLM — 致命
        LLMConfigurationError: ErrorSeverity.FATAL,

        # =====================================================================
        # Tool
        # =====================================================================

        ToolError: ErrorSeverity.RECOVERABLE,
        # Tool — 可恢复（交给 LLM 处理）
        ToolNotFoundError: ErrorSeverity.RECOVERABLE,
        ToolExecutionError: ErrorSeverity.RECOVERABLE,
        ToolInvalidArgumentsError: ErrorSeverity.RECOVERABLE,
        ToolDataError: ErrorSeverity.RECOVERABLE,
        ToolFileError: ErrorSeverity.RECOVERABLE,

        # Tool — 可重试
        ToolTimeoutError: ErrorSeverity.RETRYABLE,
        ToolDependencyError: ErrorSeverity.RETRYABLE,
        ToolResourceError: ErrorSeverity.RETRYABLE,

        # Tool — 面向用户

        # Tool — 致命
        ToolPermissionDeniedError: ErrorSeverity.FATAL,
        ToolConfigurationError: ErrorSeverity.FATAL,

        # =====================================================================
        # Flow
        # =====================================================================

        FlowError: ErrorSeverity.RETRYABLE,
        # Flow — 可重试
        FlowDependencyError: ErrorSeverity.RETRYABLE,
        FlowTimeoutError: ErrorSeverity.RETRYABLE,
        FlowResourceError: ErrorSeverity.RETRYABLE,

        # Flow — 可恢复
        FlowDataError: ErrorSeverity.RECOVERABLE,

        # Flow — 面向用户

        # Flow — 致命
        FlowExecutionError: ErrorSeverity.FATAL,
        FlowConfigurationError: ErrorSeverity.FATAL,
        FlowStateError: ErrorSeverity.FATAL,
    }

    @classmethod
    def classify(cls, error: Exception) -> tuple[BaseError, ErrorSeverity]:
        """将任意异常分类。

        Returns:
            (wrapped_error, severity)
        """

        # 1. 已经是 AgentError → 直接查表
        if isinstance(error, AgentError):
            severity = cls._SEVERITY_MAP.get(type(error))
            if severity:
                return error, severity
            # 未注册的 AgentError 子类，按 retryable 字段判断
            if error.retryable:
                return error, ErrorSeverity.RETRYABLE
            if error.user_message:
                return error, ErrorSeverity.USER_FACING
            return error, ErrorSeverity.FATAL

        # 2. 标准库 / 第三方异常 → 包装成 AgentError
        wrapped = cls._wrap_external_exception(error)
        severity = cls._SEVERITY_MAP.get(type(wrapped), ErrorSeverity.FATAL)
        return wrapped, severity

    @classmethod
    def _wrap_external_exception(cls, error: Exception) -> BaseError:
        """将第三方/标准库异常转换为对应的 AgentError。"""

        # ── 网络超时 ──
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return ExecutionError(cause=error)

        if isinstance(error, httpx.TimeoutException):
            return ExecutionError(
                message=f"HTTP timeout: {error}", cause=error,
            )

        # ── HTTP 状态码 ──
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if status == 429:
                retry_after = error.response.headers.get("retry-after")
                return FrameworkError(
                    message=f"Resource limit exceeded (429)",
                    retry_after=float(retry_after) if retry_after else None,
                    cause=error,
                )
            if status in (401, 403):
                return FrameworkError(
                    message=f"Authentication/Authorization failed ({status})",
                    cause=error,
                )
            if status in (500, 502, 503):
                return FrameworkError(
                    message=f"Service unavailable ({status})",
                    cause=error,
                )

        # ── 连接错误 ──
        if isinstance(error, (ConnectionError, OSError)):
            return FrameworkError(
                message=f"Connection error: {error}", cause=error,
            )
            # ── JSON 解析失败 ──
        if isinstance(error, json.JSONDecodeError):
            return ValidationError(
                message=f"JSON Parse error: {error}", cause=error,
            )

        # ── 兜底 ──
        return AgentError(
            message=f"Unexpected error: {type(error).__name__}: {error}",
            cause=error,
        )