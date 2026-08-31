from __future__ import annotations

from ...catalog.tokens import light_color, solid_color
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import row
from ..base.text import text


def convert_badge(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    color = str(node.props.get("color") or "blue")
    label = text(ctx, "badge_value", ctx.prop(node, "value"), styles={"fontSize": 10, "fontWeight": 500, "fontColor": solid_color(color), "maxLines": 1})
    return row(ctx, "badge", [label], styles={"height": 16, "padding": {"left": 6, "right": 6}, "borderRadius": 8, "backgroundColor": light_color(color), "alignItems": "center", "justifyContent": "center"})
