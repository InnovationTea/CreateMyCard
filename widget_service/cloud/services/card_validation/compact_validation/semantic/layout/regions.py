# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.regions。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import (
    _descendant_components,
    component_graph,
)
from services.card_validation.compact_validation.schema import (
    _schema_contains_field,
    _schema_field_names,
    _schema_leaf_count,
)
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _TWO_BY_FOUR_AUX_CELL_HEIGHT,
    _TWO_BY_FOUR_AUX_WIDTH,
    _TWO_BY_FOUR_FOCUS_AUX_HEIGHT,
    _TWO_BY_FOUR_FOCUS_WIDTH,
    _TWO_BY_FOUR_MULTI_LARGE_HEIGHT,
    _TWO_BY_FOUR_MULTI_LARGE_WIDTH,
    _TWO_BY_FOUR_MULTI_ROOT_PADDING,
    _non_negative_number,
    _visual_text_line_profile,
)
from services.card_validation.compact_validation.text import _component_content_paths
from services.compact_dsl_a2ui_converter import ComponentRow


def _is_large_2x4_panel(
    component: ComponentRow,
    components: list[ComponentRow],
) -> bool:
    child_to_parents = component_graph(components).all_parents

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


def _two_by_four_data_block_count(
    task_spec: dict[str, Any],
    data_roots: set[str],
) -> int:
    metric_grid_count = _two_by_four_metric_grid_count(task_spec)
    if metric_grid_count >= 4:
        return metric_grid_count
    block_count = len(data_roots)
    if "healthSport" not in data_roots:
        return block_count

    data_model_schema = task_spec.get("dataModelSchema")
    schema_data = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
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


def _two_by_four_metric_grid_count(task_spec: dict[str, Any]) -> int:
    """Count independent weather-related metrics that should use W8."""
    if task_spec.get("size") != "2x4":
        return 0
    data_model_schema = task_spec.get("dataModelSchema")
    data_schema = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
    if not isinstance(data_schema, dict):
        return 0
    normalized_roots = {str(root).casefold() for root in data_schema}
    if "weather" not in normalized_roots:
        return 0
    if normalized_roots.intersection({"countdown", "calendar", "earphone"}):
        return 0
    if not normalized_roots.issubset({"weather", "healthsport", "phonebattery"}):
        return 0

    weather_schema = None
    metric_count = 0
    for root_name, root_value in data_schema.items():
        normalized_root = str(root_name).casefold()
        if normalized_root == "weather":
            weather_schema = root_value
            continue
        metric_count += _schema_leaf_count(root_value)
    weather_fields = _schema_field_names(weather_schema)
    weather_groups = (
        ("temperature", "feelslike", "humidity"),
        ("winddirection", "windlevel"),
        ("alert", "warning"),
        ("airquality",),
        ("rainprobability",),
    )
    for markers in weather_groups:
        group_matches = False
        for marker in markers:
            if any(marker in field_name for field_name in weather_fields):
                group_matches = True
                break
        if group_matches:
            metric_count += 1
    return metric_count


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
    data_schema = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
    if not isinstance(data_schema, dict) or not data_schema:
        return False
    if _two_by_four_metric_grid_count(task_spec) >= 4:
        return False

    roots = tuple(data_schema)
    normalized_roots = {root.casefold() for root in roots}
    if "countdown" in normalized_roots or len(roots) > 2:
        return False
    candidate_count = len(task_spec.get("eventCandidates") or [])
    if len(roots) == 1:
        root_value = next(iter(data_schema.values()))
        leaf_count = _schema_leaf_count(root_value)
        field_names = _schema_field_names(root_value)
        if "healthsport" in normalized_roots:
            return _schema_leaf_count(data_schema) >= 4
        if "phonebattery" in normalized_roots:
            return _is_dense_phone_battery_schema(root_value)
        if "earphone" in normalized_roots:
            has_paired_charging = any("leftcharging" in name for name in field_names) and any(
                "rightcharging" in name for name in field_names
            )
            has_two_requested_actions = candidate_count >= 2
            return leaf_count >= 6 or (
                leaf_count >= 4 and (has_paired_charging or has_two_requested_actions)
            )
        if "calendar" in normalized_roots:
            has_reminder = any("remind" in name for name in field_names)
            return candidate_count > 0 and leaf_count >= 4 and has_reminder
        if "weather" in normalized_roots:
            advisory_groups = (
                ("alert", "warning"),
                ("airquality",),
                ("uv",),
                ("cold",),
            )
            advisory_count = 0
            for markers in advisory_groups:
                group_matches = False
                for marker in markers:
                    if any(marker in name for name in field_names):
                        group_matches = True
                        break
                if group_matches:
                    advisory_count += 1
            return candidate_count > 0 and leaf_count >= 4 and advisory_count >= 2
        return False

    supported = normalized_roots == {"calendar", "phonebattery"} or (
        "healthsport" in normalized_roots
    )
    if supported and _schema_leaf_count(data_schema) >= 3:
        return True

    if normalized_roots == {"phonebattery", "earphone"}:
        earphone_schema = None
        for root_name, root_value in data_schema.items():
            if str(root_name).casefold() == "earphone":
                earphone_schema = root_value
                break
        if (
            candidate_count > 0
            and earphone_schema is not None
            and _schema_leaf_count(earphone_schema) >= 4
        ):
            return True

    fact_counts = sorted(_schema_leaf_count(value) for value in data_schema.values())
    has_clear_density_imbalance = (
        fact_counts[0] <= 2
        and fact_counts[1] >= 3
        and fact_counts[1] - fact_counts[0] >= 2
        and (fact_counts[0] == 1 or len(task_spec.get("eventCandidates") or []) <= 1)
    )
    return has_clear_density_imbalance


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


def _is_two_by_four_direct_action(component: ComponentRow | None) -> bool:
    if component is None:
        return False
    if component.component_type == "Button":
        return True
    return component.component_type == "Row" and "onClick" in component.props


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
    has_expected_root_layout = root.props.get("padding") == 8 and root.props.get("itemMargin") == 8
    if len(root.children) != 2 or not has_expected_root_layout:
        return False
    for child_id in root.children:
        zone = components_by_id.get(child_id)
        if zone is None or zone.component_type not in {"Row", "Column"}:
            return False
        if zone.props.get("width") != 134 or zone.props.get("height") != 63:
            return False
    return True


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
                        object_end = index + 1
                        object_id = "/".join(parts[1:object_end])
                        break
                object_ids.add(object_id)
    return len(object_ids)


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


def _has_expected_two_by_four_aux_icon_layout(
    cell: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if cell.component_type != "Row" or len(cell.children) != 2:
        return False
    children = [components_by_id.get(child_id) for child_id in cell.children]
    visual_count = sum(child is not None and child.component_type == "Image" for child in children)
    if visual_count != 1:
        return False
    text_container = None
    for child in children:
        if child is None:
            continue
        if child.component_type in {"Column", "Text"}:
            text_container = child
            break
    if text_container is None:
        return False
    if text_container.component_type == "Text":
        return text_container.props.get("maxLines") == 1
    if not 1 <= len(text_container.children) <= 2:
        return False
    for child_id in text_container.children:
        text = components_by_id.get(child_id)
        if text is None or text.component_type != "Text" or text.props.get("maxLines") != 1:
            return False
    return True


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
    invalid_aux_size = (
        aux_column.props.get("width") != _TWO_BY_FOUR_AUX_WIDTH
        or aux_column.props.get("height") != _TWO_BY_FOUR_FOCUS_AUX_HEIGHT
    )
    if invalid_aux_size or aux_column.props.get("itemMargin") != 8 or len(aux_column.children) != 2:
        return False
    return all(
        _is_two_by_four_focus_aux_cell(components_by_id.get(cell_id))
        for cell_id in aux_column.children
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
            if not _is_two_by_four_small_backboard(components_by_id.get(zone_id)):
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
        _is_two_by_four_small_backboard(components_by_id.get(zone_id)) for zone_id in side.children
    )


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


def _action_control_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> int:
    candidates = [component, *_descendant_components(component, components_by_id)]
    count = 0
    for candidate in candidates:
        if candidate.component_type in {"ActionUnit", "Button"}:
            count += 1
            continue
        if candidate.component_type == "Row" and "onClick" in candidate.props:
            count += 1
    return count


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
    if any(marker in query for marker in ("倒计时", "倒数", "倒计日", "天后", "countdown")):
        return True
    return "天" in query and any(marker in query for marker in ("还有", "剩余", "距离", "多久"))
