# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：schema。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.syntax.expressions import _decode_json_pointer

_NUMERIC_SCHEMA_TYPES = frozenset({"integer", "number"})


def _schema_leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            return 1
        return sum(_schema_leaf_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_schema_leaf_count(child) for child in value)
    return 0


def _schema_field_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            return set()
        names = {str(key).casefold() for key in value}
        for child in value.values():
            names.update(_schema_field_names(child))
        return names
    if isinstance(value, list):
        names: set[str] = set()
        for child in value:
            names.update(_schema_field_names(child))
        return names
    return set()


def _task_spec_data_roots(task_spec: dict[str, Any]) -> set[str]:
    data_model_schema = task_spec.get("dataModelSchema")
    data_schema = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
    if not isinstance(data_schema, dict):
        return set()
    return {str(root_name).casefold() for root_name in data_schema}


def _schema_contains_field(value: Any, field_name: str) -> bool:
    if isinstance(value, dict):
        return field_name in value or any(
            _schema_contains_field(child, field_name) for child in value.values()
        )
    if isinstance(value, list):
        return any(_schema_contains_field(child, field_name) for child in value)
    return False


def _schema_node_at_path(schema: Any, path: str) -> Any | None:
    current = schema
    for token in _decode_json_pointer(path):
        current = _schema_child(current, token)
        if current is None:
            return None
    return current


def _schema_child(current: Any, token: str) -> Any | None:
    if isinstance(current, list):
        if not token.isdigit() or not current:
            return None
        index = int(token)
        if index < len(current):
            return current[index]
        return current[0]
    if not isinstance(current, dict):
        return None
    if current.get("type") == "array":
        if not token.isdigit():
            return None
        return current.get("items")
    if current.get("type") == "object":
        properties = current.get("properties")
        if isinstance(properties, dict):
            return properties.get(token)
    return current.get(token)


def _schema_type(schema_node: Any) -> str | None:
    if isinstance(schema_node, list):
        return "array"
    if not isinstance(schema_node, dict):
        return None
    schema_type = schema_node.get("type")
    return schema_type if isinstance(schema_type, str) else None


def _value_matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return True


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


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


def _path_is_within(path: str, root: str) -> bool:
    normalized_root = root.rstrip("/")
    return path == normalized_root or path.startswith(f"{normalized_root}/")


def _json_pointer_exists(root: dict[str, Any], path: str) -> bool:
    current: Any = root
    for token in _decode_json_pointer(path):
        if isinstance(current, dict):
            if token not in current:
                return False
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                return False
            index = int(token)
            if index >= len(current):
                return False
            current = current[index]
            continue
        return False
    return True


def _is_task_data_path(path: str) -> bool:
    return path == "/data" or path.startswith("/data/")
