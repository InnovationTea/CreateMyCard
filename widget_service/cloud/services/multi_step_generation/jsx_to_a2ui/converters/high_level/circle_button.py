from __future__ import annotations

from ...catalog.tokens import BUTTON_COLOR_ALIASES, light_color, solid_color
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import stack
from ..common import accessibility, palette


def _colors(node: JSXElement, ctx: ConversionContext) -> tuple[str, str]:
    if node.props.get("appearance") == "card":
        current = palette(ctx)
        return current.circle_background, current.circle_icon
    name = BUTTON_COLOR_ALIASES.get(str(node.props.get("color") or "primary"), "blue")
    if node.props.get("variant", "emphasis") == "normal":
        return light_color(name), solid_color(name)
    foreground = "#FF000000" if name == "yellow" else "#FFFFFFFF"
    return solid_color(name), foreground


def convert_circle_button(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    background, foreground = _colors(node, ctx)
    icon = image(
        ctx,
        "circle_button_icon",
        node.props["icon"],
        styles={"width": 20, "height": 20, "objectFit": "contain"},
        fill_color=foreground,
    )
    event = ctx.action_props(node)
    props = {"accessibility": accessibility(node.props["ariaLabel"]), **event}
    return stack(
        ctx,
        "circle_button",
        [icon],
        align="center",
        props=props,
        styles={"width": 36, "height": 36, "borderRadius": 18, "backgroundColor": background, "flexShrink": 0},
    )
