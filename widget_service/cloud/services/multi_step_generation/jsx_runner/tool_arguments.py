"""Conservative recovery for model-generated tool argument JSON."""

from __future__ import annotations

import json
import re
from typing import Any


class ToolArgumentError(ValueError):
    """The model returned tool arguments that are not recoverable JSON."""


def _escape_raw_controls(source: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    replacements = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    for character in source:
        if in_string and character in replacements:
            output.append(replacements[character])
            continue
        output.append(character)
        if escaped:
            escaped = False
        elif character == "\\" and in_string:
            escaped = True
        elif character == '"':
            in_string = not in_string
    return "".join(output)


def _remove_trailing_commas(source: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    for index, character in enumerate(source):
        if not in_string and character == ",":
            cursor = index + 1
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
            if cursor < len(source) and source[cursor] in "]}":
                continue
        output.append(character)
        if escaped:
            escaped = False
        elif character == "\\" and in_string:
            escaped = True
        elif character == '"':
            in_string = not in_string
    return "".join(output)


def _variants(source: str):
    variants = [(source, [])]
    controls = _escape_raw_controls(source)
    if controls != source:
        variants.append((controls, ["escaped_raw_control_characters"]))
    for candidate, rules in list(variants):
        without_trailing = _remove_trailing_commas(candidate)
        if without_trailing != candidate:
            variants.append((without_trailing, [*rules, "removed_trailing_commas"]))
    seen: set[str] = set()
    for candidate, rules in variants:
        if candidate not in seen:
            seen.add(candidate)
            yield candidate, rules


def _load_object(source: str) -> tuple[dict[str, Any], list[str]]:
    last_error: Exception = TypeError("tool arguments must be an object")
    for candidate, rules in _variants(source):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed, rules
        if isinstance(parsed, str):
            for nested, nested_rules in _variants(parsed.strip()):
                try:
                    decoded = json.loads(nested)
                except json.JSONDecodeError as exc:
                    last_error = exc
                    continue
                if isinstance(decoded, dict):
                    return decoded, [*rules, "decoded_nested_json", *nested_rules]
        last_error = TypeError("tool arguments must be an object")
    raise last_error


def _decode_opaque_string(source: str) -> str:
    output: list[str] = []
    index = 0
    escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
    }
    while index < len(source):
        character = source[index]
        if character != "\\" or index + 1 >= len(source):
            output.append(character)
            index += 1
            continue
        escaped = source[index + 1]
        if escaped in escapes:
            output.append(escapes[escaped])
            index += 2
            continue
        if escaped == "u" and index + 5 < len(source):
            token = source[index + 2:index + 6]
            if re.fullmatch(r"[0-9a-fA-F]{4}", token):
                output.append(chr(int(token, 16)))
                index += 6
                continue
        output.extend(("\\", escaped))
        index += 2
    return "".join(output)


def _recover_submit_jsx(source: str) -> tuple[dict[str, Any], list[str]] | None:
    opening = re.match(r'\s*\{\s*"jsx"\s*:\s*"', source)
    recovered = None
    if opening is not None:
        boundary = re.compile(r'"\s*,?\s*(?P<field>"(?:decision|coverage|unmetRequirements)")\s*:')
        for match in boundary.finditer(source, opening.end()):
            jsx = _decode_opaque_string(source[opening.end():match.start()]).strip()
            if not jsx.startswith("<Card") or not (jsx.endswith("</Card>") or re.search(r"/\s*>$", jsx)):
                continue
            try:
                tail, tail_repairs = _load_object("{" + source[match.start("field"):])
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(tail.get("decision"), dict) and "jsx" not in tail:
                recovered = ({"jsx": jsx, **tail}, ["recovered_opaque_jsx", *tail_repairs])
                break
    return recovered


def parse_tool_arguments(
    value: str | None,
    *,
    tool_name: str | None = None,
    repairs: list[str] | None = None,
) -> dict[str, Any]:
    source = (value or "{}").strip()
    applied: list[str] = []
    if source.startswith("\ufeff"):
        source = source.lstrip("\ufeff")
        applied.append("removed_bom")
    fence = re.fullmatch(
        r"```(?:json|javascript|js)?\s*(.*?)\s*```",
        source,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence:
        source = fence.group(1).strip()
        applied.append("removed_code_fence")
    try:
        parsed, safe_repairs = _load_object(source)
    except (json.JSONDecodeError, TypeError) as exc:
        recovered = _recover_submit_jsx(source) if tool_name == "submit_card_jsx" else None
        if recovered is None:
            raise ToolArgumentError(f"invalid tool arguments: {exc}") from exc
        parsed, safe_repairs = recovered
    applied.extend(safe_repairs)
    if repairs is not None:
        repairs.extend(dict.fromkeys(applied))
    return parsed
