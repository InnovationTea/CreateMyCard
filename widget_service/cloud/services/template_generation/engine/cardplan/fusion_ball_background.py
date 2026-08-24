"""Build the deterministic 2x2 fusion-ball background Terse tree."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from typing import Any

from services.template_generation.engine.terse_dsl_nested2_converter import Nested2Node

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")
_BACKGROUND_STYLE_KEYS = frozenset(
    {
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "linearGradient",
    }
)


@dataclass(frozen=True)
class FusionBallPalette:
    """Opaque colors derived from one theme color in HSB space."""

    large: str
    medium: str
    small: str


def build_fusion_ball_palette(theme_color: str) -> FusionBallPalette:
    """Derive the three ball colors from ``theme_color`` using HSB deltas."""
    red, green, blue = _parse_theme_color(theme_color)
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


def build_fusion_ball_background(theme_color: str) -> Nested2Node:
    """Return the standalone fusion-ball Terse background tree for a 160vp card."""
    palette = build_fusion_ball_palette(theme_color)
    large_ball = _ball("fusionBallLarge", 210, palette.large)
    medium_ball = _ball("fusionBallMedium", 160, palette.medium)
    small_ball = _ball("fusionBallSmall", 100, palette.small)
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": "fusionBallBackground",
                "width": 160,
                "height": 160,
                "borderRadius": 18,
                "alignContent": "topStart",
                "clip": True,
            },
        ),
        (
            _ball_slot("fusionBallLargeSlot", 180, 44, "center", large_ball),
            _ball_slot("fusionBallMediumSlot", 80, 220, "bottom", medium_ball),
            _ball_slot("fusionBallSmallSlot", 195, 190, "bottomEnd", small_ball),
            Nested2Node(
                "Stack",
                (
                    "overlay",
                    {
                        "_id": "fusionBallGlassLayer",
                        "width": 160,
                        "height": 160,
                        "backgroundColor": "#0DFFFFFF",
                        "backdropBlur": {"radius": 120},
                    },
                ),
                (),
            ),
        ),
    )


def apply_fusion_ball_background(
    card: Nested2Node,
    *,
    size: str,
    theme_color: str,
) -> Nested2Node:
    """Wrap a 2x2 card with the background; leave every other size unchanged."""
    if size != "2x2":
        return card
    card_options = _root_card_options(card)
    foreground_options = {
        key: value
        for key, value in card_options.items()
        if key not in _BACKGROUND_STYLE_KEYS and key != "_id"
    }
    foreground_options.update(
        {
            "_id": "cardContent",
            "width": 160,
            "height": 160,
        }
    )
    foreground = Nested2Node(card.component_type, (foreground_options,), card.children)
    root_options = {
        "_id": "root",
        "padding": 0,
        "borderRadius": 18,
        "alignContent": "topStart",
        "clip": True,
    }
    return Nested2Node(
        "Stack",
        ("card", root_options),
        (build_fusion_ball_background(theme_color), foreground),
    )


def theme_color_from_root_styles(root_styles: dict[str, Any]) -> str:
    """Resolve the existing theme accent used as the fusion-ball medium color."""
    gradient = root_styles.get("linearGradient")
    colors = gradient.get("colors") if isinstance(gradient, dict) else None
    candidates: list[Any] = []
    if isinstance(colors, list):
        candidates.extend(stop[0] for stop in colors if isinstance(stop, list) and len(stop) == 2)
    candidates.append(root_styles.get("backgroundColor"))
    for candidate in candidates:
        if isinstance(candidate, str) and _HEX_COLOR.fullmatch(candidate):
            red, green, blue = _parse_theme_color(candidate)
            return _rgb_color(red, green, blue)
    raise ValueError("Theme root styles do not contain a supported theme color.")


def _ball(component_id: str, diameter: int, color: str) -> Nested2Node:
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": component_id,
                "width": diameter,
                "height": diameter,
                "borderRadius": diameter // 2,
                "backgroundColor": color,
                "clip": True,
            },
        ),
        (),
    )


def _ball_slot(
    component_id: str,
    width: int,
    height: int,
    alignment: str,
    ball: Nested2Node,
) -> Nested2Node:
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": component_id,
                "width": width,
                "height": height,
                "alignContent": alignment,
            },
        ),
        (ball,),
    )


def _root_card_options(card: Nested2Node) -> dict[str, Any]:
    is_card_root = (
        card.component_type == "Column"
        and len(card.values) == 2
        and card.values[0] == "card"
        and isinstance(card.values[1], dict)
    )
    if not is_card_root:
        raise ValueError('Fusion-ball wrapping requires Column("card", options, ...).')
    return dict(card.values[1])


def _parse_theme_color(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
        raise ValueError("theme_color must use #RRGGBB or #AARRGGBB.")
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
