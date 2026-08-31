from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.text import text
from ..common import palette
from .helpers import segmented_text


def convert_summary(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    if "items" in node.props:
        if "content" in node.props:
            raise ValidationError("Summary.content and Summary.items are mutually exclusive")
        return segmented_text(
            node,
            ctx,
            hint="summary",
            font_size=10,
            line_height=14,
        )
    styles = {
        "fontSize": 10,
        "fontWeight": 400,
        "fontColor": palette(ctx).secondary,
        "textAlign": "start",
        "flexShrink": 1,
        "constraintSize": {"minWidth": 0},
    }
    return text(ctx, "summary", ctx.prop(node, "content"), styles=styles)
