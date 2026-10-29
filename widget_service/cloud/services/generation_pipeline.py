# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import copy
import time
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Literal, Protocol

from app.logger import logger
from config.config import get_settings
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
    serialize_compact_dsl_source,
)
from services.compact_duplicate_display import (
    duplicate_display_candidates,
    duplicate_display_feedback,
)
from services.compact_outer_recomposition import recompose_small_card
from services.compact_plan import (
    compact_plan_omitted_facts,
    evaluate_compact_plan_coverage,
)
from services.compact_repair_context import bounded_component_capacity_contexts
from services.compact_wide_recomposition import recompose_wide_card
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    GenerationContentPolicy,
    content_policy_scope,
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

    def to_diagnostic_payload(self) -> dict[str, Any]:
        """为 Trace 保留完整诊断级别，不改变修复模型输入。"""
        payload = self.to_prompt_payload()
        payload["severity"] = self.severity
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
    content_policy: GenerationContentPolicy = EXISTING_CONTENT_POLICY


@dataclass(frozen=True)
class DslProcessingResult:
    """保留实际编译源、标准 DSL 和转换问题；模型原源另存于Trace。"""

    source_dsl: str
    standard_dsl: str = ""
    issues: tuple[QualityIssue, ...] = ()
    repair_source_dsl: str | None = None

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
        item.to_diagnostic_payload() for item in result.issues
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

        with (
            content_policy_scope(context.content_policy),
            layout_phase(context.colorless_layout, context.task_spec),
        ):
            result = self._process(source_dsl, context)
            enabled = get_settings().enable_design_compact_deterministic_repair
            if enabled and result.errors and not context.skip_compact_dsl_validation:
                if not context.content_policy.is_static:
                    result = self._repair_duplicate_display(result, context)
            if context.content_policy.is_static and result.errors:
                static_recovery_started_at = time.perf_counter()
                from services.static_content_components import complete_static_text_trial
                from services.static_content_presentation import static_presentation_candidates

                plan = context.compact_plan or {}
                original_sources = set(
                    static_presentation_candidates(
                        plan, context.size, context.allowed_omitted_plan_fact_indexes
                    )
                )
                sources = list(static_presentation_candidates(
                    plan, context.size, context.allowed_omitted_plan_fact_indexes,
                    include_fallback=True,
                ))
                frozen = plan.get("staticPresentation")
                if isinstance(frozen, str) and not context.allowed_omitted_plan_fact_indexes:
                    sources.insert(0, frozen)
                    original_sources.add(frozen)
                tried = set()
                for candidate_source in sources:
                    if candidate_source in tried:
                        continue
                    tried.add(candidate_source)
                    with complete_static_text_trial(candidate_source not in original_sources):
                        candidate_result = self._process(candidate_source, context)
                    if candidate_result.errors:
                        continue
                    trace_step(
                        "static_content.presentation.recovered",
                        stage="dsl.staticPresentation",
                        status="success",
                        duration_ms=_elapsed_ms(static_recovery_started_at),
                        details={"candidateCount": len(tried), "coreChanged": False},
                        text_artifacts={"static_presentation_source": candidate_source},
                    )
                    return candidate_result
                result = self._repair_missing_shared_header(result, context)
            eligible = context.size == "2x4" and not context.skip_compact_dsl_validation
            eligible = eligible and not context.content_policy.is_static
            if not enabled or not eligible or not result.errors:
                return result
            started_at = time.perf_counter()
            profile = A2UIProtocolRegistry.read_design_protocol_profile(
                context.design_profile_id or "design-compact-dsl"
            )
            candidate = recompose_wide_card(
                result.source_dsl,
                task_spec=context.task_spec,
                card_spec=context.card_spec,
                protocol_profile=profile,
                layout_scope=context.layout_scope,
                compact_plan=context.compact_plan,
                messages=tuple(issue.message for issue in result.errors),
                allowed_omitted_fact_indexes=context.allowed_omitted_plan_fact_indexes,
                information_errors_as_warnings=context.plan_information_coverage_as_warning,
            )
            if candidate.candidate_count == 0:
                return result
            applied = False
            original = result
            if candidate.applied:
                validated = self._process(candidate.source_dsl, context)
                if not validated.errors:
                    result = validated
                    applied = True
            artifacts = {"deterministic_repair_input": original.source_dsl}
            artifact_roles = {"deterministic_repair_input": "input"}
            if applied:
                artifacts["deterministic_repair_output"] = result.source_dsl
                artifact_roles["deterministic_repair_output"] = "output"
            trace_step(
                "dsl.deterministic_repair.completed",
                stage="dsl.deterministicRepair",
                status="success",
                duration_ms=_elapsed_ms(started_at),
                details={
                    "applied": applied,
                    "candidateCount": candidate.candidate_count,
                    "reasons": list(candidate.reasons),
                },
                text_artifacts=artifacts,
                artifact_roles=artifact_roles,
            )
            return result

    def _repair_missing_shared_header(
        self, original: DslProcessingResult, context: DslProcessingContext,
    ) -> DslProcessingResult:
        from services.static_content_presentation import missing_shared_header_candidate

        if context.skip_compact_dsl_validation or not context.compact_plan:
            return original
        for issue in original.errors:
            if not issue.message.startswith("COMPACT_STATIC_CORE_MISSING:"):
                return original
        started_at = time.perf_counter()
        candidate = missing_shared_header_candidate(
            original.source_dsl, context.compact_plan, context.size,
            context.allowed_omitted_plan_fact_indexes,
        )
        if candidate is None:
            return original
        validated = self._process(candidate, context)
        if serialize_compact_dsl_source(candidate) != serialize_compact_dsl_source(
            validated.source_dsl,
        ):
            return original
        if validated.errors and not self._shared_header_capacity_only(validated, context):
            return original
        if validated.errors:
            validated = replace(validated, repair_source_dsl=validated.source_dsl)
        logger.info(
            "[Generation Pipeline] static_shared_header_prepared body_changed=false "
            "requires_model_repair={} error_count={}",
            bool(validated.errors), len(validated.errors),
        )
        trace_step(
            "static_content.shared_header.prepared",
            stage="dsl.staticPresentation",
            status="failed" if validated.errors else "success",
            duration_ms=_elapsed_ms(started_at),
            details={"candidateCount": 1, "bodyChanged": False,
                     "requiresModelRepair": bool(validated.errors)},
            text_artifacts={"shared_header_input": original.source_dsl,
                            "shared_header_candidate": validated.source_dsl},
            json_artifacts={"shared_header_issues": [
                issue.to_diagnostic_payload() for issue in validated.issues
            ]},
            artifact_roles={"shared_header_input": "input", "shared_header_candidate": "output",
                            "shared_header_issues": "diagnostic"},
        )
        return validated

    @staticmethod
    def _shared_header_capacity_only(
        result: DslProcessingResult, context: DslProcessingContext,
    ) -> bool:
        from services.compact_repair_context import static_component_capacity_contexts
        from services.static_content_presentation import static_candidate_expansion_error

        if len(result.errors) != 1:
            return False
        issue = result.errors[0]
        diagnostics = issue.prompt_context.get("compactDiagnostics", [])
        if not isinstance(diagnostics, list):
            return False
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                return False
            if diagnostic.get("code") != "COMPACT_STATIC_TEXT_CAPACITY":
                return False
            if diagnostic.get("legacyMessage") != issue.message:
                return False
            if diagnostic.get("message") != issue.message:
                return False
        actual_error = static_candidate_expansion_error(result.source_dsl, context.size)
        if issue.message != actual_error:
            return False
        return bool(static_component_capacity_contexts(
            result.source_dsl, [issue.to_prompt_payload()], context.compact_plan,
            context.allowed_omitted_plan_fact_indexes,
        ))

    def _repair_duplicate_display(
        self, original: DslProcessingResult, context: DslProcessingContext,
    ) -> DslProcessingResult:
        duplicates = ()
        for issue in original.errors:
            facts = issue.prompt_context.get("duplicateFacts")
            if isinstance(facts, list) and facts:
                duplicates = tuple(facts)
                break
        candidates = duplicate_display_candidates(original.source_dsl, duplicates)
        if not candidates:
            return original
        started_at = time.perf_counter()
        for index, candidate in enumerate(candidates, 1):
            validated = self._process(candidate.source_dsl, context)
            if validated.errors or not validated.standard_dsl:
                continue
            # 完整复检不得趁去重改动固定骨架或其它 Props；不进入 process 的恢复循环。
            candidate_source = serialize_compact_dsl_source(candidate.source_dsl)
            validated_source = serialize_compact_dsl_source(validated.source_dsl)
            if candidate_source != validated_source:
                continue
            trace_step(
                "dsl.duplicate_display.recovered",
                stage="dsl.duplicateDisplay",
                status="success",
                duration_ms=_elapsed_ms(started_at),
                details={
                    "candidateCount": index,
                    "removedPositions": list(candidate.removed_positions),
                },
                text_artifacts={
                    "duplicate_display_input": original.source_dsl,
                    "duplicate_display_output": validated.source_dsl,
                },
                artifact_roles={
                    "duplicate_display_input": "input", "duplicate_display_output": "output",
                },
            )
            return validated
        return original

    def _process(
        self,
        source_dsl: str,
        context: DslProcessingContext,
    ) -> DslProcessingResult:
        binding_repair_started_at = time.perf_counter()
        from services.layout_theme_contract import strip_source_colors
        from services.theme_style_roles import in_layout_phase

        original_source_dsl = source_dsl
        try:
            if in_layout_phase():
                source_dsl = strip_source_colors(source_dsl)
                original_source_dsl = source_dsl
            if context.content_policy.is_static:
                from services.static_content_planning import normalize_static_record_table

                source_dsl = normalize_static_record_table(source_dsl)
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
            expansion_started_at = time.perf_counter()
            expanded_source, layout_origins = expand_compact_semantic_layout(
                source_dsl,
                size=context.size,
                skip_compact_dsl_validation=context.skip_compact_dsl_validation,
            )
            if layout_origins:
                trace_step(
                    "dsl.semantic_layout.expanded",
                    stage="dsl.layoutExpansion",
                    status="success",
                    duration_ms=_elapsed_ms(expansion_started_at),
                    text_artifacts={
                        "semantic_layout_source": source_dsl,
                        "semantic_layout_expanded": expanded_source,
                    },
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
        small_recomposition = context.size == "2x2" and not context.skip_compact_dsl_validation
        if small_recomposition and not context.content_policy.is_static:
            outer_started_at = time.perf_counter()
            outer_input = source_dsl
            outer_result = recompose_small_card(
                source_dsl,
                task_spec=context.task_spec,
                card_spec=context.card_spec,
                protocol_profile=design_protocol,
                layout_scope=context.layout_scope,
                compact_plan=context.compact_plan,
            )
            source_dsl = outer_result.source_dsl
            outer_applied = outer_result.applied
            trace_step(
                "dsl.outer_recomposition.completed",
                stage="dsl.outerRecomposition",
                status="success",
                duration_ms=_elapsed_ms(outer_started_at),
                details={
                    "applied": outer_applied,
                    "reasons": list(outer_result.reasons),
                    "candidateCount": outer_result.candidate_count,
                },
                text_artifacts={
                    "outer_recomposition_input": outer_input,
                    "outer_recomposition_output": source_dsl,
                },
                artifact_roles={
                    "outer_recomposition_input": "input",
                    "outer_recomposition_output": "output",
                },
            )

        plan_coverage_started_at = time.perf_counter()
        plan_coverage = evaluate_compact_plan_coverage(
            source_dsl,
            context.compact_plan,
            context.task_spec,
            allowed_omitted_fact_indexes=context.allowed_omitted_plan_fact_indexes,
            information_errors_as_warnings=context.plan_information_coverage_as_warning,
            check_duplicate_actions=not context.skip_compact_dsl_validation,
        )
        plan_errors = plan_coverage.errors
        plan_warnings = plan_coverage.warnings
        omitted_facts = compact_plan_omitted_facts(
            source_dsl,
            context.compact_plan,
            context.task_spec,
            context.allowed_omitted_plan_fact_indexes,
        )
        duplicate_fact_context: dict[str, Any] = {}
        if plan_coverage.duplicate_facts:
            duplicate_fact_context["duplicateFacts"] = duplicate_display_feedback(
                plan_coverage.duplicate_facts,
            )
        if plan_coverage.duplicate_actions:
            duplicate_fact_context["duplicateActions"] = copy.deepcopy(
                list(plan_coverage.duplicate_actions),
            )
        plan_issues = tuple(
            QualityIssue(
                stage="validation",
                code="COMPACT_PLAN_COVERAGE_FAILED",
                message=message,
                prompt_context=(duplicate_fact_context if index == 0 else {}),
            )
            for index, message in enumerate(plan_errors)
        )
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
                    "omittedFacts": [fact.get("requirement") for fact in omitted_facts],
                }
            },
            artifact_roles={
                "coverage_validation_input": "input",
                "plan_coverage_result": "diagnostic",
            },
        )

        if not context.skip_compact_dsl_validation or context.content_policy.is_static:
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
                    **(
                        {"allowed_omitted_fact_indexes": context.allowed_omitted_plan_fact_indexes}
                        if context.content_policy.is_static
                        else {}
                    ),
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
                    source_dsl,
                    exc.errors,
                    groups=exc.groups,
                ).issues
                capacity_evidence: list[Any] = list(exc.errors)
                capacity_evidence.extend(item.to_payload() for item in exc.diagnostics)
                capacity_contexts = bounded_component_capacity_contexts(
                    source_dsl,
                    capacity_evidence,
                    context.compact_plan,
                )
                if capacity_contexts and compact_issues:
                    first_issue = compact_issues[0]
                    prompt_context = dict(first_issue.prompt_context)
                    prompt_context["capacityFits"] = capacity_contexts
                    compact_issues = (
                        replace(first_issue, prompt_context=prompt_context),
                        *compact_issues[1:],
                    )
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
            from services.card_validation.progress_sources import progress_dsl_errors

            progress_errors = progress_dsl_errors(
                standard_dsl,
                context.task_spec.get("dataModelSchema"),
            )
            if progress_errors:
                raise CompactDslConversionError("; ".join(progress_errors))
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
                warnings += (
                    QualityIssue(
                        stage="conversion",
                        code="COMPACT_OUTER_RECOMPOSITION_APPLIED",
                        message=(
                            "2x2 outer composition compiled without changing facts or font sizes."
                        ),
                        severity="warning",
                    ),
                )
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
