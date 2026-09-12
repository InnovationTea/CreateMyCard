from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, stack
from ..base.text import text
from ..common import palette


def convert_double_line_title(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    main = text(
        ctx,
        "title_main",
        ctx.prop(node, "title"),
        styles={
            "width": "matchParent",
            "height": 18,
            "flexShrink": 0,
            "fontSize": 12,
            "fontWeight": 700,
            "fontColor": palette(ctx).primary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
        },
    )
    secondary = text(
        ctx,
        "title_secondary",
        ctx.prop(node, "secondaryInfo"),
        styles={
            "width": "matchParent",
            "constraintSize": {"minHeight": 18},
            "flexShrink": 0,
            "fontSize": 12,
            "fontWeight": 500,
            "fontColor": palette(ctx).secondary,
            "maxLines": 2,
            "textOverflow": "ellipsis",
        },
    )
    content = column(
        ctx,
        "double_title_text",
        [main, secondary],
        gap=4,
        styles={
            "width": "matchParent",
            "constraintSize": {"minHeight": 40},
            "flexShrink": 0,
            "alignItems": "start",
        },
    )
    return stack(
        ctx,
        "double_line_title",
        [content],
        align="topStart",
        styles={"width": "matchParent", "constraintSize": {"minHeight": 40}},
    )
