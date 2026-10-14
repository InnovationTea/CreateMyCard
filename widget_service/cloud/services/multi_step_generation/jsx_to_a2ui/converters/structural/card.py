from __future__ import annotations

import re

from ...catalog.appearances import get_appearance, resolve_appearance_name
from ...catalog.card_sizes import resolve_card_size
from ...catalog.tokens import normalize_color
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import adapt_flex_children, column, row
from .flex_stack import _minimum_node_height


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


def _number(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _vertical_edges(value: object) -> float:
    number = _number(value)
    if number is not None:
        return number * 2
    if not isinstance(value, dict):
        return 0
    return (_number(value.get("top")) or 0) + (_number(value.get("bottom")) or 0)


def _is_event_group(node: A2UINode) -> bool:
    return (
        node.component == "Column"
        and len(node.children) == 2
        and node.id.endswith("_event_card")
        and all(child.id.endswith(f"_event_{index}_item") for index, child in enumerate(node.children))
    )


def _resolved_outer_height(node: A2UINode, offered_height: float | None) -> float:
    explicit = _number(node.styles.get("height"))
    if explicit is not None:
        return explicit
    if node.styles.get("height") == "matchParent" and offered_height is not None:
        return offered_height
    if (_number(node.styles.get("layoutWeight")) or 0) > 0 and offered_height is not None:
        return offered_height
    return _minimum_node_height(node)


def _event_height_upper_bound(node: A2UINode, width: float | None) -> float:
    """Reserve both title lines unless a literal conservatively fits one line.

    Bindings can change after compilation. Never use their initial sample or
    a Text minHeight as proof that the native title will remain one line.
    """
    minimum = _minimum_node_height(node)
    pending = list(node.children)
    while pending:
        child = pending.pop()
        pending.extend(child.children)
        if not child.id.endswith("_title") or child.styles.get("maxLines") != 2:
            continue
        maximum = (node.styles.get("constraintSize") or {}).get("maxWidth")
        if isinstance(maximum, (int, float)):
            width = min(width, maximum) if width is not None else maximum
        content = child.props.get("content")
        font = _number(child.styles.get("fontSize")) or 14
        literal_fits = (
            isinstance(content, str) and "{{" not in content and "\n" not in content
            and width is not None and len(content.encode("utf-16-le")) / 2 * font <= width - 15
        )
        return minimum if literal_fits else minimum + 18
    return minimum


def _resolve_event_group_gaps(
    node: A2UINode, offered_height: float | None, offered_width: float | None = None,
) -> None:
    """Use 8vp only with a conservative capacity proof; otherwise keep 4vp."""
    # A natural-height event group receives the containing slot's capacity as
    # `offered_height`. Use that capacity only to select the 8vp/4vp gap; the
    # emitted group itself remains wrapContent and can still be parent-aligned.
    outer_height = (
        offered_height
        if _is_event_group(node) and offered_height is not None
        else _resolved_outer_height(node, offered_height)
    )
    content_height = max(0, outer_height - _vertical_edges(node.styles.get("padding")))
    width = _number(node.styles.get("width"))
    if width is None:
        width = offered_width
    content_width = _content_extent(width, node.styles.get("padding", 0), "width")

    if _is_event_group(node):
        item_height = sum(_event_height_upper_bound(child, content_width) for child in node.children)
        node.props["itemMargin"] = 8 if content_height >= item_height + 8 else 4

    if not node.children:
        return
    if node.component != "Column":
        for child in node.children:
            # A Row's width belongs to all columns, not to each child. Unknown
            # allocations must not be treated as proof of single-line titles.
            child_width = content_width if node.component == "Stack" else None
            _resolve_event_group_gaps(child, content_height, child_width)
        return

    gap = _number(node.props.get("itemMargin")) or 0
    available_for_children = max(0, content_height - gap * max(0, len(node.children) - 1))
    weights = [max(0, _number(child.styles.get("layoutWeight")) or 0) for child in node.children]
    fixed_height = sum(
        _resolved_outer_height(child, None)
        for child, weight in zip(node.children, weights, strict=True)
        if weight == 0
    )
    total_weight = sum(weights)
    flexible_height = max(0, available_for_children - fixed_height)
    for child, weight in zip(node.children, weights, strict=True):
        if weight > 0 and total_weight > 0:
            allocated = max(_minimum_node_height(child), flexible_height * weight / total_weight)
        else:
            allocated = _resolved_outer_height(child, None)
            # A natural-height EventCard does not consume the parent's free
            # space, but that space is still relevant when choosing its 8vp
            # or 4vp internal gap. Only lend it unclaimed slack: weighted
            # siblings retain ownership of flexible space.
            if _is_event_group(child) and total_weight == 0:
                allocated += flexible_height
        _resolve_event_group_gaps(child, allocated, content_width)


def convert_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    explicit_appearance = node.props.get("appearance")
    semantic_size, width, height = resolve_card_size(node.props.get("size"))
    appearance_name = resolve_appearance_name(explicit_appearance, semantic_size)
    appearance = get_appearance(appearance_name)
    padding = node.props.get("padding", 12)
    inner = ctx.with_appearance(appearance_name).with_card_surface(
        semantic_size,
        _content_extent(width, padding, "width"),
        _content_extent(height, padding, "height"),
    )
    source_children = node.child_elements()
    direction = str(node.props.get("direction") or "column")
    is_row = direction == "row"
    stretch = node.props.get("align") in {None, "stretch"}
    children = [
        inner.for_flex_child(child, is_row=is_row, stretch=stretch).convert(child)
        for child in source_children
    ]
    if not children:
        raise ValidationError("<Card> must contain at least one component child")
    background = node.props.get("background")
    adapt_flex_children(
        source_children,
        children,
        is_row=is_row,
        fill_table_height=True,
    )
    if stretch:
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
    result = layout(
        inner,
        "root",
        children,
        gap=node.props.get("gap", 0),
        styles=resolved_styles,
    )
    _resolve_event_group_gaps(result, float(height))
    return result
