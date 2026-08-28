# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

from __future__ import annotations

import json
from typing import (
    Optional,
    Any,
    Dict,
    Mapping, NoReturn,
)

from errors.codes import StatusCode
from errors.status_mapping import build_status_exception_map


class BaseError(Exception):
    """
    Framework unified exception base class.

    Key design points:
    - StatusCode is the primary semantic identifier
    - Exception type represents control / recovery semantics
    - Message rendering is template-based and lazy-safe
    """

    status: StatusCode = StatusCode.ERROR
    recoverable: bool = False
    fatal: bool = False

    def __init__(
            self,
            status: StatusCode,
            *,
            msg: Optional[str] = None,
            details: Optional[Any] = None,
            cause: Optional[BaseException] = None,
            **kwargs: dict[str, Any],
    ):
        if msg is None and "error_msg" in kwargs:
            msg = str(kwargs["error_msg"])
        self.status = status
        self.code = self.status.code
        self.params = kwargs
        self.details = details
        self.cause = cause
        self.__cause__ = cause

        self._template_message = self._render_message()
        self.message = msg if msg else self._template_message
        super().__init__(self._template_message)

    def _render_message(self) -> str:
        """
        Render error message from StatusCode template.

        Never raise formatting exception outward.
        """
        try:
            return _format_template(self.status.errmsg, params=self.params)
        except Exception:
            return self.status.errmsg

    def to_dict(self) -> Dict[str, Any]:
        """
        Standard structured output for API / RPC / logging.
        """
        return {
            "code": self.code,
            "status": self.status.name,
            "message": self._template_message,
            "params": self.params,
            "raw_message": self.message,
            "details": self.details,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message if self.message else self._template_message}"

    @classmethod
    def _reconstruct(cls, status, msg, details, cause, params):
        params = params or {}
        return cls(status, msg=msg, details=details, cause=cause, **params)

    def __reduce__(self):
        return (
            self.__class__._reconstruct,
            (self.status, self.message, self.details, self.cause, self.params),
            None,
        )


class _SafeDict(dict):
    """
    dict subclass used for safe string formatting.
    If a key is missing, it inserts a placeholder '<missing:key>' instead of raising KeyError.
    """

    def __missing__(self,
                    key: str) -> str:
        return f"<missing:{key}>"


def _format_template(template: str,
                     params: Optional[Mapping[str, Any]] = None) -> str:
    """
    Safely format a template using provided params. Missing keys will be shown as '<missing:KEY>'.
    If template is None or empty, returns an empty string.
    """
    if not template:
        return ""
    safe = _SafeDict()
    if params:
        # copy to safe dict so unknown keys fallback works
        safe.update({k: (v if isinstance(v, str) else str(v)) for k, v in params.items()})
    try:
        return template.format_map(safe)
    except Exception:
        # As a last resort, return the raw template plus params summary
        try:
            return f"{template} (format error, params={dict(params) if params else {} })"
        except Exception:
            return template


# =======================
# Basic exception definitions
# =======================

class FrameworkError(BaseError):
    """
    Infrastructure / environment / dependency failures.
    Must abort current execution.
    """
    recoverable = False
    fatal = True


class ConfigurationError(FrameworkError):
    pass


class ValidationError(BaseError):
    """
    Constraint / validation / unsupported capability errors.
    Should NOT retry or replan.
    """
    recoverable = False
    fatal = False


class Termination(BaseError):
    """
    Non-error control-flow termination.
    Used for normal stop, cancellation, completion, etc.
    """
    recoverable = False
    fatal = False


# =========================
# Module domain exception definitions
# =========================

class RunnerTermination(Termination):
    def __init__(self, reason, status, **kwargs):
        super().__init__(status, **kwargs)
        self.reason = reason


class ExecutionError(BaseError):
    """
    Execution-time errors during llm / tool / flow execution.
    Usually recoverable via retry / replan.
    """
    recoverable = True
    fatal = False


class AgentError(ExecutionError):

    status: StatusCode = StatusCode.ERROR
    retryable: bool = False

    def __init__(
            self,
            status: Optional[StatusCode] = None,
            retryable: Optional[bool] = None,
            *,
            msg: Optional[str] = None,
            details: Optional[Any] = None,
            context: Optional[dict[str, Any]] = None,
            cause: Optional[Exception] = None,
            **kwargs: dict[str, Any],
    ):
        super().__init__(
            status or self.status,
            msg=msg,
            details=details,
            cause=cause,
            **kwargs,
        )
        self.context = context or {}
        if retryable is not None:
            self.retryable = retryable

    def with_context(self, **kwargs) -> "AgentError":
        """链式追加上下文信息。"""
        self.context.update(kwargs)
        return self


class LLMError(AgentError):
    """LLM相关错误基类。"""
    pass


class LLMTimeoutError(LLMError):
    retryable = True
    user_message = "大模型响应超时，正在重试，请稍后"


class LLMExecutionError(LLMError):
    retryable = True
    user_message = "大模型处理任务出现异常，正在重试，请稍后"


class LLMResourceError(LLMError):
    retryable = True
    user_message = "当前请求规模超出大模型处理限制，正在调整后重试"


class LLMDependencyError(LLMError):
    retryable = True
    user_message = "大模型服务配置异常，当前暂时无法处理该请求"


class LLMDataError(LLMError):
    retryable = True


class LLMConfigurationError(LLMError):
    retryable = False


class ToolError(AgentError):
    """Tool相关错误基类。"""
    pass


class ToolNotFoundError(ToolError):
    retryable = False


class ToolInvalidArgumentsError(ToolError):
    retryable = False


class ToolPermissionDeniedError(ToolError):
    retryable = False
    user_message = "操作权限不足，无法执行该工具"


class ToolTimeoutError(ToolError):
    retryable = True
    user_message = "工具执行超时，正在重试，请稍后"


class ToolExecutionError(ToolError):
    retryable = False


class ToolDependencyError(ToolError):
    retryable = True
    user_message = "工具依赖服务暂时异常，正在重试，请稍后"


class ToolDataError(ToolError):
    retryable = False


class ToolConfigurationError(ToolError):
    retryable = False
    user_message = "工具配置异常，当前暂时无法执行该操作"


class ToolResourceError(ToolError):
    retryable = True
    user_message = "当前请求超出工具处理限制，正在调整后重试"


class ToolFileError(ToolError):
    retryable = False


class FlowError(AgentError):
    pass


class FlowExecutionError(FlowError):
    retryable = False


class FlowDependencyError(FlowError):
    retryable = True
    user_message = "任务依赖的服务暂时异常，正在重试，请稍后"


class FlowTimeoutError(FlowError):
    retryable = True
    user_message = "任务处理超时，正在重试，请稍后"


class FlowConfigurationError(FlowError):
    retryable = False
    user_message = "服务配置异常，当前暂时无法处理该请求"


class FlowStateError(FlowError):
    retryable = False
    user_message = "任务状态异常，当前暂时无法继续处理"


class FlowResourceError(FlowError):
    retryable = True
    user_message = "当前请求超出处理限制，正在调整后重试"


class FlowDataError(FlowError):
    retryable = False


STATUS_TO_EXCEPTION = build_status_exception_map()


def build_error(
        status: StatusCode,
        *,
        msg: Optional[str] = None,
        details: Optional[Any] = None,
        cause: Optional[BaseException] = None,
        **kwargs,
) -> BaseError:
    """
    Build exception instance without raising.
    Useful for deferred throw or wrapping.
    """
    exc_cls = STATUS_TO_EXCEPTION.get(status, FrameworkError)
    return exc_cls(status, msg=msg, details=details, cause=cause, **kwargs)


def raise_error(
        status: StatusCode,
        *,
        msg: Optional[str] = None,
        details: Optional[Any] = None,
        cause: Optional[BaseException] = None,
        **kwargs,
) -> NoReturn:
    """
    Unified error raising entry.
    """
    raise build_error(status, msg=msg, details=details, cause=cause, **kwargs)


def system_error(
        status: StatusCode,
        *,
        cause: Optional[Exception] = None,
        **kwargs,
) -> None:
    raise FrameworkError(status, cause=cause, **kwargs)


def validate_error(
        status: StatusCode,
        *,
        cause: Optional[Exception] = None,
        **kwargs,
) -> None:
    raise ValidationError(status, cause=cause, **kwargs)


def terminate(
        status: StatusCode,
        **kwargs,
) -> None:
    raise Termination(status, **kwargs)
