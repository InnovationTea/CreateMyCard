from __future__ import annotations

from ...catalog.tokens import BUTTON_COLOR_ALIASES, light_color, solid_color
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import row
from ..base.text import text
from ..common import color_with_opacity, palette


def _colors(node: JSXElement, ctx: ConversionContext) -> tuple[str, str, str]:
    if node.props.get("appearance") == "card":
        current = palette(ctx)
        return current.action_background, current.action_text, current.action_icon
    name = BUTTON_COLOR_ALIASES.get(str(node.props.get("color") or "primary"), "blue")
    if node.props.get("variant", "emphasis") == "normal":
        return light_color(name), solid_color(name), solid_color(name)
    foreground = "#FF000000" if name == "yellow" else "#FFFFFFFF"
    return solid_color(name), foreground, foreground


def convert_pill_button(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    background, foreground, icon_color = _colors(node, ctx)
    if node.props.get("disabled"):
        background = color_with_opacity(background, 0.4)
        foreground = color_with_opacity(foreground, 0.4)
        icon_color = color_with_opacity(icon_color, 0.4)
    common_styles = {
        "width": 120 if ctx.inside_backplate else 136,
        "height": 36,
        "borderRadius": 30,
        "backgroundColor": background,
        "flexShrink": 0,
    }
    event = ctx.action_props(node)
    if not node.props.get("icon"):
        props = {
            "label": str(node.props["label"]),
            "enabled": not bool(node.props.get("disabled", False)),
            **event,
        }
        return ctx.make(
            "Button",
            "pill_button",
            props=props,
            styles={**common_styles, "fontSize": 14, "fontWeight": 500, "fontColor": foreground},
        )
    icon = image(
        ctx,
        "pill_icon",
        node.props["icon"],
        styles={"width": 20, "height": 20, "objectFit": "contain", "flexShrink": 0},
        fill_color=icon_color,
    )
    label = text(
        ctx,
        "pill_label",
        node.props["label"],
        styles={
            "fontSize": 14,
            "fontWeight": 500,
            "fontColor": foreground,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "flexShrink": 1,
        },
    )
    return row(
        ctx,
        "pill_button",
        [icon, label],
        gap=8,
        props=event,
        styles={**common_styles, "alignItems": "center", "justifyContent": "center"},
    )
