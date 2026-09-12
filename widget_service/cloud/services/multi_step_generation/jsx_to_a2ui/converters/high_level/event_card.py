from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row, stack
from ..base.text import text
from ..common import palette


def convert_event_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    current_palette = palette(ctx)
    has_location = node.props.get("location") is not None
    compact = node.props.get("density") == "compact"
    event_height = 32 if compact else 50 if has_location else 34
    rail_top = 17 if compact else 18
    # The rail has zero layout height. Paint a bounded line through its
    # unclipped box and clip it at the text-sized event boundary. This avoids
    # a wrapContent/matchParent height cycle without fixing the event height
    # or estimating whether a dynamic title occupies one or two lines.
    max_event_height = event_height if compact else event_height + 18
    dot = stack(
        ctx,
        "event_dot",
        [],
        styles={
            "width": 8,
            "height": 8,
            "borderRadius": 4,
            "borderWidth": 1.5,
            "borderColor": current_palette.primary,
            "flexShrink": 0,
            "margin": {"top": 4 if compact else 5},
        },
    )
    line = ctx.make(
        "Divider",
        "event_line",
        styles={
            "vertical": True,
            "strokeWidth": 1,
            "color": current_palette.secondary,
            "height": max_event_height - rail_top,
            "flexShrink": 0,
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
            "height": 0,
            "margin": {"top": rail_top},
            "clip": False,
            "flexShrink": 0,
        },
    )
    bounded_text = {"width": "matchParent", "constraintSize": {"minWidth": 0}}
    title_styles = {
        **bounded_text,
        "constraintSize": {"minWidth": 0, "minHeight": 16 if compact else 18},
        "fontSize": 12 if compact else 14,
        "fontWeight": 500,
        "fontColor": current_palette.primary,
        "maxLines": 1 if compact else 2,
        "textOverflow": "ellipsis",
        "flexShrink": 0,
    }
    if compact:
        title_styles["height"] = 16
    title = text(
        ctx,
        "event_title",
        ctx.prop(node, "title"),
        styles=title_styles,
    )
    time_styles = {
        "height": 14 if compact else 16,
        "fontSize": 10 if compact else 12,
        "fontWeight": 400,
        "fontColor": current_palette.secondary,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "flexShrink": 0,
        "constraintSize": {"minWidth": 0},
    }
    if not compact:
        time_styles["width"] = "matchParent"
    time = text(
        ctx,
        "event_time",
        ctx.prop(node, "time"),
        styles=time_styles,
    )
    location = None
    if has_location:
        location_styles = {
            "height": 14 if compact else 16,
            "fontSize": 10 if compact else 12,
            "fontWeight": 400,
            "fontColor": current_palette.secondary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "constraintSize": {"minWidth": 0},
        }
        if compact:
            location_styles["layoutWeight"] = 1
        else:
            location_styles["width"] = "matchParent"
        location = text(
            ctx,
            "event_location",
            ctx.prop(node, "location"),
            styles=location_styles,
        )
    if compact:
        detail_children = [time]
        if location is not None:
            detail_children.extend(
                [
                    text(
                        ctx,
                        "event_meta_separator",
                        "｜",
                        styles={
                            "height": 14,
                            "fontSize": 10,
                            "fontWeight": 400,
                            "fontColor": current_palette.secondary,
                            "flexShrink": 0,
                        },
                    ),
                    location,
                ]
            )
        details = row(
            ctx,
            "event_details",
            detail_children,
            gap=4,
            styles={
                "width": "matchParent",
                "height": 14,
                "flexShrink": 0,
                "constraintSize": {"minWidth": 0},
                "alignItems": "center",
            },
        )
    else:
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
        gap=2 if compact else 0,
        styles={
            # The text subtree is the only height-defining overlay child.
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
            "clip": True,
            "flexShrink": 1,
            "constraintSize": constraint_size,
        },
    )
