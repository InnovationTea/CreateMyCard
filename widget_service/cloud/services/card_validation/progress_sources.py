# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""标准进度数值来源检查，供转换后和完整产物复用。"""

import json
import math
from typing import Any

from services.card_validation.base import expression_references, is_wrapped_expression, read_pointer


def progress_dsl_errors(source: str, schema: dict[str, Any] | None) -> list[str]:
    """转换与保存的必要门禁，不依赖完整产物校验开关。"""
    components: list[dict[str, Any]] = []
    try:
        for line in source.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            update = record.get("updateComponents") if isinstance(record, dict) else None
            if isinstance(update, dict):
                values = update.get("components")
                if isinstance(values, list):
                    for component in values:
                        if isinstance(component, dict):
                            components.append(component)
    except json.JSONDecodeError as exc:
        return [f"进度来源检查无法解析标准 DSL：{exc}"]
    return progress_source_errors(components, schema)


def progress_source_errors(
    components: list[dict[str, Any]], schema: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    for component in components:
        if component.get("component") != "Progress":
            continue
        value = component.get("value")
        label = f"Progress {component.get('id')}.value"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value):
                errors.append(f"{label} 必须是有限数值。")
            continue
        if not isinstance(value, str):
            errors.append(f"{label} 必须是数值或合法数值表达式。")
            continue
        if not is_wrapped_expression(value):
            errors.append(f"{label} 不接受格式化文本或数值字符串。")
            continue
        for path in expression_references(value):
            if path.startswith("/__display/"):
                errors.append(f"{label} 不得绑定没有运行时重算关系的首帧副本 {path}。")
                continue
            if schema is None:
                continue
            _found, node = read_pointer(schema, path)
            schema_type = node.get("type") if isinstance(node, dict) else None
            if schema_type not in {"integer", "number"}:
                errors.append(f"{label} 的动态来源 {path} 必须声明为 number/integer。")
    return errors
