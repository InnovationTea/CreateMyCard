from __future__ import annotations

import re

from ...catalog.appearances import get_appearance
from ...catalog.card_sizes import resolve_card_size
from ...catalog.tokens import normalize_color
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, orient_child_flex_basis, row


def _align(value: object, *, is_row: bool) -> str | None:
    if value is None or value == "stretch":
        return None
    mapping = {
        "flex-start": "top" if is_row else "start",
        "start": "top" if is_row else "start",
        "flex-end": "bottom" if is_row else "end",
        "end": "bottom" if is_row else "end",
        "center": "center",
    }
    return mapping.get(str(value), str(value))


def _justify(value: object) -> str | None:
    if value is None:
        return None
    return {
        "flex-start": "start",
        "flex-end": "end",
        "space-between": "spaceBetween",
        "space-around": "spaceAround",
        "space-evenly": "spaceEvenly",
        "between": "spaceBetween",
    }.get(str(value), str(value))


def _content_extent(extent: object, padding: object, axis: str) -> int | float | None:
    if not isinstance(extent, int | float) or isinstance(extent, bool):
        return None
    if isinstance(padding, int | float) and not isinstance(padding, bool):
        return max(0, extent - 2 * padding)
    if isinstance(padding, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)px\s*", padding)
        if match:
            return max(0, extent - 2 * float(match.group(1)))
    if isinstance(padding, dict):
        start, end = ("left", "right") if axis == "width" else ("top", "bottom")
        before = padding.get(start, 0)
        after = padding.get(end, 0)
        before_is_number = isinstance(before, int | float) and not isinstance(before, bool)
        after_is_number = isinstance(after, int | float) and not isinstance(after, bool)
        if before_is_number and after_is_number:
            return max(0, extent - before - after)
    return None


def convert_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    explicit_appearance = node.props.get("appearance")
    appearance_name = str(explicit_appearance or "blue-soft")
    appearance = get_appearance(appearance_name)
    semantic_size, width, height = resolve_card_size(node.props.get("size"))
    padding = node.props.get("padding", 12)
    inner = ctx.with_appearance(appearance_name).with_card_surface(
        semantic_size,
        _content_extent(width, padding, "width"),
        _content_extent(height, padding, "height"),
    )
    source_children = node.child_elements()
    children = [inner.convert(child) for child in source_children]
    if not children:
        raise ValidationError("<Card> must contain at least one component child")
    background = node.props.get("background")
    direction = str(node.props.get("direction") or "column")
    is_row = direction == "row"
    orient_child_flex_basis(source_children, children, is_row=is_row)
    if node.props.get("align") in {None, "stretch"}:
        for child in children:
            child.styles.setdefault("height" if is_row else "width", "matchParent")
    styles = {
        "width": width,
        "height": height,
        "padding": padding,
        "borderRadius": 20 if node.props.get("appearance") else 24,
        "clip": True,
        "backgroundColor": normalize_color(background) if background else appearance.background,
        "linearGradient": appearance.gradient if explicit_appearance and not background else None,
        "shadow": appearance.shadow if explicit_appearance else None,
        "alignItems": _align(node.props.get("align"), is_row=is_row),
        "justifyContent": _justify(node.props.get("justify")),
    }
    resolved_styles: dict[str, object] = {}
    for key, value in styles.items():
        if value is not None:
            resolved_styles[key] = value
    layout = row if is_row else column
    return layout(
        inner,
        "root",
        children,
        gap=node.props.get("gap", 0),
        styles=resolved_styles,
    )
