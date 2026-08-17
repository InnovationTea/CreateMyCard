# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Convert, validate, and repair one Design Compact DSL document."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from app.logger import logger
from config.config import get_settings
from custom.a2ui_model_client import A2UIModelClient
from models.generation import DEFAULT_WIDGET_SIZE, WidgetSize
from services.card_validation import validate_card
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)
from services.generation_pipeline import QualityIssue
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.retry_controller import RetryController

_OUTPUT_SEPARATOR = "==========================="
_MODEL_FORMAT = "compact-dsl"


@dataclass(frozen=True)
class CompactDslRepairResult:
    """保留最终极简协议、标准 DSL 和 repair 执行结果。"""

    compact_dsl: str
    dsl: str
    repair_count: int
    initial_errors: tuple[str, ...]


class CompactDslRepairError(RuntimeError):
    """极简协议经过有限次数 repair 后仍未通过转换或校验。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(errors))


def _validation_message(diagnostic) -> str:
    location = diagnostic.file_kind
    if diagnostic.line is not None:
        location += f":{diagnostic.line}"
    if diagnostic.json_pointer:
        location += f" {diagnostic.json_pointer}"
    return f"{diagnostic.code}: {diagnostic.message} [{location}]"


def _build_initial_prompt(system_prompt: str, size: WidgetSize) -> list[dict[str, str]]:
    user_content = json.dumps(
        {
            "mode": "standalone-repair",
            "size": size,
            "instruction": "修复稍后提供的 Design Compact DSL，只输出完整的极简协议。",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


async def repair_compact_dsl(
    compact_dsl: str,
    *,
    size: WidgetSize = DEFAULT_WIDGET_SIZE,
    max_repair_attempts: int | None = None,
) -> CompactDslRepairResult:
    """复用第四接口的转换、校验、RetryController 和模型 repair 链路。"""
    if not compact_dsl.strip():
        raise ValueError("compact_dsl must not be empty")

    settings = get_settings()
    repair_attempt_limit = (
        settings.validation_failure_max_repair_attempts
        if max_repair_attempts is None
        else max_repair_attempts
    )
    design_profile_id = settings.design_compact_profile_id
    design_protocol = A2UIProtocolRegistry.read_design_protocol_profile(
        design_profile_id
    )
    system_prompt = A2UIProtocolRegistry.read_design_prompt(design_profile_id)
    initial_prompt = _build_initial_prompt(system_prompt, size)
    model_profile = {
        "id": design_profile_id,
        "format": _MODEL_FORMAT,
    }
    latest_dsl = ""
    latest_issues: tuple[QualityIssue, ...] = ()
    model_client: A2UIModelClient | None = None

    def evaluate(source_dsl: str) -> list[str]:
        nonlocal latest_dsl, latest_issues
        try:
            latest_dsl = convert_compact_dsl_to_a2ui(
                source_dsl,
                size=size,
                protocol_profile=design_protocol,
            )
        except CompactDslConversionError as exc:
            issue = QualityIssue(
                stage="conversion",
                code="DESIGN_CONVERSION_FAILED",
                message=str(exc),
            )
            latest_dsl = ""
            latest_issues = (issue,)
            return [issue.repair_message()]

        try:
            reporter = validate_card(dsl_text=latest_dsl)
        except Exception as exc:
            logger.error(
                "[Repair Compact DSL] validator execution failed "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )
            issue = QualityIssue(
                stage="validation",
                code="VALIDATOR_EXECUTION_FAILED",
                message=f"validator execution failed: {exc}",
            )
            latest_issues = (issue,)
            return [issue.repair_message()]
        validation_errors = [
            _validation_message(item)
            for item in reporter.diagnostics
            if item.severity == "error" and item.file_kind != "cardspec"
        ]
        latest_issues = tuple(
            QualityIssue(
                stage="validation",
                code="ARTIFACT_VALIDATION_FAILED",
                message=message,
            )
            for message in validation_errors
        )
        return [item.repair_message() for item in latest_issues]

    async def repair(source_dsl: str, errors: list[str]) -> str:
        nonlocal model_client
        if len(latest_issues) != len(errors):
            raise RuntimeError("repair quality issue state is inconsistent")
        if model_client is None:
            model_client = A2UIModelClient(
                backend=settings.design_compact_model_backend,
                operation_name="generateWidgetCardCompactDsl",
            )
        quality_errors = [item.to_prompt_payload() for item in latest_issues]
        repair_prompt = PromptBuilder().build_repair(
            initial_prompt,
            source_dsl,
            quality_errors,
            dsl_format=design_profile_id,
        )
        return await model_client.generate_repair(repair_prompt, model_profile)

    try:
        retry_result = await RetryController().run(
            operation=lambda: compact_dsl,
            evaluate=evaluate,
            retry_on_quality_failure=True,
            max_repair_attempts=repair_attempt_limit,
            repair=repair,
        )
        if retry_result.errors:
            raise CompactDslRepairError(retry_result.errors)
        return CompactDslRepairResult(
            compact_dsl=retry_result.result,
            dsl=latest_dsl,
            repair_count=retry_result.retryCount,
            initial_errors=tuple(retry_result.initialErrors),
        )
    finally:
        if model_client is not None:
            await model_client.aclose()


def main() -> None:
    """粘贴极简协议，转换并校验，失败时自动调用模型 repair。"""
    logger.remove()
    compact_dsl = r"""
["root","Column",{"width":160,"height":160,"padding":8,"borderRadius":18,"clip":true},["title"]]
["title","Text",{"content":"在这里粘贴极简协议","fontSize":20,"fontColor":"#E5000000"}]
["/ui/state","ready"]
"""
    result = asyncio.run(repair_compact_dsl(compact_dsl))
    print(result.compact_dsl.strip())
    print(_OUTPUT_SEPARATOR)
    print(result.dsl.rstrip())


if __name__ == "__main__":
    main()
