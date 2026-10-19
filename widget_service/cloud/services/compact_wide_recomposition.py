"""失败后有界搜索2x4无损候选；复用原校验，不改变发布或模型重试规则。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    parse_compact_dsl_rows,
)
from services.compact_plan import evaluate_compact_plan_coverage
from services.compact_repair_simplification import (
    Rows,
    binding_paths,
    core_role_variants,
    serialize_rows,
    simplification_variants,
)

MAX_WIDE_REPAIR_CANDIDATES = 64
_REPAIR_MARKERS = (
    "vertical layout", "horizontal layout", "text width overflow",
    "语义布局不符合合同", "layout does not match semantic contract",
    "SecondaryBody is auxiliary and cannot be the only",
)


@dataclass(frozen=True)
class WideRecompositionResult:
    source_dsl: str
    applied: bool = False
    candidate_count: int = 0
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Snapshot:
    data: tuple[str, ...]
    actions: tuple[str, ...]
    bindings: dict[str, frozenset[str]]
    texts: dict[str, tuple[str, ...]]


def _texts(value: Any) -> list[str]:
    result = []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{{") and text.endswith("}}"):
            text = text.removeprefix("{{").removesuffix("}}").strip()
        if text:
            result.append(text)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key not in {"path", "label"}:
                result.extend(_texts(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_texts(child))
    return result


def _snapshot(rows: Rows) -> _Snapshot:
    nodes = {row.component_id: row for row in rows if isinstance(row, ComponentRow)}
    data = []
    for row in rows:
        if isinstance(row, DataRow):
            data.append(json.dumps([row.path, row.value], sort_keys=True, ensure_ascii=False))
    actions = []
    bindings: dict[str, frozenset[str]] = {}
    texts: dict[str, tuple[str, ...]] = {}
    pending = [("root", "root")]
    seen: set[str] = set()
    while pending:
        identifier, region = pending.pop()
        node = nodes.get(identifier)
        if node is None or identifier in seen:
            raise CompactDslConversionError("Deterministic candidate must preserve a closed tree.")
        seen.add(identifier)
        if node.component_type == "Region":
            region = identifier
        handlers = node.props.get("onClick")
        if handlers is not None:
            actions.append(json.dumps(
                [region, node.component_type, handlers], sort_keys=True, ensure_ascii=False,
            ))
        paths = set(bindings.get(region, frozenset()))
        paths.update(binding_paths(node.props))
        bindings[region] = frozenset(paths)
        displayed = list(texts.get(region, ()))
        for key in ("title", "value", "unit", "mainText", "secondaryText", "primaryText", "items"):
            displayed.extend(_texts(node.props.get(key)))
        if node.component_type in {"PillButton", "CardButton", "CircleButton"}:
            displayed.extend(_texts(node.props.get("label")))
        texts[region] = tuple(displayed)
        for child in node.children:
            pending.append((child, region))
    if seen != set(nodes):
        raise CompactDslConversionError("Deterministic candidate cannot discard unreachable facts.")
    return _Snapshot(tuple(data), tuple(sorted(actions)), bindings, texts)


def _preserves(candidate: _Snapshot, baseline: _Snapshot) -> bool:
    if candidate.data != baseline.data or candidate.actions != baseline.actions:
        return False
    if candidate.bindings != baseline.bindings:
        return False
    for region, texts in baseline.texts.items():
        updated = candidate.texts.get(region, ())
        for text in texts:
            if not any(text in value for value in updated):
                return False
    return True


def _variants(rows: Rows, task: dict, plan: dict | None, messages: tuple[str, ...]):
    if any("SecondaryBody is auxiliary and cannot be the only" in text for text in messages):
        yield from core_role_variants(rows, plan)
    wrap = any("width" in text for text in messages)
    yield from simplification_variants(rows, task, wrap=wrap)


def recompose_wide_card(
    source_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    protocol_profile: dict[str, Any],
    layout_scope: str | None,
    compact_plan: dict[str, Any] | None,
    messages: tuple[str, ...],
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
    information_errors_as_warnings: bool = False,
    candidate_limit: int = MAX_WIDE_REPAIR_CANDIDATES,
) -> WideRecompositionResult:
    """只接受完整通过且不增加事实缺失的候选；未找到则返回原稿。"""
    unchanged = WideRecompositionResult(source_dsl)
    if (card_spec.get("suggestSize") or task_spec.get("size")) != "2x4":
        return unchanged
    if layout_scope is None:
        return unchanged
    relevant = False
    for message in messages:
        if any(marker in message for marker in _REPAIR_MARKERS):
            relevant = True
    if not relevant:
        return unchanged
    limit = min(MAX_WIDE_REPAIR_CANDIDATES, max(0, candidate_limit))
    if limit == 0:
        return unchanged
    try:
        rows = parse_compact_dsl_rows(source_dsl, expand_layouts=False, size="2x4")
        root = next((row for row in rows if isinstance(row, ComponentRow)), None)
        if root is None or root.component_type != "Layout":
            return unchanged
        baseline = _snapshot(rows)
        try:
            coverage = evaluate_compact_plan_coverage(
                source_dsl, compact_plan, task_spec,
                allowed_omitted_fact_indexes=allowed_omitted_fact_indexes,
                information_errors_as_warnings=information_errors_as_warnings,
            )
            coverage_warnings = set(coverage.warnings)
        except CompactDslConversionError:
            coverage_warnings = set()
    except CompactDslConversionError:
        return WideRecompositionResult(source_dsl, reasons=("unsupported_source",))
    seen = {serialize_rows(rows)}
    count = 0
    for reason, candidate_rows in _variants(rows, task_spec, compact_plan, messages):
        candidate = serialize_rows(candidate_rows)
        if candidate in seen:
            continue
        if count >= limit:
            break
        seen.add(candidate)
        count += 1
        try:
            if not _preserves(_snapshot(candidate_rows), baseline):
                continue
            coverage = evaluate_compact_plan_coverage(
                candidate, compact_plan, task_spec,
                allowed_omitted_fact_indexes=allowed_omitted_fact_indexes,
                information_errors_as_warnings=information_errors_as_warnings,
            )
            if coverage.errors or set(coverage.warnings) - coverage_warnings:
                continue
            validate_compact_dsl(
                candidate, task_spec=task_spec, card_spec=card_spec,
                compact_plan=compact_plan, protocol_profile=protocol_profile,
                layout_scope=layout_scope, enforce_model_component_types=True,
            )
        except (CompactDslConversionError, CompactDslValidationError):
            continue
        return WideRecompositionResult(candidate, True, count, (reason,))
    return WideRecompositionResult(
        source_dsl, candidate_count=count, reasons=("no_valid_candidate",),
    )
