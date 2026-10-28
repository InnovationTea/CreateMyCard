# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""重复按钮的有限无损候选；固定槽重组选型继续交原模型修复。"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from services.card_validation.compact_validation.semantic.action_display import (
    ActionDisplayTree,
    read_action_display_tree,
    strict_action_identity,
)
from services.compact_dsl_a2ui_converter import DataRow
from services.compact_duplicate_display import DuplicateDisplayCandidate

_MAX_CANDIDATES = 8
_REGION_COLLAPSE = {
    "title-content-action": (3, "title-content"),
    "title-hero-support-action": (4, "title-hero-support"),
    "title-two-ratios": (4, "title-two-ratios"),
}
_OWNERSHIP_INSTRUCTION = (
    "同一完整 onClick 执行动作只保留一个完整按钮入口；逐项核对 actionId 与 occurrences，"
    "保留原事件数组、参数类型和值、动态绑定、动作标签及对象归属。"
    "不同参数、开关值、列表项上下文和父子点击不能按文案或 actionId 合并。"
    "fixedRequiredSlot 为 true 的重复入口不能直接删槽、清空 onClick、虚构信息或复制正文填槽；"
    "只在 repairStrategy 允许范围内重新选择必要父布局并重新分配已有真实信息，完整满足角色合同。"
    "非固定槽只移除已确认重复的可选动作角色并收敛合法 variant，其他事实、字号与动作保持。"
)


@dataclass(frozen=True)
class _ActionRemoval:
    component_id: str
    parent_id: str
    variant: str


def duplicate_action_feedback(duplicates: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """附准确父角色与所有权文字，不提供恢复 DSL 或新增布局。"""
    result = []
    for duplicate in duplicates:
        feedback = copy.deepcopy(duplicate)
        feedback["ownershipInstruction"] = _OWNERSHIP_INSTRUCTION
        required = []
        for occurrence in duplicate.get("occurrences", []):
            if occurrence.get("fixedRequiredSlot") is True:
                required.append(copy.deepcopy(occurrence))
        feedback["requiredActionPositions"] = required
        result.append(feedback)
    return result


def _verified_occurrences(
    tree: ActionDisplayTree, duplicate: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    if not isinstance(duplicate.get("actionId"), str):
        return ()
    fact_index = duplicate.get("factIndex")
    if type(fact_index) is not int or fact_index < 0:
        return ()
    expected_count = duplicate.get("expectedVisibleCount")
    if type(expected_count) is not int or expected_count != 1:
        return ()
    supplied = duplicate.get("occurrences")
    if not isinstance(supplied, list) or len(supplied) < 2:
        return ()
    actual_count = duplicate.get("actualVisibleCount")
    if type(actual_count) is not int or actual_count != len(supplied):
        return ()
    actual_by_id = {}
    for occurrence in tree.occurrences:
        actual_by_id[occurrence.get("componentId")] = occurrence
    verified = []
    seen = set()
    identities = set()
    for occurrence in supplied:
        if not isinstance(occurrence, dict):
            return ()
        identifier = occurrence.get("componentId")
        if not isinstance(identifier, str) or identifier in seen:
            return ()
        actual = actual_by_id.get(identifier)
        if actual is None or strict_action_identity(actual) != strict_action_identity(occurrence):
            return ()
        identity = strict_action_identity(actual.get("onClick"))
        if identity is None:
            return ()
        identities.add(identity)
        seen.add(identifier)
        verified.append(actual)
    if len(identities) != 1:
        return ()
    identity = next(iter(identities))
    complete_ids = set()
    for occurrence in tree.occurrences:
        if strict_action_identity(occurrence.get("onClick")) == identity:
            complete_ids.add(occurrence.get("componentId"))
    if complete_ids != seen:
        return ()
    return tuple(verified)


def _tail_removal(tree: ActionDisplayTree, identifier: str) -> _ActionRemoval | None:
    result = None
    parent_id = tree.parents.get(identifier)
    parent = tree.nodes.get(parent_id) if parent_id is not None else None
    button = tree.nodes.get(identifier)
    if parent is None or button is None:
        return result
    if parent.component_type != "Region" or button.component_type != "PillButton":
        return result
    variant = parent.props.get("variant")
    collapse = _REGION_COLLAPSE.get(variant) if isinstance(variant, str) else None
    if collapse is None or len(parent.children) != collapse[0]:
        return result
    if parent.children[-1] == identifier:
        result = _ActionRemoval(identifier, parent.component_id, collapse[1])
    return result


def _content_signature(tree: ActionDisplayTree, identifier: str) -> str | None:
    node = tree.nodes.get(identifier)
    if node is None or node.props.get("onClick"):
        return None
    children = node.children
    props = copy.deepcopy(node.props)
    if node.component_type == "Region" and children:
        removal = _tail_removal(tree, children[-1])
        if removal is not None:
            children = children[:-1]
            props["variant"] = removal.variant
    signatures = []
    for child_id in children:
        signature = _content_signature(tree, child_id)
        if signature is None:
            return None
        signatures.append(signature)
    return strict_action_identity([node.component_type, props, signatures])


def _same_owner(tree: ActionDisplayTree, first: str, second: str) -> bool:
    first_parent = tree.parents.get(first)
    second_parent = tree.parents.get(second)
    if first_parent is None or second_parent is None:
        return False
    if first_parent == second_parent:
        return True
    first_owner = tree.parents.get(first_parent)
    if first_owner is None or first_owner != tree.parents.get(second_parent):
        return False
    # 同一直接父节点且完整正文语义相同才证明同属；不按路径前缀猜不同对象。
    first_signature = _content_signature(tree, first_parent)
    second_signature = _content_signature(tree, second_parent)
    return first_signature is not None and first_signature == second_signature


def _removal_options(
    tree: ActionDisplayTree, duplicate: dict[str, Any],
) -> tuple[tuple[_ActionRemoval, ...], ...]:
    occurrences = _verified_occurrences(tree, duplicate)
    if not occurrences:
        return ()
    identifiers = []
    signatures = set()
    for occurrence in occurrences:
        identifier = occurrence.get("componentId")
        button = tree.nodes.get(identifier)
        if button is None or button.component_type != "PillButton":
            return ()
        handlers = button.props.get("onClick")
        if not isinstance(handlers, list) or len(handlers) != 1:
            return ()
        signature = strict_action_identity(button.props)
        if signature is None:
            return ()
        identifiers.append(identifier)
        signatures.add(signature)
    if len(signatures) != 1:
        return ()
    options = []
    for keeper in identifiers:
        removals = []
        for identifier in identifiers:
            if identifier == keeper:
                continue
            removal = _tail_removal(tree, identifier)
            if removal is None or not _same_owner(tree, identifier, keeper):
                break
            removals.append(removal)
        if len(removals) == len(identifiers) - 1:
            options.append(tuple(removals))
    return tuple(options)


def _apply_removals(
    tree: ActionDisplayTree, removals: tuple[_ActionRemoval, ...],
) -> DuplicateDisplayCandidate | None:
    changes = {}
    removed = set()
    for removal in removals:
        if removal.parent_id in changes:
            return None
        changes[removal.parent_id] = removal
        removed.add(removal.component_id)
    values = []
    descriptions = []
    for row in tree.rows:
        if isinstance(row, DataRow):
            values.append([row.path, row.value])
            continue
        if row.component_id in removed:
            descriptions.append(f"{row.component_id}.onClick")
            continue
        props = copy.deepcopy(row.props)
        children = row.children
        change = changes.get(row.component_id)
        if change is not None:
            props["variant"] = change.variant
            children = children[:-1]
        value = [row.component_id, row.component_type, props]
        if children:
            value.append(list(children))
        values.append(value)
    source = "\n".join(json.dumps(value, ensure_ascii=False) for value in values)
    return DuplicateDisplayCandidate(source, tuple(descriptions))


def duplicate_action_candidates(
    source_dsl: str, duplicates: tuple[dict[str, Any], ...],
) -> tuple[DuplicateDisplayCandidate, ...]:
    """复核原树和诊断，只去除同属且完全等价的可选尾部动作，最多八个候选。"""
    if not duplicates:
        return ()
    tree = read_action_display_tree(source_dsl)
    if tree is None:
        return ()
    combinations: list[tuple[_ActionRemoval, ...]] = [()]
    for duplicate in duplicates:
        options = _removal_options(tree, duplicate)
        if not options:
            return ()
        combined = []
        for previous in combinations:
            for option in options:
                combined.append((*previous, *option))
                if len(combined) == _MAX_CANDIDATES:
                    break
            if len(combined) == _MAX_CANDIDATES:
                break
        combinations = combined
    candidates = []
    seen = set()
    for removals in combinations:
        candidate = _apply_removals(tree, removals)
        if candidate is not None and candidate.source_dsl not in seen:
            seen.add(candidate.source_dsl)
            candidates.append(candidate)
    return tuple(candidates)
