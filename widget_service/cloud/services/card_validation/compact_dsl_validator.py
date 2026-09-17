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
)

_EXPRESSION_PATTERN = re.compile(r"^\{\{\s*(?P<body>.*?)\s*\}\}$")
_REFERENCE_PATTERN = re.compile(r"\$\{(?P<path>[^{}]*)\}")
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
    _collect_hero_value_errors(components, task_spec, errors)
    _collect_height_budget_errors(components, task_spec, card_spec, errors)
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
        errors.append(
            f"component {component.component_id}: fontSize {_format_vp(font_size)} "
            "is reserved for a pure number/integer value. Text, formatted values, "
            "names, dates, times, and statuses must use at most 18fp on their own line."
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


def _pure_numeric_binding_path(
    content: Any,
    data_model_schema: dict[str, Any],
) -> str | None:
    path: str | None = None
    if isinstance(content, dict) and set(content) == {"path"}:
        candidate = content.get("path")
        path = candidate if isinstance(candidate, str) else None
    elif isinstance(content, str):
        match = _EXPRESSION_PATTERN.fullmatch(content.strip())
        if match is not None:
            reference = _REFERENCE_PATTERN.fullmatch(match.group("body").strip())
            if reference is not None:
                path = reference.group("path").strip()
        elif re.fullmatch(r"[+-]?\d+(?:\.\d+)?", content.strip()):
            return ""
    if path is None:
        return None
    schema_node = _schema_node_at_path(data_model_schema, path)
    if _schema_type(schema_node) not in _NUMERIC_SCHEMA_TYPES:
        return None
    return path


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


def _collect_layout_route_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    visible_binding_paths: list[str],
    errors: list[str],
) -> None:
    size = task_spec.get("size")
    if size not in {"2x2", "2x4"}:
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

    components_by_id = {
        component.component_id: component for component in components
    }
    root = components_by_id.get("root")
    if size == "2x2" and len(data_roots) == 1:
        event_candidates = task_spec.get("eventCandidates")
        if isinstance(event_candidates, list) and len(event_candidates) == 2:
            _collect_2x2_dual_action_layout_errors(
                components_by_id,
                root,
                errors,
            )
            return
        if root is not None and len(root.children) == 1:
            only_child = components_by_id.get(root.children[0])
            if _is_2x2_small_backboard(only_child):
                errors.append(
                    "2x2 card has one data root and must use a full-width "
                    "single-business layout; do not generate an isolated "
                    "136x64 S4 backboard or add an Image to ordinary content."
                )
        _collect_2x2_countdown_group_errors(
            components,
            components_by_id,
            visible_binding_paths,
            errors,
        )
        return
    if len(data_roots) != 2:
        return

    if size == "2x2":
        if root is not None and root.component_type == "Column":
            zones = [components_by_id.get(child_id) for child_id in root.children]
            has_s4_zones = len(zones) == 2 and all(
                zone is not None
                and zone.component_type in {"Row", "Column"}
                and zone.props.get("width") == 136
                and zone.props.get("height") == 64
                for zone in zones
            )
            if has_s4_zones and root.props.get("itemMargin") == 8:
                if "countdown" in data_roots:
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
                            path.startswith("/data/countdown/")
                            for path in component_paths
                        ):
                            countdown_texts.append(component)
                    countdown_style_valid = countdown_texts and all(
                        _non_negative_number(component.props.get("fontSize")) == 14
                        and component.props.get("fontWeight") == 700
                        for component in countdown_texts
                    )
                    if not countdown_style_valid:
                        errors.append(
                            "2x2 S4 countdown must be displayed as ordinary "
                            "14fp/700 primary text inside its backboard; do not "
                            "reuse the V01 30fp/38fp hero or 800 font weight."
                        )
                        return
                return

        roots = ", ".join(sorted(data_roots))
        errors.append(
            f"2x2 card displays two data roots ({roots}) and must use S4: root "
            "must be a Column with exactly two direct 136x64 Row/Column "
            "backboards and itemMargin 8. Apply S4 text layout inside both "
            "backboards; countdown is only a 14fp/700 primary value, never a "
            "30fp/38fp hero or a standalone countdown group."
        )
        return

    if root is not None and root.component_type == "Row" and len(root.children) == 2:
        backboards = [components_by_id.get(child_id) for child_id in root.children]
        if all(
            backboard is not None
            and backboard.component_type == "Column"
            and backboard.props.get("width") == 144
            and backboard.props.get("height") == 136
            for backboard in backboards
        ):
            return

    roots = ", ".join(sorted(data_roots))
    errors.append(
        f"2x4 card displays two data roots ({roots}) and must use W9: root must "
        "be a Row with exactly two direct 144x136 Column backboards. Do not use "
        "a shared title, a shared action area, or stacked full-width business rows."
    )


def _collect_2x2_dual_action_layout_errors(
    components_by_id: dict[str, ComponentRow],
    root: ComponentRow | None,
    errors: list[str],
) -> None:
    if root is None or root.component_type != "Column" or len(root.children) != 2:
        errors.append(
            "2x2 single-business card with two actions must use S3: root must be "
            "a Column containing only header_area and action_area."
        )
        return

    header = components_by_id.get(root.children[0])
    action_area = components_by_id.get(root.children[1])
    header_valid = header is not None and all(
        (
            header.component_type == "Column",
            header.props.get("width") == 136,
            header.props.get("height") == 48,
            len(header.children) == 2,
        )
    )
    actions_valid = action_area is not None and all(
        (
            action_area.component_type == "Column",
            action_area.props.get("width") == 136,
            action_area.props.get("itemMargin") == 8,
            len(action_area.children) == 2,
        )
    )
    if root.props.get("itemMargin") != 8 or not header_valid or not actions_valid:
        errors.append(
            "2x2 S3 must use a 136x48 header_area, an 8vp root gap, and an "
            "action_area containing two 136x36 ActionUnit capsules with 8vp gap."
        )
        return

    assert header is not None
    assert action_area is not None
    title = components_by_id.get(header.children[0])
    summary = components_by_id.get(header.children[1])
    text_styles_valid = _matches_single_line_text_style(
        title,
        font_size=14,
        font_weight=700,
    ) and _matches_single_line_text_style(
        summary,
        font_size=12,
        font_weight=400,
    )
    if not text_styles_valid:
        errors.append(
            "2x2 S3 header_area must contain exactly two single-line Text rows: "
            "a 14fp/700 business title and one 12fp/400 merged data summary. "
            "Do not use a hero number, value_row, or a third information row."
        )

    action_components = [
        components_by_id.get(child_id) for child_id in action_area.children
    ]
    if any(
        component is None or component.component_type != "ActionUnit"
        for component in action_components
    ):
        errors.append(
            "2x2 S3 action_area must contain exactly two ActionUnit capsules."
        )

    if summary is None or summary.component_type != "Text":
        return
    summary_paths: list[str] = []
    _collect_binding_context(
        summary.props.get("content"),
        f"component {summary.component_id}.props.content",
        summary_paths,
        [],
    )
    if len(set(summary_paths)) > 1 and " | " not in str(summary.props.get("content")):
        errors.append(
            "2x2 S3 must merge multiple data fields into its second line with "
            'the ASCII separator " | ".'
        )


def _matches_single_line_text_style(
    component: ComponentRow | None,
    *,
    font_size: int,
    font_weight: int,
) -> bool:
    if component is None or component.component_type != "Text":
        return False
    return all(
        (
            component.props.get("fontSize") == font_size,
            component.props.get("fontWeight") == font_weight,
            component.props.get("maxLines") == 1,
        )
    )


def _is_2x2_small_backboard(component: ComponentRow | None) -> bool:
    if component is None:
        return False
    if component.component_type not in {"Row", "Column"}:
        return False
    if component.props.get("width") != 136:
        return False
    if component.props.get("height") != 64:
        return False
    if "backgroundColor" not in component.props:
        return False
    return component.props.get("borderRadius") in {12, 16}


def _collect_2x2_countdown_group_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    visible_binding_paths: list[str],
    errors: list[str],
) -> None:
    has_countdown = any(
        path.endswith("/countdownDays") for path in visible_binding_paths
    )
    if not has_countdown:
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


def _collect_component_contract_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    try:
        validate_card_header_layout(components, size=task_spec.get("size"))
    except CompactDslConversionError as exc:
        errors.append(str(exc))
    allowed_handlers = _task_event_handlers(task_spec)
    for component in components:
        _collect_container_errors(component, errors)
        if component.component_type == "ActionUnit":
            _collect_action_unit_errors(component, errors)
        _collect_on_click_errors(component, allowed_handlers, errors)


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
    references = list(_REFERENCE_PATTERN.finditer(body))
    if not references:
        _collect_missing_reference_error(body, location, errors)
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


def _collect_missing_reference_error(
    body: str,
    location: str,
    errors: list[str],
) -> None:
    quoted_path = _quoted_expression_path(body)
    if quoted_path is not None:
        errors.append(
            f'{location}: expression wraps quoted JSON Pointer "{quoted_path}"; '
            f"use ${{{quoted_path}}} for a dynamic binding, or use a plain "
            "static value without {{ }}."
        )
        return
    errors.append(
        f"{location}: expression has no ${{/json/pointer}} reference; "
        "use a plain static value instead."
    )


def _quoted_expression_path(body: str) -> str | None:
    if not _is_quoted_literal(body):
        return None
    candidate = body[1:-1]
    if not candidate.startswith("/"):
        return None
    return candidate


def _is_quoted_literal(value: str) -> bool:
    if len(value) < 2 or value[0] not in {"'", '"'}:
        return False
    quote = value[0]
    if value[-1] != quote:
        return False
    escaped = False
    for char in value[1:-1]:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == quote:
            return False
    return not escaped


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
