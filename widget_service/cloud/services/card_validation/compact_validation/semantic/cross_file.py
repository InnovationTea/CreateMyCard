# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：semantic.cross_file。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    emit_error,
)
from services.card_validation.compact_validation.schema import (
    _is_task_data_path,
    _json_type_name,
    _path_is_within,
    _schema_node_at_path,
    _schema_type,
    _value_matches_schema_type,
)
from services.compact_dsl_a2ui_converter import (
    DataRow,
)


def static_source_errors(fact: dict[str, Any], source: str) -> list[str]:
    """仅检查引用可追溯及明确原文约束；摘要语义由模型判断。"""
    from config.config import get_settings

    references = fact.get("sourceTexts")
    if not isinstance(references, list) or not references:
        return ["静态 text 事实必须提交非空 sourceTexts。"]
    errors: list[str] = []
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    valid_sources = []
    for reference in references:
        if not isinstance(reference, str) or not reference.strip():
            errors.append("sourceTexts 只接受非空原文字符串。")
            continue
        reference = reference.replace("\r\n", "\n").replace("\r", "\n")
        if len(reference) > get_settings().static_content_max_source_chars:
            errors.append("静态来源引用超过长度预算。")
        if reference not in source:
            diagnostic = _static_source_diagnostic()
            errors.append(diagnostic.message)
        valid_sources.append(reference)
    display = fact.get("text")
    if not isinstance(display, str) or not display.strip():
        return [*errors, "静态展示文字必须非空。"]
    display = display.replace("\r\n", "\n").replace("\r", "\n")
    protected = fact.get("protectedTexts", [])
    if not isinstance(protected, list):
        return [*errors, "protectedTexts 必须是原文片段数组。"]
    if len(protected) > 12:
        errors.append("单事实保护片段不得超过12项。")
    for fragment in protected:
        if not isinstance(fragment, str) or not fragment.strip():
            errors.append("保护片段必须是非空文字。")
            continue
        fragment = fragment.replace("\r\n", "\n").replace("\r", "\n")
        if not any(fragment in reference for reference in valid_sources):
            errors.append("保护片段没有来源引用依据。")
        if fragment not in display:
            errors.append("COMPACT_STATIC_PROTECTED_TEXT_CHANGED: 展示文字缺少保护片段。")
    verbatim = fact.get("preserveVerbatim", False)
    if not isinstance(verbatim, bool):
        errors.append("preserveVerbatim 必须是布尔值。")
    if verbatim is True and display not in valid_sources:
        errors.append("原文展示必须完整保留一个引用片段。")
    return errors


def _static_source_diagnostic() -> CompactDiagnostic:
    return CompactDiagnostic(
        code="COMPACT_STATIC_SOURCE_NOT_ALLOWED",
        validation_class="semantic",
        category="cross_file",
        message="COMPACT_STATIC_SOURCE_NOT_ALLOWED: 来源引用不在本轮有效输入中。",
        legacy_message="COMPACT_STATIC_SOURCE_NOT_ALLOWED: 来源引用不在本轮有效输入中。",
        expected={"quotedFromCurrentInput": True},
    )


def _collect_undeclared_data_path_error(
    path: str, data_model_schema: dict[str, Any], errors: list[str]
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
                f"{path}: path is not declared by TaskSpec.dataModelSchema; remove it or "
                f"use a declared field."
            ),
        ),
    )


def _collect_data_type_error(
    row: DataRow, data_model_schema: dict[str, Any], errors: list[str]
) -> None:
    if not _is_task_data_path(row.path):
        return
    schema_node = _schema_node_at_path(data_model_schema, row.path)
    if schema_node is None:
        return
    expected_type = _schema_type(schema_node)
    type_matches = expected_type is None or _value_matches_schema_type(row.value, expected_type)
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
                f"{row.path}: data row type {actual_type} does not match schema type "
                f"{expected_type} declared by TaskSpec."
            ),
        ),
    )


def _unused_data_capability_warnings(
    binding_paths: list[str], card_spec: dict[str, Any]
) -> list[str]:
    warnings: list[str] = []
    for root in _card_spec_data_roots(card_spec):
        if any(_path_is_within(path, root) for path in binding_paths):
            continue
        warnings.append(f"{root}: declared data capability is not used by any component.")
    return warnings


def _card_spec_data_roots(card_spec: dict[str, Any]) -> list[str]:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return []
    roots: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        root = binding.get("writeResultTo")
        if isinstance(root, str) and root.startswith("/"):
            roots.append(root)
    return roots


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
