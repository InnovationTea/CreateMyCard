# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""定位已接受动作的重复独立入口；候选匹配不替代严格执行身份比较。"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    parse_compact_dsl_rows,
)
from services.event_matching import event_handlers_match

_BUTTON_TYPES = frozenset({"PillButton", "CircleButton", "CardButton"})
_LIST_TYPES = frozenset({"List", "Grid", "ForEach", "Repeat", "RecordList", "SummaryList"})
_TEMPLATE_PROPERTIES = frozenset({"template", "itemTemplate", "dataSource", "forEach", "repeat"})
_REGION_ROLES = {
    "center": ("content",),
    "title-content": ("title", "content"),
    "title-hero-support": ("title", "hero", "support"),
    "title-content-action": ("title", "content", "action"),
    "title-hero-support-action": ("title", "hero", "support", "action"),
    "title-two-ratios": ("title", "left", "right", "action"),
}


@dataclass(frozen=True)
class ActionDisplayTree:
    rows: tuple[ComponentRow | DataRow, ...]
    nodes: dict[str, ComponentRow]
    parents: dict[str, str]
    occurrences: tuple[dict[str, Any], ...]


def strict_action_identity(value: Any) -> str | None:
    """保留数组顺序和 JSON 参数类型，不归一化开关值或动态表达式。"""
    result = None
    try:
        result = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        # 非 JSON 参数交原合同校验；诊断不抛出新异常遮蔽原始错误。
        result = None
    return result


def _list_context(node: ComponentRow) -> bool:
    return node.component_type in _LIST_TYPES or bool(_TEMPLATE_PROPERTIES.intersection(node.props))


def _parent_role(parent: ComponentRow, index: int) -> tuple[str, bool]:
    layout = parent.props.get("layout")
    if parent.component_type == "Layout":
        if layout == "W-content-side-slots" and index in (1, 2):
            role = "upper" if index == 1 else "lower"
            return f"{layout}.{role}", True
        if layout == "W-four-slots":
            return f"{layout}.slot[{index}]", True
        if layout == "S-content-dual-action" and index >= len(parent.children) - 2:
            return f"{layout}.action[{index}]", True
    if parent.component_type == "Region":
        variant = parent.props.get("variant")
        roles = _REGION_ROLES.get(variant, ()) if isinstance(variant, str) else ()
        if index < len(roles):
            return f"Region.{variant}.{roles[index]}", False
    return f"{parent.component_type}.children[{index}]", False


def _button_occurrence(
    node: ComponentRow, parent: ComponentRow, index: int,
) -> dict[str, Any] | None:
    result = None
    handlers = node.props.get("onClick")
    if node.component_type not in _BUTTON_TYPES or node.children:
        return result
    if not isinstance(handlers, list) or not handlers:
        return result
    if any(not isinstance(handler, dict) for handler in handlers):
        return result
    role, fixed = _parent_role(parent, index)
    result = {
        "componentId": node.component_id,
        "componentType": node.component_type,
        "property": "onClick",
        "parentId": parent.component_id,
        "parentRole": role,
        "fixedRequiredSlot": fixed,
        "onClick": copy.deepcopy(handlers),
    }
    return result


def _walk_actions(
    nodes: dict[str, ComponentRow],
) -> tuple[dict[str, str], tuple[dict[str, Any], ...]] | None:
    if "root" not in nodes:
        return None
    parents: dict[str, str] = {}
    occurrences = []
    seen: set[str] = set()
    pending = [("root", None, 0, False)]
    while pending:
        identifier, parent_id, index, blocked = pending.pop()
        node = nodes.get(identifier)
        if node is None or identifier in seen:
            return None
        seen.add(identifier)
        in_list = blocked or _list_context(node)
        if parent_id is not None:
            parent = nodes.get(parent_id)
            if parent is None:
                return None
            parents[identifier] = parent_id
            if not in_list:
                occurrence = _button_occurrence(node, parent, index)
                if occurrence is not None:
                    occurrences.append(occurrence)
        descendants_blocked = in_list or bool(node.props.get("onClick"))
        for child_index in range(len(node.children) - 1, -1, -1):
            child = node.children[child_index]
            pending.append((child, identifier, child_index, descendants_blocked))
    return parents, tuple(occurrences)


def read_action_display_tree(source_dsl: str) -> ActionDisplayTree | None:
    """只看原始可达树；多父引用或环没有安全的入口归属，交原树校验处理。"""
    try:
        rows = parse_compact_dsl_rows(
            source_dsl, expand_layouts=False, preserve_unreachable=True,
        )
    except CompactDslConversionError:
        return None
    nodes: dict[str, ComponentRow] = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            if row.component_id in nodes:
                return None
            nodes[row.component_id] = row
    walked = _walk_actions(nodes)
    result = None
    if walked is not None:
        parents, occurrences = walked
        result = ActionDisplayTree(rows, nodes, parents, occurrences)
    return result


def _accepted_actions(plan: Any, handlers: dict[str, Any]) -> dict[str, tuple[int, dict[str, Any]]]:
    facts = plan.get("info_required") if isinstance(plan, dict) else None
    if not isinstance(facts, list):
        return {}
    accepted: dict[str, tuple[int, dict[str, Any]]] = {}
    repeated = set()
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        action_id = fact.get("actionId")
        if not isinstance(action_id, str):
            continue
        handler = handlers.get(action_id)
        if not isinstance(handler, dict):
            continue
        if action_id in accepted:
            repeated.add(action_id)
        accepted[action_id] = (index, handler)
    for action_id in repeated:
        accepted.pop(action_id, None)
    return accepted


def _matching_action(
    occurrence: dict[str, Any], accepted: dict[str, tuple[int, dict[str, Any]]],
) -> str | None:
    matches = []
    for action_id, (_, expected) in accepted.items():
        handlers = occurrence.get("onClick", [])
        if any(event_handlers_match(handler, expected) for handler in handlers):
            matches.append(action_id)
    result = None
    if len(matches) == 1:
        result = matches[0]
    return result


def find_duplicate_actions(
    source_dsl: str, plan: dict[str, Any] | None,
    event_handlers_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """仅同一唯一 Plan Action 且完整执行数组相同的独立按钮构成重复。"""
    accepted = _accepted_actions(plan, event_handlers_by_id)
    if not accepted:
        return ()
    tree = read_action_display_tree(source_dsl)
    if tree is None:
        return ()
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for occurrence in tree.occurrences:
        action_id = _matching_action(occurrence, accepted)
        identity = strict_action_identity(occurrence.get("onClick"))
        if action_id is not None and identity is not None:
            groups.setdefault((action_id, identity), []).append(occurrence)
    result = []
    for (action_id, _), occurrences in groups.items():
        if len(occurrences) < 2:
            continue
        action = accepted.get(action_id)
        if action is None:
            continue
        result.append({
            "actionId": action_id,
            "factIndex": action[0],
            "expectedVisibleCount": 1,
            "actualVisibleCount": len(occurrences),
            "occurrences": copy.deepcopy(occurrences),
        })
    return tuple(result)
