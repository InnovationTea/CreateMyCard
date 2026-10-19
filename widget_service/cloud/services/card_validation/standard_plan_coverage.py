# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""单步兜底的事实语义交接；不把Compact组件或布局合同施加到标准A2UI。"""

import ast
import json
import re
from typing import Any

from app.logger import logger
from services.single_step_contract import clean_font_requirements

from .base import expression_body, is_single_wrapped_expression
from .source_parser import normalize_dsl_text

_VISIBLE_FIELDS = {"Text": "content", "Button": "label", "Checkbox": "label"}
_PATH = re.compile(r"\$\{(?P<path>/[^}]+)\}")
_EXPRESSION_ATOM = re.compile(r"'(?:\\.|[^'\\])*'|(?P<binding>\$\{/[^}]+\})")


def standard_plan_coverage_errors(
    genui: str, plan: dict | None, task_spec: dict,
    *, font_requirements: list[dict] | None = None,
) -> list[str]:
    """只检查已接受事实/动作，不要求高阶标题或固定骨架；数据行不算展示。"""
    if not plan and not font_requirements:
        return []
    try:
        messages = [json.loads(line) for line in normalize_dsl_text(genui).splitlines()]
    except (json.JSONDecodeError, TypeError):
        return ["Single-step coverage requires valid standard A2UI JSONL."]
    update = None
    for message in messages:
        if isinstance(message, dict) and isinstance(message.get("updateComponents"), dict):
            update = message.get("updateComponents")
    if update is None:
        return ["Single-step coverage requires updateComponents."]
    paths: set[str] = set()
    literals: list[str] = []
    handlers: list[dict] = []
    displays: list[tuple[set[str], list[str], object]] = []
    for component in _reachable_components(update):
        kind = component.get("component")
        field = _VISIBLE_FIELDS.get(kind) if isinstance(kind, str) else None
        if field is not None:
            component_paths: set[str] = set()
            component_literals: list[str] = []
            _collect_visible(component.get(field), component_paths, component_literals)
            paths.update(component_paths)
            literals.extend(component_literals)
            styles = component.get("styles")
            font = styles.get("fontSize") if isinstance(styles, dict) else None
            displays.append((component_paths, component_literals, font))
        clicks = component.get("onClick")
        if isinstance(clicks, list):
            for handler in clicks:
                if isinstance(handler, dict):
                    handlers.append(handler)
    facts = plan.get("info_required", []) if isinstance(plan, dict) else []
    if not isinstance(facts, list):
        return ["Single-step fallback has an invalid accepted fact contract."]
    candidates = task_spec.get("eventCandidates", [])
    errors: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        data_id = fact.get("dataId")
        if isinstance(data_id, str) and data_id not in paths:
            errors.append(f"Single-step fallback is missing visible Plan data: {data_id}.")
        text = fact.get("text")
        if isinstance(text, str) and _normalize(text):
            if not any(_normalize(text) in value for value in literals):
                errors.append(f"Single-step fallback is missing Plan text: {text}.")
        action_id = fact.get("actionId")
        if isinstance(action_id, str):
            expected = _event_handler(candidates, action_id)
            if expected is None or expected not in handlers:
                errors.append(f"Single-step fallback is missing Plan action: {action_id}.")
    for requirement in clean_font_requirements(font_requirements):
        data_id = requirement.get("dataId")
        text = requirement.get("text")
        font = requirement.get("fontSize")
        matched = False
        for visible_paths, visible_texts, actual_font in displays:
            same_data = isinstance(data_id, str) and data_id in visible_paths
            same_text = isinstance(text, str) and any(
                _normalize(text) in value for value in visible_texts
            )
            if (same_data or same_text) and actual_font == font:
                matched = True
                break
        if not matched:
            errors.append(
                f"Single-step fallback must preserve fontSize {font} for {data_id or text}."
            )
    return errors


def _reachable_components(update: dict) -> list[dict]:
    components = update.get("components")
    root = update.get("root")
    if not isinstance(components, list) or not isinstance(root, str):
        return []
    indexed: dict[str, dict] = {}
    for component in components:
        if not isinstance(component, dict):
            continue
        identifier = component.get("id")
        if isinstance(identifier, str):
            indexed[identifier] = component
    pending = [root]
    visited: set[str] = set()
    reachable: list[dict] = []
    while pending:
        identifier = pending.pop()
        if identifier in visited:
            continue
        visited.add(identifier)
        component = indexed.get(identifier)
        if component is None:
            continue
        styles = component.get("styles")
        if isinstance(styles, dict):
            if styles.get("visibility") in ("hidden", "none") or styles.get("opacity") == 0:
                continue
        reachable.append(component)
        children = component.get("children")
        if isinstance(children, list):
            for child in reversed(children):
                if isinstance(child, str):
                    pending.append(child)
        elif isinstance(children, dict):
            template = children.get("componentId")
            if isinstance(template, str):
                pending.append(template)
    return reachable


def _collect_visible(value: Any, paths: set[str], literals: list[str]) -> None:
    if isinstance(value, str):
        matches = list(_PATH.finditer(value))
        for match in matches:
            paths.add(match.group("path"))
        if is_single_wrapped_expression(value):
            literals.extend(_normalize(item) for item in _concatenated_literals(value))
        elif not matches:
            literals.append(_normalize(value))
    elif isinstance(value, dict):
        path = value.get("path")
        if set(value) == {"path"} and isinstance(path, str):
            paths.add(path)


def _concatenated_literals(value: str) -> list[str]:
    """只收集无条件拼接片段，不把条件/函数内出现的字符串当作可见文本。"""
    body = expression_body(value)
    if len(body) > 2048:
        return []
    bindings: set[str] = set()

    def replace_binding(match: re.Match) -> str:
        if match.group("binding") is None:
            return match.group(0)
        name = f"__single_step_binding_{len(bindings)}"
        bindings.add(name)
        return name

    translated = _EXPRESSION_ATOM.sub(replace_binding, body)
    try:
        root = ast.parse(translated, mode="eval").body
    except (SyntaxError, ValueError, RecursionError) as exc:
        logger.debug(
            "Single-step literal coverage skipped unsupported expression: {}", type(exc).__name__
        )
        return []
    pending = [root]
    literals: list[str] = []
    segment = ""
    while pending:
        node = pending.pop()
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            pending.extend((node.right, node.left))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            segment += node.value
        elif isinstance(node, ast.Name) and node.id in bindings:
            if segment:
                literals.append(segment)
                segment = ""
        else:
            return []
    if segment:
        literals.append(segment)
    return literals


def _event_handler(candidates: Any, action_id: str) -> dict | None:
    handler = None
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("id") != action_id:
                continue
            call = candidate.get("call")
            args = candidate.get("args")
            if isinstance(call, str) and isinstance(args, dict):
                handler = {"call": call, "args": args}
                break
    return handler


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()
