from __future__ import annotations

import math

from ...catalog.bindings import data_model_expression_reference
from ...catalog.tokens import normalize_color
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from ..base.progress import progress
from ..common import palette
from .emphasized_data import convert_emphasized_data


def collect_progress_line2_conversion_errors(node: JSXElement) -> list[str]:
    return []


def _expression_atom(value: object) -> str:
    if isinstance(value, dict) and set(value) == {"path"}:
        return data_model_expression_reference(value["path"])
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(
            "ProgressLine2 implicit display requires numeric currentValue and totalValue"
        )
    return repr(value)


def _dynamic_percentage_expression(current: object, total: object) -> str:
    current_atom = _expression_atom(current)
    total_atom = _expression_atom(total)
    ratio = f"{current_atom} / {total_atom} * 100"
    # The expression catalog only provides arithmetic, comparison and ternary
    # operators. For a non-negative value, x - x % 1 is Math.trunc(x).
    return (
        "{{ "
        f"{total_atom} <= 0 ? 0 : "
        f"{ratio} < 0 ? 0 : "
        f"{ratio} > 100 ? 100 : "
        f"{ratio} - {ratio} % 1"
        " }}"
    )


def convert_progress_line_bar(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_progress_line2_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    dark = node.props.get("mode", "light") == "dark"
    track_color = "#66FFFFFF" if dark else "#1A000000"
    raw_bar_color = node.props.get("barColor")
    if raw_bar_color is None:
        bar_color = "#FFFFFFFF" if dark else "#FF0A59F7"
    else:
        bar_color = (
            palette(ctx).primary
            if raw_bar_color == "var(--card-primary)"
            else normalize_color(raw_bar_color)
        )
    bar = progress(
        ctx,
        "progress_bar",
        ctx.prop(node, "currentValue"),
        ctx.prop(node, "totalValue"),
        kind="linear",
        color=bar_color,
        stroke_width=8,
        styles={"width": "matchParent", "height": 8, "backgroundColor": track_color},
    )
    display_node = node
    if node.props.get("value") is None and node.props.get("items") is None:
        current = node.props.get("currentValue", 0)
        total = node.props.get("totalValue", 100)
        data_ids = node.props.get("dataIds")
        current_id = data_ids.get("currentValue") if isinstance(data_ids, dict) else None
        total_id = data_ids.get("totalValue") if isinstance(data_ids, dict) else None
        if current_id is not None or total_id is not None:
            if current_id is not None and total_id is None and total == 100:
                current_binding = ctx.bound_data(node.props, "currentValue")
                assert current_binding is not None
                derived_root, _ = ctx.register_derived_display(current_binding)
                display_node = JSXElement(
                    "EmphasizedData",
                    {
                        "value": {"path": f"{derived_root}/visiblePercentage"},
                        "unit": "%",
                    },
                )
            else:
                current_value = ctx.prop(node, "currentValue", 0)
                total_value = ctx.prop(node, "totalValue", 100)
                display_node = JSXElement(
                    "EmphasizedData",
                    {
                        "value": _dynamic_percentage_expression(
                            current_value,
                            total_value,
                        ),
                        "unit": "%",
                    },
                )
        else:
            percent = 0
            current_is_number = isinstance(current, int | float) and not isinstance(current, bool)
            total_is_positive_number = (
                isinstance(total, int | float)
                and not isinstance(total, bool)
                and total > 0
            )
            if current_is_number and total_is_positive_number:
                percent = math.trunc(max(0, min(100, current / total * 100)))
            display_node = JSXElement("EmphasizedData", {"value": percent, "unit": "%"})
    # ProgressLine2 keeps the ordinary 38vp value line box and tightens the
    # unit to its 12vp font box. A2UI has no baseline alignment mode, so the
    # supported bottom alignment is the closest deterministic equivalent.
    data = convert_emphasized_data(
        display_node,
        ctx,
        value_height=38,
        unit_height=12,
        unit_bottom_inset=0,
    )
    return column(
        ctx,
        "progress_value_above",
        [data, bar],
        gap=8,
        styles={"width": "matchParent", "alignItems": "start"},
    )
