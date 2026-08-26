# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Convert, validate, and repair one Design Compact DSL document."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.logger import logger
from config.config import get_settings
from custom.a2ui_model_client import A2UIModelClient
from models.artifact import WidgetArtifact
from models.generation import TaskSpec
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessingResult,
    DslProcessorKind,
    QualityIssue,
    get_dsl_processor,
)
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.retry_controller import RetryController
from services.source_artifact_repository import SourceArtifactRepository
from services.validator import ArtifactValidator

_OUTPUT_SEPARATOR = "==========================="
_MODEL_FORMAT = "compact-dsl"


@dataclass(frozen=True)
class CompactDslRepairResult:
    """保留最终极简协议、标准 DSL 和 repair 执行结果。"""

    compact_dsl: str
    dsl: str
    repair_count: int
    initial_errors: tuple[str, ...]


@dataclass(frozen=True)
class CompactDslArtifactSource:
    """从结果件提取 repair 所需的极简协议和完整生成上下文。"""

    artifact: WidgetArtifact
    task_spec: TaskSpec
    compact_dsl: str


class CompactDslRepairError(RuntimeError):
    """极简协议经过有限次数 repair 后仍未通过转换或校验。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(errors))


def load_compact_dsl_artifact(artifact_path: str | Path) -> CompactDslArtifactSource:
    """读取 artifact v2 结果件，并取得 Design Compact DSL 与 TaskSpec。"""
    path = Path(artifact_path)
    parsed = SourceArtifactRepository().parse_document(
        path.read_text(encoding="utf-8")
    )
    compact_dsl = parsed.design_token
    if compact_dsl is None or not compact_dsl.strip():
        raise ValueError("artifact must contain a non-empty designcompactdsl block")
    task_spec = TaskSpec.model_validate(parsed.artifact.taskSpec)
    return CompactDslArtifactSource(
        artifact=parsed.artifact,
        task_spec=task_spec,
        compact_dsl=compact_dsl,
    )


async def repair_compact_dsl(
    artifact_path: str | Path,
    *,
    max_repair_attempts: int | None = None,
) -> CompactDslRepairResult:
    """从完整结果件复用第四接口上下文，修复其中的 Design Compact DSL。"""
    source = load_compact_dsl_artifact(artifact_path)
    return await _repair_compact_dsl_source(
        source,
        max_repair_attempts=max_repair_attempts,
    )


async def _repair_compact_dsl_source(
    source: CompactDslArtifactSource,
    *,
    max_repair_attempts: int | None = None,
) -> CompactDslRepairResult:
    """执行与第四接口一致的 prompt、转换、校验和 repair 链路。"""
    compact_dsl = source.compact_dsl
    size = source.task_spec.size

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
    validation_protocol = A2UIProtocolRegistry(
        source.artifact.meta.protocolProfileId
    ).get_profile()
    system_prompt = A2UIProtocolRegistry.read_design_prompt(design_profile_id)
    initial_prompt = PromptBuilder().build_design_compact(
        source.task_spec,
        system_prompt,
    )
    model_profile = {
        "id": design_profile_id,
        "format": _MODEL_FORMAT,
    }
    task_spec_value = source.task_spec.model_dump(mode="json", exclude_none=True)
    processing_context = DslProcessingContext(
        size=size,
        card_spec=source.artifact.cardSpec,
        task_spec=task_spec_value,
        protocol_profile=design_protocol,
        design_profile_id=design_profile_id,
    )
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    latest_dsl = ""
    latest_issues: tuple[QualityIssue, ...] = ()
    latest_processing_result = DslProcessingResult(source_dsl="")
    model_client: A2UIModelClient | None = None

    def evaluate(source_dsl: str) -> list[str]:
        nonlocal latest_dsl, latest_issues, latest_processing_result
        processing_result = processor.process(source_dsl, processing_context)
        latest_processing_result = processing_result
        latest_dsl = processing_result.standard_dsl
        if processing_result.errors:
            latest_issues = processing_result.errors
            return [item.repair_message() for item in latest_issues]

        validation_artifact = source.artifact.model_copy(
            update={"genui": latest_dsl}
        )
        validation_errors = ArtifactValidator().validate(
            validation_artifact,
            validation_protocol,
        )
        validation_issues = tuple(
            QualityIssue(
                stage="validation",
                code="ARTIFACT_VALIDATION_FAILED",
                message=message,
            )
            for message in validation_errors
        )
        latest_processing_result = DslProcessingResult(
            source_dsl=processing_result.source_dsl,
            standard_dsl=processing_result.standard_dsl,
            issues=processing_result.issues + validation_issues,
        )
        latest_issues = validation_issues
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
        final_compact_dsl = latest_processing_result.source_dsl
        if not final_compact_dsl:
            final_compact_dsl = retry_result.result
        return CompactDslRepairResult(
            compact_dsl=final_compact_dsl,
            dsl=latest_dsl,
            repair_count=retry_result.retryCount,
            initial_errors=tuple(retry_result.initialErrors),
        )
    finally:
        if model_client is not None:
            await model_client.aclose()


def main() -> None:
    """读取结果件，转换并校验极简协议，失败时自动调用模型 repair。"""
    logger.remove()
    artifact_path = Path(__file__).resolve().parents[2] / "docs" / "0824" / "0824.txt"
    result = asyncio.run(repair_compact_dsl(artifact_path))
    print(result.compact_dsl.strip())
    print(_OUTPUT_SEPARATOR)
    print(result.dsl.rstrip())


if __name__ == "__main__":
    main()
