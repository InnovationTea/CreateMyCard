from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.text import text
from ..common import palette


def collect_table_text_conversion_errors(node: JSXElement) -> list[str]:
    items = node.props.get("items")
    if not isinstance(items, list) or len(items) < 2:
        return ["<TableText> items must contain at least two rows"]
    errors: list[str] = []
    for index, item in enumerate(items):
        where = f"<TableText> items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        if not isinstance(item.get("label"), str) or not item["label"].strip():
            errors.append(f"{where}.label must be a non-empty string")
        parameter = item.get("parameter")
        if isinstance(parameter, bool) or not isinstance(parameter, (str, int, float)):
            errors.append(f"{where}.parameter must be a string or number")
    return errors


def convert_table_text(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_table_text_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props.get("items")
    assert isinstance(items, list)

    rows: list[A2UINode] = []
    for index, item in enumerate(items):
        assert isinstance(item, dict)
        label = item.get("label")
        assert isinstance(label, str)

        label_node = text(
            ctx,
            "table_text_label",
            label,
            styles={
                "height": 16,
                "fontSize": 10,
                "fontWeight": 500,
                "fontColor": palette(ctx).secondary,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "layoutWeight": 1,
                "flexShrink": 1,
                "constraintSize": {"minWidth": 0},
            },
        )
        parameter_node = text(
            ctx,
            "table_text_parameter",
            ctx.item_prop(node.tag, item, index, "parameter"),
            styles={
                "height": 16,
                "fontSize": 10,
                "fontWeight": 500,
                "fontColor": palette(ctx).primary,
                "textAlign": "end",
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "flexShrink": 1,
                "constraintSize": {"minWidth": 0},
            },
        )
        rows.append(
            row(
                ctx,
                "table_text_item",
                [label_node, parameter_node],
                gap=8,
                styles={
                    "width": "matchParent",
                    "height": 16,
                    "alignItems": "bottom",
                    "justifyContent": "spaceBetween",
                },
            )
        )

    return column(
        ctx,
        "table_text",
        rows,
        gap=2,
        styles={"width": "matchParent", "alignItems": "start"},
    )
