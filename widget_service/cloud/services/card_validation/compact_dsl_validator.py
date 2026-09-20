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

_EXPRESSION_PATTERN = re.compile(r"^\{\{\s*(?P<body>.*?)\s*\}\}$")
_REFERENCE_PATTERN = re.compile(r"\$\{(?P<path>[^{}]*)\}")
_SIMPLE_FORMATTED_EXPRESSION_PATTERN = re.compile(
    r"^\{\{\s*\$\{(?P<path>/[^{}]+)\}\s*\+\s*'(?P<unit>[^']+)'\s*\}\}$"
)
_NON_EMPTY_CONTAINER_TYPES = frozenset({"Row", "Column", "List", "Stack"})
_REFERENCE_CANVAS_HEIGHT = {
    "2x2": 160.0,
    "2x4": 160.0,
    "4x2": 160.0,
}
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
    }
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
    _collect_component_contract_errors(components, task_spec, errors)
    _collect_two_by_two_weather_date_errors(components, task_spec, errors)
    _collect_hero_value_errors(components, task_spec, errors)
    _collect_height_budget_errors(components, task_spec, card_spec, errors)
    size = card_spec.get("suggestSize") or task_spec.get("size")
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

    _collect_layout_route_errors(
        components,
        task_spec,
        visible_binding_paths,
        errors,
    )

    data_model = build_compact_data_model(data_rows)
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

    if task_spec.get("size") == "2x2":
        _collect_adjacent_display_unit_errors(
            components,
            components_by_id,
            data_model_schema,
            errors,
        )

    numeric_paths: dict[str, str | None] = {}
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
            continue
        errors.append(
            f"component {component.component_id}: fontSize {_format_vp(font_size)} "
            "is reserved for a pure number/integer value. Text, formatted values, "
            "names, dates, times, and statuses must use at most 18fp on their own line; "
            "a directly bound temperature, duration, or percentage may use 20/24fp "
            "only in a single-business full-width column with a sufficient text budget."
        )

    for component in components:
        if component.component_type != "Row":
            continue
        for index, child_id in enumerate(component.children[:-1]):
            if child_id not in numeric_paths:
                continue
            numeric_path = numeric_paths[child_id]
            suffix = components_by_id.get(component.children[index + 1])
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
        component_width == 136.0
        if task_spec.get("size") == "2x2"
        else component_width == 296.0
    )
    is_large_2x4_panel = (
        task_spec.get("size") == "2x4"
        and component_width == 120.0
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
        return (path, None) if isinstance(path, str) else (None, None)
    if not isinstance(content, str):
        return None, None
    match = _SIMPLE_FORMATTED_EXPRESSION_PATTERN.fullmatch(content.strip())
    if match is None:
        return None, None
    return match.group("path"), match.group("unit")


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
            if width == 144.0 and height == 136.0:
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
    percentage = any(word in description for word in ("百分比", "百分率"))
    percentage = percentage and re.fullmatch(r"\d+(?:\.\d+)?%", sample) is not None
    pressure: str | None = None
    if temperature or duration or percentage:
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
            unit = suffix_content.strip()
            if unit not in _COMMON_DISPLAY_UNITS:
                continue
            value_path = _pure_binding_path(value.props.get("content"))
            if not value_path:
                continue
            schema_type = _schema_type(
                _schema_node_at_path(data_model_schema, value_path)
            )
            if schema_type in _NUMERIC_SCHEMA_TYPES:
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
            is_full_width_backboard = child.props.get("width") == 296
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
    if component.props.get("width") != 144:
        return False
    if component.props.get("height") != 136:
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
    if action.props.get("width") != 120 or action.props.get("height") != 36:
        errors.append(
            f"2x4 large backboard {backboard.component_id} action must be 120x36."
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
            "contain at most four Text rows: title, primary value, and up to "
            "two auxiliary rows. Merge or remove lower-priority fields."
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
        if action.props.get("width") != 296 or action.props.get("height") != 36:
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
                f"{action.component_id} must use layoutWeight 1 so the 296x36 "
                "action remains fixed at the bottom without overlapping content."
            )


def _is_2x2_small_backboard(component: ComponentRow | None) -> bool:
    if component is None or component.component_type not in {"Row", "Column"}:
        return False
    if component.props.get("width") != 136:
        return False
    if component.props.get("height") != 64:
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
    if len(root.children) != 2 or root.props.get("itemMargin") != 8:
        return False
    for child_id in root.children:
        zone = components_by_id.get(child_id)
        if zone is None or zone.component_type not in {"Row", "Column"}:
            return False
        if zone.props.get("width") != 136 or zone.props.get("height") != 64:
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


def _binding_roots(value: Any, location: str) -> set[str]:
    paths: list[str] = []
    _collect_binding_context(value, location, paths, [])
    roots: set[str] = set()
    for path in paths:
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "data":
            roots.add(parts[1])
    return roots


def _collect_two_by_four_w9_content_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    for zone_id in root.children:
        zone = components_by_id.get(zone_id)
        if zone is None:
            continue

        content_components: list[ComponentRow] = []
        actions: list[ComponentRow] = []
        for child_id in zone.children:
            child = components_by_id.get(child_id)
            if child is None:
                continue
            if _is_two_by_four_direct_action(child):
                actions.append(child)
                continue
            content_components.append(child)
            content_components.extend(_descendant_components(child, components_by_id))

        text_components = [
            component
            for component in content_components
            if component.component_type == "Text"
        ]
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
        for component in text_components:
            paths = paths_by_text[component.component_id]
            if not any(path.endswith("/countdownDays") for path in paths):
                continue
            has_countdown = True
            font_size = _non_negative_number(component.props.get("fontSize"))
            if font_size != 14 or component.props.get("fontWeight") != 700:
                errors.append(
                    f"2x4 W9 countdown {component.component_id} must use ordinary "
                    "14fp/700 primary text; do not reuse the single-business hero."
                )
        if has_countdown:
            for component in text_components:
                content = component.props.get("content")
                if isinstance(content, str) and content.strip() == "天":
                    errors.append(
                        f"2x4 W9 countdown backboard {zone.component_id} must "
                        "combine the value and unit in one Text (for example, "
                        "`30天`); do not place `天` on a separate row."
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
    if len(root.children) != 2 or root.props.get("itemMargin") != 8:
        return False
    for child_id in root.children:
        backboard = components_by_id.get(child_id)
        if not _is_two_by_four_large_backboard(backboard):
            return False
    return True


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
                "2x4 cards must not stack two or more full-width 296x48-64 "
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
                    "144x136 backboard; remove duplicate or lower-priority actions."
                )

    if size == "2x2" and len(data_roots) == 1:
        if root is not None and len(root.children) == 1:
            only_child = components_by_id.get(root.children[0])
            if _is_2x2_small_backboard(only_child):
                errors.append(
                    "2x2 card has one data root and must use a full-width "
                    "single-business layout; do not generate an isolated "
                    "136x64 S4 backboard."
                )
        _collect_2x2_countdown_group_errors(
            components,
            components_by_id,
            visible_binding_paths,
            task_spec,
            errors,
        )
        return

    data_block_count = len(data_roots)
    if size == "2x4":
        data_block_count = _two_by_four_data_block_count(task_spec, data_roots)
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
            "must be a Column with exactly two direct 136x64 Row/Column "
            "backboards and itemMargin 8. Countdown remains ordinary 14fp/700 "
            "primary text inside its backboard."
        )
        return

    if root is not None and _has_two_by_four_w9_backboards(root, components_by_id):
        _collect_two_by_four_w9_content_errors(
            root,
            components_by_id,
            errors,
        )
        return

    roots = ", ".join(sorted(data_roots))
    errors.append(
        f"2x4 card displays two semantic data blocks ({roots}) and must use W9: "
        "root must be a Row with exactly two direct 144x136 Column backboards "
        "and itemMargin 8. Do not use a shared title, a shared action area, or "
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
        value_group = parent_by_child.get(countdown_value.component_id)
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
