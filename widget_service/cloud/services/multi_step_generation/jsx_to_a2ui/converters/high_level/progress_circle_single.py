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


def convert_progress_circle_single(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    raw_value = node.props["value"]
    value = ctx.prop(node, "value")
    value_binding = ctx.bound_data(node.props, "value")
    numeric_value = normalize_percentage_value(raw_value)
    if numeric_value is None:
        raise ValidationError(
            "<ProgressCircleSingle> value must be a number or numeric percentage "
            "such as 68 or '68%'"
        )
    derived_root = None
    if value_binding is not None and isinstance(value_binding.value, str):
        derived_root, plan = ctx.register_derived_display(value_binding)
        if normalize_percentage_value(plan.raw) is None:
            raise ValidationError(
                "<ProgressCircleSingle> bound value must be a number or numeric "
                "percentage such as 68 or '68%'"
            )
        progress_value = {"path": f"{derived_root}/progressValue"}
    elif value_binding is not None:
        progress_value = value
        derived_root, _ = ctx.register_derived_display(value_binding)
    else:
        progress_value = numeric_value
    current_palette = palette(ctx)
    card_mode = node.props.get("appearance") == "card"
    ring = ring_with_icon(
        ctx,
        value=progress_value,
        icon=node.props["icon"],
        size=52,
        stroke_width=6,
        icon_size=20,
        hint="single_ring",
        aria_label=node.props.get("ariaLabel"),
        bar_color=(
            current_palette.progress_bar
            if card_mode
            else node.props.get("barColor") or "#FF64BB5C"
        ),
        track_color=current_palette.progress_track if card_mode else node.props.get("trackColor"),
        icon_color=current_palette.progress_icon if card_mode else None,
    )
    has_secondary = node.props.get("secondaryLabel") is not None
    value_styles = {
        "height": 16 if has_secondary else 18,
        "fontSize": 10 if has_secondary else 12,
        "fontWeight": 400 if has_secondary else 500,
        "fontColor": current_palette.secondary,
        "flexShrink": 0,
    }
    data_ids = node.props.get("dataIds")
    value_is_bound = isinstance(data_ids, dict) and "value" in data_ids
    if "displayValue" in node.props:
        value_text = text(
            ctx,
            "ring_display_value",
            ctx.prop(node, "displayValue"),
            styles=value_styles,
        )
    elif is_formatted_percentage(raw_value):
        value_text = text(
            ctx,
            "ring_display_value",
            value if value_is_bound else raw_value.strip(),
            styles=value_styles,
        )
    elif value_is_bound:
        display_number = value
        if derived_root is not None:
            display_number = {"path": f"{derived_root}/visiblePercentage"}
        value_text = row(
            ctx,
            "ring_display_value",
            [
                text(ctx, "ring_display_number", display_number, styles=value_styles),
                text(ctx, "ring_display_unit", "%", styles=value_styles),
            ],
            gap=0,
            styles={"height": value_styles["height"], "alignItems": "center", "flexShrink": 0},
        )
    else:
        value_text = text(
            ctx,
            "ring_display_value",
            f"{math.trunc(raw_value)}%",
            styles=value_styles,
        )
    label = text(
        ctx,
        "ring_label",
        ctx.prop(node, "label"),
        styles={
            "height": 20,
            "fontSize": 14,
            "fontWeight": 700,
            "fontColor": current_palette.primary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
        },
    )
    secondary = None
    if has_secondary:
        secondary = text(
            ctx,
            "ring_secondary_label",
            ctx.prop(node, "secondaryLabel"),
            styles={
                "height": 16,
                "fontSize": 10,
                "fontWeight": 400,
                "fontColor": current_palette.secondary,
                "maxLines": 1,
                "textOverflow": "ellipsis",
            },
        )
    labels = column(
        ctx,
        "ring_stat",
        [label, value_text, secondary],
        gap=0,
        styles={
            "height": 52,
            "alignItems": "start",
            "justifyContent": "center",
            "flexShrink": 0,
        },
    )
    props = (
        {"accessibility": accessibility(node.props.get("ariaLabel"))}
        if node.props.get("ariaLabel")
        else {}
    )
    return row(
        ctx,
        "progress_circle_single",
        [ring, labels],
        gap=8,
        props=props,
        styles={"alignItems": "center", "flexShrink": 0},
    )
