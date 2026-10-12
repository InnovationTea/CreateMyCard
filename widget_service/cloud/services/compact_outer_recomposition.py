# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""有界小卡外层编译；不调用模型，不改组件Recipe或发布门禁。"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_composition_context import small_card_display_text
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    parse_compact_dsl_rows,
)
from services.compact_plan import compact_plan_coverage_errors
from services.compact_reference_canvas import reference_dimension

_PLAIN_COLUMN_PROPS = frozenset({
    "width", "height", "layoutWeight", "flexShrink", "itemMargin", "justifyContent", "alignItems",
})
_CONTENT_TYPES = frozenset({"EmphasizedData", "EmphasisText", "SecondaryBody", "TableText"})
_ITEM_PROPS = frozenset({"label", "value", "maxLines"})


@dataclass(frozen=True)
class OuterRecompositionResult:
    source_dsl: str
    reasons: tuple[str, ...] = ()
    candidate_count: int = 0
    applied: bool = False


def _validation_errors(source: str, context: dict[str, Any]) -> tuple[str, ...]:
    try:
        validate_compact_dsl(source, enforce_model_component_types=True, **context)
    except CompactDslValidationError as exc:
        return tuple(exc.errors)
    return ()


def _plain_leaves(rows: tuple[ComponentRow | DataRow, ...]) -> list[ComponentRow] | None:
    components = [row for row in rows if isinstance(row, ComponentRow)]
    if not components:
        return None
    root = components[0]
    if root.component_id != "root" or root.component_type != "Column":
        return None
    if root.props.get("onClick") or root.props.get("template_root"):
        return None
    leaves: list[ComponentRow] = []
    for row in components[1:]:
        if row.component_type == "Column":
            if set(row.props) - _PLAIN_COLUMN_PROPS:
                return None
            if row.props.get("width") not in (None, "matchParent"):
                return None
            continue
        if row.children:
            return None
        if row.component_type not in _CONTENT_TYPES | {"SingleLineTitle", "PillButton"}:
            return None
        if row.props.get("onClick") and row.component_type != "PillButton":
            return None
        leaves.append(row)
    titles = [row for row in leaves if row.component_type == "SingleLineTitle"]
    actions = [row for row in leaves if row.component_type == "PillButton"]
    if len(titles) != 1 or len(actions) > 1:
        return None
    if leaves[0] != titles[0] or (actions and leaves[-1] != actions[0]):
        return None
    return leaves


def _inner_width(root: ComponentRow, profile: dict[str, Any] | None) -> float | None:
    if root.props.get("width") != "matchParent":
        return None
    padding = root.props.get("padding")
    if isinstance(padding, bool):
        return None
    if isinstance(padding, (int, float)):
        horizontal = padding * 2
    elif isinstance(padding, dict):
        left, right = padding.get("left"), padding.get("right")
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        horizontal = left + right
    else:
        return None
    return reference_dimension("2x2", "width", profile) - horizontal


def _reflow_items(row: ComponentRow) -> list[dict[str, Any]] | None:
    """仅同规格supporting14到body14，不把普通信息换成metadata12。"""
    if row.component_type != "SecondaryBody" or row.props.get("role") != "supporting":
        return None
    if row.props.get("columns", 1) != 1 or row.props.get("fontSize", 14) != 14:
        return None
    allowed = {"width", "fontSize", "role", "columns", "items"}
    if set(row.props) - allowed or row.props.get("width") != "matchParent":
        return None
    items = row.props.get("items")
    if not isinstance(items, list) or len(items) not in (1, 2):
        return None
    for item in items:
        if not isinstance(item, dict) or set(item) - _ITEM_PROPS:
            return None
        if not isinstance(item.get("label"), str) or "value" not in item:
            return None
        if item.get("maxLines", 1) != 1:
            return None
    return items


def _certain_label_pressure(
    row: ComponentRow, task: dict[str, Any], width: float,
) -> bool:
    items = _reflow_items(row)
    if items is None:
        return False
    pressure = False
    for item in items:
        label, value = item.get("label"), item.get("value")
        text = small_card_display_text(value, task)
        if not isinstance(label, str) or text is None:
            return False  # 整个原信息组的每项都需可读，不猜未知值的换行。
        full_text = label + text
        conservative_width = sum(14 * (0.6 if ch.isascii() else 1) for ch in full_text)
        if "\n" in full_text or conservative_width > width * 2:
            return False  # 两行仍无已知可行空间时不自动合组；原错误/源不变。
        # 仅完整中文方块字与空格的下限触发候选，不把ASCII字符估算当硬门禁。
        lower_bound = 0.0
        for character in full_text:
            if "\u4e00" <= character <= "\u9fff":
                lower_bound += 14
            elif character.isspace():
                lower_bound += 14 / 4
        if lower_bound > width:
            pressure = True
    return pressure


def _joined_value(label: str, value: Any) -> str | None:
    if "${" in label or "{{" in label:
        return None
    result: str | None = None
    if isinstance(value, dict):
        path = value.get("path")
        if set(value) == {"path"} and isinstance(path, str):
            result = "{{ " + json.dumps(label, ensure_ascii=False) + " + ${" + path + "} }}"
    elif isinstance(value, str):
        expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, re.DOTALL)
        if expression is not None:
            result = "{{ " + json.dumps(label, ensure_ascii=False)
            result += " + (" + expression.group(1).strip() + ") }}"
        elif "{{" not in value:
            result = label + value
    return result


def _unique_id(base: str, used: set[str]) -> str:
    candidate = base
    index = 1
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _reflow(
    leaves: list[ComponentRow], pressure_ids: set[str], used: set[str],
) -> list[ComponentRow] | None:
    result: list[ComponentRow] = []
    for row in leaves:
        if row.component_id not in pressure_ids:
            result.append(row)
            continue
        items = _reflow_items(row)
        if items is None:
            return None
        bodies: list[ComponentRow] = []
        for item in items:
            label = item.get("label")
            if not isinstance(label, str) or "value" not in item:
                return None
            value = _joined_value(label, item.get("value"))
            if value is None:
                return None
            bodies.append(ComponentRow(
                _unique_id(row.component_id + "_full", used), "SecondaryBody",
                {"role": "body", "fontSize": 14, "width": "matchParent",
                 "items": [{"value": value, "maxLines": 2}]},
            ))
        result.append(ComponentRow(
            row.component_id, "Column", {"width": "matchParent", "itemMargin": 0},
            tuple(body.component_id for body in bodies),
        ))
        result.extend(bodies)
    return result


def _serialize(rows: list[ComponentRow | DataRow]) -> str:
    values: list[list[Any]] = []
    for row in rows:
        if isinstance(row, DataRow):
            values.append([row.path, row.value])
            continue
        value: list[Any] = [row.component_id, row.component_type, row.props]
        if row.children:
            value.append(list(row.children))
        values.append(value)
    return "\n".join(json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                     for value in values)


def _candidate(
    root: ComponentRow, leaves: list[ComponentRow], data: list[DataRow],
    gap: int, content_gap: int, pressure_ids: set[str], used: set[str],
) -> str | None:
    used = set(used)
    flowed = _reflow(leaves, pressure_ids, used)
    if flowed is None:
        return None
    title = flowed[0]
    action = flowed[-1] if flowed[-1].component_type == "PillButton" else None
    content = flowed[1:-1] if action is not None else flowed[1:]
    if not content:
        return None
    child_ids: list[str] = []
    nested_ids: set[str] = set()
    for row in content:
        if row.component_id not in nested_ids:
            child_ids.append(row.component_id)
        nested_ids.update(row.children)
    flow = ComponentRow(
        _unique_id("content_flow", used), "Column",
        {"width": "matchParent", "layoutWeight": 1, "itemMargin": content_gap,
         "alignItems": "start", "justifyContent": "start"}, tuple(child_ids),
    )
    props = copy.deepcopy(root.props)
    props["itemMargin"] = gap
    if action is not None:
        children = (title.component_id, flow.component_id, action.component_id)
        body_rows = [flow, *content, action]
    else:
        body = ComponentRow(
            _unique_id("body_flow", used), "Column",
            {"width": "matchParent", "layoutWeight": 1,
             "alignItems": "start", "justifyContent": "end"}, (flow.component_id,),
        )
        children = (title.component_id, body.component_id)
        body_rows = [body, flow, *content]
    return _serialize([ComponentRow(root.component_id, "Column", props, children),
                       title, *body_rows, *data])


def recompose_small_card(
    source_dsl: str, *, task_spec: dict[str, Any], card_spec: dict[str, Any],
    protocol_profile: dict[str, Any] | None, layout_scope: str | None,
    compact_plan: dict[str, Any] | None,
) -> OuterRecompositionResult:
    """最多16个无模型候选，原校验与硬事实均闭合才替换；否则原样回退。"""
    unchanged = OuterRecompositionResult(source_dsl)
    size = card_spec.get("suggestSize") or task_spec.get("size")
    if size != "2x2" or layout_scope is None:
        return unchanged
    try:
        rows = parse_compact_dsl_rows(source_dsl)
    except CompactDslConversionError:
        return unchanged  # 原处理器仍报告原解析错误，不掩盖失败。
    leaves = _plain_leaves(rows)
    if leaves is None or compact_plan_coverage_errors(source_dsl, compact_plan, task_spec):
        return unchanged
    root = rows[0]
    if not isinstance(root, ComponentRow):
        return unchanged
    context = {"task_spec": task_spec, "card_spec": card_spec,
               "protocol_profile": protocol_profile, "layout_scope": layout_scope}
    original_errors = _validation_errors(source_dsl, context)
    for message in original_errors:
        if ": vertical layout requires at least " not in message:
            return unchanged
    width = _inner_width(root, protocol_profile)
    pressure_ids: set[str] = set()
    if width is not None:
        for row in leaves:
            if _certain_label_pressure(row, task_spec, width):
                pressure_ids.add(row.component_id)
    if not original_errors and not pressure_ids:
        return unchanged
    reasons = ("height_capacity",) if original_errors else ()
    if pressure_ids:
        reasons += ("complete_label_width",)
    data = [row for row in rows if isinstance(row, DataRow)]
    used = set(row.component_id for row in rows if isinstance(row, ComponentRow))
    gaps = (6, 4, 2, 0) if leaves[-1].component_type == "PillButton" else (6,)
    attempted = 0
    for gap in gaps:
        for content_gap in (6, 4, 2, 0):
            candidate = _candidate(root, leaves, data, gap, content_gap, pressure_ids, used)
            if candidate is None:
                continue
            attempted += 1
            if _validation_errors(candidate, context):
                continue
            if compact_plan_coverage_errors(candidate, compact_plan, task_spec):
                continue
            return OuterRecompositionResult(candidate, reasons, attempted, True)
    return OuterRecompositionResult(source_dsl, reasons, attempted)
