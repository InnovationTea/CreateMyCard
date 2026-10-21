# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""统一校验标准日志的身份字段、事件格式、级别与异常堆栈。"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from app.logger import json_for_log

if TYPE_CHECKING:
    from collections.abc import Mapping

    from services.validation_execution import ValidationExecutionContext

LogLevel = Literal["info", "warning", "error"]


class ValidationLogger(Protocol):
    """校验观测只依赖服务日志器的三个稳定级别。"""

    def info(self, message: str) -> None:
        ...

    def warning(self, message: str) -> None:
        ...

    def error(self, message: str) -> None:
        ...


def format_validation_execution_fields(context: ValidationExecutionContext) -> str:
    """将只读执行身份格式化为稳定键值字段。"""

    fields = (
        f"operation={context.operation} "
        f"generation_mode={context.generation_mode} "
        f"phase={context.phase} "
        f"attempt={context.attempt} "
        f"purpose={context.purpose}"
    )
    if context.candidate_index is not None:
        fields += f" candidate_index={context.candidate_index}"
    return fields


def _format_detail(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json_for_log(value)
    return str(value)


def log_validation_event(
    logger: ValidationLogger,
    *,
    component: str,
    event: str,
    execution_context: ValidationExecutionContext | None = None,
    level: LogLevel = "info",
    details: Mapping[str, Any] | None = None,
    exception: BaseException | None = None,
) -> None:
    """记录一次标准校验事件；不创建 Trace，也不吞掉或转换异常。"""

    if execution_context is None:
        from services.validation_execution import ValidationExecutionContext

        execution_context = ValidationExecutionContext()
    fields = [component, event, format_validation_execution_fields(execution_context)]
    if details:
        fields.extend(f"{key}={_format_detail(value)}" for key, value in details.items())
    if exception is not None:
        fields.extend(
            (
                f"exception_type={type(exception).__name__}",
                f"exception={exception!r}",
                f"traceback={traceback.format_exc()}",
            )
        )
    getattr(logger, level)(" ".join(fields))


@dataclass(frozen=True)
class ValidationObserver:
    """为一次校验调用提供显式、无状态的标准日志边界。"""

    logger: ValidationLogger
    component: str
    event_prefix: str
    execution_context: ValidationExecutionContext

    def started(self, **details: Any) -> None:
        self._log("started", details=details)

    def completed(self, **details: Any) -> None:
        self._log("completed", details=details)

    def failed(
        self,
        *,
        level: LogLevel = "error",
        exception: BaseException | None = None,
        **details: Any,
    ) -> None:
        self._log("failed", level=level, details=details, exception=exception)

    def warnings(self, **details: Any) -> None:
        self._log("warnings", level="warning", details=details)

    def crashed(self, exception: BaseException, **details: Any) -> None:
        self._log("crashed", level="error", details=details, exception=exception)

    def _log(
        self,
        suffix: str,
        *,
        level: LogLevel = "info",
        details: Mapping[str, Any] | None = None,
        exception: BaseException | None = None,
    ) -> None:
        log_validation_event(
            self.logger,
            component=self.component,
            event=f"{self.event_prefix}_{suffix}",
            execution_context=self.execution_context,
            level=level,
            details=details,
            exception=exception,
        )
