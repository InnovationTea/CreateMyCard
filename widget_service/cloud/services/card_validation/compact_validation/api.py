# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：api。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.card_validation.compact_dual_action_validator import collect_dual_action_errors
from services.card_validation.compact_validation.context import ComponentRows, ValidationContext
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    CompactDslValidationError,
    CompactDslValidationResult,
    DiagnosticCollector,
    RuleLocation,
)
from services.card_validation.compact_validation.flows.hero import (
    _collect_hero_value_errors,
)
from services.card_validation.compact_validation.flows.layout import (
    _collect_layout_route_errors,
)
from services.card_validation.compact_validation.repair_guidance import (
    RepairGuidanceContext,
    resolve_fix_hint,
)
from services.card_validation.compact_validation.semantic.bindings import (
    _collect_binding_data_errors,
    _collect_progress_value_errors,
)
from services.card_validation.compact_validation.semantic.cross_file import (
    _checked_data_schema,
    _collect_data_type_error,
    _collect_undeclared_data_path_error,
    _unused_data_capability_warnings,
)
from services.card_validation.compact_validation.semantic.display import (
    _collect_ambiguous_metric_text_errors,
    _collect_raw_boolean_text_errors,
    _collect_semantic_text_errors,
    _collect_two_by_two_weather_date_errors,
    _collect_unbound_action_hint_errors,
)
from services.card_validation.compact_validation.semantic.effective import (
    _collect_asset_source_errors,
    _collect_event_candidate_error,
    _task_event_handlers,
)
from services.card_validation.compact_validation.semantic.layout.assets import (
    _collect_asset_color_errors,
)
from services.card_validation.compact_validation.semantic.layout.fusion import (
    _collect_fusion_composition_errors,
)
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _collect_height_budget_errors,
)
from services.card_validation.compact_validation.source_locations import SourceLocations
from services.card_validation.compact_validation.syntax.components import (
    _collect_action_unit_errors,
    _collect_component_parent_errors,
    _collect_container_errors,
    _collect_on_click_structure_errors,
)
from services.card_validation.compact_validation.syntax.expressions import _collect_binding_context
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    build_compact_data_model,
    parse_compact_dsl_rows,
    validate_card_header_layout,
    validate_timeline_unit_layout,
)


def validate_compact_dsl(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    original_source: str | None = None,
    repair_context: RepairGuidanceContext | None = None,
) -> CompactDslValidationResult:
    """Validate expressions, first-frame data, and TaskSpec data boundaries."""
    try:
        rows = parse_compact_dsl_rows(compact_dsl)
    except CompactDslConversionError as exc:
        raise CompactDslValidationError([str(exc)]) from exc

    components = ComponentRows(row for row in rows if isinstance(row, ComponentRow))
    data_rows = [row for row in rows if isinstance(row, DataRow)]
    context = ValidationContext(
        original_source=compact_dsl if original_source is None else original_source,
        validation_source=compact_dsl,
        components=components,
        data_rows=data_rows,
        task_spec=task_spec,
        card_spec=card_spec,
    )
    binding_paths = context.binding_paths
    visible_binding_paths = context.visible_binding_paths
    errors = DiagnosticCollector()
    _collect_asset_source_errors(components, task_spec, errors)
    _collect_asset_color_errors(components, task_spec, errors)
    _collect_component_contract_errors(components, task_spec, errors)
    _collect_fusion_composition_errors(components, task_spec, errors)
    _collect_ambiguous_metric_text_errors(components, task_spec, errors)
    _collect_semantic_text_errors(components, task_spec, errors)
    _collect_raw_boolean_text_errors(components, task_spec, errors)
    _collect_progress_value_errors(components, task_spec, errors)
    _collect_unbound_action_hint_errors(components, errors)
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
            source_location=RuleLocation(component.component_id),
        )
        visible_props = {key: value for key, value in component.props.items() if key != "onClick"}
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
    context.data_model = data_model
    _collect_data_context_errors(
        binding_paths,
        data_rows,
        data_model,
        task_spec,
        errors,
    )
    if errors:
        locations = SourceLocations(context)
        records: list[str | CompactDiagnostic] = []
        for record in errors.records:
            if isinstance(record, str):
                records.append(record)
                continue
            hint = resolve_fix_hint(record, repair_context)
            records.append(replace(locations.locate(record), fix_hint=hint))
        raise CompactDslValidationError.from_records(records)

    warnings = _unused_data_capability_warnings(binding_paths, card_spec)
    return CompactDslValidationResult(warnings=tuple(warnings))


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
