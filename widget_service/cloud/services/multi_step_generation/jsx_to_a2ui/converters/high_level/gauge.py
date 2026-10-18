from __future__ import annotations

import math

from ...catalog.bindings import data_model_expression_reference
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, stack
from ..base.progress import progress
from ..base.text import text
from ..common import palette


def _number(value: object, where: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{where} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{where} must be numeric") from exc
    if not math.isfinite(result):
        raise ValidationError(f"{where} must be finite")
    return result


def collect_gauge_conversion_errors(node: JSXElement) -> list[str]:
    errors: list[str] = []
    try:
        minimum = _number(node.props.get("min", 1), "<Gauge> min")
        maximum = _number(node.props.get("max", 100), "<Gauge> max")
        _number(node.props.get("value"), "<Gauge> value")
        if maximum <= minimum:
            errors.append("<Gauge> max must be greater than min")
    except ValidationError as exc:
        errors.append(str(exc))
    return errors


def convert_gauge(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_gauge_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    minimum = _number(node.props.get("min", 1), "<Gauge> min")
    maximum = _number(node.props.get("max", 100), "<Gauge> max")
    literal_value = _number(node.props["value"], "<Gauge> value")
    bounded = max(minimum, min(maximum, literal_value))
    binding = ctx.bound_data(node.props, "value")
    display_value = ctx.prop(node, "value")
    if binding is None:
        progress_value: object = (bounded - minimum) / (maximum - minimum) * 100
    else:
        reference = data_model_expression_reference(binding.path)
        progress_value = (
            "{{ Math.max(0, Math.min(100, "
            f"(({reference} - {minimum}) / {maximum - minimum}) * 100)) }}"
        )

    dark = node.props.get("mode", "light") == "dark"
    current = palette(ctx)
    bar_color = "#FFFFFFFF" if dark else current.action_text
    track_color = "#33FFFFFF" if dark else f"#33{current.action_text[-6:]}"
    value_color = "#FFFFFFFF" if dark else current.primary
    label_color = "#99FFFFFF" if dark else current.secondary

    ring = progress(
        ctx,
        "gauge_progress",
        progress_value,
        100,
        kind="ring",
        color=bar_color,
        stroke_width=10,
        styles={
            "width": 94,
            "height": 94,
            "backgroundColor": track_color,
            "flexShrink": 0,
        },
    )
    copy = column(
        ctx,
        "gauge_copy",
        [
            text(
                ctx,
                "gauge_value",
                display_value,
                styles={
                    "width": "matchParent",
                    "constraintSize": {"minWidth": 0},
                    "height": 24,
                    "fontSize": 20,
                    "fontWeight": 700,
                    "fontColor": value_color,
                    "textAlign": "center",
                    "maxLines": 1,
                },
            ),
            text(
                ctx,
                "gauge_label",
                node.props["label"],
                styles={
                    "width": "matchParent",
                    "constraintSize": {"minWidth": 0},
                    "height": 16,
                    "fontSize": 10,
                    "fontWeight": 400,
                    "fontColor": label_color,
                    "textAlign": "center",
                    "maxLines": 1,
                    "textOverflow": "ellipsis",
                },
            ),
        ],
        gap=0,
        styles={
            "width": 94,
            "height": 80,
            "padding": {"top": 4, "right": 14, "bottom": 8, "left": 14},
            "alignItems": "center",
            "justifyContent": "center",
        },
    )
    return stack(
        ctx,
        "gauge",
        [ring, copy],
        align="top",
        styles={"width": 94, "height": 80, "clip": True, "flexShrink": 0},
    )
