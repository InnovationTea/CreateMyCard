"""在修复请求边界组织 Compact 说明，不改写质量问题和修复记录。"""

from __future__ import annotations

import json
from typing import Any

from app.logger import logger


def _required_text(value: dict[str, Any], key: str) -> str:
    text = value.get(key)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Compact diagnostic requires non-empty {key}")
    return text


def _format_location(diagnostic: dict[str, Any]) -> str | None:
    parts: list[str] = []
    line = diagnostic.get("sourceLine")
    if isinstance(line, int) and not isinstance(line, bool) and line > 0:
        parts.append(f"原文第 {line} 行")
    component_id = diagnostic.get("componentId")
    if isinstance(component_id, str) and component_id:
        parts.append(f"组件 {component_id}")
        path = diagnostic.get("propertyPath")
        if isinstance(path, str) and path:
            parts.append(f"属性 {path}")
    result: str | None = None
    if parts:
        result = "位置：" + "；".join(parts)
    return result


def _json_fact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_diagnostic(diagnostic: dict[str, Any]) -> str:
    code = _required_text(diagnostic, "code")
    validation_class = _required_text(diagnostic, "validationClass")
    category = _required_text(diagnostic, "category")
    message = _required_text(diagnostic, "message")
    if diagnostic.get("severity") != "error":
        raise ValueError("Only Compact errors belong in repair feedback")
    if "expected" not in diagnostic:
        raise ValueError("Compact diagnostic requires its hard constraints")
    lines = [f"错误码：{code}", f"分类：{validation_class} / {category}"]
    location = _format_location(diagnostic)
    if location is not None:
        lines.append(location)
    lines.append(f"问题：{message}")
    if "actual" in diagnostic:
        source_names = {"original": "本轮原始文本", "validation": "本轮校验文本"}
        source = source_names.get(diagnostic.get("evidenceSource"))
        if source is None:
            raise ValueError("Compact diagnostic actual requires evidenceSource")
        lines.append(f"实际值（来源：{source}）：{_json_fact(diagnostic.get('actual'))}")
    lines.append(f"约束：{_json_fact(diagnostic.get('expected'))}")
    hint = diagnostic.get("fixHint")
    if hint is not None:
        lines.append("修改建议：" + _required_text(diagnostic, "fixHint"))
    return "\n".join(lines)


def format_compact_issue_for_model(payload: dict[str, Any]) -> str:
    """读取完整迁移的一组诊断，按原顺序逐条呈现。"""
    diagnostics = payload.get("compactDiagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise ValueError("Compact feedback requires a complete non-empty diagnostic group")
    paragraphs: list[str] = []
    for index, diagnostic in enumerate(diagnostics, 1):
        if not isinstance(diagnostic, dict):
            raise TypeError("Compact diagnostic must be an object")
        paragraph = _format_diagnostic(diagnostic)
        if len(diagnostics) > 1:
            paragraph = f"关联问题 {index}\n{paragraph}"
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def compact_issue_for_model(payload: dict[str, Any]) -> dict[str, Any]:
    """只修改新建的外层对象；诊断嵌套值只读，不被文字说明覆盖。"""
    result = dict(payload)
    is_compact = (
        payload.get("stage") == "validation"
        and payload.get("code") == "COMPACT_DSL_VALIDATION_FAILED"
    )
    if not is_compact or "compactDiagnostics" not in payload:
        return result
    result.pop("compactDiagnostics", None)
    try:
        result["message"] = format_compact_issue_for_model(payload)
    except Exception as exc:
        logger.warning("Compact feedback formatting failed: {}: {}", type(exc).__name__, exc)
    return result
