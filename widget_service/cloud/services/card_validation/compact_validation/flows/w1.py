# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""按原顺序编排 W1 的展示语义与布局检查。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import _descendant_components
from services.card_validation.compact_validation.semantic.display import (
    _collect_w1_cell_business_roots,
    _collect_w1_complete_fact_lines,
    _collect_w1_duplicate_facts,
    _collect_w1_progress_request_error,
    _collect_w1_required_action_cells,
)
from services.card_validation.compact_validation.semantic.layout.w1 import (
    _collect_two_by_four_w1_focus_alignment_errors,
    _collect_w1_battery_progress_shape,
    _collect_w1_cell_fact_density,
    _collect_w1_cell_text_layout,
    _collect_w1_focus_structure_errors,
    _collect_w1_nested_action,
    _collect_w1_progress_readout,
)
from services.card_validation.compact_validation.text import (
    _component_content_paths,
)
from services.compact_dsl_a2ui_converter import ComponentRow


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
    focus_text_paths: set[str] = set()
    for component in focus_components:
        if component.component_type == "Text":
            focus_text_paths.update(_component_content_paths(component))
    aux_components = [
        aux_column,
        *_descendant_components(aux_column, components_by_id),
    ]
    aux_text_paths: set[str] = set()
    for component in aux_components:
        if component.component_type == "Text":
            aux_text_paths.update(_component_content_paths(component))
    _collect_w1_duplicate_facts(focus_text_paths, aux_text_paths, errors)
    _collect_w1_focus_structure_errors(focus, focus_components, components_by_id, errors)
    has_progress = _collect_w1_progress_request_error(task_spec, focus_components, errors)
    _collect_w1_progress_readout(focus, focus_components, has_progress, errors)
    data_model_schema = task_spec.get("dataModelSchema")
    data_schema = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
    normalized_roots = (
        {str(root_name).casefold() for root_name in data_schema}
        if isinstance(data_schema, dict)
        else set()
    )
    _collect_two_by_four_w1_focus_alignment_errors(
        focus,
        focus_components,
        normalized_roots,
        components_by_id,
        errors,
    )
    _collect_w1_battery_progress_shape(focus_components, has_progress, normalized_roots, errors)
    _collect_w1_required_action_cells(task_spec, aux_column, components_by_id, errors)
    for cell_id in aux_column.children:
        cell = components_by_id.get(cell_id)
        if cell is None:
            continue
        cell_components = [cell, *_descendant_components(cell, components_by_id)]
        cell_texts: list[ComponentRow] = []
        for component in cell_components:
            if component.component_type == "Text":
                cell_texts.append(component)
        text_count = _collect_w1_cell_text_layout(cell, cell_components, cell_texts, errors)
        visible_paths: set[str] = set()
        paths_per_text: list[list[str]] = []
        for component in cell_components:
            if component.component_type == "Text":
                component_paths = _component_content_paths(component)
                paths_per_text.append(component_paths)
                visible_paths.update(component_paths)
        normalized_paths = {path.casefold() for path in visible_paths}
        is_paired_earphone_summary = (
            text_count == 2
            and len(visible_paths) <= 4
            and bool(normalized_paths)
            and all(path.startswith("/data/earphone/") for path in normalized_paths)
            and any("/left" in path for path in normalized_paths)
            and any("/right" in path for path in normalized_paths)
            and all(len(component_paths) <= 2 for component_paths in paths_per_text)
        )
        _collect_w1_cell_fact_density(
            cell, visible_paths, text_count, is_paired_earphone_summary, errors
        )
        _collect_w1_complete_fact_lines(
            cell, visible_paths, paths_per_text, is_paired_earphone_summary, errors
        )
        _collect_w1_nested_action(cell, cell_components, errors)
        _collect_w1_cell_business_roots(cell, cell_components, errors)
