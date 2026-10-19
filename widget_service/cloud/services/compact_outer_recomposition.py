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
from services.validation_execution import ValidationExecutionContext

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
    if "${" in label or "{{" in label or '"' in label:
        return None
    escaped = json.dumps(label, ensure_ascii=False).removeprefix('"').removesuffix('"')
    escaped = escaped.replace('\\"', '"').replace("'", "\\'")
    literal = "'" + escaped + "'"
    result: str | None = None
    if isinstance(value, dict):
        path = value.get("path")
        if set(value) == {"path"} and isinstance(path, str):
            result = "{{ " + literal + " + ${" + path + "} }}"
    elif isinstance(value, str):
        expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, re.DOTALL)
        if expression is not None:
            result = "{{ " + literal
            result += " + (" + expression.group(1).strip() + ") }}"
        elif "{{" not in value:
            result = label + value
    return result


def _source_pressure_task(task: dict[str, Any], data: list[DataRow]) -> dict[str, Any]:
    """只读当前源实际值替换压力样值；不改发布schema或模型输入。"""
    result = copy.deepcopy(task)
    values = {row.path: row.value for row in data}

    def visit(schema: Any, path: str) -> None:
        if isinstance(schema, list):
            for index, child in enumerate(schema):
                visit(child, path + f"/{index}")
            return
        if not isinstance(schema, dict):
            return
        if "type" in schema:
            value = values.get(path)
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                schema["sampleValue"] = value
            return
        for key, child in schema.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            visit(child, path + "/" + escaped)

    visit(result.get("dataModelSchema"), "")
    return result


def _object_owner(task: dict[str, Any], path: str) -> str | None:
    schema = task.get("dataModelSchema")
    owner: str | None = None
    traversed = ""
    for part in path.removeprefix("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(schema, list) and part.isdigit():
            index = int(part)
            schema = schema[index] if index < len(schema) else None
        elif isinstance(schema, dict) and "type" not in schema:
            schema = schema.get(key)
        else:
            return None
        traversed += "/" + part
        if isinstance(schema, dict) and "type" not in schema:
            owner = traversed
    if not isinstance(schema, dict) or "type" not in schema:
        return None
    return owner


def _single_attribute(
    row: ComponentRow, task: dict[str, Any],
) -> tuple[dict[str, Any], str, str] | None:
    result: tuple[dict[str, Any], str, str] | None = None
    items = _reflow_items(row)
    item = items[0] if items is not None and len(items) == 1 else None
    value = item.get("value") if item is not None else None
    paths: list[str] = []
    if isinstance(value, dict) and isinstance(value.get("path"), str):
        paths.append(value.get("path"))
    elif isinstance(value, str):
        paths = re.findall(r"\$\{(/[^{}]+)\}", value)
    owners = {_object_owner(task, path) for path in paths}
    owner = next(iter(owners)) if len(owners) == 1 else None
    if item is not None and isinstance(owner, str):
        text = small_card_display_text(value, task)
        if text is not None and "\n" not in text:
            result = item, owner, text
    return result


def _paragraph(
    leaves: list[ComponentRow], task: dict[str, Any], width: float,
) -> list[ComponentRow] | None:
    """至多合一个同对象连续组；用既有body14两行，不缩字或跨对象。"""
    for start in range(1, len(leaves) - 1):
        expressions: list[str] = []
        display: list[str] = []
        owner: str | None = None
        chosen: list[ComponentRow] | None = None
        for end in range(start, min(len(leaves), start + 4)):
            attribute = _single_attribute(leaves[end], task)
            if attribute is None:
                break
            item, current_owner, text = attribute
            if owner is not None and owner != current_owner:
                break
            owner = current_owner
            label = item.get("label")
            if not isinstance(label, str) or "\n" in label:
                break
            label = label.rstrip()
            joined = _joined_value(label, item.get("value"))
            if joined is None or not joined.startswith("{{"):
                break
            expressions.append("(" + joined.removeprefix("{{").removesuffix("}}").strip() + ")")
            display.append(label + text)
            full_text = ";".join(display)
            # 沿用容量估算的ASCII半字宽，仅筛候选；原宽度门禁与真机验收不放宽。
            estimated = sum(14 * (0.5 if ch.isascii() else 1) for ch in full_text)
            if estimated > width * 2:
                break
            if len(expressions) < 2:
                continue
            value = "{{ " + " + ';' + ".join(expressions) + " }}"
            body = ComponentRow(
                leaves[start].component_id, "SecondaryBody",
                {"role": "body", "fontSize": 14, "width": "matchParent",
                 "items": [{"value": value, "maxLines": 2}]},
            )
            after_group = end + 1
            chosen = leaves[:start] + [body] + leaves[after_group:]
        if chosen is not None:
            return chosen
    return None


def _compact_existing_attribute_group(
    leaves: list[ComponentRow], task: dict[str, Any], width: float,
) -> list[ComponentRow] | None:
    """两项原属性同字号合组；仍仅一个同对象组，不修改组件内部Recipe。"""
    for index, row in enumerate(leaves):
        items = _reflow_items(row)
        if items is None or len(items) != 2:
            continue
        expressions: list[str] = []
        display: list[str] = []
        owners: set[str] = set()
        for item in items:
            single = ComponentRow(row.component_id, row.component_type,
                                  {**row.props, "items": [item]})
            attribute = _single_attribute(single, task)
            if attribute is None:
                break
            original, owner, text = attribute
            label = original.get("label")
            if not isinstance(label, str) or "\n" in label:
                break
            label = label.rstrip()
            joined = _joined_value(label, original.get("value"))
            if joined is None or not joined.startswith("{{"):
                break
            owners.add(owner)
            display.append(label + text)
            expression = joined.removeprefix("{{").removesuffix("}}").strip()
            expressions.append("(" + expression + ")")
        if len(expressions) != len(items) or len(owners) != 1:
            continue
        text_width = sum(14 * (0.6 if char.isascii() else 1) for char in ";".join(display))
        if text_width > width * 2:
            continue
        value = "{{ " + " + ';' + ".join(expressions) + " }}"
        body = ComponentRow(
            row.component_id, "SecondaryBody",
            {"role": "body", "fontSize": 14, "width": "matchParent",
             "items": [{"value": value, "maxLines": 2}]},
        )
        after_group = index + 1
        return leaves[:index] + [body] + leaves[after_group:]
    return None


def _wrap_complete_value_rows(
    leaves: list[ComponentRow], task: dict[str, Any], width: float, role: str,
) -> tuple[list[ComponentRow], bool]:
    output: list[ComponentRow] = []
    changed = False
    for row in leaves:
        eligible = row.component_type == "SecondaryBody" and row.props.get("role") == role
        allowed = {"role", "fontSize", "width", "columns", "items"}
        if not eligible or set(row.props) - allowed or row.props.get("width") != "matchParent":
            output.append(row)
            continue
        items = row.props.get("items")
        font = 12 if role == "metadata" else 14
        same_spec = row.props.get("fontSize", font) == font and row.props.get("columns", 1) == 1
        if not same_spec or not isinstance(items, list) or len(items) != 1:
            output.append(row)
            continue
        item = items[0]
        if not isinstance(item, dict) or set(item) - _ITEM_PROPS or item.get("maxLines", 1) != 1:
            output.append(row)
            continue
        value = small_card_display_text(item.get("value"), task)
        label = item.get("label", "")
        if value is None or not isinstance(label, str):
            output.append(row)
            continue
        if role == "body" and label:
            output.append(row)  # 独立label和值分占文字区，不用整区宽度替代原标签布局。
            continue
        text = label + value
        estimated = sum(font * (0.6 if ch.isascii() else 1) for ch in text)
        if "\n" in text or not width < estimated <= width * 2:
            output.append(row)
            continue
        props = copy.deepcopy(row.props)
        props["items"] = [{**item, "maxLines": 2}]
        output.append(ComponentRow(row.component_id, row.component_type, props))
        changed = True
    return output, changed


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
    validation_execution_context: ValidationExecutionContext | None = None,
) -> OuterRecompositionResult:
    """最多32个无模型候选，原校验与硬事实均闭合才替换；否则原样回退。"""
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
    context = {
        "task_spec": task_spec,
        "card_spec": card_spec,
        "protocol_profile": protocol_profile,
        "layout_scope": layout_scope,
    }
    execution_context = validation_execution_context or ValidationExecutionContext()
    source_context = execution_context.with_purpose("recomposition_source")
    original_errors = _validation_errors(
        source_dsl,
        {**context, "execution_context": source_context},
    )
    height_error = False
    width_error = False
    for message in original_errors:
        if ": vertical layout requires at least " in message:
            height_error = True
        elif ": text width overflow;" in message:
            width_error = True
        else:
            return unchanged
    width = _inner_width(root, protocol_profile)
    data = [row for row in rows if isinstance(row, DataRow)]
    pressure_task = _source_pressure_task(task_spec, data)
    pressure_ids: set[str] = set()
    metadata_wrapped = False
    body_wrapped = False
    if width is not None:
        for row in leaves:
            if _certain_label_pressure(row, pressure_task, width):
                pressure_ids.add(row.component_id)
        leaves, metadata_wrapped = _wrap_complete_value_rows(
            leaves, pressure_task, width, "metadata",
        )
        if width_error:
            leaves, body_wrapped = _wrap_complete_value_rows(leaves, pressure_task, width, "body")
    wrapped = metadata_wrapped or body_wrapped
    if not original_errors and not pressure_ids and not wrapped:
        return unchanged
    reasons = ("height_capacity",) if height_error else ()
    if width_error or body_wrapped:
        reasons += ("complete_text_width",)
    if pressure_ids:
        reasons += ("complete_label_width",)
    if metadata_wrapped:
        reasons += ("complete_metadata_width",)
    variants = [leaves]
    if width is not None:
        grouped = _paragraph(leaves, pressure_task, width)
        if grouped is None:
            grouped = _compact_existing_attribute_group(leaves, pressure_task, width)
        if grouped is not None:
            variants.append(grouped)
    used = set(row.component_id for row in rows if isinstance(row, ComponentRow))
    gaps = (6, 4, 2, 0) if leaves[-1].component_type == "PillButton" else (6,)
    attempted = 0
    for variant in variants:
        remaining_pressure = set()
        for row in variant:
            if row.component_id in pressure_ids and _reflow_items(row) is not None:
                remaining_pressure.add(row.component_id)
        for gap in gaps:
            for content_gap in (6, 4, 2, 0):
                candidate = _candidate(
                    root, variant, data, gap, content_gap, remaining_pressure, used,
                )
                if candidate is None:
                    continue
                attempted += 1
                candidate_context = execution_context.with_purpose(
                    "recomposition_candidate",
                    candidate_index=attempted,
                )
                validation_context = {
                    **context,
                    "execution_context": candidate_context,
                }
                if _validation_errors(candidate, validation_context):
                    continue
                if compact_plan_coverage_errors(candidate, compact_plan, task_spec):
                    continue
                return OuterRecompositionResult(candidate, reasons, attempted, True)
    return OuterRecompositionResult(source_dsl, reasons, attempted)
