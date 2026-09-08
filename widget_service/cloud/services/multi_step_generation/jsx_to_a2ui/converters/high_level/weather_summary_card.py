from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import column, row
from ..base.text import text
from ..common import accessibility


PRIMARY = "#FF000000"
SECONDARY = "#99000000"


def convert_weather_summary_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    title = text(
        ctx,
        "weather_card_city",
        node.props["city"],
        styles={
            "layoutWeight": 1,
            "flexShrink": 1,
            "height": 18,
            "fontSize": 12,
            "fontWeight": 400,
            "fontColor": SECONDARY,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "textAlign": "start",
        },
    )
    icon = image(
        ctx,
        "weather_card_icon",
        node.props["icon"],
        styles={
            "width": 20,
            "height": 20,
            "borderRadius": 4,
            "objectFit": "contain",
            "flexShrink": 0,
        },
        accessibility=accessibility(node.props.get("ariaLabel")),
    )
    title_row = row(
        ctx,
        "weather_card_title_row",
        [title, icon],
        gap=4,
        styles={
            "width": 116,
            "constraintSize": {"minHeight": 20},
            "alignItems": "top",
            "justifyContent": "spaceBetween",
        },
    )
    temperature = text(
        ctx,
        "weather_card_temperature",
        node.props["temperature"],
        styles={
            "height": 46,
            "fontSize": 38,
            "fontWeight": 700,
            "fontColor": PRIMARY,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "flexShrink": 0,
        },
    )
    reading = row(
        ctx,
        "weather_card_reading",
        [temperature],
        gap=8,
        styles={"margin": {"top": 4}, "alignItems": "center"},
    )
    top = column(
        ctx,
        "weather_card_top",
        [title_row, reading],
        gap=0,
        styles={"width": "matchParent", "alignItems": "start"},
    )
    meta_line = text(
        ctx,
        "weather_card_meta",
        f'{node.props["condition"]} ｜ {node.props["airQuality"]}',
        styles={
            "height": 18,
            "fontSize": 12,
            "fontWeight": 400,
            "fontColor": SECONDARY,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "textAlign": "start",
        },
    )
    range_line = text(
        ctx,
        "weather_card_range",
        f'{node.props["high"]}/{node.props["low"]}',
        styles={
            "height": 18,
            "fontSize": 12,
            "fontWeight": 400,
            "fontColor": SECONDARY,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "textAlign": "start",
        },
    )
    meta = column(
        ctx,
        "weather_card_meta_group",
        [meta_line, range_line],
        gap=0,
        styles={"width": "matchParent", "alignItems": "start"},
    )
    return column(
        ctx,
        "weather_summary_card",
        [top, meta],
        gap=0,
        styles={
            "width": 140,
            "height": 140,
            "padding": 12,
            "borderRadius": 24,
            "clip": True,
            "backgroundColor": "#FFFFFFFF",
            "linearGradient": {
                "angle": 180,
                "colors": [["#1A46B1E3", 0], ["#00FFFFFF", 1]],
                "repeating": False,
            },
            "borderWidth": 1,
            "borderColor": "#0F000000",
            "alignItems": "start",
            "justifyContent": "spaceBetween",
        },
    )
