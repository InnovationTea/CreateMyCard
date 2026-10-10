# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""按原顺序编排 W9 展示语义与布局检查，共享本轮背板分析结果。"""

from __future__ import annotations

import json
import re
from typing import Any

from services.card_validation.compact_validation.context import (
    _descendant_components,
)
from services.card_validation.compact_validation.semantic.display import (
    _collect_w9_action_ownership,
    _collect_w9_action_usage,
    _collect_w9_business_roots,
    _collect_w9_countdown_unit,
    _collect_w9_weather_date_weekday,
    _collect_w9_weather_metric_label,
    _has_w9_weather_field_count_error,
)
from services.card_validation.compact_validation.semantic.layout.regions import (
    _is_two_by_four_direct_action,
)
from services.card_validation.compact_validation.semantic.layout.w9 import (
    _collect_two_by_four_w9_density_errors,
    _collect_two_by_four_w9_sparse_layout_errors,
    _collect_w9_content_row_limit,
    _collect_w9_countdown_typography,
    _collect_w9_countdown_unit_position,
    _collect_w9_text_fact_density,
    _collect_w9_weather_day_rows,
    _collect_w9_weather_day_typography,
    _collect_w9_weather_decoration,
    _collect_w9_weather_divider,
    _collect_w9_weather_fact_rows,
)
from services.card_validation.compact_validation.text import (
    _component_content_paths,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_two_by_four_w9_content_errors(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    total_action_count = 0
    action_fingerprints: set[str] = set()
    has_duplicate_action = False
    parent_by_child: dict[str, ComponentRow] = {}
    for parent in components_by_id.values():
        for child_id in parent.children:
            parent_by_child[child_id] = parent
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

        counted_actions = list(actions)
        if "onClick" in zone.props:
            counted_actions.append(zone)
        total_action_count += len(counted_actions)
        for action in counted_actions:
            fingerprint = json.dumps(
                action.props.get("onClick"),
                ensure_ascii=False,
                sort_keys=True,
            )
            if fingerprint in action_fingerprints:
                has_duplicate_action = True
            action_fingerprints.add(fingerprint)

        _collect_two_by_four_w9_density_errors(
            zone,
            content_regions,
            content_components,
            components_by_id,
            task_spec,
            errors,
        )

        text_components = [
            component for component in content_components if component.component_type == "Text"
        ]
        _collect_two_by_four_w9_sparse_layout_errors(
            zone, components_by_id, text_components, actions, errors
        )
        _collect_w9_content_row_limit(zone, text_components, errors)
        content_roots: set[str] = set()
        paths_by_text: dict[str, list[str]] = {}
        for component in text_components:
            paths = _component_content_paths(component)
            paths_by_text[component.component_id] = paths
            for path in paths:
                parts = path.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "data":
                    content_roots.add(parts[1])

            _collect_w9_text_fact_density(component, paths, errors)
        _collect_w9_business_roots(zone, content_roots, errors)
        if content_roots == {"weather"}:
            _collect_two_by_four_w9_weather_triplet_errors(
                zone,
                text_components,
                content_components,
                paths_by_text,
                errors,
            )

        _collect_w9_action_ownership(zone, counted_actions, content_roots, errors)
        countdown_texts: list[ComponentRow] = []
        countdown_units: list[ComponentRow] = []
        for component in text_components:
            content = component.props.get("content")
            if isinstance(content, str) and content.strip() == "天":
                countdown_units.append(component)
            paths = paths_by_text[component.component_id]
            if not any(path.endswith("/countdownDays") for path in paths):
                continue
            countdown_texts.append(component)
            _collect_w9_countdown_typography(component, errors)
        _collect_w9_countdown_unit(zone, countdown_texts, countdown_units, errors)
        _collect_w9_countdown_unit_position(
            countdown_texts, countdown_units, parent_by_child, errors
        )
        daily_texts: dict[str, set[str]] = {}
        for component in text_components:
            for path in paths_by_text[component.component_id]:
                match = re.match(r"^/data/weather/daily/(\d+)/", path)
                if match is None:
                    continue
                daily_texts.setdefault(match.group(1), set()).add(component.component_id)
        if len(daily_texts) >= 2:
            for day_index, component_ids in daily_texts.items():
                if len(component_ids) == 1:
                    component_id = next(iter(component_ids))
                    component = components_by_id.get(component_id)
                    if component is None:
                        continue
                    day_paths = paths_by_text.get(component_id, [])
                    _collect_w9_weather_date_weekday(component_id, day_paths, errors)
                    _collect_w9_weather_day_typography(component, component_id, errors)
                    continue
                _collect_w9_weather_day_rows(zone, day_index, component_ids, errors)
            _collect_w9_weather_divider(zone, content_components, errors)
    _collect_w9_action_usage(task_spec, has_duplicate_action, total_action_count, errors)


def _collect_two_by_four_w9_weather_triplet_errors(
    zone: ComponentRow,
    text_components: list[ComponentRow],
    content_components: list[ComponentRow],
    paths_by_text: dict[str, list[str]],
    errors: list[str],
) -> None:
    weather_fields = {
        "temperature": ("temperaturerangetext", "温度"),
        "rain": ("rainprobabilitypercent", "降雨"),
        "air": ("airquality", "空气"),
    }
    field_components: dict[str, list[ComponentRow]] = {name: [] for name in weather_fields}
    for component in text_components:
        normalized_paths = [
            path.casefold() for path in paths_by_text.get(component.component_id, [])
        ]
        for field_name, (path_marker, _) in weather_fields.items():
            if any(path_marker in path for path in normalized_paths):
                field_components[field_name].append(component)
    if not all(field_components.values()):
        return

    _collect_w9_weather_decoration(zone, content_components, errors)
    for field_name, (_, label) in weather_fields.items():
        matched_components = field_components[field_name]
        if _has_w9_weather_field_count_error(zone, field_name, matched_components, errors):
            continue
        component = matched_components[0]
        component_paths = paths_by_text.get(component.component_id, [])
        _collect_w9_weather_fact_rows(component, component_paths, errors)
        _collect_w9_weather_metric_label(component, label, errors)
