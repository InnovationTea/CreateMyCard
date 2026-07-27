from __future__ import annotations

import json
import re
from typing import Any

from .base import set_pointer, walk_json
from .context import ValidationContext
from .diagnostics import Reporter


def extract_fenced(raw: str, lang: str) -> str | None:
    match = re.search(rf"```{re.escape(lang)}\s*([\s\S]*?)```", raw, re.I)
    if match:
        return match.group(1).strip()
    return None


def extract_combined(raw: str) -> tuple[str, str]:
    genui = extract_fenced(raw, "genui")
    cardspec = extract_fenced(raw, "cardspec")
    if genui is not None and cardspec is not None:
        return genui, cardspec
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    json_lines = [line for line in lines if line.startswith("{")]
    if len(json_lines) >= 4:
        return "\n".join(json_lines[:3]), "\n".join(json_lines[3:])
    return raw, ""


def normalize_dsl_text(raw: str) -> str:
    fenced = extract_fenced(raw, "genui")
    if fenced is not None:
        return fenced
    return raw.strip()


def normalize_cardspec_text(raw: str) -> str:
    fenced = extract_fenced(raw, "cardspec")
    if fenced is not None:
        return fenced
    return raw.strip()


class SourceParser:
    def parse(self, dsl_text: str, cardspec_text: str, reporter: Reporter) -> ValidationContext:
        context = ValidationContext(dsl_text=dsl_text, cardspec_text=cardspec_text)
        self._parse_dsl(context, reporter)
        self._parse_cardspec(context, reporter)
        self._build_indexes(context)
        return context

    def _parse_dsl(self, context: ValidationContext, reporter: Reporter) -> None:
        if not context.dsl_text:
            return
        lines = [line.strip() for line in context.dsl_text.splitlines() if line.strip()]
        context.dsl_line_count = len(lines)
        if len(lines) != 3:
            reporter.add(
                "error",
                "DSL_JSONL_LINE_COUNT",
                "hard",
                "genui",
                line=None,
                actual=len(lines),
                expected=3,
            )
        for index, line in enumerate(lines[:3], 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                reporter.add(
                    "error",
                    "DSL_JSON_PARSE_FAILED",
                    "hard",
                    "genui",
                    line=index,
                    message=f"genui 第 {index} 行不是合法 JSON：{exc.msg}。",
                    fix_hint="修复该行 JSON 语法，注意逗号、引号和括号配对。",
                )
                continue
            if not isinstance(value, dict):
                reporter.add(
                    "error",
                    "DSL_JSON_PARSE_FAILED",
                    "hard",
                    "genui",
                    line=index,
                    message=f"genui 第 {index} 行必须是 JSON object。",
                    actual=value,
                )
                continue
            context.dsl_messages.append(value)

    def _parse_cardspec(self, context: ValidationContext, reporter: Reporter) -> None:
        if not context.cardspec_text:
            return
        try:
            value = json.loads(context.cardspec_text)
        except json.JSONDecodeError as exc:
            reporter.add(
                "error",
                "CARD_JSON_PARSE_FAILED",
                "hard",
                "cardspec",
                message=f"CardSpec 不是合法 JSON：{exc.msg}。",
                fix_hint="修复 CardSpec JSON 语法，确保只输出一个 JSON object。",
            )
            return
        if not isinstance(value, dict):
            reporter.add(
                "error",
                "CARD_JSON_PARSE_FAILED",
                "hard",
                "cardspec",
                message="CardSpec 必须是 JSON object。",
                actual=value,
            )
            return
        context.cardspec = value

    def _build_indexes(self, context: ValidationContext) -> None:
        if len(context.dsl_messages) >= 1:
            context.create_surface = (
                context.dsl_messages[0].get("createSurface", {})
                if isinstance(context.dsl_messages[0], dict)
                else {}
            )
        if len(context.dsl_messages) >= 2:
            context.update_components = (
                context.dsl_messages[1].get("updateComponents", {})
                if isinstance(context.dsl_messages[1], dict)
                else {}
            )
        if len(context.dsl_messages) >= 3:
            context.update_data_model = (
                context.dsl_messages[2].get("updateDataModel", {})
                if isinstance(context.dsl_messages[2], dict)
                else {}
            )

        components = context.update_components.get("components")
        if isinstance(components, list):
            context.components = [item for item in components if isinstance(item, dict)]
        for component in context.components:
            component_id = component.get("id")
            if isinstance(component_id, str):
                if component_id in context.components_by_id:
                    context.duplicate_component_ids.add(component_id)
                context.components_by_id[component_id] = component

        root = context.update_components.get("root")
        if isinstance(root, str):
            context.root_id = root
            context.root_component = context.components_by_id.get(root)

        path = context.update_data_model.get("path")
        value = context.update_data_model.get("value")
        if path == "/" or path is None:
            context.data_model = value if value is not None else {}
        elif isinstance(path, str):
            context.data_model = set_pointer({}, path, value)
        else:
            context.data_model = {}

        self._collect_expressions(context)
        self._collect_template_contexts(context)

    def _contains_expression_marker(self, value: object) -> bool:
        if not isinstance(value, str):
            return False

        expression_markers = ("{{", "}}", "${")
        return any(marker in value for marker in expression_markers)

    def _collect_expressions(self, context: ValidationContext) -> None:
        for component in context.components:
            component_id_value = component.get("id")
            component_id = (
                component_id_value if isinstance(component_id_value, str) else None
            )

            for pointer, value in walk_json(component):
                if not self._contains_expression_marker(value):
                    continue
                context.expression_locations.append(
                    (
                        "genui",
                        f"/updateComponents/componentsById/{component_id}{pointer}",
                        value,
                        component_id,
                    )
                )

    def _collect_template_contexts(self, context: ValidationContext) -> None:
        for component in context.components:
            children = component.get("children")
            if not isinstance(children, dict):
                continue
            component_id = children.get("componentId")
            path = children.get("path")
            if not isinstance(component_id, str) or not isinstance(path, str):
                continue
            for descendant_id in self._descendants(component_id, context.components_by_id):
                context.template_context_by_component[descendant_id] = {
                    "templateRoot": component_id,
                    "path": path,
                    "containerId": component.get("id"),
                }

    def _descendants(self, component_id: str, by_id: dict[str, dict[str, Any]]) -> set[str]:
        result: set[str] = set()
        stack = [component_id]
        while stack:
            current_id = stack.pop()
            if current_id in result:
                continue
            result.add(current_id)
            component = by_id.get(current_id, {})
            children = component.get("children")
            if isinstance(children, list):
                stack.extend(child for child in children if isinstance(child, str))
            elif isinstance(children, dict) and isinstance(children.get("componentId"), str):
                stack.append(children["componentId"])
        return result
