from __future__ import annotations

from ...catalog.display_values import (
    normalize_display_value,
    normalize_percentage_value,
)
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import row
from ..base.text import text
from ..common import palette


def collect_emphasized_data_conversion_errors(node: JSXElement) -> list[str]:
    raw_items = node.props.get("items")
    if raw_items is None:
        return []
    if not isinstance(raw_items, list):
        return ["EmphasizedData.items must be an array of objects"]
    errors: list[str] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            errors.append(f"EmphasizedData.items[{index}] must be an object")
        elif "value" not in item:
            errors.append(f"EmphasizedData.items[{index}] must contain value")
    return errors


def convert_emphasized_data(
    node: JSXElement,
    ctx: ConversionContext,
    *,
    value_height: int = 38,
    unit_height: int | None = 18,
    unit_bottom_inset: int = 0,
) -> A2UINode:
    errors = collect_emphasized_data_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))

    def derived_items(binding) -> list[dict]:
        root_path, plan = ctx.register_derived_display(binding)
        result = []
        wrappable_raw_text = (
            plan.mode == "raw"
            and isinstance(plan.raw, str)
            and normalize_percentage_value(plan.raw) is None
        )
        for index, part in enumerate(plan.parts):
            part_path = f"{root_path}/parts/{index}"
            result.append(
                {
                    "value": {"path": f"{part_path}/value"},
                    "unit": ({"path": f"{part_path}/unit"} if part.unit is not None else None),
                    "wrappableRawText": wrappable_raw_text,
                }
            )
        return result

    def bound_string_items(owner: dict, binding, *, item_index: int | None = None) -> list[dict]:
        plan = normalize_display_value(binding.value)
        data_ids = owner.get("dataIds")
        # Two independently bound source fields are already structured data;
        # preserve them when the value itself has no formatted unit.
        if plan.mode == "raw" and isinstance(data_ids, dict) and "unit" in data_ids:
            if item_index is None:
                return [
                    {
                        "value": ctx.prop(node, "value"),
                        "unit": ctx.prop(node, "unit"),
                        "wrappableRawText": False,
                    }
                ]
            return [
                {
                    "value": ctx.item_prop(node.tag, owner, item_index, "value"),
                    "unit": ctx.item_prop(node.tag, owner, item_index, "unit"),
                    "wrappableRawText": False,
                }
            ]
        return derived_items(binding)

    def literal_items(owner: dict) -> list[dict]:
        value = owner.get("value")
        if isinstance(value, str):
            plan = normalize_display_value(value)
            if plan.mode == "parts":
                return [
                    {
                        "value": part.value,
                        "unit": part.unit,
                        "wrappableRawText": False,
                    }
                    for part in plan.parts
                ]
            unit = owner.get("unit")
            return [
                {
                    "value": value,
                    "unit": unit,
                    "wrappableRawText": (
                        unit is None and normalize_percentage_value(value) is None
                    ),
                }
            ]
        return [
            {
                "value": value,
                "unit": owner.get("unit"),
                "wrappableRawText": False,
            }
        ]

    raw_items = node.props.get("items")
    items: list[dict] = []
    if raw_items is None:
        value_binding = ctx.bound_data(node.props, "value")
        if value_binding is not None and isinstance(value_binding.value, str):
            items.extend(bound_string_items(node.props, value_binding))
        elif value_binding is None:
            items.extend(literal_items(node.props))
        else:
            items.append(
                {
                    "value": ctx.prop(node, "value"),
                    "unit": ctx.prop(node, "unit"),
                    "wrappableRawText": False,
                }
            )
    else:
        for index, item in enumerate(raw_items):
            value_binding = ctx.bound_data(item, "value")
            if value_binding is not None and isinstance(value_binding.value, str):
                items.extend(bound_string_items(item, value_binding, item_index=index))
            elif value_binding is None:
                items.extend(literal_items(item))
            else:
                items.append(
                    {
                        "value": ctx.item_prop(node.tag, item, index, "value"),
                        "unit": ctx.item_prop(node.tag, item, index, "unit"),
                        "wrappableRawText": False,
                    }
                )
    wraps_single_raw_text = (
        len(items) == 1
        and items[0].get("wrappableRawText") is True
        and items[0].get("unit") is None
    )
    children = []
    for index, item in enumerate(items):
        value_styles = {
            "fontSize": 38,
            "fontWeight": 700,
            "fontColor": palette(ctx).primary,
        }
        if wraps_single_raw_text:
            value_styles.update(
                {
                    "width": "matchParent",
                    "constraintSize": {"minWidth": 0, "minHeight": value_height},
                    "flexShrink": 1,
                }
            )
        else:
            value_styles.update(
                {
                    "height": value_height,
                    # Numeric and structured values are atomic. This prevents
                    # values such as 29 from splitting across two lines.
                    "maxLines": 1,
                    "flexShrink": 0,
                }
            )
        children.append(
            text(
                ctx,
                f"emphasized_value_{index + 1}",
                item.get("value"),
                styles=value_styles,
            )
        )
        if item.get("unit") is not None:
            # Ordinary EmphasizedData uses a 38vp value line box and an 18vp
            # unit line box aligned at the bottom, matching JSX flex-end.
            # Components with distinct typography geometry (ProgressLine2)
            # can opt into their own baseline approximation explicitly.
            unit_styles = {
                "fontSize": 12,
                "fontWeight": 400,
                "fontColor": palette(ctx).secondary,
                "flexShrink": 0,
            }
            if unit_height is not None:
                unit_styles["height"] = unit_height
            if unit_bottom_inset:
                unit_styles["padding"] = {"bottom": unit_bottom_inset}
            children.append(
                text(
                    ctx,
                    f"emphasized_unit_{index + 1}",
                    item.get("unit"),
                    styles=unit_styles,
                )
            )
    row_styles = {
        "alignItems": "bottom",
        "flexShrink": 0,
    }
    if wraps_single_raw_text:
        row_styles.update(
            {
                "width": "matchParent",
                "constraintSize": {"minWidth": 0},
                "flexShrink": 1,
            }
        )
    return row(
        ctx,
        "emphasized_data",
        children,
        gap=2,
        styles=row_styles,
    )
