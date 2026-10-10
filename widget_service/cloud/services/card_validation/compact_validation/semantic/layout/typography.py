# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.typography。"""

from __future__ import annotations

import math
import re
from typing import Any

from services.card_validation.compact_validation.context import (
    HeroTextAnalysis,
    _has_parent_column,
)
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.schema import (
    _NUMERIC_SCHEMA_TYPES,
    _schema_node_at_path,
)
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _TWO_BY_FOUR_MULTI_INNER_WIDTH,
    _format_vp,
    _non_negative_number,
)
from services.card_validation.compact_validation.semantic.layout.regions import _is_large_2x4_panel
from services.card_validation.compact_validation.text import (
    _COMMON_DISPLAY_UNITS,
    _MEASUREMENT_DESCRIPTION_MARKERS,
    _MEASUREMENT_SAMPLE_PATTERN,
    _pure_numeric_binding_path,
)
from services.compact_dsl_a2ui_converter import ComponentRow

_SIMPLE_FORMATTED_EXPRESSION_PATTERN = re.compile(
    r"^\{\{\s*\$\{(?P<path>/[^{}]+)\}\s*\+\s*'(?P<unit>[^']+)'\s*\}\}$"
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
    if effective_width not in expected and not (
        task_spec["size"] == "2x4" and effective_width in {114.0, 120.0}
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
    if not is_full_width and not is_large_2x4_panel:
        return False
    if isinstance(data, dict) and len(data) != 1 and not is_large_2x4_panel:
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
            return path, None
        return None, None
    if not isinstance(content, str):
        return None, None
    match = _SIMPLE_FORMATTED_EXPRESSION_PATTERN.fullmatch(content.strip())
    if match is None:
        return None, None
    path = match.group("path")
    unit = match.group("unit")
    return path, unit


def _formatted_hero_pressure(sample: str, description: str) -> str | None:
    """保留单位，不求值任意表达式，不把名称或日期误当作主读数。"""
    temperature = "温度" in description
    temperature = (
        temperature and re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*(?:°C|℃|°F)", sample) is not None
    )
    duration = any(word in description for word in ("时长", "持续时间"))
    duration = duration and re.fullmatch(r"\d+小时(?:\d+分)?|\d+(?:分钟|分|秒)", sample) is not None
    percentage = any(word in description for word in ("百分比", "百分率", "电量", "占比", "比例"))
    percentage = percentage and re.fullmatch(r"\d+(?:\.\d+)?%", sample) is not None
    measurement = any(marker in description for marker in _MEASUREMENT_DESCRIPTION_MARKERS)
    measurement = measurement and _MEASUREMENT_SAMPLE_PATTERN.fullmatch(sample) is not None
    pressure: str | None = None
    known_formatted_value = temperature or duration or percentage
    if known_formatted_value or measurement:
        pressure = re.sub(r"\d+", lambda match: "9" * max(2, len(match.group())), sample)
        if temperature:
            pressure = re.sub(
                r"(?<![\d.])\d+", lambda match: "9" * max(2, len(match.group())), sample
            )
            pressure = "-" + pressure.lstrip("+-")
        elif percentage:
            pressure = "100%"
            if "." in sample:
                decimals = sample.split(".", 1)[1].removesuffix("%")
                pressure = "100." + "9" * len(decimals) + "%"
    return pressure


def _collect_mixed_font_row_alignment_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    for component in components:
        if component.component_type != "Row":
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
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_MIXED_FONT_ROW_ALIGNMENT",
                    validation_class="semantic",
                    category="layout",
                    message="混合字号文本行没有按底部对齐。",
                    expected={"alignItems": "bottom"},
                    actual=component.props.get("alignItems"),
                    component_id=component.component_id,
                    property_path="/alignItems",
                    legacy_message=(
                        f"component {component.component_id}: a Row containing mixed "
                        "Text font sizes must use alignItems bottom so every visible "
                        "text bottom aligns."
                    ),
                ),
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
            expected_padding = min(
                8,
                max(
                    0,
                    int(math.ceil((max_font_size - child_font_size) / 4)),
                ),
            )
            if actual_padding == expected_padding:
                continue
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_MIXED_FONT_PADDING",
                    validation_class="semantic",
                    category="layout",
                    message="混合字号行中的较小文本缺少正确的底部补偿。",
                    expected={"bottomPadding": expected_padding},
                    actual=child.props.get("padding"),
                    component_id=child.component_id,
                    property_path="/padding",
                    legacy_message=(
                        f"component {child.component_id}: smaller Text in mixed-size Row "
                        f"{component.component_id} must use padding.bottom "
                        f"{expected_padding} to compensate the visible glyph baseline "
                        'after Row alignItems "bottom" aligns the Text boxes.'
                    ),
                ),
            )


def _numeric_hero_pressure_text(schema: dict[str, Any], path: str) -> str:
    node = _schema_node_at_path(schema, path) if path else None
    candidates: list[int | float] = []
    if isinstance(node, dict):
        for key in ("sampleValue", "minimum", "maximum"):
            value = node.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                candidates.append(value)
    if not candidates:
        return "999"

    integer_digits = 3
    decimal_digits = 0
    has_negative = False
    for candidate in candidates:
        has_negative = has_negative or candidate < 0
        rendered = str(abs(candidate))
        if "e" in rendered.casefold():
            rendered = f"{abs(candidate):f}".rstrip("0").rstrip(".")
        integer, separator, fraction = rendered.partition(".")
        integer_digits = max(integer_digits, len(integer))
        if separator:
            decimal_digits = max(decimal_digits, len(fraction))

    pressure = "9" * integer_digits
    if decimal_digits:
        pressure += "." + "9" * decimal_digits
    if has_negative:
        pressure = "-" + pressure
    return pressure


def _collect_primary_value_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    data_model_schema: dict[str, Any],
    errors: list[str],
) -> HeroTextAnalysis:
    numeric_paths: dict[str, str | None] = {}
    formatted_hero_ids: set[str] = set()
    for component in components:
        if component.component_type != "Text":
            continue
        font_size = _non_negative_number(component.props.get("fontSize"))
        if font_size is None or font_size <= 18:
            continue
        path = _pure_numeric_binding_path(
            component.props.get("content"),
            data_model_schema,
        )
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
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_PRIMARY_TEXT_ELIGIBILITY",
                validation_class="semantic",
                category="layout",
                message="大字号文本不满足当前支持的主内容条件。",
                expected={
                    "eligibility": (
                        "纯数值或受支持的主内容；格式化测量值须满足真实单位、"
                        "字号、容器和文本预算约束"
                    ),
                    "ordinaryTextMaximumFontSize": 18,
                    "formattedMeasurementFontSizes": [20, 24],
                },
                actual={"fontSize": font_size, "props": component.props},
                component_id=component.component_id,
                property_path="/fontSize",
                legacy_message=(
                    f"component {component.component_id}: fontSize {_format_vp(font_size)} "
                    "requires a pure number/integer or a supported primary value. "
                    "A directly bound measurement with a declared unit may use 20/24fp "
                    "in a full-width area or 2x4 large panel when its text budget fits; "
                    "ordinary names, dates, times, and statuses remain at most 18fp."
                ),
            ),
        )
    return HeroTextAnalysis(numeric_paths, formatted_hero_ids)


def _collect_numeric_unit_alignment_errors(
    component: ComponentRow,
    value: ComponentRow,
    suffix: ComponentRow,
    value_font_size: float | None,
    errors: list[str],
) -> None:
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
    has_intrinsic_width = value.props.get("width") is None and suffix.props.get("width") is None
    suffix_font_size = _non_negative_number(suffix.props.get("fontSize"))
    expected_unit_padding = 0
    if value_font_size is not None and suffix_font_size is not None:
        expected_unit_padding = min(
            8,
            max(
                0,
                int(math.ceil((value_font_size - suffix_font_size) / 4)),
            ),
        )
    has_valid_alignment = (
        component.props.get("alignItems") == "bottom"
        and unit_bottom_padding == expected_unit_padding
        and has_valid_height
        and has_compact_spacing
        and has_intrinsic_width
    )
    if not has_valid_alignment:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_NUMERIC_UNIT_ALIGNMENT",
                validation_class="semantic",
                category="layout",
                message="数值与单位的行布局不满足基线补偿和紧凑宽高约束。",
                expected={
                    "alignItems": "bottom",
                    "unitBottomPadding": expected_unit_padding,
                    "unitMaximumHeight": 24,
                    "maximumItemMargin": 4,
                    "intrinsicTextWidths": True,
                },
                actual={"row": component.props, "value": value.props, "unit": suffix.props},
                component_id=component.component_id,
                legacy_message=(
                    f"component {component.component_id}: numeric value "
                    f"and unit {suffix.component_id} must use Row alignItems "
                    '"bottom"; the unit must use capped visual bottom padding '
                    "for its font-size difference and must not use the "
                    "numeric value's fixed height; both Text nodes must use "
                    "intrinsic width and their Row itemMargin must not exceed 4."
                ),
            ),
        )
