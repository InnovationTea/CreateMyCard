# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Design-token and high-level component expansion for 2x2 Compact DSL."""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from typing import Any

A2UI_ICON_BUTTON_LABEL = "\u200B"
CARD_2X2_INNER_SIZE = 136
ICON_ROUND_SIZE = 40
ICON_ROUND_ICON_SIZE = 20
TITLE_ICON_SIZE = 20
BOTTOM_RING_ACTION_AREA_HEIGHT = 52
CAPSULE_ICON_SIZE = 18
CAPSULE_ICON_TEXT_GAP = 12

_RING_UNIT_CENTER_ICON_STATES = frozenset({"center-icon", "without-reading"})
_RING_UNIT_CENTER_TEXT_STATES = frozenset({"center-text", "center-reading"})
_RING_READING_NUMBER_TEXT = {
    "fontSize": 16,
    "fontWeight": 700,
    "maxLines": 1,
    "flexShrink": 0,
}
_RING_READING_UNIT_TEXT = {
    "fontSize": 10,
    "fontWeight": 400,
    "opacity": 0.6,
    "maxLines": 1,
    "flexShrink": 0,
}
_TIMELINE_UNIT_DEFAULT_COLOR = "#FFE84026"
_TIMELINE_UNIT_DEFAULT_LINE_COLOR = "#1A000000"


class DesignTokenConversionError(ValueError):
    """Raised when a Compact DSL design token cannot be expanded."""


_LEGACY_TOKEN_PREFIXES = (
    "padding_level",
    "corner_radius_level",
    "font_weight_",
)
_LEGACY_FONT_SIZE_TOKENS = frozenset(
    {
        "Display_L",
        "Display_M",
        "Display_S",
        "Title_L",
        "Title_M",
        "Title_S",
        "Subtitle_L",
        "Subtitle_M",
        "Subtitle_S",
        "Body_L",
        "Body_M",
        "Body_S",
        "Caption_L",
        "Caption_M",
    }
)
_TOKEN_AWARE_PROPERTIES = frozenset(
    {
        "borderRadius",
        "fontSize",
        "fontWeight",
        "height",
        "itemMargin",
        "margin",
        "maxHeight",
        "maxWidth",
        "minHeight",
        "minWidth",
        "padding",
        "space",
        "strokeWidth",
        "width",
    }
)
_COLOR_PROPERTIES = frozenset(
    {
        "backgroundColor",
        "borderColor",
        "color",
        "fillColor",
        "fontColor",
        "actionInk",
        "selectedColor",
        "shadowColor",
        "strokeColor",
        "unSelectedColor",
    }
)
_COLOR_TOKENS = {
    "font_primary": "#E5000000",
    "font_secondary": "#99000000",
    "font_tertiary": "#66000000",
    "font_emphasize": "#FF0A59F7",
    "font_on_primary": "#FFFFFFFF",
    "warning": "#FFE84026",
    "alert": "#FFED6F21",
    "confirm": "#FF64BB5C",
    "icon_primary": "#E5000000",
    "icon_secondary": "#99000000",
    "icon_tertiary": "#66000000",
    "icon_fourth": "#33000000",
    "icon_emphasize": "#FF0A59F7",
    "icon_on_primary": "#FFFFFFFF",
    "icon_on_secondary": "#99FFFFFF",
    "icon_on_tertiary": "#66FFFFFF",
    "icon_on_fourth": "#33FFFFFF",
    "background_primary": "#FFFFFFFF",
    "background_emphasize": "#FF0A59F7",
    "comp_background_list_card": "#FFFFFFFF",
    "comp_background_emphasize": "#FF0A59F7",
    "comp_background_tertiary": "#0C000000",
    "comp_background_secondary": "#19000000",
    "comp_background_primary_contrary": "#FFFFFFFF",
    "comp_divider": "#33000000",
    "container40": "#66000000",
    "primary50": "#7F000000",
    "multi_color_01": "#FF564AF7",
    "multi_color_02": "#FF46B1E3",
    "multi_color_03": "#FF61CFBE",
    "multi_color_04": "#FF64BB5C",
    "multi_color_05": "#FFA5D61D",
    "multi_color_06": "#FFAC49F5",
    "multi_color_07": "#FFE64566",
    "multi_color_08": "#FFE84026",
    "multi_color_09": "#FFED6F21",
    "multi_color_10": "#FFF9A01E",
    "multi_color_11": "#FFF7CE00",
    "multi_color_aux_01": "#FF8981F7",
    "multi_color_aux_02": "#FF86C5E3",
    "multi_color_aux_03": "#FF92D6CC",
    "multi_color_aux_04": "#FF92C48D",
    "multi_color_aux_05": "#FFBDDB69",
    "multi_color_aux_06": "#FFC386F0",
    "multi_color_aux_07": "#FFE67C92",
    "multi_color_aux_08": "#FFE87361",
    "multi_color_aux_09": "#FFED955F",
    "multi_color_aux_10": "#FFF9BC64",
    "multi_color_aux_11": "#FFF5DC62",
    "mask_primary": "#CC000000",
    "mask_secondary": "#99000000",
    "mask_tertiary": "#66000000",
    "mask_fourth": "#33000000",
    "mask_fifth": "#19000000",
    "mask_sixth": "#0C000000",
}
ROOT_LINEAR_GRADIENT_PALETTES = (
    {
        "angle": 180,
        "colors": [
            ["#FFEAF2FF", 0.0],
            ["#FFF7FBFF", 0.55],
            ["#FFFFFFFF", 1.0],
        ],
    },
    {
        "angle": 180,
        "colors": [
            ["#FFFFE9E5", 0.0],
            ["#FFFFF6F3", 0.55],
            ["#FFFFFFFF", 1.0],
        ],
    },
    {
        "angle": 180,
        "colors": [
            ["#FFE5F6FF", 0.0],
            ["#FFF4FBFF", 0.55],
            ["#FFFFFFFF", 1.0],
        ],
    },
    {
        "angle": 180,
        "colors": [
            ["#FFE7F8EE", 0.0],
            ["#FFF5FCF8", 0.55],
            ["#FFFFFFFF", 1.0],
        ],
    },
    {
        "angle": 180,
        "colors": [
            ["#FFFFEDD8", 0.0],
            ["#FFFFF8EF", 0.55],
            ["#FFFFFFFF", 1.0],
        ],
    },
    {
        "angle": 180,
        "colors": [
            ["#FFF1E8FF", 0.0],
            ["#FFFAF6FF", 0.55],
            ["#FFFFFFFF", 1.0],
        ],
    },
)
SURFACE_DESIGNS: dict[str, dict[str, Any]] = {
    "Surface.brandSoft": {"linearGradient": ROOT_LINEAR_GRADIENT_PALETTES[0]},
    "Surface.redSoft": {"linearGradient": ROOT_LINEAR_GRADIENT_PALETTES[1]},
    "Surface.cyanSoft": {"linearGradient": ROOT_LINEAR_GRADIENT_PALETTES[2]},
    "Surface.greenSoft": {"linearGradient": ROOT_LINEAR_GRADIENT_PALETTES[3]},
    "Surface.orangeSoft": {"linearGradient": ROOT_LINEAR_GRADIENT_PALETTES[4]},
    "Surface.purpleSoft": {"linearGradient": ROOT_LINEAR_GRADIENT_PALETTES[5]},
    "Surface.weatherStrongBlue": {
        "linearGradient": {
            "angle": 180,
            "colors": [["#FF317AF7", 0.0], ["#FF46B1E3", 1.0]],
        }
    },
    "Surface.trafficStrongDark": {
        "linearGradient": {
            "angle": 180,
            "colors": [["#FF46484D", 0.0], ["#FF467794", 1.0]],
        }
    },
    "Surface.sportStrongOrange": {
        "linearGradient": {
            "angle": 180,
            "colors": [["#FFED6F21", 0.0], ["#FFF9A01E", 1.0]],
        }
    },
    "Surface.sleepStrongPurple": {
        "linearGradient": {
            "angle": 180,
            "colors": [["#FFAC49F5", 0.0], ["#FFC386F0", 1.0]],
        }
    },
}
PRESERVE_ORIGINAL_COLOR_ICON_BASENAMES = frozenset({"icon_weather1.svg"})
BOTTOM_RING_ACTION_EQUIVALENT_ICON_GROUPS = (
    frozenset(
        {
            "battery_leaf_fill.svg",
            "icon_save_power.svg",
            "battery_saving_fill.svg",
            "battery_saver_fill.svg",
        }
    ),
)
SEMANTIC_REPAIRABLE_ROOT_GRADIENT_COLOR_SETS = frozenset(
    {
        frozenset({"#FFEAF2FF", "#FFF7FBFF", "#FFFFFFFF"}),
        frozenset({"#FFE5F6FF", "#FFF4FBFF", "#FFFFFFFF"}),
        frozenset({"#FFE1ECFF", "#FFF3F7FF", "#FFFFFFFF"}),
    }
)
WEATHER_ROOT_GRADIENT_COLOR_SETS = frozenset(
    {
        frozenset({"#FF317AF7", "#FF46B1E3"}),
        frozenset({"#FF46484D", "#FF467794"}),
    }
)
SLEEP_ROOT_GRADIENT_COLOR_SET = frozenset({"#FFAC49F5", "#FFC386F0"})
STRONG_ROOT_GRADIENT_COLOR_SETS = frozenset(
    {
        *WEATHER_ROOT_GRADIENT_COLOR_SETS,
        frozenset({"#FFED6F21", "#FFF9A01E"}),
        SLEEP_ROOT_GRADIENT_COLOR_SET,
    }
)
GRADIENT_ACTION_INKS = {
    frozenset({"#FF317AF7", "#FF46B1E3"}): "#FF317AF7",
    frozenset({"#FF46484D", "#FF467794"}): "#FF467794",
    frozenset({"#FFED6F21", "#FFF9A01E"}): "#FFED6F21",
    frozenset({"#FFAC49F5", "#FFC386F0"}): "#FFAC49F5",
    frozenset({"#1A0A59F7", "#FFFFFFFF"}): "#FF0A59F7",
    frozenset({"#1A0A8FF7", "#FFFFFFFF"}): "#FF0A8FF7",
    frozenset({"#1AE84026", "#FFFFFFFF"}): "#FFE84026",
    frozenset({"#1A000000", "#FFFFFFFF"}): "#FF0A8FF7",
    frozenset({"#1A64BB5C", "#FFFFFFFF"}): "#FF64BB5C",
    frozenset({"#1AF9A01E", "#FFFFFFFF"}): "#FFF9A01E",
    frozenset({"#1AED6F21", "#FFFFFFFF"}): "#FFED6F21",
    frozenset({"#1AAC49F5", "#FFFFFFFF"}): "#FFAC49F5",
    frozenset({"#FFEAF2FF", "#FFF7FBFF", "#FFFFFFFF"}): "#FF0A59F7",
    frozenset({"#FFFFE9E5", "#FFFFF6F3", "#FFFFFFFF"}): "#FFE84026",
    frozenset({"#FFF0F2F5", "#FFF8F9FA", "#FFFFFFFF"}): "#FF0A8FF7",
    frozenset({"#FFE5F6FF", "#FFF4FBFF", "#FFFFFFFF"}): "#FF0A8FF7",
    frozenset({"#FFE7F8EE", "#FFF5FCF8", "#FFFFFFFF"}): "#FF64BB5C",
    frozenset({"#FFFFEDD8", "#FFFFF8EF", "#FFFFFFFF"}): "#FFF9A01E",
    frozenset({"#FFF1E8FF", "#FFFAF6FF", "#FFFFFFFF"}): "#FFAC49F5",
}
GRADIENT_ACTION_BACKGROUNDS = {
    frozenset({"#FF317AF7", "#FF46B1E3"}): "#FFFFFFFF",
    frozenset({"#FF46484D", "#FF467794"}): "#FFFFFFFF",
    frozenset({"#FFED6F21", "#FFF9A01E"}): "#FFFFFFFF",
    frozenset({"#FFAC49F5", "#FFC386F0"}): "#FFFFFFFF",
    frozenset({"#1A0A59F7", "#FFFFFFFF"}): "#1A0A59F7",
    frozenset({"#1A0A8FF7", "#FFFFFFFF"}): "#1A0A8FF7",
    frozenset({"#1AE84026", "#FFFFFFFF"}): "#1AE84026",
    frozenset({"#1A000000", "#FFFFFFFF"}): "#1A0A8FF7",
    frozenset({"#1A64BB5C", "#FFFFFFFF"}): "#1A64BB5C",
    frozenset({"#1AF9A01E", "#FFFFFFFF"}): "#1AF9A01E",
    frozenset({"#1AED6F21", "#FFFFFFFF"}): "#1AED6F21",
    frozenset({"#1AAC49F5", "#FFFFFFFF"}): "#1AAC49F5",
    frozenset({"#FFEAF2FF", "#FFF7FBFF", "#FFFFFFFF"}): "#1A0A59F7",
    frozenset({"#FFFFE9E5", "#FFFFF6F3", "#FFFFFFFF"}): "#1AE84026",
    frozenset({"#FFF0F2F5", "#FFF8F9FA", "#FFFFFFFF"}): "#1A0A8FF7",
    frozenset({"#FFE5F6FF", "#FFF4FBFF", "#FFFFFFFF"}): "#1A0A8FF7",
    frozenset({"#FFE7F8EE", "#FFF5FCF8", "#FFFFFFFF"}): "#1A64BB5C",
    frozenset({"#FFFFEDD8", "#FFFFF8EF", "#FFFFFFFF"}): "#1AF9A01E",
    frozenset({"#FFF1E8FF", "#FFFAF6FF", "#FFFFFFFF"}): "#1AAC49F5",
}
SHALLOW_ROOT_GRADIENTS = {
    frozenset({"#1A0A59F7", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[0],
    frozenset({"#1A0A8FF7", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[2],
    frozenset({"#1AE84026", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[1],
    frozenset({"#1A000000", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[2],
    frozenset({"#1A64BB5C", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[3],
    frozenset({"#1AF9A01E", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[4],
    frozenset({"#1AED6F21", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[4],
    frozenset({"#1AAC49F5", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[5],
    frozenset({"#FFEAF2FF", "#FFF7FBFF", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[0],
    frozenset({"#FFFFE9E5", "#FFFFF6F3", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[1],
    frozenset({"#FFF0F2F5", "#FFF8F9FA", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[2],
    frozenset({"#FFE5F6FF", "#FFF4FBFF", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[2],
    frozenset({"#FFE7F8EE", "#FFF5FCF8", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[3],
    frozenset({"#FFFFEDD8", "#FFFFF8EF", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[4],
    frozenset({"#FFF1E8FF", "#FFFAF6FF", "#FFFFFFFF"}): ROOT_LINEAR_GRADIENT_PALETTES[5],
}


def _with_design_aliases(
    designs: dict[str, dict[str, Any]],
    aliases: dict[str, str],
) -> dict[str, dict[str, Any]]:
    merged = copy.deepcopy(designs)
    for alias, source in aliases.items():
        merged[alias] = copy.deepcopy(merged[source])
    return merged


_TEXT_DESIGNS: dict[str, dict[str, Any]] = {
    "display-l": {"fontSize": 56, "fontWeight": 300},
    "display-m": {"fontSize": 48, "fontWeight": 300},
    "display-s": {"fontSize": 36, "fontWeight": 700},
    "title-l": {"fontSize": 30, "fontWeight": 700},
    "title-m": {"fontSize": 24, "fontWeight": 700},
    "title-s": {"fontSize": 20, "fontWeight": 700},
    "subtitle-l": {"fontSize": 18, "fontWeight": 500},
    "subtitle-m": {"fontSize": 16, "fontWeight": 500},
    "subtitle-s": {"fontSize": 14, "fontWeight": 500},
    "body-l": {"fontSize": 16, "fontWeight": 500},
    "body-m": {"fontSize": 14, "fontWeight": 400},
    "body-s": {"fontSize": 12, "fontWeight": 400},
    "caption-l": {"fontSize": 12, "fontWeight": 500},
    "caption-m": {"fontSize": 10, "fontWeight": 500},
    "card-title": {"fontSize": 14, "fontWeight": 500},
    "hero-value": {"fontSize": 30, "fontWeight": 700},
    "hero-unit": {"fontSize": 16, "fontWeight": 700},
    "hero-label": {"fontSize": 12, "fontWeight": 400},
    "meta-text": {"fontSize": 12, "fontWeight": 400},
}
_TEXT_DESIGNS = _with_design_aliases(
    _TEXT_DESIGNS,
    {
        "TitleBar.title": "card-title",
        "HeroMetric.value": "hero-value",
        "HeroMetric.unit": "hero-unit",
        "DescriptionBlock.primary": "title-s",
        "DescriptionBlock.secondary": "hero-label",
        "DescriptionBlock.meta": "meta-text",
        "MetricRow.value": "hero-value",
        "MetricRow.unit": "hero-unit",
        "StatusText.primary": "body-m",
        "StatusText.secondary": "body-s",
    },
)

_BUTTON_DESIGNS: dict[str, dict[str, Any]] = {
    "capsule": {
        "width": "matchParent",
        "height": 36,
        "borderRadius": 20,
        "padding": {"left": 8, "top": 0, "right": 8, "bottom": 0},
        "backgroundColor": "#190A59F7",
        "fontColor": "font_emphasize",
        "fontSize": 14,
        "fontWeight": 700,
        "maxFontSize": 14,
        "minFontSize": 12,
        "maxLines": 1,
        "flexShrink": 0,
    },
    "icon-round": {
        "width": ICON_ROUND_SIZE,
        "height": ICON_ROUND_SIZE,
        "borderRadius": 20,
        "padding": 0,
        "backgroundColor": "comp_background_tertiary",
        "flexShrink": 0,
    },
}
_BUTTON_DESIGNS = _with_design_aliases(
    _BUTTON_DESIGNS,
    {
        "ActionSlot.capsule": "capsule",
        "ActionSlot.iconRound": "icon-round",
    },
)

_IMAGE_DESIGNS: dict[str, dict[str, Any]] = {
    "icon-lg": {
        "width": "matchParent",
        "height": "matchParent",
        "aspectRatio": 1.0,
        "borderRadius": 8,
        "objectFit": "cover",
        "clip": True,
        "flexShrink": 0,
    },
    "source-icon": {
        "width": 20,
        "height": 20,
        "objectFit": "contain",
        "flexShrink": 0,
    },
    "hero-icon": {
        "width": 36,
        "height": 36,
        "objectFit": "contain",
        "flexShrink": 0,
    },
}
_IMAGE_DESIGNS = _with_design_aliases(
    _IMAGE_DESIGNS,
    {
        "TitleBar.icon": "source-icon",
        "LeadVisual.icon": "hero-icon",
        "LeadVisual.image": "icon-lg",
    },
)

_PROGRESS_DESIGNS: dict[str, dict[str, Any]] = {
    "linear-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "linear-bar-small": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "segmented-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "threshold-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "#6B7F91",
        "color": "#C8F000",
    },
    "ring": {
        "type": "ring",
        "width": "matchParent",
        "height": "matchParent",
        "strokeWidth": 6,
        "backgroundColor": "comp_background_secondary",
        "color": "multi_color_10",
    },
}
_PROGRESS_DESIGNS = _with_design_aliases(
    _PROGRESS_DESIGNS,
    {
        "ProgressBar.linear": "linear-bar",
        "ProgressBar.segmented": "segmented-bar",
        "ProgressBar.threshold": "threshold-bar",
        "RingProgress.track": "ring",
    },
)

_DIVIDER_DESIGNS: dict[str, dict[str, Any]] = {
    "line": {
        "strokeWidth": 1,
        "vertical": False,
        "color": "comp_divider",
    },
    "bar": {
        "strokeWidth": 8,
        "vertical": False,
        "color": "comp_background_tertiary",
    },
}
_DIVIDER_DESIGNS = _with_design_aliases(
    _DIVIDER_DESIGNS,
    {
        "Timeline.line": "line",
        "VisualDivider.bar": "bar",
    },
)

_CHECKBOX_DESIGNS: dict[str, dict[str, Any]] = {
    "default": {
        "width": 20,
        "height": 20,
        "borderRadius": 10,
        "selectedColor": "#FF0A59F7",
        "unSelectedColor": "#66000000",
        "mark": {
            "strokeColor": "#FFFFFFFF",
            "size": 20,
            "strokeWidth": 2,
        },
        "shape": "circle",
    },
    "check": {
        "width": 16,
        "height": 16,
        "borderRadius": 4,
        "selectedColor": "icon_on_fourth",
        "unSelectedColor": "icon_tertiary",
        "mark": {
            "strokeColor": "icon_on_primary",
            "size": 16,
            "strokeWidth": 2,
        },
        "shape": "rounded_square",
    },
}
_CHECKBOX_DESIGNS = _with_design_aliases(
    _CHECKBOX_DESIGNS,
    {
        "Selection.circle": "default",
        "Selection.check": "check",
    },
)

_COMPONENT_DESIGNS = {
    "Text": _TEXT_DESIGNS,
    "Image": _IMAGE_DESIGNS,
    "Button": _BUTTON_DESIGNS,
    "Progress": _PROGRESS_DESIGNS,
    "Divider": _DIVIDER_DESIGNS,
    "Checkbox": _CHECKBOX_DESIGNS,
}


def expand_component_design(component: Any) -> dict[str, Any]:
    explicit_props = copy.deepcopy(component.props)
    design = explicit_props.pop("design", None)
    if design is None:
        return explicit_props
    if not isinstance(design, str) or not design:
        raise DesignTokenConversionError(
            f"{component.component_id}: design must be a non-empty string."
        )

    if design in SURFACE_DESIGNS:
        if component.component_id != "root":
            raise DesignTokenConversionError(
                f'{component.component_id}: surface design "{design}" '
                "can only be used on root."
            )
        expanded = copy.deepcopy(SURFACE_DESIGNS[design])
        for property_name, value in explicit_props.items():
            expanded[property_name] = copy.deepcopy(value)
        return expanded

    component_designs = _COMPONENT_DESIGNS.get(component.component_type)
    if component_designs is None or design not in component_designs:
        raise DesignTokenConversionError(
            f"{component.component_id}: unsupported "
            f'{component.component_type}.design "{design}".'
        )
    expanded = copy.deepcopy(component_designs[design])
    for property_name, value in explicit_props.items():
        expanded[property_name] = copy.deepcopy(value)
    return expanded


def expand_high_level_components(
    rows: list[Any],
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    """Expand high-level Compact DSL components into primitive component rows."""
    expanded_rows: list[Any] = []
    for row in rows:
        component_type = getattr(row, "component_type", None)
        if component_type == "RingUnit":
            expanded_rows.extend(
                _expand_ring_unit(row, component_row_type=component_row_type)
            )
            continue
        if component_type == "TimelineUnit":
            expanded_rows.extend(
                _expand_timeline_unit(row, component_row_type=component_row_type)
            )
            continue
        expanded_rows.append(row)
    return expanded_rows


def normalize_ring_stack_children(
    components: list[Any],
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    """Normalize explicit Progress-ring stacks and center visual sizing."""
    component_types = {
        component.component_id: component.component_type
        for component in components
    }
    ring_center_ids: set[str] = set()
    normalized: list[Any] = []
    for component in components:
        if component.component_type != "Stack":
            normalized.append(
                _normalize_ring_center_component(
                    component,
                    ring_center_ids,
                    component_row_type=component_row_type,
                )
            )
            continue
        children = list(component.children)
        progress_ids = [
            child for child in children if component_types.get(child) == "Progress"
        ]
        image_ids = [
            child for child in children if component_types.get(child) == "Image"
        ]
        text_ids = [
            child for child in children if component_types.get(child) == "Text"
        ]
        center_ids = image_ids + text_ids
        if not progress_ids or not center_ids:
            normalized.append(component)
            continue
        reordered_ids = set(progress_ids)
        reordered_ids.update(center_ids)
        remaining_ids = [
            child
            for child in children
            if child not in reordered_ids
        ]
        ring_center_ids.update(center_ids)
        normalized.append(
            component_row_type(
                component.component_id,
                component.component_type,
                component.props,
                tuple(progress_ids + center_ids + remaining_ids),
            )
        )
    return normalized


def _normalize_ring_center_component(
    component: Any,
    ring_center_ids: set[str],
    *,
    component_row_type: Callable[..., Any],
) -> Any:
    if component.component_id not in ring_center_ids:
        return component
    props = copy.deepcopy(component.props)
    if component.component_type == "Image":
        props["width"] = 24
        props["height"] = 24
    if component.component_type == "Text":
        props["fontSize"] = 16
    return component_row_type(
        component.component_id,
        component.component_type,
        props,
        component.children,
    )


def _expand_ring_unit(
    component: Any,
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    state = component.props["state"]
    size = component.props["size"]
    ring_bar = _ring_unit_bar(
        component.component_id,
        component.props,
        component_row_type=component_row_type,
    )
    if state in _RING_UNIT_CENTER_ICON_STATES:
        return _expand_ring_without_reading(
            component,
            ring_bar,
            size,
            component_row_type=component_row_type,
        )
    if state in _RING_UNIT_CENTER_TEXT_STATES:
        return _expand_ring_center_reading(
            component,
            ring_bar,
            size,
            component_row_type=component_row_type,
        )
    return _expand_ring_with_reading(
        component,
        ring_bar,
        size,
        component_row_type=component_row_type,
    )


def _expand_ring_without_reading(
    component: Any,
    ring_bar: Any,
    size: int,
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    children = [ring_bar.component_id]
    rows = [
        component_row_type(
            component.component_id,
            "Stack",
            _ring_stack_props(size),
            tuple(children),
        ),
        ring_bar,
    ]
    center_icon = component.props.get("centerIcon")
    if center_icon is None:
        return rows
    icon = _ring_center_icon(
        component.component_id,
        center_icon,
        size,
        component_row_type=component_row_type,
    )
    children.append(icon.component_id)
    rows[0] = component_row_type(
        rows[0].component_id,
        rows[0].component_type,
        rows[0].props,
        tuple(children),
    )
    rows.append(icon)
    return rows


def _expand_ring_center_reading(
    component: Any,
    ring_bar: Any,
    size: int,
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    reading_id = _ring_child_id(component.component_id, "center_reading")
    rows = [
        component_row_type(
            component.component_id,
            "Stack",
            _ring_stack_props(size),
            (ring_bar.component_id, reading_id),
        ),
        ring_bar,
    ]
    rows.extend(
        _ring_reading_rows(
            reading_id,
            component.props["reading"],
            id_prefix=component.component_id,
            font_color=component.props.get("color"),
            component_row_type=component_row_type,
        )
    )
    return rows


def _expand_ring_with_reading(
    component: Any,
    ring_bar: Any,
    size: int,
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    stack_id = _ring_child_id(component.component_id, "ring_stack")
    reading_id = _ring_child_id(component.component_id, "reading_below")
    stack_children = [ring_bar.component_id]
    rows = [
        component_row_type(
            component.component_id,
            "Column",
            {"itemMargin": 4, "alignItems": "center", "flexShrink": 0},
            (stack_id, reading_id),
        ),
        component_row_type(
            stack_id,
            "Stack",
            _ring_stack_props(size),
            tuple(stack_children),
        ),
        ring_bar,
    ]
    center_icon = component.props.get("centerIcon")
    if center_icon is not None:
        icon = _ring_center_icon(
            component.component_id,
            center_icon,
            size,
            component_row_type=component_row_type,
        )
        stack_children.append(icon.component_id)
        rows[1] = component_row_type(
            rows[1].component_id,
            rows[1].component_type,
            rows[1].props,
            tuple(stack_children),
        )
        rows.append(icon)
    rows.extend(
        _ring_reading_rows(
            reading_id,
            component.props["reading"],
            id_prefix=component.component_id,
            font_color=component.props.get("color"),
            component_row_type=component_row_type,
        )
    )
    return rows


def _ring_unit_bar(
    component_id: str,
    props: dict[str, Any],
    *,
    component_row_type: Callable[..., Any],
) -> Any:
    bar_props = {
        "design": "ring",
        "width": "matchParent",
        "height": "matchParent",
        "value": copy.deepcopy(props["value"]),
        "total": copy.deepcopy(props["total"]),
    }
    for color_name in ("color", "backgroundColor"):
        if color_name in props:
            bar_props[color_name] = copy.deepcopy(props[color_name])
    return component_row_type(
        _ring_child_id(component_id, "ring_bar"),
        "Progress",
        bar_props,
    )


def _ring_stack_props(size: int) -> dict[str, Any]:
    return {
        "width": size,
        "height": size,
        "alignContent": "center",
        "flexShrink": 0,
    }


def _ring_center_icon(
    component_id: str,
    source: str,
    size: int,
    *,
    component_row_type: Callable[..., Any],
) -> Any:
    icon_size = 24 if size >= 52 else 20
    return component_row_type(
        _ring_child_id(component_id, "center_icon"),
        "Image",
        {
            "src": source,
            "width": icon_size,
            "height": icon_size,
            "flexShrink": 0,
        },
    )


def _ring_reading_rows(
    reading_id: str,
    reading: dict[str, Any],
    *,
    id_prefix: str,
    component_row_type: Callable[..., Any],
    font_color: Any = None,
) -> list[Any]:
    content = {"path": reading["path"]}
    unit = reading.get("unit")
    number_props = {"content": content, **copy.deepcopy(_RING_READING_NUMBER_TEXT)}
    unit_props = {"content": unit, **copy.deepcopy(_RING_READING_UNIT_TEXT)}
    if isinstance(font_color, str) and font_color:
        number_props["fontColor"] = font_color
        unit_props["fontColor"] = font_color
    if unit is None or unit == "":
        return [
            component_row_type(
                reading_id,
                "Text",
                number_props,
            )
        ]

    num_id = _ring_child_id(id_prefix, "reading_num")
    unit_id = _ring_child_id(id_prefix, "reading_unit")
    return [
        component_row_type(
            reading_id,
            "Row",
            {"alignItems": "bottom", "flexShrink": 0, "itemMargin": 0},
            (num_id, unit_id),
        ),
        component_row_type(
            num_id,
            "Text",
            number_props,
        ),
        component_row_type(
            unit_id,
            "Text",
            unit_props,
        ),
    ]


def _ring_child_id(component_id: str, suffix: str) -> str:
    return f"{component_id}_{suffix}"


def _expand_timeline_unit(
    component: Any,
    *,
    component_row_type: Callable[..., Any],
) -> list[Any]:
    height = _numeric_prop(component.props.get("height"), default=68)
    line_height = max(height - 16, 1)
    color = component.props.get("color", _TIMELINE_UNIT_DEFAULT_COLOR)
    line_color = component.props.get(
        "lineColor",
        _TIMELINE_UNIT_DEFAULT_LINE_COLOR,
    )
    dot_id = f"{component.component_id}_dot"
    line_id = f"{component.component_id}_line"
    return [
        component_row_type(
            component.component_id,
            "Column",
            {
                "width": component.props.get("width", 16),
                "height": height,
                "alignItems": "center",
                "justifyContent": "start",
                "flexShrink": component.props.get("flexShrink", 0),
            },
            (dot_id, line_id),
        ),
        component_row_type(
            dot_id,
            "Text",
            {
                "content": "",
                "width": 14,
                "height": 14,
                "borderRadius": 7,
                "borderWidth": 4,
                "borderColor": color,
                "backgroundColor": "#00FFFFFF",
                "flexShrink": 0,
            },
        ),
        component_row_type(
            line_id,
            "Divider",
            {
                "width": 1,
                "height": line_height,
                "vertical": True,
                "color": line_color,
                "strokeWidth": 1,
                "flexShrink": 0,
            },
        ),
    ]


def _numeric_prop(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    return default


def resolve_tokens(
    property_name: str,
    value: Any,
    component_id: str,
) -> Any:
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for child_name, child_value in value.items():
            nested_name = child_name
            if property_name in {"margin", "padding"}:
                nested_name = property_name
            resolved[child_name] = resolve_tokens(
                nested_name,
                child_value,
                component_id,
            )
        return resolved
    if isinstance(value, list):
        if property_name == "colors":
            return _resolve_gradient_stops(value, component_id)
        resolved_items: list[Any] = []
        for item in value:
            resolved_items.append(resolve_tokens(property_name, item, component_id))
        return resolved_items
    if not isinstance(value, str):
        return value
    if property_name in _COLOR_PROPERTIES:
        return _COLOR_TOKENS.get(value, value)
    if property_name in _TOKEN_AWARE_PROPERTIES:
        _reject_legacy_style_token(component_id, property_name, value)
    return value


def _resolve_gradient_stops(
    stops: list[Any],
    component_id: str,
) -> list[Any]:
    resolved_stops: list[Any] = []
    for stop in stops:
        if not isinstance(stop, list) or len(stop) != 2:
            raise DesignTokenConversionError(
                f"{component_id}: each gradient color must be [color, position]."
            )
        color, position = stop
        if not isinstance(color, str):
            raise DesignTokenConversionError(
                f"{component_id}: gradient colors must be strings."
            )
        if not isinstance(position, (int, float)):
            raise DesignTokenConversionError(
                f"{component_id}: gradient positions must be numbers."
            )
        resolved_stops.append([_COLOR_TOKENS.get(color, color), position])
    return resolved_stops


def _reject_legacy_style_token(
    component_id: str,
    property_name: str,
    value: str,
) -> None:
    is_legacy_prefix = value.startswith(_LEGACY_TOKEN_PREFIXES)
    is_legacy_font_size = value in _LEGACY_FONT_SIZE_TOKENS
    if is_legacy_prefix or is_legacy_font_size:
        raise DesignTokenConversionError(
            f'{component_id}: legacy token "{value}" is not defined by PROMPT.md '
            f"for {property_name}."
        )


def convert_action_unit(
    component: Any,
    *,
    convert_path_bindings: Callable[[Any], Any],
) -> list[dict[str, Any]]:
    state = component.props["state"]
    if state == "capsule":
        return _convert_action_unit_capsule(
            component,
            convert_path_bindings=convert_path_bindings,
        )
    return _convert_action_unit_icon_round(
        component,
        convert_path_bindings=convert_path_bindings,
    )


def _convert_action_unit_capsule(
    component: Any,
    *,
    convert_path_bindings: Callable[[Any], Any],
) -> list[dict[str, Any]]:
    icon = component.props.get("icon")
    if isinstance(icon, str) and icon:
        return _convert_action_unit_capsule_with_icon(
            component,
            icon,
            convert_path_bindings=convert_path_bindings,
        )

    converted: dict[str, Any] = {
        "id": component.component_id,
        "component": "Button",
        "label": component.props["label"],
        "onClick": convert_path_bindings(component.props["onClick"]),
    }
    if "enabled" in component.props:
        converted["enabled"] = convert_path_bindings(component.props["enabled"])
    styles = _resolved_design_styles(component.component_id, _BUTTON_DESIGNS["capsule"])
    _apply_action_background(styles, component.props)
    action_ink = component.props.get("actionInk")
    if action_ink is not None:
        styles["fontColor"] = action_ink
    converted["styles"] = styles
    return [converted]


def _convert_action_unit_capsule_with_icon(
    component: Any,
    icon_source: str,
    *,
    convert_path_bindings: Callable[[Any], Any],
) -> list[dict[str, Any]]:
    icon_id = f"{component.component_id}_icon"
    text_id = f"{component.component_id}_text"
    styles = _resolved_design_styles(component.component_id, _BUTTON_DESIGNS["capsule"])
    _apply_action_background(styles, component.props)
    text_styles = _capsule_text_styles(styles, component.props.get("actionInk"))
    row_styles = _capsule_row_styles(styles)
    row: dict[str, Any] = {
        "id": component.component_id,
        "component": "Row",
        "children": [icon_id, text_id],
        "itemMargin": CAPSULE_ICON_TEXT_GAP,
        "onClick": convert_path_bindings(component.props["onClick"]),
        "styles": row_styles,
    }
    icon_styles = {
        "width": CAPSULE_ICON_SIZE,
        "height": CAPSULE_ICON_SIZE,
        "objectFit": "contain",
        "flexShrink": 0,
    }
    if not should_preserve_original_icon_color(icon_source):
        icon_styles["fillColor"] = text_styles.get("fontColor", "#FF0A59F7")
    icon = {
        "id": icon_id,
        "component": "Image",
        "src": icon_source,
        "styles": icon_styles,
    }
    text = {
        "id": text_id,
        "component": "Text",
        "content": component.props["label"],
        "styles": text_styles,
    }
    return [row, icon, text]


def _apply_action_background(
    styles: dict[str, Any],
    props: dict[str, Any],
) -> None:
    action_background = props.get("_actionBackground")
    if isinstance(action_background, str):
        styles["backgroundColor"] = action_background
        return
    if props.get("actionSurface") == "white":
        styles["backgroundColor"] = "#FFFFFFFF"
        return
    action_ink = props.get("actionInk")
    if _is_explicit_action_ink_color(action_ink):
        styles["backgroundColor"] = _color_with_alpha(action_ink, "1A")


def _is_explicit_action_ink_color(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if value.upper() == "#FFFFFFFF":
        return False
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", value))


def _color_with_alpha(color: str, alpha: str) -> str:
    if len(color) == 9:
        return f"#{alpha}{color[-6:]}"
    if len(color) == 7:
        return f"#{alpha}{color[-6:]}"
    return "#1A0A59F7"


def _capsule_row_styles(styles: dict[str, Any]) -> dict[str, Any]:
    row_style_names = {
        "backgroundColor",
        "borderRadius",
        "flexShrink",
        "height",
        "padding",
        "width",
    }
    row_styles = {
        name: copy.deepcopy(value)
        for name, value in styles.items()
        if name in row_style_names
    }
    row_styles["justifyContent"] = "center"
    row_styles["alignItems"] = "center"
    return row_styles


def _capsule_text_styles(
    capsule_styles: dict[str, Any],
    action_ink: Any,
) -> dict[str, Any]:
    text_style_names = {
        "fontColor",
        "fontSize",
        "fontWeight",
        "maxFontSize",
        "maxLines",
        "minFontSize",
    }
    text_styles = {
        name: copy.deepcopy(value)
        for name, value in capsule_styles.items()
        if name in text_style_names
    }
    if action_ink is not None:
        text_styles["fontColor"] = action_ink
    text_styles.update(
        {
            "height": capsule_styles.get("height", 30),
            "textAlign": "center",
            "textOverflow": "clip",
            "flexShrink": 0,
        }
    )
    return text_styles


def _convert_action_unit_icon_round(
    component: Any,
    *,
    convert_path_bindings: Callable[[Any], Any],
) -> list[dict[str, Any]]:
    icon_id = f"{component.component_id}_icon"
    styles = _resolved_design_styles(component.component_id, _BUTTON_DESIGNS["icon-round"])
    normalize_icon_button_stack(styles)
    _apply_action_background(styles, component.props)
    icon_color = resolve_tokens(
        "fillColor",
        component.props.get("actionInk", "icon_emphasize"),
        component.component_id,
    )
    stack = {
        "id": component.component_id,
        "component": "Stack",
        "children": [icon_id],
        "onClick": convert_path_bindings(component.props["onClick"]),
        "styles": styles,
    }
    icon_styles = {
        "width": ICON_ROUND_ICON_SIZE,
        "height": ICON_ROUND_ICON_SIZE,
        "objectFit": "contain",
        "flexShrink": 0,
    }
    if not should_preserve_original_icon_color(component.props["icon"]):
        icon_styles["fillColor"] = icon_color
    icon = {
        "id": icon_id,
        "component": "Image",
        "src": component.props["icon"],
        "styles": icon_styles,
    }
    return [stack, icon]


def should_preserve_original_icon_color(source: Any) -> bool:
    if not isinstance(source, str):
        return False
    basename = source.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return basename in PRESERVE_ORIGINAL_COLOR_ICON_BASENAMES


def _resolved_design_styles(
    component_id: str,
    styles: dict[str, Any],
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for property_name, value in styles.items():
        resolved[property_name] = resolve_tokens(property_name, value, component_id)
    return resolved


def normalize_icon_button_stack(styles: dict[str, Any]) -> None:
    styles["alignContent"] = "center"
    styles["clip"] = True
