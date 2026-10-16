# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, Protocol

from custom.model_transport import ModelBackend
from services.card_validation import (
    CompactDslValidationError,
    validate_compact_dsl,
)
from services.card_validation.compact_validation.diagnostics import DiagnosticGroup
from services.card_validation.compact_validation.repair_guidance import RepairGuidanceContext
from services.card_validation.display_unit_rules import repair_repeated_display_units
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    expand_compact_semantic_layout,
    repair_compact_dsl_binding_paths,
    repair_compact_dsl_safe_structure,
)
from services.compact_outer_recomposition import recompose_small_card
from services.compact_plan import (
    compact_plan_omitted_facts,
    evaluate_compact_plan_coverage,
)
from services.generation_trace_recorder import TraceSpan, trace_operation, trace_record, trace_step
from services.protocol_registry import A2UIProtocolRegistry
from utils.ops_metrics import report_ops_metrics

IssueStage = Literal["conversion", "validation"]
IssueSeverity = Literal["error", "warning"]


class DslProcessorKind(StrEnum):
    """标识生成路由使用的 DSL 处理器，避免业务分支散落字符串常量。"""

    STANDARD_A2UI = "standard"
    DESIGN_COMPACT = "design-compact"


@dataclass(frozen=True)
class QualityIssue:
    """描述一次转换或 Artifact 校验发现的质量问题。"""

    stage: IssueStage
    code: str
    message: str
    severity: IssueSeverity = "error"
    prompt_context: dict[str, Any] = field(default_factory=dict)

    def repair_message(self) -> str:
        return f"[stage={self.stage} code={self.code}] {self.message}"

    def to_prompt_payload(self) -> dict[str, Any]:
        """把质量问题转换为 repair user 消息中的稳定结构。"""
        payload: dict[str, Any] = {
            "stage": self.stage,
            "code": self.code,
            "message": self.message,
        }
        payload.update(self.prompt_context)
        return payload


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
    skip_compact_dsl_validation: bool = False
    layout_scope: str | None = None
    compact_plan: dict[str, Any] | None = None
    allowed_omitted_plan_fact_indexes: tuple[int, ...] = ()
    plan_information_coverage_as_warning: bool = False
    repair_context: RepairGuidanceContext | None = None
    colorless_layout: bool = False


@dataclass(frozen=True)
class DslProcessingResult:
    """保留实际编译源、标准 DSL 和转换问题；模型原源另存于Trace。"""

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
    stores_design_token: bool = False
    single_step: bool = False
    quality_repair_limit: int | None = None


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
        standard_dsl = repair_repeated_display_units(
            source_dsl,
            context.card_spec,
            context.data_capabilities,
        )
        return DslProcessingResult(source_dsl=source_dsl, standard_dsl=standard_dsl)


def _capture_processing_result(span: TraceSpan, result: DslProcessingResult) -> None:
    span.text_artifacts["dsl_processing_input"] = result.source_dsl
    span.text_artifacts["dsl_processing_output"] = result.standard_dsl
    span.json_artifacts["dsl_processing_issues"] = [
        item.to_prompt_payload() for item in result.issues
    ]
    span.artifact_roles.update(
        {
            "dsl_processing_input": "input",
            "dsl_processing_output": "output",
            "dsl_processing_issues": "diagnostic",
        }
    )


class DesignCompactProcessor:
    @trace_operation("dsl.processing", kind="group", capture=_capture_processing_result)
    def process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        from services.theme_style_roles import layout_phase

        with layout_phase(context.colorless_layout, context.task_spec):
            return self._process(source_dsl, context)

    def _process(
        self, source_dsl: str, context: DslProcessingContext,
    ) -> DslProcessingResult:
        binding_repair_started_at = time.perf_counter()
        from services.layout_theme_contract import strip_source_colors
        from services.theme_style_roles import in_layout_phase

        original_source_dsl = source_dsl
        try:
            if in_layout_phase():
                source_dsl = strip_source_colors(source_dsl)
                original_source_dsl = source_dsl
            source_dsl = repair_compact_dsl_safe_structure(
                source_dsl,
                size=context.size,
                skip_compact_dsl_validation=context.skip_compact_dsl_validation,
            )
            safe_structure_repaired = source_dsl != original_source_dsl
            source_dsl = repair_compact_dsl_binding_paths(
                source_dsl,
                task_spec=context.task_spec,
                card_spec=context.card_spec,
                skip_compact_dsl_validation=context.skip_compact_dsl_validation,
            )
            expanded_source, layout_origins = expand_compact_semantic_layout(
                source_dsl, size=context.size,
                skip_compact_dsl_validation=context.skip_compact_dsl_validation,
            )
            if layout_origins:
                trace_step(
                    "dsl.semantic_layout.expanded", stage="dsl.layoutExpansion", status="success",
                    text_artifacts={"semantic_layout_source": source_dsl,
                                    "semantic_layout_expanded": expanded_source},
                    json_artifacts={"semantic_layout_origins": layout_origins},
                )
        except CompactDslConversionError as exc:
            trace_step(
                "dsl.binding_repair.completed",
                stage="dsl.bindingRepair",
                status="failed",
                duration_ms=_elapsed_ms(binding_repair_started_at),
                details={"message": str(exc)},
            )
            report_ops_metrics(body={"taskFailValidation": 1})
            return self._validation_failure(source_dsl, (str(exc),))
        trace_step(
            "dsl.binding_repair.completed",
            stage="dsl.bindingRepair",
            status="success",
            duration_ms=_elapsed_ms(binding_repair_started_at),
            details={"safeStructureRepaired": safe_structure_repaired},
            text_artifacts={
                "binding_repair_input": original_source_dsl,
                "compact_dsl_binding_repaired": source_dsl,
            },
            artifact_roles={
                "binding_repair_input": "input",
                "compact_dsl_binding_repaired": "output",
            },
        )

        design_profile_id = context.design_profile_id or "design-compact-dsl"
        design_protocol = A2UIProtocolRegistry.read_design_protocol_profile(design_profile_id)
        outer_applied = False
        if context.size == "2x2" and not context.skip_compact_dsl_validation:
            outer_started_at = time.perf_counter()
            outer_input = source_dsl
            outer_result = recompose_small_card(
                source_dsl, task_spec=context.task_spec, card_spec=context.card_spec,
                protocol_profile=design_protocol, layout_scope=context.layout_scope,
                compact_plan=context.compact_plan,
            )
            source_dsl = outer_result.source_dsl
            outer_applied = outer_result.applied
            trace_step(
                "dsl.outer_recomposition.completed",
                stage="dsl.outerRecomposition", status="success",
                duration_ms=_elapsed_ms(outer_started_at),
                details={"applied": outer_applied, "reasons": list(outer_result.reasons),
                         "candidateCount": outer_result.candidate_count},
                text_artifacts={"outer_recomposition_input": outer_input,
                                "outer_recomposition_output": source_dsl},
                artifact_roles={"outer_recomposition_input": "input",
                                "outer_recomposition_output": "output"},
            )

        plan_coverage_started_at = time.perf_counter()
        plan_coverage = evaluate_compact_plan_coverage(
            source_dsl,
            context.compact_plan,
            context.task_spec,
            allowed_omitted_fact_indexes=context.allowed_omitted_plan_fact_indexes,
            information_errors_as_warnings=context.plan_information_coverage_as_warning,
        )
        plan_errors = plan_coverage.errors
        plan_warnings = plan_coverage.warnings
        omitted_facts = compact_plan_omitted_facts(
            source_dsl,
            context.compact_plan,
            context.task_spec,
            context.allowed_omitted_plan_fact_indexes,
        )
        plan_issues = self._validation_failure(
            source_dsl, plan_errors, code="COMPACT_PLAN_COVERAGE_FAILED",
        ).issues
        plan_warning_issues = tuple(
            QualityIssue(
                stage="validation",
                code="COMPACT_PLAN_COVERAGE_WARNING",
                message=message,
                severity="warning",
            )
            for message in plan_warnings
        )
        optional_omission_issues = tuple(
            QualityIssue(
                stage="validation",
                code="COMPACT_PLAN_FACT_OMITTED",
                message=(
                    "Plan fact was omitted by the bounded fallback: "
                    f"{fact.get('requirement') or 'unknown requirement'}."
                ),
                severity="warning",
            )
            for fact in omitted_facts
        )
        trace_step(
            "dsl.plan_coverage_validation.completed",
            stage="dsl.planCoverageValidation",
            status="failed" if plan_errors else "success",
            duration_ms=_elapsed_ms(plan_coverage_started_at),
            details={"warningCount": len(plan_warnings)},
            text_artifacts={"coverage_validation_input": source_dsl},
            json_artifacts={
                "plan_coverage_result": {
                    "errors": list(plan_errors),
                    "warnings": list(plan_warnings),
                    "informationCoverageSeverity": (
                        "warning" if context.plan_information_coverage_as_warning else "error"
                    ),
                    "omittedFacts": [
                        fact.get("requirement") for fact in omitted_facts
                    ],
                }
            },
            artifact_roles={
                "coverage_validation_input": "input",
                "plan_coverage_result": "diagnostic",
            },
        )

        if not context.skip_compact_dsl_validation:
            compact_validation_started_at = time.perf_counter()
            try:
                validation_result = validate_compact_dsl(
                    source_dsl,
                    task_spec=context.task_spec,
                    card_spec=context.card_spec,
                    compact_plan=context.compact_plan,
                    protocol_profile=design_protocol,
                    layout_scope=context.layout_scope,
                    enforce_model_component_types=True,
                    original_source=original_source_dsl,
                    repair_context=context.repair_context,
                )
            except CompactDslValidationError as exc:
                trace_step(
                    "dsl.compact_validation.completed",
                    stage="dsl.compactValidation",
                    status="failed",
                    duration_ms=_elapsed_ms(compact_validation_started_at),
                    json_artifacts={
                        "compact_validation_errors": list(exc.errors),
                        "compact_diagnostics": [item.to_payload() for item in exc.diagnostics],
                    },
                    text_artifacts={"compact_validation_input": source_dsl},
                    artifact_roles={"compact_validation_input": "input"},
                )
                compact_issues = self._validation_failure(
                    source_dsl, exc.errors, groups=exc.groups,
                ).issues
                return DslProcessingResult(
                    source_dsl=source_dsl,
                    issues=(
                        *plan_issues,
                        *plan_warning_issues,
                        *optional_omission_issues,
                        *compact_issues,
                    ),
                )
            trace_step(
                "dsl.compact_validation.completed",
                stage="dsl.compactValidation",
                status="success",
                duration_ms=_elapsed_ms(compact_validation_started_at),
                details={"warningCount": len(validation_result.warnings)},
                json_artifacts={
                    "compact_validation_result": {
                        "errors": [],
                        "warnings": list(validation_result.warnings),
                    }
                },
                text_artifacts={"compact_validation_input": source_dsl},
                artifact_roles={
                    "compact_validation_input": "input",
                    "compact_validation_result": "diagnostic",
                },
            )
        else:
            # 跳过 Compact 专项校验，后续转换与 artifact 校验按原流程执行。
            validation_result = None
            trace_record(
                "dsl.compact_validation.skipped",
                stage="dsl.compactValidation",
                status="skipped",
                details={"reason": "explicit_validation_skip"},
            )

        if plan_issues:
            return DslProcessingResult(
                source_dsl=source_dsl,
                issues=(*plan_issues, *plan_warning_issues, *optional_omission_issues),
            )

        try:
            design_protocol["appVersion"] = context.task_spec["appVersion"]
            conversion_started_at = time.perf_counter()
            standard_dsl = convert_compact_dsl_to_a2ui(
                source_dsl,
                size=context.size,
                protocol_profile=design_protocol,
                skip_compact_dsl_validation=context.skip_compact_dsl_validation,
            )
            trace_step(
                "dsl.conversion.completed",
                stage="dsl.convert",
                status="success",
                duration_ms=_elapsed_ms(conversion_started_at),
                text_artifacts={
                    "conversion_input": source_dsl,
                    "standard_a2ui_before_unit_repair": standard_dsl,
                },
                artifact_roles={
                    "conversion_input": "input",
                    "standard_a2ui_before_unit_repair": "output",
                },
            )
            unit_repair_started_at = time.perf_counter()
            unit_repair_input = standard_dsl
            standard_dsl = repair_repeated_display_units(
                standard_dsl,
                context.card_spec,
                context.data_capabilities,
            )
            trace_step(
                "dsl.unit_repair.completed",
                stage="dsl.unitRepair",
                status="success",
                duration_ms=_elapsed_ms(unit_repair_started_at),
                text_artifacts={
                    "unit_repair_input": unit_repair_input,
                    "standard_a2ui_after_unit_repair": standard_dsl,
                },
                artifact_roles={
                    "unit_repair_input": "input",
                    "standard_a2ui_after_unit_repair": "output",
                },
            )
            warnings = tuple(
                QualityIssue(
                    stage="validation",
                    code="COMPACT_DSL_VALIDATION_WARNING",
                    message=message,
                    severity="warning",
                )
                for message in (validation_result.warnings if validation_result else ())
            )
            if outer_applied:
                warnings += (QualityIssue(
                    stage="conversion", code="COMPACT_OUTER_RECOMPOSITION_APPLIED",
                    message="2x2 outer composition compiled without changing facts or font sizes.",
                    severity="warning",
                ),)
            return DslProcessingResult(
                source_dsl=source_dsl,
                standard_dsl=standard_dsl,
                issues=(
                    *plan_warning_issues,
                    *optional_omission_issues,
                    *warnings,
                ),
            )
        except CompactDslConversionError as exc:
            trace_step(
                "dsl.conversion.completed",
                stage="dsl.convert",
                status="failed",
                duration_ms=_elapsed_ms(conversion_started_at),
                details={"message": str(exc)},
            )
            issue = QualityIssue(
                stage="conversion",
                code="DESIGN_CONVERSION_FAILED",
                message=str(exc),
            )
            return DslProcessingResult(source_dsl=source_dsl, issues=(issue,))

    @staticmethod
    def _validation_failure(
        source_dsl: str,
        errors: tuple[str, ...],
        *,
        code: str = "COMPACT_DSL_VALIDATION_FAILED",
        groups: tuple[DiagnosticGroup, ...] | None = None,
    ) -> DslProcessingResult:
        if groups is None:
            groups = tuple(DiagnosticGroup(message, has_legacy_record=True) for message in errors)
        issues = tuple(
            QualityIssue(
                stage="validation",
                code=code,
                message=group.legacy_message,
                prompt_context=group.prompt_context(),
            )
            for group in groups
        )
        return DslProcessingResult(source_dsl=source_dsl, issues=issues)


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


_PROCESSORS: dict[DslProcessorKind, DslProcessor] = {
    DslProcessorKind.STANDARD_A2UI: StandardA2UIProcessor(),
    DslProcessorKind.DESIGN_COMPACT: DesignCompactProcessor(),
}


def get_dsl_processor(kind: DslProcessorKind) -> DslProcessor:
    """按路由策略取得无状态 DSL Processor。"""
    return _PROCESSORS[kind]
