from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row, stack
from ..base.text import text
from ..common import palette


def convert_event_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    current_palette = palette(ctx)
    has_location = node.props.get("location") is not None
    event_height = 54 if has_location else 38
    # Do not size the rail from its parent. On the real A2UI runtime a
    # matchParent rail plus a weighted Divider consumes every bit of height
    # offered by an outer flexible slot, making the timeline extend to the
    # bottom of the card. The JSX rail only spans EventCard's own text box:
    # 5 top padding + 8 dot + 5 gap + the remaining 20/36 vp.
    line_height = event_height - 18
    dot = stack(ctx, "event_dot", [], styles={"width": 8, "height": 8, "borderRadius": 4, "borderWidth": 1.5, "borderColor": "#FFFF2F23", "flexShrink": 0})
    line = ctx.make("Divider", "event_line", styles={"vertical": True, "strokeWidth": 1, "color": "#FFD8D8D8", "height": line_height})
    rail = column(
        ctx,
        "event_rail",
        [dot, line],
        gap=5,
        styles={
            "width": 8,
            "padding": {"top": 5},
            "alignItems": "center",
            "flexShrink": 0,
        },
    )
    bounded_text = {"width": "matchParent", "constraintSize": {"minWidth": 0}}
    title = text(ctx, "event_title", ctx.prop(node, "title"), styles={**bounded_text, "fontSize": 14, "fontWeight": 500, "fontColor": current_palette.primary, "maxLines": 2, "textOverflow": "ellipsis", "flexShrink": 0})
    time = text(ctx, "event_time", ctx.prop(node, "time"), styles={**bounded_text, "height": 16, "fontSize": 12, "fontWeight": 400, "fontColor": current_palette.secondary, "maxLines": 1, "textOverflow": "ellipsis"})
    location = None
    if has_location:
        location = text(ctx, "event_location", ctx.prop(node, "location"), styles={**bounded_text, "height": 16, "fontSize": 12, "fontWeight": 400, "fontColor": current_palette.secondary, "maxLines": 1, "textOverflow": "ellipsis"})
    details = column(ctx, "event_details", [time, location], gap=0, styles={"width": "matchParent", "flexShrink": 0, "constraintSize": {"minWidth": 0}, "alignItems": "start"})
    body = column(ctx, "event_content", [title, details], gap=4, styles={"layoutWeight": 1, "flexShrink": 1, "constraintSize": {"minWidth": 0}, "alignItems": "start"})
    constraint_size = {
        "minWidth": 0,
        "minHeight": event_height,
    }
    if ctx.card_size != "2x4":
        constraint_size["maxWidth"] = 116
    return row(
        ctx,
        "event_card",
        [rail, body],
        gap=7,
        styles={
            "width": "matchParent",
            "flexShrink": 1,
            "constraintSize": constraint_size,
            "alignItems": "top",
        },
    )
