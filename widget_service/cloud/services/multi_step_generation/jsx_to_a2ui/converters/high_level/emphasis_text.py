from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from ..base.text import text
from ..common import palette


def convert_emphasis_text(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    main = text(ctx, "emphasis_main", ctx.prop(node, "mainText"), styles={"height": 27, "fontSize": 20, "fontWeight": 700, "fontColor": palette(ctx).primary, "maxLines": 1})
    secondary = None
    if node.props.get("secondaryText") is not None:
        secondary = text(ctx, "emphasis_secondary", ctx.prop(node, "secondaryText"), styles={"height": 16, "fontSize": 12, "fontWeight": 400, "fontColor": palette(ctx).secondary, "maxLines": 1})
    return column(ctx, "emphasis_text", [main, secondary], styles={"alignItems": "start"})
