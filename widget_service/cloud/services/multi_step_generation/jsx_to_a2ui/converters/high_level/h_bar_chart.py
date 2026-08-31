from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.progress import progress
from ..base.text import text
from ..common import palette


def _alpha(color: str, alpha: str) -> str:
    if len(color) != 9 or not color.startswith("#"):
        raise ValidationError(f"cannot apply alpha to invalid A2UI color {color!r}")
    return f"#{alpha}{color[-6:]}"


def collect_h_bar_chart_conversion_errors(node: JSXElement) -> list[str]:
    items = node.props.get("items")
    if not isinstance(items, list) or len(items) < 2:
        return ["<H_BarChart> items must contain at least two bars"]
    errors: list[str] = []
    for index, item in enumerate(items):
        where = f"<H_BarChart> items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        if not isinstance(item.get("label"), str) or not item["label"].strip():
            errors.append(f"{where}.label must be a non-empty string")
        value_unit = item.get("valueUnit")
        if isinstance(value_unit, bool) or not isinstance(value_unit, (str, int, float)):
            errors.append(f"{where}.valueUnit must be a string or number")
        percent = item.get("percent")
        if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not 0 <= percent <= 100:
            errors.append(f"{where}.percent must be a number from 0 to 100")
    return errors


def convert_h_bar_chart(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_h_bar_chart_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props.get("items")
    assert isinstance(items, list)
    mode = node.props.get("mode", "light")
    current = palette(ctx)
    dark = mode == "dark"
    text_color = "#80FFFFFF" if dark else _alpha(current.action_text, "99")
    track_color = "#33FFFFFF" if dark else _alpha(current.action_text, "33")
    bar_color = "#FFFFFFFF" if dark else current.action_text

    bars: list[A2UINode] = []
    for index, item in enumerate(items):
        where = f"<H_BarChart> items[{index}]"
        assert isinstance(item, dict)
        label = item.get("label")
        value_unit = item.get("valueUnit")
        percent = item.get("percent")
        assert isinstance(label, str)
        assert isinstance(percent, (int, float)) and not isinstance(percent, bool)

        label_node = text(
            ctx,
            "bar_chart_label",
            label,
            styles={
                "height": 20,
                "fontSize": 14,
                "fontWeight": 700,
                "fontColor": text_color,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "layoutWeight": 1,
                "flexShrink": 1,
                "constraintSize": {"minWidth": 0},
            },
        )
        value_node = text(
            ctx,
            "bar_chart_value_unit",
            ctx.item_prop(node.tag, item, index, "valueUnit"),
            styles={
                "height": 20,
                "fontSize": 14,
                "fontWeight": 700,
                "fontColor": text_color,
                "textAlign": "end",
                "maxLines": 1,
                "flexShrink": 0,
            },
        )
        meta = row(
            ctx,
            "bar_chart_meta",
            [label_node, value_node],
            gap=8,
            styles={
                "width": "matchParent",
                "height": 20,
                "alignItems": "bottom",
                "justifyContent": "spaceBetween",
            },
        )
        track = progress(
            ctx,
            "bar_chart_track",
            percent,
            100,
            kind="linear",
            color=bar_color,
            stroke_width=6,
            styles={
                "width": "matchParent",
                "height": 6,
                "borderRadius": 3,
                "backgroundColor": track_color,
                "flexShrink": 0,
            },
        )
        bars.append(
            column(
                ctx,
                "bar_chart_item",
                [meta, track],
                gap=4,
                styles={"width": "matchParent", "height": 30, "alignItems": "start"},
            )
        )

    return column(
        ctx,
        "bar_chart",
        bars,
        gap=11,
        styles={"width": "matchParent", "alignItems": "start"},
    )
