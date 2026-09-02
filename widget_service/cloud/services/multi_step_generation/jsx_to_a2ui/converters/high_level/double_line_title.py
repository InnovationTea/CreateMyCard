from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import column, row, stack
from ..base.text import text
from ..common import accessibility, palette


def convert_double_line_title(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    has_icon = bool(node.props.get("icon"))
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
            "padding": {"right": 24} if has_icon else None,
            "flexShrink": 0,
            "alignItems": "start",
        },
    )
    icon = None
    if node.props.get("icon"):
        icon = image(
            ctx,
            "title_icon",
            node.props["icon"],
            styles={
                "width": 20,
                "height": 20,
                "borderRadius": 4,
                "objectFit": node.props.get("iconFit", "contain"),
                "flexShrink": 0,
            },
            fill_color="#FFFFFFFF" if node.props.get("invertIcon") else None,
            accessibility=accessibility(node.props.get("iconAlt")),
        )
    icon_layer = (
        row(
            ctx,
            "title_icon_layer",
            [icon],
            styles={"width": "matchParent", "height": 20, "justifyContent": "end", "alignItems": "top"},
        )
        if icon
        else None
    )
    return stack(
        ctx,
        "double_line_title",
        [content, icon_layer],
        align="topStart",
        styles={"width": "matchParent", "constraintSize": {"minHeight": 40}},
    )
