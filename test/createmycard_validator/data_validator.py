"""DataModel integrity rules."""

from __future__ import annotations

from typing import Any

try:
    from .common import EXPR_RE, PATH_RE, DataBinding, Finding, ValidationContext, error, json_pointer_get, warning
except ImportError:
    from common import EXPR_RE, PATH_RE, DataBinding, Finding, ValidationContext, error, json_pointer_get, warning  # type: ignore


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []

    for binding in ctx.bindings:
        findings.extend(validate_binding(ctx, binding))

    for component in ctx.components:
        component_id = str(component.get("id", "<unknown>"))
        children = component.get("children")
        if isinstance(children, dict):
            source = children.get("path")
            if isinstance(source, str):
                exists, value = json_pointer_get(ctx.data_roots, source) if source.startswith("/") else (False, None)
                if not exists:
                    findings.append(error("RULE_DATA_007", f"List '{component_id}' 的重复模板路径 '{source}' 在 DataModel 中不存在", 5))
                elif not isinstance(value, list):
                    findings.append(warning("RULE_DATA_004", f"component '{component_id}' repeated source is not an array: {source}"))

        for key, value in component.items():
            if isinstance(value, str) and "{{" in value:
                if not EXPR_RE.match(value.strip()):
                    findings.append(error("RULE_DATA_005", f"component '{component_id}' field '{key}' has invalid expression syntax", 5))

        if component.get("component") == "Text":
            content = component.get("content")
            if isinstance(content, str):
                if content.startswith("/"):
                    findings.append(error("RULE_DATA_003", f"Text '{component_id}' appears to render a raw data path: {content}", 10))
                if "{{" in content and "}}" in content:
                    findings.append(error("RULE_DATA_006", f"Text '{component_id}' 的 content 包含 '{{ }}' 表达式语法，应使用对象形式 {{ path: '...' }}", 5))

    return findings


def validate_binding(ctx: ValidationContext, binding: DataBinding) -> list[Finding]:
    if binding.is_relative:
        return validate_relative_binding(ctx, binding)
    return validate_absolute_binding(ctx, binding)


def validate_absolute_binding(ctx: ValidationContext, binding: DataBinding) -> list[Finding]:
    path = binding.path
    if not PATH_RE.match(path):
        return [error("RULE_DATA_001", f"component '{binding.component_id}' binding path is not a valid JSON Pointer: {path}", 5)]
    exists, _ = json_pointer_get(ctx.data_roots, path)
    if ctx.data_roots and not exists:
        return [error("RULE_DATA_002", f"component '{binding.component_id}' binding path has no initial value: {path}", 10)]
    return []


def validate_relative_binding(ctx: ValidationContext, binding: DataBinding) -> list[Finding]:
    if not binding.repeated or not binding.scope_path:
        return [error("RULE_DATA_001", f"component '{binding.component_id}' binding path must start with '/': {binding.path}", 5)]

    exists, source = json_pointer_get(ctx.data_roots, binding.scope_path)
    if ctx.data_roots and not exists:
        return [error("RULE_DATA_002", f"component '{binding.component_id}' repeated scope has no initial value: {binding.scope_path}", 10)]
    if not isinstance(source, list) or not source:
        return []

    sample = source[0]
    exists, _ = get_relative_value(sample, binding.path)
    if not exists:
        return [error("RULE_DATA_002", f"component '{binding.component_id}' relative binding path has no item value: {binding.path}", 10)]
    return []


def get_relative_value(root: Any, path: str) -> tuple[bool, Any]:
    current = root
    for part in path.split("."):
        if not part:
            return False, None
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current
