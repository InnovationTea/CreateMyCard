# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.cross_file。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.schema import (
    _card_spec_data_roots,
    _is_task_data_path,
    _json_type_name,
    _path_is_within,
    _schema_node_at_path,
    _schema_type,
    _value_matches_schema_type,
)
from services.compact_dsl_a2ui_converter import DataRow

from ..diagnostics import CompactDiagnostic, emit_error


def _checked_data_schema(task_spec: dict[str, Any], errors: list[str]) -> dict[str, Any] | None:
    value = task_spec.get("dataModelSchema")
    result: dict[str, Any] | None = None
    if isinstance(value, dict):
        result = value
    else:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_CONTEXT_SCHEMA_INVALID",
                validation_class="semantic",
                category="cross_file",
                message="本轮服务端的数据声明不是对象，无法进行声明一致性校验。",
                legacy_message="TaskSpec.dataModelSchema must be an object.",
                expected={"schemaType": "object", "repairBoundary": "模型不能改写服务端上下文"},
            ),
        )
    return result


def _collect_undeclared_data_path_error(
    path: str,
    data_model_schema: dict[str, Any],
    errors: list[str],
) -> None:
    if not _is_task_data_path(path):
        return
    if _schema_node_at_path(data_model_schema, path) is not None:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_CROSS_FILE_UNDECLARED_PATH",
            validation_class="semantic",
            category="cross_file",
            data_path=path,
            message=f"路径 {path} 未在本轮数据 schema 中声明。",
            actual={"path": path, "declared": False},
            expected={"declaredByTaskSchema": True},
            legacy_message=(
                f"{path}: path is not declared by TaskSpec.dataModelSchema; "
                "remove it or use a declared field."
            ),
        ),
    )


def _collect_data_type_error(
    row: DataRow,
    data_model_schema: dict[str, Any],
    errors: list[str],
) -> None:
    if not _is_task_data_path(row.path):
        return
    schema_node = _schema_node_at_path(data_model_schema, row.path)
    if schema_node is None:
        return
    expected_type = _schema_type(schema_node)
    type_matches = expected_type is None or _value_matches_schema_type(
        row.value,
        expected_type,
    )
    if type_matches:
        return
    actual_type = _json_type_name(row.value)
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_CROSS_FILE_DATA_TYPE",
            validation_class="semantic",
            category="cross_file",
            data_path=row.path,
            message=(
                f"路径 {row.path} 的首帧数据类型为 {actual_type}，"
                f"与声明类型 {expected_type} 不一致。"
            ),
            actual={"path": row.path, "type": actual_type},
            expected={"type": expected_type},
            legacy_message=(
                f"{row.path}: data row type {actual_type} does not match "
                f"schema type {expected_type} declared by TaskSpec."
            ),
        ),
    )


def _unused_data_capability_warnings(
    binding_paths: list[str],
    card_spec: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for root in _card_spec_data_roots(card_spec):
        if any(_path_is_within(path, root) for path in binding_paths):
            continue
        warnings.append(f"{root}: declared data capability is not used by any component.")
    return warnings
