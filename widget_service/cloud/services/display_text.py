"""Resolve plain text and restricted string concatenation without executing expressions."""

import ast
import re
from collections.abc import Callable
from typing import Any

_LITERAL = r'''(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
_DISPLAY_TOKEN = rf"(?:\$\{{/[^{{}}]+\}}|{_LITERAL})"
_CONCATENATION = rf"{_DISPLAY_TOKEN}(?:\s*\+\s*{_DISPLAY_TOKEN})*"
_BOOLEAN_CONDITIONAL = re.compile(
    rf"\s*\{{\{{\s*\$\{{(?P<path>/[^{{}}]+)\}}\s*\?\s*"
    rf"(?P<yes>{_CONCATENATION})\s*:\s*(?P<no>{_CONCATENATION})\s*\}}\}}\s*",
    flags=re.DOTALL,
)


def current_display_text(value: Any, lookup: Callable[[str], Any]) -> str | None:
    """Resolve concatenation or a boolean-binding conditional without executing code."""
    text = concatenated_display_text(value, lookup)
    if text is not None or not isinstance(value, str):
        return text
    # Group support is theme-only; composition and width estimation keep the flat contract.
    text = _grouped_display_text(value, lookup)
    if text is not None:
        return text
    conditional = _BOOLEAN_CONDITIONAL.fullmatch(value)
    if conditional is None:
        return None
    condition = lookup(conditional.group("path"))
    if not isinstance(condition, bool):
        return None
    branch = conditional.group("yes" if condition else "no")
    return concatenated_display_text("{{ " + branch + " }}", lookup)


def _grouped_operand(
    match: re.Match[str], lookup: Callable[[str], Any],
) -> str | int | float | None:
    result: str | int | float | None = None
    raw_path = match.group("path")
    if raw_path is not None:
        sample = lookup(raw_path.removeprefix("${").removesuffix("}"))
        if not isinstance(sample, bool) and isinstance(sample, (str, int, float)):
            result = sample
    else:
        try:
            literal = ast.literal_eval(match.group("literal"))
        except (SyntaxError, ValueError):
            return None
        if isinstance(literal, str):
            result = literal
    return result


def _grouped_display_text(value: str, lookup: Callable[[str], Any]) -> str | None:
    expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, flags=re.DOTALL)
    if expression is None:
        return None
    body = expression.group(1).strip()
    if "(" not in body:
        return None
    token = re.compile(
        rf"(?P<path>\$\{{/[^{{}}]+\}})|(?P<literal>{_LITERAL})|(?P<symbol>[+()])"
    )
    # Keep group results typed: a numeric subgroup must not become string addition.
    groups: list[str | int | float | None] = [None]
    expects_operand = True
    offset = 0
    for match in token.finditer(body):
        if body[offset:match.start()].strip():
            return None
        offset = match.end()
        symbol = match.group("symbol")
        if symbol == "(":
            if not expects_operand:
                return None
            groups.append(None)
            continue
        if symbol == "+":
            if expects_operand:
                return None
            expects_operand = True
            continue
        if symbol == ")":
            if expects_operand or len(groups) == 1:
                return None
            sample = groups.pop()
        else:
            if not expects_operand:
                return None
            sample = _grouped_operand(match, lookup)
        if sample is None:
            return None
        previous = groups[-1]
        if previous is not None:
            if not isinstance(previous, str) and not isinstance(sample, str):
                return None
            sample = str(previous) + str(sample)
        groups[-1] = sample
        expects_operand = False
    if expects_operand or len(groups) != 1 or body[offset:].strip():
        return None
    return str(groups[0])


def concatenated_display_text(value: Any, lookup: Callable[[str], Any]) -> str | None:
    if not isinstance(value, str):
        return None
    if "{{" not in value:
        return value
    expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, flags=re.DOTALL)
    if expression is None:
        return None
    token = re.compile(rf"(?P<path>\$\{{(/[^{{}}]+)\}})|(?P<literal>{_LITERAL})")
    body = expression.group(1).strip()
    parts: list[str] = []
    string_mode = False
    offset = 0
    for match in token.finditer(body):
        if body[offset:match.start()].strip() != ("+" if parts else ""):
            return None
        raw_path = match.group("path")
        if raw_path is not None:
            path = raw_path.removeprefix("${").removesuffix("}")
            sample = lookup(path)
            if isinstance(sample, bool) or not isinstance(sample, (str, int, float)):
                return None
            if parts and not string_mode and not isinstance(sample, str):
                return None
            string_mode = string_mode or isinstance(sample, str)
            parts.append(str(sample))
        else:
            try:
                parts.append(ast.literal_eval(match.group("literal")))
                string_mode = True
            except (SyntaxError, ValueError):
                return None
        offset = match.end()
    return "".join(parts) if parts and not body[offset:].strip() else None
