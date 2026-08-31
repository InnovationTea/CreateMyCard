from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from ..base.text import text
from ..common import palette


def convert_data_display(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    label = text(
        ctx,
        "data_display_label",
        node.props["label"],
        styles={
            "height": 18,
            "fontSize": 12,
            "fontWeight": 500,
            "fontColor": palette(ctx).secondary,
            "textAlign": "center",
            "maxLines": 1,
        },
    )
    value = text(
        ctx,
        "data_display_value",
        ctx.prop(node, "value"),
        styles={
            "height": 60,
            "fontSize": 56,
            "fontWeight": 700,
            "fontColor": palette(ctx).primary,
            "textAlign": "center",
            "maxLines": 1,
        },
    )
    supporting = text(
        ctx,
        "data_display_supporting",
        node.props["supportingText"],
        styles={
            "height": 20,
            "fontSize": 14,
            "fontWeight": 400,
            "fontColor": palette(ctx).secondary,
            "textAlign": "center",
            "maxLines": 1,
        },
    )
    return column(
        ctx,
        "data_display",
        [label, value, supporting],
        gap=8,
        styles={"alignItems": "center"},
    )
