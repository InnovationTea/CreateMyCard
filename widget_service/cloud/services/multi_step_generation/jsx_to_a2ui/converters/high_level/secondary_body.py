from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.text import text
from ..common import palette
from .helpers import segmented_text


def convert_secondary_body(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    if "items" in node.props:
        if "body" in node.props:
            raise ValidationError("SecondaryBody.body and SecondaryBody.items are mutually exclusive")
        return segmented_text(
            node,
            ctx,
            hint="secondary_body",
            font_size=14,
            line_height=19,
            font_color=palette(ctx).primary,
        )
    return text(ctx, "secondary_body", ctx.prop(node, "body"), styles={
        "fontSize": 14,
        "fontWeight": 400,
        "fontColor": palette(ctx).primary,
        "textAlign": "start",
        "flexShrink": 1,
        "constraintSize": {"minWidth": 0},
    })
