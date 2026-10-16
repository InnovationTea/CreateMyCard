"""仅转换输入，不执行模型调用或云侧业务修复。"""

import json
from dataclasses import dataclass
from typing import Any

from debug_tools.paths import ensure_cloud_import_path


@dataclass(frozen=True)
class Conversion:
    format: str
    messages: list[dict[str, Any]]
    text: str


def convert(source: str, input_format: str = "auto", size: str = "2x2") -> Conversion:
    if not source.strip():
        raise ValueError("请输入 A2UI 或 Compact DSL")
    try:
        value = json.loads(source)
        rows = value if isinstance(value, list) else [value]
        if rows and isinstance(rows[0], str):
            rows = [rows]
    except json.JSONDecodeError:
        rows = []
        for line in source.splitlines():
            if line.strip():
                rows.append(json.loads(line))
    compact = bool(rows) and isinstance(rows[0], list)
    selected = "compact" if compact else "a2ui"
    if input_format != "auto" and input_format != selected:
        raise ValueError("输入内容与选择的格式不匹配")
    if compact:
        ensure_cloud_import_path()
        from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
        from services.protocol_registry import A2UIProtocolRegistry

        profile = A2UIProtocolRegistry.read_design_protocol_profile("design-compact-dsl")
        normalized = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        converted = convert_compact_dsl_to_a2ui(normalized, size=size, protocol_profile=profile)
        rows = [json.loads(line) for line in converted.splitlines() if line.strip()]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError("A2UI 必须由消息对象组成")
    allowed = {"createSurface", "updateComponents", "updateDataModel", "deleteSurface"}
    for row in rows:
        operations = allowed.intersection(row)
        if len(operations) != 1:
            raise ValueError("每条 A2UI 消息须包含一个受支持的消息操作")
        operation = next(iter(operations))
        payload = row.get(operation)
        if not isinstance(payload, dict) or not isinstance(payload.get("surfaceId"), str):
            raise ValueError("A2UI 消息缺少 surfaceId 或操作内容无效")
    return Conversion(selected, rows, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
