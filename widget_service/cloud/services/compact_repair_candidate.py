# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""只整理与选择失败后的宽卡修复候选，不参与首次生成。"""

import json
import re
from dataclasses import dataclass

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    DataRow,
    parse_compact_dsl_rows,
    repair_compact_dsl_binding_paths,
    repair_compact_dsl_safe_structure,
)
from services.compact_plan import evaluate_compact_plan_coverage
from services.compact_wide_recomposition import recompose_wide_card
from services.generation_pipeline import DslProcessingContext
from services.protocol_registry import A2UIProtocolRegistry

_FONT_ERROR = re.compile(
    r"^([^:]+): SecondaryBody\.fontSize must be the fixed Recipe value (12|14)\."
)
_DSL_BLOCK = re.compile(r"```genui\s*\n(.*?)\n```", re.DOTALL)


@dataclass(frozen=True)
class CompactRepairSelection:
    source_dsl: str
    candidate_dsl: str
    corrections: tuple[str, ...] = ()
    rejection_issues: tuple[dict[str, str], ...] = ()
    layout_candidate_count: int = 0
    layout_search_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Assessment:
    source_dsl: str
    parse_error: str | None = None
    coverage_errors: tuple[str, ...] = ()
    issues: tuple[dict[str, str], ...] = ()


def _issue(code: str, message: str) -> dict[str, str]:
    return {"stage": "validation", "code": code, "message": message}


def _assess(source: str, context: DslProcessingContext) -> _Assessment:
    try:
        blocks = _DSL_BLOCK.findall(source)
        prefix_has_source = source.split("```", 1)[0].strip().startswith("[")
        multiple_sources = len(blocks) > 1 or (prefix_has_source and bool(blocks))
        if multiple_sources:
            raise CompactDslConversionError("Compact DSL must contain exactly one genui fence.")
        normalized = repair_compact_dsl_safe_structure(source, size=context.size)
        normalized = repair_compact_dsl_binding_paths(
            normalized, task_spec=context.task_spec, card_spec=context.card_spec
        )
        coverage = evaluate_compact_plan_coverage(
            normalized,
            context.compact_plan,
            context.task_spec,
            allowed_omitted_fact_indexes=context.allowed_omitted_plan_fact_indexes,
        )
    except CompactDslConversionError as exc:
        message = str(exc)
        return _Assessment(
            source_dsl=source,
            parse_error=message,
            issues=(_issue("COMPACT_DSL_VALIDATION_FAILED", message),),
        )
    issues = []
    for message in coverage.errors:
        issues.append(_issue("COMPACT_PLAN_COVERAGE_FAILED", message))
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        context.design_profile_id or "design-compact-dsl"
    )
    try:
        validate_compact_dsl(
            normalized,
            task_spec=context.task_spec,
            card_spec=context.card_spec,
            protocol_profile=profile,
            layout_scope=context.layout_scope,
            enforce_model_component_types=True,
        )
    except CompactDslValidationError as exc:
        for message in exc.errors:
            issues.append(_issue("COMPACT_DSL_VALIDATION_FAILED", message))
    return _Assessment(normalized, coverage_errors=coverage.errors, issues=tuple(issues))


def _correct_fixed_fonts(assessment: _Assessment) -> tuple[str, tuple[str, ...]]:
    fonts: dict[str, int] = {}
    for issue in assessment.issues:
        message = issue.get("message")
        if not isinstance(message, str):
            continue
        match = _FONT_ERROR.match(message)
        if match:
            fonts[match.group(1)] = int(match.group(2))
    if not fonts or assessment.parse_error is not None:
        return assessment.source_dsl, ()
    rows = parse_compact_dsl_rows(assessment.source_dsl)
    serialized = []
    corrections = []
    for row in rows:
        if isinstance(row, DataRow):
            serialized.append([row.path, row.value])
            continue
        props = dict(row.props)
        font = fonts.get(row.component_id)
        if font is not None and row.component_type == "SecondaryBody":
            props["fontSize"] = font
            corrections.append(f"{row.component_id}.fontSize={font}")
        value = [row.component_id, row.component_type, props]
        if row.children:
            value.append(list(row.children))
        serialized.append(value)
    lines = []
    for row in serialized:
        lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines), tuple(corrections)


def _prepare(source: str, context: DslProcessingContext) -> tuple[_Assessment, tuple[str, ...]]:
    assessment = _assess(source, context)
    corrected, corrections = _correct_fixed_fonts(assessment)
    if corrections:
        assessment = _assess(corrected, context)
    return assessment, corrections


def _extract_unique_valid_source(
    source: str, context: DslProcessingContext
) -> tuple[_Assessment | None, tuple[str, ...]]:
    sources = _DSL_BLOCK.findall(source)
    prefix = source.split("```", 1)[0].strip()
    if prefix.startswith("["):
        sources.insert(0, prefix)
    accepted: dict[str, tuple[_Assessment, tuple[str, ...]]] = {}
    for candidate in sources:
        assessment, corrections = _prepare(candidate, context)
        if not assessment.issues:
            accepted[assessment.source_dsl.strip()] = (assessment, corrections)
    result: tuple[_Assessment | None, tuple[str, ...]] = (None, ())
    if len(accepted) == 1:
        result = next(iter(accepted.values()))
    return result


def select_compact_repair_candidate(
    previous_source: str, candidate_source: str, context: DslProcessingContext
) -> CompactRepairSelection:
    """保留已覆盖的必要信息；允许正确补语义后暴露新的布局容量错误。"""
    if context.size != "2x4":
        return CompactRepairSelection(candidate_source, candidate_source)
    previous = _assess(previous_source, context)
    candidate, corrections = _prepare(candidate_source, context)
    if candidate.parse_error is not None and "```" in candidate_source:
        extracted, extracted_corrections = _extract_unique_valid_source(candidate_source, context)
        if extracted is not None:
            candidate = extracted
            corrections = ("extract_unique_valid_dsl", *extracted_corrections)
    regression = candidate.parse_error is not None and previous.parse_error is None
    if previous.parse_error is None and candidate.parse_error is None:
        previous_errors = set(previous.coverage_errors)
        for message in candidate.coverage_errors:
            if message not in previous_errors:
                regression = True
                break
    selection = CompactRepairSelection(
        candidate.source_dsl, candidate.source_dsl, corrections=corrections
    )
    if regression:
        selection = CompactRepairSelection(
            previous_source,
            candidate.source_dsl,
            corrections=corrections,
            rejection_issues=candidate.issues,
        )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        context.design_profile_id or "design-compact-dsl"
    )
    recomposed = recompose_wide_card(
        selection.source_dsl,
        task_spec=context.task_spec,
        card_spec=context.card_spec,
        protocol_profile=profile,
        layout_scope=context.layout_scope,
        compact_plan=context.compact_plan,
        allowed_omitted_fact_indexes=context.allowed_omitted_plan_fact_indexes,
    )
    corrections = selection.corrections
    if recomposed.applied:
        corrections += ("wide_layout_recomposition", *recomposed.reasons)
    selection = CompactRepairSelection(
        recomposed.source_dsl,
        selection.candidate_dsl,
        corrections=corrections,
        rejection_issues=selection.rejection_issues,
        layout_candidate_count=recomposed.candidate_count,
        layout_search_reasons=recomposed.reasons,
    )
    return selection
