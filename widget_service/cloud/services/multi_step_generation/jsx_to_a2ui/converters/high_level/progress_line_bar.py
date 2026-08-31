from __future__ import annotations

import math

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...catalog.tokens import normalize_color
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from ..base.progress import progress
from ..common import palette
from .emphasized_data import convert_emphasized_data


_DYNAMIC_DISPLAY_ERROR = (
    "ProgressLine2 with dynamic currentValue/totalValue must provide "
    "an explicit bound value or items display; only a bound currentValue "
    "with a static totalValue={100} can use the implicit percentage display"
)


def collect_progress_line2_conversion_errors(node: JSXElement) -> list[str]:
    if node.props.get("value") is not None or node.props.get("items") is not None:
        return []
    data_ids = node.props.get("dataIds")
    current_id = data_ids.get("currentValue") if isinstance(data_ids, dict) else None
    total_id = data_ids.get("totalValue") if isinstance(data_ids, dict) else None
    if current_id is None and total_id is None:
        return []
    total = node.props.get("totalValue", 100)
    if current_id is not None and total_id is None and total == 100:
        return []
    return [_DYNAMIC_DISPLAY_ERROR]


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
        bar_color = palette(ctx).primary if raw_bar_color == "var(--card-primary)" else normalize_color(raw_bar_color)
    bar = progress(ctx, "progress_bar", ctx.prop(node, "currentValue"), ctx.prop(node, "totalValue"), kind="linear", color=bar_color, stroke_width=8, styles={"width": "matchParent", "height": 8, "backgroundColor": track_color})
    display_node = node
    if node.props.get("value") is None and node.props.get("items") is None:
        current = node.props.get("currentValue", 0)
        total = node.props.get("totalValue", 100)
        data_ids = node.props.get("dataIds")
        current_id = data_ids.get("currentValue") if isinstance(data_ids, dict) else None
        total_id = data_ids.get("totalValue") if isinstance(data_ids, dict) else None
        if current_id is not None or total_id is not None:
            if current_id is not None and total_id is None and total == 100:
                display_node = JSXElement(
                    "EmphasizedData",
                    {
                        "value": current,
                        "unit": "%",
                        "dataIds": {"value": current_id},
                    },
                )
            else:  # Final invariant guard; preflight normally catches this.
                raise ValidationError(_DYNAMIC_DISPLAY_ERROR)
        else:
            percent = 0
            if isinstance(current, (int, float)) and not isinstance(current, bool) and isinstance(total, (int, float)) and not isinstance(total, bool) and total > 0:
                percent = math.trunc(max(0, min(100, current / total * 100)))
            display_node = JSXElement("EmphasizedData", {"value": percent, "unit": "%"})
    # ProgressLine2 gives its emphasized value a 47vp line box.  Keep the
    # ordinary EmphasizedData geometry (38vp) unchanged elsewhere.
    data = convert_emphasized_data(
        display_node,
        ctx,
        value_height=47,
        unit_height=None,
        unit_bottom_inset=8,
    )
    return column(ctx, "progress_value_above", [data, bar], gap=8, styles={"width": "matchParent", "alignItems": "start"})
