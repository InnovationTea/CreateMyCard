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
            "width": "matchParent",
            "height": 18,
            "fontSize": 12,
            "fontWeight": 500,
            "fontColor": palette(ctx).secondary,
            "textAlign": "center",
            "maxLines": 1,
            "constraintSize": {"minWidth": 0},
        },
    )
    value = text(
        ctx,
        "data_display_value",
        ctx.prop(node, "value"),
        styles={
            "width": "matchParent",
            "height": 60,
            "fontSize": 56,
            "fontWeight": 700,
            "fontColor": palette(ctx).primary,
            "textAlign": "center",
            "maxLines": 1,
            "constraintSize": {"minWidth": 0},
        },
    )
    supporting = text(
        ctx,
        "data_display_supporting",
        node.props["supportingText"],
        styles={
            "width": "matchParent",
            "constraintSize": {"minWidth": 0, "minHeight": 20},
            "fontSize": 14,
            "fontWeight": 400,
            "fontColor": palette(ctx).secondary,
            "textAlign": "center",
            "flexShrink": 1,
        },
    )
    return column(
        ctx,
        "data_display",
        [label, value, supporting],
        gap=8,
        styles={
            "width": "matchParent",
            "constraintSize": {"minWidth": 0},
            "alignItems": "center",
            "flexShrink": 1,
        },
    )
