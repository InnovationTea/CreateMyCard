from __future__ import annotations

from ...catalog.tokens import solid_color
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.progress import progress
from ..base.text import text
from ..common import palette


def convert_progress_line_labels_below(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    bar = progress(
        ctx,
        "progress_bar",
        ctx.prop(node, "currentValue"),
        ctx.prop(node, "totalValue"),
        kind="linear",
        color=solid_color(str(node.props.get("color") or "blue")),
        stroke_width=8,
        styles={"width": 116, "height": 8},
    )
    left = text(
        ctx,
        "progress_left",
        ctx.prop(node, "leftLabel"),
        styles={
            "height": 13,
            "fontSize": 10,
            "fontWeight": 400,
            "fontColor": palette(ctx).primary,
            "textAlign": "start",
            "maxLines": 1,
            "layoutWeight": 1,
        },
    )
    right = text(
        ctx,
        "progress_right",
        ctx.prop(node, "rightLabel"),
        styles={
            "height": 13,
            "fontSize": 10,
            "fontWeight": 400,
            "fontColor": palette(ctx).primary,
            "textAlign": "end",
            "maxLines": 1,
            "layoutWeight": 1,
        },
    )
    labels = row(
        ctx,
        "progress_labels",
        [left, right],
        styles={"width": 116, "justifyContent": "spaceBetween", "alignItems": "top"},
    )
    return column(ctx, "progress_labels_below", [bar, labels], gap=4, styles={"width": 116, "alignItems": "start"})
