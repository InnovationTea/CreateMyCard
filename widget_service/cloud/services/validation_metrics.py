# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""把正式校验产生的 warning 转换为统一运维上报。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from config.config import get_settings
from services.card_validation.diagnostics import Diagnostic
from services.validation_execution import ValidationExecutionContext
from utils.ops_metrics import VALIDATION_ERROR_MESSAGE, report_ops_metrics

ValidationWarningSource = Literal["compact_dsl", "a2ui_artifact"]


@dataclass(frozen=True)
class ValidationWarning:
    """一条可上报的校验 warning，不包含完整业务输入。"""

    source: ValidationWarningSource
    code: str
    message: str
    location: str = ""

    @classmethod
    def from_artifact_diagnostic(cls, diagnostic: Diagnostic) -> ValidationWarning:
        """保留原生 A2UI 诊断的稳定错误码、正文和位置。"""

        location = diagnostic.file_kind
        if diagnostic.line is not None:
            location += f":{diagnostic.line}"
        if diagnostic.json_pointer:
            location += f" {diagnostic.json_pointer}"
        return cls(
            source="a2ui_artifact",
            code=diagnostic.code,
            message=diagnostic.message,
            location=location,
        )


def report_validation_warnings(
    warnings: Iterable[ValidationWarning],
    context: ValidationExecutionContext,
) -> None:
    """按正式校验执行身份去重并逐条上报 warning。"""

    settings = get_settings()
    if not getattr(settings, "enable_validation_warning_metrics", False):
        return
    if not context.report_metrics or context.is_probe:
        return

    reported: set[tuple[str, str, str, str]] = set()
    for warning in warnings:
        identity = (
            warning.source,
            warning.code,
            warning.message,
            warning.location,
        )
        if identity in reported:
            continue
        reported.add(identity)
        report_ops_metrics(
            body={
                VALIDATION_ERROR_MESSAGE: _format_warning_message(warning, context),
            }
        )


def _format_warning_message(
    warning: ValidationWarning,
    context: ValidationExecutionContext,
) -> str:
    fields = (
        f"[operation={context.operation}] "
        f"[generation_mode={context.generation_mode}] "
        f"[phase={context.phase}] "
        f"[attempt={context.attempt}] "
        f"[source={warning.source}] "
        f"[purpose={context.purpose}] "
        f"{warning.code}: {warning.message}"
    )
    if warning.location:
        fields += f" [{warning.location}]"
    return f"[warning] {fields}"
