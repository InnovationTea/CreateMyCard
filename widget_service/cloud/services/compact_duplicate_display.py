# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""为已确认的重复展示构造无损候选；候选采用和完整复检由 pipeline 负责。"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    parse_compact_dsl_rows,
)

_MAX_CANDIDATES = 8
_ITEM_PROPERTY = re.compile(r"items\[(\d+)\]\.value\Z")
_TEXT_PROPERTIES = {
    "EmphasisText": frozenset({"mainText", "secondaryText"}),
    "InfoBlock": frozenset({"primaryText", "secondaryText"}),
}
_ITEM_MINIMUM = {"SecondaryBody": 1, "TableText": 2}
_OWNERSHIP_INSTRUCTION = (
    "按同一 dataId 选择唯一完整展示落点，保留已有对象标签、单位、绑定和动作；"
    "不得按相同样值去重，不得删除独有事实或造新事实填槽。"
    "若requiredDisplayPositions确认同一事实占据至少两个不同必填展示槽，"
    "不能清空属性、删除固定槽或放入占位文字；仅在repairStrategy允许范围内"
    "重新分配已有独立事实或调整必要父布局的合法组合，并补齐全部角色后完整复检。"
    "普通重复保持信息组内修复，不据此扩大为整卡重建。"
)


@dataclass(frozen=True)
class _DisplayPosition:
    component_id: str
    property_name: str
    item_index: int | None = None


@dataclass(frozen=True)
class DuplicateDisplayCandidate:
    source_dsl: str
    removed_positions: tuple[str, ...]


def duplicate_display_feedback(
    duplicate_facts: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    """补充所有权和必填槽边界，不改变原覆盖检查的判定和位置。"""
    result = []
    for fact in duplicate_facts:
        feedback = copy.deepcopy(fact)
        required = []
        for occurrence in fact.get("occurrences", []):
            component_type = occurrence.get("componentType")
            property_name = occurrence.get("property")
            is_main = component_type == "EmphasisText" and property_name == "mainText"
            info_properties = _TEXT_PROPERTIES.get("InfoBlock", frozenset())
            is_info = component_type == "InfoBlock" and property_name in info_properties
            if is_main or is_info:
                required.append(copy.deepcopy(occurrence))
        feedback["ownershipInstruction"] = _OWNERSHIP_INSTRUCTION
        feedback["requiredDisplayPositions"] = required
        result.append(feedback)
    return result


def duplicate_display_candidates(
    source_dsl: str, duplicate_facts: tuple[dict[str, Any], ...],
) -> tuple[DuplicateDisplayCandidate, ...]:
    """仅删除可选纯绑定文字或等价独立条目，不改树、样值、字号和其它属性。"""
    if not duplicate_facts:
        return ()
    try:
        rows = parse_compact_dsl_rows(source_dsl, expand_layouts=False)
    except CompactDslConversionError:
        return ()
    components = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            components[row.component_id] = row
    combinations: list[tuple[_DisplayPosition, ...]] = [()]
    for fact in duplicate_facts:
        options = _removal_options(fact, components)
        if not options:
            return ()
        combined = []
        for previous in combinations:
            for option in options:
                combined.append(tuple(dict.fromkeys((*previous, *option))))
                if len(combined) == _MAX_CANDIDATES:
                    break
            if len(combined) == _MAX_CANDIDATES:
                break
        combinations = combined
    candidates = []
    seen = set()
    for removals in combinations:
        candidate = _apply_removals(rows, removals)
        if candidate is None or candidate.source_dsl in seen:
            continue
        seen.add(candidate.source_dsl)
        candidates.append(candidate)
    return tuple(candidates)


def _removal_options(
    fact: dict[str, Any], components: dict[str, ComponentRow],
) -> list[tuple[_DisplayPosition, ...]]:
    occurrences = fact.get("occurrences")
    data_id = fact.get("dataId")
    if not isinstance(occurrences, list) or not isinstance(data_id, str):
        return []
    if fact.get("expectedVisibleCount") != 1 or len(occurrences) < 2:
        return []
    positions = []
    for occurrence in occurrences:
        position = _resolve_position(occurrence, data_id, components)
        if position is None:
            return []
        positions.append(position)
    options = []
    for keeper in positions:
        removals = []
        for position in positions:
            if position == keeper:
                continue
            if not _can_remove(position, keeper, components):
                break
            removals.append(position)
        else:
            if removals:
                options.append(tuple(removals))
    return options


def _resolve_position(
    occurrence: Any, data_id: str, components: dict[str, ComponentRow],
) -> _DisplayPosition | None:
    if not isinstance(occurrence, dict):
        return None
    component = components.get(occurrence.get("componentId"))
    if component is None or component.children or "onClick" in component.props:
        return None
    if component.component_type != occurrence.get("componentType"):
        return None
    if "visual" in component.props or "variant" in component.props:
        return None
    property_name = occurrence.get("property")
    if not isinstance(property_name, str):
        return None
    allowed = _TEXT_PROPERTIES.get(component.component_type, frozenset())
    if property_name in allowed:
        value = component.props.get(property_name)
        if value == {"path": data_id}:
            return _DisplayPosition(component.component_id, property_name)
        return None
    match = _ITEM_PROPERTY.fullmatch(property_name)
    if match is None or component.component_type not in _ITEM_MINIMUM:
        return None
    item_index = int(match.group(1))
    items = component.props.get("items")
    if not isinstance(items, list) or item_index >= len(items):
        return None
    item = items[item_index]
    if not isinstance(item, dict) or item.get("value") != {"path": data_id}:
        return None
    if not set(item) <= {"label", "value", "maxLines"}:
        return None
    label = item.get("label", "")
    if not isinstance(label, str) or "{{" in label or "${" in label:
        return None
    return _DisplayPosition(component.component_id, "items", item_index)


def _can_remove(
    position: _DisplayPosition, keeper: _DisplayPosition,
    components: dict[str, ComponentRow],
) -> bool:
    removed = components.get(position.component_id)
    retained = components.get(keeper.component_id)
    if removed is None or retained is None:
        return False
    if position.property_name == "secondaryText":
        if removed.component_type != "EmphasisText":
            return False
        value = removed.props.get("secondaryText")
        main_value = removed.props.get("mainText")
        if not _same_binding_object(value, main_value):
            return False
        # 静态主标题可能区分早晚、地点等对象；未知上下文不能仅因路径相同删除。
        text_properties = _TEXT_PROPERTIES.get(retained.component_type, frozenset())
        for name in text_properties:
            if name in retained.props:
                if not _same_binding_object(value, retained.props.get(name)):
                    return False
        return True
    if position.item_index is None or keeper.item_index is None:
        return False
    if removed.component_type != retained.component_type:
        return False
    # 不跨对象推断同名标签：条目去重只在同一正文组件内进行。
    if removed.component_id != retained.component_id:
        return False
    items = removed.props.get("items")
    if not isinstance(items, list):
        return False
    return items[position.item_index] == items[keeper.item_index]


def _same_binding_object(first: Any, second: Any) -> bool:
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    if set(first) != {"path"} or set(second) != {"path"}:
        return False
    first_path = first.get("path")
    second_path = second.get("path")
    if not isinstance(first_path, str) or not isinstance(second_path, str):
        return False
    return first_path.rpartition("/")[0] == second_path.rpartition("/")[0]


def _apply_removals(
    rows: tuple[ComponentRow | DataRow, ...], removals: tuple[_DisplayPosition, ...],
) -> DuplicateDisplayCandidate | None:
    values = []
    descriptions = []
    for row in rows:
        if isinstance(row, DataRow):
            values.append([row.path, row.value])
            continue
        props = copy.deepcopy(row.props)
        indexes = []
        for removal in removals:
            if removal.component_id != row.component_id:
                continue
            if removal.item_index is None:
                props.pop(removal.property_name, None)
                descriptions.append(f"{row.component_id}.{removal.property_name}")
            else:
                indexes.append(removal.item_index)
        if indexes:
            items = props.get("items")
            if not isinstance(items, list):
                return None
            for index in sorted(indexes, reverse=True):
                items.pop(index)
                descriptions.append(f"{row.component_id}.items[{index}]")
            minimum = _ITEM_MINIMUM.get(row.component_type)
            if minimum is None or len(items) < minimum:
                return None
        value = [row.component_id, row.component_type, props]
        if row.children:
            value.append(list(row.children))
        values.append(value)
    source = "\n".join(json.dumps(value, ensure_ascii=False) for value in values)
    return DuplicateDisplayCandidate(source, tuple(descriptions))
