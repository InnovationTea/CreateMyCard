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
    if isinstance(raw_value, bool) or not isinstance(raw_value, str | int | float):
        errors.append("NumericRatio.value must be a string or number")
    unit = node.props.get("unit")
    if unit is not None and not isinstance(unit, str):
        errors.append("NumericRatio.unit must be a string")
    return errors


def convert_numeric_ratio(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_numeric_ratio_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    value_binding = ctx.bound_data(node.props, "value")
    resolved_value = node.props.get("value")
    if value_binding is not None:
        resolved_value = value_binding.value_for_prop(node.tag, "value")
    # JSX receives the display-formatted binding, not necessarily the raw number.
    # Decide both the numeric derivation and the default unit from that same value.
    numeric_display = (
        isinstance(resolved_value, int | float) and not isinstance(resolved_value, bool)
    )
    unit = node.props.get("unit")
    if unit is None:
        unit = "%" if numeric_display else ""
    icon_image = image(
        ctx,
        "ratio_icon_image",
        node.props["icon"],
        styles={"width": 12, "height": 12, "objectFit": "contain"},
        fill_color=palette(ctx).primary,
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
    display_value = ctx.prop(node, "value")
    if value_binding is not None and numeric_display:
        derived_root, _ = ctx.register_derived_display(value_binding)
        display_value = {"path": f"{derived_root}/visiblePercentage"}
    value = text(ctx, "ratio_value", display_value, styles=text_styles)
    value_children = [value]
    if unit:
        unit_styles = dict(text_styles)
        visibility = ctx.unit_visibility(value_binding)
        if visibility is not None:
            unit_styles["visibility"] = visibility
        value_children.append(text(ctx, "ratio_unit", unit, styles=unit_styles))
    value_group = row(
        ctx,
        "ratio_text",
        value_children,
        gap=0,
        styles={"height": 16, "alignItems": "center", "flexShrink": 1},
    )
    return row(
        ctx,
        "numeric_ratio",
        [icon, value_group],
        gap=4,
        styles={"height": 16, "alignItems": "center"},
    )
