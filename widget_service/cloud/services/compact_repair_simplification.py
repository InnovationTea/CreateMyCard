# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""容量修复的等价候选；保留事实和动作，接受判定仍由原校验链路负责。"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from typing import Any

from services.card_validation.base import expression_references
from services.compact_component_runtime import (
    CompactComponentRuntimeError,
    secondary_body_variant,
    visual_recipe_part,
)
from services.compact_dsl_a2ui_converter import ComponentRow, DataRow

_Rows = list[ComponentRow | DataRow]
_ACTION_PROPS = frozenset({"label", "labelLines", "onClick", "width", "layoutWeight", "flexShrink"})
_SUPPORTING_PROPS = frozenset(
    {
        "items",
        "role",
        "columns",
        "fontSize",
        "fontColor",
        "width",
        "layoutWeight",
        "flexShrink",
        "separator",
    }
)
_REPEATED_DISPLAY = re.compile(r"重复|两处|两次|两份|多处|各显示|分别显示|对比|左右两边")
_LARGE_ACTION = re.compile(r"CardButton|卡片按钮|卡片式按钮|大按钮|大块按钮", re.IGNORECASE)


def _rewrite(rows: _Rows, changed: dict[str, ComponentRow], removed: set[str]) -> _Rows:
    result = []
    for row in rows:
        if isinstance(row, ComponentRow):
            if row.component_id in removed:
                continue
            row = changed.get(row.component_id, row)
        result.append(row)
    return result


def _lightweight_actions(rows: _Rows) -> _Rows:
    changed = {}
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "CardButton":
            continue
        if row.children or set(row.props) - _ACTION_PROPS:
            continue
        if row.props.get("width") not in (None, "matchParent"):
            continue
        label = row.props.get("label")
        handlers = row.props.get("onClick")
        if not isinstance(label, str) or not isinstance(handlers, list):
            continue
        props = copy.deepcopy(row.props)
        props.pop("width", None)
        props.pop("labelLines", None)
        changed[row.component_id] = ComponentRow(row.component_id, "PillButton", props)
    return _rewrite(rows, changed, set())


def _vertical_details(rows: _Rows) -> _Rows:
    changed = {}
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "TextBlock":
            continue
        if "fontSize" in row.props or row.children:
            continue
        items = row.props.get("items")
        if not isinstance(items, list) or len(items) not in (2, 3):
            continue
        props = copy.deepcopy(row.props)
        kind = "TableText"
        if len(items) == 3:
            kind = "SecondaryBody"
            props["columns"] = 1
        changed[row.component_id] = ComponentRow(row.component_id, kind, props)
    return _rewrite(rows, changed, set())


def _supporting_items(row: ComponentRow) -> list[dict[str, Any]] | None:
    result = None
    if row.component_type != "SecondaryBody" or row.children:
        return result
    if set(row.props) - _SUPPORTING_PROPS:
        return result
    items = row.props.get("items")
    if isinstance(items, list) and items:
        if all(isinstance(item, dict) for item in items):
            result = items
    return result


def _supporting_font(row: ComponentRow, items: list[dict[str, Any]]) -> int:
    variant = secondary_body_variant(items, row.props.get("columns", 2))
    _, styles = visual_recipe_part("SecondaryBody", "text", size="2x4", variant=variant)
    font = styles.get("fontSize")
    if not isinstance(font, int) or isinstance(font, bool):
        raise CompactComponentRuntimeError("SecondaryBody.text must declare an integer fontSize.")
    return font


def _item_owner(items: list[dict[str, Any]], *, allow_root: bool = False) -> str | None:
    owners = set()
    for item in items:
        value = item.get("value")
        paths = []
        if isinstance(value, dict):
            path = value.get("path")
            if isinstance(path, str):
                paths.append(path)
        elif isinstance(value, str):
            paths = expression_references(value)
        if not paths:
            return None
        for path in paths:
            owner = path.rpartition("/")[0]
            is_data_owner = owner.startswith("/data/") or (allow_root and owner == "/data")
            if not is_data_owner:
                return None
            owners.add(owner)
    result = None
    if len(owners) == 1:
        result = next(iter(owners))
    return result


def _with_items(row: ComponentRow, items: list[dict[str, Any]]) -> ComponentRow:
    props = copy.deepcopy(row.props)
    props["items"] = copy.deepcopy(items)
    if "fontSize" in props:
        props["fontSize"] = _supporting_font(row, items)
    return ComponentRow(row.component_id, row.component_type, props)


def _deduplicate_supporting(rows: _Rows) -> _Rows:
    changed = {}
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        items = _supporting_items(row)
        if items is None:
            continue
        unique = []
        for item in items:
            if item not in unique or _item_owner([item], allow_root=True) is None:
                unique.append(item)
        if len(unique) != len(items):
            changed[row.component_id] = _with_items(row, unique)
    return _rewrite(rows, changed, set())


def _merge_pair(left: ComponentRow, right: ComponentRow) -> ComponentRow | None:
    left_items = _supporting_items(left)
    right_items = _supporting_items(right)
    if left_items is None or right_items is None:
        return None
    owner = _item_owner(left_items)
    if owner is None or owner != _item_owner(right_items):
        return None
    left_style = dict(left.props)
    right_style = dict(right.props)
    left_style.pop("items", None)
    right_style.pop("items", None)
    if left_style != right_style:
        return None
    items = [*left_items, *right_items]
    if len(items) > 4:
        return None
    merged_font = _supporting_font(left, items)
    original_font = max(_supporting_font(left, left_items), _supporting_font(right, right_items))
    if merged_font < original_font:
        return None
    return _with_items(left, items)


def _merge_supporting(rows: _Rows) -> _Rows:
    components = {}
    references: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        components[row.component_id] = row
        for child in row.children:
            references[child] = references.get(child, 0) + 1
    changed = {}
    removed: set[str] = set()
    for parent in components.values():
        if parent.component_id == "root" or parent.component_type != "Column":
            continue
        children = []
        index = 0
        while index < len(parent.children):
            left_id = parent.children[index]
            children.append(left_id)
            index += 1
            if index >= len(parent.children):
                continue
            right_id = parent.children[index]
            if references.get(left_id) != 1 or references.get(right_id) != 1:
                continue
            left = components.get(left_id)
            right = components.get(right_id)
            if left is None or right is None:
                continue
            merged = _merge_pair(left, right)
            if merged is not None:
                changed[left_id] = merged
                removed.add(right_id)
                index += 1
        if tuple(children) != parent.children:
            changed[parent.component_id] = ComponentRow(
                parent.component_id,
                parent.component_type,
                copy.deepcopy(parent.props),
                tuple(children),
            )
    return _rewrite(rows, changed, removed)


def simplification_variants(rows: _Rows, task_spec: dict[str, Any]) -> Iterator[tuple[str, _Rows]]:
    """返回少量确定性候选；原校验器检查覆盖、语义、实际 Recipe 与布局。"""
    query = task_spec.get("userQuery")
    large_action_requested = isinstance(query, str) and _LARGE_ACTION.search(query) is not None
    operations = []
    if not large_action_requested:
        lightened = _lightweight_actions(rows)
        for original, replacement in zip(rows, lightened, strict=True):
            if replacement == original or not isinstance(replacement, ComponentRow):
                continue
            candidate = _rewrite(rows, {replacement.component_id: replacement}, set())
            yield "lightweight_actions", candidate
        operations.append(("lightweight_actions", _lightweight_actions))
    operations.append(("merge_supporting", _merge_supporting))
    operations.append(("vertical_details", _vertical_details))
    repeats_requested = isinstance(query, str) and _REPEATED_DISPLAY.search(query) is not None
    if not repeats_requested:
        operations.append(("deduplicate_supporting", _deduplicate_supporting))
    seen = [rows]
    variants = []
    combined = rows
    reasons = []
    for reason, operation in operations:
        candidate = operation(rows)
        if candidate not in seen:
            seen.append(candidate)
            variants.append((reason, candidate))
        updated = operation(combined)
        if updated != combined:
            reasons.append(reason)
            combined = updated
    if combined != rows:
        yield "+".join(reasons), combined
    for reason, candidate in variants:
        if candidate != combined:
            yield reason, candidate
    yield "existing_components", rows
