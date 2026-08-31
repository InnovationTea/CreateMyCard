from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from .numeric_ratio import collect_numeric_ratio_conversion_errors, convert_numeric_ratio


def _numeric_ratio_item_node(node: JSXElement, item: dict) -> JSXElement:
    child_props = {
        "icon": item.get("icon"),
        "value": item.get("value"),
        "appearance": node.props.get("appearance"),
    }
    if "unit" in item:
        child_props["unit"] = item["unit"]
    if item.get("dataIds") is not None:
        child_props["dataIds"] = item.get("dataIds")
    return JSXElement("NumericRatio", child_props)


def collect_numeric_ratio_stack_conversion_errors(node: JSXElement) -> list[str]:
    items = node.props.get("items")
    if not isinstance(items, list):
        return ["NumericRatioStack.items must be an array"]
    errors: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"NumericRatioStack.items[{index}] must be an object")
            continue
        for error in collect_numeric_ratio_conversion_errors(_numeric_ratio_item_node(node, item)):
            errors.append(f"NumericRatioStack.items[{index}]: {error}")
    return errors


def convert_numeric_ratio_stack(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_numeric_ratio_stack_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props.get("items")
    children = []
    for item in items:
        child = _numeric_ratio_item_node(node, item)
        children.append(convert_numeric_ratio(child, ctx))
    return column(ctx, "numeric_ratio_stack", children, gap=4, styles={"alignItems": "start"})
