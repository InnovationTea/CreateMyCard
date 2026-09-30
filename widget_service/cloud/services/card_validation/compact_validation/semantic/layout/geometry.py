# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.geometry。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import component_index
from services.card_validation.compact_validation.syntax.components import _NON_EMPTY_CONTAINER_TYPES
from services.compact_dsl_a2ui_converter import ComponentRow

from ...diagnostics import CompactDiagnostic, emit_error

_REFERENCE_CANVAS_HEIGHT = {
    "2x2": 150.0,
    "2x4": 150.0,
    "4x2": 150.0,
}


_TWO_BY_FOUR_MULTI_ROOT_PADDING = 8


_TWO_BY_FOUR_MULTI_LARGE_WIDTH = 138


_TWO_BY_FOUR_MULTI_LARGE_HEIGHT = 134


_TWO_BY_FOUR_MULTI_INNER_WIDTH = 114


_TWO_BY_FOUR_FOCUS_WIDTH = 136


_TWO_BY_FOUR_AUX_WIDTH = 130


_TWO_BY_FOUR_FOCUS_AUX_HEIGHT = 126


_TWO_BY_FOUR_AUX_CELL_HEIGHT = 59


_TWO_BY_TWO_HERO_SLOT_WIDTH = 126.0


_TWO_BY_TWO_HERO_BOX_WIDTH = 106.0


_TWO_BY_TWO_HERO_BOX_HEIGHT = 58.0


_TWO_BY_TWO_HERO_FONT_TIERS = (20.0, 24.0, 30.0, 38.0)


_TWO_BY_TWO_HERO_UNIT_MAX_FONT = {
    20.0: 12.0,
    24.0: 12.0,
    30.0: 14.0,
    38.0: 16.0,
}


def _horizontal_padding_at_least(props: dict[str, Any], minimum: float) -> bool:
    padding = props.get("padding")
    if isinstance(padding, (int, float)):
        return padding >= minimum
    if not isinstance(padding, dict):
        return False
    left = _non_negative_number(padding.get("left"))
    right = _non_negative_number(padding.get("right"))
    return left is not None and left >= minimum and right is not None and right >= minimum


def _horizontal_content_width(component: ComponentRow) -> float | None:
    width = _non_negative_number(component.props.get("width"))
    if width is None:
        return None
    padding = component.props.get("padding")
    if isinstance(padding, (int, float)):
        return max(width - 2 * float(padding), 0.0)
    if not isinstance(padding, dict):
        return width
    left = _non_negative_number(padding.get("left"))
    right = _non_negative_number(padding.get("right"))
    if left is None or right is None:
        return None
    return max(width - left - right, 0.0)


def _visual_text_line_profile(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    visiting: set[str],
) -> list[bool]:
    """Return visual text lines, marking lines that use emphasized text."""
    if component.component_type == "Text":
        font_size = _non_negative_number(component.props.get("fontSize")) or 0.0
        font_weight = _non_negative_number(component.props.get("fontWeight")) or 0.0
        return [font_size > 12 or font_weight >= 500]
    if component.component_id in visiting:
        return []

    visiting.add(component.component_id)
    child_profiles: list[list[bool]] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        child_profiles.append(_visual_text_line_profile(child, components_by_id, visiting))
    visiting.remove(component.component_id)

    if component.component_type in {"Column", "List"}:
        result: list[bool] = []
        for profile in child_profiles:
            result.extend(profile)
        return result
    if component.component_type not in {"Row", "Stack"}:
        return []

    line_count = max((len(profile) for profile in child_profiles), default=0)
    result = []
    for line_index in range(line_count):
        emphasized = False
        for profile in child_profiles:
            if line_index < len(profile) and profile[line_index]:
                emphasized = True
                break
        result.append(emphasized)
    return result


def _text_line_pressure_height(component: ComponentRow, font_size: float) -> float:
    natural_height = font_size * 1.4 + _vertical_padding(component.props)
    explicit_height = _non_negative_number(component.props.get("height")) or 0.0
    return max(natural_height, explicit_height)


def _collect_height_budget_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    errors: list[str],
) -> None:
    """Reject vertical layouts whose declared minimum height cannot fit."""
    components_by_id = component_index(components)
    for component in components:
        if component.component_type not in {"Column", "List"}:
            continue
        available_height = _component_available_height(
            component,
            task_spec,
            card_spec,
        )
        if available_height is None:
            continue
        required_height = _column_children_minimum_height(
            component,
            components_by_id,
        )
        if required_height <= available_height:
            continue
        overflow = required_height - available_height
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_HEIGHT_OVERFLOW",
                validation_class="semantic",
                category="layout",
                component_id=component.component_id,
                message=(
                    f"{component.component_id} 的内容最小高度为 {_format_vp(required_height)}vp，"
                    f"可用高度为 {_format_vp(available_height)}vp，超出 {_format_vp(overflow)}vp。"
                ),
                actual={"minimumRequiredHeight": required_height},
                expected={
                    "maximumHeight": available_height,
                    "overflowConstraint": "不能依靠裁剪、flex shrink 或分布式对齐消除高度超限。",
                },
                legacy_message=(
                    f"component {component.component_id}: vertical layout requires at least "
                    f"{_format_vp(required_height)}vp within {_format_vp(available_height)}vp; "
                    f"it overflows by {_format_vp(overflow)}vp. Reduce child heights, margins, "
                    "or gaps instead of relying on clipping, flex shrink, or distributed alignment."
                ),
            ),
        )


def _component_available_height(
    component: ComponentRow,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
) -> float | None:
    outer_height = _component_outer_height(component, task_spec, card_spec)
    if outer_height is None:
        return None
    return max(0.0, outer_height - _vertical_padding(component.props))


def _component_outer_height(
    component: ComponentRow,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
) -> float | None:
    if component.component_id == "root":
        size = card_spec.get("suggestSize")
        if not isinstance(size, str) or not size:
            size = task_spec.get("size")
        if isinstance(size, str):
            reference_height = _REFERENCE_CANVAS_HEIGHT.get(size)
            if reference_height is not None:
                return reference_height
    return _non_negative_number(component.props.get("height"))


def _column_children_minimum_height(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> float:
    child_heights: list[float] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        child_height = _minimum_outer_height(child, components_by_id, set())
        child_heights.append(child_height + _vertical_margin(child.props))

    gap = _vertical_gap(component, len(child_heights))
    return sum(child_heights) + gap


def _minimum_outer_height(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    visiting: set[str],
) -> float:
    if component.component_type == "CardHeader":
        return 20.0
    explicit_height = _non_negative_number(component.props.get("height"))
    if explicit_height is not None:
        return explicit_height
    if component.component_type == "ActionUnit":
        return _action_unit_minimum_height(component)
    if component.component_type not in _NON_EMPTY_CONTAINER_TYPES:
        return 0.0
    if component.component_id in visiting:
        return 0.0

    visiting.add(component.component_id)
    child_heights: list[float] = []
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        child_height = _minimum_outer_height(child, components_by_id, visiting)
        child_heights.append(child_height + _vertical_margin(child.props))
    visiting.remove(component.component_id)

    if component.component_type in {"Column", "List"}:
        content_height = sum(child_heights)
        content_height += _vertical_gap(component, len(child_heights))
    else:
        content_height = max(child_heights, default=0.0)
    return _vertical_padding(component.props) + content_height


def _action_unit_minimum_height(component: ComponentRow) -> float:
    if component.props.get("state") == "capsule":
        return 36.0
    if component.props.get("state") == "icon-round":
        return 30.0
    return 0.0


def _vertical_gap(component: ComponentRow, child_count: int) -> float:
    if child_count < 2:
        return 0.0
    property_name = "space" if component.component_type == "List" else "itemMargin"
    gap = _non_negative_number(component.props.get(property_name))
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


def _non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return float(value)


def _format_vp(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
