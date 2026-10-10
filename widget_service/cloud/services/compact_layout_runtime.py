# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Load and evaluate versioned Compact layout contracts without rewriting DSL."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from services.compact_component_runtime import (
    CompactComponentRuntimeError,
    component_visual_recipe,
)
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_region_layout import reference_region_boxes

LAYOUT_CONTRACT_VERSION = "layout-contracts-v1"
_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "protocol_profiles"
    / "design-compact-dsl-fusion"
    / "runtime"
    / "layout-contracts-v1.json"
)
_EVENT_POLICIES = frozenset({"allow", "forbid", "forbid-subtree", "require"})


class CompactLayoutRuntimeError(ValueError):
    """Raised when a layout contract is malformed or the DSL matches no layout."""


@dataclass(frozen=True)
class CompactLayoutMatch:
    """The formal layout selected by deterministic contract matching."""

    layout_id: str
    contract_version: str = LAYOUT_CONTRACT_VERSION


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompactLayoutRuntimeError(
            f"Unable to load Compact layout contract: {_CONTRACT_PATH}"
        ) from exc
    _validate_contract(payload)
    return payload


def load_layout_contract() -> dict[str, Any]:
    """Return an isolated copy of the complete layout contract."""
    return copy.deepcopy(_load_contract())


def layout_ids_for_size(size: str) -> tuple[str, ...]:
    """Return all formal layout IDs registered for one widget size."""
    layouts = _load_contract().get("layouts")
    if not isinstance(layouts, dict):
        return ()
    identifiers: list[str] = []
    for layout_id, layout in layouts.items():
        if not isinstance(layout_id, str) or not isinstance(layout, dict):
            continue
        if layout.get("size") == size:
            identifiers.append(layout_id)
    return tuple(identifiers)


def allowed_layout_ids(size: str, layout_scope: str) -> tuple[str, ...]:
    """Resolve a fixed layout ID or an adaptive scope to formal layout IDs."""
    contract = _load_contract()
    layouts = contract.get("layouts")
    if not isinstance(layouts, dict):
        raise CompactLayoutRuntimeError("Compact layout contract has no layouts.")
    fixed = layouts.get(layout_scope)
    if isinstance(fixed, dict):
        if fixed.get("size") != size:
            raise CompactLayoutRuntimeError(
                f"Layout {layout_scope} is not registered for size {size}."
            )
        return (layout_scope,)

    scopes = contract.get("scopes")
    identifiers = scopes.get(layout_scope) if isinstance(scopes, dict) else None
    if not isinstance(identifiers, list) or not identifiers:
        raise CompactLayoutRuntimeError(f"Unknown Compact layout scope: {layout_scope}.")
    resolved: list[str] = []
    for layout_id in identifiers:
        layout = layouts.get(layout_id) if isinstance(layout_id, str) else None
        if not isinstance(layout, dict) or layout.get("size") != size:
            raise CompactLayoutRuntimeError(
                f"Layout scope {layout_scope} contains an invalid layout for size {size}."
            )
        resolved.append(layout_id)
    return tuple(resolved)


def match_compact_layout(
    components: list[ComponentRow],
    *,
    size: str,
    layout_scope: str,
) -> CompactLayoutMatch:
    """Match raw Compact rows to one formal layout without changing their geometry."""
    components_by_id = _reference_components(components, size=size)
    root = components_by_id.get("root")
    if root is None:
        raise CompactLayoutRuntimeError("Compact layout requires a root component.")

    contract = _load_contract()
    layouts = contract.get("layouts")
    if not isinstance(layouts, dict):
        raise CompactLayoutRuntimeError("Compact layout contract has no layouts.")

    closest: tuple[int, str, list[str]] | None = None
    closest_rank: tuple[int, int, int] | None = None
    alternatives: list[str] = []
    for layout_id in allowed_layout_ids(size, layout_scope):
        layout = layouts.get(layout_id)
        if not isinstance(layout, dict):
            continue
        patterns = layout.get("patterns")
        if not isinstance(patterns, list):
            continue
        best_variant: tuple[tuple[int, int, int], int, list[str]] | None = None
        action_errors = _action_count_mismatches(layout, components)
        for pattern_index, pattern in enumerate(patterns):
            mismatches = _pattern_mismatches(
                pattern,
                root,
                components_by_id,
                size=size,
            )
            mismatches.extend(action_errors)
            if not mismatches:
                return CompactLayoutMatch(layout_id=layout_id)
            root_errors: list[str] = []
            for rule in pattern.get("rules", []):
                if rule.get("path") == []:
                    root_errors.extend(_rule_mismatches(rule, root, components_by_id, size=size))
            rank = (len(action_errors), len(root_errors), len(mismatches))
            if best_variant is None or rank < best_variant[0]:
                best_variant = (rank, pattern_index + 1, mismatches)
            candidate = (len(mismatches), layout_id, mismatches)
            if closest_rank is None or rank < closest_rank:
                closest = candidate
                closest_rank = rank
        if best_variant is not None:
            alternatives.append(
                f"{layout_id} variant {best_variant[1]}: {'; '.join(best_variant[2])}"
            )

    allowed = ", ".join(allowed_layout_ids(size, layout_scope))
    detail = "layout structure does not match any registered pattern"
    if closest is not None:
        detail = f"closest {closest[1]}: {'; '.join(closest[2])}"
    raise CompactLayoutRuntimeError(
        f"Compact layout does not match scope {layout_scope} ({allowed}): {detail}. "
        f"Alternatives (choose one complete variant): {' | '.join(alternatives)}."
    )


def adaptive_slot_ids(components: list[ComponentRow], *, size: str) -> frozenset[str]:
    """读取已匹配布局的区域槽身份，区分动作背板与固定高度文字按钮。"""
    by_id = _reference_components(components, size=size)
    root = by_id.get("root")
    if root is None:
        return frozenset()
    layouts = _load_contract().get("layouts", {})
    for layout in layouts.values():
        if layout.get("size") != size:
            continue
        for pattern in layout.get("patterns", []):
            if _pattern_mismatches(pattern, root, by_id, size=size):
                continue
            if _action_count_mismatches(layout, components):
                continue
            slots: set[str] = set()
            for rule in pattern.get("rules", []):
                if not isinstance(rule.get("slotSize"), dict):
                    continue
                component = _component_at_path(root, by_id, rule.get("path"))
                if component is not None:
                    slots.add(component.component_id)
            return frozenset(slots)
    return frozenset()


def _reference_components(
    components: list[ComponentRow], *, size: str
) -> dict[str, ComponentRow]:
    """匹配时求解显式权重，不将参考数值写回模型输入或渲染产物。"""
    if size not in {"2x2", "2x4"}:
        return {component.component_id: component for component in components}
    nodes: list[dict[str, Any]] = []
    parent_types: dict[str, str] = {}
    for component in components:
        for child_id in component.children:
            parent_types[child_id] = component.component_type
    for component in components:
        styles = dict(_component_root_styles(component, size=size) or {})
        # 与高阶组件展开的缺省外部放置一致：Row 中未指定宽度的填充组件等权分配。
        row_fill = parent_types.get(component.component_id) == "Row"
        if row_fill and styles.get("width") == "matchParent" and "width" not in component.props:
            styles["layoutWeight"] = 1
        styles.update(component.props)
        nodes.append({
            "id": component.component_id,
            "component": component.component_type,
            "styles": styles,
            "children": component.children,
        })
    boxes = reference_region_boxes(nodes, size=size)
    resolved: dict[str, ComponentRow] = {}
    for component in components:
        props = dict(component.props)
        box = boxes.get(component.component_id)
        # 仅供本次只读匹配使用；覆盖同名输入，不能由模型伪造参考尺寸。
        reference_dimensions: dict[str, float] = {}
        if box is not None:
            for axis in ("width", "height"):
                length = box.axis(axis)
                if length is not None:
                    reference_dimensions[axis] = length
        props["_referenceDimensions"] = reference_dimensions
        if box is not None and "layoutWeight" in props:
            for axis in ("width", "height"):
                length = box.axis(axis)
                if axis not in props and length is not None:
                    props[axis] = length
        resolved[component.component_id] = ComponentRow(
            component.component_id, component.component_type, props, component.children
        )
    return resolved


def _pattern_mismatches(
    pattern: Any,
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    *,
    size: str,
) -> list[str]:
    if not isinstance(pattern, dict):
        return ["pattern must be an object"]
    rules = pattern.get("rules")
    if not isinstance(rules, list):
        return ["pattern.rules must be an array"]
    mismatches: list[str] = []
    for rule in rules:
        mismatches.extend(
            _rule_mismatches(
                rule,
                root,
                components_by_id,
                size=size,
            )
        )
    return mismatches


def _rule_mismatches(
    rule: Any,
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    *,
    size: str,
) -> list[str]:
    if not isinstance(rule, dict):
        return ["layout rule must be an object"]
    path = rule.get("path")
    component = _component_at_path(root, components_by_id, path)
    path_label = _path_label(path)
    if component is None:
        return [f"slot {path_label} is missing"]

    mismatches: list[str] = []
    types = rule.get("types")
    if isinstance(types, list) and component.component_type not in types:
        mismatches.append(
            f"slot {path_label} must use {'/'.join(types)}, got {component.component_type}"
        )

    props = rule.get("props")
    if isinstance(props, dict):
        for name, expected in props.items():
            actual = component.props.get(name)
            if actual == "matchParent" and isinstance(expected, (int, float)):
                actual = component.props.get("_referenceDimensions", {}).get(name)
            if actual != expected:
                mismatches.append(
                    f"slot {path_label}.{name} must be {expected!r}, got {actual!r}"
                )

    slot_size = rule.get("slotSize")
    if isinstance(slot_size, dict):
        mismatches.extend(
            _slot_size_mismatches(
                component,
                slot_size,
                size=size,
                path_label=path_label,
            )
        )

    child_count = len(component.children)
    expected_count = rule.get("childCount")
    minimum = rule.get("childCountMin")
    maximum = rule.get("childCountMax")
    if isinstance(expected_count, int) and child_count != expected_count:
        mismatches.append(
            f"slot {path_label} must have {expected_count} children, got {child_count}"
        )
    if isinstance(minimum, int) and child_count < minimum:
        mismatches.append(
            f"slot {path_label} must have at least {minimum} children, got {child_count}"
        )
    if isinstance(maximum, int) and child_count > maximum:
        mismatches.append(
            f"slot {path_label} must have at most {maximum} children, got {child_count}"
        )

    event_policy = rule.get("eventPolicy")
    if event_policy == "forbid" and _has_event(component):
        mismatches.append(f"slot {path_label} must not bind an event")
    elif event_policy == "require" and not _has_event(component):
        mismatches.append(f"slot {path_label} must bind an event")
    elif event_policy == "forbid-subtree":
        event_count = _subtree_event_count(component, components_by_id, set())
        if event_count:
            mismatches.append(f"slot {path_label} subtree must not bind events")
    return mismatches


def _slot_size_mismatches(
    component: ComponentRow,
    expected_size: dict[str, Any],
    *,
    size: str,
    path_label: str,
) -> list[str]:
    recipe_styles = _component_root_styles(component, size=size)
    mismatches: list[str] = []
    for dimension in ("width", "height"):
        expected = expected_size.get(dimension)
        if not isinstance(expected, (int, float)):
            continue
        actual = component.props.get(dimension)
        if actual is None and recipe_styles is not None:
            actual = recipe_styles.get(dimension)
        if actual == "matchParent":
            actual = component.props.get("_referenceDimensions", {}).get(dimension)
        if actual != expected:
            mismatches.append(
                f"slot {path_label}.{dimension} must resolve to {expected!r}, "
                f"got {actual!r}"
            )
    return mismatches


def _component_root_styles(
    component: ComponentRow,
    *,
    size: str,
) -> dict[str, Any] | None:
    try:
        recipe = component_visual_recipe(component.component_type, size=size)
    except CompactComponentRuntimeError:
        return None
    parts = recipe.get("parts")
    if not isinstance(parts, dict):
        return None
    part_name = "root"
    has_visual = component.props.get("icon") or component.props.get("visual")
    if component.component_type == "InfoBlock" and not has_visual:
        part_name = "rootNoVisual"
    part = parts.get(part_name)
    if not isinstance(part, dict):
        return None
    styles = part.get("styles")
    return styles if isinstance(styles, dict) else None


def _component_at_path(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    path: Any,
) -> ComponentRow | None:
    if not isinstance(path, list):
        return None
    current = root
    for index in path:
        if not isinstance(index, int) or index < 0 or index >= len(current.children):
            return None
        child_id = current.children[index]
        child = components_by_id.get(child_id)
        if child is None:
            return None
        current = child
    return current


def _action_count_mismatches(
    layout: dict[str, Any],
    components: list[ComponentRow],
) -> list[str]:
    action_range = layout.get("actionCount")
    if not isinstance(action_range, dict):
        return []
    minimum = action_range.get("min")
    maximum = action_range.get("max")
    count = sum(1 for component in components if _has_event(component))
    mismatches: list[str] = []
    if isinstance(minimum, int) and count < minimum:
        mismatches.append(f"layout requires at least {minimum} actions, got {count}")
    if isinstance(maximum, int) and count > maximum:
        mismatches.append(f"layout allows at most {maximum} actions, got {count}")
    return mismatches


def _has_event(component: ComponentRow) -> bool:
    on_click = component.props.get("onClick")
    return isinstance(on_click, list) and bool(on_click)


def _subtree_event_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    visiting: set[str],
) -> int:
    if component.component_id in visiting:
        return 0
    visiting.add(component.component_id)
    count = 1 if _has_event(component) else 0
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is not None:
            count += _subtree_event_count(child, components_by_id, visiting)
    visiting.remove(component.component_id)
    return count


def _path_label(path: Any) -> str:
    if not isinstance(path, list) or not path:
        return "root"
    return "root/" + "/".join(str(index) for index in path)


def _validate_contract(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("version") != LAYOUT_CONTRACT_VERSION:
        raise CompactLayoutRuntimeError(
            f"Compact layout contract must use version {LAYOUT_CONTRACT_VERSION}."
        )
    layouts = payload.get("layouts")
    if not isinstance(layouts, dict) or not layouts:
        raise CompactLayoutRuntimeError("Compact layout contract must declare layouts.")
    for layout_id, layout in layouts.items():
        _validate_layout(layout_id, layout)
    scopes = payload.get("scopes")
    if not isinstance(scopes, dict):
        raise CompactLayoutRuntimeError("Compact layout contract scopes must be an object.")
    for scope, identifiers in scopes.items():
        if not isinstance(scope, str) or not isinstance(identifiers, list):
            raise CompactLayoutRuntimeError("Compact layout scopes must be named arrays.")
        if not identifiers or any(identifier not in layouts for identifier in identifiers):
            raise CompactLayoutRuntimeError(
                f"Compact layout scope {scope} references an unknown layout."
            )


def _validate_layout(layout_id: Any, layout: Any) -> None:
    if not isinstance(layout_id, str) or not isinstance(layout, dict):
        raise CompactLayoutRuntimeError("Compact layouts must be named objects.")
    if layout.get("size") not in {"2x2", "2x4"}:
        raise CompactLayoutRuntimeError(f"Layout {layout_id} has an invalid size.")
    patterns = layout.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise CompactLayoutRuntimeError(f"Layout {layout_id} must declare patterns.")
    for pattern in patterns:
        rules = pattern.get("rules") if isinstance(pattern, dict) else None
        if not isinstance(rules, list) or not rules:
            raise CompactLayoutRuntimeError(
                f"Layout {layout_id} patterns must declare rules."
            )
        for rule in rules:
            _validate_rule(layout_id, rule)


def _validate_rule(layout_id: str, rule: Any) -> None:
    if not isinstance(rule, dict) or not isinstance(rule.get("path"), list):
        raise CompactLayoutRuntimeError(f"Layout {layout_id} has an invalid rule.")
    types = rule.get("types")
    if types is not None:
        valid_types = isinstance(types, list) and bool(types)
        if not valid_types or any(not isinstance(item, str) or not item for item in types):
            raise CompactLayoutRuntimeError(
                f"Layout {layout_id} rule types must be non-empty strings."
            )
    event_policy = rule.get("eventPolicy")
    if event_policy is not None and event_policy not in _EVENT_POLICIES:
        raise CompactLayoutRuntimeError(
            f"Layout {layout_id} has an invalid event policy."
        )
    slot_size = rule.get("slotSize")
    if slot_size is not None:
        valid_slot_size = isinstance(slot_size, dict) and bool(slot_size)
        if valid_slot_size:
            for name, value in slot_size.items():
                valid_name = name in {"width", "height"}
                valid_value = isinstance(value, (int, float)) and value > 0
                if not valid_name or not valid_value:
                    valid_slot_size = False
                    break
        if not valid_slot_size:
            raise CompactLayoutRuntimeError(
                f"Layout {layout_id} has an invalid slot size."
            )
