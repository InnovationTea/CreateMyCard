# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Translate provable reference-frame regions into native flexible A2UI layout."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

_CONTAINERS = frozenset({"Row", "Column", "Stack"})
_REFERENCE_SIZES = {"2x2": (150.0, 150.0), "2x4": (300.0, 150.0)}


@dataclass(frozen=True)
class _Frame:
    width: float | None
    height: float | None
    flexible_width: bool = False
    flexible_height: bool = False


def _number(value: Any) -> float | None:
    result: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and value >= 0:
            result = float(value)
    return result


def _dimension(value: Any, available: float | None) -> float | None:
    result = _number(value)
    if value in ("matchParent", "100%"):
        result = available
    return result


def _insets(styles: dict[str, Any], key: str, axis: str) -> float | None:
    raw = styles.get(key, 0)
    number = _number(raw)
    result: float | None = None
    if number is not None:
        result = number * 2
    elif isinstance(raw, dict):
        sides = ("left", "right") if axis == "width" else ("top", "bottom")
        first = _number(raw.get(sides[0], 0))
        second = _number(raw.get(sides[1], 0))
        if first is not None and second is not None:
            result = first + second
    return result


def _inner(frame: _Frame, styles: dict[str, Any], axis: str) -> float | None:
    dimension = getattr(frame, axis)
    padding = _insets(styles, "padding", axis)
    result: float | None = None
    if dimension is not None and padding is not None:
        result = max(0.0, dimension - padding)
    return result


def _equal(first: float | None, second: float | None) -> bool:
    if first is None or second is None:
        return False
    return abs(first - second) < 0.01


def _is_intrinsic(component: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> bool:
    kind = component.get("component")
    styles = component.get("styles", {})
    if kind == "Image" or kind == "Checkbox":
        return True
    if kind == "Progress":
        return styles.get("type") != "linear"
    if kind == "Stack":
        for child_id in component.get("children", []):
            child = nodes.get(child_id, {})
            if child.get("component") in {"Image", "Progress"}:
                return True
    return False


def _can_grow(component: dict[str, Any], axis: str) -> bool:
    kind = component.get("component")
    styles = component.get("styles", {})
    if axis == "width":
        return kind in _CONTAINERS or kind in {"Text", "Button", "Progress", "Divider"}
    height = _number(styles.get("height"))
    return kind in _CONTAINERS and height is not None and height > 36


def _main_axis(component: dict[str, Any]) -> str | None:
    result: str | None = None
    if component.get("component") == "Row":
        result = "width"
    elif component.get("component") == "Column":
        result = "height"
    return result


def _children(component: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for child_id in component.get("children", []):
        child = nodes.get(child_id)
        if child is not None:
            result.append(child)
    return result


def _allocation(
    parent: dict[str, Any], children: list[dict[str, Any]], available: float | None, axis: str
) -> dict[str, float]:
    """Resolve existing weights only when every non-weighted sibling has a known size."""
    result: dict[str, float] = {}
    gap = _number(parent.get("itemMargin", 0))
    if available is None or gap is None:
        return result
    remainder = available - gap * max(0, len(children) - 1)
    weights: dict[str, float] = {}
    for child in children:
        styles = child.get("styles", {})
        margin = _insets(styles, "margin", axis)
        if margin is None:
            return {}
        remainder -= margin
        weight = _number(styles.get("layoutWeight"))
        child_id = child.get("id")
        if weight is not None and weight > 0:
            weights[child_id] = weight
            continue
        dimension = _dimension(styles.get(axis), available)
        if dimension is None:
            return {}
        remainder -= dimension
    if remainder < 0 or not weights:
        return result
    total = sum(weights.values())
    for child_id, weight in weights.items():
        result[child_id] = remainder * weight / total
    return result


def _new_weights(
    parent: dict[str, Any],
    children: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    available: float | None,
    axis: str,
) -> dict[str, float]:
    """Only replace exact-fill partitions; preserve compact readouts and button contents."""
    result: dict[str, float] = {}
    parent_height = _number(parent.get("styles", {}).get("height"))
    capsule = parent.get("onClick") and parent_height is not None and parent_height <= 36
    if available is None or capsule:
        return result
    text_only = all(child.get("component") == "Text" for child in children)
    if axis == "width" and text_only and len(children) > 1:
        return result
    gap = _number(parent.get("itemMargin", 0))
    if gap is None:
        return result
    occupied = gap * max(0, len(children) - 1)
    for child in children:
        styles = child.get("styles", {})
        if styles.get("layoutWeight"):
            return {}
        dimension = _number(styles.get(axis))
        margin = _insets(styles, "margin", axis)
        if dimension is None or margin is None:
            return {}
        occupied += dimension + margin
        constrained = "constraintSize" in styles or "aspectRatio" in styles
        if constrained or _is_intrinsic(child, nodes):
            continue
        if dimension > 0 and _can_grow(child, axis):
            result[child.get("id")] = dimension
    if not _equal(occupied, available):
        return {}
    return result


class _RegionAdapter:
    def __init__(self, components: list[dict[str, Any]]) -> None:
        self.nodes = {component["id"]: component for component in components}
        self.output = copy.deepcopy(self.nodes)
        self.visited: set[str] = set()

    def visit(self, component_id: str, frame: _Frame) -> None:
        if component_id in self.visited:
            return
        self.visited.add(component_id)
        node = self.nodes.get(component_id)
        if node is None or node.get("component") not in _CONTAINERS:
            return
        if component_id == "template_root" or not isinstance(node.get("children", []), list):
            return
        styles = node.get("styles", {})
        if "constraintSize" in styles or "aspectRatio" in styles:
            return
        children = _children(node, self.nodes)
        axis = _main_axis(node)
        inner_width = _inner(frame, styles, "width")
        inner_height = _inner(frame, styles, "height")
        available = inner_width if axis == "width" else inner_height
        flexible = frame.flexible_width if axis == "width" else frame.flexible_height
        existing = _allocation(node, children, available, axis) if axis else {}
        weights = {}
        if axis and flexible:
            weights = _new_weights(node, children, self.nodes, available, axis)
        if axis and (frame.flexible_width or frame.flexible_height):
            self.output[component_id].setdefault("itemMargin", 0)
        for child in children:
            child_frame = self.adapt_child(
                child,
                frame,
                inner_width,
                inner_height,
                axis,
                existing,
                weights,
            )
            self.visit(child["id"], child_frame)

    def adapt_child(
        self,
        child: dict[str, Any],
        parent_frame: _Frame,
        inner_width: float | None,
        inner_height: float | None,
        axis: str | None,
        existing: dict[str, float],
        weights: dict[str, float],
    ) -> _Frame:
        child_id = child["id"]
        original = child.get("styles", {})
        target = self.output[child_id].setdefault("styles", {})
        dimensions = {
            "width": _dimension(original.get("width"), inner_width),
            "height": _dimension(original.get("height"), inner_height),
        }
        if axis and child_id in existing:
            dimensions[axis] = existing[child_id]
        flags = {"width": False, "height": False}
        protected = "constraintSize" in original or "aspectRatio" in original
        protected = protected or child_id == "template_root" or _is_intrinsic(child, self.nodes)
        for dimension, available in (("width", inner_width), ("height", inner_height)):
            parent_flexible = getattr(parent_frame, "flexible_" + dimension)
            if not parent_flexible or protected:
                continue
            if dimension == axis and child_id in weights:
                target.pop(dimension, None)
                target["layoutWeight"] = weights[child_id]
                flags[dimension] = True
            elif dimension == axis and (_number(original.get("layoutWeight")) or 0) > 0:
                flags[dimension] = True
            elif _equal(dimensions[dimension], available):
                margin = _insets(original, "margin", dimension)
                can_fill = dimension == "width" or child.get("component") in _CONTAINERS
                if can_fill and margin == 0:
                    target[dimension] = "matchParent"
                    flags[dimension] = True
        return _Frame(dimensions["width"], dimensions["height"], flags["width"], flags["height"])


def adapt_region_layout(components: list[dict[str, Any]], *, size: str) -> list[dict[str, Any]]:
    """Adapt general cards without touching facts, events, intrinsic visuals or template trees."""
    reference = _REFERENCE_SIZES.get(size)
    ids: set[str] = set()
    for component in components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or component_id in ids:
            return components
        ids.add(component_id)
    if reference is None or "root" not in ids or "template_root" in ids:
        return components
    adapter = _RegionAdapter(components)
    adapter.visit("root", _Frame(*reference, True, True))
    return list(adapter.output.values())
