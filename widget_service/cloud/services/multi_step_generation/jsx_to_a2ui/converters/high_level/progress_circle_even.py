from __future__ import annotations

import math

from ...catalog.bindings import is_formatted_percentage
from ...catalog.display_values import normalize_percentage_value
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.text import text
from ..common import accessibility, palette
from .helpers import ring_with_icon


def convert_progress_circle_even(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    size_name = node.props.get("size", "sm")
    diameter = 96 if size_name == "md" else 44
    stroke = 6
    icon_size = 20
    current_palette = palette(ctx)
    card_mode = node.props.get("appearance") == "card"
    external_binding = ctx.bound_data(node.props, "externalText")
    external_value = ctx.prop(node, "externalText")
    derived_root = None
    raw_external_value = node.props.get("externalText", node.props.get("value"))
    if external_binding is not None:
        derived_root, plan = ctx.register_derived_display(external_binding)
        if normalize_percentage_value(plan.raw) is None:
            raise ValidationError(
                "<ProgressCircle> bound externalText must be a number or numeric percentage such as 68 or '68%'"
            )
        progress_value = {"path": f"{derived_root}/progressValue"}
    else:
        progress_value = normalize_percentage_value(raw_external_value)
        if progress_value is None:
            raise ValidationError(
                "<ProgressCircle> externalText must be a number or numeric percentage such as 68 or '68%'"
            )
    ring = ring_with_icon(
        ctx,
        value=progress_value,
        icon=node.props["icon"],
        size=diameter,
        stroke_width=stroke,
        icon_size=icon_size,
        hint="even_ring",
        aria_label=node.props.get("ariaLabel"),
        bar_color=current_palette.progress_bar if card_mode else node.props.get("barColor") or "#FF64BB5C",
        track_color=current_palette.progress_track if card_mode else node.props.get("trackColor"),
        icon_color=current_palette.progress_icon if card_mode else None,
    )
    text_styles = {
        "height": 14,
        "fontSize": 10,
        "fontWeight": 500,
        "fontColor": palette(ctx).primary,
        "textAlign": "center",
        "maxLines": 1,
        "flexShrink": 0,
    }
    if is_formatted_percentage(raw_external_value):
        external = text(ctx, "ring_external_text", external_value, styles=text_styles)
    elif external_binding is not None:
        external = row(
            ctx,
            "ring_external_text",
            [
                text(
                    ctx,
                    "ring_external_number",
                    {"path": f"{derived_root}/visiblePercentage"},
                    styles=text_styles,
                ),
                text(ctx, "ring_external_unit", "%", styles=text_styles),
            ],
            gap=0,
            styles={"height": 14, "alignItems": "center", "flexShrink": 0},
        )
    else:
        external = text(
            ctx,
            "ring_external_text",
            f"{math.trunc(progress_value)}%",
            styles=text_styles,
        )
    props = {"accessibility": accessibility(node.props.get("ariaLabel"))} if node.props.get("ariaLabel") else {}
    return column(
        ctx,
        "progress_circle_even",
        [ring, external],
        gap=2,
        props=props,
        styles={"alignItems": "center", "flexShrink": 0},
    )
