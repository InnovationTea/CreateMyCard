from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from ..base import is_wrapped_expression, read_pointer, static_expression_value

COLOR_KEYS = ("fontColor", "textColor", "fillColor", "backgroundColor", "borderColor", "color")
FONT_COMPONENTS = {"Text", "Button"}
CONTAINERS = {"Row", "Column", "Stack", "List"}
EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF))
HEX_RE = re.compile(r"^#[0-9a-fA-F]{8}$")
ALPHA_STEPS = frozenset(
    {
        0x00,
        0x0C,
        0x0D,
        0x19,
        0x1A,
        0x26,
        0x27,
        0x33,
        0x4D,
        0x66,
        0x7F,
        0x80,
        0x99,
        0xB2,
        0xB3,
        0xCC,
        0xE5,
        0xE6,
        0xFF,
    }
)
FUSION_BACKGROUND_ID = "fusionBallBackground"
FUSION_CONTENT_ID_PREFIX = "__genui_render_component__"
FUSION_COMPONENTS = {
    "fusionBallLargeSlot": ("Stack", ("fusionBallLarge",)),
    "fusionBallLarge": ("Divider", ()),
    "fusionBallMediumSlot": ("Stack", ("fusionBallMedium",)),
    "fusionBallMedium": ("Divider", ()),
    "fusionBallSmallSlot": ("Stack", ("fusionBallSmall",)),
    "fusionBallSmall": ("Divider", ()),
    "fusionBallGlassLayer": ("Divider", ()),
}
FUSION_BACKGROUND_CHILDREN = (
    "fusionBallLargeSlot",
    "fusionBallMediumSlot",
    "fusionBallSmallSlot",
    "fusionBallGlassLayer",
)
QUALITY_WARNING_CODES = frozenset(
    {
        "ICON.DUPLICATE_SRC",
    }
)


@dataclass(frozen=True)
class QualityScene:
    kind: str
    shell_root: dict[str, Any]
    content_root: dict[str, Any]


def component_pointer(index: int, key: str = "") -> str:
    suffix = f"/{key}" if key else ""
    return f"/updateComponents/components/{index}{suffix}"


def iter_components(context: Any) -> Iterator[tuple[int, dict[str, Any]]]:
    for index, component in enumerate(context.components):
        if isinstance(component, dict):
            yield index, component


def children_of(
    component: dict[str, Any], by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    children = component.get("children")
    if not isinstance(children, list):
        return []
    return [by_id[child] for child in children if isinstance(child, str) and child in by_id]


def quality_scene(context: Any) -> QualityScene | None:
    root = context.components_by_id.get(context.root_id) if context.root_id else None
    if not isinstance(root, dict):
        return None
    content_root = _fusion_content_root(root, context.components_by_id)
    if content_root is not None:
        return QualityScene("fusionBall", root, content_root)
    kind = "template" if root.get("id") == "template_root" else "normal"
    return QualityScene(kind, root, root)


def _fusion_content_root(
    root: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    root_children = root.get("children")
    if root.get("component") != "Stack" or not isinstance(root_children, list):
        return None
    if len(root_children) != 2 or root_children[0] != FUSION_BACKGROUND_ID:
        return None
    content_id = root_children[1]
    valid_content_id = isinstance(content_id, str) and content_id.startswith(
        FUSION_CONTENT_ID_PREFIX
    )
    if not valid_content_id:
        return None
    background = by_id.get(FUSION_BACKGROUND_ID)
    content_root = by_id.get(content_id)
    if not _valid_fusion_background(background, by_id):
        return None
    if not isinstance(content_root, dict):
        return None
    if content_root.get("component") not in {"Row", "Column", "Stack"}:
        return None
    return content_root


def _valid_fusion_background(
    background: dict[str, Any] | None,
    by_id: dict[str, dict[str, Any]],
) -> bool:
    if not isinstance(background, dict) or background.get("component") != "Stack":
        return False
    if background.get("children") != list(FUSION_BACKGROUND_CHILDREN):
        return False
    for component_id, (component_type, expected_children) in FUSION_COMPONENTS.items():
        component = by_id.get(component_id)
        if not isinstance(component, dict) or component.get("component") != component_type:
            return False
        children = component.get("children")
        if expected_children and children != list(expected_children):
            return False
        if not expected_children and children not in (None, []):
            return False
    return True


def parents_by_id(context: Any) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for component in context.components:
        parent_id = component.get("id")
        children = component.get("children")
        if not isinstance(parent_id, str) or not isinstance(children, list):
            continue
        for child_id in children:
            if isinstance(child_id, str):
                result.setdefault(child_id, set()).add(parent_id)
    return result


def iter_reachable_components(
    context: Any,
    start_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    root_id = start_id or context.root_id
    if not isinstance(root_id, str):
        return
    visited: set[str] = set()
    stack = [root_id]
    while stack:
        component_id = stack.pop()
        if component_id in visited:
            continue
        visited.add(component_id)
        component = context.components_by_id.get(component_id)
        if not isinstance(component, dict):
            continue
        yield component
        children = component.get("children")
        if isinstance(children, list):
            child_ids = [child for child in children if isinstance(child, str)]
            stack.extend(reversed(child_ids))


def contains_action(
    component: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> bool:
    component_id = component.get("id")
    if not isinstance(component_id, str):
        return False
    visited: set[str] = set()
    stack = [component_id]
    while stack:
        current_id = stack.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        current = by_id.get(current_id)
        if not isinstance(current, dict):
            continue
        handlers = current.get("onClick")
        if isinstance(handlers, list) and handlers:
            return True
        children = current.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, str))
    return False


def is_emoji(value: Any) -> bool:
    return isinstance(value, str) and any(
        start <= ord(char) <= end for char in value for start, end in EMOJI_RANGES
    )


def static_color(value: Any) -> str | None:
    if not isinstance(value, str) or value.strip().startswith(("{{", "${", "$theme(")):
        return None
    return value.strip() if HEX_RE.fullmatch(value.strip()) else None


def alpha(value: str) -> int:
    raw = value[1:]
    return int(raw[:2], 16) if len(raw) == 8 else 0xFF


def all_colors(component: dict[str, Any]) -> Iterator[tuple[str, Any]]:
    styles = component.get("styles")
    if not isinstance(styles, dict):
        return
    for key in COLOR_KEYS:
        if key in styles:
            yield key, styles[key]
    for gradient_key in ("linearGradient", "radialGradient"):
        gradient = styles.get(gradient_key)
        if not isinstance(gradient, dict) or not isinstance(gradient.get("colors"), list):
            continue
        for index, stop in enumerate(gradient["colors"]):
            if isinstance(stop, (list, tuple)) and stop:
                yield f"{gradient_key}/colors/{index}/0", stop[0]


def display_text(value: Any, data_model: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        if not is_wrapped_expression(stripped):
            return stripped
        resolved = static_expression_value(stripped, data_model)
        is_scalar = isinstance(resolved, (str, int, float)) and not isinstance(resolved, bool)
        return str(resolved) if is_scalar else None
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str):
            found, resolved = read_pointer(data_model, path)
            valid_scalar = isinstance(resolved, (str, int, float)) and not isinstance(
                resolved,
                bool,
            )
            if found and valid_scalar:
                return str(resolved)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def add(
    reporter: Any,
    code: str,
    pointer: str,
    message: str,
    actual: Any = None,
    expected: Any = None,
) -> None:
    severity = "warning" if code in QUALITY_WARNING_CODES else "error"
    reporter.add(
        severity,
        code,
        "quality",
        "genui",
        line=2,
        json_pointer=pointer,
        actual=actual,
        expected=expected,
        message=message,
        source="aesthetic-quality",
    )
