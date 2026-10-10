"""主文字与相邻单位检查编排。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import component_index
from services.card_validation.compact_validation.schema import (
    _NUMERIC_SCHEMA_TYPES,
    _schema_node_at_path,
    _schema_type,
)
from services.card_validation.compact_validation.semantic.display import (
    _collect_hero_suffix_errors,
    _collect_non_numeric_display_unit_error,
    _collect_non_numeric_primary_suffix_error,
)
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _non_negative_number,
)
from services.card_validation.compact_validation.semantic.layout.typography import (
    _collect_mixed_font_row_alignment_errors,
    _collect_numeric_unit_alignment_errors,
    _collect_primary_value_errors,
)
from services.card_validation.compact_validation.text import (
    _COMMON_DISPLAY_UNITS,
    _is_allowed_display_unit,
    _pure_binding_path,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_hero_value_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    """在原调用位置编排展示语义与排版检查，保留模板的整组豁免。"""
    components_by_id = component_index(components)
    # 与质量阶段使用相同的有效模板根标记，仅豁免主文字校验。
    if len(components_by_id) == len(components) and "template_root" in components_by_id:
        root = components_by_id.get("root")
        if root is not None and "template_root" in root.children:
            return
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return

    _collect_adjacent_display_unit_errors(
        components,
        components_by_id,
        data_model_schema,
        errors,
        enforce_all_numeric_sizes=task_spec.get("size") == "2x4",
    )
    if task_spec.get("size") == "2x4":
        _collect_mixed_font_row_alignment_errors(
            components,
            components_by_id,
            errors,
        )
    analysis = _collect_primary_value_errors(components, task_spec, data_model_schema, errors)
    _collect_hero_suffix_errors(
        components,
        components_by_id,
        data_model_schema,
        analysis.numeric_paths,
        analysis.formatted_ids,
        errors,
    )


def _collect_adjacent_display_unit_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    data_model_schema: dict[str, Any],
    errors: list[str],
    enforce_all_numeric_sizes: bool,
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
            if value_path is None:
                continue
            if value_path:
                schema_type = _schema_type(_schema_node_at_path(data_model_schema, value_path))
            else:
                schema_type = "number"
            value_font_size = _non_negative_number(value.props.get("fontSize"))
            if _collect_non_numeric_primary_suffix_error(
                component, value, suffix, value_path, value_font_size, schema_type, errors
            ):
                continue
            unit = suffix_content.strip()
            if schema_type in _NUMERIC_SCHEMA_TYPES:
                is_known_unit = unit in _COMMON_DISPLAY_UNITS
                if value_path:
                    is_known_unit = _is_allowed_display_unit(
                        suffix_content,
                        value_path,
                        data_model_schema,
                    )
                if not is_known_unit:
                    continue
                if not enforce_all_numeric_sizes:
                    continue
                _collect_numeric_unit_alignment_errors(
                    component, value, suffix, value_font_size, errors
                )
                continue
            _collect_non_numeric_display_unit_error(component, unit, value_path, errors)
