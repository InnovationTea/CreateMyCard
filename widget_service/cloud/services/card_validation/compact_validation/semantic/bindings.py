# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.bindings。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.schema import (
    _NUMERIC_SCHEMA_TYPES,
    _schema_node_at_path,
    _schema_type,
)
from services.card_validation.compact_validation.text import _pure_binding_path
from services.compact_dsl_a2ui_converter import ComponentRow

from ..diagnostics import CompactDiagnostic, emit_error
from ..schema import _json_pointer_exists


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


def _collect_progress_value_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
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
                    f"component {component.component_id}: Progress.value path "
                    f"{value_path} has schema type {schema_type or 'unknown'}; bind a "
                    "number/integer field such as 68, not formatted text such as "
                    "'68%'. If only formatted text exists, remove Progress and show "
                    "the complete value with Text."
                ),
            ),
        )
