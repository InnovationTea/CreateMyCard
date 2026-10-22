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
    conditional = _BOOLEAN_CONDITIONAL.fullmatch(value)
    if conditional is None:
        return None
    condition = lookup(conditional.group("path"))
    if not isinstance(condition, bool):
        return None
    branch = conditional.group("yes" if condition else "no")
    return concatenated_display_text("{{ " + branch + " }}", lookup)


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
