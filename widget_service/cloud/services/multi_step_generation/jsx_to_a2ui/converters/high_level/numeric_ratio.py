from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import row, stack
from ..base.text import text
from ..common import palette


def collect_numeric_ratio_conversion_errors(node: JSXElement) -> list[str]:
    errors: list[str] = []
    raw_value = node.props.get("value")
    if isinstance(raw_value, bool) or not isinstance(raw_value, (str, int, float)):
        errors.append("NumericRatio.value must be a string or number")
    unit = node.props.get("unit")
    if unit is not None and not isinstance(unit, str):
        errors.append("NumericRatio.unit must be a string")
    return errors


def convert_numeric_ratio(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_numeric_ratio_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    raw_value = node.props.get("value")
    unit = node.props.get("unit")
    if unit is None:
        unit = "%" if isinstance(raw_value, (int, float)) else ""
    icon_image = image(
        ctx,
        "ratio_icon_image",
        node.props["icon"],
        styles={"width": 12, "height": 12, "objectFit": "contain"},
        fill_color=palette(ctx).secondary,
    )
    icon = stack(
        ctx,
        "ratio_icon",
        [icon_image],
        styles={"width": 16, "height": 16, "alignContent": "center", "flexShrink": 0},
    )
    text_styles = {
        "height": 16,
        "fontSize": 10,
        "fontWeight": 400,
        "fontColor": palette(ctx).secondary,
        "maxLines": 1,
        "flexShrink": 0,
    }
    value = text(ctx, "ratio_value", ctx.prop(node, "value"), styles=text_styles)
    value_children = [value]
    if unit:
        value_children.append(text(ctx, "ratio_unit", unit, styles=text_styles))
    value_group = row(
        ctx,
        "ratio_text",
        value_children,
        gap=0,
        styles={"height": 16, "alignItems": "center", "flexShrink": 1},
    )
    return row(ctx, "numeric_ratio", [icon, value_group], gap=4, styles={"height": 16, "alignItems": "center"})
