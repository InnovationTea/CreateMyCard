from __future__ import annotations

import re

from .base import BaseValidator, expression_body, expression_like, expression_references


class ExpressionValidator(BaseValidator):
    stage = "hard"
    name = "expression"

    _function_re = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    _double_string_re = re.compile(r'"(?:[^"\\]|\\.)*"')

    def validate(self, context, rules, reporter) -> None:
        expression_rules = getattr(rules, "expression", {}) or {}
        self._max_length = int(expression_rules.get("maxLength", 2048))
        self._max_paren_depth = int(expression_rules.get("maxParenDepth", 20))
        self._banned_variables = tuple(expression_rules.get(
            "bannedVariables", ["$__widthBreakpoint", "$__colorMode", "$context"]
        ))
        self._banned_operators = tuple(expression_rules.get(
            "bannedOperators", ["===", "!==", "??", "?."]
        ))
        self._banned_keywords = tuple(expression_rules.get(
            "bannedKeywords", ["and", "or", "not"]
        ))
        self._allowed_functions = set(expression_rules.get("allowedFunctions", ["size"]))

        for file_kind, pointer, value, component_id in context.expression_locations:
            line = 2 if file_kind == "genui" else None
            if file_kind == "cardspec":
                reporter.add(
                    "error",
                    "CARD_STATIC_FIELD_INVALID",
                    "hard",
                    "cardspec",
                    json_pointer=pointer,
                    actual=value,
                    message="CardSpec 不允许写表达式。",
                    fix_hint="CardSpec 的 title/description/arguments 必须是静态 JSON 值。",
                )
                continue
            self._check_expression(value, pointer, line, reporter)

        self._check_forbidden_expression_fields(context, reporter)

    def _check_expression(self, value: str, pointer: str, line: int | None, reporter) -> None:
        stripped = value.strip()
        if "{{" in stripped or "}}" in stripped:
            if not (stripped.startswith("{{") and stripped.endswith("}}")) or stripped.count("{{") != 1 or stripped.count("}}") != 1:
                reporter.add(
                    "error",
                    "EXPR_FULL_STRING_REQUIRED",
                    "hard",
                    "genui",
                    line=line,
                    json_pointer=pointer,
                    actual=value,
                    message="动态值必须是完整 {{ ... }} 表达式，不能半嵌入普通字符串或嵌套表达式。",
                    fix_hint="例如把 \"会议 {{ ${/time} }}\" 改成 \"{{ '会议 ' + ${/time} }}\"。",
                )
                return
        elif "${" in stripped:
            reporter.add(
                "error",
                "EXPR_FULL_STRING_REQUIRED",
                "hard",
                "genui",
                line=line,
                json_pointer=pointer,
                actual=value,
                message="包含 ${...} 的动态值必须包裹在 {{ ... }} 中。",
                fix_hint="例如写成 \"{{ ${/path/to/value} }}\"。",
            )
            return
        else:
            return

        body = expression_body(stripped)
        if not body:
            reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, actual=value, message="表达式内容不能为空。")
        if len(stripped) > self._max_length:
            reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, message=f"表达式长度不能超过 {self._max_length} 字符。")
        if self._paren_depth(body) > self._max_paren_depth:
            reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, message=f"表达式括号嵌套不能超过 {self._max_paren_depth} 层。")
        if self._double_string_re.search(body):
            reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, actual=value, message="表达式内字符串必须使用单引号。")
        for banned in self._banned_variables:
            if banned in body:
                reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, actual=banned, message="表达式使用了禁用变量。")
        if any(token in body for token in self._banned_operators):
            reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, message="表达式包含当前语法不支持的操作符。")
        for word in self._banned_keywords:
            if re.search(rf"\b{word}\b", body):
                reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, actual=word, message="逻辑操作只能使用 &&、||、!。")
        for function_name in self._function_re.findall(body):
            if function_name not in self._allowed_functions:
                reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, actual=function_name, expected=sorted(self._allowed_functions), message="表达式只允许使用声明的内置函数。")
        for ref in expression_references(stripped):
            if not ref:
                reporter.add("error", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, message="表达式中存在空的 ${} 引用。")
            elif ref.startswith("/") and "." in ref.strip("/"):
                reporter.add("warning", "EXPR_PARSE_FAILED", "hard", "genui", line=line, json_pointer=pointer, actual=ref, message="JSON Pointer 片段中出现点号，请确认不是误写成点路径。")

    def _paren_depth(self, body: str) -> int:
        depth = 0
        max_depth = 0
        in_string = False
        escaped = False
        for char in body:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "'":
                    in_string = False
                continue
            if char == "'":
                in_string = True
            elif char == "(":
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == ")":
                depth = max(0, depth - 1)
        return max_depth

    def _check_forbidden_expression_fields(self, context, reporter) -> None:
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            for field in ("id", "component"):
                if expression_like(component.get(field)):
                    reporter.add("error", "EXPR_FORBIDDEN_FIELD", "hard", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/{field}", actual=component.get(field), message=f"{field} 不允许表达式。")
            on_click = component.get("onClick")
            if isinstance(on_click, list):
                for index, handler in enumerate(on_click):
                    if not isinstance(handler, dict):
                        continue
                    for field in ("call", "as"):
                        if expression_like(handler.get(field)):
                            reporter.add("error", "EXPR_FORBIDDEN_FIELD", "hard", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/onClick/{index}/{field}", actual=handler.get(field), message=f"EventHandler.{field} 不允许表达式。")
            children = component.get("children")
            if isinstance(children, dict) and expression_like(children.get("path")):
                reporter.add("error", "EXPR_FORBIDDEN_FIELD", "hard", "genui", line=2, json_pointer=f"/updateComponents/componentsById/{component_id}/children/path", actual=children.get("path"), message="模板 children.path 不允许表达式。")
