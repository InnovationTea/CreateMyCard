# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：api。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    CompactDslValidationError,
    CompactDslValidationResult,
    RuleLocation,
)
from services.card_validation.compact_validation.flows.contracts import (
    _collect_component_contract_errors,
    _collect_data_context_errors,
)
from services.card_validation.compact_validation.semantic.bindings import (
    _collect_progress_value_errors,
    _compact_component_binding_errors,
)
from services.card_validation.compact_validation.semantic.cross_file import (
    _unused_data_capability_warnings,
)
from services.card_validation.compact_validation.semantic.display import (
    _collect_action_label_length_errors,
    _collect_ambiguous_metric_text_errors,
    _collect_compound_duration_component_errors,
    _collect_progress_readout_object_errors,
    _collect_raw_boolean_text_errors,
    _collect_semantic_text_errors,
    _collect_unbound_action_hint_errors,
)
from services.card_validation.compact_validation.semantic.effective import (
    _collect_asset_source_errors,
    _collect_model_asset_source_errors,
)
from services.card_validation.compact_validation.semantic.layout.assets import (
    _collect_asset_color_errors,
)
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _collect_height_budget_errors,
)
from services.card_validation.compact_validation.semantic.layout.horizontal import (
    _collect_horizontal_budget_errors,
)
from services.card_validation.compact_validation.semantic.layout.text_width import (
    _collect_text_width_budget_errors,
)
from services.card_validation.compact_validation.semantic.numeric_display import (
    _collect_numeric_component_errors,
)
from services.card_validation.compact_validation.semantic.plan_contracts import (
    collect_actions_only_plan_errors,
    collect_plan_contract_errors,
    collect_secondary_body_context_errors,
)
from services.card_validation.compact_validation.syntax.expressions import _collect_binding_context
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    DataRow,
    build_compact_data_model,
    expand_high_level_component_rows,
    normalize_mixed_font_text_rows,
    parse_compact_dsl_rows,
)
from services.compact_layout_runtime import CompactLayoutRuntimeError, match_compact_layout
from services.compact_whole_card_click import accepted_whole_card_click

from .context import ComponentRows, ValidationContext
from .diagnostics import DiagnosticCollector
from .repair_guidance import RepairGuidanceContext, resolve_fix_hint
from .source_locations import SourceLocations
from .syntax.components import collect_model_component_errors


def validate_compact_dsl(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    compact_plan: dict[str, Any] | None = None,
    protocol_profile: dict[str, Any] | None = None,
    layout_scope: str | None = None,
    enforce_model_component_types: bool = False,
    original_source: str | None = None,
    repair_context: RepairGuidanceContext | None = None,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> CompactDslValidationResult:
    """Validate expressions, first-frame data, and TaskSpec data boundaries."""
    try:
        original_rows = parse_compact_dsl_rows(
            compact_dsl,
            expand_layouts=False,
            size=task_spec.get("size"),
        )
        from services.generation_content_policy import current_content_policy

        if current_content_policy().is_static:
            source_components = [row for row in original_rows if isinstance(row, ComponentRow)]
            static_model_errors = collect_model_component_errors(source_components)
            if static_model_errors:
                raise CompactDslValidationError.from_records(static_model_errors.records)
        rows = parse_compact_dsl_rows(compact_dsl, size=task_spec.get("size"))
    except CompactDslConversionError as exc:
        raise CompactDslValidationError([str(exc)]) from exc
    from services.compact_semantic_layout import collect_semantic_layout_warnings

    warnings = list(collect_semantic_layout_warnings(original_rows))
    components = ComponentRows(row for row in rows if isinstance(row, ComponentRow))
    context = ValidationContext(
        original_source=compact_dsl if original_source is None else original_source,
        validation_source=compact_dsl,
        components=components,
        original_components=components,
        data_rows=[],
        task_spec=task_spec,
        card_spec=card_spec,
    )
    from services.compact_dsl_a2ui_converter import expand_compact_semantic_layout

    _expanded_source, context.layout_origins = expand_compact_semantic_layout(
        compact_dsl, size=task_spec.get("size"),
    )
    if enforce_model_component_types and not current_content_policy().is_static:
        model_errors = collect_model_component_errors(components)
        if model_errors:
            raise _validation_error(model_errors, context, repair_context)
    data_rows = [row for row in rows if isinstance(row, DataRow)]
    context.data_rows = data_rows
    data_model = build_compact_data_model(data_rows)
    context.data_model = data_model
    size = card_spec.get("suggestSize") or task_spec.get("size")
    layout_errors: list[str] = []
    if layout_scope is not None:
        if not isinstance(size, str):
            layout_errors.append("Compact layout validation requires a valid widget size.")
        else:
            try:
                whole_card_click = accepted_whole_card_click(task_spec, compact_plan)
                match_compact_layout(
                    components, size=size, layout_scope=layout_scope,
                    root_action_handler=(
                        whole_card_click.handler if whole_card_click is not None else None
                    ),
                )
            except CompactLayoutRuntimeError as exc:
                layout_errors.append(str(exc))
    binding_contract_errors = _compact_component_binding_errors(
        components, task_spec.get("dataModelSchema")
    )
    collect_actions_only_plan_errors(
        [row for row in original_rows if isinstance(row, ComponentRow)],
        compact_plan,
        binding_contract_errors,
    )
    collect_plan_contract_errors(
        components,
        task_spec,
        compact_plan,
        binding_contract_errors,
        size=size if isinstance(size, str) else None,
    )
    if enforce_model_component_types:
        collect_secondary_body_context_errors(components, binding_contract_errors)
    _collect_compound_duration_component_errors(components, task_spec, binding_contract_errors)
    if binding_contract_errors:
        combined_errors = DiagnosticCollector()
        combined_errors.extend(layout_errors)
        for record in binding_contract_errors.records:
            if isinstance(record, CompactDiagnostic):
                combined_errors.emit(record)
            else:
                combined_errors.append(record)
        raise _validation_error(combined_errors, context, repair_context)
    original_errors = DiagnosticCollector()
    from services.generation_content_policy import current_content_policy

    if current_content_policy().is_static:
        from .semantic.static_content import collect_static_group_errors

        collect_static_group_errors(
            compact_dsl,
            compact_plan,
            original_errors,
            allowed_omitted_fact_indexes,
        )
    _collect_action_label_length_errors(components, original_errors)
    _collect_model_asset_source_errors(components, task_spec, original_errors)
    _collect_asset_color_errors(components, task_spec, original_errors)
    _collect_numeric_component_errors(components, task_spec, original_errors)
    if original_errors:
        original_errors.extend(layout_errors)
        raise _validation_error(original_errors, context, repair_context)
    try:
        components = expand_high_level_component_rows(components, size=size, data_model=data_model)
    except CompactDslConversionError as exc:
        from .semantic.layout.text_capacity import capacity_diagnostic_from_error

        diagnostic = capacity_diagnostic_from_error(exc)
        if diagnostic is not None:
            capacity_errors = DiagnosticCollector()
            capacity_errors.emit(diagnostic)
            raise _validation_error(capacity_errors, context, repair_context) from exc
        raise CompactDslValidationError([str(exc)]) from exc
    components = ComponentRows(components)
    context.components = components
    binding_paths = context.binding_paths
    visible_binding_paths = context.visible_binding_paths
    errors = DiagnosticCollector()
    _collect_asset_source_errors(components, task_spec, errors)
    _collect_component_contract_errors(components, task_spec, errors)
    _collect_ambiguous_metric_text_errors(
        components, task_spec, warnings, layout_origins=context.layout_origins,
    )
    _collect_semantic_text_errors(components, task_spec, errors)
    _collect_raw_boolean_text_errors(components, task_spec, errors)
    _collect_progress_value_errors(components, task_spec, errors)
    _collect_progress_readout_object_errors(components, task_spec, errors)
    _collect_unbound_action_hint_errors(components, errors)
    budget_components = normalize_mixed_font_text_rows(components, data_model=data_model)
    _collect_height_budget_errors(
        budget_components, task_spec, card_spec, errors, protocol_profile,
        layout_origins=context.layout_origins,
    )
    _collect_text_width_budget_errors(
        budget_components, task_spec, card_spec, errors, protocol_profile,
        include_label_pressure=(card_spec.get("suggestSize") or task_spec.get("size")) == "2x4",
        warnings=warnings,
    )
    _collect_horizontal_budget_errors(
        budget_components, task_spec, card_spec, errors, protocol_profile,
        warnings=warnings,
        original_components=context.original_components,
    )
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
        _collect_binding_context(visible_props, location, visible_binding_paths, [])
    _collect_data_context_errors(binding_paths, data_rows, data_model, task_spec, errors)
    errors.extend(layout_errors)
    if errors:
        raise _validation_error(errors, context, repair_context)
    warnings.extend(_unused_data_capability_warnings(binding_paths, card_spec))
    return CompactDslValidationResult(warnings=tuple(dict.fromkeys(warnings)))


def _validation_error(
    errors: DiagnosticCollector,
    context: ValidationContext,
    repair_context: RepairGuidanceContext | None,
) -> CompactDslValidationError:
    locations = SourceLocations(context)
    records: list[str | CompactDiagnostic] = []
    for record in errors.records:
        if isinstance(record, str):
            records.append(record)
            continue
        located = locations.locate(record)
        hint = resolve_fix_hint(located, repair_context)
        records.append(replace(located, fix_hint=hint))
    return CompactDslValidationError.from_records(records)
