# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：semantic.layout.geometry。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.constants import _NON_EMPTY_CONTAINER_TYPES
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    CompactDslValidationError,
    emit_error,
)
from services.card_validation.compact_validation.text import _format_vp, _non_negative_number
from services.compact_component_runtime import visual_recipe_part
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
)
from services.compact_reference_canvas import reference_dimension
from services.compact_region_layout import reference_region_boxes


def _collect_height_budget_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    errors: list[str],
    protocol_profile: dict[str, Any] | None = None,
) -> None:
    """Reject vertical layouts whose declared minimum height cannot fit."""
    components_by_id = {component.component_id: component for component in components}
    size = card_spec.get("suggestSize") or task_spec.get("size")
    boxes = {}
    if isinstance(size, str):
        nodes: list[dict[str, Any]] = []
        for row in components:
            styles = row.props
            if row.component_type == "SingleLineTitle":
                styles = {**row.props, "height": _single_line_title_height(row, size=size)}
            nodes.append(
                {
                    "id": row.component_id,
                    "component": row.component_type,
                    "styles": styles,
                    "children": list(row.children),
                }
            )
        try:
            boxes = reference_region_boxes(nodes, size=size, profile=protocol_profile)
        except ValueError as exc:
            errors.append(str(exc))
            return
    for component in components:
        if component.component_type != "Column":
            continue
        available_height = _component_available_height(
            component, task_spec, card_spec, protocol_profile
        )
        box = boxes.get(component.component_id)
        if box is not None and box.height is not None:
            available_height = max(0.0, box.height - _vertical_padding(component.props))
        if available_height is None:
            _collect_unresolved_height_error(component, components_by_id, errors)
            continue
        required_height = _column_children_minimum_height(
            component, components_by_id, measure_content_overflow=size == "2x2"
        )
        height_tolerance = 2.0 if size == "2x2" else 0.0
        if required_height <= available_height + height_tolerance + 1e-07:
            continue
        overflow = required_height - available_height
        breakdown = _column_height_breakdown(component, components_by_id)
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_HEIGHT_OVERFLOW",
                validation_class="semantic",
                category="layout",
                message=(
                    f"component {component.component_id}: vertical layout requires at "
                    f"least {_format_vp(required_height)}vp within "
                    f"{_format_vp(available_height)}vp; it overflows by "
                    f"{_format_vp(overflow)}vp. Occupancy: {breakdown}."
                ),
                legacy_message=(
                    f"component {component.component_id}: vertical layout requires at "
                    f"least {_format_vp(required_height)}vp within "
                    f"{_format_vp(available_height)}vp; it overflows by "
                    f"{_format_vp(overflow)}vp. Regroup facts or choose a layout with "
                    f"enough body space; preserve required text, actions, font sizes and "
                    f"fixed design heights. Weight, clipping, flex shrink and distributed "
                    f"alignment cannot eliminate content height. Occupancy: {breakdown}."
                ),
                expected={
                    "maximumHeight": available_height,
                    "heightTolerance": height_tolerance,
                    "preserveFixedDesignSizes": True,
                    "preserveRequiredTextAndActions": True,
                    "overflowConstraint": (
                        "不能依靠权重、裁剪、flex shrink 或分布式对齐消除内容高度超限。"
                    ),
                },
                actual={
                    "minimumRequiredHeight": required_height,
                    "overflow": overflow,
                    "occupancy": breakdown,
                },
                component_id=component.component_id,
            ),
        )


def _collect_unresolved_height_error(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    """无界列不能证明填满子项或纵向权重的实际高度分配成立。"""
    dependent_children: list[str] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        weighted = (_non_negative_number(child.props.get("layoutWeight")) or 0.0) > 0
        if child.props.get("height") == "matchParent" or weighted:
            dependent_children.append(child_id)
    if not dependent_children:
        return
    message = (
        f"component {component.component_id}: vertical layout has unresolved available height; "
        f"children {', '.join(dependent_children)} require parent height for matchParent or "
        "vertical weight allocation. Minimum content height does not prove that allocation fits."
    )
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_HEIGHT_UNRESOLVED",
            validation_class="semantic",
            category="layout",
            message=message,
            legacy_message=message,
            expected={"resolvedAvailableHeight": True},
            actual={"availableHeight": None, "dependentChildren": dependent_children},
            component_id=component.component_id,
        ),
    )


def _column_height_breakdown(
    component: ComponentRow, components_by_id: dict[str, ComponentRow]
) -> str:
    """反馈真实子树占用，不给模型推测或改变组件的设计量。"""
    parts: list[str] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        height = _minimum_outer_height(
            child,
            components_by_id,
            set(),
            height_weighted=bool(_non_negative_number(child.props.get("layoutWeight"))),
        )
        margin = _vertical_margin(child.props)
        parts.append(f"{child_id}={_format_vp(height)}vp+margin({_format_vp(margin)}vp)")
    gap = _vertical_gap(component, len(parts))
    parts.append(f"gaps={_format_vp(gap)}vp")
    return ", ".join(parts)


def _component_available_height(
    component: ComponentRow,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    protocol_profile: dict[str, Any] | None = None,
) -> float | None:
    outer_height = _component_outer_height(component, task_spec, card_spec, protocol_profile)
    if outer_height is None:
        return None
    return max(0.0, outer_height - _vertical_padding(component.props))


def _component_outer_height(
    component: ComponentRow,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    protocol_profile: dict[str, Any] | None = None,
) -> float | None:
    if component.component_id == "root":
        size = card_spec.get("suggestSize")
        if not isinstance(size, str) or not size:
            size = task_spec.get("size")
        if isinstance(size, str):
            try:
                return reference_dimension(size, "height", protocol_profile)
            except ValueError as exc:
                raise CompactDslValidationError([str(exc)]) from exc
    return _non_negative_number(component.props.get("height"))


def _column_children_minimum_height(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    *,
    measure_content_overflow: bool = False,
) -> float:
    child_heights: list[float] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        child_height = _minimum_outer_height(
            child,
            components_by_id,
            set(),
            height_weighted=bool(_non_negative_number(child.props.get("layoutWeight"))),
            measure_content_overflow=measure_content_overflow,
        )
        child_heights.append(child_height + _vertical_margin(child.props))

    gap = _vertical_gap(component, len(child_heights))
    return sum(child_heights) + gap


def _single_line_title_height(component: ComponentRow, *, size: str | None = None) -> float:
    """标题预占与实际展开共用视觉合同，不维护另一份固定高度。"""
    variant = "withIcon" if component.props.get("icon") else None
    _, styles = visual_recipe_part("SingleLineTitle", "root", size=size, variant=variant)
    height = _non_negative_number(styles.get("height"))
    if height is None:
        raise CompactDslValidationError(["SingleLineTitle Recipe must declare a fixed height."])
    return height


def _minimum_outer_height(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    visiting: set[str],
    *,
    height_weighted: bool = False,
    measure_content_overflow: bool = False,
) -> float:
    if component.component_type == "SingleLineTitle":
        return _single_line_title_height(component)
    constraints = component.props.get("constraintSize")
    minimum = constraints.get("minHeight") if isinstance(constraints, dict) else None
    minimum_height = _non_negative_number(minimum) or 0.0
    explicit_height = _non_negative_number(component.props.get("height"))
    is_container = component.component_type in _NON_EMPTY_CONTAINER_TYPES
    if explicit_height is not None and not (
        is_container and (height_weighted or measure_content_overflow)
    ):
        return max(minimum_height, explicit_height)
    if component.component_type not in _NON_EMPTY_CONTAINER_TYPES:
        return minimum_height
    if component.component_id in visiting:
        return 0.0

    visiting.add(component.component_id)
    child_heights: list[float] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        child_height = _minimum_outer_height(
            child,
            components_by_id,
            visiting,
            height_weighted=(
                component.component_type == "Column"
                and bool(_non_negative_number(child.props.get("layoutWeight")))
            ),
            measure_content_overflow=measure_content_overflow,
        )
        child_heights.append(child_height + _vertical_margin(child.props))
    visiting.remove(component.component_id)

    if component.component_type == "Column":
        content_height = sum(child_heights)
        content_height += _vertical_gap(component, len(child_heights))
    else:
        content_height = max(child_heights, default=0.0)
    reserved_height = explicit_height if measure_content_overflow and not height_weighted else 0
    return max(
        minimum_height, reserved_height or 0, _vertical_padding(component.props) + content_height
    )


def _vertical_gap(component: ComponentRow, child_count: int) -> float:
    if child_count < 2:
        return 0.0
    gap = _non_negative_number(component.props.get("itemMargin"))
    if gap is None:
        return 0.0
    return gap * (child_count - 1)


def _vertical_padding(props: dict[str, Any]) -> float:
    return _vertical_box_extent(props.get("padding"))


def _vertical_margin(props: dict[str, Any]) -> float:
    return _vertical_box_extent(props.get("margin"))


def _vertical_box_extent(value: Any) -> float:
    scalar = _non_negative_number(value)
    if scalar is not None:
        return scalar * 2
    if not isinstance(value, dict):
        return 0.0
    top = _non_negative_number(value.get("top")) or 0.0
    bottom = _non_negative_number(value.get("bottom")) or 0.0
    return top + bottom
