# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

from custom.model_transport import ModelBackend
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    repair_compact_dsl_binding_paths,
    validate_compact_dsl_context,
)
from services.compact_dsl_protocol import preflight_compact_dsl
from services.protocol_registry import A2UIProtocolRegistry
from services.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
    convert_terse_dsl_nested2_to_a2ui,
)

IssueStage = Literal["conversion", "validation"]
IssueSeverity = Literal["error", "warning"]


class DslProcessorKind(StrEnum):
    """标识生成路由使用的 DSL 处理器，避免业务分支散落字符串常量。"""

    STANDARD_A2UI = "standard"
    DESIGN_COMPACT = "design-compact"
    TERSE_NESTED2 = "terse-nested2"
    LEGACY_COMPACT = "legacy-compact"


@dataclass(frozen=True)
class QualityIssue:
    """描述一次转换或 Artifact 校验发现的质量问题。"""

    stage: IssueStage
    code: str
    message: str
    severity: IssueSeverity = "error"

    def repair_message(self) -> str:
        return f"[stage={self.stage} code={self.code}] {self.message}"


@dataclass(frozen=True)
class DslProcessingContext:
    """DSL Processor 执行一次确定性转换所需的请求上下文。"""

    size: str
    card_spec: dict
    task_spec: dict
    protocol_profile: dict
    design_profile_id: str | None = None
    data_capabilities: list = field(default_factory=list)
    event_candidates: list = field(default_factory=list)


@dataclass(frozen=True)
class DslProcessingResult:
    """保留模型源 DSL、标准 DSL 和转换阶段问题。"""

    source_dsl: str
    standard_dsl: str = ""
    issues: tuple[QualityIssue, ...] = ()

    @property
    def errors(self) -> tuple[QualityIssue, ...]:
        return tuple(item for item in self.issues if item.severity == "error")


@dataclass(frozen=True)
class GenerationRoutePolicy:
    """集中描述第三至第五接口的固定差异。"""

    operation: str
    protocol_profile_id: str
    backend: ModelBackend
    processor_kind: DslProcessorKind
    source_format: str
    model_profile_id: str
    model_format: str
    design_profile_id: str | None = None
    supports_edit: bool = True
    supports_dynamic_capabilities: bool = True
    validation_failure_blocking: bool = False


class DslProcessor(Protocol):
    def process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        """把模型源 DSL 转换为标准 A2UI，失败时返回结构化问题。"""
        ...


class StandardA2UIProcessor:
    def process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        del context
        return DslProcessingResult(source_dsl=source_dsl, standard_dsl=source_dsl)


class DesignCompactProcessor:
    def process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        try:
            source_dsl = repair_compact_dsl_binding_paths(
                source_dsl,
                task_spec=context.task_spec,
                card_spec=context.card_spec,
            )
            context_result = validate_compact_dsl_context(
                source_dsl,
                task_spec=context.task_spec,
                card_spec=context.card_spec,
            )
            design_profile_id = context.design_profile_id or "design-compact-dsl"
            design_protocol = A2UIProtocolRegistry.read_design_protocol_profile(
                design_profile_id
            )
            standard_dsl = convert_compact_dsl_to_a2ui(
                source_dsl,
                size=context.size,
                protocol_profile=design_protocol,
            )
            warnings = tuple(
                QualityIssue(
                    stage="conversion",
                    code="DESIGN_CONTEXT_WARNING",
                    message=message,
                    severity="warning",
                )
                for message in context_result.warnings
            )
            return DslProcessingResult(
                source_dsl=source_dsl,
                standard_dsl=standard_dsl,
                issues=warnings,
            )
        except CompactDslConversionError as exc:
            issue = QualityIssue(
                stage="conversion",
                code="DESIGN_CONVERSION_FAILED",
                message=str(exc),
            )
            return DslProcessingResult(source_dsl=source_dsl, issues=(issue,))


class TerseNested2Processor:
    def process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        try:
            standard_dsl = convert_terse_dsl_nested2_to_a2ui(
                source_dsl,
                size=context.size,
                protocol_profile=context.protocol_profile,
            )
            return DslProcessingResult(
                source_dsl=source_dsl,
                standard_dsl=standard_dsl,
            )
        except TerseDslNested2ConversionError as exc:
            issue = QualityIssue(
                stage="conversion",
                code="TERSE_CONVERSION_FAILED",
                message=str(exc),
            )
            return DslProcessingResult(source_dsl=source_dsl, issues=(issue,))


class LegacyCompactProcessor:
    def process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        preflight = preflight_compact_dsl(
            source_dsl,
            context.card_spec,
            context.data_capabilities,
            context.event_candidates,
            context.task_spec,
        )
        issues = tuple(
            QualityIssue(
                stage="conversion",
                code=item.category,
                message=item.message,
                severity=item.severity,
            )
            for item in preflight.diagnostics
        )
        standard_dsl = preflight.genui if preflight.passed else ""
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl=standard_dsl,
            issues=issues,
        )


_PROCESSORS: dict[DslProcessorKind, DslProcessor] = {
    DslProcessorKind.STANDARD_A2UI: StandardA2UIProcessor(),
    DslProcessorKind.DESIGN_COMPACT: DesignCompactProcessor(),
    DslProcessorKind.TERSE_NESTED2: TerseNested2Processor(),
    DslProcessorKind.LEGACY_COMPACT: LegacyCompactProcessor(),
}


def get_dsl_processor(kind: DslProcessorKind) -> DslProcessor:
    """按路由策略取得无状态 DSL Processor。"""
    return _PROCESSORS[kind]
