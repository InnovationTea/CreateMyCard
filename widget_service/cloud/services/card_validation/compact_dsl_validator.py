# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""TaskSpec-aware validation for Design Compact DSL before A2UI conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    build_compact_data_model,
    parse_compact_dsl_rows,
    validate_card_header_layout,
    validate_timeline_unit_layout,
)

from .compact_dual_action_validator import collect_dual_action_errors
from .validation_policy import CompactRule, resolve_validation_policy

_EXPRESSION_PATTERN = re.compile(r"^\{\{\s*(?P<body>.*?)\s*\}\}$")
_REFERENCE_PATTERN = re.compile(r"\$\{(?P<path>[^{}]*)\}")
_STRING_LITERAL_PATTERN = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")
_SIMPLE_FORMATTED_EXPRESSION_PATTERN = re.compile(
    r"^\{\{\s*\$\{(?P<path>/[^{}]+)\}\s*\+\s*'(?P<unit>[^']+)'\s*\}\}$"
)
_NON_EMPTY_CONTAINER_TYPES = frozenset({"Row", "Column", "List", "Stack"})
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
    "指数", "等级", "评分", "得分", "概率", "风险", "质量", "健康",
)
_AMBIGUOUS_STATUS_MARKERS = (
    "良", "中等", "低", "高", "正常", "异常", "未知", "未充电", "已充电",
    "未连接", "已连接",
)
_FUSION_DESIGN_PREFIX = "fusion-ball-"


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
) -> CompactDslValidationResult:
    """Validate expressions, first-frame data, and TaskSpec data boundaries."""
    try:
        rows = parse_compact_dsl_rows(compact_dsl)
    except CompactDslConversionError as exc:
        raise CompactDslValidationError([str(exc)]) from exc

    components = [row for row in rows if isinstance(row, ComponentRow)]
    data_rows = [row for row in rows if isinstance(row, DataRow)]
    binding_paths: list[str] = []
    visible_binding_paths: list[str] = []
    errors: list[str] = []
    root = next((component for component in components if component.component_id == "root"), None)
    policy = resolve_validation_policy(
        root_id="root" if root is not None else None,
        root_children=root.children if root is not None else (),
        component_ids=(component.component_id for component in components),
    )
    if CompactRule.ASSET_SOURCE in policy.compact_rules:
        _collect_asset_source_errors(components, task_spec, errors)
    if CompactRule.COMPONENT_CONTRACT in policy.compact_rules:
        _collect_component_contract_errors(components, task_spec, errors)
    if CompactRule.FUSION_COMPOSITION in policy.compact_rules:
        _collect_fusion_composition_errors(components, task_spec, errors)
    if CompactRule.METRIC_LABEL in policy.compact_rules:
        _collect_ambiguous_metric_text_errors(components, task_spec, errors)
    if CompactRule.WEATHER_DATE in policy.compact_rules:
        _collect_two_by_two_weather_date_errors(components, task_spec, errors)
    if CompactRule.HERO_VALUE in policy.compact_rules:
        _collect_hero_value_errors(components, task_spec, errors)
    if CompactRule.HEIGHT_BUDGET in policy.compact_rules:
        _collect_height_budget_errors(components, task_spec, card_spec, errors)
    size = card_spec.get("suggestSize") or task_spec.get("size")
    if CompactRule.DUAL_ACTION in policy.compact_rules:
        collect_dual_action_errors(components, size, errors)
    for component in components:
        location = f"component {component.component_id}.props"
        _collect_binding_context(
            component.props,
            location,
            binding_paths,
            errors,
        )
        visible_props = {
            key: value for key, value in component.props.items() if key != "onClick"
        }
        _collect_binding_context(
            visible_props,
            location,
            visible_binding_paths,
            [],
        )

    if CompactRule.LAYOUT_ROUTE in policy.compact_rules:
        _collect_layout_route_errors(
            components,
            task_spec,
            visible_binding_paths,
            errors,
        )

    data_model = build_compact_data_model(data_rows)
    if CompactRule.DATA_CONTEXT in policy.compact_rules:
        _collect_data_context_errors(
            binding_paths,
            data_rows,
            data_model,
            task_spec,
            errors,
        )
    if errors:
        raise CompactDslValidationError(errors)

    warnings = _unused_data_capability_warnings(binding_paths, card_spec)
    return CompactDslValidationResult(warnings=tuple(warnings))


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
        keys = ["backgroundImage"]
        if component.component_type == "Image":
            keys.append("src")
        elif component.component_type in {"ActionUnit", "CardHeader"}:
            keys.append("icon")
        for key in keys:
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
    components_by_id = {
        component.component_id: component for component in components
    }
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return

    _collect_adjacent_display_unit_errors(
        components,
        components_by_id,
        data_model_schema,
        errors,
    )

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


def _collect_two_by_two_weather_date_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    if task_spec.get("size") != "2x2":
        return
    data_model_schema = task_spec.get("dataModelSchema")
    schema_data = (
        data_model_schema.get("data")
        if isinstance(data_model_schema, dict)
        else None
    )
    if not isinstance(schema_data, dict) or set(schema_data) != {"weather"}:
        return
    for component in components:
        if component.component_type != "Text":
            continue
        paths: list[str] = []
        _collect_binding_context(
            component.props.get("content"),
            f"component {component.component_id}.props.content",
            paths,
            [],
        )
        has_date = any(path.endswith("/date") for path in paths)
        has_weekday = any(path.endswith("/weekday") for path in paths)
        if not has_date or not has_weekday:
            continue
        errors.append(
            f"component {component.component_id}: 2x2 single-day weather must not "
            "concatenate date and weekday in one Text. Keep weekday by default, "
            "or keep date alone when the user explicitly requests the exact date."
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
        component_width == 126.0
        if task_spec.get("size") == "2x2"
        else component_width == 276.0
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
    temperature = temperature and re.fullmatch(
        r"[+-]?\d+(?:\.\d+)?\s*(?:°C|℃|°F)", sample
    ) is not None
    duration = any(word in description for word in ("时长", "持续时间"))
    duration = duration and re.fullmatch(
        r"\d+小时(?:\d+分)?|\d+(?:分钟|分|秒)", sample
    ) is not None
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
) -> None:
    for component in components:
        if component.component_type != "Row":
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
            if not value_path:
                continue
            schema_type = _schema_type(
                _schema_node_at_path(data_model_schema, value_path)
            )
            value_font_size = _non_negative_number(
                value.props.get("fontSize")
            )
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
            if unit not in _COMMON_DISPLAY_UNITS:
                continue
            if schema_type in _NUMERIC_SCHEMA_TYPES:
                if value_font_size is None or value_font_size < 30:
                    continue
                padding = suffix.props.get("padding")
                unit_bottom_padding = None
                if isinstance(padding, (int, float)):
                    unit_bottom_padding = float(padding)
                elif isinstance(padding, dict):
                    unit_bottom_padding = _non_negative_number(
                        padding.get("bottom")
                    )
                unit_height = _non_negative_number(suffix.props.get("height"))
                has_valid_height = unit_height is None or unit_height <= 24
                has_valid_alignment = (
                    component.props.get("alignItems") == "bottom"
                    and unit_bottom_padding == 4
                    and has_valid_height
                )
                if not has_valid_alignment:
                    errors.append(
                        f"component {component.component_id}: large numeric value "
                        f"and unit {suffix.component_id} must use Row alignItems "
                        '"bottom"; the unit must use padding.bottom 4 and must not '
                        "use the large value's fixed height."
                    )
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


def _two_by_four_data_block_count(
    task_spec: dict[str, Any],
    data_roots: set[str],
) -> int:
    block_count = len(data_roots)
    if "healthSport" not in data_roots:
        return block_count

    data_model_schema = task_spec.get("dataModelSchema")
    schema_data = (
        data_model_schema.get("data")
        if isinstance(data_model_schema, dict)
        else None
    )
    if not isinstance(schema_data, dict):
        return block_count
    health_sport = schema_data.get("healthSport")
    if not isinstance(health_sport, dict):
        return block_count

    has_daily_summary = False
    has_exercise_record = False
    for field_name in health_sport:
        has_daily_summary = has_daily_summary or field_name.startswith("daily")
        has_exercise_record = has_exercise_record or field_name.startswith("exercise")
    if has_daily_summary and has_exercise_record:
        block_count += 1
    return block_count


def _schema_leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            return 1
        return sum(_schema_leaf_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_schema_leaf_count(child) for child in value)
    return 0


def _schema_field_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            return set()
        names = {str(key).casefold() for key in value}
        for child in value.values():
            names.update(_schema_field_names(child))
        return names
    if isinstance(value, list):
        names: set[str] = set()
        for child in value:
            names.update(_schema_field_names(child))
        return names
    return set()


def _is_dense_phone_battery_schema(value: Any) -> bool:
    field_names = _schema_field_names(value)
    detail_groups = (
        ("temperature",),
        ("health",),
        ("plugged", "charger", "chargingtype"),
        ("updated", "updatetime"),
    )
    detail_count = 0
    for markers in detail_groups:
        group_matches = False
        for field_name in field_names:
            for marker in markers:
                if marker in field_name:
                    group_matches = True
                    break
            if group_matches:
                break
        if group_matches:
            detail_count += 1
    fact_count = _schema_leaf_count(value)
    has_raw_and_formatted_soc = {
        "batterysoc",
        "batterysoctext",
    }.issubset(field_names)
    if has_raw_and_formatted_soc:
        fact_count -= 1
    return detail_count >= 2 or fact_count >= 4


def _uses_two_by_four_focus_aux_layout(task_spec: dict[str, Any]) -> bool:
    if task_spec.get("size") != "2x4":
        return False
    data_model_schema = task_spec.get("dataModelSchema")
    data_schema = (
        data_model_schema.get("data")
        if isinstance(data_model_schema, dict)
        else None
    )
    if not isinstance(data_schema, dict) or not data_schema:
        return False

    roots = tuple(data_schema)
    normalized_roots = {root.casefold() for root in roots}
    if "countdown" in normalized_roots or len(roots) > 2:
        return False
    if len(roots) == 1:
        if "healthsport" in normalized_roots:
            return _schema_leaf_count(data_schema) >= 4
        if "phonebattery" in normalized_roots:
            phone_battery = next(iter(data_schema.values()))
            return _is_dense_phone_battery_schema(phone_battery)
        if "earphone" in normalized_roots:
            return _schema_leaf_count(data_schema) >= 6
        return False

    supported = normalized_roots == {"calendar", "phonebattery"} or (
        "healthsport" in normalized_roots
    )
    return supported and _schema_leaf_count(data_schema) >= 3


def _has_stacked_two_by_four_backboards(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
) -> bool:
    for component in components:
        if component.component_type != "Column":
            continue
        full_width_backboard_count = 0
        for child_id in component.children:
            child = components_by_id.get(child_id)
            if child is None or child.component_type not in {"Row", "Column"}:
                continue
            height = _non_negative_number(child.props.get("height"))
            border_radius = _non_negative_number(child.props.get("borderRadius"))
            is_full_width_backboard = child.props.get("width") in {276, 296}
            is_compact_height = height is not None and 48 <= height <= 64
            has_backboard_shape = border_radius is not None and border_radius >= 12
            if is_full_width_backboard and is_compact_height and has_backboard_shape:
                full_width_backboard_count += 1
        if full_width_backboard_count >= 2:
            return True
    return False


def _is_two_by_four_large_backboard(component: ComponentRow | None) -> bool:
    if component is None or component.component_type != "Column":
        return False
    if component.props.get("width") != _TWO_BY_FOUR_MULTI_LARGE_WIDTH:
        return False
    if component.props.get("height") != _TWO_BY_FOUR_MULTI_LARGE_HEIGHT:
        return False
    return component.props.get("padding") == 12


def _descendant_on_click_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> int:
    count = 0
    pending = list(component.children)
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        child = components_by_id.get(child_id)
        if child is None:
            continue
        if "onClick" in child.props:
            count += 1
        pending.extend(child.children)
    return count


def _descendant_type_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    component_type: str,
) -> int:
    count = 0
    pending = list(component.children)
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        child = components_by_id.get(child_id)
        if child is None:
            continue
        if child.component_type == component_type:
            count += 1
        pending.extend(child.children)
    return count


def _is_two_by_four_direct_action(component: ComponentRow | None) -> bool:
    if component is None:
        return False
    if component.component_type == "Button":
        return True
    return component.component_type == "Row" and "onClick" in component.props


def _horizontal_padding_at_least(props: dict[str, Any], minimum: float) -> bool:
    padding = props.get("padding")
    if isinstance(padding, (int, float)):
        return padding >= minimum
    if not isinstance(padding, dict):
        return False
    left = _non_negative_number(padding.get("left"))
    right = _non_negative_number(padding.get("right"))
    return left is not None and left >= minimum and right is not None and right >= minimum


def _collect_two_by_four_action_backboard_errors(
    backboard: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    actions: list[ComponentRow] = []
    for child_id in backboard.children:
        child = components_by_id.get(child_id)
        if _is_two_by_four_direct_action(child):
            actions.append(child)
    if len(actions) != 1:
        return

    action = actions[0]
    if not backboard.children or backboard.children[-1] != action.component_id:
        errors.append(
            f"2x4 large backboard {backboard.component_id} must place its action "
            "as the final direct child."
        )
    if (
        action.props.get("width") != _TWO_BY_FOUR_MULTI_INNER_WIDTH
        or action.props.get("height") != 36
    ):
        errors.append(
            f"2x4 large backboard {backboard.component_id} action must be "
            f"{_TWO_BY_FOUR_MULTI_INNER_WIDTH}x36."
        )
    if action.component_type == "Row":
        _collect_two_by_four_action_row_errors(action, errors)

    content_ids = backboard.children[:-1]
    if len(content_ids) != 1:
        errors.append(
            f"2x4 large backboard {backboard.component_id} with a Button must "
            "have exactly [content, Button] as direct children."
        )
        return
    content = components_by_id.get(content_ids[0])
    if content is None or content.component_type != "Column":
        errors.append(
            f"2x4 large backboard {backboard.component_id} content must be a Column."
        )
        return
    if content.props.get("layoutWeight") != 1:
        errors.append(
            f"2x4 large backboard {backboard.component_id} content must use "
            "layoutWeight 1 so the Button stays at the bottom."
        )
    if _descendant_type_count(content, components_by_id, "Text") > 4:
        errors.append(
            f"2x4 large backboard {backboard.component_id} with a Button may "
            "contain at most four Text nodes across no more than three visual "
            "rows. Merge or remove lower-priority fields."
        )


def _collect_two_by_four_action_row_errors(
    action: ComponentRow,
    errors: list[str],
) -> None:
    props = action.props
    valid_layout = (
        props.get("itemMargin") == 8
        and props.get("justifyContent") == "center"
        and props.get("alignItems") == "center"
        and _horizontal_padding_at_least(props, 8)
    )
    if valid_layout:
        return
    errors.append(
        f"2x4 graphical action Row {action.component_id} must use itemMargin 8, "
        "at least 8vp left/right padding, justifyContent center, and alignItems "
        "center so its icon and label stay centered."
    )


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


def _collect_two_by_two_narrow_graphical_action_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in component.children
    }
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
            errors.append(
                f"2x2 narrow graphical action Row {action.component_id} must be centered "
                f"by parent Column {parent.component_id}; set alignItems to center when "
                "the action is narrower than the parent's content width."
            )


def _collect_two_by_four_full_width_action_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
    ) -> None:
    parent_by_child: dict[str, ComponentRow] = {}
    for component in components:
        for child_id in component.children:
            parent_by_child[child_id] = component

    for action in components:
        if not _is_two_by_four_direct_action(action):
            continue
        if action.props.get("width") != 276 or action.props.get("height") != 36:
            continue

        parent = parent_by_child.get(action.component_id)
        is_full_height_foreground = (
            parent is not None
            and parent.component_type == "Column"
            and parent.props.get("width") == "matchParent"
            and parent.props.get("height") == "matchParent"
        )
        if not is_full_height_foreground:
            errors.append(
                f"2x4 full-width action {action.component_id} must be a direct "
                "child of the matchParent foreground Column; do not nest it "
                "inside a fixed-height main/body container where content can overlap."
            )
            continue

        if parent is None:
            continue
        if not parent.children or parent.children[-1] != action.component_id:
            errors.append(
                f"2x4 full-width action {action.component_id} must be the final "
                "direct child of foreground Column {parent.component_id}."
            )
            continue
        if len(parent.children) < 2:
            continue
        content = components_by_id.get(parent.children[-2])
        if content is None or content.props.get("layoutWeight") != 1:
            errors.append(
                f"2x4 content immediately above full-width action "
                f"{action.component_id} must use layoutWeight 1 so the 276x36 "
                "action remains fixed at the bottom without overlapping content."
            )


def _is_2x2_small_backboard(component: ComponentRow | None) -> bool:
    if component is None or component.component_type not in {"Row", "Column"}:
        return False
    if component.props.get("width") != 134:
        return False
    if component.props.get("height") != 63:
        return False
    if "backgroundColor" not in component.props:
        return False
    return component.props.get("borderRadius") in {12, 16}


def _has_two_by_two_s4_zones(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if root is None or root.component_type != "Column":
        return False
    has_expected_root_layout = (
        root.props.get("padding") == 8 and root.props.get("itemMargin") == 8
    )
    if len(root.children) != 2 or not has_expected_root_layout:
        return False
    for child_id in root.children:
        zone = components_by_id.get(child_id)
        if zone is None or zone.component_type not in {"Row", "Column"}:
            return False
        if zone.props.get("width") != 134 or zone.props.get("height") != 63:
            return False
    return True


def _descendant_components(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> list[ComponentRow]:
    descendants: list[ComponentRow] = []
    pending = list(component.children)
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        child = components_by_id.get(child_id)
        if child is None:
            continue
        descendants.append(child)
        pending.extend(child.children)
    return descendants


def _component_content_paths(component: ComponentRow) -> list[str]:
    paths: list[str] = []
    _collect_binding_context(
        component.props.get("content"),
        f"component {component.component_id}.props.content",
        paths,
        [],
    )
    return paths


def _two_by_two_s4_object_count(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> int:
    object_ids: set[str] = set()
    for zone_id in root.children:
        zone = components_by_id.get(zone_id)
        if zone is None:
            continue
        zone_components = [zone, *_descendant_components(zone, components_by_id)]
        for component in zone_components:
            if component.component_type != "Text":
                continue
            for path in _component_content_paths(component):
                parts = path.strip("/").split("/")
                if len(parts) < 2 or parts[0] != "data":
                    continue
                object_id = parts[1]
                for index, part in enumerate(parts[2:], start=2):
                    if part.isdigit():
                        object_id = "/".join(parts[1 : index + 1])
                        break
                object_ids.add(object_id)
    return len(object_ids)


def _numeric_content_paths(
    components: list[ComponentRow],
    data_model_schema: dict[str, Any],
) -> set[str]:
    paths: set[str] = set()
    for component in components:
        if component.component_type != "Text":
            continue
        for path in _component_content_paths(component):
            schema_node = _schema_node_at_path(data_model_schema, path)
            if _schema_type(schema_node) in _NUMERIC_SCHEMA_TYPES:
                paths.add(path)
    return paths


def _binding_roots(value: Any, location: str) -> set[str]:
    paths: list[str] = []
    _collect_binding_context(value, location, paths, [])
    roots: set[str] = set()
    for path in paths:
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "data":
            roots.add(parts[1])
    return roots


def _first_text_component(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    visiting: set[str],
) -> ComponentRow | None:
    if component.component_type == "Text":
        return component
    if component.component_id in visiting:
        return None
    visiting.add(component.component_id)
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        result = _first_text_component(child, components_by_id, visiting)
        if result is not None:
            visiting.remove(component.component_id)
            return result
    visiting.remove(component.component_id)
    return None


def _collect_two_by_four_w9_density_errors(
    zone: ComponentRow,
    content_regions: list[ComponentRow],
    content_components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    if any(
        component.component_type == "Progress"
        for component in content_components
    ):
        return

    line_profile: list[bool] = []
    for region in content_regions:
        line_profile.extend(
            _visual_text_line_profile(region, components_by_id, set())
        )
    if not line_profile:
        return

    first_text = None
    for region in content_regions:
        first_text = _first_text_component(region, components_by_id, set())
        if first_text is not None:
            break
    if first_text is not None:
        font_size = _non_negative_number(first_text.props.get("fontSize"))
        font_weight = _non_negative_number(first_text.props.get("fontWeight"))
        identifier = first_text.component_id.casefold()
        looks_like_title = "title" in identifier or "label" in identifier
        has_later_emphasis = any(line_profile[1:])
        if (
            font_size == 12
            and font_weight == 400
            and (looks_like_title or has_later_emphasis)
        ):
            line_profile = line_profile[1:]

    large_number_count = 0
    for component in content_components:
        if component.component_type != "Text":
            continue
        font_size = _non_negative_number(component.props.get("fontSize"))
        if font_size is not None and font_size >= 30:
            large_number_count += 1

    if large_number_count:
        data_model_schema = task_spec.get("dataModelSchema")
        numeric_paths = (
            _numeric_content_paths(content_components, data_model_schema)
            if isinstance(data_model_schema, dict)
            else set()
        )
        if len(numeric_paths) >= 2:
            errors.append(
                f"2x4 W9 backboard {zone.component_id} displays multiple peer "
                "quantitative fields and must keep all of them as ordinary "
                "complete text lines with the same typography; do not promote "
                "one field to a 30fp/38fp hero."
            )
        if large_number_count > 1:
            errors.append(
                f"2x4 W9 backboard {zone.component_id} contains multiple "
                "30fp/38fp values. Keep peer metrics as ordinary complete text "
                "lines instead of manufacturing multiple hero values."
            )
        if len(line_profile) > 2:
            errors.append(
                f"2x4 W9 backboard {zone.component_id} with a 30fp/38fp numeric "
                "hero may contain only the value/unit line and one 12fp/400 "
                "auxiliary line after its business title. Merge auxiliary fields "
                "with ' | '."
            )


def _collect_two_by_four_w9_content_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    for zone_id in root.children:
        zone = components_by_id.get(zone_id)
        if zone is None:
            continue

        content_regions: list[ComponentRow] = []
        content_components: list[ComponentRow] = []
        actions: list[ComponentRow] = []
        for child_id in zone.children:
            child = components_by_id.get(child_id)
            if child is None:
                continue
            if _is_two_by_four_direct_action(child):
                actions.append(child)
                continue
            content_regions.append(child)
            content_components.append(child)
            content_components.extend(_descendant_components(child, components_by_id))

        _collect_two_by_four_w9_density_errors(
            zone,
            content_regions,
            content_components,
            components_by_id,
            task_spec,
            errors,
        )

        text_components = [
            component
            for component in content_components
            if component.component_type == "Text"
        ]
        _collect_two_by_four_w9_sparse_layout_errors(
            zone, components_by_id, text_components, actions, errors
        )
        if len(text_components) > 4:
            errors.append(
                f"2x4 W9 backboard {zone.component_id} may contain at most four "
                "content Text rows. Merge same-object fields instead of stacking "
                "additional rows."
            )

        content_roots: set[str] = set()
        paths_by_text: dict[str, list[str]] = {}
        for component in text_components:
            paths = _component_content_paths(component)
            paths_by_text[component.component_id] = paths
            for path in paths:
                parts = path.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "data":
                    content_roots.add(parts[1])

        if len(content_roots) > 1:
            errors.append(
                f"2x4 W9 backboard {zone.component_id} mixes data roots "
                f"{sorted(content_roots)}. Each backboard must display exactly "
                "one business object; move every field to its owning backboard."
            )

        for action in actions:
            action_roots = _binding_roots(
                action.props.get("onClick"),
                f"component {action.component_id}.props.onClick",
            )
            if (
                action_roots
                and content_roots
                and content_roots.isdisjoint(action_roots)
            ):
                errors.append(
                    f"2x4 W9 action {action.component_id} binds data root(s) "
                    f"{sorted(action_roots)} but is placed in backboard "
                    f"{zone.component_id}, which displays {sorted(content_roots)}. "
                    "Move the action to its owning business backboard."
                )

        has_countdown = False
        has_countdown_unit = False
        for component in text_components:
            content = component.props.get("content")
            if isinstance(content, str) and content.strip() == "天":
                has_countdown_unit = True
            paths = paths_by_text[component.component_id]
            if not any(path.endswith("/countdownDays") for path in paths):
                continue
            has_countdown = True
            font_size = _non_negative_number(component.props.get("fontSize"))
            if font_size not in {30, 38} or component.props.get("fontWeight") != 700:
                errors.append(
                    f"2x4 W9 countdown {component.component_id} must use a "
                    "30fp/38fp, 700-weight numeric hero in its own backboard."
                )
        if has_countdown and not has_countdown_unit:
            errors.append(
                f"2x4 W9 countdown backboard {zone.component_id} must place "
                "the unit `天` in a separate Text directly below the numeric hero."
            )

        daily_texts: dict[str, set[str]] = {}
        for component in text_components:
            for path in paths_by_text[component.component_id]:
                match = re.match(r"^/data/weather/daily/(\d+)/", path)
                if match is None:
                    continue
                daily_texts.setdefault(match.group(1), set()).add(
                    component.component_id
                )
        if len(daily_texts) >= 2:
            for day_index, component_ids in daily_texts.items():
                if len(component_ids) == 1:
                    component_id = next(iter(component_ids))
                    component = components_by_id.get(component_id)
                    if component is None:
                        continue
                    font_size = _non_negative_number(
                        component.props.get("fontSize")
                    )
                    if font_size == 12 and component.props.get("fontWeight") == 400:
                        continue
                    errors.append(
                        f"2x4 W9 compact weather day {component_id} must use "
                        "12fp/400 auxiliary text."
                    )
                    continue
                errors.append(
                    f"2x4 W9 weather day {day_index} in backboard "
                    f"{zone.component_id} is split across multiple Text rows "
                    f"{sorted(component_ids)}. Merge each day into one 12fp/400 row."
                )
            if any(
                component.component_type == "Divider"
                for component in content_components
            ):
                errors.append(
                    f"2x4 W9 multi-day weather backboard {zone.component_id} "
                    "must not insert Divider components between compact day rows."
                )


def _collect_two_by_two_s4_text_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    action_hint_prefixes = ("点击", "点此", "一键")
    for zone_id in root.children:
        zone = components_by_id.get(zone_id)
        if zone is None:
            continue
        text_components = []
        for descendant in _descendant_components(zone, components_by_id):
            if descendant.component_type == "Text":
                text_components.append(descendant)

        if len(text_components) > 2:
            errors.append(
                f"2x2 S4 backboard {zone.component_id} contains "
                f"{len(text_components)} Text rows; keep at most two single-line "
                "Text components."
            )
        for text_component in text_components:
            if text_component.props.get("maxLines") != 1:
                errors.append(
                    f"2x2 S4 Text {text_component.component_id} must use "
                    "maxLines 1; a backboard must never render a third line."
                )
            content = text_component.props.get("content")
            if not isinstance(content, str) or "{{" in content:
                continue
            text_width = _non_negative_number(text_component.props.get("width"))
            font_size = _non_negative_number(
                text_component.props.get("fontSize")
            )
            if text_width is None or font_size is None:
                continue
            estimated_width = 0.0
            for character in content.strip():
                estimated_width += font_size * (0.6 if character.isascii() else 1.0)
            if estimated_width > text_width:
                errors.append(
                    f"2x2 S4 static Text {text_component.component_id} exceeds its "
                    f"{text_width:g}vp single-line width; shorten the wording while "
                    "keeping its meaning. Do not wrap it, add a third line, or move "
                    "the visual."
                )

        if "onClick" in zone.props:
            for text_component in text_components:
                content = text_component.props.get("content")
                if not isinstance(content, str) or "{{" in content:
                    continue
                if content.strip().startswith(action_hint_prefixes):
                    errors.append(
                        f"2x2 S4 clickable backboard {zone.component_id} must not "
                        f"show action hint Text {text_component.component_id}; "
                        "bind the action only to the backboard."
                    )

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
                    errors.append(
                        f"2x2 S4 meeting time {text_component.component_id} must "
                        "use its own 12fp/400 auxiliary row; do not combine it "
                        "with the 14fp/700 meeting title."
                    )
                continue
            if (
                text_component.props.get("fontSize") == 14
                and text_component.props.get("fontWeight") == 700
            ):
                has_meeting_title = True
        if has_calendar_content and not has_meeting_title:
            errors.append(
                f"2x2 S4 calendar backboard {zone.component_id} must keep a "
                "separate 14fp/700 meeting title above its 12fp/400 time row."
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
            if (
                zone.component_type == "Column"
                and zone.props.get("justifyContent") != "center"
            ):
                errors.append(
                    f"2x2 S4 backboard {zone.component_id} without a visual must "
                    "vertically center its one or two text lines with "
                    "justifyContent center; do not reserve an empty third line."
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
            errors.append(
                f"2x2 S4 text group {text_group.component_id} must use "
                "justifyContent center so its one or two lines remain vertically "
                "centered beside the visual."
            )


def _collect_two_by_two_ring_group_alignment_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child: dict[str, ComponentRow] = {}
    for component in components:
        for child_id in component.children:
            parent_by_child[child_id] = component

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
        errors.append(
            f"2x2 compact ring group {content_group.component_id} must use "
            'alignItems "center" so the ring and its single status line remain '
            "horizontally centered."
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
        f"#{rgb}: {', '.join(locations)}"
        for rgb, locations in sorted(colors.items())
    )
    errors.append(
        "2x2 S4 must use one card palette across both business zones. Text, "
        "tintable Image, Progress, and Divider colors must share one RGB and "
        f"may differ only in alpha. Found mixed palette colors: {details}."
    )


def _has_two_by_four_w9_backboards(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if root is None or root.component_type != "Row":
        return False
    expected_root_layout = (
        root.props.get("padding") == _TWO_BY_FOUR_MULTI_ROOT_PADDING
        and root.props.get("itemMargin") == 8
    )
    if len(root.children) != 2 or not expected_root_layout:
        return False
    for child_id in root.children:
        backboard = components_by_id.get(child_id)
        if not _is_two_by_four_large_backboard(backboard):
            return False
    return True


def _is_two_by_four_focus_aux_cell(component: ComponentRow | None) -> bool:
    if component is None or component.component_type not in {"Row", "Column"}:
        return False
    return (
        component.props.get("width") == _TWO_BY_FOUR_AUX_WIDTH
        and component.props.get("height") == _TWO_BY_FOUR_AUX_CELL_HEIGHT
        and component.props.get("borderRadius") == 12
        and "backgroundColor" in component.props
    )


def _has_two_by_four_w1_focus_aux(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if root is None or root.component_type != "Row":
        return False
    if (
        root.props.get("padding") != 12
        or root.props.get("itemMargin") != 10
        or len(root.children) != 2
    ):
        return False

    focus = components_by_id.get(root.children[0])
    aux_column = components_by_id.get(root.children[1])
    if focus is None or focus.component_type not in {"Row", "Column"}:
        return False
    if (
        focus.props.get("width") != _TWO_BY_FOUR_FOCUS_WIDTH
        or focus.props.get("height") != _TWO_BY_FOUR_FOCUS_AUX_HEIGHT
        or "backgroundColor" in focus.props
    ):
        return False
    if aux_column is None or aux_column.component_type != "Column":
        return False
    if (
        aux_column.props.get("width") != _TWO_BY_FOUR_AUX_WIDTH
        or aux_column.props.get("height") != _TWO_BY_FOUR_FOCUS_AUX_HEIGHT
        or aux_column.props.get("itemMargin") != 8
        or len(aux_column.children) != 2
    ):
        return False
    return all(
        _is_two_by_four_focus_aux_cell(components_by_id.get(cell_id))
        for cell_id in aux_column.children
    )


def _collect_two_by_four_w1_focus_aux_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    focus = components_by_id.get(root.children[0])
    aux_column = components_by_id.get(root.children[1])
    if focus is None or aux_column is None:
        return

    focus_components = [focus, *_descendant_components(focus, components_by_id)]
    large_texts = [
        component
        for component in focus_components
        if component.component_type == "Text"
        and (_non_negative_number(component.props.get("fontSize")) or 0) >= 30
    ]
    if len(large_texts) > 1:
        errors.append(
            "2x4 W1-focus-aux may contain only one 30fp/38fp hero in the "
            "left focus zone. Keep peer metrics as auxiliary content."
        )
    if any(component.props.get("onClick") for component in focus_components):
        errors.append(
            "2x4 W1-focus-aux actions must occupy a right auxiliary cell; "
            "do not bind actions inside the left focus zone."
        )
    query = str(task_spec.get("userQuery") or "").casefold()
    progress_requested = False
    for marker in ("进度", "进度条", "进度环", "环形", "progress"):
        if marker in query:
            progress_requested = True
            break
    has_progress = False
    for component in focus_components:
        if component.component_type == "Progress":
            has_progress = True
            break
    if has_progress and not progress_requested:
        errors.append(
            "2x4 W1-focus-aux must not add Progress unless the user explicitly "
            "requests a progress visualization. Use the left focus for the "
            "primary value and its necessary status instead."
        )

    for cell_id in aux_column.children:
        cell = components_by_id.get(cell_id)
        if cell is None:
            continue
        cell_components = [cell, *_descendant_components(cell, components_by_id)]
        text_count = sum(
            component.component_type == "Text" for component in cell_components
        )
        if text_count > 2:
            errors.append(
                f"2x4 W1-focus-aux cell {cell.component_id} may contain at most "
                "two Text nodes. Merge its auxiliary information."
            )
        if any(
            component.component_type in {"Button", "ActionUnit"}
            for component in cell_components
        ):
            errors.append(
                f"2x4 W1-focus-aux cell {cell.component_id} must bind onClick "
                "to the auxiliary backboard itself; do not nest a Button or "
                "ActionUnit inside it."
            )

        cell_roots: set[str] = set()
        for component in cell_components:
            if component.component_type == "Text":
                for path in _component_content_paths(component):
                    parts = path.strip("/").split("/")
                    if len(parts) >= 2 and parts[0] == "data":
                        cell_roots.add(parts[1])
            cell_roots.update(
                _binding_roots(
                    component.props.get("onClick"),
                    f"component {component.component_id}.props.onClick",
                )
            )
        if len(cell_roots) > 1:
            errors.append(
                f"2x4 W1-focus-aux cell {cell.component_id} mixes data roots "
                f"{sorted(cell_roots)}. Each auxiliary cell must belong to one "
                "business object."
            )


def _is_two_by_four_small_backboard(component: ComponentRow | None) -> bool:
    if component is None or component.component_type not in {"Row", "Column"}:
        return False
    expected_size = (
        component.props.get("width") == _TWO_BY_FOUR_MULTI_LARGE_WIDTH
        and component.props.get("height") == 63
    )
    return expected_size and component.props.get("padding") == 12


def _has_two_by_four_w8_backboards(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if root is None or root.component_type != "Column":
        return False
    root_layout_valid = (
        root.props.get("padding") == _TWO_BY_FOUR_MULTI_ROOT_PADDING
        and root.props.get("itemMargin") == 8
        and len(root.children) == 2
    )
    if not root_layout_valid:
        return False
    for row_id in root.children:
        row = components_by_id.get(row_id)
        if row is None or row.component_type != "Row":
            return False
        row_layout_valid = (
            row.props.get("width") == 284
            and row.props.get("height") == 63
            and row.props.get("itemMargin") == 8
            and len(row.children) == 2
        )
        if not row_layout_valid:
            return False
        for zone_id in row.children:
            if not _is_two_by_four_small_backboard(
                components_by_id.get(zone_id)
            ):
                return False
    return True


def _has_two_by_four_w10_backboards(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if root is None or root.component_type != "Row":
        return False
    root_layout_valid = (
        root.props.get("padding") == _TWO_BY_FOUR_MULTI_ROOT_PADDING
        and root.props.get("itemMargin") == 8
        and len(root.children) == 2
    )
    if not root_layout_valid:
        return False
    first = components_by_id.get(root.children[0])
    second = components_by_id.get(root.children[1])
    if _is_two_by_four_large_backboard(first):
        side = second
    elif _is_two_by_four_large_backboard(second):
        side = first
    else:
        return False
    if side is None or side.component_type != "Column":
        return False
    side_layout_valid = (
        side.props.get("width") == _TWO_BY_FOUR_MULTI_LARGE_WIDTH
        and side.props.get("height") == _TWO_BY_FOUR_MULTI_LARGE_HEIGHT
        and side.props.get("itemMargin") == 8
        and len(side.children) == 2
    )
    if not side_layout_valid:
        return False
    return all(
        _is_two_by_four_small_backboard(components_by_id.get(zone_id))
        for zone_id in side.children
    )


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
        child_profiles.append(
            _visual_text_line_profile(child, components_by_id, visiting)
        )
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


def _contains_action_control(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if component.component_type in {"ActionUnit", "Button"}:
        return True
    if component.component_type == "Row" and "onClick" in component.props:
        return True
    descendants = _descendant_components(component, components_by_id)
    for descendant in descendants:
        if descendant.component_type in {"ActionUnit", "Button"}:
            return True
        if descendant.component_type == "Row" and "onClick" in descendant.props:
            return True
    return False


def _is_two_by_two_title_region(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if component.component_type == "CardHeader":
        return True
    height = _non_negative_number(component.props.get("height"))
    if height not in {20.0, 28.0}:
        return False
    profile = _visual_text_line_profile(component, components_by_id, set())
    return len(profile) == 1


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
        information_components.extend(
            _descendant_components(region, components_by_id)
        )
        line_profile.extend(
            _visual_text_line_profile(region, components_by_id, set())
        )
    if any(
        component.component_type == "Progress"
        for component in information_components
    ):
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
            errors.append(
                "2x2 150vp single-business content displays multiple peer "
                "quantitative fields and must keep all of them as ordinary "
                "complete text lines with the same typography; do not promote "
                "one field to a 30fp/38fp hero."
            )
        if large_number_count > 1:
            errors.append(
                "2x2 150vp single-business content contains multiple 30fp/38fp "
                "values. Treat peer metrics as ordinary complete text lines instead "
                "of manufacturing multiple hero values."
            )
        if len(line_profile) > 2:
            errors.append(
                "2x2 150vp single-business content with a 30fp/38fp numeric hero "
                "may contain only the value/unit line and one 12fp/400 auxiliary "
                "line. Merge auxiliary fields into that line with ' | '."
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
        errors.append(
            "2x2 150vp single-business pure-text content with an action may "
            "contain at most one prominent line and two 12fp/400 auxiliary "
            "lines. Merge related auxiliary fields with ' | ' and remove "
            "lower-priority update text."
        )
    if has_action and len(line_profile) == 3:
        oversized_text = False
        for component in information_components:
            font_size = _non_negative_number(component.props.get("fontSize"))
            if component.component_type == "Text" and (font_size or 0) > 18:
                oversized_text = True
                break
        if oversized_text:
            errors.append(
                "2x2 150vp single-business content with an action and three "
                "information lines must keep its prominent text at 18fp or "
                "smaller so the 36vp action remains unobstructed."
            )


def _collect_layout_route_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    visible_binding_paths: list[str],
    errors: list[str],
) -> None:
    size = task_spec.get("size")
    if size not in {"2x2", "2x4"}:
        return

    components_by_id = {
        component.component_id: component for component in components
    }
    root = components_by_id.get("root")
    _collect_two_by_two_content_density_errors(
        components,
        task_spec,
        components_by_id,
        errors,
    )
    if (
        size == "2x2"
        and root is not None
        and _has_two_by_two_s4_zones(root, components_by_id)
    ):
        _collect_two_by_two_s4_vertical_alignment_errors(
            root,
            components_by_id,
            errors,
        )
    if size == "2x2" and _uses_2x2_v01_countdown_layout(task_spec):
        _collect_2x2_countdown_group_errors(
            components,
            components_by_id,
            visible_binding_paths,
            task_spec,
            errors,
        )
        return

    visible_data_roots = {
        parts[1]
        for path in visible_binding_paths
        if len(parts := path.strip("/").split("/")) >= 2 and parts[0] == "data"
    }
    data_roots = visible_data_roots
    if size == "2x2":
        _collect_two_by_two_narrow_graphical_action_errors(
            components,
            components_by_id,
            errors,
        )
        _collect_two_by_two_ring_group_alignment_errors(
            components,
            components_by_id,
            errors,
        )
        data_model_schema = task_spec.get("dataModelSchema")
        schema_data = (
            data_model_schema.get("data")
            if isinstance(data_model_schema, dict)
            else None
        )
        if isinstance(schema_data, dict):
            data_roots = set(schema_data)

    if size == "2x4":
        _collect_two_by_four_full_width_action_errors(
            components,
            components_by_id,
            errors,
        )
        if _has_stacked_two_by_four_backboards(components, components_by_id):
            errors.append(
                "2x4 cards must not stack two or more full-width 276x48-59 "
                "content backboards vertically. Select the matching W skeleton; "
                "two semantic data blocks must use W9 left/right backboards."
            )
        for component in components:
            if not _is_two_by_four_large_backboard(component):
                continue
            _collect_two_by_four_action_backboard_errors(
                component,
                components_by_id,
                errors,
            )
            if _descendant_on_click_count(component, components_by_id) > 1:
                errors.append(
                    f"2x4 large backboard {component.component_id} may contain at "
                    "most one action control. Do not stack two buttons inside a "
                    "138x134 backboard; remove duplicate or lower-priority actions."
                )

    if size == "2x2" and len(data_roots) == 1:
        if (
            root is not None
            and _has_two_by_two_s4_zones(root, components_by_id)
            and _two_by_two_s4_object_count(root, components_by_id) != 2
        ):
            errors.append(
                "2x2 S4 requires exactly two independent display objects. "
                "Fields from one object must remain in one single-business "
                "layout instead of being split across two 134x63 backboards."
            )
        if root is not None and len(root.children) == 1:
            only_child = components_by_id.get(root.children[0])
            if _is_2x2_small_backboard(only_child):
                errors.append(
                    "2x2 card has one data root and must use a full-width "
                    "single-business layout; do not generate an isolated "
                    "134x63 S4 backboard."
                )
        _collect_2x2_countdown_group_errors(
            components,
            components_by_id,
            visible_binding_paths,
            task_spec,
            errors,
        )
        return

    if size == "2x4" and _uses_two_by_four_focus_aux_layout(task_spec):
        if root is not None and _has_two_by_four_w1_focus_aux(
            root,
            components_by_id,
        ):
            _collect_two_by_four_w1_focus_aux_errors(
                root,
                components_by_id,
                task_spec,
                errors,
            )
            return
        errors.append(
            "2x4 card has one dominant focus and at most two auxiliary slots and "
            "must use W1-focus-aux: root Row padding 12/itemMargin 10, a left "
            "136x126 focus zone without a backboard, and a right 130x126 Column "
            "containing two 130x59 backboards separated by itemMargin 8."
        )
        return

    data_block_count = len(data_roots)
    if size == "2x4":
        data_block_count = _two_by_four_data_block_count(task_spec, data_roots)
        if data_block_count == 4:
            if _has_two_by_four_w8_backboards(root, components_by_id):
                return
            errors.append(
                "2x4 card displays four semantic data blocks and must use W8: "
                "root must be a Column with padding 8 and two direct 284x63 "
                "Rows separated by itemMargin 8; each Row must contain two "
                "138x63 backboards separated by itemMargin 8."
            )
            return
        if data_block_count == 3:
            if _has_two_by_four_w10_backboards(root, components_by_id):
                return
            errors.append(
                "2x4 card displays three semantic data blocks and must use W10: "
                "root must be a Row with padding 8 and itemMargin 8, containing "
                "one 138x134 large backboard and one 138x134 Column with two "
                "138x63 backboards separated by itemMargin 8."
            )
            return
    if (
        size == "2x2"
        and root is not None
        and _has_two_by_two_s4_zones(root, components_by_id)
        and _two_by_two_s4_object_count(root, components_by_id) != 2
    ):
        errors.append(
            "2x2 S4 requires exactly two independent display objects. Fields "
            "from one object must remain in one single-business layout instead "
            "of being split across two 134x63 backboards."
        )
        return
    if data_block_count != 2:
        return

    if size == "2x2":
        if root is not None and _has_two_by_two_s4_zones(root, components_by_id):
            _collect_two_by_two_s4_text_errors(
                root,
                components_by_id,
                errors,
            )
            _collect_two_by_two_s4_palette_errors(
                root,
                components_by_id,
                errors,
            )
            if "countdown" not in data_roots:
                return
            countdown_texts = []
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
                if any(
                    path.startswith("/data/countdown/") for path in component_paths
                ):
                    countdown_texts.append(component)
            countdown_style_valid = bool(countdown_texts)
            for component in countdown_texts:
                font_size = _non_negative_number(component.props.get("fontSize"))
                if font_size != 14 or component.props.get("fontWeight") != 700:
                    countdown_style_valid = False
            if countdown_style_valid:
                return
            errors.append(
                "2x2 S4 countdown must be displayed as ordinary 14fp/700 "
                "primary text inside its backboard; do not reuse the V01 "
                "30fp/38fp hero or standalone countdown group."
            )
            return

        roots = ", ".join(sorted(data_roots))
        errors.append(
            f"2x2 card displays two data roots ({roots}) and must use S4: root "
            "must be a Column with padding 8 and exactly two direct 134x63 "
            "Row/Column backboards with itemMargin 8. Countdown remains ordinary 14fp/700 "
            "primary text inside its backboard."
        )
        return

    if root is not None and _has_two_by_four_w9_backboards(root, components_by_id):
        _collect_two_by_four_w9_content_errors(
            root,
            components_by_id,
            task_spec,
            errors,
        )
        return

    roots = ", ".join(sorted(data_roots))
    errors.append(
        f"2x4 card displays two semantic data blocks ({roots}) and must use W9: "
        "root must be a Row with padding 8 and exactly two direct 138x134 "
        "Column backboards with itemMargin 8. Do not use a shared title, a shared action area, or "
        "stacked full-width business rows."
    )


def _collect_2x2_countdown_group_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    visible_binding_paths: list[str],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    has_countdown = any(
        path.endswith("/countdownDays") for path in visible_binding_paths
    )
    if not has_countdown:
        return

    day_units = []
    for component in components:
        if component.component_type != "Text":
            continue
        content = component.props.get("content")
        if not isinstance(content, str):
            continue
        if content.strip() == "天":
            day_units.append(component)
    if len(day_units) > 1:
        errors.append(
            "2x2 countdown must display the day unit exactly once; do not place "
            "'天' beside the value and repeat it again in a second metadata row."
        )
    if not _uses_2x2_v01_countdown_layout(task_spec):
        return

    uses_expanded_layout = _countdown_uses_expanded_layout(
        components, visible_binding_paths
    )

    parent_by_child = {
        child_id: component
        for component in components
        for child_id in component.children
    }
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
                errors.append(
                    "2x2 countdown with an action or additional visible data must "
                    "place the countdown number in a left-aligned value_row; do not "
                    "keep the V01 centered vertical number/unit layout."
                )
                continue
            value_group = parent_by_child.get(direct_parent.component_id)
            if value_group is None or value_group.component_type != "Column":
                errors.append(
                    "2x2 expanded countdown value_row must belong to a full-width "
                    "value_group Column."
                )
                continue
            if value_group.props.get("alignItems") != "start" or direct_parent.props.get(
                "justifyContent"
            ) != "start":
                errors.append(
                    "2x2 countdown with an action or additional visible data must "
                    "left-align value_group and value_row; centered countdown values "
                    "are reserved for the display-only V01 layout."
                )
            if value_group.children and value_group.children[0] != direct_parent.component_id:
                errors.append(
                    "2x2 expanded countdown value_row must be the first child of value_group."
                )
            if len(value_group.children) > 2:
                errors.append(
                    "2x2 expanded countdown value_group may contain only the value_row "
                    "and one optional auxiliary-data row."
                )
            continue
        value_group = direct_parent
        if value_group is None or value_group.component_type != "Column":
            continue
        if len(value_group.children) != 2:
            errors.append(
                "2x2 V01 countdown value_group must contain exactly two visual "
                "rows: the countdown number and a second-line unit/meta row. "
                "Do not add a third aux_text or repeat the target name."
            )
            continue
        second_line = components_by_id.get(value_group.children[1])
        if second_line is None:
            continue
        if second_line.component_type == "Row" and len(second_line.children) > 2:
            errors.append(
                "2x2 V01 countdown meta_row may contain only the unit and the "
                "optional time on the same line."
            )


def _countdown_uses_expanded_layout(
    components: list[ComponentRow], visible_binding_paths: list[str]
) -> bool:
    return any(component.props.get("onClick") for component in components) or any(
        not path.endswith("/countdownDays") for path in visible_binding_paths
    )


def _collect_two_by_four_w9_sparse_layout_errors(
    zone: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    text_components: list[ComponentRow],
    actions: list[ComponentRow],
    errors: list[str],
) -> None:
    if len(text_components) > 3:
        return
    for child_id in zone.children:
        child = components_by_id.get(child_id)
        if child is None or child.component_type != "Column" or child in actions:
            continue
        if child.props.get("layoutWeight") == 1 and child.props.get("justifyContent") == "center":
            return
    suffix = " with its action area" if actions else ""
    errors.append(
        f"2x4 W9 sparse backboard {zone.component_id}{suffix} must use a direct content "
        "Column with layoutWeight 1 and justifyContent center so the primary content "
        "group remains vertically centered."
    )


def _uses_2x2_v01_countdown_layout(task_spec: dict[str, Any]) -> bool:
    if task_spec.get("size") != "2x2":
        return False
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return False
    data_schema = data_model_schema.get("data")
    if not isinstance(data_schema, dict) or not data_schema:
        return False
    if set(data_schema) - {"countdown", "calendar"}:
        return False
    if not _schema_contains_field(data_schema, "countdownDays"):
        return False

    query_value = task_spec.get("userQuery")
    query = query_value.casefold() if isinstance(query_value, str) else ""
    if any(
        marker in query
        for marker in ("倒计时", "倒数", "倒计日", "天后", "countdown")
    ):
        return True
    return "天" in query and any(
        marker in query for marker in ("还有", "剩余", "距离", "多久")
    )


def _schema_contains_field(value: Any, field_name: str) -> bool:
    if isinstance(value, dict):
        return field_name in value or any(
            _schema_contains_field(child, field_name) for child in value.values()
        )
    if isinstance(value, list):
        return any(_schema_contains_field(child, field_name) for child in value)
    return False


def _has_ancestor_component_type(
    component_id: str,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
    component_type: str,
) -> bool:
    current = parent_by_child.get(component_id)
    visited: set[str] = set()
    while current is not None and current not in visited:
        visited.add(current)
        parent = components_by_id.get(current)
        if parent is None:
            return False
        if parent.component_type == component_type:
            return True
        current = parent_by_child.get(current)
    return False


def _is_status_or_ambiguous_text(component: ComponentRow, task_spec: dict[str, Any]) -> bool:
    content = component.props.get("content")
    if isinstance(content, str) and "{{" not in content:
        return any(marker in content for marker in _AMBIGUOUS_STATUS_MARKERS)
    paths: list[str] = []
    _collect_binding_context(
        content,
        f"component {component.component_id}.props.content",
        paths,
        [],
    )
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return False
    for path in paths:
        node = _schema_node_at_path(schema, path)
        description = node.get("description") if isinstance(node, dict) else None
        if isinstance(description, str) and any(
            marker in description for marker in _AMBIGUOUS_METRIC_DESCRIPTION_MARKERS
        ):
            return True
    return False


def _collect_fusion_composition_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    if task_spec.get("size") != "2x2":
        return
    components_by_id = {component.component_id: component for component in components}
    root = components_by_id.get("root")
    design = root.props.get("design") if root is not None else None
    if not isinstance(design, str) or not design.startswith(_FUSION_DESIGN_PREFIX):
        return
    parent_by_child = {
        child_id: parent.component_id
        for parent in components
        for child_id in parent.children
    }
    ring_count = sum(
        component.component_type == "Progress" and component.props.get("type") == "ring"
        for component in components
    )
    action_count = sum(
        component.component_type in {"Button", "ActionUnit"} for component in components
    )
    image_count = sum(
        component.component_type == "Image"
        and not _has_ancestor_component_type(
            component.component_id, parent_by_child, components_by_id, "Progress"
        )
        for component in components
    )
    status_count = sum(
        _is_status_or_ambiguous_text(component, task_spec)
        for component in components
        if component.component_type == "Text"
    )
    if image_count >= 1 and ring_count >= 1 and action_count >= 1 and status_count >= 2:
        errors.append(
            "2x2 fusion-ball cards must not combine a title/auxiliary icon, a ring "
            "Progress, multiple status texts, and a button. Keep one primary visual "
            "focus: remove the icon or ring, merge status text, or fall back to a "
            "non-fusion layout."
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


def _has_nearby_metric_label(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> bool:
    def has_metric_label(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if "{{" in value:
            candidates = [
                match[1:-1].strip()
                for match in _STRING_LITERAL_PATTERN.findall(value)
            ]
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
        child_id: parent.component_id
        for parent in components
        for child_id in parent.children
    }
    for component in components:
        if component.component_type != "Text":
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
        validate_card_header_layout(components, size=task_spec.get("size"))
    except CompactDslConversionError as exc:
        errors.append(str(exc))
    try:
        validate_timeline_unit_layout(components, size=task_spec.get("size"))
    except CompactDslConversionError as exc:
        errors.append(str(exc))
    allowed_handlers = _task_event_handlers(task_spec)
    for component in components:
        _collect_container_errors(component, errors)
        if component.component_type == "ActionUnit":
            _collect_action_unit_errors(component, errors)
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
) -> None:
    """Reject vertical layouts whose declared minimum height cannot fit."""
    components_by_id = {component.component_id: component for component in components}
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


def _collect_action_unit_errors(
    component: ComponentRow,
    errors: list[str],
) -> None:
    location = f"component {component.component_id}"
    state = component.props.get("state")
    if state not in {"capsule", "icon-round"}:
        errors.append(
            f'{location}: ActionUnit.state must be "capsule" or "icon-round".'
        )
        return
    if component.children:
        errors.append(f"{location}: ActionUnit must not declare children.")
    if "onClick" not in component.props:
        errors.append(f"{location}: ActionUnit.onClick is required.")
    if state == "capsule":
        _collect_required_non_empty_string(
            component.props.get("label"),
            f"{location}: capsule ActionUnit.label",
            errors,
        )
        icon = component.props.get("icon")
        if icon is not None and (not isinstance(icon, str) or not icon.strip()):
            errors.append(
                f"{location}: capsule ActionUnit.icon must be a non-empty "
                "string when provided."
            )
        return
    _collect_required_non_empty_string(
        component.props.get("icon"),
        f"{location}: icon-round ActionUnit.icon",
        errors,
    )
    if "label" in component.props:
        errors.append(f"{location}: icon-round ActionUnit must not declare label.")


def _collect_required_non_empty_string(
    value: Any,
    field: str,
    errors: list[str],
) -> None:
    if isinstance(value, str) and value.strip():
        return
    errors.append(f"{field} must be a non-empty string.")


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
        errors.append(
            f"{location}[0]: handler must exactly match a TaskSpec eventCandidate."
        )


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
    return [
        token.replace("~1", "/").replace("~0", "~")
        for token in path[1:].split("/")
    ]
