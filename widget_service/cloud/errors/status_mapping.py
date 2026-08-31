# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

from __future__ import annotations

from typing import (
    Dict,
    Type,
)

from errors.codes import StatusCode

ALLOWED_SCOPES = {
    "LLM",
    "TOOL",
    "FLOW"
}


def _get_exception_class_registry() -> Dict[str, Type]:
    # Note: BaseError is imported lazily inside the function to avoid circular imports.
    """
    Lazily import and return the registry mapping exception class names to actual classes.

    This avoids a circular import between `status_mapping` and `errors` at module import time.
    """
    from errors import errors as _errors

    return {
        "BaseError": _errors.BaseError,
        "FrameworkError": _errors.FrameworkError,
        "ExecutionError": _errors.ExecutionError,
        "ValidationError": _errors.ValidationError,
        "Termination": _errors.Termination,
        "AgentError": _errors.AgentError,

        "LLMError": _errors.LLMError,
        "LLMTimeoutError": _errors.LLMTimeoutError,
        "LLMExecutionError": _errors.LLMExecutionError,
        "LLMResourceError": _errors.LLMResourceError,
        "LLMDependencyError": _errors.LLMDependencyError,
        "LLMDataError": _errors.LLMDataError,
        "LLMConfigurationError": _errors.LLMConfigurationError,

        "ToolError": _errors.ToolError,
        "ToolNotFoundError": _errors.ToolNotFoundError,
        "ToolInvalidArgumentsError": _errors.ToolInvalidArgumentsError,
        "ToolPermissionDeniedError": _errors.ToolPermissionDeniedError,
        "ToolTimeoutError": _errors.ToolTimeoutError,
        "ToolExecutionError": _errors.ToolExecutionError,
        "ToolDependencyError": _errors.ToolDependencyError,
        "ToolDataError": _errors.ToolDataError,
        "ToolConfigurationError": _errors.ToolConfigurationError,
        "ToolResourceError": _errors.ToolResourceError,
        "ToolFileError": _errors.ToolFileError,

        "FlowError": _errors.FlowError,
        "FlowExecutionError": _errors.FlowExecutionError,
        "FlowDependencyError": _errors.FlowDependencyError,
        "FlowDataError": _errors.FlowDataError,
        "FlowTimeoutError": _errors.FlowTimeoutError,
        "FlowConfigurationError": _errors.FlowConfigurationError,
        "FlowStateError": _errors.FlowStateError,
        "FlowResourceError": _errors.FlowResourceError,
    }

KEYWORD_RULES = [
    (("INVALID", "VALIDATE", "NOT_SUPPORTED", "PARAM", "MISSING", "DUPLICATED"), "ValidationError"),
    (("CONFIG", "SCHEMA", "FORMAT", "TEMPLATE"), "ValidationError"),

    (("INIT", "CONNECT", "SERVICE", "QUEUE", "PROVIDER"), "FrameworkError"),
    (("CALL", "INVOKE_LLM", "MODEL", "REMOTE"), "FrameworkError"),

    (("TIMEOUT", "EXECUTE", "EXECUTION", "RUNTIME", "PROCESS", "STREAM", "RESPONSE"), "ExecutionError"),
]

RANGE_RULES = [
    # =============================================================================================================
    # 101. LLM 相关 101000–101999
    # =============================================================================================================
    ((101000, 101049), "LLMTimeoutError"),
    ((101050, 101099), "LLMExecutionError"),
    ((101100, 101149), "LLMDependencyError"),
    ((101150, 101199), "LLMDataError"),
    ((101200, 101249), "LLMConfigurationError"),
    ((101250, 101299), "LLMResourceError"),

    # =============================================================================================================
    # 102. Tool 相关 102000–102999
    # =============================================================================================================
    ((102000, 102049), "ToolNotFoundError"),
    ((102050, 102099), "ToolInvalidArgumentsError"),
    ((102100, 102149), "ToolPermissionDeniedError"),
    ((102150, 102199), "ToolTimeoutError"),
    ((102200, 102249), "ToolExecutionError"),
    ((102250, 102299), "ToolDependencyError"),
    ((102300, 102349), "ToolDataError"),
    ((102350, 102399), "ToolConfigurationError"),
    ((102450, 102499), "ToolFileError"),
    ((102500, 102549), "ToolResourceError"),

    # =============================================================================================================
    # 103. Flow 相关 103000–103999
    # =============================================================================================================
    ((103000, 103049), "FlowExecutionError"),
    ((103050, 103099), "FlowDependencyError"),
    ((103100, 103149), "FlowDataError"),
    ((103150, 103199), "FlowTimeoutError"),
    ((103200, 103249), "FlowConfigurationError"),
    ((103250, 103299), "FlowStateError"),
    ((103300, 103349), "FlowResourceError"),
]

# Manual overrides expressed as names to avoid failing import when some legacy names are absent.
_MANUAL_OVERRIDES_RAW = {}

# Build the actual mapping only for StatusCode members that exist in the current enum.
MANUAL_OVERRIDES: Dict[StatusCode, str] = {}
for _name, _exc in _MANUAL_OVERRIDES_RAW.items():
    if hasattr(StatusCode, _name):
        MANUAL_OVERRIDES[getattr(StatusCode, _name)] = _exc


def _match_keyword(name: str) -> str | None:
    for keywords, exc_name in KEYWORD_RULES:
        if any(k in name for k in keywords):
            return exc_name
    return None


def _match_range(code: int) -> str | None:
    for (start, end), exc_name in RANGE_RULES:
        if start <= code <= end:
            return exc_name
    return None


def resolve_exception_class(status: StatusCode) -> Type:
    # Defer obtaining the actual exception classes to avoid circular import
    registry = _get_exception_class_registry()

    # 1. Manual override
    if status in MANUAL_OVERRIDES:
        return registry[MANUAL_OVERRIDES[status]]

    # 2. Scoped status codes use range rule
    name = status.name
    code = status.code
    scope = name.split("_", 1)[0]

    if scope in ALLOWED_SCOPES:
        exc_name = _match_range(code)
        if exc_name:
            return registry[exc_name]

    # 3. Non-scoped status codes use keyword rule
    exc_name = _match_keyword(name)
    if exc_name:
        return registry[exc_name]

    # 4. Absolute fallback
    return registry["ExecutionError"]


def build_status_exception_map() -> Dict[StatusCode, Type]:
    """
    Generate full StatusCode -> ExceptionClass mapping.
    """
    mapping: Dict[StatusCode, Type] = {}
    for status in StatusCode:
        mapping[status] = resolve_exception_class(status)
    return mapping