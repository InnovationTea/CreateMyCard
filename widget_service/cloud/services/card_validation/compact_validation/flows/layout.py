# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""保留原布局路由顺序，调度各类规则和跨类别检查流程。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import (
    component_index,
)
from services.card_validation.compact_validation.flows.two_by_two import (
    _collect_2x2_countdown_group_errors,
    _collect_two_by_two_s4_text_errors,
)
from services.card_validation.compact_validation.flows.w1 import (
    _collect_two_by_four_w1_focus_aux_errors,
)
from services.card_validation.compact_validation.flows.w9 import (
    _collect_two_by_four_w9_content_errors,
)
from services.card_validation.compact_validation.semantic.layout.regions import (
    _has_two_by_two_s4_zones,
    _is_two_by_four_large_backboard,
    _two_by_four_data_block_count,
    _uses_2x2_v01_countdown_layout,
    _uses_two_by_four_focus_aux_layout,
)
from services.card_validation.compact_validation.semantic.layout.routing import (
    _collect_backboard_action_count,
    _collect_s4_countdown_typography,
    _collect_s4_object_count,
    _collect_single_business_structure,
    _collect_stacked_backboards,
    _collect_w8_skeleton,
    _collect_w10_skeleton,
    _validate_s4_skeleton,
    _validate_w1_skeleton,
    _validate_w9_skeleton,
)
from services.card_validation.compact_validation.semantic.layout.two_by_four import (
    _collect_two_by_four_action_backboard_errors,
    _collect_two_by_four_aux_icon_errors,
    _collect_two_by_four_countdown_backboard_errors,
    _collect_two_by_four_detached_unit_errors,
    _collect_two_by_four_full_width_action_errors,
    _collect_two_by_four_small_backboard_errors,
    _collect_two_by_four_weather_calendar_alignment_errors,
)
from services.card_validation.compact_validation.semantic.layout.two_by_two import (
    _collect_two_by_two_centered_hero_errors,
    _collect_two_by_two_content_density_errors,
    _collect_two_by_two_narrow_graphical_action_errors,
    _collect_two_by_two_ring_group_alignment_errors,
    _collect_two_by_two_s4_palette_errors,
    _collect_two_by_two_s4_vertical_alignment_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_layout_route_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    visible_binding_paths: list[str],
    errors: list[str],
) -> None:
    size = task_spec.get("size")
    if size not in {"2x2", "2x4"}:
        return

    components_by_id = component_index(components)
    root = components_by_id.get("root")
    if size == "2x4":
        _collect_two_by_four_small_backboard_errors(
            components,
            components_by_id,
            errors,
        )
    _collect_two_by_two_content_density_errors(
        components,
        task_spec,
        components_by_id,
        errors,
    )
    _collect_two_by_two_centered_hero_errors(
        task_spec,
        root,
        components_by_id,
        errors,
    )
    if size == "2x2" and root is not None and _has_two_by_two_s4_zones(root, components_by_id):
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

    visible_data_roots: set[str] = set()
    for path in visible_binding_paths:
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "data":
            visible_data_roots.add(parts[1])
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
        schema_data = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
        if isinstance(schema_data, dict):
            data_roots = set(schema_data)

    if size == "2x4":
        _collect_two_by_four_detached_unit_errors(
            components,
            components_by_id,
            task_spec,
            errors,
        )
        _collect_two_by_four_weather_calendar_alignment_errors(
            components,
            task_spec,
            errors,
        )
        _collect_two_by_four_full_width_action_errors(
            components,
            components_by_id,
            errors,
        )
        _collect_two_by_four_aux_icon_errors(
            components,
            components_by_id,
            errors,
        )
        _collect_stacked_backboards(components, components_by_id, errors)
        for component in components:
            if not _is_two_by_four_large_backboard(component):
                continue
            _collect_two_by_four_countdown_backboard_errors(
                component,
                components_by_id,
                errors,
            )
            _collect_two_by_four_action_backboard_errors(
                component,
                components_by_id,
                errors,
            )
            _collect_backboard_action_count(component, components_by_id, errors)
    if size == "2x2" and len(data_roots) == 1:
        _collect_single_business_structure(root, components_by_id, errors)
        _collect_2x2_countdown_group_errors(
            components,
            components_by_id,
            visible_binding_paths,
            task_spec,
            errors,
        )
        return

    if size == "2x4" and _uses_two_by_four_focus_aux_layout(task_spec):
        if _validate_w1_skeleton(root, components_by_id, errors):
            _collect_two_by_four_w1_focus_aux_errors(
                root,
                components_by_id,
                task_spec,
                errors,
            )
            return
        return

    data_block_count = len(data_roots)
    if size == "2x4":
        data_block_count = _two_by_four_data_block_count(task_spec, data_roots)
        if data_block_count >= 4:
            _collect_w8_skeleton(root, components_by_id, errors)
            return
        if data_block_count == 3:
            _collect_w10_skeleton(root, components_by_id, errors)
            return
    if size == "2x2" and _collect_s4_object_count(root, components_by_id, errors):
        return
    if data_block_count != 2:
        return

    if size == "2x2":
        if _validate_s4_skeleton(root, components_by_id, data_roots, errors):
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
            _collect_s4_countdown_typography(components, data_roots, errors)
            return
        return

    if _validate_w9_skeleton(root, components_by_id, data_roots, errors):
        _collect_two_by_four_w9_content_errors(
            root,
            components_by_id,
            task_spec,
            errors,
        )
        return
