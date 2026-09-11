from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.text import text
from ..common import palette


def convert_single_line_title(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    title = text(
        ctx,
        "title_text",
        ctx.prop(node, "title"),
        styles={
            "width": "wrapContent",
            "height": 18,
            "flexShrink": 1,
            "constraintSize": {"minWidth": 0, "maxWidth": "100%"},
            "fontSize": 12,
            "fontWeight": 400,
            "fontColor": palette(ctx).secondary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "textAlign": "start",
        },
    )
    content = column(
        ctx,
        "single_title_text",
        [title],
        styles={
            "width": "wrapContent",
            "height": 18,
            "alignItems": "start",
            "layoutWeight": 0,
            "flexShrink": 1,
            "constraintSize": {"minWidth": 0, "maxWidth": "100%"},
        },
    )
    return row(
        ctx,
        "single_line_title",
        [content],
        styles={
            # Keep the whole chain intrinsic: a weighted/fill child can make
            # a native wrapContent title consume the space before a badge.
            "width": "wrapContent",
            "height": 18,
            "flexShrink": 1,
            "alignItems": "top",
            "constraintSize": {"minWidth": 0, "maxWidth": "100%"},
        },
    )
