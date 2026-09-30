# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：text。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.schema import (
    _NUMERIC_SCHEMA_TYPES,
    _schema_node_at_path,
    _schema_type,
)
from services.card_validation.compact_validation.syntax.expressions import (
    _EXPRESSION_PATTERN,
    _REFERENCE_PATTERN,
    _STRING_LITERAL_PATTERN,
    _collect_binding_context,
)
from services.compact_dsl_a2ui_converter import ComponentRow

_COMMON_DISPLAY_UNITS = frozenset(
    {
        "%",
        "°C",
        "℃",
        "°F",
        "天",
        "小时",
        "分钟",
        "分",
        "秒",
        "毫秒",
        "步",
        "次",
        "件",
        "个",
        "条",
        "项",
        "人",
        "级",
        "公里",
        "千米",
        "米",
        "厘米",
        "毫米",
        "km",
        "m",
        "cm",
        "mm",
        "kg",
        "g",
        "mg",
        "kcal",
        "千卡",
        "cal",
        "mL",
        "ml",
        "L",
        "A",
        "mA",
        "V",
        "W",
        "kW",
        "kWh",
        "bpm",
        "次/分钟",
        "mV",
        "μA",
        "uA",
        "kHz",
        "MHz",
        "Pa",
        "kPa",
        "Wh",
        "MB",
        "GB",
        "TB",
        "km/h",
        "m/s",
    }
)


_MEASUREMENT_DESCRIPTION_MARKERS = (
    "温度",
    "电量",
    "电池电量",
    "剩余电量",
    "占比",
    "比例",
    "电流",
    "电压",
    "功率",
    "频率",
    "速度",
    "距离",
    "容量",
    "湿度",
    "压力",
    "海拔",
    "重量",
    "体重",
    "长度",
    "宽度",
    "高度",
)


_MEASUREMENT_SAMPLE_PATTERN = re.compile(
    r"[+-]?\d+(?:\.\d+)?\s*(?:°C|℃|°F|mA|μA|uA|A|mV|V|kW|W|kWh|Wh|MHz|kHz|Hz|"
    r"km/h|m/s|km|千米|公里|m|米|cm|厘米|mm|毫米|kg|g|mg|MB|GB|TB|Pa|kPa|%|"
    r"毫秒|小时|分钟|分|秒)$"
)


_AMBIGUOUS_METRIC_DESCRIPTION_MARKERS = (
    "指数",
    "等级",
    "评分",
    "得分",
    "概率",
    "风险",
    "质量",
    "健康",
)


_AMBIGUOUS_STATUS_MARKERS = (
    "良",
    "中等",
    "低",
    "高",
    "正常",
    "异常",
    "未知",
    "未充电",
    "已充电",
    "未连接",
    "已连接",
)


def _pure_numeric_binding_path(
    content: Any,
    data_model_schema: dict[str, Any],
) -> str | None:
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
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", content.strip()):
        return ""
    return None


def _is_allowed_display_unit(
    content: Any,
    numeric_path: str,
    data_model_schema: dict[str, Any],
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


def _numeric_content_paths(
    components: list[ComponentRow],
    data_model_schema: dict[str, Any],
) -> set[str]:
    paths: set[str] = set()
    for component in components:
        if component.component_type != "Text":
            continue
        for path in _component_content_paths(component):
            schema_node = _schema_node_at_path(data_model_schema, path)
            if _schema_type(schema_node) in _NUMERIC_SCHEMA_TYPES:
                paths.add(path)
    return paths


def _binding_roots(value: Any, location: str) -> set[str]:
    paths: list[str] = []
    _collect_binding_context(value, location, paths, [])
    roots: set[str] = set()
    for path in paths:
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "data":
            roots.add(parts[1])
    return roots


def _is_status_or_ambiguous_text(component: ComponentRow, task_spec: dict[str, Any]) -> bool:
    content = component.props.get("content")
    if isinstance(content, str) and "{{" not in content:
        return any(marker in content for marker in _AMBIGUOUS_STATUS_MARKERS)
    paths: list[str] = []
    _collect_binding_context(
        content,
        f"component {component.component_id}.props.content",
        paths,
        [],
    )
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return False
    for path in paths:
        node = _schema_node_at_path(schema, path)
        description = node.get("description") if isinstance(node, dict) else None
        if isinstance(description, str) and any(
            marker in description for marker in _AMBIGUOUS_METRIC_DESCRIPTION_MARKERS
        ):
            return True
    return False


def _static_text_fragments(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    if "{{" not in value:
        return value.strip()
    fragments: list[str] = []
    for literal in _STRING_LITERAL_PATTERN.findall(value):
        fragments.append(literal[1:-1].strip())
    return " ".join(fragment for fragment in fragments if fragment)


def _nearby_text_context(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> str:
    fragments = [_static_text_fragments(component.props.get("content"))]
    parent_id = parent_by_child.get(component.component_id)
    parent = components_by_id.get(parent_id) if parent_id else None
    if parent is None:
        return " ".join(fragment for fragment in fragments if fragment)
    for sibling_id in parent.children:
        if sibling_id == component.component_id:
            continue
        sibling = components_by_id.get(sibling_id)
        if sibling is None or sibling.component_type != "Text":
            continue
        fragments.append(_static_text_fragments(sibling.props.get("content")))
    return " ".join(fragment for fragment in fragments if fragment)
