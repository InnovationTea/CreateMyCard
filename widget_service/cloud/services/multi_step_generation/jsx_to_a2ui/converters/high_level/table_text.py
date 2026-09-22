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
        if isinstance(parameter, bool) or not isinstance(
            parameter, str | int | float
        ):
            errors.append(f"{where}.parameter must be a string or number")
    return errors


def convert_table_text(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_table_text_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props.get("items")
    if not isinstance(items, list):
        raise AssertionError()
    parent_width = ctx.parent_content_width
    narrow_multirow = (
        len(items) >= 3
        and isinstance(parent_width, int | float)
        and not isinstance(parent_width, bool)
        and parent_width <= 120
    )
    row_height: str | int = "wrapContent" if narrow_multirow else 16
    text_height: str | int = "wrapContent" if narrow_multirow else 16

    rows: list[A2UINode] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AssertionError()
        label = item.get("label")
        if not isinstance(label, str):
            raise AssertionError()

        label_node = text(
            ctx,
            "table_text_label",
            ctx.item_prop(node.tag, item, index, "label"),
            styles={
                "width": "fixAtIdealSize",
                "height": 12 if narrow_multirow else text_height,
                "fontSize": 10,
                "fontWeight": 500,
                "fontColor": palette(ctx).secondary,
                "maxLines": 1,
                "flexShrink": 0,
            },
        )
        parameter_node = text(
            ctx,
            "table_text_parameter",
            ctx.item_prop(node.tag, item, index, "parameter"),
            styles={
                "height": row_height,
                "fontSize": 10,
                "fontWeight": 500,
                "fontColor": palette(ctx).primary,
                "textAlign": "end",
                "maxLines": 2 if narrow_multirow else 1,
                "textOverflow": "ellipsis",
                "layoutWeight": 1,
                "flexShrink": 1,
                "constraintSize": {
                    "minWidth": 0,
                    **({"minHeight": 12, "maxHeight": 24} if narrow_multirow else {}),
                },
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
                    "height": row_height,
                    "flexShrink": 0,
                    # Native Column suppresses itemMargin under spaceBetween.
                    # Explicit row margins preserve CSS gap's minimum while
                    # still allowing surplus height to be distributed.
                    **({"margin": {"bottom": 2}}
                       if len(items) >= 3 and index < len(items) - 1 else {}),
                    **({"constraintSize": {"minHeight": 16, "maxHeight": 24}}
                       if narrow_multirow else {}),
                    "alignItems": "top" if narrow_multirow else "bottom",
                    "justifyContent": "spaceBetween",
                },
            )
        )

    return column(
        ctx,
        "table_text",
        rows,
        gap=0 if len(rows) >= 3 else 2,
        styles={
            "width": "matchParent",
            # Auto-height slots measure their rows. Definite slots opt into
            # adaptive filling in adapt_flex_children.
            "height": "wrapContent",
            "alignItems": "start",
            "justifyContent": "spaceBetween" if len(rows) >= 3 else "start",
        },
    )
