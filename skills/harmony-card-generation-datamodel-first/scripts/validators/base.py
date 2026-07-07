from __future__ import annotations

import re
from typing import Any, Iterable


EXPR_RE = re.compile(r"\{\{([\s\S]*)\}\}")
INTERP_RE = re.compile(r"\$\{([^}]+)\}")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class BaseValidator:
    stage = "hard"
    name = "base"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        raise NotImplementedError


def walk_json(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    yield pointer or "/", value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, pointer + "/" + escape_pointer(str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, pointer + "/" + str(index))


def escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def unescape_pointer(value: str) -> str:
    return value.replace("~1", "/").replace("~0", "~")


def is_json_pointer(value: Any) -> bool:
    return isinstance(value, str) and (value == "/" or value.startswith("/"))


def is_empty_required_value(value: Any, *, empty_strings: bool = True, empty_collections: bool = False) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return empty_strings and not value.strip()
    if empty_collections and isinstance(value, (dict, list)):
        return len(value) == 0
    return False


def read_pointer(data: Any, pointer: str) -> tuple[bool, Any]:
    if not is_json_pointer(pointer):
        return False, None
    if pointer == "/":
        return True, data
    current = data
    for raw_part in pointer.strip("/").split("/"):
        part = unescape_pointer(raw_part)
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def set_pointer(data: dict[str, Any], pointer: str, value: Any) -> dict[str, Any]:
    if pointer == "/":
        return value if isinstance(value, dict) else {"value": value}
    current: Any = data
    parts = [unescape_pointer(part) for part in pointer.strip("/").split("/")]
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return data
        current = current.setdefault(part, {})
    if isinstance(current, dict) and parts:
        current[parts[-1]] = value
    return data


def pointer_overlaps(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)(?:vp|fp|px)?\s*", value)
        if match:
            return float(match.group(1))
    return None


def is_match_parent(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == "matchParent"


def resolve_dimension(value: Any, parent_size: Any = None) -> float | None:
    if is_match_parent(value):
        return numeric(parent_size)
    return numeric(value)


def spacing_tuple(value: Any) -> tuple[float, float, float, float]:
    if value is None:
        return 0, 0, 0, 0
    number = numeric(value)
    if number is not None:
        return number, number, number, number
    if isinstance(value, dict):
        return (
            numeric(value.get("top")) or 0,
            numeric(value.get("right")) or 0,
            numeric(value.get("bottom")) or 0,
            numeric(value.get("left")) or 0,
        )
    return 0, 0, 0, 0


def expression_like(value: Any) -> bool:
    return isinstance(value, str) and ("{{" in value or "}}" in value or "${" in value or "$__dataModel" in value)


def is_wrapped_expression(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith("{{") and value.strip().endswith("}}")


def expression_body(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        return stripped[2:-2].strip()
    return stripped


def expression_references(value: str) -> list[str]:
    return INTERP_RE.findall(expression_body(value))


def estimate_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for char in text:
        if CJK_RE.match(char):
            width += font_size
        elif char.isspace():
            width += 0.35 * font_size
        elif char in ".,;:!?'\"°%/|":
            width += 0.4 * font_size
        else:
            width += 0.6 * font_size
    return width


def schema_path_exists(schema: dict[str, Any], pointer: str) -> bool:
    if not is_json_pointer(pointer):
        return False
    if pointer == "/":
        return True
    current = schema
    for raw_part in pointer.strip("/").split("/"):
        part = unescape_pointer(raw_part)
        current_type = current.get("type") if isinstance(current, dict) else None
        if current_type == "array":
            current = current.get("items", {})
            if part.isdigit():
                continue
        if isinstance(current, dict) and "properties" in current and part in current["properties"]:
            current = current["properties"][part]
        else:
            return False
    return True


def static_expression_value(value: str, data_model: Any) -> Any:
    refs = expression_references(value)
    body = expression_body(value)
    if len(refs) == 1 and body == "${" + refs[0] + "}":
        ref = refs[0]
        if ref.startswith("/"):
            ok, result = read_pointer(data_model, ref)
            if ok:
                return result
    return None
