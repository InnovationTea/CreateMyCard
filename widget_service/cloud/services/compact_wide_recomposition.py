# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""失败后的宽卡有界布局搜索；复用原合同，不调用模型或修改校验门禁。"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    parse_compact_dsl_rows,
)
from services.compact_outer_recomposition import OuterRecompositionResult
from services.compact_plan import compact_plan_coverage_errors
from services.compact_repair_simplification import simplification_variants

_LIMIT = 64
_GEOMETRY_MARKERS = (
    "vertical layout requires at least",
    "text width overflow",
    "pressure width",
    "Compact layout does not match scope",
    "SecondaryBody.columns must",
)
_RELATION_PROPS = frozenset(
    {
        "width",
        "height",
        "itemMargin",
        "alignItems",
        "justifyContent",
        "layoutWeight",
        "flexShrink",
    }
)
_WEIGHTS = ((1, 1), (1, 2), (2, 1), (1, 3), (3, 1))
_Rows = list[ComponentRow | DataRow]


@dataclass(frozen=True)
class _Context:
    task_spec: dict[str, Any]
    card_spec: dict[str, Any]
    protocol_profile: dict[str, Any] | None
    layout_scope: str | None
    compact_plan: dict[str, Any] | None
    allowed_omitted_fact_indexes: tuple[int, ...]


@dataclass
class _Search:
    context: _Context
    seen: set[str] = field(default_factory=set)
    count: int = 0

    def accept(self, source: str) -> bool:
        if source in self.seen or self.count >= _LIMIT:
            return False
        self.seen.add(source)
        self.count += 1
        if _coverage_errors(source, self.context):
            return False
        return not _errors(source, self.context)


def _coverage_errors(source: str, context: _Context) -> tuple[str, ...]:
    return compact_plan_coverage_errors(
        source,
        context.compact_plan,
        context.task_spec,
        allowed_omitted_fact_indexes=context.allowed_omitted_fact_indexes,
    )


def _errors(source: str, context: _Context) -> tuple[str, ...]:
    try:
        validate_compact_dsl(
            source,
            task_spec=context.task_spec,
            card_spec=context.card_spec,
            protocol_profile=context.protocol_profile,
            layout_scope=context.layout_scope,
            enforce_model_component_types=True,
        )
    except CompactDslValidationError as exc:
        return tuple(exc.errors)
    return ()


def _serialize(rows: list[ComponentRow | DataRow]) -> str:
    lines = []
    for row in rows:
        if isinstance(row, DataRow):
            value = [row.path, row.value]
        else:
            value = [row.component_id, row.component_type, row.props]
            if row.children:
                value.append(list(row.children))
        lines.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def _replace(
    rows: list[ComponentRow | DataRow],
    changed: dict[str, ComponentRow],
) -> list[ComponentRow | DataRow]:
    result = []
    for row in rows:
        if isinstance(row, ComponentRow):
            row = changed.get(row.component_id, row)
        result.append(row)
    return result


def _text_variants(rows: _Rows) -> Iterator[tuple[str, _Rows]]:
    yield "existing_components", rows
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "SecondaryBody":
            continue
        for columns in (1, 2):
            for wrap in (False, True):
                props = copy.deepcopy(row.props)
                props["columns"] = columns
                if wrap:
                    items = props.get("items")
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, dict):
                            item["maxLines"] = 2
                replacement = ComponentRow(
                    row.component_id, row.component_type, props, row.children
                )
                yield "complete_text_reflow", _replace(rows, {row.component_id: replacement})


def _panels(rows: list[ComponentRow | DataRow]) -> list[ComponentRow | DataRow] | None:
    components = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            components[row.component_id] = row
    root = components.get("root")
    if root is None or root.component_type != "Row" or len(root.children) != 2:
        return None
    changed = {}
    for identifier in root.children:
        panel = components.get(identifier)
        if panel is None or panel.component_type != "Column":
            return None
        if panel.props.get("padding") not in (None, 8):
            return None
        props = copy.deepcopy(panel.props)
        props["padding"] = 8
        changed[identifier] = ComponentRow(identifier, "Column", props, panel.children)
    return _replace(rows, changed)


def _axis_variants(rows: _Rows) -> Iterator[tuple[str, _Rows]]:
    components = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            components[row.component_id] = row
    eligible = []
    for row in components.values():
        if row.component_id == "root" or len(row.children) != 2:
            continue
        if row.component_type not in ("Column", "Row"):
            continue
        if set(row.props) - _RELATION_PROPS:
            continue
        children = []
        for identifier in row.children:
            child = components.get(identifier)
            if child is None or child.props.get("width") not in (None, "matchParent"):
                break
            children.append(child)
        if len(children) == 2:
            eligible.append((row, children))
    for parent, children in eligible:
        kind = "Row" if parent.component_type == "Column" else "Column"
        weights = _WEIGHTS if kind == "Row" else ((1, 1),)
        for ratio in weights:
            changed = {
                parent.component_id: ComponentRow(
                    parent.component_id,
                    kind,
                    copy.deepcopy(parent.props),
                    parent.children,
                ),
            }
            for child, weight in zip(children, ratio, strict=True):
                props = copy.deepcopy(child.props)
                props["layoutWeight"] = weight
                changed[child.component_id] = ComponentRow(
                    child.component_id,
                    child.component_type,
                    props,
                    child.children,
                )
            yield "parent_axis_reflow", _replace(rows, changed)


def _partition_variants(rows: _Rows) -> Iterator[tuple[str, _Rows]]:
    components = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            components[row.component_id] = row
    for parent in components.values():
        if parent.component_id == "root" or parent.component_type != "Column":
            continue
        if len(parent.children) < 3 or set(parent.props) - _RELATION_PROPS:
            continue
        eligible = True
        for identifier in parent.children:
            child = components.get(identifier)
            if child is None or child.props.get("width") not in (None, "matchParent"):
                eligible = False
                break
        if not eligible:
            continue
        identifiers = []
        for suffix in ("left", "right"):
            identifier = f"{parent.component_id}_reflow_{suffix}"
            while identifier in components or identifier in identifiers:
                identifier += "_"
            identifiers.append(identifier)
        for split in range(1, len(parent.children)):
            for ratio in _WEIGHTS:
                changed = {
                    parent.component_id: ComponentRow(
                        parent.component_id,
                        "Row",
                        copy.deepcopy(parent.props),
                        tuple(identifiers),
                    ),
                }
                groups = (parent.children[:split], parent.children[split:])
                candidate = _replace(rows, changed)
                for identifier, group, weight in zip(identifiers, groups, ratio, strict=True):
                    props = {
                        "width": "matchParent",
                        "height": "matchParent",
                        "layoutWeight": weight,
                        "alignItems": "start",
                        "justifyContent": "start",
                    }
                    if "itemMargin" in parent.props:
                        props["itemMargin"] = parent.props.get("itemMargin")
                    candidate.append(ComponentRow(identifier, "Column", props, group))
                yield "ordered_column_partition", candidate


def _layout_variants(rows: _Rows) -> Iterator[tuple[str, _Rows]]:
    yield "existing_layout", rows
    panels = _panels(rows)
    if panels is not None:
        yield "formal_split_padding", panels
    yield from _axis_variants(rows)
    yield from _partition_variants(rows)
    if panels is not None:
        for reason, candidate in _axis_variants(panels):
            yield "formal_split_padding+" + reason, candidate
        for reason, candidate in _partition_variants(panels):
            yield "formal_split_padding+" + reason, candidate


def _candidates(variants: Iterable[tuple[str, _Rows]]) -> Iterator[tuple[str, str, _Rows]]:
    pending = []
    for variant_reason, rows in variants:
        for reason, text_rows in _text_variants(rows):
            if variant_reason != "existing_components":
                reason = variant_reason + "+" + reason
            pending.append((reason, iter(_layout_variants(text_rows))))
    while pending:
        text_reason, variants = pending.pop(0)
        try:
            layout_reason, candidate = next(variants)
        except StopIteration:
            continue
        yield text_reason, layout_reason, candidate
        pending.append((text_reason, variants))


def _find_candidate(
    search: _Search,
    candidates: Iterator[tuple[str, str, _Rows]],
    budget: int,
    phase: str,
) -> OuterRecompositionResult | None:
    started_at = search.count
    result: OuterRecompositionResult | None = None
    while search.count - started_at < budget and search.count < _LIMIT:
        try:
            text_reason, layout_reason, rows = next(candidates)
        except StopIteration:
            break
        source = _serialize(rows)
        if search.accept(source):
            result = OuterRecompositionResult(
                source, (phase, text_reason, layout_reason), search.count, True
            )
            break
    return result


def recompose_wide_card(
    source_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    protocol_profile: dict[str, Any] | None,
    layout_scope: str | None,
    compact_plan: dict[str, Any] | None,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> OuterRecompositionResult:
    """至多验证64个无损候选；只有原校验全部通过才返回替代源。"""
    unchanged = OuterRecompositionResult(source_dsl)
    size = card_spec.get("suggestSize") or task_spec.get("size")
    if size != "2x4" or layout_scope is None:
        return unchanged
    context = _Context(
        task_spec,
        card_spec,
        protocol_profile,
        layout_scope,
        compact_plan,
        allowed_omitted_fact_indexes,
    )
    try:
        rows = list(parse_compact_dsl_rows(source_dsl))
        for row in rows:
            if isinstance(row, ComponentRow) and row.props.get("template_root"):
                return unchanged
        if _coverage_errors(source_dsl, context):
            return unchanged
        errors = _errors(source_dsl, context)
    except CompactDslConversionError as exc:
        return OuterRecompositionResult(source_dsl, ("unsupported_source: " + str(exc),))
    if not errors:
        return unchanged
    for message in errors:
        if not any(marker in message for marker in _GEOMETRY_MARKERS):
            return unchanged
    search = _Search(context)
    layouts = _candidates((("existing_components", rows),))
    result = _find_candidate(search, layouts, max(1, _LIMIT // 2), "deterministic_layout")
    if result is not None:
        return result
    simplified = []
    for reason, candidate in simplification_variants(rows, task_spec):
        if candidate != rows:
            simplified.append((reason, candidate))
    candidates = layouts
    phase = "deterministic_layout"
    if simplified:
        candidates = _candidates(simplified)
        phase = "component_simplification"
    result = _find_candidate(search, candidates, _LIMIT - search.count, phase)
    if result is not None:
        return result
    if search.count >= _LIMIT:
        return OuterRecompositionResult(source_dsl, ("search_limit",), search.count)
    return OuterRecompositionResult(source_dsl, ("no_valid_candidate",), search.count)
