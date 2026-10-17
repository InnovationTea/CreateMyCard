# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""横向固定内容预算；复用参考分区，仅报告可证明的宽度不足。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    emit_error,
)
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_region_layout import reference_region_boxes

_CONTAINERS = frozenset({"Row", "Column", "Stack"})
_UNMODELED = frozenset({"aspectRatio", "borderWidth"})
_ROOT_WIDTH_WARNING_LIMITS = {
    "2x2": 10.0,
    "2x4": 32.0,
}

_WEIGHTED_WIDTH_WARNING_LIMITS = {
    "2x2": 24.0,
    "2x4": 52.0,
}

_GAP_WIDTH_WARNING_LIMITS = {
    "2x2": 16.0,
    "2x4": 16.0,
}
_EPSILON = 1e-7


@dataclass(frozen=True)
class _WidthConstraints:
    minimum: float = 0.0
    maximum: float | None = None


def _number(value: Any) -> float | None:
    result: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and value >= 0:
            result = float(value)
    return result


def _inset(props: dict[str, Any], key: str) -> float | None:
    value = props.get(key, 0)
    result: float | None = None
    if isinstance(value, dict):
        left = _number(value.get("left", 0))
        right = _number(value.get("right", 0))
        if left is not None and right is not None:
            result = left + right
    else:
        scalar = _number(value)
        if scalar is not None:
            result = scalar * 2.0
    return result


def _width_constraints(props: dict[str, Any]) -> _WidthConstraints | None:
    """按端侧嵌套约束优先级读取宽度；高度约束不影响横向下界。"""
    nested = props.get("constraintSize", {})
    result: _WidthConstraints | None = None
    if not isinstance(nested, dict):
        return result
    raw_minimum = nested.get("minWidth", props.get("minWidth", 0.0))
    minimum = _number(raw_minimum)
    has_maximum = "maxWidth" in nested or "maxWidth" in props
    maximum = _number(nested.get("maxWidth", props.get("maxWidth")))
    if minimum is None or (has_maximum and maximum is None):
        return result
    if maximum is None or minimum <= maximum:
        result = _WidthConstraints(minimum, maximum)
    return result


def _uncertain_constraints(props: dict[str, Any]) -> bool:
    constraints = _width_constraints(props)
    if constraints is None:
        return True
    # 参考分区分配未实现上下限冻结再分配，不用它证明受约束的实际槽位。
    return constraints.minimum > 0.0 or constraints.maximum is not None


@dataclass
class _WidthBudget:
    minimum: float = 0.0
    compressible_gap: float = 0.0
    occupancy: list[dict[str, Any]] = field(default_factory=list)


def _children_budget(
    node: ComponentRow, by_id: dict[str, ComponentRow], trail: frozenset[str]
) -> _WidthBudget | None:
    result: _WidthBudget | None = _WidthBudget()
    widths: list[float] = []
    occupancy: list[dict[str, Any]] = []
    for child_id in node.children:
        child = by_id.get(child_id)
        if child is None:
            return None
        if child.props.get("visibility") == "none":
            continue
        width = _minimum_width(child, by_id, trail)
        margin = _inset(child.props, "margin")
        if width is None or margin is None:
            return None
        widths.append(width + margin)
        occupancy.append({"componentId": child_id, "minimumWidth": width, "margin": margin})
    gap = _number(node.props.get("itemMargin", node.props.get("space", 0)))
    if gap is None:
        result = None
    elif node.component_type == "Row":
        gaps = gap * max(0, len(widths) - 1)
        occupancy.append({"gaps": gaps})
        result = _WidthBudget(
            minimum=sum(widths) + gaps,
            compressible_gap=gaps,
            occupancy=occupancy,
        )
    else:
        result = _WidthBudget(
            minimum=max(widths, default=0.0),
            occupancy=occupancy,
        )
    return result


def _minimum_width(
    node: ComponentRow, by_id: dict[str, ComponentRow], trail: frozenset[str]
) -> float | None:
    result: float | None = None
    if node.component_id in trail or len(trail) >= 64:
        return result
    if any(key in node.props for key in _UNMODELED):
        return result
    constraints = _width_constraints(node.props)
    if constraints is None:
        return result
    padding = _inset(node.props, "padding")
    if padding is None:
        return result
    # 未知文字的宽度下界为零，不等于它实际没有宽度；不猜字体或绑定结果。
    result = padding
    if node.component_type in _CONTAINERS:
        budget = _children_budget(node, by_id, trail | {node.component_id})
        result = None if budget is None else budget.minimum + padding
    width = _number(node.props.get("width"))
    shrink = _number(node.props.get("flexShrink"))
    if width is not None and constraints.maximum is not None:
        width = min(width, constraints.maximum)
    if result is not None and shrink == 0.0 and width is not None:
        result = max(result, width)
    if result is not None:
        result = max(result, constraints.minimum)
    return result


def _reference_nodes(components: list[ComponentRow]) -> list[dict[str, Any]]:
    """只使用根可达且空间分配可建模的树，保留其它校验的非法树职责。"""
    by_id = {node.component_id: node for node in components}
    if len(by_id) != len(components):
        return []
    pending = ["root"]
    visited: set[str] = set()
    nodes: list[dict[str, Any]] = []
    while pending:
        identifier = pending.pop()
        node = by_id.get(identifier)
        if node is None or identifier in visited:
            return []
        visited.add(identifier)
        if node.props.get("visibility") == "none":
            continue
        children: list[str] = []
        for child_id in node.children:
            child = by_id.get(child_id)
            if child is None:
                return []
            if child.props.get("visibility") != "none":
                children.append(child_id)
        props = dict(node.props)
        if "itemMargin" not in props and "space" in props:
            props["itemMargin"] = props.get("space")
        nodes.append(
            {
                "id": identifier,
                "component": node.component_type,
                "styles": props,
                "children": children,
            }
        )
        pending.extend(children)
        if len(visited) > 512:
            return []
    return nodes


def _uncertain_intrinsic_width(
    node: ComponentRow, by_id: dict[str, ComponentRow], trail: frozenset[str]
) -> bool:
    if node.component_id in trail or len(trail) >= 64:
        return True
    if any(key in node.props for key in _UNMODELED):
        return True
    if _uncertain_constraints(node.props):
        return True
    # 明确宽度或等权分区的分配不依赖更深层的自然宽度。
    if "width" in node.props or (_number(node.props.get("layoutWeight")) or 0.0) > 0:
        return False
    for child_id in node.children:
        child = by_id.get(child_id)
        if child is None:
            return True
        if _uncertain_intrinsic_width(child, by_id, trail | {node.component_id}):
            return True
    return False


def _known_allocation(
    node: ComponentRow, by_id: dict[str, ComponentRow], parents: dict[str, str]
) -> bool:
    current: ComponentRow | None = node
    visited: set[str] = set()
    while current is not None:
        if current.component_id in visited:
            return False
        visited.add(current.component_id)
        if any(key in current.props for key in _UNMODELED):
            return False
        if _uncertain_constraints(current.props):
            return False
        parent_id = parents.get(current.component_id)
        parent = by_id.get(parent_id) if parent_id is not None else None
        if parent is not None and parent.component_type == "Row":
            for child_id in parent.children:
                sibling = by_id.get(child_id)
                if sibling is None:
                    return False
                if sibling.props.get("visibility") == "none":
                    continue
                if _uncertain_intrinsic_width(sibling, by_id, frozenset()):
                    return False
        current = parent
    return True


def _has_horizontal_weight_ancestor(
    node: ComponentRow,
    by_id: dict[str, ComponentRow],
    parents: dict[str, str],
) -> bool:
    """判断当前 Row 是否位于父 Row 分配的横向权重区域内。"""
    current: ComponentRow | None = node
    visited: set[str] = set()
    while current is not None:
        if current.component_id in visited:
            return False
        visited.add(current.component_id)

        parent_id = parents.get(current.component_id)
        parent = by_id.get(parent_id) if parent_id is not None else None
        layout_weight = _number(current.props.get("layoutWeight")) or 0.0
        is_horizontal_weight = (
            parent is not None and parent.component_type == "Row" and layout_weight > 0.0
        )
        if is_horizontal_weight:
            return True
        current = parent
    return False


def _non_blocking_width_overflow_reason(
    *,
    node: ComponentRow,
    by_id: dict[str, ComponentRow],
    parents: dict[str, str],
    size: Any,
    overflow: float,
    compressible_gap: float,
) -> str | None:
    """按可压缩间距、根布局和横向权重层级决定宽度溢出是否可降级。"""
    if not isinstance(size, str) or size not in {"2x2", "2x4"}:
        return None

    gap_limit = _GAP_WIDTH_WARNING_LIMITS[size]
    gap_can_absorb = overflow <= compressible_gap + _EPSILON
    if gap_can_absorb and overflow <= gap_limit + _EPSILON:
        return "compressible_item_margin"

    if node.component_id == "root":
        root_limit = _ROOT_WIDTH_WARNING_LIMITS[size]
        if overflow <= root_limit + _EPSILON:
            return "root_flexible_layout"
        return None

    if _has_horizontal_weight_ancestor(node, by_id, parents):
        weighted_limit = _WEIGHTED_WIDTH_WARNING_LIMITS[size]
        if overflow <= weighted_limit + _EPSILON:
            return "weighted_flexible_layout"

    return None


def _collect_horizontal_budget_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    errors: list[str],
    protocol_profile: dict[str, Any] | None = None,
    *,
    warnings: list[str] | None = None,
) -> None:
    size = card_spec.get("suggestSize") or task_spec.get("size")
    if not isinstance(size, str) or size not in {"2x2", "2x4"}:
        return
    nodes = _reference_nodes(components)
    if not nodes:
        return
    try:
        boxes = reference_region_boxes(nodes, size=size, profile=protocol_profile)
    except ValueError as exc:
        if str(exc) not in errors:
            errors.append(str(exc))
        return
    by_id = {node.component_id: node for node in components}
    parents: dict[str, str] = {}
    for node in components:
        for child_id in node.children:
            parents[child_id] = node.component_id
    for node in components:
        if node.component_type != "Row":
            continue
        box = boxes.get(node.component_id)
        padding = _inset(node.props, "padding")
        if box is None or box.width is None or padding is None:
            continue
        if not _known_allocation(node, by_id, parents):
            continue
        budget = _children_budget(node, by_id, frozenset({node.component_id}))
        available = max(0.0, box.width - padding)
        if budget is None or budget.minimum <= available + 1e-7:
            continue
        overflow = budget.minimum - available
        message = (
            f"component {node.component_id}: horizontal layout requires at least "
            f"{budget.minimum:g}vp within {available:g}vp; it overflows by {overflow:g}vp."
        )
        warning_reason = _non_blocking_width_overflow_reason(
            node=node,
            by_id=by_id,
            parents=parents,
            size=size,
            overflow=overflow,
            compressible_gap=budget.compressible_gap,
        )
        if warnings is not None and warning_reason is not None:
            warnings.append(
                "COMPACT_LAYOUT_WIDTH_OVERFLOW: "
                f"{message} Occupancy: {budget.occupancy}. "
                f"Fallback: {warning_reason}."
            )
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_WIDTH_OVERFLOW",
                validation_class="semantic",
                category="layout",
                message=message,
                legacy_message=message,
                expected={"maximumWidth": available, "preserveFixedContent": True},
                actual={
                    "minimumRequiredWidth": budget.minimum,
                    "overflow": overflow,
                    "occupancy": budget.occupancy,
                },
                evidence_source="expanded",
                component_id=node.component_id,
            ),
        )
