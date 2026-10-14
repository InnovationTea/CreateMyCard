# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""语义／展示：仅兜底原始数值组件中有充分证据的非量化文本。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.schema import _schema_node_at_path, _schema_type
from services.card_validation.compact_validation.text import _pure_binding_path
from services.compact_composition_planner import is_compound_duration_text
from services.compact_dsl_a2ui_converter import ComponentRow

_CALENDAR_TEXT = re.compile(
    r"(?:\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?"
    r"(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|\d{1,2}月\d{1,2}日|(?:星期|周)[一二三四五六日天])"
)
_CLOCK_TEXT = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")
_CLOCK_DESCRIPTION_MARKERS = ("时刻", "钟点", "几点", "日期")
_QUANTITY_FRAGMENT = re.compile(r"[\d零〇一二三四五六七八九十百千万亿两半]")
_NON_QUANTITATIVE_DESCRIPTION_MARKERS = (
    "状态", "名称", "名字", "姓名", "日期", "时刻", "钟点", "几点", "星期", "周几", "地点", "地址",
)
_UNAVAILABLE_TEXT = frozenset({
    "", "-", "--", "—", "–", "...", "…", "暂无", "暂无数据", "无数据", "未知", "待更新",
    "加载中", "加载失败", "获取失败", "读取失败", "数据不可用", "未获取", "不可用",
    "n/a", "na", "null", "none", "unknown", "loading", "unavailable", "nan",
})
_UNAVAILABLE_MARKERS = (
    "暂无", "无数据", "加载", "获取失败", "读取失败", "未获取", "不可用", "尚未", "等待",
    "网络错误", "loading", "failed", "unavailable", "unknown",
)


def _is_plain_non_numeric_text(value: Any) -> bool:
    """只证明普通文案；未知计量格式、中文数词和表达式不靠白名单拒绝。"""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    normalized = stripped.casefold()
    if normalized in _UNAVAILABLE_TEXT:
        return False
    if any(marker in normalized for marker in _UNAVAILABLE_MARKERS):
        return False
    if "{{" in stripped or "${" in stripped:
        return False
    if is_compound_duration_text(stripped):
        return False
    if _CALENDAR_TEXT.fullmatch(stripped):
        return True
    if _QUANTITY_FRAGMENT.search(stripped):
        return False
    return any(character.isalpha() for character in stripped)


def _is_declared_clock_text(sample: Any, description: str) -> bool:
    """冒号读数也可能是配速或用时，只有明确钟点语义才能证明选型错误。"""
    if not isinstance(sample, str) or _CLOCK_TEXT.fullmatch(sample.strip()) is None:
        return False
    return any(marker in description for marker in _CLOCK_DESCRIPTION_MARKERS)


def _non_numeric_binding_details(value: Any, task_spec: dict[str, Any]) -> dict[str, Any] | None:
    """字段语义与真实合同样值须同时明确；不将首帧或缺省值充当字段合同。"""
    details: dict[str, Any] | None = None
    path = _pure_binding_path(value)
    if not path:
        return details
    node = _schema_node_at_path(task_spec.get("dataModelSchema"), path)
    if not isinstance(node, dict) or _schema_type(node) != "string":
        return details
    description = node.get("description")
    if not isinstance(description, str):
        return details
    if not any(marker in description for marker in _NON_QUANTITATIVE_DESCRIPTION_MARKERS):
        return details
    sample = node.get("sampleValue")
    if _is_plain_non_numeric_text(sample) or _is_declared_clock_text(sample, description):
        details = {"dataPath": path, "description": description, "sampleValue": sample}
    return details


def _collect_numeric_component_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str],
) -> None:
    """展开前检查 EmphasizedData 选型，不检查其他组件或内部字号。"""
    for component in components:
        if component.component_type != "EmphasizedData":
            continue
        value = component.props.get("value")
        details = _non_numeric_binding_details(value, task_spec)
        if details is None and not _is_plain_non_numeric_text(value):
            continue
        actual: dict[str, Any] = {"value": value}
        if details is not None:
            actual.update(details)
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_NUMERIC_COMPONENT_MISUSE",
                validation_class="semantic",
                category="display",
                message="EmphasizedData.value 使用了已确认的非量化文本。",
                legacy_message=(
                    f"component {component.component_id}: EmphasizedData.value contains "
                    "non-quantitative text; its content role requires a numeric value "
                    "or a single measurement readout."
                ),
                expected={"valueRole": "numericOrSingleMeasurement"},
                actual=actual,
                component_id=component.component_id,
                property_path="/value",
            ),
        )
