from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import column, row
from ..base.text import text
from ..common import palette


def convert_single_line_title(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    icon_src = node.props.get("icon")
    has_icon = isinstance(icon_src, str) and bool(icon_src.strip())
    title = text(
        ctx,
        "title_text",
        ctx.prop(node, "title"),
        styles={
            "width": "wrapContent",
            "height": 16,
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
            "height": 16,
            "alignItems": "start",
            "layoutWeight": 0,
            "flexShrink": 1,
            "constraintSize": {"minWidth": 0, "maxWidth": "100%"},
        },
    )
    children = [content]
    root_styles = {
        # Keep the whole chain intrinsic: a weighted/fill child can make
        # a native wrapContent title consume the space before a badge.
        "width": "wrapContent",
        "height": 16,
        "flexShrink": 1,
        "alignItems": "top",
        "constraintSize": {"minWidth": 0, "maxWidth": "100%"},
    }
    if has_icon:
        content.styles.update({"layoutWeight": 1, "width": "wrapContent"})
        title.styles["width"] = "matchParent"
        icon = image(
            ctx,
            "title_icon",
            icon_src,
            styles={
                "width": 20,
                "height": 20,
                "objectFit": "contain",
                "flexShrink": 0,
            },
            fill_color=node.props.get("fillColor"),
        )
        children.append(icon)
        root_styles.update(
            {
                "width": "matchParent",
                "height": 20,
                "justifyContent": "spaceBetween",
                "alignItems": "center",
            }
        )
    return row(
        ctx,
        "single_line_title",
        children,
        styles=root_styles,
    )
