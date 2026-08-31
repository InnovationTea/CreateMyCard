from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.text import text
from ..common import palette


def collect_text_block_conversion_errors(node: JSXElement) -> list[str]:
    items = node.props.get("items")
    if not isinstance(items, list) or len(items) < 2:
        return ["<TextBlock> items must contain at least two groups"]
    errors: list[str] = []
    for index, item in enumerate(items):
        where = f"<TextBlock> items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        if not isinstance(item.get("label"), str) or not item["label"].strip():
            errors.append(f"{where}.label must be a non-empty string")
        parameter = item.get("parameter")
        if isinstance(parameter, bool) or not isinstance(parameter, (str, int, float)):
            errors.append(f"{where}.parameter must be a string or number")
    return errors


def convert_text_block(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_text_block_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props["items"]
    assert isinstance(items, list)
    current = palette(ctx)
    # The JSX runtime maps TextBlock to the card action color on light cards,
    # but deliberately overrides it to white on every dark/gradient card.
    # Do not use action_text unconditionally here: on a gradient it is the
    # accent intended for white action surfaces, not the TextBlock foreground.
    accent = current.primary if current.primary == "#FFFFFFFF" else current.action_text
    background = "#1A" + accent[-6:]
    blocks: list[A2UINode] = []
    for index, item in enumerate(items):
        assert isinstance(item, dict)
        blocks.append(
            column(
                ctx,
                "text_block_item",
                [
                    text(ctx, "text_block_label", item["label"], styles={"width": "matchParent", "constraintSize": {"minWidth": 0}, "height": 18, "fontSize": 12, "fontWeight": 700, "fontColor": accent, "maxLines": 1, "textOverflow": "ellipsis"}),
                    text(ctx, "text_block_parameter", ctx.item_prop(node.tag, item, index, "parameter"), styles={"width": "matchParent", "constraintSize": {"minWidth": 0}, "height": 16, "fontSize": 10, "fontWeight": 500, "fontColor": accent, "maxLines": 1, "textOverflow": "ellipsis"}),
                ],
                gap=2,
                styles={
                    "height": 64,
                    "padding": {"left": 8, "right": 8},
                    "borderRadius": 16,
                    "backgroundColor": background,
                    "alignItems": "start",
                    "justifyContent": "center",
                    "constraintSize": {"minWidth": 64},
                    "layoutWeight": 1,
                    "flexShrink": 1,
                },
            )
        )
    return row(
        ctx,
        "text_block",
        blocks,
        gap=8,
        styles={"width": "matchParent", "height": 64, "alignItems": "center"},
    )
