# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：text。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.constants import (
    _COMMON_DISPLAY_UNITS,
    _EXPRESSION_PATTERN,
    _NUMERIC_SCHEMA_TYPES,
    _REFERENCE_PATTERN,
    _STRING_LITERAL_PATTERN,
    _VISUAL_RECIPE_MARKER_PREFIX,
)
from services.card_validation.compact_validation.schema import _schema_node_at_path, _schema_type
from services.card_validation.compact_validation.syntax.expressions import _collect_binding_context
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
)


def _uses_visual_recipe(component: ComponentRow) -> bool:
    marker = component.props.get("_visualRecipe")
    return isinstance(marker, str) and marker.startswith(_VISUAL_RECIPE_MARKER_PREFIX)


def _uses_visual_recipe_part(component: ComponentRow, part: str) -> bool:
    marker = component.props.get("_visualRecipe")
    return marker == f"{_VISUAL_RECIPE_MARKER_PREFIX}{part}"


def _pure_numeric_binding_path(content: Any, data_model_schema: dict[str, Any]) -> str | None:
    path = _pure_binding_path(content)
    if path is None:
        return None
    if path == "":
        return path
    schema_node = _schema_node_at_path(data_model_schema, path)
    if _schema_type(schema_node) not in _NUMERIC_SCHEMA_TYPES:
        return None
    return path


def _pure_binding_path(content: Any) -> str | None:
    if isinstance(content, dict) and set(content) == {"path"}:
        candidate = content.get("path")
        return candidate if isinstance(candidate, str) else None
    if not isinstance(content, str):
        return None
    match = _EXPRESSION_PATTERN.fullmatch(content.strip())
    if match is not None:
        reference = _REFERENCE_PATTERN.fullmatch(match.group("body").strip())
        return reference.group("path").strip() if reference is not None else None
    if re.fullmatch("[+-]?\\d+(?:\\.\\d+)?", content.strip()):
        return ""
    return None


def _is_allowed_display_unit(
    content: Any, numeric_path: str, data_model_schema: dict[str, Any]
) -> bool:
    if not isinstance(content, str):
        return False
    unit = content.strip()
    if not unit:
        return False
    if unit in _COMMON_DISPLAY_UNITS:
        return True
    schema_node = _schema_node_at_path(data_model_schema, numeric_path)
    if not isinstance(schema_node, dict):
        return False
    description = schema_node.get("description")
    return isinstance(description, str) and unit in description


def _component_content_paths(component: ComponentRow) -> list[str]:
    paths: list[str] = []
    _collect_binding_context(
        component.props.get("content"),
        f"component {component.component_id}.props.content",
        paths,
        [],
    )
    return paths


def _static_text_fragments(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    if "{{" not in value:
        return value.strip()
    fragments: list[str] = []
    for literal in _STRING_LITERAL_PATTERN.findall(value):
        fragments.append(literal[1:-1].strip())
    return " ".join(fragment for fragment in fragments if fragment)


def _non_negative_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return float(value)


def _format_vp(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
