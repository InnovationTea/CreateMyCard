from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import row
from ..base.text import text
from ..common import palette


def collect_card_button_conversion_errors(node: JSXElement) -> list[str]:
    text_value = node.props.get("text")
    if not isinstance(text_value, str) or not text_value.strip():
        return ["<CardButton> text must be a non-empty string"]
    return []


def _colors(ctx: ConversionContext) -> tuple[str, str]:
    current = palette(ctx)
    if current.name.endswith("-gradient"):
        return "#33FFFFFF", "#FFFFFFFF"
    return current.action_background, current.action_text


def _with_opacity(color: str, opacity: float) -> str:
    alpha = round(int(color[1:3], 16) * opacity)
    return f"#{alpha:02X}{color[3:]}"


def _content(
    node: JSXElement,
    ctx: ConversionContext,
    foreground: str,
) -> list[A2UINode]:
    children = [
        text(
            ctx,
            "card_button_label",
            node.props["text"],
            styles={
                "height": 20,
                "fontSize": 14,
                "fontWeight": 700,
                "fontColor": foreground,
                "textAlign": "start",
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "flexShrink": 1,
                "constraintSize": {"minWidth": 0},
            },
        )
    ]
    icon = node.props.get("icon")
    if icon:
        children.append(
            image(
                ctx,
                "card_button_icon",
                icon,
                styles={"width": 24, "height": 24, "objectFit": "contain", "flexShrink": 0},
                fill_color=foreground,
            )
        )
    return children


def convert_card_button(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_card_button_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    background, foreground = _colors(ctx)
    if node.props.get("disabled"):
        background = _with_opacity(background, 0.4)
        foreground = _with_opacity(foreground, 0.4)
    props = ctx.action_props(node)
    styles = {
        "width": "matchParent",
        "height": "matchParent",
        "padding": {"top": 7, "right": 12, "bottom": 7, "left": 12},
        "borderRadius": 16,
        "backgroundColor": background,
        "alignItems": "center",
        "justifyContent": "spaceBetween",
        "constraintSize": {"minWidth": 0, "minHeight": 48, "maxHeight": 64},
    }
    return row(
        ctx,
        "card_button",
        _content(node, ctx, foreground),
        gap=8,
        props=props,
        styles=styles,
    )
