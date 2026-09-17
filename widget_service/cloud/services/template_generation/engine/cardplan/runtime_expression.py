"""解析模板作者侧不带外层引号的运行时 Expr，不执行表达式。"""

from __future__ import annotations

import re

from services.template_generation.engine.a2ui_expression import normalize_tersel_expression

from .models import TemplateValue

_EXPR_CALL = re.compile(r"(?<![\w.$#])Expr\s*\(")
_DATA_REFERENCE = re.compile(r"data\.([A-Za-z_][A-Za-z0-9_]*)")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CLOSERS = {"(": ")", "[": "]", "{": "}"}


def translate_runtime_expressions(source: str) -> str:
    """在 Python AST 解析之前封装 Expr，避免 JS 三元被误认为编译期语法。"""
    translated: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char in {"'", '"', "`"}:
            end = _quoted_end(source, index)
            translated.append(source[slice(index, end)])
        elif source.startswith("#Expr(", index):
            end = _call_end(source, index + len("#Expr")) + 1
            translated.append(source[slice(index, end)])
        elif char == "#":
            newline = source.find("\n", index)
            end = len(source) if newline < 0 else newline + 1
            translated.append(source[slice(index, end)])
        else:
            call = _EXPR_CALL.match(source, index)
            if call is None:
                end = index + 1
                translated.append(char)
            else:
                closing = _call_end(source, call.end() - 1)
                argument = source[slice(call.end(), closing)].strip()
                end = closing + 1
                legacy = argument.startswith("`") and _quoted_end(argument, 0) == len(argument)
                if legacy:
                    translated.append(source[slice(index, end)])
                else:
                    translated.append(f"_CardTplRuntimeExpr({argument!r})")
        index = end
    return "".join(translated)


def _quoted_end(source: str, start: int) -> int:
    quote = source[start]
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
            continue
        if source[index] == quote:
            return index + 1
        index += 1
    raise ValueError("Provider Template Expr string is not closed")


def _call_end(source: str, opening: int) -> int:
    stack: list[str] = []
    index = opening
    while index < len(source):
        char = source[index]
        if char in {"'", '"', "`"}:
            index = _quoted_end(source, index)
            continue
        closer = _CLOSERS.get(char)
        if closer is not None:
            stack.append(closer)
        elif char in {")", "]", "}"}:
            if not stack or stack.pop() != char:
                raise ValueError("Provider Template Expr delimiters do not match")
            if not stack:
                return index
        index += 1
    raise ValueError("Provider Template Expr call is not closed")


def parse_runtime_expression(source: str) -> TemplateValue:
    """将受限 JS 表达式转为已有的 literal/binding IR 并复用 A2UI 语法校验。"""
    parts: list[TemplateValue] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char in {"'", '"'}:
            value, index = _read_string(source, index)
            parts.append(_literal(_expression_string(value)))
            continue
        if char == "`":
            template_parts, index = _read_template(source, index)
            parts.extend(template_parts)
            continue
        reference = _DATA_REFERENCE.match(source, index)
        if reference is not None:
            parts.append(TemplateValue(kind="binding", name=reference.group(1)))
            index = reference.end()
            continue
        identifier = _IDENTIFIER.match(source, index)
        if identifier is not None:
            name = identifier.group(0)
            if name not in {"size", "true", "false"}:
                raise ValueError(f"Provider Template Expr identifier is not supported: {name}")
            parts.append(_literal(name))
            index = identifier.end()
            continue
        if char == "$":
            raise ValueError("Provider Template Expr references must use declared data.xxx")
        parts.append(_literal(char))
        index += 1

    symbolic: list[str] = []
    for part in parts:
        if part.kind == "binding":
            assert isinstance(part.name, str)
            symbolic.append("${data." + part.name + "}")
        else:
            assert isinstance(part.value, str)
            symbolic.append(part.value)
    try:
        normalize_tersel_expression("".join(symbolic))
    except RecursionError as exc:
        raise ValueError("Provider Template Expr exceeds the parser complexity limit") from exc
    return TemplateValue(kind="expression", items=tuple(parts))


def _literal(value: str) -> TemplateValue:
    return TemplateValue(kind="literal", value=value)


def _expression_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return "'" + escaped + "'"


def _read_escape(source: str, index: int, quote: str) -> tuple[str, int]:
    escapes = {"\\": "\\", "n": "\n", "r": "\r", "t": "\t", quote: quote}
    if quote == "`":
        escapes["$"] = "$"
    following = source[slice(index + 1, index + 2)]
    value = escapes.get(following)
    if value is None:
        raise ValueError("Provider Template Expr string contains an unsupported escape")
    return value, index + 2


def _read_string(source: str, start: int) -> tuple[str, int]:
    quote = source[start]
    value: list[str] = []
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == quote:
            return "".join(value), index + 1
        if char == "\\":
            escaped, index = _read_escape(source, index, quote)
            value.append(escaped)
            continue
        if char in {"\n", "\r"}:
            raise ValueError("Provider Template Expr string contains an unescaped newline")
        value.append(char)
        index += 1
    raise ValueError("Provider Template Expr string is not closed")


def _read_template(source: str, start: int) -> tuple[list[TemplateValue], int]:
    parts = [_literal("(")]
    literal: list[str] = []
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "`":
            parts.append(_literal(_expression_string("".join(literal)) + ")"))
            return parts, index + 1
        if char == "\\":
            escaped, index = _read_escape(source, index, "`")
            literal.append(escaped)
            continue
        if source.startswith("${", index):
            reference = _DATA_REFERENCE.match(source, index + 2)
            if reference is None:
                raise ValueError("Provider Template Expr interpolation requires ${data.xxx}")
            if source[slice(reference.end(), reference.end() + 1)] != "}":
                raise ValueError("Provider Template Expr interpolation requires ${data.xxx}")
            parts.append(_literal(_expression_string("".join(literal)) + " + "))
            parts.append(TemplateValue(kind="binding", name=reference.group(1)))
            parts.append(_literal(" + "))
            literal.clear()
            index = reference.end() + 1
            continue
        literal.append(char)
        index += 1
    raise ValueError("Provider Template Expr template string is not closed")
