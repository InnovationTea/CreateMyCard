# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：compatibility.hero。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

import math
import re
from typing import Any

from services.card_validation.compact_validation.constants import (
    _COMMON_DISPLAY_UNITS,
    _MEASUREMENT_DESCRIPTION_MARKERS,
    _MEASUREMENT_SAMPLE_PATTERN,
    _NUMERIC_SCHEMA_TYPES,
    _SIMPLE_FORMATTED_EXPRESSION_PATTERN,
    _TWO_BY_FOUR_MULTI_INNER_WIDTH,
    _TWO_BY_FOUR_MULTI_LARGE_HEIGHT,
    _TWO_BY_FOUR_MULTI_LARGE_WIDTH,
)
from services.card_validation.compact_validation.schema import _schema_node_at_path, _schema_type
from services.card_validation.compact_validation.text import (
    _format_vp,
    _is_allowed_display_unit,
    _non_negative_number,
    _pure_binding_path,
    _pure_numeric_binding_path,
    _uses_visual_recipe,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
)


def _collect_hero_value_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    components_by_id = {component.component_id: component for component in components}
    if len(components_by_id) == len(components) and "template_root" in components_by_id:
        root = components_by_id.get("root")
        if root is not None and "template_root" in root.children:
            return
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return
    _collect_adjacent_display_unit_errors(
        components,
        components_by_id,
        data_model_schema,
        errors,
        enforce_all_numeric_sizes=task_spec.get("size") == "2x4",
    )
    if task_spec.get("size") == "2x4":
        _collect_mixed_font_row_alignment_errors(components, components_by_id, errors)
    numeric_paths: dict[str, str | None] = {}
    formatted_hero_ids: set[str] = set()
    for component in components:
        if component.component_type != "Text":
            continue
        if _uses_visual_recipe(component):
            continue
        font_size = _non_negative_number(component.props.get("fontSize"))
        if font_size is None or font_size <= 18:
            continue
        path = _pure_numeric_binding_path(component.props.get("content"), data_model_schema)
        numeric_paths[component.component_id] = path
        if path is not None:
            continue
        if _is_readable_formatted_hero(component, components, task_spec, font_size):
            numeric_paths.pop(component.component_id)
            formatted_hero_ids.add(component.component_id)
            continue
        if _is_adaptive_primary_text(component, components, task_spec, font_size):
            numeric_paths.pop(component.component_id)
            continue
        errors.append(
            f"component {component.component_id}: fontSize {_format_vp(font_size)} "
            f"requires a pure number/integer or a supported primary value. A directly "
            f"bound measurement with a declared unit may use 20/24fp in a full-width area "
            f"or 2x4 large panel when its text budget fits; ordinary names, dates, times, "
            f"and statuses remain at most 18fp."
        )
    for component in components:
        if component.component_type != "Row":
            continue
        if _uses_visual_recipe(component):
            continue
        for index, child_id in enumerate(component.children[:-1]):
            suffix = components_by_id.get(component.children[index + 1])
            if child_id in formatted_hero_ids:
                if suffix is not None and suffix.component_type == "Text":
                    errors.append(
                        f"component {component.component_id}: formatted value {child_id} "
                        f"already contains its unit; do not append Text "
                        f"{suffix.component_id} or a field label."
                    )
                continue
            if child_id not in numeric_paths:
                continue
            numeric_path = numeric_paths[child_id]
            if suffix is None or suffix.component_type != "Text":
                continue
            content = suffix.props.get("content")
            if _is_allowed_display_unit(content, numeric_path or "", data_model_schema):
                continue
            value_source = numeric_path or "the preceding value"
            errors.append(
                f"component {component.component_id}: Text {suffix.component_id} after the "
                f"large numeric value must contain only a real unit for {value_source}. "
                f"Move labels or descriptions to a separate line."
            )


def _is_adaptive_primary_text(
    component: ComponentRow,
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    font_size: float,
) -> bool:
    if font_size not in (20.0, 24.0, 30.0, 32.0, 38.0):
        return False
    if task_spec.get("size") not in {"2x2", "2x4"}:
        return False
    props = component.props
    if props.get("maxLines") != 1 or props.get("padding", 0) != 0:
        return False
    parents = [parent for parent in components if component.component_id in parent.children]
    if len(parents) != 1:
        return False
    parent = parents[0]
    if parent.component_type not in {"Column", "Row"} or parent.props.get("padding", 0) != 0:
        return False
    if parent.component_type == "Row" and len(parent.children) != 1:
        return False
    width = _non_negative_number(props.get("width"))
    parent_width = _non_negative_number(parent.props.get("width"))
    effective_width = width if width is not None else parent_width
    if effective_width is None or parent_width != effective_width:
        return False
    expected = {"2x2": {126.0, 136.0}, "2x4": {276.0, 296.0}}[task_spec["size"]]
    if effective_width not in expected and (
        not (task_spec["size"] == "2x4" and effective_width in {114.0, 120.0})
    ):
        return False
    height = _non_negative_number(props.get("height"))
    return height is None or height >= font_size * 1.4


def _is_readable_formatted_hero(
    component: ComponentRow,
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    font_size: float,
) -> bool:
    """放行全宽或大分区内、单行且通过压力预算的格式化主读数。"""
    if font_size not in (20.0, 24.0):
        return False
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return False
    data = schema.get("data")
    if not isinstance(data, dict):
        return False
    content = component.props.get("content")
    path, expression_unit = _formatted_hero_binding(content)
    if path is None:
        return False
    node = _schema_node_at_path(schema, path)
    if not isinstance(node, dict):
        return False
    sample = node.get("sampleValue")
    description = node.get("description")
    if not isinstance(description, str):
        return False
    if expression_unit is not None:
        if expression_unit not in _COMMON_DISPLAY_UNITS:
            return False
        if node.get("type") not in (*_NUMERIC_SCHEMA_TYPES, "string"):
            return False
        if not isinstance(sample, (int, float, str)) or isinstance(sample, bool):
            return False
        sample = f"{sample}{expression_unit}"
    elif node.get("type") != "string" or not isinstance(sample, str):
        return False
    pressure = _formatted_hero_pressure(sample, description)
    if pressure is None:
        return False
    if task_spec.get("size") not in ("2x2", "2x4"):
        return False
    props = component.props
    component_width = _non_negative_number(props.get("width"))
    if component_width is None:
        return False
    is_full_width = (
        component_width == 126.0 if task_spec.get("size") == "2x2" else component_width == 276.0
    )
    is_large_2x4_panel = (
        task_spec.get("size") == "2x4"
        and component_width == _TWO_BY_FOUR_MULTI_INNER_WIDTH
        and _is_large_2x4_panel(component, components)
    )
    if not is_full_width and (not is_large_2x4_panel):
        return False
    if isinstance(data, dict) and len(data) != 1 and (not is_large_2x4_panel):
        return False
    expected_width = component_width
    if props.get("width") != expected_width or props.get("maxLines") != 1:
        return False
    height = _non_negative_number(props.get("height"))
    if height is None or height < font_size * 1.4:
        return False
    if props.get("padding", 0) != 0 or props.get("margin", 0) != 0:
        return False
    parents = []
    for parent in components:
        if component.component_id in parent.children:
            parents.append(parent)
    if len(parents) != 1:
        return False
    parent = parents[0]
    if parent.component_type == "Column":
        if parent.props.get("width") != expected_width:
            return False
    elif parent.component_type == "Row":
        if parent.props.get("width") != expected_width:
            return False
        if not _has_parent_column(parent, components, expected_width):
            return False
    else:
        return False
    if parent.props.get("padding", 0) != 0:
        return False
    estimated = 0.0
    for character in pressure:
        estimated += font_size * (0.6 if character.isascii() else 1.0)
    return estimated * 1.2 <= expected_width


def _formatted_hero_binding(content: Any) -> tuple[str | None, str | None]:
    if isinstance(content, dict) and set(content) == {"path"}:
        path = content.get("path")
        if isinstance(path, str):
            return (path, None)
        return (None, None)
    if not isinstance(content, str):
        return (None, None)
    match = _SIMPLE_FORMATTED_EXPRESSION_PATTERN.fullmatch(content.strip())
    if match is None:
        return (None, None)
    path = match.group("path")
    unit = match.group("unit")
    return (path, unit)


def _is_large_2x4_panel(component: ComponentRow, components: list[ComponentRow]) -> bool:
    child_to_parents: dict[str, list[ComponentRow]] = {}
    for parent in components:
        for child_id in parent.children:
            child_to_parents.setdefault(child_id, []).append(parent)
    pending = [component.component_id]
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        for parent in child_to_parents.get(child_id, []):
            width = _non_negative_number(parent.props.get("width"))
            height = _non_negative_number(parent.props.get("height"))
            if (
                width == _TWO_BY_FOUR_MULTI_LARGE_WIDTH
                and height == _TWO_BY_FOUR_MULTI_LARGE_HEIGHT
            ):
                return True
            pending.append(parent.component_id)
    return False


def _has_parent_column(
    component: ComponentRow, components: list[ComponentRow], width: float
) -> bool:
    child_to_parents: dict[str, list[ComponentRow]] = {}
    for parent in components:
        for child_id in parent.children:
            child_to_parents.setdefault(child_id, []).append(parent)
    pending = [component.component_id]
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        for parent in child_to_parents.get(child_id, []):
            if (
                parent.component_type == "Column"
                and parent.props.get("width") == width
                and (parent.props.get("padding", 0) == 0)
            ):
                return True
            pending.append(parent.component_id)
    return False


def _formatted_hero_pressure(sample: str, description: str) -> str | None:
    """保留单位，不求值任意表达式，不把名称或日期误当作主读数。"""
    temperature = "温度" in description
    temperature = (
        temperature and re.fullmatch("[+-]?\\d+(?:\\.\\d+)?\\s*(?:°C|℃|°F)", sample) is not None
    )
    duration = any(word in description for word in ("时长", "持续时间"))
    duration = (
        duration and re.fullmatch("\\d+小时(?:\\d+分)?|\\d+(?:分钟|分|秒)", sample) is not None
    )
    percentage = any(word in description for word in ("百分比", "百分率", "电量", "占比", "比例"))
    percentage = percentage and re.fullmatch("\\d+(?:\\.\\d+)?%", sample) is not None
    measurement = any(marker in description for marker in _MEASUREMENT_DESCRIPTION_MARKERS)
    measurement = measurement and _MEASUREMENT_SAMPLE_PATTERN.fullmatch(sample) is not None
    pressure: str | None = None
    has_measured_format = temperature or duration or percentage
    if has_measured_format or measurement:
        pressure = re.sub("\\d+", lambda match: "9" * max(2, len(match.group())), sample)
        if temperature:
            pressure = re.sub(
                "(?<![\\d.])\\d+", lambda match: "9" * max(2, len(match.group())), sample
            )
            pressure = "-" + pressure.lstrip("+-")
        elif percentage:
            pressure = "100%"
            if "." in sample:
                decimals = sample.split(".", 1)[1].removesuffix("%")
                pressure = "100." + "9" * len(decimals) + "%"
    return pressure


def _collect_adjacent_display_unit_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    data_model_schema: dict[str, Any],
    errors: list[str],
    enforce_all_numeric_sizes: bool,
) -> None:
    for component in components:
        if component.component_type != "Row":
            continue
        if _uses_visual_recipe(component):
            continue
        for index, child_id in enumerate(component.children[:-1]):
            value = components_by_id.get(child_id)
            suffix = components_by_id.get(component.children[index + 1])
            if value is None or value.component_type != "Text":
                continue
            if suffix is None or suffix.component_type != "Text":
                continue
            suffix_content = suffix.props.get("content")
            if not isinstance(suffix_content, str):
                continue
            value_path = _pure_binding_path(value.props.get("content"))
            if value_path is None:
                continue
            if value_path:
                schema_type = _schema_type(_schema_node_at_path(data_model_schema, value_path))
            else:
                schema_type = "number"
            value_font_size = _non_negative_number(value.props.get("fontSize"))
            if (
                value_font_size is not None
                and value_font_size >= 30
                and (schema_type not in _NUMERIC_SCHEMA_TYPES)
            ):
                errors.append(
                    f"component {component.component_id}: large primary Text "
                    f"{value.component_id} binds non-numeric field {value_path} and must "
                    f"occupy its own row; do not append {suffix.component_id} as a unit or "
                    f"label."
                )
                continue
            unit = suffix_content.strip()
            if schema_type in _NUMERIC_SCHEMA_TYPES:
                is_known_unit = unit in _COMMON_DISPLAY_UNITS
                if value_path:
                    is_known_unit = _is_allowed_display_unit(
                        suffix_content, value_path, data_model_schema
                    )
                if not is_known_unit:
                    continue
                if not enforce_all_numeric_sizes:
                    continue
                padding = suffix.props.get("padding")
                unit_bottom_padding = None
                if isinstance(padding, (int, float)):
                    unit_bottom_padding = float(padding)
                elif isinstance(padding, dict):
                    unit_bottom_padding = _non_negative_number(padding.get("bottom"))
                unit_height = _non_negative_number(suffix.props.get("height"))
                has_valid_height = unit_height is None or unit_height <= 24
                item_margin = _non_negative_number(component.props.get("itemMargin"))
                has_compact_spacing = item_margin is None or item_margin <= 4
                has_intrinsic_width = (
                    value.props.get("width") is None and suffix.props.get("width") is None
                )
                suffix_font_size = _non_negative_number(suffix.props.get("fontSize"))
                expected_unit_padding = 0
                if value_font_size is not None and suffix_font_size is not None:
                    expected_unit_padding = min(
                        8, max(0, int(math.ceil((value_font_size - suffix_font_size) / 4)))
                    )
                has_valid_alignment = (
                    component.props.get("alignItems") == "bottom"
                    and unit_bottom_padding == expected_unit_padding
                    and has_valid_height
                    and has_compact_spacing
                    and has_intrinsic_width
                )
                if not has_valid_alignment:
                    errors.append(
                        f"component {component.component_id}: numeric value and unit "
                        f'{suffix.component_id} must use Row alignItems "bottom"; the unit '
                        f"must use capped visual bottom padding for its font-size "
                        f"difference and must not use the numeric value's fixed height; "
                        f"both Text nodes must use intrinsic width and their Row "
                        f"itemMargin must not exceed 4."
                    )
                continue
            if unit not in _COMMON_DISPLAY_UNITS:
                continue
            errors.append(
                f"component {component.component_id}: display unit {unit!r} cannot follow "
                f"non-numeric binding {value_path}. Remove the unit or bind a "
                f"number/integer value."
            )


def _collect_mixed_font_row_alignment_errors(
    components: list[ComponentRow], components_by_id: dict[str, ComponentRow], errors: list[str]
) -> None:
    for component in components:
        if component.component_type != "Row":
            continue
        if _uses_visual_recipe(component):
            continue
        text_children: list[ComponentRow] = []
        for child_id in component.children:
            child = components_by_id.get(child_id)
            if child is None or child.component_type != "Text":
                continue
            font_size = _non_negative_number(child.props.get("fontSize"))
            if font_size is not None:
                text_children.append(child)
        if len(text_children) < 2:
            continue
        font_sizes = [_non_negative_number(child.props.get("fontSize")) for child in text_children]
        numeric_font_sizes = [font_size for font_size in font_sizes if font_size is not None]
        max_font_size = max(numeric_font_sizes)
        min_font_size = min(numeric_font_sizes)
        if max_font_size == min_font_size:
            continue
        if component.props.get("alignItems") != "bottom":
            errors.append(
                f"component {component.component_id}: a Row containing mixed Text font "
                f"sizes must use alignItems bottom so every visible text bottom aligns."
            )
        for child in text_children:
            child_font_size = _non_negative_number(child.props.get("fontSize"))
            if child_font_size is None or child_font_size == max_font_size:
                continue
            padding = child.props.get("padding")
            actual_padding = None
            if isinstance(padding, (int, float)):
                actual_padding = float(padding)
            elif isinstance(padding, dict):
                actual_padding = _non_negative_number(padding.get("bottom"))
            expected_padding = min(8, max(0, int(math.ceil((max_font_size - child_font_size) / 4))))
            if actual_padding == expected_padding:
                continue
            errors.append(
                f"component {child.component_id}: smaller Text in mixed-size Row "
                f"{component.component_id} must use padding.bottom {expected_padding} to "
                f'compensate the visible glyph baseline after Row alignItems "bottom" '
                f"aligns the Text boxes."
            )
