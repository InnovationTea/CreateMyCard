from __future__ import annotations

from ...catalog.display_units import repeats_numeric_unit
from ...catalog.display_values import normalize_percentage_value
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.image import image
from ..base.layout import column, row, stack
from ..base.progress import progress
from ..base.text import text
from ..common import palette


def collect_info_block_conversion_errors(node: JSXElement) -> list[str]:
    errors: list[str] = []
    visual = node.props.get("visual")
    if visual is not None:
        if not isinstance(visual, dict):
            return ["<InfoBlock> visual must be an object when provided"]
        visual_type = visual.get("type")
        if visual_type not in {"icon", "progressCircle"}:
            errors.append("<InfoBlock> visual.type must be 'icon' or 'progressCircle'")
        icon = visual.get("icon")
        if not isinstance(icon, str) or not icon.strip():
            errors.append("<InfoBlock> visual.icon must be a non-empty asset src")
        allowed = {"type", "icon", "color"} if visual_type == "icon" else {"type", "icon"}
        unknown = set(visual) - allowed
        if unknown:
            errors.append(
                "<InfoBlock> visual has unsupported fields: " + ", ".join(sorted(unknown))
            )
        if visual_type == "icon" and visual.get("color") not in {None, "native"}:
            errors.append("<InfoBlock> visual.color may only be 'native'")
    unit = node.props.get("unit")
    if unit is not None and not isinstance(unit, str):
        errors.append("<InfoBlock> unit must be a string")
    return errors


def convert_info_block(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_info_block_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    visual = node.props.get("visual")
    current_palette = palette(ctx)
    visual_foreground = current_palette.primary

    primary_value = ctx.prop(node, "primaryText")
    primary_binding = ctx.bound_data(node.props, "primaryText")
    primary_display = primary_binding.value if primary_binding is not None else primary_value
    primary = text(
        ctx,
        "info_block_primary_value",
        primary_value,
        styles={
            "height": 20,
            "fontSize": 14,
            "fontWeight": 700,
            "fontColor": current_palette.primary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "flexShrink": 1,
            "constraintSize": {"minWidth": 0},
        },
    )
    primary_children: list[A2UINode] = [primary]
    explicit_unit = node.props.get("unit")
    if explicit_unit is not None and not repeats_numeric_unit(primary_display, explicit_unit):
        primary_children.append(
            text(
                ctx,
                "info_block_unit",
                node.props["unit"],
                styles={
                    "height": 16,
                    "fontSize": 10,
                    "fontWeight": 500,
                    "fontColor": current_palette.secondary,
                    "maxLines": 1,
                    "flexShrink": 0,
                    "visibility": ctx.unit_visibility(primary_binding),
                },
            )
        )
    primary_row = row(
        ctx,
        "info_block_primary",
        primary_children,
        gap=2,
        styles={
            "width": "matchParent",
            "height": 20,
            "alignItems": "bottom",
            "constraintSize": {"minWidth": 0},
        },
    )
    secondary = text(
        ctx,
        "info_block_secondary",
        ctx.prop(node, "secondaryText"),
        styles={
            "width": "matchParent",
            "height": 18,
            "fontSize": 12,
            "fontWeight": 500,
            "fontColor": current_palette.secondary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "flexShrink": 1,
            "constraintSize": {"minWidth": 0},
        },
    )
    copy = column(
        ctx,
        "info_block_copy",
        [primary_row, secondary],
        gap=0,
        styles={
            "layoutWeight": 1,
            "flexShrink": 1,
            "alignItems": "start",
            "justifyContent": "center",
            "constraintSize": {"minWidth": 0},
        },
    )

    visual_node = None
    if isinstance(visual, dict) and visual["type"] == "progressCircle":
        icon = visual["icon"]
        if not isinstance(icon, str):
            raise AssertionError()
        if primary_binding is not None:
            if normalize_percentage_value(primary_binding.value) is None:
                raise ValidationError(
                    "<InfoBlock> progressCircle primaryText must be a number or "
                    "numeric percentage such as 68 or '68%'"
                )
            if isinstance(primary_binding.value, str):
                derived_root, _ = ctx.register_derived_display(primary_binding)
                progress_value = {
                    "path": f"{derived_root}/progressValue"
                }
            else:
                progress_value = {"path": primary_binding.path}
        else:
            progress_value = normalize_percentage_value(
                node.props.get("primaryText")
            )
            # Match the JSX runtime's progressPercentage()/clamp() fallback.
            if progress_value is None:
                progress_value = 0
        ring = progress(
            ctx,
            "info_block_progress",
            progress_value,
            100,
            kind="ring",
            color=current_palette.progress_bar,
            stroke_width=6,
            styles={
                "width": 44,
                "height": 44,
                "backgroundColor": current_palette.progress_track,
                "flexShrink": 0,
            },
        )
        icon_node = image(
            ctx,
            "info_block_progress_icon",
            icon,
            styles={"width": 20, "height": 20, "objectFit": "contain"},
            fill_color=current_palette.progress_icon,
        )
        visual_node = stack(
            ctx,
            "info_block_progress_visual",
            [ring, icon_node],
            align="center",
            styles={"width": 44, "height": 44, "flexShrink": 0},
        )
    elif isinstance(visual, dict):
        icon = visual["icon"]
        if not isinstance(icon, str):
            raise AssertionError()
        visual_node = image(
            ctx,
            "info_block_icon",
            icon,
            styles={"width": 24, "height": 24, "objectFit": "contain", "flexShrink": 0},
            fill_color=None if visual.get("color") == "native" else visual_foreground,
        )

    return row(
        ctx,
        "info_block",
        [copy, visual_node],
        gap=4,
        styles={
            "width": "matchParent",
            "height": 64,
            "padding": {"left": 8, "right": 8},
            "borderRadius": 16,
            "backgroundColor": current_palette.action_background,
            "alignItems": "center",
            "justifyContent": "spaceBetween",
            "flexShrink": 0,
            "clip": True,
        },
    )
