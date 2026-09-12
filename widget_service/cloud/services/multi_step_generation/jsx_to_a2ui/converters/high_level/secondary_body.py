from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from ..common import palette
from .helpers import segmented_text


def convert_secondary_body(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    # A2UI fallback keeps deterministic pairs and natural Text wrapping.
    # JSX measures fields at runtime; this converter cannot observe rendered
    # widths after a native data update. Do not constrain JSX to this grouping.
    if "body" in node.props:
        raise ValidationError(
            "SecondaryBody.body is no longer supported; use items={[{value: ...}]} and item-level dataIds.value"
        )
    items = node.props.get("items")
    if isinstance(items, list) and len(items) > 2:
        rows = []
        for index in range(0, len(items), 2):
            row_node = JSXElement(
                tag=node.tag,
                props={**node.props, "items": items[index:index + 2]},
                children=[],
            )
            rows.append(
                segmented_text(
                    row_node,
                    ctx,
                    hint="secondary_body_row",
                    font_size=12,
                    line_height=16,
                    font_color=palette(ctx).secondary,
                )
            )
        return column(
            ctx,
            "secondary_body",
            rows,
            gap=2,
            styles={
                "width": "matchParent",
                "height": "wrapContent",
                "flexShrink": 0,
                "constraintSize": {"minWidth": 0, "minHeight": 16 * len(rows) + 2 * (len(rows) - 1)},
                "alignItems": "start",
            },
        )
    return segmented_text(
        node,
        ctx,
        hint="secondary_body",
        font_size=14,
        line_height=19,
        font_color=palette(ctx).secondary,
    )
