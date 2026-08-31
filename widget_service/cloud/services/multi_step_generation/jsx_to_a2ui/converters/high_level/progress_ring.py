from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from .helpers import ring_with_icon


def convert_progress_ring(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    size = int(node.props.get("size", 44))
    icon_size_name = node.props.get("iconSize", "sm")
    icon_size = 24 if icon_size_name in {"md", "single"} else 16
    return ring_with_icon(ctx, value=node.props["value"], icon=node.props["icon"], size=size, stroke_width=int(node.props.get("strokeWidth", 6)), icon_size=icon_size, hint="progress_ring", bar_color=node.props.get("barColor") or "#FF64BB5C")
