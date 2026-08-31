from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.text import text


PRIMARY = "#FF000000"
SECONDARY = "#99000000"


def _emphasized_value(value: object, ctx: ConversionContext) -> A2UINode:
    value_node = text(
        ctx,
        "secondary_card_value",
        value,
        styles={
            "height": 46,
            "fontSize": 38,
            "fontWeight": 700,
            "fontColor": PRIMARY,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "flexShrink": 0,
        },
    )
    return row(ctx, "secondary_card_emphasized_data", [value_node], gap=2, styles={"alignItems": "bottom"})


def convert_secondary_body_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    lines = node.props["lines"]
    if not isinstance(lines, list):
        raise ValidationError("SecondaryBodyCard.lines must be an array")
    if any(isinstance(line, (dict, list)) for line in lines):
        raise ValidationError("SecondaryBodyCard.lines entries must be scalar text values")

    title = text(
        ctx,
        "secondary_card_title",
        node.props["title"],
        styles={
            "width": "matchParent",
            "height": 18,
            "fontSize": 12,
            "fontWeight": 400,
            "fontColor": SECONDARY,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "textAlign": "start",
        },
    )
    value = _emphasized_value(node.props["value"], ctx) if node.props.get("value") is not None else None
    top = column(
        ctx,
        "secondary_card_top",
        [title, value],
        gap=2,
        styles={"width": "matchParent", "alignItems": "start"},
    )
    line_nodes = [
        text(
            ctx,
            "secondary_card_line",
            line,
            styles={
                "width": "matchParent",
                "height": 19,
                "fontSize": 14,
                "fontWeight": 400,
                "fontColor": SECONDARY,
                "textAlign": "start",
                "maxLines": 1,
                "textOverflow": "ellipsis",
            },
        )
        for line in lines
    ]
    bottom = column(
        ctx,
        "secondary_card_bottom",
        line_nodes,
        gap=2,
        styles={"width": "matchParent", "alignItems": "start"},
    )
    return column(
        ctx,
        "secondary_body_card",
        [top, bottom],
        gap=0,
        styles={
            "width": 140,
            "height": 140,
            "padding": 12,
            "borderRadius": 24,
            "clip": True,
            "backgroundColor": "#FFFAFAFA",
            "borderWidth": 1,
            "borderColor": "#1A000000",
            "alignItems": "start",
            "justifyContent": "spaceBetween",
        },
    )
