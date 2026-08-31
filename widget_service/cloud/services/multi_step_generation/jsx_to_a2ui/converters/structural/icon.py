from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..common import accessibility


def convert_icon(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    src = node.props.get("src") or node.props.get("name")
    size = node.props.get("size")
    styles = {"objectFit": "contain"}
    if size is not None:
        styles.update({"width": size, "height": size})
    return image(ctx, "icon", src, styles=styles, accessibility=None if node.props.get("decorative", True) else accessibility(node.props.get("alt")))


def convert_app_icon(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    return image(ctx, "app_icon", node.props.get("src") or node.props.get("name"), styles={"width": 20, "height": 20, "borderRadius": 4, "objectFit": "cover", "flexShrink": 0}, accessibility=accessibility(node.props.get("alt")))


def convert_weather_icon(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    return image(ctx, "weather_icon", node.props.get("src") or node.props.get("name"), styles={"width": 20, "height": 20, "borderRadius": 4, "objectFit": "contain", "flexShrink": 0}, accessibility=accessibility(node.props.get("alt")))
