# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.two_by_two。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from services.card_validation.base import estimate_text_width
from services.card_validation.compact_validation.context import (
    _descendant_components,
    component_graph,
)
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _TWO_BY_TWO_HERO_BOX_HEIGHT,
    _TWO_BY_TWO_HERO_BOX_WIDTH,
    _TWO_BY_TWO_HERO_FONT_TIERS,
    _TWO_BY_TWO_HERO_SLOT_WIDTH,
    _TWO_BY_TWO_HERO_UNIT_MAX_FONT,
    _horizontal_content_width,
    _non_negative_number,
    _text_line_pressure_height,
    _visual_text_line_profile,
)
from services.card_validation.compact_validation.semantic.layout.regions import (
    _action_control_count,
    _contains_action_control,
    _has_two_by_two_s4_zones,
    _is_two_by_two_title_region,
    _uses_2x2_v01_countdown_layout,
)
from services.card_validation.compact_validation.semantic.layout.typography import (
    _numeric_hero_pressure_text,
)
from services.card_validation.compact_validation.syntax.expressions import _collect_binding_context
from services.card_validation.compact_validation.text import (
    _component_content_paths,
    _is_allowed_display_unit,
    _numeric_content_paths,
    _pure_numeric_binding_path,
)
from services.compact_dsl_a2ui_converter import ComponentRow


@dataclass(frozen=True)
class _CenteredHeroContext:
    """A sparse 2x2 title/value/action composition eligible for the safe box."""

    content_area: ComponentRow
    value: ComponentRow
    unit: ComponentRow | None


def _collect_two_by_two_narrow_graphical_action_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child = component_graph(components).last_parent
    for action in components:
        if action.component_type != "Row" or "onClick" not in action.props:
            continue
        children = [components_by_id.get(child_id) for child_id in action.children]
        if not any(child is not None and child.component_type == "Image" for child in children):
            continue
        if not any(child is not None and child.component_type == "Text" for child in children):
            continue
        parent = parent_by_child.get(action.component_id)
        if parent is None or parent.component_type != "Column":
            continue
        action_width = _horizontal_content_width(action)
        parent_width = _horizontal_content_width(parent)
        if action_width is None or parent_width is None or action_width >= parent_width:
            continue
        if parent.props.get("alignItems") != "center":
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_NARROW_ACTION_ALIGNMENT",
                    validation_class="semantic",
                    category="layout",
                    message="窄图文动作没有被父容器水平居中。",
                    expected={"parentAlignItems": "center"},
                    actual=parent.props.get("alignItems"),
                    component_id=parent.component_id,
                    property_path="/alignItems",
                    legacy_message=(
                        f"2x2 narrow graphical action Row {action.component_id} must be centered "
                        f"by parent Column {parent.component_id}; set alignItems to center when "
                        "the action is narrower than the parent's content width."
                    ),
                ),
            )


def _collect_two_by_two_s4_vertical_alignment_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    for zone_id in root.children:
        zone = components_by_id.get(zone_id)
        if zone is None:
            continue
        direct_children: list[ComponentRow] = []
        for child_id in zone.children:
            child = components_by_id.get(child_id)
            if child is not None:
                direct_children.append(child)

        has_visual = False
        for child in direct_children:
            if child.component_type in {"Image", "Progress", "Stack"}:
                has_visual = True
                break
        if not has_visual:
            if zone.component_type == "Column" and zone.props.get("justifyContent") != "center":
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_S4_TEXT_ONLY_ALIGNMENT",
                        validation_class="semantic",
                        category="layout",
                        message="没有视觉元素的背板未将文本垂直居中。",
                        expected={"justifyContent": "center", "emptyThirdLineAllowed": False},
                        actual=zone.props.get("justifyContent"),
                        component_id=zone.component_id,
                        property_path="/justifyContent",
                        legacy_message=(
                            f"2x2 S4 backboard {zone.component_id} without a visual must "
                            "vertically center its one or two text lines with "
                            "justifyContent center; do not reserve an empty third line."
                        ),
                    ),
                )
            continue

        text_group = None
        for child in direct_children:
            if child.component_type in {"Column", "Text"}:
                text_group = child
                break
        if (
            text_group is not None
            and text_group.component_type == "Column"
            and text_group.props.get("justifyContent") != "center"
        ):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_S4_TEXT_GROUP_ALIGNMENT",
                    validation_class="semantic",
                    category="layout",
                    message="视觉元素旁的文本组未垂直居中。",
                    expected={"justifyContent": "center"},
                    actual=text_group.props.get("justifyContent"),
                    component_id=text_group.component_id,
                    property_path="/justifyContent",
                    legacy_message=(
                        f"2x2 S4 text group {text_group.component_id} must use "
                        "justifyContent center so its one or two lines remain vertically "
                        "centered beside the visual."
                    ),
                ),
            )


def _collect_two_by_two_ring_group_alignment_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child = component_graph(components).last_parent

    for stack in components:
        if stack.component_type != "Stack":
            continue
        has_ring = False
        for child_id in stack.children:
            child = components_by_id.get(child_id)
            if (
                child is not None
                and child.component_type == "Progress"
                and child.props.get("type") == "ring"
            ):
                has_ring = True
                break
        if not has_ring:
            continue
        content_group = parent_by_child.get(stack.component_id)
        if content_group is None or content_group.component_type != "Column":
            continue
        direct_text_count = 0
        for child_id in content_group.children:
            child = components_by_id.get(child_id)
            if child is not None and child.component_type == "Text":
                direct_text_count += 1
        if direct_text_count > 1:
            continue
        if content_group.props.get("alignItems") == "center":
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X2_RING_GROUP_ALIGNMENT",
                validation_class="semantic",
                category="layout",
                message="紧凑进度环与状态文本组未水平居中。",
                expected={"alignItems": "center"},
                actual=content_group.props.get("alignItems"),
                component_id=content_group.component_id,
                property_path="/alignItems",
                legacy_message=(
                    f"2x2 compact ring group {content_group.component_id} must use "
                    'alignItems "center" so the ring and its single status line remain '
                    "horizontally centered."
                ),
            ),
        )


def _collect_two_by_two_s4_palette_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    color_keys = {
        "Text": ("fontColor",),
        "Image": ("fillColor",),
        "Progress": ("color", "backgroundColor"),
        "Divider": ("color",),
    }
    colors: dict[str, list[str]] = {}
    pending = list(root.children)
    visited: set[str] = set()
    while pending:
        component_id = pending.pop()
        if component_id in visited:
            continue
        visited.add(component_id)
        component = components_by_id.get(component_id)
        if component is None:
            continue
        pending.extend(component.children)
        for key in color_keys.get(component.component_type, ()):
            value = component.props.get(key)
            if not isinstance(value, str):
                continue
            if re.fullmatch(r"#[0-9A-Fa-f]{8}", value) is None:
                continue
            rgb = value[3:].upper()
            colors.setdefault(rgb, []).append(f"{component_id}.{key}")
    if len(colors) <= 1:
        return
    details = ", ".join(
        f"#{rgb}: {', '.join(locations)}" for rgb, locations in sorted(colors.items())
    )
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_S4_PALETTE",
            validation_class="semantic",
            category="layout",
            message="两个业务区域使用了不同的主色。",
            expected={
                "sharedRgbRequired": True,
                "alphaMayDiffer": True,
                "appliesTo": ["Text", "可染色 Image", "Progress", "Divider"],
            },
            actual={"colors": details},
            component_id=root.component_id,
            legacy_message=(
                "2x2 S4 must use one card palette across both business zones. Text, "
                "tintable Image, Progress, and Divider colors must share one RGB and "
                f"may differ only in alpha. Found mixed palette colors: {details}."
            ),
        ),
    )


def _two_by_two_centered_hero_context(
    task_spec: dict[str, Any],
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> _CenteredHeroContext | None:
    if task_spec.get("size") != "2x2" or len(root.children) != 3:
        return None

    title_area = components_by_id.get(root.children[0])
    content_area = components_by_id.get(root.children[1])
    action_area = components_by_id.get(root.children[2])
    if title_area is None or content_area is None or action_area is None:
        return None
    if not _is_two_by_two_title_region(title_area, components_by_id):
        return None
    if _contains_action_control(content_area, components_by_id):
        return None
    if _action_control_count(action_area, components_by_id) != 1:
        return None

    content_components = [
        content_area,
        *_descendant_components(content_area, components_by_id),
    ]
    allowed_types = {"Column", "Row", "Stack", "Text"}
    if any(component.component_type not in allowed_types for component in content_components):
        return None

    text_components = [
        component for component in content_components if component.component_type == "Text"
    ]
    if len(text_components) not in {1, 2}:
        return None

    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return None
    numeric_values: list[tuple[ComponentRow, str]] = []
    for component in text_components:
        path = _pure_numeric_binding_path(component.props.get("content"), schema)
        if path is not None:
            numeric_values.append((component, path))
    if len(numeric_values) != 1:
        return None

    value, numeric_path = numeric_values[0]
    unit: ComponentRow | None = None
    for component in text_components:
        if component.component_id == value.component_id:
            continue
        if not _is_allowed_display_unit(
            component.props.get("content"),
            numeric_path,
            schema,
        ):
            return None
        unit = component
    return _CenteredHeroContext(
        content_area=content_area,
        value=value,
        unit=unit,
    )


def _collect_two_by_two_centered_hero_errors(
    task_spec: dict[str, Any],
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if root is None or root.component_type != "Column":
        return
    context = _two_by_two_centered_hero_context(
        task_spec,
        root,
        components_by_id,
    )
    if context is None:
        return

    content_area = context.content_area
    content_layout_is_valid = (
        _non_negative_number(content_area.props.get("width")) == _TWO_BY_TWO_HERO_SLOT_WIDTH
        and content_area.props.get("layoutWeight") == 1
        and content_area.props.get("justifyContent") == "center"
        and content_area.props.get("alignItems") == "center"
        and "height" not in content_area.props
    )

    hero_box: ComponentRow | None = None
    value_row: ComponentRow | None = None
    if len(content_area.children) == 1:
        hero_box = components_by_id.get(content_area.children[0])
    if hero_box is not None and len(hero_box.children) == 1:
        value_row = components_by_id.get(hero_box.children[0])
    expected_value_children = [context.value.component_id]
    if context.unit is not None:
        expected_value_children.append(context.unit.component_id)
    hero_box_is_valid = (
        hero_box is not None
        and hero_box.component_type == "Column"
        and _non_negative_number(hero_box.props.get("width")) == _TWO_BY_TWO_HERO_BOX_WIDTH
        and _non_negative_number(hero_box.props.get("height")) == _TWO_BY_TWO_HERO_BOX_HEIGHT
        and hero_box.props.get("justifyContent") == "center"
        and hero_box.props.get("alignItems") == "center"
        and hero_box.props.get("padding", 0) == 0
    )
    value_row_is_valid = (
        value_row is not None
        and value_row.component_type == "Row"
        and list(value_row.children) == expected_value_children
        and _non_negative_number(value_row.props.get("width")) == _TWO_BY_TWO_HERO_BOX_WIDTH
        and value_row.props.get("justifyContent") == "center"
        and value_row.props.get("alignItems") == "bottom"
        and value_row.props.get("padding", 0) == 0
        and (context.unit is None or _non_negative_number(value_row.props.get("itemMargin")) == 2.0)
    )
    if not content_layout_is_valid or not hero_box_is_valid or not value_row_is_valid:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X2_HERO_SAFE_BOX",
                validation_class="semantic",
                category="layout",
                message="单值主内容没有采用要求的居中安全盒结构。",
                expected={
                    "contentArea": {"width": 126, "layoutWeight": 1, "centerBothAxes": True},
                    "heroBox": {"width": 106, "height": 58, "centerBothAxes": True},
                    "valueRow": {"width": 106, "centered": True},
                },
                component_id=context.content_area.component_id,
                legacy_message=(
                    "2x2 sparse single-value Hero with one bottom action must use a "
                    "126vp layoutWeight content_area centered on both axes, containing "
                    "one centered 106x58vp hero_box and a centered 106vp value_row."
                ),
            ),
        )

    value_font = _non_negative_number(context.value.props.get("fontSize"))
    if value_font not in _TWO_BY_TWO_HERO_FONT_TIERS:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X2_HERO_FONT_TIER",
                validation_class="semantic",
                category="layout",
                message="单值主内容的字号不在允许档位内。",
                expected={"fontSize": [38, 30, 24, 20]},
                actual=value_font,
                component_id=context.value.component_id,
                property_path="/fontSize",
                legacy_message=(
                    "2x2 centered single-value Hero must use one approved value font "
                    "tier: 38fp, 30fp, 24fp, or 20fp."
                ),
            ),
        )
        return

    unit_font = 0.0
    unit_text = ""
    if context.unit is not None:
        unit_font_value = _non_negative_number(context.unit.props.get("fontSize"))
        maximum_unit_font = _TWO_BY_TWO_HERO_UNIT_MAX_FONT.get(value_font)
        if unit_font_value is None or maximum_unit_font is None:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_HERO_UNIT_FONT",
                    validation_class="semantic",
                    category="layout",
                    message="主值的单位没有声明可用字号。",
                    expected={"unitFontSizeRequired": True},
                    actual=context.unit.props.get("fontSize"),
                    component_id=context.unit.component_id,
                    property_path="/fontSize",
                    legacy_message=("2x2 centered single-value Hero unit must declare a fontSize."),
                ),
            )
            return
        if unit_font_value < 12.0 or unit_font_value > maximum_unit_font:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_HERO_UNIT_FONT_PAIR",
                    validation_class="semantic",
                    category="layout",
                    message="主值与单位的字号不满足配对档位约束。",
                    expected={
                        "valueFontSize": value_font,
                        "minimumUnitFontSize": 12,
                        "maximumUnitFontSize": maximum_unit_font,
                        "pairedTiers": [[38, 16], [30, 14], [24, 12], [20, 12]],
                    },
                    actual=unit_font_value,
                    component_id=context.unit.component_id,
                    property_path="/fontSize",
                    legacy_message=(
                        "2x2 centered single-value Hero must downgrade value and unit "
                        "together using 38/16fp, 30/14fp, 24/12fp, or 20/12fp limits."
                    ),
                ),
            )
        unit_font = unit_font_value
        content = context.unit.props.get("content")
        unit_text = content.strip() if isinstance(content, str) else ""

    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return
    numeric_path = _pure_numeric_binding_path(
        context.value.props.get("content"),
        schema,
    )
    if numeric_path is None:
        return
    pressure_text = _numeric_hero_pressure_text(schema, numeric_path)
    pressure_width = estimate_text_width(pressure_text, value_font)
    if unit_text:
        pressure_width += estimate_text_width(unit_text, unit_font) + 2.0
    if pressure_width * 1.2 > _TWO_BY_TWO_HERO_BOX_WIDTH:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X2_HERO_WIDTH_BUDGET",
                validation_class="semantic",
                category="layout",
                message="主值与单位超过安全盒的宽度压力预算。",
                expected={
                    "maximumWidth": _TWO_BY_TWO_HERO_BOX_WIDTH,
                    "reserveFactor": 1.2,
                    "pairedFontTiers": [[38, 16], [30, 14], [24, 12], [20, 12]],
                },
                actual={"pressureWidthWithReserve": pressure_width * 1.2},
                component_id=context.value.component_id,
                legacy_message=(
                    "2x2 centered single-value Hero exceeds the 106vp width pressure "
                    "budget; downgrade value/unit together through "
                    "38/16fp -> 30/14fp -> 24/12fp -> 20/12fp until it fits."
                ),
            ),
        )

    line_height = _text_line_pressure_height(context.value, value_font)
    if context.unit is not None:
        line_height = max(
            line_height,
            _text_line_pressure_height(context.unit, unit_font),
        )
    if value_row is not None:
        explicit_row_height = _non_negative_number(value_row.props.get("height"))
        if explicit_row_height is not None:
            line_height = max(line_height, explicit_row_height)
    if line_height > _TWO_BY_TWO_HERO_BOX_HEIGHT:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X2_HERO_HEIGHT_BUDGET",
                validation_class="semantic",
                category="layout",
                message="主值与单位超过安全盒的高度压力预算。",
                expected={
                    "maximumHeight": _TWO_BY_TWO_HERO_BOX_HEIGHT,
                    "downgradeValueAndUnitTogether": True,
                    "clippingAllowed": False,
                },
                actual={"pressureHeight": line_height},
                component_id=context.value.component_id,
                legacy_message=(
                    "2x2 centered single-value Hero exceeds the 58vp height pressure "
                    "budget; downgrade value/unit together instead of clipping it."
                ),
            ),
        )


def _collect_two_by_two_content_density_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    """Enforce the text-line budget introduced for the 150vp 2x2 canvas."""
    if task_spec.get("size") != "2x2":
        return
    if _uses_2x2_v01_countdown_layout(task_spec):
        return
    if any(component.component_type == "TimelineUnit" for component in components):
        return

    root = components_by_id.get("root")
    if root is None or root.component_type != "Column":
        return
    if _has_two_by_two_s4_zones(root, components_by_id):
        return

    information_regions: list[ComponentRow] = []
    for index, child_id in enumerate(root.children):
        child = components_by_id.get(child_id)
        if child is None:
            continue
        if index == 0 and _is_two_by_two_title_region(child, components_by_id):
            continue
        if _contains_action_control(child, components_by_id):
            continue
        information_regions.append(child)
    if not information_regions:
        return

    information_components: list[ComponentRow] = []
    line_profile: list[bool] = []
    for region in information_regions:
        information_components.append(region)
        information_components.extend(_descendant_components(region, components_by_id))
        line_profile.extend(_visual_text_line_profile(region, components_by_id, set()))
    if any(component.component_type == "Progress" for component in information_components):
        return

    large_number_count = 0
    for component in information_components:
        if component.component_type != "Text":
            continue
        font_size = _non_negative_number(component.props.get("fontSize"))
        if font_size is not None and font_size >= 30:
            large_number_count += 1

    if large_number_count:
        data_model_schema = task_spec.get("dataModelSchema")
        numeric_paths = (
            _numeric_content_paths(information_components, data_model_schema)
            if isinstance(data_model_schema, dict)
            else set()
        )
        if len(numeric_paths) >= 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_PEER_METRIC_TYPOGRAPHY",
                    validation_class="semantic",
                    category="layout",
                    message="并列数值中有单个指标被放大为主数值。",
                    expected={
                        "peerMetrics": (
                            "全部使用相同排版的普通完整文本行，不能单独突出为 30fp/38fp 主值"
                        )
                    },
                    actual={"numericPaths": sorted(numeric_paths)},
                    component_id=root.component_id,
                    legacy_message=(
                        "2x2 150vp single-business content displays multiple peer "
                        "quantitative fields and must keep all of them as ordinary "
                        "complete text lines with the same typography; do not promote "
                        "one field to a 30fp/38fp hero."
                    ),
                ),
            )
        if large_number_count > 1:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_HERO_COUNT",
                    validation_class="semantic",
                    category="layout",
                    message="单业务内容中存在多个大字号数值。",
                    expected={
                        "maximumLargeNumberCount": 1,
                        "peerMetricsUseOrdinaryCompleteText": True,
                    },
                    actual={"largeNumberCount": large_number_count},
                    component_id=root.component_id,
                    legacy_message=(
                        "2x2 150vp single-business content contains multiple 30fp/38fp "
                        "values. Treat peer metrics as ordinary complete text lines instead "
                        "of manufacturing multiple hero values."
                    ),
                ),
            )
        if len(line_profile) > 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_HERO_LINE_BUDGET",
                    validation_class="semantic",
                    category="layout",
                    message="主数值内容包含过多信息行。",
                    expected={
                        "maximumVisualLines": 2,
                        "lines": ["数值与单位", "一行 12fp/400 辅助信息"],
                    },
                    actual={"lineCount": len(line_profile)},
                    component_id=root.component_id,
                    legacy_message=(
                        "2x2 150vp single-business content with a 30fp/38fp numeric hero "
                        "may contain only the value/unit line and one 12fp/400 auxiliary "
                        "line. Merge auxiliary fields into that line with ' | '."
                    ),
                ),
            )
        return

    has_action = False
    for child_id in root.children:
        child = components_by_id.get(child_id)
        if child is not None and _contains_action_control(
            child,
            components_by_id,
        ):
            has_action = True
            break
    if has_action and len(line_profile) > 3:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X2_ACTION_CONTENT_LINES",
                validation_class="semantic",
                category="layout",
                message="带动作的纯文本内容超过信息行预算。",
                expected={
                    "maximumVisualLines": 3,
                    "lines": ["一行突出内容", "两行 12fp/400 辅助信息"],
                },
                actual={"lineCount": len(line_profile)},
                component_id=root.component_id,
                legacy_message=(
                    "2x2 150vp single-business pure-text content with an action may "
                    "contain at most one prominent line and two 12fp/400 auxiliary "
                    "lines. Merge related auxiliary fields with ' | ' and remove "
                    "lower-priority update text."
                ),
            ),
        )
    if has_action and len(line_profile) == 3:
        oversized_text = False
        for component in information_components:
            font_size = _non_negative_number(component.props.get("fontSize"))
            if component.component_type == "Text" and (font_size or 0) > 18:
                oversized_text = True
                break
        if oversized_text:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_ACTION_CONTENT_FONT",
                    validation_class="semantic",
                    category="layout",
                    message="三行信息的主文字过大，可能遮挡底部动作。",
                    expected={
                        "maximumFontSize": 18,
                        "actionHeight": 36,
                        "actionMustRemainUnobstructed": True,
                    },
                    component_id=root.component_id,
                    legacy_message=(
                        "2x2 150vp single-business content with an action and three "
                        "information lines must keep its prominent text at 18fp or "
                        "smaller so the 36vp action remains unobstructed."
                    ),
                ),
            )


def _countdown_uses_expanded_layout(
    components: list[ComponentRow], visible_binding_paths: list[str]
) -> bool:
    return any(component.props.get("onClick") for component in components) or any(
        not path.endswith("/countdownDays") for path in visible_binding_paths
    )


def _collect_s4_text_budget(
    zone: ComponentRow,
    text_components: list[ComponentRow],
    errors: list[str],
) -> None:
    if len(text_components) > 2:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_S4_TEXT_COUNT",
                validation_class="semantic",
                category="layout",
                message="背板文本行数超过上限。",
                expected={"maximumTextCount": 2, "maxLinesPerText": 1},
                actual={"textCount": len(text_components)},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x2 S4 backboard {zone.component_id} contains "
                    f"{len(text_components)} Text rows; keep at most two single-line "
                    "Text components."
                ),
            ),
        )
    for text_component in text_components:
        if text_component.props.get("maxLines") != 1:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_S4_TEXT_MAX_LINES",
                    validation_class="semantic",
                    category="layout",
                    message="背板文本没有限制为单行。",
                    expected={"maxLines": 1},
                    actual=text_component.props.get("maxLines"),
                    component_id=text_component.component_id,
                    property_path="/maxLines",
                    legacy_message=(
                        f"2x2 S4 Text {text_component.component_id} must use "
                        "maxLines 1; a backboard must never render a third line."
                    ),
                ),
            )
        content = text_component.props.get("content")
        if not isinstance(content, str) or "{{" in content:
            continue
        text_width = _non_negative_number(text_component.props.get("width"))
        font_size = _non_negative_number(text_component.props.get("fontSize"))
        if text_width is None or font_size is None:
            continue
        estimated_width = 0.0
        for character in content.strip():
            estimated_width += font_size * (0.6 if character.isascii() else 1.0)
        if estimated_width > text_width:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_S4_STATIC_TEXT_WIDTH",
                    validation_class="semantic",
                    category="layout",
                    message="静态文本的估算宽度超过单行可用宽度。",
                    expected={
                        "maximumWidth": text_width,
                        "preserveMeaning": True,
                        "wrappingAllowed": False,
                        "thirdLineAllowed": False,
                        "movingVisualAllowed": False,
                    },
                    actual={"estimatedWidth": estimated_width},
                    component_id=text_component.component_id,
                    legacy_message=(
                        f"2x2 S4 static Text {text_component.component_id} exceeds its "
                        f"{text_width:g}vp single-line width; shorten the wording while "
                        "keeping its meaning. Do not wrap it, add a third line, or move "
                        "the visual."
                    ),
                ),
            )


def _collect_s4_calendar_typography(
    zone: ComponentRow,
    text_components: list[ComponentRow],
    errors: list[str],
) -> None:
    has_calendar_content = False
    has_meeting_title = False
    for text_component in text_components:
        paths = _component_content_paths(text_component)
        if any(path.startswith("/data/calendar/") for path in paths):
            has_calendar_content = True
        has_start_time = any(path.endswith("/dtStart") for path in paths)
        if has_start_time:
            if (
                text_component.props.get("fontSize") != 12
                or text_component.props.get("fontWeight") != 400
            ):
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_S4_MEETING_TIME",
                        validation_class="semantic",
                        category="layout",
                        message="会议时间没有使用独立的辅助文本排版。",
                        expected={
                            "fontSize": 12,
                            "fontWeight": 400,
                            "separateFromMeetingTitle": True,
                        },
                        actual={
                            "fontSize": text_component.props.get("fontSize"),
                            "fontWeight": text_component.props.get("fontWeight"),
                        },
                        component_id=text_component.component_id,
                        legacy_message=(
                            f"2x2 S4 meeting time {text_component.component_id} must "
                            "use its own 12fp/400 auxiliary row; do not combine it "
                            "with the 14fp/700 meeting title."
                        ),
                    ),
                )
            continue
        if (
            text_component.props.get("fontSize") == 14
            and text_component.props.get("fontWeight") == 700
        ):
            has_meeting_title = True
    if has_calendar_content and not has_meeting_title:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_S4_MEETING_TITLE",
                validation_class="semantic",
                category="layout",
                message="日程背板缺少独立的标题排版。",
                expected={
                    "titleFontSize": 14,
                    "titleFontWeight": 700,
                    "timeFontSize": 12,
                    "timeFontWeight": 400,
                    "titleAboveTime": True,
                },
                component_id=zone.component_id,
                legacy_message=(
                    f"2x2 S4 calendar backboard {zone.component_id} must keep a "
                    "separate 14fp/700 meeting title above its 12fp/400 time row."
                ),
            ),
        )


def _collect_2x2_countdown_layout(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    visible_binding_paths: list[str],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    if not _uses_2x2_v01_countdown_layout(task_spec):
        return

    uses_expanded_layout = _countdown_uses_expanded_layout(components, visible_binding_paths)

    parent_by_child = component_graph(components).last_parent
    countdown_values = []
    for component in components:
        if component.component_type != "Text":
            continue
        component_paths: list[str] = []
        _collect_binding_context(
            component.props.get("content"),
            f"component {component.component_id}.props.content",
            component_paths,
            [],
        )
        if any(path.endswith("/countdownDays") for path in component_paths):
            countdown_values.append(component)

    for countdown_value in countdown_values:
        direct_parent = parent_by_child.get(countdown_value.component_id)
        if uses_expanded_layout:
            if direct_parent is None or direct_parent.component_type != "Row":
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_2X2_COUNTDOWN_VALUE_ROW",
                        validation_class="semantic",
                        category="layout",
                        message="带动作或额外数据的倒计时数值未置于水平行内。",
                        expected={
                            "parentType": "Row",
                            "alignment": "start",
                            "verticalV01LayoutAllowed": False,
                        },
                        component_id=countdown_value.component_id,
                        legacy_message=(
                            "2x2 countdown with an action or additional visible data must "
                            "place the countdown number in a left-aligned value_row; do not "
                            "keep the V01 centered vertical number/unit layout."
                        ),
                    ),
                )
                continue
            value_group = parent_by_child.get(direct_parent.component_id)
            if value_group is None or value_group.component_type != "Column":
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_2X2_COUNTDOWN_VALUE_GROUP",
                        validation_class="semantic",
                        category="layout",
                        message="扩展倒计时数值行缺少内容列。",
                        expected={"parentType": "Column", "width": "全宽"},
                        component_id=direct_parent.component_id,
                        legacy_message=(
                            "2x2 expanded countdown value_row must belong to a full-width "
                            "value_group Column."
                        ),
                    ),
                )
                continue
            if (
                value_group.props.get("alignItems") != "start"
                or direct_parent.props.get("justifyContent") != "start"
            ):
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_2X2_COUNTDOWN_ALIGNMENT",
                        validation_class="semantic",
                        category="layout",
                        message="扩展倒计时内容没有左对齐。",
                        expected={
                            "valueGroupAlignItems": "start",
                            "valueRowJustifyContent": "start",
                        },
                        actual={
                            "groupAlignItems": value_group.props.get("alignItems"),
                            "rowJustifyContent": direct_parent.props.get("justifyContent"),
                        },
                        component_id=value_group.component_id,
                        legacy_message=(
                            "2x2 countdown with an action or additional visible data must "
                            "left-align value_group and value_row; centered countdown values "
                            "are reserved for the display-only V01 layout."
                        ),
                    ),
                )
            if value_group.children and value_group.children[0] != direct_parent.component_id:
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_2X2_COUNTDOWN_ROW_ORDER",
                        validation_class="semantic",
                        category="layout",
                        message="扩展倒计时的数值行不是内容组的第一个子节点。",
                        expected={"firstChildId": direct_parent.component_id},
                        actual=value_group.children,
                        component_id=value_group.component_id,
                        property_path="/children",
                        legacy_message=(
                            "2x2 expanded countdown value_row must be "
                            "the first child of value_group."
                        ),
                    ),
                )
            if len(value_group.children) > 2:
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_2X2_COUNTDOWN_GROUP_ROWS",
                        validation_class="semantic",
                        category="layout",
                        message="扩展倒计时内容组包含过多行。",
                        expected={"maximumRows": 2, "rows": ["数值行", "可选的一行辅助数据"]},
                        actual={"childCount": len(value_group.children)},
                        component_id=value_group.component_id,
                        legacy_message=(
                            "2x2 expanded countdown value_group may contain only the value_row "
                            "and one optional auxiliary-data row."
                        ),
                    ),
                )
            continue
        value_group = direct_parent
        if value_group is None or value_group.component_type != "Column":
            continue
        if len(value_group.children) != 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_V01_COUNTDOWN_ROWS",
                    validation_class="semantic",
                    category="layout",
                    message="展示型倒计时内容组没有保持两行结构。",
                    expected={
                        "rowCount": 2,
                        "rows": ["倒计时数值", "单位或附加时间"],
                        "extraAuxiliaryOrRepeatedTargetAllowed": False,
                    },
                    actual={"childCount": len(value_group.children)},
                    component_id=value_group.component_id,
                    legacy_message=(
                        "2x2 V01 countdown value_group must contain exactly two visual "
                        "rows: the countdown number and a second-line unit/meta row. "
                        "Do not add a third aux_text or repeat the target name."
                    ),
                ),
            )
            continue
        second_line = components_by_id.get(value_group.children[1])
        if second_line is None:
            continue
        if second_line.component_type == "Row" and len(second_line.children) > 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_V01_META_ROW",
                    validation_class="semantic",
                    category="layout",
                    message="展示型倒计时的附加信息行包含过多节点。",
                    expected={
                        "maximumChildren": 2,
                        "content": ["单位", "可选时间"],
                        "sameLineRequired": True,
                    },
                    actual={"childCount": len(second_line.children)},
                    component_id=second_line.component_id,
                    legacy_message=(
                        "2x2 V01 countdown meta_row may contain only the unit and the "
                        "optional time on the same line."
                    ),
                ),
            )
