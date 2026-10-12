# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：flows.contracts。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.semantic.bindings import (
    _collect_binding_data_errors,
)
from services.card_validation.compact_validation.semantic.cross_file import (
    _checked_data_schema,
    _collect_data_type_error,
    _collect_undeclared_data_path_error,
)
from services.card_validation.compact_validation.semantic.effective import (
    _collect_event_candidate_error,
    _task_event_handlers,
)
from services.card_validation.compact_validation.syntax.components import (
    _collect_component_parent_errors,
    _collect_container_errors,
    _collect_on_click_structure_errors,
)
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    validate_single_line_title_layout,
)


def _collect_component_contract_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    _collect_component_parent_errors(components, errors)
    try:
        validate_single_line_title_layout(components, size=task_spec.get("size"))
    except CompactDslConversionError as exc:
        errors.append(str(exc))
    allowed_handlers = _task_event_handlers(task_spec)
    for component in components:
        _collect_container_errors(component, errors)
        shape = _collect_on_click_structure_errors(component, errors)
        if shape.handler is not None:
            _collect_event_candidate_error(component, shape.handler, allowed_handlers, errors)


def _collect_data_context_errors(
    binding_paths: list[str],
    data_rows: list[DataRow],
    data_model: dict[str, Any],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    _collect_binding_data_errors(binding_paths, data_model, errors)
    data_model_schema = _checked_data_schema(task_spec, errors)
    if data_model_schema is None:
        return
    paths_to_validate = list(dict.fromkeys(binding_paths))
    paths_to_validate.extend(row.path for row in data_rows)
    for path in dict.fromkeys(paths_to_validate):
        _collect_undeclared_data_path_error(path, data_model_schema, errors)
    for row in data_rows:
        _collect_data_type_error(row, data_model_schema, errors)
