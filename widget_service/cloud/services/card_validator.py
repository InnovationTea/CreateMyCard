# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""A2UI 卡片校验 API 的兼容适配层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.card_validation import validate_card as validate_card_api
from services.card_validation.diagnostics import Diagnostic


@dataclass(frozen=True)
class CardValidationReport:
    """兼容原有调用方的字符串校验结果。"""

    errors: list[str]
    warnings: list[str]

    def passed(self, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)


def validate_card(
    genui_text: str,
    cardspec: dict[str, Any] | str,
    strict: bool = False,
    allowed_asset_sources: set[str] | None = None,
) -> CardValidationReport:
    """通过服务内 API 校验 genui 和 CardSpec，不执行校验脚本或子进程。"""
    effective_capabilities = None
    if allowed_asset_sources is not None:
        effective_capabilities = {
            "data": [],
            "event": [],
            "asset": [{"src": source} for source in sorted(allowed_asset_sources)],
        }
    reporter = validate_card_api(
        dsl_text=genui_text,
        cardspec=cardspec,
        effective_capabilities=effective_capabilities,
    )
    errors = [_format_diagnostic(item) for item in reporter.diagnostics if item.severity == "error"]
    warnings = [
        _format_diagnostic(item) for item in reporter.diagnostics if item.severity == "warning"
    ]
    if strict:
        errors.extend(warnings)
    return CardValidationReport(errors=errors, warnings=warnings)


def _format_diagnostic(diagnostic: Diagnostic) -> str:
    location = diagnostic.file_kind
    if diagnostic.line is not None:
        location += f":{diagnostic.line}"
    if diagnostic.json_pointer:
        location += f" {diagnostic.json_pointer}"
    return f"{diagnostic.code}: {diagnostic.message} [{location}]"
