"""Provider Template 字段类型兼容规则。"""

from __future__ import annotations

from typing import Any


def field_types_are_compatible(
    path: str,
    expected_type: str,
    actual_type: Any,
) -> bool:
    """允许降雨概率在新旧能力快照间由 string 平滑迁移到 number。"""
    if actual_type == expected_type:
        return True
    is_rain_probability = path.endswith("/rainProbabilityPercent")
    string_to_number = expected_type == "string" and actual_type == "number"
    number_to_string = expected_type == "number" and actual_type == "string"
    return is_rain_probability and (string_to_number or number_to_string)
