# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""TaskSpec-aware validation for Design Compact DSL before A2UI conversion."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from services.compact_component_bindings import collect_compact_component_binding_errors
from services.compact_component_runtime import VISUAL_RECIPE_VERSION
from services.compact_dsl_a2ui_converter import (
    MODEL_COMPACT_INPUT_COMPONENT_TYPES,
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    build_compact_data_model,
    expand_high_level_component_rows,
    parse_compact_dsl_rows,
    validate_single_line_title_layout,
)
from services.compact_layout_runtime import (
    CompactLayoutRuntimeError,
    match_compact_layout,
)
from services.compact_reference_canvas import reference_dimension

_EXPRESSION_PATTERN = re.compile(r"^\{\{\s*(?P<body>.*?)\s*\}\}$")
_REFERENCE_PATTERN = re.compile(r"\$\{(?P<path>[^{}]*)\}")
_STRING_LITERAL_PATTERN = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")
_SIMPLE_FORMATTED_EXPRESSION_PATTERN = re.compile(
    r"^\{\{\s*\$\{(?P<path>/[^{}]+)\}\s*\+\s*'(?P<unit>[^']+)'\s*\}\}$"
)
_NON_EMPTY_CONTAINER_TYPES = frozenset({"Row", "Column", "Stack"})
_VISUAL_RECIPE_MARKER_PREFIX = f"{VISUAL_RECIPE_VERSION}:"
_TWO_BY_FOUR_MULTI_LARGE_WIDTH = 132
_TWO_BY_FOUR_MULTI_LARGE_HEIGHT = 126
_TWO_BY_FOUR_MULTI_INNER_WIDTH = 116
_NUMERIC_SCHEMA_TYPES = frozenset({"integer", "number"})
_COMMON_DISPLAY_UNITS = frozenset(
    {
        "%",
        "°C",
        "℃",
        "°F",
        "天",
        "小时",
        "分钟",
        "分",
        "秒",
        "毫秒",
        "步",
        "次",
        "件",
        "个",
        "条",
        "项",
        "人",
        "级",
        "公里",
        "千米",
        "米",
        "厘米",
        "毫米",
        "km",
        "m",
        "cm",
        "mm",
        "kg",
        "g",
        "mg",
        "kcal",
        "千卡",
        "cal",
        "mL",
        "ml",
        "L",
        "A",
        "mA",
        "V",
        "W",
        "kW",
        "kWh",
        "bpm",
        "次/分钟",
        "mV",
        "μA",
        "uA",
        "kHz",
        "MHz",
        "Pa",
        "kPa",
        "Wh",
        "MB",
        "GB",
        "TB",
        "km/h",
        "m/s",
    }
)


def _uses_visual_recipe(component: ComponentRow) -> bool:
    marker = component.props.get("_visualRecipe")
    return isinstance(marker, str) and marker.startswith(_VISUAL_RECIPE_MARKER_PREFIX)


def _uses_visual_recipe_part(component: ComponentRow, part: str) -> bool:
    marker = component.props.get("_visualRecipe")
    return marker == f"{_VISUAL_RECIPE_MARKER_PREFIX}{part}"


_MEASUREMENT_DESCRIPTION_MARKERS = (
    "温度",
    "电量",
    "电池电量",
    "剩余电量",
    "占比",
    "比例",
    "电流",
    "电压",
    "功率",
    "频率",
    "速度",
    "距离",
    "容量",
    "湿度",
    "压力",
    "海拔",
    "重量",
    "体重",
    "长度",
    "宽度",
    "高度",
)
_MEASUREMENT_SAMPLE_PATTERN = re.compile(
    r"[+-]?\d+(?:\.\d+)?\s*(?:°C|℃|°F|mA|μA|uA|A|mV|V|kW|W|kWh|Wh|MHz|kHz|Hz|"
    r"km/h|m/s|km|千米|公里|m|米|cm|厘米|mm|毫米|kg|g|mg|MB|GB|TB|Pa|kPa|%|"
    r"毫秒|小时|分钟|分|秒)$"
)

_AMBIGUOUS_METRIC_DESCRIPTION_MARKERS = (
    "指数",
    "等级",
    "评分",
    "得分",
    "概率",
    "风险",
    "质量",
    "健康",
)
_AMBIGUOUS_STATUS_MARKERS = (
    "良",
    "中等",
    "低",
    "高",
    "正常",
    "异常",
    "未知",
    "未充电",
    "已充电",
    "未连接",
    "已连接",
)
@dataclass(frozen=True)
class CompactDslValidationResult:
    """Compact DSL validation warnings returned to the generation pipeline."""

    warnings: tuple[str, ...] = ()


class CompactDslValidationError(ValueError):
    """One or more Compact DSL contract violations."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(dict.fromkeys(errors))
        details = "\n".join(f"- {message}" for message in self.errors)
        super().__init__(f"Compact DSL validation failed:\n{details}")


def validate_compact_dsl(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    protocol_profile: dict[str, Any] | None = None,
    layout_scope: str | None = None,
    enforce_model_component_types: bool = False,
    allow_internal_components: bool = False,
) -> CompactDslValidationResult:
    """Validate expressions, first-frame data, and TaskSpec data boundaries."""
    try:
        rows = parse_compact_dsl_rows(
            compact_dsl, allow_internal_components=allow_internal_components,
        )
    except CompactDslConversionError as exc:
        raise CompactDslValidationError([str(exc)]) from exc

    components = [row for row in rows if isinstance(row, ComponentRow)]
    if enforce_model_component_types:
        unsupported_model_components = [
            row
            for row in components
            if row.component_type not in MODEL_COMPACT_INPUT_COMPONENT_TYPES
        ]
        if unsupported_model_components:
            errors = [
                (
                    f"component {row.component_id}: {row.component_type} is converter-internal "
                    "and cannot be generated directly; use a semantic Compact component."
                )
                for row in unsupported_model_components
            ]
            raise CompactDslValidationError(errors)
    data_rows = [row for row in rows if isinstance(row, DataRow)]
    data_model = build_compact_data_model(data_rows)
    size = card_spec.get("suggestSize") or task_spec.get("size")
    layout_errors: list[str] = []
    if layout_scope is not None:
        if not isinstance(size, str):
            layout_errors.append(
                "Compact layout validation requires a valid widget size."
            )
        else:
            try:
                match_compact_layout(
                    components,
                    size=size,
                    layout_scope=layout_scope,
                )
            except CompactLayoutRuntimeError as exc:
                layout_errors.append(str(exc))
    binding_contract_errors = _compact_component_binding_errors(
        components,
        task_spec.get("dataModelSchema"),
    )
    if binding_contract_errors:
        raise CompactDslValidationError([*layout_errors, *binding_contract_errors])
    try:
        components = expand_high_level_component_rows(
            components,
            size=size,
            data_model=data_model,
        )
    except CompactDslConversionError as exc:
        raise CompactDslValidationError([str(exc)]) from exc
    binding_paths: list[str] = []
    visible_binding_paths: list[str] = []
    errors: list[str] = []
    _collect_asset_source_errors(components, task_spec, errors)
    _collect_component_contract_errors(components, task_spec, errors)
    _collect_ambiguous_metric_text_errors(components, task_spec, errors)
    _collect_semantic_text_errors(components, task_spec, errors)
    _collect_raw_boolean_text_errors(components, task_spec, errors)
    _collect_progress_value_errors(components, task_spec, errors)
    _collect_progress_readout_object_errors(components, task_spec, errors)
    _collect_unbound_action_hint_errors(components, errors)
    _collect_height_budget_errors(components, task_spec, card_spec, errors, protocol_profile)
    for component in components:
        location = f"component {component.component_id}.props"
        _collect_binding_context(
            component.props,
            location,
            binding_paths,
            errors,
        )
        visible_props = {key: value for key, value in component.props.items() if key != "onClick"}
        _collect_binding_context(
            visible_props,
            location,
            visible_binding_paths,
            [],
        )

    _collect_data_context_errors(
        binding_paths,
        data_rows,
        data_model,
        task_spec,
        errors,
    )
    errors.extend(layout_errors)
    if errors:
        raise CompactDslValidationError(errors)

    warnings = _unused_data_capability_warnings(binding_paths, card_spec)
    return CompactDslValidationResult(warnings=tuple(warnings))


def _compact_component_binding_errors(
    components: list[ComponentRow],
    data_model_schema: Any,
) -> list[str]:
    def schema_type_for_path(path: str) -> str | None:
        return _schema_type(_schema_node_at_path(data_model_schema, path))

    errors: list[str] = []
    resolver = schema_type_for_path if isinstance(data_model_schema, dict) else None
    for component in components:
        errors.extend(
            collect_compact_component_binding_errors(
                component.component_id,
                component.component_type,
                component.props,
                schema_type_resolver=resolver,
            )
        )
    return errors


def _collect_asset_source_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    """转换前只接受模型输入中的原始静态素材路径，不提前放行交付 URL。"""
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return
    sources: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        src = candidate.get("src")
        if isinstance(src, str):
            sources.add(src)
    for component in components:
        for key in ("backgroundImage",):
            value = component.props.get(key)
            if not isinstance(value, str) or value.strip().startswith("{{"):
                continue
            if value not in sources:
                errors.append(
                    f"component {component.component_id}.props.{key}: "
                    "asset must use an original src from TaskSpec.assetCandidates."
                )

def _collect_hero_value_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    components_by_id = {component.component_id: component for component in components}
    # 与质量阶段使用相同的有效模板根标记，仅豁免主文字校验。
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
        _collect_mixed_font_row_alignment_errors(
            components,
            components_by_id,
            errors,
        )

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
        errors.append(
            f"component {component.component_id}: fontSize {_format_vp(font_size)} "
            "requires a pure number/integer or a supported primary value. "
            "A directly bound measurement with a declared unit may use 20/24fp "
            "in a full-width area or 2x4 large panel when its text budget fits; "
            "ordinary names, dates, times, and statuses remain at most 18fp."
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
                        f"component {component.component_id}: formatted value "
                        f"{child_id} already contains its unit; do not append "
                        f"Text {suffix.component_id} or a field label."
                    )
                continue
            if child_id not in numeric_paths:
                continue
            numeric_path = numeric_paths[child_id]
            if suffix is None or suffix.component_type != "Text":
                continue
            content = suffix.props.get("content")
            if _is_allowed_display_unit(
                content,
                numeric_path or "",
                data_model_schema,
            ):
                continue
            value_source = numeric_path or "the preceding value"
            errors.append(
                f"component {component.component_id}: Text {suffix.component_id} "
                f"after the large numeric value must contain only a real unit for "
                f"{value_source}. Move labels or descriptions to a separate line."
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


def _is_large_2x4_panel(
    component: ComponentRow,
    components: list[ComponentRow],
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
    component: ComponentRow,
    components: list[ComponentRow],
    width: float,
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
                and parent.props.get("padding", 0) == 0
            ):
                return True
            pending.append(parent.component_id)
    return False


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
    if temperature or duration or percentage or measurement:
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


def _pure_numeric_binding_path(
    content: Any,
    data_model_schema: dict[str, Any],
) -> str | None:
    path = _pure_binding_path(content)
    if path is None:
        return None
    if path == "":
        return path
    schema_node = _schema_node_at_path(data_model_schema, path)
    if _schema_type(schema_node) not in _NUMERIC_SCHEMA_TYPES:
        return None
    return path


def _pure_binding_path(content: Any) -> str | None:
    if isinstance(content, dict) and set(content) == {"path"}:
        candidate = content.get("path")
        return candidate if isinstance(candidate, str) else None
    if not isinstance(content, str):
        return None
    match = _EXPRESSION_PATTERN.fullmatch(content.strip())
    if match is not None:
        reference = _REFERENCE_PATTERN.fullmatch(match.group("body").strip())
        return reference.group("path").strip() if reference is not None else None
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", content.strip()):
        return ""
    return None


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
                and schema_type not in _NUMERIC_SCHEMA_TYPES
            ):
                errors.append(
                    f"component {component.component_id}: large primary Text "
                    f"{value.component_id} binds non-numeric field {value_path} "
                    f"and must occupy its own row; do not append "
                    f"{suffix.component_id} as a unit or label."
                )
                continue
            unit = suffix_content.strip()
            if schema_type in _NUMERIC_SCHEMA_TYPES:
                is_known_unit = unit in _COMMON_DISPLAY_UNITS
                if value_path:
                    is_known_unit = _is_allowed_display_unit(
                        suffix_content,
                        value_path,
                        data_model_schema,
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
                    errors.append(
                        f"component {component.component_id}: numeric value "
                        f"and unit {suffix.component_id} must use Row alignItems "
                        '"bottom"; the unit must use capped visual bottom padding '
                        "for its font-size difference and must not use the "
                        "numeric value's fixed height; both Text nodes must use "
                        "intrinsic width and their Row itemMargin must not exceed 4."
                    )
                continue
            if unit not in _COMMON_DISPLAY_UNITS:
                continue
            errors.append(
                f"component {component.component_id}: display unit {unit!r} cannot "
                f"follow non-numeric binding {value_path}. Remove the unit or bind "
                "a number/integer value."
            )


def _is_allowed_display_unit(
    content: Any,
    numeric_path: str,
    data_model_schema: dict[str, Any],
) -> bool:
    if not isinstance(content, str):
        return False
    unit = content.strip()
    if not unit:
        return False
    if unit in _COMMON_DISPLAY_UNITS:
        return True
    schema_node = _schema_node_at_path(data_model_schema, numeric_path)
    if not isinstance(schema_node, dict):
        return False
    description = schema_node.get("description")
    return isinstance(description, str) and unit in description


def _collect_mixed_font_row_alignment_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
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
                f"component {component.component_id}: a Row containing mixed "
                "Text font sizes must use alignItems bottom so every visible "
                "text bottom aligns."
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
            errors.append(
                f"component {child.component_id}: smaller Text in mixed-size Row "
                f"{component.component_id} must use padding.bottom "
                f"{expected_padding} to compensate the visible glyph baseline "
                'after Row alignItems "bottom" aligns the Text boxes.'
            )


def _component_content_paths(component: ComponentRow) -> list[str]:
    paths: list[str] = []
    _collect_binding_context(
        component.props.get("content"),
        f"component {component.component_id}.props.content",
        paths,
        [],
    )
    return paths


def _collect_raw_boolean_text_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return
    for component in components:
        if component.component_type != "Text":
            continue
        boolean_paths: list[str] = []
        for path in _component_content_paths(component):
            schema_node = _schema_node_at_path(data_model_schema, path)
            if _schema_type(schema_node) == "boolean":
                boolean_paths.append(path)
        if not boolean_paths:
            continue
        content = component.props.get("content")
        if isinstance(content, str) and "?" in content:
            continue
        errors.append(
            f"component {component.component_id}: boolean field(s) "
            f"{', '.join(boolean_paths)} must be mapped to user-facing Text "
            "with a conditional expression; do not display raw true/false."
        )


def _collect_progress_value_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return
    for component in components:
        if component.component_type != "Progress":
            continue
        value_path = _pure_binding_path(component.props.get("value"))
        if not value_path:
            continue
        if value_path.startswith("/__display/") and value_path.endswith(
            "/progressValue"
        ):
            continue
        schema_type = _schema_type(_schema_node_at_path(data_model_schema, value_path))
        if schema_type in _NUMERIC_SCHEMA_TYPES:
            continue
        errors.append(
            f"component {component.component_id}: Progress.value path "
            f"{value_path} has schema type {schema_type or 'unknown'}; bind a "
            "number/integer field such as 68, not formatted text such as "
            "'68%'. If only formatted text exists, remove Progress and show "
            "the complete value with Text."
        )


def _data_business_root(path: str | None) -> str | None:
    root = None
    if path:
        parts = path.split("/")
        if len(parts) >= 4 and parts[1] == "data":
            root = f"/data/{parts[2]}"
    return root


def _progress_readout_root(component: ComponentRow, schema: dict[str, Any]) -> str | None:
    """只识别单字段动态读数，不把动态名称、标签或多字段摘要当配对证据。"""
    root = None
    if component.component_type == "Text":
        paths = _component_content_paths(component)
        if len(paths) == 1:
            path = paths[0]
            node = _schema_node_at_path(schema, path)
            sample = node.get("sampleValue") if isinstance(node, dict) else None
            numeric = _schema_type(node) in _NUMERIC_SCHEMA_TYPES
            formatted = isinstance(sample, str) and bool(
                _MEASUREMENT_SAMPLE_PATTERN.fullmatch(sample.strip())
            )
            if numeric or formatted:
                root = _data_business_root(path)
    return root


def _collect_progress_readout_object_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    """阻止进度与直接同组读数明确来自不同业务根；不猜测远端分区或同根指标。"""
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return
    components_by_id = {component.component_id: component for component in components}
    for parent in components:
        if parent.component_type not in {"Row", "Column", "Stack"}:
            continue
        readout_roots: set[str] = set()
        progresses: list[ComponentRow] = []
        for child_id in parent.children:
            child = components_by_id.get(child_id)
            if child is None:
                continue
            root = _progress_readout_root(child, schema)
            if root is not None:
                readout_roots.add(root)
            if child.component_type == "Progress":
                progresses.append(child)
        if not readout_roots:
            continue
        for progress in progresses:
            value_path = _pure_binding_path(progress.props.get("value"))
            value_root = _data_business_root(value_path)
            if value_root is None or value_root in readout_roots:
                continue
            errors.append(
                f"component {progress.component_id}: Progress.value {value_path} belongs to "
                f"{value_root}, but the direct sibling readout(s) in {parent.component_id} "
                f"belong to {', '.join(sorted(readout_roots))}. Keep progress and its readout "
                "on the same object; if that object has no numeric field, omit its progress "
                "and retain its complete text. Do not borrow another object's value."
            )


def _is_ambiguous_metric_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    description = node.get("description")
    sample = node.get("sampleValue")
    if not isinstance(description, str) or not any(
        marker in description
        for marker in _AMBIGUOUS_METRIC_DESCRIPTION_MARKERS
        if marker != "概率"
    ):
        return False
    if isinstance(sample, (int, float)) and not isinstance(sample, bool):
        return True
    return isinstance(sample, str) and 0 < len(sample.strip()) <= 8


def _static_text_fragments(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    if "{{" not in value:
        return value.strip()
    fragments: list[str] = []
    for literal in _STRING_LITERAL_PATTERN.findall(value):
        fragments.append(literal[1:-1].strip())
    return " ".join(fragment for fragment in fragments if fragment)


def _nearby_text_context(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> str:
    fragments = [_static_text_fragments(component.props.get("content"))]
    parent_id = parent_by_child.get(component.component_id)
    parent = components_by_id.get(parent_id) if parent_id else None
    if parent is None:
        return " ".join(fragment for fragment in fragments if fragment)
    for sibling_id in parent.children:
        if sibling_id == component.component_id:
            continue
        sibling = components_by_id.get(sibling_id)
        if sibling is None or sibling.component_type != "Text":
            continue
        fragments.append(_static_text_fragments(sibling.props.get("content")))
    return " ".join(fragment for fragment in fragments if fragment)


def _has_dangling_range_separator(content: Any) -> bool:
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    if "{{" not in stripped:
        return stripped.endswith(("-", "~", "～", "至", "–", "—"))
    match = _EXPRESSION_PATTERN.match(stripped)
    if match is None:
        return False
    body = match.group("body").rstrip()
    return bool(re.search(r"(?:'|\")\s*(?:-|~|～|至|–|—)\s*(?:'|\")\s*$", body))


def _collect_semantic_text_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    components_by_id = {component.component_id: component for component in components}
    parent_by_child: dict[str, str] = {}
    for parent in components:
        for child_id in parent.children:
            parent_by_child[child_id] = parent.component_id

    for component in components:
        if component.component_type != "Text":
            continue
        content = component.props.get("content")
        if _has_dangling_range_separator(content):
            errors.append(
                f"component {component.component_id}: time/date range ends with "
                "a dangling separator. Bind both start and end values, or remove "
                "the separator and display the available value only."
            )

        paths = _component_content_paths(component)
        normalized_paths = [path.casefold() for path in paths]
        own_text = _static_text_fragments(content)
        nearby_text = _nearby_text_context(
            component,
            parent_by_child,
            components_by_id,
        )
        if any(path.endswith("/eventcount") for path in normalized_paths):
            has_range_context = any(
                marker in own_text for marker in ("未来", "接下来", "近", "今天", "明天", "本周")
            )
            has_schedule_context = any(marker in own_text for marker in ("安排", "日程", "会议"))
            if not has_range_context or not has_schedule_context:
                errors.append(
                    f"component {component.component_id}: calendar eventCount "
                    "must not be shown as a standalone number or unit. Combine it "
                    "with its time scope and schedule meaning, for example "
                    "未来7天 2项安排, inside the calendar region."
                )

        has_reminder_path = any(
            "remindtime" in path or "remindminutes" in path for path in normalized_paths
        )
        if has_reminder_path and not any(marker in nearby_text for marker in ("分钟", "分")):
            errors.append(
                f"component {component.component_id}: reminder value must keep "
                "its minute semantics, such as 提前 15 分钟; do not display a "
                "bare numeric reminder value."
            )

        has_wind_level_path = any(path.endswith("/windlevel") for path in normalized_paths)
        if has_wind_level_path and "风力" not in nearby_text:
            errors.append(
                f"component {component.component_id}: windLevel must include the "
                "metric label 风力, for example 风力 2级; do not show a bare 2级."
            )


def _collect_unbound_action_hint_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    components_by_id = {component.component_id: component for component in components}
    parent_by_child: dict[str, str] = {}
    for parent in components:
        for child_id in parent.children:
            parent_by_child[child_id] = parent.component_id

    action_prefixes = (
        "点击",
        "点一下",
        "点此",
        "一键",
        "打开",
        "查看",
        "设置",
        "导航",
        "拨打",
        "进入",
    )
    for component in components:
        if component.component_type != "Text":
            continue
        text = _static_text_fragments(component.props.get("content"))
        if not text.startswith(action_prefixes):
            continue
        current: ComponentRow | None = component
        has_click_ancestor = False
        while current is not None:
            if current.props.get("onClick"):
                has_click_ancestor = True
                break
            parent_id = parent_by_child.get(current.component_id)
            current = components_by_id.get(parent_id) if parent_id else None
        if has_click_ancestor:
            continue
        errors.append(
            f"component {component.component_id}: action-like Text {text!r} has "
            "no clickable ancestor. Bind the matching event to its action slot "
            "or remove the action wording."
        )


def _has_nearby_metric_label(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> bool:
    def has_metric_label(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if "{{" in value:
            candidates = [match[1:-1].strip() for match in _STRING_LITERAL_PATTERN.findall(value)]
        else:
            candidates = [value.strip()]
        return any(
            len(candidate) >= 2
            and candidate not in _AMBIGUOUS_STATUS_MARKERS
            and candidate not in _COMMON_DISPLAY_UNITS
            for candidate in candidates
        )

    if has_metric_label(component.props.get("content")):
        return True

    current = component.component_id
    for _ in range(3):
        parent_id = parent_by_child.get(current)
        parent = components_by_id.get(parent_id) if parent_id else None
        if parent is None:
            return False
        for sibling_id in parent.children:
            if sibling_id == current:
                continue
            sibling = components_by_id.get(sibling_id)
            text = (
                sibling.props.get("content")
                if sibling and sibling.component_type == "Text"
                else None
            )
            if has_metric_label(text):
                return True
        current = parent.component_id
    return False


def _collect_ambiguous_metric_text_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    components_by_id = {component.component_id: component for component in components}
    parent_by_child = {
        child_id: parent.component_id for parent in components for child_id in parent.children
    }
    for component in components:
        if component.component_type != "Text":
            continue
        if _uses_visual_recipe_part(component, "ProgressLine2.value"):
            continue
        paths: list[str] = []
        _collect_binding_context(
            component.props.get("content"),
            f"component {component.component_id}.props.content",
            paths,
            [],
        )
        for path in paths:
            node = _schema_node_at_path(task_spec.get("dataModelSchema"), path)
            if _is_ambiguous_metric_node(node) and not _has_nearby_metric_label(
                component, parent_by_child, components_by_id
            ):
                detail = node.get("description") if isinstance(node, dict) else path
                errors.append(
                    f"component {component.component_id}: value {path} has ambiguous meaning "
                    f"({detail}); add a nearby metric label such as 感冒指数、紫外线指数 "
                    "or 睡眠得分 instead of showing the value alone."
                )
                break


def _collect_component_contract_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    _collect_component_parent_errors(components, errors)
    try:
        validate_single_line_title_layout(components, size=task_spec.get("size"))
    except CompactDslConversionError as exc:
        errors.append(str(exc))
    allowed_handlers = _task_event_handlers(task_spec)
    for component in components:
        _collect_container_errors(component, errors)
        _collect_on_click_errors(component, allowed_handlers, errors)


def _collect_component_parent_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child: dict[str, str] = {}
    for component in components:
        children_seen: set[str] = set()
        for child_id in component.children:
            if child_id in children_seen:
                errors.append(
                    f"component {component.component_id}.children references "
                    f"{child_id} more than once."
                )
                continue
            children_seen.add(child_id)
            existing_parent = parent_by_child.get(child_id)
            if existing_parent is None:
                parent_by_child[child_id] = component.component_id
                continue
            if existing_parent == component.component_id:
                continue
            errors.append(
                f"component {child_id} has multiple parents: {existing_parent} "
                f"and {component.component_id}. Each component may appear in "
                "exactly one parent children list."
            )


def _collect_container_errors(
    component: ComponentRow,
    errors: list[str],
) -> None:
    if component.component_type not in _NON_EMPTY_CONTAINER_TYPES:
        return
    if component.children:
        return
    errors.append(
        f"component {component.component_id}: {component.component_type}.children "
        "must be non-empty; use parent itemMargin, padding, or layout alignment "
        "instead of an empty spacer container."
    )


def _collect_height_budget_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    errors: list[str],
    protocol_profile: dict[str, Any] | None = None,
) -> None:
    """Reject vertical layouts whose declared minimum height cannot fit."""
    components_by_id = {component.component_id: component for component in components}
    for component in components:
        if component.component_type != "Column":
            continue
        available_height = _component_available_height(
            component,
            task_spec,
            card_spec,
            protocol_profile,
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
        errors.append(
            f"component {component.component_id}: vertical layout requires at least "
            f"{_format_vp(required_height)}vp within {_format_vp(available_height)}vp; "
            f"it overflows by {_format_vp(overflow)}vp. Reduce child heights, margins, "
            "or gaps instead of relying on clipping, flex shrink, or distributed alignment."
        )


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
    if component.component_type == "SingleLineTitle":
        return 20.0
    shrink = _non_negative_number(component.props.get("flexShrink"))
    weight = _non_negative_number(component.props.get("layoutWeight"))
    if (shrink is not None and shrink > 0) or (weight is not None and weight > 0):
        constraints = component.props.get("constraintSize")
        minimum = constraints.get("minHeight") if isinstance(constraints, dict) else None
        return _non_negative_number(minimum) or 0.0
    explicit_height = _non_negative_number(component.props.get("height"))
    if explicit_height is not None:
        return explicit_height
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

    if component.component_type == "Column":
        content_height = sum(child_heights)
        content_height += _vertical_gap(component, len(child_heights))
    else:
        content_height = max(child_heights, default=0.0)
    return _vertical_padding(component.props) + content_height


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


def _collect_on_click_errors(
    component: ComponentRow,
    allowed_handlers: list[dict[str, Any]],
    errors: list[str],
) -> None:
    if "onClick" not in component.props:
        return
    location = f"component {component.component_id}.props.onClick"
    handlers = component.props.get("onClick")
    if not isinstance(handlers, list) or len(handlers) != 1:
        errors.append(f"{location}: onClick must contain exactly one handler.")
        return
    handler = handlers[0]
    if not isinstance(handler, dict):
        errors.append(f"{location}[0]: handler must be an object.")
        return
    if set(handler) != {"call", "args"}:
        errors.append(f"{location}[0]: handler must contain only call and args.")
        return
    call = handler.get("call")
    args = handler.get("args")
    if not isinstance(call, str) or not call.strip():
        errors.append(f"{location}[0].call: call must be a non-empty string.")
        return
    if not isinstance(args, dict):
        errors.append(f"{location}[0].args: args must be an object.")
        return
    if handler not in allowed_handlers:
        errors.append(f"{location}[0]: handler must exactly match a TaskSpec eventCandidate.")


def _task_event_handlers(task_spec: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return []
    handlers: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        handler = _event_handler_from_candidate(candidate)
        if handler is not None:
            handlers.append(handler)
    return handlers


def _event_handler_from_candidate(
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    source = candidate
    call = source.get("call")
    args = source.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        nested_action = candidate.get("action")
        if not isinstance(nested_action, dict):
            return None
        source = nested_action
        call = source.get("call")
        args = source.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    return {"call": call, "args": args}


def _collect_binding_context(
    value: Any,
    location: str,
    binding_paths: list[str],
    errors: list[str],
) -> None:
    if isinstance(value, str):
        _collect_expression_context(value, location, binding_paths, errors)
        return
    if isinstance(value, dict):
        if set(value) == {"path"}:
            _collect_path_binding(
                value.get("path"),
                location,
                binding_paths,
                errors,
            )
            return
        for key, child_value in value.items():
            _collect_binding_context(
                child_value,
                f"{location}.{key}",
                binding_paths,
                errors,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_binding_context(
                item,
                f"{location}[{index}]",
                binding_paths,
                errors,
            )


def _collect_expression_context(
    value: str,
    location: str,
    binding_paths: list[str],
    errors: list[str],
) -> None:
    markers = ("{{", "}}", "${")
    if not any(marker in value for marker in markers):
        return

    stripped = value.strip()
    match = _EXPRESSION_PATTERN.fullmatch(stripped)
    has_one_opening = stripped.count("{{") == 1
    has_one_closing = stripped.count("}}") == 1
    if match is None or not has_one_opening or not has_one_closing:
        errors.append(
            f"{location}: expression must occupy the full string as "
            '"{{ ... }}" and contain exactly one wrapper.'
        )
        return

    body = match.group("body").strip()
    quoted_paths = _quoted_expression_paths(body)
    for path in quoted_paths:
        errors.append(
            f'{location}: expression wraps quoted JSON Pointer "{path}"; '
            f"use ${{{path}}} for a dynamic binding, or use a plain "
            "static value without {{ }}."
        )

    references = list(_REFERENCE_PATTERN.finditer(body))
    if not references:
        if not quoted_paths:
            errors.append(
                f"{location}: expression has no ${{/json/pointer}} reference; "
                "use a plain static value instead."
            )
        return

    if body.count("${") != len(references):
        errors.append(f"{location}: expression contains an incomplete ${{...}} reference.")
    for reference in references:
        path = reference.group("path").strip()
        if not _is_json_pointer(path):
            errors.append(
                f'{location}: expression reference "{path}" must be an absolute JSON Pointer.'
            )
            continue
        binding_paths.append(path)


def _quoted_expression_paths(body: str) -> list[str]:
    """Collect JSON Pointer-looking string literals from an expression body."""
    paths: list[str] = []
    index = 0
    while index < len(body):
        quote = body[index]
        if quote not in {"'", '"'}:
            index += 1
            continue

        index += 1
        literal: list[str] = []
        escaped = False
        while index < len(body):
            char = body[index]
            index += 1
            if escaped:
                literal.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char != quote:
                literal.append(char)
                continue

            candidate = "".join(literal)
            is_binding_path = candidate in {"/data", "/state"}
            is_binding_descendant = candidate.startswith(("/data/", "/state/"))
            if (is_binding_path or is_binding_descendant) and candidate not in paths:
                paths.append(candidate)
            break
    return paths


def _collect_path_binding(
    path: Any,
    location: str,
    binding_paths: list[str],
    errors: list[str],
) -> None:
    if not isinstance(path, str) or not _is_json_pointer(path):
        errors.append(f"{location}: PathBinding.path must be an absolute JSON Pointer.")
        return
    binding_paths.append(path)


def _collect_data_context_errors(
    binding_paths: list[str],
    data_rows: list[DataRow],
    data_model: dict[str, Any],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    for path in dict.fromkeys(binding_paths):
        if not _json_pointer_exists(data_model, path):
            errors.append(f"{path}: binding path has no matching Compact DSL data row.")

    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        errors.append("TaskSpec.dataModelSchema must be an object.")
        return

    paths_to_validate = list(dict.fromkeys(binding_paths))
    paths_to_validate.extend(row.path for row in data_rows)
    for path in dict.fromkeys(paths_to_validate):
        _collect_undeclared_data_path_error(path, data_model_schema, errors)
    for row in data_rows:
        _collect_data_type_error(row, data_model_schema, errors)


def _collect_undeclared_data_path_error(
    path: str,
    data_model_schema: dict[str, Any],
    errors: list[str],
) -> None:
    if not _is_task_data_path(path):
        return
    if _schema_node_at_path(data_model_schema, path) is not None:
        return
    errors.append(
        f"{path}: path is not declared by TaskSpec.dataModelSchema; "
        "remove it or use a declared field."
    )


def _collect_data_type_error(
    row: DataRow,
    data_model_schema: dict[str, Any],
    errors: list[str],
) -> None:
    if not _is_task_data_path(row.path):
        return
    schema_node = _schema_node_at_path(data_model_schema, row.path)
    if schema_node is None:
        return
    expected_type = _schema_type(schema_node)
    type_matches = expected_type is None or _value_matches_schema_type(
        row.value,
        expected_type,
    )
    if type_matches:
        return
    actual_type = _json_type_name(row.value)
    errors.append(
        f"{row.path}: data row type {actual_type} does not match "
        f"schema type {expected_type} declared by TaskSpec."
    )


def _schema_node_at_path(schema: Any, path: str) -> Any | None:
    current = schema
    for token in _decode_json_pointer(path):
        current = _schema_child(current, token)
        if current is None:
            return None
    return current


def _schema_child(current: Any, token: str) -> Any | None:
    if isinstance(current, list):
        if not token.isdigit() or not current:
            return None
        index = int(token)
        if index < len(current):
            return current[index]
        return current[0]
    if not isinstance(current, dict):
        return None
    if current.get("type") == "array":
        if not token.isdigit():
            return None
        return current.get("items")
    if current.get("type") == "object":
        properties = current.get("properties")
        if isinstance(properties, dict):
            return properties.get(token)
    return current.get(token)


def _schema_type(schema_node: Any) -> str | None:
    if isinstance(schema_node, list):
        return "array"
    if not isinstance(schema_node, dict):
        return None
    schema_type = schema_node.get("type")
    return schema_type if isinstance(schema_type, str) else None


def _value_matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return True


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _unused_data_capability_warnings(
    binding_paths: list[str],
    card_spec: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for root in _card_spec_data_roots(card_spec):
        if any(_path_is_within(path, root) for path in binding_paths):
            continue
        warnings.append(f"{root}: declared data capability is not used by any component.")
    return warnings


def _card_spec_data_roots(card_spec: dict[str, Any]) -> list[str]:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return []
    roots: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        root = binding.get("writeResultTo")
        if isinstance(root, str) and root.startswith("/"):
            roots.append(root)
    return roots


def _path_is_within(path: str, root: str) -> bool:
    normalized_root = root.rstrip("/")
    return path == normalized_root or path.startswith(f"{normalized_root}/")


def _json_pointer_exists(root: dict[str, Any], path: str) -> bool:
    current: Any = root
    for token in _decode_json_pointer(path):
        if isinstance(current, dict):
            if token not in current:
                return False
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                return False
            index = int(token)
            if index >= len(current):
                return False
            current = current[index]
            continue
        return False
    return True


def _is_task_data_path(path: str) -> bool:
    return path == "/data" or path.startswith("/data/")


def _is_json_pointer(path: str) -> bool:
    return isinstance(path, str) and path.startswith("/")


def _decode_json_pointer(path: str) -> list[str]:
    if path == "/":
        return []
    if not _is_json_pointer(path):
        return []
    return [token.replace("~1", "/").replace("~0", "~") for token in path[1:].split("/")]
