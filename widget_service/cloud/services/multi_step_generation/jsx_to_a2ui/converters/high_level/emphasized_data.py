from __future__ import annotations

from ...catalog.bindings import a2ui_expression, data_model_expression_reference
from ...catalog.display_units import is_unitless_number, units_equivalent
from ...catalog.display_values import (
    normalize_display_value,
    normalize_percentage_value,
)
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import row
from ..base.text import fixed_text_line_box, text
from ..common import palette

# Bundled HarmonyOS Sans SC metrics: 38px/38px Bold has its first baseline
# 32vp below the line-box top; 12px/18px Regular has it at 13vp. A2UI Row
# has no baseline enum. Top-align these line boxes and offset the unit's
# first line, so wrapping units grow down instead of lifting the number.
_VALUE_FIRST_BASELINE = 32
_UNIT_FIRST_BASELINE = 13


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
    unit_height: int | None = None,
    unit_bottom_inset: int = 0,
) -> A2UINode:
    errors = collect_emphasized_data_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))

    def derived_items(binding, *, declared_unit: bool = False) -> list[dict]:
        root_path, plan = ctx.register_derived_display(binding)
        parts_key = "parts"
        if declared_unit and binding.display_unit:
            plan = normalize_display_value(binding.display_value)
            parts_key = "unitParts"
        result = []
        wrappable_raw_text = (
            plan.mode == "raw"
            and isinstance(plan.raw, str)
            and normalize_percentage_value(plan.raw) is None
        )
        for index, part in enumerate(plan.parts):
            part_path = f"{root_path}/{parts_key}/{index}"
            result.append(
                {
                    "value": {"path": f"{part_path}/value"},
                    "unit": ({"path": f"{part_path}/unit"} if part.unit is not None else None),
                    "wrappableRawText": wrappable_raw_text,
                }
            )
        return result

    def bound_string_items(owner: dict, binding, *, item_index: int | None = None) -> list[dict]:
        data_ids = owner.get("dataIds")
        if isinstance(data_ids, dict) and "unit" in data_ids:
            if item_index is None:
                unit = ctx.prop(node, "unit")
            else:
                unit = ctx.item_prop(node.tag, owner, item_index, "unit")
            return [{"value": {"path": binding.path}, "unit": unit, "wrappableRawText": False}]
        # The JSX already declares the suffix. Reuse its existing string display
        # model so updates between numeric and complete text retain precision and
        # follow the same shape/rebuild contract as the preview.
        if binding.display_unit and owner.get("unit") != "":
            return derived_items(binding, declared_unit=True)
        plan = normalize_display_value(binding.value)
        if plan.mode == "raw":
            return [{
                "value": {"path": binding.path}, "unit": owner.get("unit"),
                "wrappableRawText": not is_unitless_number(binding.value) and not owner.get("unit"),
            }]
        return derived_items(binding)

    def literal_items(owner: dict, item_index: int | None = None) -> list[dict]:
        value = owner.get("value")
        unit = owner.get("unit")
        if ctx.bound_data(owner, "unit") is not None:
            unit = ctx.prop(node, "unit") if item_index is None else ctx.item_prop(
                node.tag, owner, item_index, "unit"
            )
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
                "unit": unit,
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
                items.extend(literal_items(item, index))
            else:
                items.append(
                    {
                        "value": ctx.item_prop(node.tag, item, index, "value"),
                        "unit": ctx.item_prop(node.tag, item, index, "unit"),
                        "wrappableRawText": False,
                    }
                )
    # Preserve the existing Celsius display rule for an explicit numeric unit,
    # just as normalizeEmphasizedItem does in JSX.
    for item in items:
        unit = item.get("unit")
        value = item.get("value")
        if not isinstance(unit, str) or not units_equivalent(unit, "℃"):
            continue
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            item["value"] = a2ui_expression([
                data_model_expression_reference(value.get("path")), "'°'",
            ])
            item["unit"] = None
        elif is_unitless_number(value):
            item["value"] = f"{str(value).strip()}°"
            item["unit"] = None
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
        value_node = text(
            ctx,
            f"emphasized_value_{index + 1}",
            item.get("value"),
            styles=value_styles,
        )
        if not wraps_single_raw_text:
            value_node = fixed_text_line_box(
                ctx, f"emphasized_value_slot_{index + 1}", value_node, value_height
            )
        children.append(value_node)
        if item.get("unit") is not None:
            # Ordinary units can wrap beside an atomic number, with an 18vp
            # line box. ProgressLine2 opts into its fixed unit geometry.
            unit_styles = {
                "fontSize": 12,
                "fontWeight": 400,
                "fontColor": palette(ctx).secondary,
                "flexShrink": 1,
            }
            if unit_height is None:
                unit_styles["constraintSize"] = {"minHeight": 18}
            else:
                unit_styles["height"] = unit_height
                unit_styles["flexShrink"] = 0
            unit = item.get("unit")
            unit_node = text(
                ctx,
                f"emphasized_unit_{index + 1}",
                unit,
                styles=unit_styles,
            )
            # Only fixed/non-wrapping units have a single known line box.
            # Keep multiline and independently bound units content-driven.
            single_character = isinstance(unit, str) and len(unit) == 1 and not unit.isspace()
            if unit_height is not None or single_character:
                unit_node.styles.pop("constraintSize", None)
                unit_node = fixed_text_line_box(
                    ctx,
                    f"emphasized_unit_slot_{index + 1}",
                    unit_node,
                    18 if unit_height is None else unit_height,
                )
            if unit_height is None:
                # The value Text is centered in value_height. Preserve that
                # baseline if an implementation caller supplies a taller box.
                unit_top = _VALUE_FIRST_BASELINE - _UNIT_FIRST_BASELINE + (value_height - 38) / 2
                unit_node.styles["margin"] = {"top": unit_top}
            elif unit_bottom_inset:
                unit_node.styles["margin"] = {"bottom": unit_bottom_inset}
            children.append(unit_node)
    row_styles = {
        "alignItems": "top" if unit_height is None else "bottom",
        "flexShrink": 0,
    }
    if unit_height is None:
        # JSX's automatic content minimum protects an atomic number + unit
        # from a full-width sibling. If every child is non-shrinking, shrinking
        # just this Row would let its painted contents overlap that sibling.
        # Keep content-driven/multiline units shrinkable so they can still wrap.
        can_wrap = any(child.styles.get("flexShrink") != 0 for child in children)
        row_styles.update({
            "flexShrink": 1 if can_wrap else 0,
            "constraintSize": {"maxWidth": "100%"},
        })
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
