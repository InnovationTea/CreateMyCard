# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：semantic.bindings。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.constants import _NUMERIC_SCHEMA_TYPES
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    emit_error,
)
from services.card_validation.compact_validation.schema import (
    _json_pointer_exists,
    _schema_node_at_path,
    _schema_type,
)
from services.card_validation.compact_validation.text import _pure_binding_path
from services.compact_component_bindings import collect_compact_component_binding_errors
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
)


def _compact_component_binding_errors(
    components: list[ComponentRow], data_model_schema: Any
) -> list[str]:

    def schema_type_for_path(path: str) -> str | None:
        return _schema_type(_schema_node_at_path(data_model_schema, path))

    errors: list[str] = []
    resolver = schema_type_for_path if isinstance(data_model_schema, dict) else None
    for component in components:
        errors.extend(
            collect_compact_component_binding_errors(
                component.component_id,
                component.component_type,
                component.props,
                schema_type_resolver=resolver,
            )
        )
        if component.component_type not in {"ProgressCircleSingle", "ProgressLine2"}:
            continue
        readout = _pure_binding_path(component.props.get("displayValue"))
        if not readout:
            continue
        node = _schema_node_at_path(data_model_schema, readout)
        if not isinstance(node, dict):
            continue
        expected_path = node.get("numericSource")
        if expected_path is None and node.get("type") in _NUMERIC_SCHEMA_TYPES:
            expected_path = readout
        if expected_path is None:
            if node.get("type") == "string":
                errors.append(
                    f"component {component.component_id}: readout {readout} has no registered "
                    "numeric source; retain complete text instead of guessing a progress metric."
                )
            continue
        actual_path = _pure_binding_path(component.props.get("value"))
        if actual_path != expected_path:
            errors.append(
                f"component {component.component_id}: progress value must use registered "
                f"numeric source {expected_path} for readout {readout}, not {actual_path}."
            )
    return errors


def _collect_progress_value_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return
    for component in components:
        if component.component_type != "Progress":
            continue
        value_path = _pure_binding_path(component.props.get("value"))
        if not value_path:
            continue
        schema_type = _schema_type(_schema_node_at_path(data_model_schema, value_path))
        if schema_type in _NUMERIC_SCHEMA_TYPES:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_BINDING_PROGRESS_TYPE",
                validation_class="semantic",
                category="binding",
                component_id=component.component_id,
                property_path="/value",
                message=f"Progress.value 绑定的字段 {value_path} 没有合法的数值类型声明。",
                actual={"path": value_path, "schemaType": schema_type},
                expected={"schemaTypes": ["number", "integer"]},
                legacy_message=(
                    f"component {component.component_id}: Progress.value path {value_path} "
                    f"has schema type {schema_type or 'unknown'}; bind a number/integer "
                    f"field such as 68, not formatted text such as '68%'. If only "
                    f"formatted text exists, remove Progress and show the complete value "
                    f"with Text."
                ),
            ),
        )


def _collect_binding_data_errors(
    binding_paths: list[str], data_model: dict[str, Any], errors: list[str]
) -> None:
    for path in dict.fromkeys(binding_paths):
        if not _json_pointer_exists(data_model, path):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_BINDING_DATA_MISSING",
                    validation_class="semantic",
                    category="binding",
                    message=f"绑定路径 {path} 缺少匹配的首帧数据。",
                    legacy_message=f"{path}: binding path has no matching Compact DSL data row.",
                    actual={"path": path, "exists": False},
                    expected={"matchingFirstFrameData": True},
                    data_path=path,
                ),
            )
