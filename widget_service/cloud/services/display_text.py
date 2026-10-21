"""Resolve plain text and restricted string concatenation without executing expressions."""

import ast
import re
from collections.abc import Callable
from typing import Any


def concatenated_display_text(value: Any, lookup: Callable[[str], Any]) -> str | None:
    if not isinstance(value, str):
        return None
    if "{{" not in value:
        return value
    expression = re.fullmatch(r"\s*\{\{(.*?)\}\}\s*", value, flags=re.DOTALL)
    if expression is None:
        return None
    literal = r'''(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
    token = re.compile(rf"(?P<path>\$\{{(/[^{{}}]+)\}})|(?P<literal>{literal})")
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
