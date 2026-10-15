# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""校验 Plan 已冻结的素材分配与语义分区约束。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.constants import _EXPRESSION_PATTERN
from services.card_validation.compact_validation.syntax.expressions import (
    _collect_binding_context,
)
from services.compact_component_semantics import CORE_INFORMATION_COMPONENT_TYPES
from services.compact_dsl_a2ui_converter import ComponentRow

_BUTTON_COMPONENT_TYPES = frozenset({"PillButton", "CircleButton", "CardButton"})


def collect_plan_contract_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    compact_plan: dict[str, Any] | None,
    errors: list[str],
) -> None:
    """校验模型输出对 Plan 素材分配和语义分区的落实情况。"""
    _collect_title_icon_contract_errors(components, errors)
    _collect_title_button_icon_conflict_errors(components, errors)
    _collect_plan_asset_assignment_errors(components, task_spec, compact_plan, errors)
    _collect_anchor_support_errors(components, compact_plan, errors)


def _collect_title_icon_contract_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    """在运行时覆盖 SVG 颜色前保留标题显式输入的结构校验。"""
    bitmap_suffixes = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
    for component in components:
        if component.component_type != "SingleLineTitle":
            continue
        icon = component.props.get("icon")
        has_icon = isinstance(icon, str) and bool(icon.strip())
        if icon is not None and not has_icon:
            errors.append("SingleLineTitle.icon must be a non-empty static asset path.")
        if "fillColor" not in component.props:
            continue
        if not has_icon:
            errors.append("SingleLineTitle.fillColor requires icon.")
            continue
        fill_color = component.props.get("fillColor")
        valid_color = isinstance(fill_color, str) and bool(
            re.fullmatch(r"#[0-9A-Fa-f]{8}", fill_color)
        )
        if not valid_color:
            errors.append("SingleLineTitle.fillColor must use #AARRGGBB.")
            continue
        if icon.lower().endswith(bitmap_suffixes):
            errors.append("SingleLineTitle bitmap icon must not set fillColor.")


def collect_secondary_body_context_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    """阻止新生成的 SecondaryBody 独立承担一个语义分区。"""
    components_by_id = {component.component_id: component for component in components}
    parent_by_child: dict[str, str] = {}
    for parent in components:
        for child_id in parent.children:
            parent_by_child[child_id] = parent.component_id
    for component in components:
        if component.component_type != "SecondaryBody":
            continue
        current_id = component.component_id
        while True:
            parent_id = parent_by_child.get(current_id)
            parent = components_by_id.get(parent_id) if parent_id is not None else None
            if parent is None:
                errors.append(_isolated_secondary_body_error(component.component_id))
                break
            sibling_ids = [
                child_id for child_id in parent.children if child_id != current_id
            ]
            sibling_component_ids = _component_subtree_ids(
                sibling_ids,
                components_by_id,
            )
            has_core_sibling = False
            for sibling_id in sibling_component_ids:
                sibling = components_by_id.get(sibling_id)
                if sibling is None:
                    continue
                if sibling.component_type in CORE_INFORMATION_COMPONENT_TYPES:
                    has_core_sibling = True
                    break
            if has_core_sibling:
                break
            if len(parent.children) != 1:
                errors.append(_isolated_secondary_body_error(component.component_id))
                break
            current_id = parent.component_id


def _collect_title_button_icon_conflict_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    """按钮与标题竞争同一素材时保留按钮，要求模型修复标题。"""
    title_icons: dict[str, list[str]] = {}
    button_icons: dict[str, list[str]] = {}
    for component in components:
        icon = component.props.get("icon")
        if not isinstance(icon, str) or not icon.strip():
            continue
        if component.component_type == "SingleLineTitle":
            title_icons.setdefault(icon, []).append(component.component_id)
        elif component.component_type in _BUTTON_COMPONENT_TYPES:
            button_icons.setdefault(icon, []).append(component.component_id)

    for icon, title_ids in title_icons.items():
        conflicting_button_ids = button_icons.get(icon)
        if conflicting_button_ids is None:
            continue
        errors.append(
            f"SingleLineTitle components {title_ids} and button components "
            f"{conflicting_button_ids} reuse icon {icon!r}; keep the button icon and "
            "replace the title icon with another unused matching asset; remove it only "
            "when no alternative candidate exists."
        )


def _collect_plan_asset_assignment_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    compact_plan: dict[str, Any] | None,
    errors: list[str],
) -> None:
    """确保 DSL 落实 Plan 已接受的按钮优先、标题随后素材分配。"""
    if not isinstance(compact_plan, dict):
        return
    assignments = compact_plan.get("assetAssignments")
    if not isinstance(assignments, dict):
        return
    asset_sources = _asset_sources_by_id(task_spec)
    event_handlers = _event_handlers_by_id(task_spec)
    buttons = [
        component
        for component in components
        if component.component_type in _BUTTON_COMPONENT_TYPES
    ]
    action_assignments = assignments.get("actions")
    if isinstance(action_assignments, list):
        for assignment in action_assignments:
            if not isinstance(assignment, dict):
                continue
            action_id = assignment.get("actionId")
            if not isinstance(action_id, str):
                continue
            handler = event_handlers.get(action_id)
            if handler is None:
                continue
            matching_buttons = [
                button for button in buttons if _component_uses_handler(button, handler)
            ]
            if not matching_buttons:
                errors.append(
                    f"assetAssignments action {action_id!r} has no matching button component."
                )
                continue
            expected_source = asset_sources.get(assignment.get("assetId"))
            actual_icons = [button.props.get("icon") for button in matching_buttons]
            if expected_source is None:
                if any(isinstance(icon, str) and icon.strip() for icon in actual_icons):
                    errors.append(
                        f"button for action {action_id!r} must not use an icon because "
                        "its accepted Plan asset assignment is null."
                    )
                continue
            if expected_source not in actual_icons:
                errors.append(
                    f"button for action {action_id!r} must use Plan-assigned icon "
                    f"{expected_source!r}."
                )

    title_assignment = assignments.get("title")
    if not isinstance(title_assignment, dict):
        return
    _collect_title_asset_assignment_errors(components, asset_sources, title_assignment, errors)


def _collect_title_asset_assignment_errors(
    components: list[ComponentRow],
    asset_sources: dict[str, str],
    title_assignment: dict[str, Any],
    errors: list[str],
) -> None:
    """标题素材按实际消费校验，不推断分区，也不为装饰素材强制新增标题。"""
    titles = [
        component
        for component in components
        if component.component_type == "SingleLineTitle"
    ]
    expected_title_source = asset_sources.get(title_assignment.get("assetId"))
    if not titles:
        return
    matching_count = 0
    for title in titles:
        icon = title.props.get("icon")
        if not isinstance(icon, str) or not icon.strip():
            continue
        if expected_title_source is None:
            errors.append(
                f"SingleLineTitle {title.component_id!r} must not use an icon because "
                "its accepted Plan asset assignment is null."
            )
            continue
        if icon != expected_title_source:
            errors.append(
                f"SingleLineTitle {title.component_id!r} uses an unassigned icon {icon!r}; "
                f"the Plan-assigned title icon is {expected_title_source!r}."
            )
            continue
        matching_count += 1
    if expected_title_source is not None and matching_count != 1:
        errors.append(
            "SingleLineTitle components must use Plan-assigned title icon "
            f"{expected_title_source!r} exactly once; found {matching_count} uses."
        )


def _collect_anchor_support_errors(
    components: list[ComponentRow],
    compact_plan: dict[str, Any] | None,
    errors: list[str],
) -> None:
    """Anchor 左下必须落实独立事实，不能用无绑定标签占位。"""
    components_by_id = {component.component_id: component for component in components}
    parents = {
        child_id: component
        for component in components
        for child_id in component.children
    }
    plan_facts: list[dict[str, Any]] = []
    if isinstance(compact_plan, dict):
        candidate_facts = compact_plan.get("info_required")
        if isinstance(candidate_facts, list):
            plan_facts = [fact for fact in candidate_facts if isinstance(fact, dict)]

    support_plan_indexes = _anchor_support_plan_indexes(compact_plan)
    for action in components:
        if action.component_type != "CircleButton":
            continue
        action_slot = parents.get(action.component_id)
        bottom = parents.get(action_slot.component_id) if action_slot is not None else None
        if action_slot is None or bottom is None or bottom.component_type != "Row":
            continue
        support_roots = [
            child_id
            for child_id in bottom.children
            if child_id != action_slot.component_id
        ]
        support_ids = _component_subtree_ids(support_roots, components_by_id)
        if not support_ids:
            errors.append(
                "S-title-anchor requires a non-empty left support region with at least "
                "one independent fact; choose a text-action layout when support is empty."
            )
            continue
        action_ids = _component_subtree_ids([action_slot.component_id], components_by_id)
        support_paths, support_texts = _visible_subtree_evidence(
            support_ids,
            components_by_id,
        )
        outside_ids = set(components_by_id) - support_ids - action_ids
        outside_paths, outside_texts = _visible_subtree_evidence(
            outside_ids,
            components_by_id,
        )
        planned_paths, planned_texts = _planned_support_evidence(
            plan_facts,
            support_plan_indexes,
        )
        unique_paths = support_paths - outside_paths
        valid_dynamic_fact = (
            bool(unique_paths & planned_paths) if plan_facts else bool(unique_paths)
        )
        unique_texts = support_texts - outside_texts
        if valid_dynamic_fact or bool(unique_texts & planned_texts):
            continue
        errors.append(
            "S-title-anchor left support must realize an independent Plan fact that is "
            "not already consumed by the title or primary region. A static category "
            "label such as '当前天气' is not support information; choose a text-action "
            "layout instead."
        )


def _anchor_support_plan_indexes(
    compact_plan: dict[str, Any] | None,
) -> set[int] | None:
    if not isinstance(compact_plan, dict):
        return None
    composition = compact_plan.get("composition")
    if not isinstance(composition, dict):
        return None
    if composition.get("layout") != "S-title-anchor":
        return None
    indexes: set[int] = set()
    for region in composition.get("regions", []):
        if not isinstance(region, dict):
            continue
        if tuple(region.get("path", []))[:3] != (1, 1, 0):
            continue
        for group in region.get("groups", []):
            if not isinstance(group, dict):
                continue
            for index in group.get("factIndexes", []):
                if isinstance(index, int) and not isinstance(index, bool):
                    indexes.add(index)
    return indexes


def _planned_support_evidence(
    plan_facts: list[dict[str, Any]],
    support_plan_indexes: set[int] | None,
) -> tuple[set[str], set[str]]:
    planned_paths: set[str] = set()
    planned_texts: set[str] = set()
    for index, fact in enumerate(plan_facts):
        if support_plan_indexes is not None and index not in support_plan_indexes:
            continue
        data_id = fact.get("dataId")
        if isinstance(data_id, str):
            planned_paths.add(data_id)
        text = fact.get("text")
        if isinstance(text, str) and text.strip():
            planned_texts.add(_normalize_visible_text(text))
    return planned_paths, planned_texts


def _isolated_secondary_body_error(component_id: str) -> str:
    return (
        f"component {component_id}: SecondaryBody is auxiliary and cannot be the only "
        "information component in its semantic region; pair it with a core information "
        "component. Titles, buttons and other SecondaryBody instances do not count."
    )


def _component_subtree_ids(
    roots: list[str],
    components_by_id: dict[str, ComponentRow],
) -> set[str]:
    pending = list(roots)
    result: set[str] = set()
    while pending:
        component_id = pending.pop()
        if component_id in result:
            continue
        component = components_by_id.get(component_id)
        if component is None:
            continue
        result.add(component_id)
        pending.extend(component.children)
    return result


def _visible_subtree_evidence(
    component_ids: set[str],
    components_by_id: dict[str, ComponentRow],
) -> tuple[set[str], set[str]]:
    paths: list[str] = []
    texts: set[str] = set()
    for component_id in component_ids:
        component = components_by_id.get(component_id)
        if component is None:
            continue
        visible_props = {
            key: value for key, value in component.props.items() if key != "onClick"
        }
        _collect_binding_context(
            visible_props,
            f"component {component.component_id}.props",
            paths,
            [],
        )
        _collect_visible_text_values(visible_props, texts)
    return set(paths), texts


def _collect_visible_text_values(value: Any, texts: set[str]) -> None:
    if isinstance(value, str):
        if not _EXPRESSION_PATTERN.fullmatch(value.strip()):
            normalized = _normalize_visible_text(value)
            if normalized:
                texts.add(normalized)
        return
    if isinstance(value, list):
        for item in value:
            _collect_visible_text_values(item, texts)
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        if key in {"onClick", "icon", "src", "role"}:
            continue
        _collect_visible_text_values(item, texts)


def _normalize_visible_text(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _asset_sources_by_id(task_spec: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return result
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        source = candidate.get("src")
        if isinstance(identifier, str) and isinstance(source, str):
            result[identifier] = source
    return result


def _event_handlers_by_id(task_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return result
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        call = candidate.get("call")
        args = candidate.get("args")
        valid_identifier = isinstance(identifier, str)
        valid_handler = isinstance(call, str) and isinstance(args, dict)
        if valid_identifier and valid_handler:
            result[identifier] = {"call": call, "args": args}
    return result


def _component_uses_handler(component: ComponentRow, handler: dict[str, Any]) -> bool:
    on_click = component.props.get("onClick")
    return isinstance(on_click, list) and handler in on_click
