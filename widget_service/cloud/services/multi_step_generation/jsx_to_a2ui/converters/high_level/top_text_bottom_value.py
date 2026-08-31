from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row, stack
from ..base.text import text
from ..common import palette


def collect_top_text_bottom_value_conversion_errors(node: JSXElement) -> list[str]:
    items = node.props.get("items")
    if not isinstance(items, list) or len(items) < 2:
        return ["<TopTextBottomValue> items must contain at least two groups"]
    errors: list[str] = []
    for index, item in enumerate(items):
        where = f"<TopTextBottomValue> items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        if not isinstance(item.get("label"), str) or not item["label"].strip():
            errors.append(f"{where}.label must be a non-empty string")
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            errors.append(f"{where}.value must be a string or number")
        if not isinstance(item.get("unit"), str) or not item["unit"].strip():
            errors.append(f"{where}.unit must be a non-empty string")
    return errors


def convert_top_text_bottom_value(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_top_text_bottom_value_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props["items"]
    assert isinstance(items, list)
    item_nodes: list[A2UINode] = []
    for index, item in enumerate(items):
        assert isinstance(item, dict)
        item_nodes.append(
            column(
                ctx,
                "top_text_bottom_value_item",
                [
                    text(
                        ctx,
                        "top_text_bottom_value_label",
                        item["label"],
                        styles={
                            "height": 18,
                            "fontSize": 12,
                            "fontWeight": 500,
                            "fontColor": palette(ctx).primary,
                            "textAlign": "center",
                            "maxLines": 1,
                            "flexShrink": 0,
                        },
                    ),
                    text(
                        ctx,
                        "top_text_bottom_value_number",
                        ctx.item_prop(node.tag, item, index, "value"),
                        styles={
                            "height": 32,
                            "fontSize": 24,
                            "fontWeight": 700,
                            "fontColor": palette(ctx).primary,
                            "textAlign": "center",
                            "maxLines": 1,
                            "flexShrink": 0,
                        },
                    ),
                    text(
                        ctx,
                        "top_text_bottom_value_unit",
                        item["unit"],
                        styles={
                            "height": 18,
                            "fontSize": 12,
                            "fontWeight": 400,
                            "fontColor": palette(ctx).secondary,
                            "textAlign": "center",
                            "maxLines": 1,
                            "flexShrink": 0,
                        },
                    ),
                ],
                gap=0,
                styles={
                    "height": 68,
                    "alignItems": "center",
                    "justifyContent": "center",
                    "flexShrink": 0,
                },
            )
        )
    content = row(
        ctx,
        "top_text_bottom_value_content",
        item_nodes,
        gap=0,
        styles={
            "width": "matchParent",
            "height": 68,
            "alignItems": "center",
            "justifyContent": "spaceAround",
        },
    )
    divider_color = "#33FFFFFF" if palette(ctx).primary == "#FFFFFFFF" else "#33000000"
    item_count = len(items)
    dividers = []
    for index in range(1, item_count):
        left = round(296 * index / item_count, 4)
        dividers.append(
            column(
                ctx,
                "top_text_bottom_value_divider",
                [],
                styles={
                    "width": 1,
                    "height": 62,
                    "margin": {"left": left, "top": 3},
                    "backgroundColor": divider_color,
                    "flexShrink": 0,
                },
            )
        )
    return stack(
        ctx,
        "top_text_bottom_value",
        [content, *dividers],
        align="topStart",
        styles={"width": "matchParent", "height": 68},
    )
