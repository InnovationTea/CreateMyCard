from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, stack
from ..base.text import text
from ..common import palette


def convert_single_line_title(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    title = text(
        ctx,
        "title_text",
        ctx.prop(node, "title"),
        styles={
            "width": "matchParent",
            "height": 18,
            "flexShrink": 0,
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
            "width": "matchParent",
            "height": 18,
            "alignItems": "start",
        },
    )
    return stack(
        ctx,
        "single_line_title",
        [content],
        align="topStart",
        styles={"width": "matchParent", "height": 18},
    )
