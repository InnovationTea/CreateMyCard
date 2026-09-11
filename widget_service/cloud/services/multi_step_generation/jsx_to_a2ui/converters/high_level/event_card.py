from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, stack
from ..base.text import text
from ..common import palette


def convert_event_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    current_palette = palette(ctx)
    has_location = node.props.get("location") is not None
    event_height = 54 if has_location else 38
    # Measure the text first in an overlay Stack. Its matchParent decoration
    # is measured against that local box, not a flexible Row's offered height.
    # Do not use a weighted Divider: the rail must never size the event.
    dot = stack(
        ctx,
        "event_dot",
        [],
        styles={
            "width": 8,
            "height": 8,
            "borderRadius": 4,
            "borderWidth": 1.5,
            "borderColor": "#FFFF2F23",
            "flexShrink": 0,
            "margin": {"top": 5},
        },
    )
    line = ctx.make(
        "Divider",
        "event_line",
        styles={
            "vertical": True,
            "strokeWidth": 1,
            "color": "#FFD8D8D8",
            "height": "matchParent",
            "layoutWeight": 0,
        },
    )
    rail = stack(
        ctx,
        "event_rail",
        [line],
        align="top",
        styles={
            "width": 8,
            "height": "matchParent",
            "padding": {"top": 18},
            "flexShrink": 0,
        },
    )
    bounded_text = {"width": "matchParent", "constraintSize": {"minWidth": 0}}
    title = text(
        ctx,
        "event_title",
        ctx.prop(node, "title"),
        styles={
            **bounded_text,
            "constraintSize": {"minWidth": 0, "minHeight": 18},
            "fontSize": 14,
            "fontWeight": 500,
            "fontColor": current_palette.primary,
            "maxLines": 2,
            "textOverflow": "ellipsis",
            "flexShrink": 0,
        },
    )
    time = text(
        ctx,
        "event_time",
        ctx.prop(node, "time"),
        styles={
            **bounded_text,
            "height": 16,
            "fontSize": 12,
            "fontWeight": 400,
            "fontColor": current_palette.secondary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
        },
    )
    location = None
    if has_location:
        location = text(
            ctx,
            "event_location",
            ctx.prop(node, "location"),
            styles={
                **bounded_text,
                "height": 16,
                "fontSize": 12,
                "fontWeight": 400,
                "fontColor": current_palette.secondary,
                "maxLines": 1,
                "textOverflow": "ellipsis",
            },
        )
    details = column(
        ctx,
        "event_details",
        [time, location],
        gap=0,
        styles={
            "width": "matchParent",
            "flexShrink": 0,
            "constraintSize": {"minWidth": 0},
            "alignItems": "start",
        },
    )
    body = column(
        ctx,
        "event_content",
        [title, details],
        gap=4,
        styles={
            # A percentage width participates in Stack's initial measurement;
            # matchParent would defer this height-defining child as well.
            "width": "100%",
            "padding": {"left": 15},
            "layoutWeight": 0,
            "flexShrink": 0,
            "constraintSize": {"minWidth": 0},
            "alignItems": "start",
        },
    )
    constraint_size = {
        "minWidth": 0,
        "minHeight": event_height,
    }
    if ctx.card_size != "2x4":
        constraint_size["maxWidth"] = 116
    return stack(
        ctx,
        "event_card",
        [body, rail, dot],
        align="topStart",
        styles={
            "width": "matchParent",
            "height": "wrapContent",
            "flexShrink": 1,
            "constraintSize": constraint_size,
        },
    )
