# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Palette calculation and A2UI expansion for fusion balls."""

from __future__ import annotations

import colorsys
import copy
import re
from dataclasses import dataclass
from typing import Any

from packaging.version import InvalidVersion, Version

from config.config import get_settings

FUSION_BALL_CONTENT_ID_PREFIX = "__genui_render_component__"
FUSION_BALL_MIN_PRD_VERSION_CONFIG = "fusion_ball_min_prd_version"
FUSION_BALL_BASE_SIZE = 160
FUSION_BALL_DESIGN_TOKENS = (
    "fusion-ball-schedule-cool",
    "fusion-ball-schedule-warm",
    "fusion-ball-sleep-violet",
    "fusion-ball-sport-orange",
)

_BASE_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
_ARGB_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{8}$")
_FUSION_ROOT_TYPES = frozenset({"Row", "Column", "Stack"})
_DESIGN_TOKEN_BASE_COLORS = {
    "fusion-ball-schedule-cool": "#FF2BA2D9",
    "fusion-ball-schedule-warm": "#FFFF5533",
    "fusion-ball-sport-orange": "#FFFF8833",
}
_DESIGN_TOKEN_FIXED_PALETTES = {
    "fusion-ball-sleep-violet": ("#FF121E59", "#FF2BA2D9", "#FF52CCCC"),
}
_FUSION_CAPSULE_BACKGROUND = "#33FFFFFF"
_FUSION_CAPSULE_TEXT = "#E6FFFFFF"
_FUSION_CAPSULE_ICON = "#99FFFFFF"
_FUSION_CAPSULE_HEIGHT = 36
_FUSION_CAPSULE_BORDER_RADII = frozenset({18, 20})
_BACKGROUND_STYLE_KEYS = frozenset(
    {
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "linearGradient",
    }
)
_FUSION_COMPONENT_IDS = frozenset(
    {
        "fusionBallBackground",
        "fusionBallLargeSlot",
        "fusionBallLarge",
        "fusionBallMediumSlot",
        "fusionBallMedium",
        "fusionBallSmallSlot",
        "fusionBallSmall",
        "fusionBallGlassLayer",
    }
)


class FusionBallExpansionError(ValueError):
    """Raised when fusion-ball colors or component expansion are invalid."""


@dataclass(frozen=True)
class FusionBallPalette:
    """Large, medium, and small opaque ARGB ball colors."""

    large: str
    medium: str
    small: str


def fusion_ball_enabled(prd_ver: Any) -> bool:
    """按配置最低版本和请求 prdVer 以失效关闭方式裁决融球。"""
    minimum = get_settings().CONFIG.get(FUSION_BALL_MIN_PRD_VERSION_CONFIG)
    if not isinstance(prd_ver, str) or not isinstance(minimum, str):
        return False
    if not prd_ver or not minimum:
        return False
    try:
        requested_version = Version(prd_ver)
        minimum_version = Version(minimum)
    except InvalidVersion:
        return False
    return requested_version >= minimum_version


def build_fusion_ball_content_id(original_id: str) -> str:
    """Prefix the original content id with the renderer overflow marker."""
    if not isinstance(original_id, str) or not original_id:
        raise FusionBallExpansionError("Fusion-ball content id must be a non-empty string.")
    if original_id.startswith(FUSION_BALL_CONTENT_ID_PREFIX):
        return original_id
    return f"{FUSION_BALL_CONTENT_ID_PREFIX}{original_id}"


def fusion_ball_relative_size(
    size: int,
    parent_size: int = FUSION_BALL_BASE_SIZE,
) -> str:
    """Convert one fusion-ball dimension to a percentage of its direct parent."""
    percentage = f"{size * 100 / parent_size:.6f}".rstrip("0").rstrip(".")
    return f"{percentage}%"


def build_fusion_ball_palette(
    large_color: str,
    medium_color: str,
    small_color: str,
) -> FusionBallPalette:
    """Build a palette from explicit large, medium, and small ARGB colors."""
    colors = (large_color, medium_color, small_color)
    if not all(isinstance(color, str) and _ARGB_COLOR_PATTERN.fullmatch(color) for color in colors):
        raise FusionBallExpansionError("Fusion-ball colors must use #AARRGGBB.")
    return FusionBallPalette(*(color.upper() for color in colors))


def derive_fusion_ball_palette(base_color: str) -> FusionBallPalette:
    """Use the base color as medium and derive large/small colors in HSB space."""
    red, green, blue = _parse_base_color(base_color)
    hue, saturation, brightness = colorsys.rgb_to_hsv(
        red / 255,
        green / 255,
        blue / 255,
    )
    hue_degrees = hue * 360
    return FusionBallPalette(
        large=_hsb_color(hue_degrees + 25, saturation * 100, brightness * 100 - 40),
        medium=_rgb_color(red, green, blue),
        small=_hsb_color(hue_degrees - 25, saturation * 100 + 25, brightness * 100),
    )


def fusion_ball_palette_for_root(
    components: list[Any],
    *,
    size: str,
    app_version: Any,
) -> FusionBallPalette | None:
    """Resolve a root fusion Style Design Token for supported 2x2 cards."""
    if size != "2x2" or not fusion_ball_enabled(app_version):
        return None
    roots = [item for item in components if _component_id(item) == "root"]
    if len(roots) != 1:
        return None
    root = roots[0]
    component_type = getattr(root, "component_type", None)
    props = getattr(root, "props", None)
    if isinstance(root, dict):
        component_type = root.get("component_type")
        props = root.get("props")
    if component_type not in _FUSION_ROOT_TYPES or not isinstance(props, dict):
        return None
    design_token = props.get("design")
    if not isinstance(design_token, str):
        return None
    fixed_palette = _DESIGN_TOKEN_FIXED_PALETTES.get(design_token)
    if fixed_palette is not None:
        return build_fusion_ball_palette(*fixed_palette)
    base_color = _DESIGN_TOKEN_BASE_COLORS.get(design_token)
    if base_color is None:
        return None
    return derive_fusion_ball_palette(base_color)


def expand_fusion_ball_components(
    components: list[dict[str, Any]],
    palette: FusionBallPalette,
) -> list[dict[str, Any]]:
    """Wrap a converted A2UI root with the deterministic fusion-ball background."""
    copied = copy.deepcopy(components)
    roots = [item for item in copied if item.get("id") == "root"]
    if len(roots) != 1:
        raise FusionBallExpansionError("A2UI components must contain exactly one root.")
    root = roots[0]
    if root.get("component") not in _FUSION_ROOT_TYPES:
        raise FusionBallExpansionError("Fusion-ball root must be Row, Column, or Stack.")
    original_root_id = root.get("id")
    if not isinstance(original_root_id, str):
        raise FusionBallExpansionError("Fusion-ball root id must be a string.")
    content_id = build_fusion_ball_content_id(original_root_id)
    _validate_component_ids(copied, content_id)

    foreground = copy.deepcopy(root)
    foreground["id"] = content_id
    foreground_styles = foreground.get("styles")
    if not isinstance(foreground_styles, dict):
        foreground_styles = {}
        foreground["styles"] = foreground_styles
    for property_name in _BACKGROUND_STYLE_KEYS:
        foreground_styles.pop(property_name, None)
    foreground_styles["width"] = "matchParent"
    foreground_styles["height"] = "matchParent"

    content_components = [foreground, *(item for item in copied if item is not root)]
    _apply_fusion_capsule_styles(content_components, content_id)

    expanded_root = {
        "id": "root",
        "component": "Stack",
        "children": ["fusionBallBackground", content_id],
        "styles": {
            "width": "matchParent",
            "height": "matchParent",
            "padding": 0,
            "borderRadius": 20,
            "clip": True,
            "backgroundColor": "#00000000",
            "alignContent": "topStart",
        },
    }
    background = _build_fusion_ball_components(palette)
    remaining = content_components[1:]
    return [expanded_root, *background, foreground, *remaining]


def _apply_fusion_capsule_styles(
    components: list[dict[str, Any]],
    content_id: str,
) -> None:
    components_by_id = {
        item.get("id"): item for item in components if isinstance(item.get("id"), str)
    }
    content_ids = _collect_descendant_ids(components_by_id, content_id)
    for component_id in content_ids:
        component = components_by_id.get(component_id)
        if not isinstance(component, dict) or not _is_capsule_action_component(component):
            continue
        styles = component.setdefault("styles", {})
        if not isinstance(styles, dict):
            continue
        component_type = component.get("component")
        if component_type == "Button":
            styles["backgroundColor"] = _FUSION_CAPSULE_BACKGROUND
            styles["fontColor"] = _FUSION_CAPSULE_TEXT
            continue
        if component_type != "Row":
            continue
        styles["backgroundColor"] = _FUSION_CAPSULE_BACKGROUND
        for child_id in component.get("children") or []:
            child = components_by_id.get(child_id)
            if not isinstance(child, dict):
                continue
            child_styles = child.setdefault("styles", {})
            if not isinstance(child_styles, dict):
                continue
            if child.get("component") == "Text":
                child_styles["fontColor"] = _FUSION_CAPSULE_TEXT
            elif child.get("component") == "Image":
                child_styles["fillColor"] = _FUSION_CAPSULE_ICON


def _collect_descendant_ids(
    components_by_id: dict[str, dict[str, Any]],
    root_id: str,
) -> set[str]:
    visited: set[str] = set()
    stack = [root_id]
    while stack:
        component_id = stack.pop()
        if component_id in visited:
            continue
        visited.add(component_id)
        component = components_by_id.get(component_id)
        if not isinstance(component, dict):
            continue
        children = component.get("children")
        if isinstance(children, list):
            stack.extend(child_id for child_id in children if isinstance(child_id, str))
    return visited


def _is_capsule_action_component(component: dict[str, Any]) -> bool:
    if "onClick" not in component:
        return False
    if component.get("component") not in {"Button", "Row"}:
        return False
    styles = component.get("styles")
    if not isinstance(styles, dict):
        return False
    return (
        styles.get("height") == _FUSION_CAPSULE_HEIGHT
        and styles.get("borderRadius") in _FUSION_CAPSULE_BORDER_RADII
    )


def _component_id(component: Any) -> str | None:
    component_id = getattr(component, "component_id", None)
    if isinstance(component_id, str):
        return component_id
    if isinstance(component, dict):
        value = component.get("component_id")
        if isinstance(value, str):
            return value
    return None


def _validate_component_ids(
    components: list[dict[str, Any]],
    content_id: str,
) -> None:
    component_ids: list[str] = []
    for component in components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            raise FusionBallExpansionError("A2UI component id must be a non-empty string.")
        component_ids.append(component_id)
    if len(component_ids) != len(set(component_ids)):
        raise FusionBallExpansionError("A2UI component ids must be unique.")
    reserved_ids = _FUSION_COMPONENT_IDS | {content_id}
    conflicts = sorted(set(component_ids) & reserved_ids)
    if conflicts:
        raise FusionBallExpansionError(
            f"Fusion-ball component ids already exist: {', '.join(conflicts)}."
        )


def _build_fusion_ball_components(palette: FusionBallPalette) -> list[dict[str, Any]]:
    return [
        _stack(
            "fusionBallBackground",
            [
                "fusionBallLargeSlot",
                "fusionBallMediumSlot",
                "fusionBallSmallSlot",
                "fusionBallGlassLayer",
            ],
            width=fusion_ball_relative_size(160),
            height=fusion_ball_relative_size(160),
            borderRadius=20,
            alignContent="topStart",
            clip=True,
        ),
        _stack(
            "fusionBallLargeSlot",
            ["fusionBallLarge"],
            width=fusion_ball_relative_size(180),
            height=fusion_ball_relative_size(44),
            alignContent="center",
        ),
        _ball(
            "fusionBallLarge",
            210,
            palette.large,
            parent_width=180,
            parent_height=44,
        ),
        _stack(
            "fusionBallMediumSlot",
            ["fusionBallMedium"],
            width=fusion_ball_relative_size(80),
            height=fusion_ball_relative_size(220),
            alignContent="bottom",
        ),
        _ball(
            "fusionBallMedium",
            160,
            palette.medium,
            parent_width=80,
            parent_height=220,
        ),
        _stack(
            "fusionBallSmallSlot",
            ["fusionBallSmall"],
            width=fusion_ball_relative_size(195),
            height=fusion_ball_relative_size(190),
            alignContent="bottomEnd",
        ),
        _ball(
            "fusionBallSmall",
            100,
            palette.small,
            parent_width=195,
            parent_height=190,
        ),
        {
            "id": "fusionBallGlassLayer",
            "component": "Divider",
            "styles": {
                "width": fusion_ball_relative_size(160),
                "height": fusion_ball_relative_size(160),
                "strokeWidth": 0,
                "color": "#00000000",
                "backgroundColor": "#0DFFFFFF",
                "backdropBlur": {"radius": 120},
            },
        },
    ]


def _stack(
    component_id: str,
    children: list[str],
    **styles: Any,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Stack",
        "children": children,
        "styles": styles,
    }


def _ball(
    component_id: str,
    diameter: int,
    color: str,
    *,
    parent_width: int,
    parent_height: int,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Divider",
        "styles": {
            "width": fusion_ball_relative_size(diameter, parent_width),
            "height": fusion_ball_relative_size(diameter, parent_height),
            "strokeWidth": 0,
            "color": "#00000000",
            "borderRadius": diameter // 2,
            "backgroundColor": color,
            "clip": True,
        },
    }


def _parse_base_color(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or _BASE_COLOR_PATTERN.fullmatch(value) is None:
        raise FusionBallExpansionError("base_color must use #RRGGBB or #AARRGGBB.")
    rgb = value[3:] if len(value) == 9 else value[1:]
    return int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)


def _hsb_color(hue: float, saturation: float, brightness: float) -> str:
    normalized_hue = hue % 360 / 360
    normalized_saturation = _clamp_percentage(saturation) / 100
    normalized_brightness = _clamp_percentage(brightness) / 100
    channels = colorsys.hsv_to_rgb(
        normalized_hue,
        normalized_saturation,
        normalized_brightness,
    )
    return _rgb_color(*(round(channel * 255) for channel in channels))


def _rgb_color(red: int, green: int, blue: int) -> str:
    return f"#FF{red:02X}{green:02X}{blue:02X}"


def _clamp_percentage(value: float) -> float:
    return max(0.0, min(100.0, value))
