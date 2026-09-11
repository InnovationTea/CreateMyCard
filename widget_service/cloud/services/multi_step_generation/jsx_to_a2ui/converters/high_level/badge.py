from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import row
from ..base.text import text
from ..common import palette


def convert_badge(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    current = palette(ctx)
    label = text(
        ctx,
        "badge_value",
        ctx.prop(node, "value"),
        styles={"fontSize": 10, "fontWeight": 500, "fontColor": current.primary, "maxLines": 1},
    )
    return row(
        ctx,
        "badge",
        [label],
        styles={
            # Badge has its own content width, even inside a stretching Column.
            "width": "wrapContent",
            "constraintSize": {"maxWidth": "100%"},
            "flexShrink": 0,
            "height": 16,
            "padding": {"left": 6, "right": 6},
            "borderRadius": 8,
            "backgroundColor": current.progress_track,
            "alignItems": "center",
            "justifyContent": "center",
        },
    )
