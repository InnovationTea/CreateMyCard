"""Build scene-gated deterministic 2x2 fusion-ball backgrounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.template_generation.engine.terse_dsl_nested2_converter import Nested2Node

_CARD_CONTENT_ID = "cardContent"
_FUSION_FOREGROUND_COLOR = "#FFFFFFFF"
_FUSION_TEXT_COLOR = "#CCFFFFFF"
_FUSION_ICON_REPLACEMENTS = {
    "resources/base/media/icon_weather1.svg": "resources/base/media/icon_weather1_foreground.svg",
}
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
    """Fixed large, medium, and small ball colors for one approved scene."""

    large: str
    medium: str
    small: str


_FUSION_BALL_PALETTES = {
    "weather": FusionBallPalette("#003399", "#0089BF", "#4174D9"),
    "health-sport": FusionBallPalette("#B33C24", "#FF8833", "#F7E6C3"),
    "sleep": FusionBallPalette("#43388C", "#5761D9", "#B398D9"),
}


def fusion_ball_palette_for_scene(scene: str | None) -> FusionBallPalette | None:
    """Resolve the fixed palette for an approved scene."""
    return _FUSION_BALL_PALETTES.get(scene) if scene is not None else None


def build_fusion_ball_background(palette: FusionBallPalette) -> Nested2Node:
    """Return the standalone fusion-ball Terse background tree for a 160vp card."""
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
    palette: FusionBallPalette | None,
    scene: str | None,
) -> Nested2Node:
    """Wrap an eligible 2x2 card; leave other sizes and scenes unchanged."""
    if size != "2x2" or palette is None:
        return card
    card_options = _root_card_options(card)
    foreground_options = {
        key: value
        for key, value in card_options.items()
        if key not in _BACKGROUND_STYLE_KEYS and key != "_id"
    }
    foreground_options.update(
        {
            "_id": _CARD_CONTENT_ID,
            "width": 160,
            "height": 160,
        }
    )
    foreground_children = tuple(
        _apply_fusion_content_foreground(
            child,
            preserve_image_foreground=scene == "weather",
        )
        for child in card.children
    )
    foreground = Nested2Node(card.component_type, (foreground_options,), foreground_children)
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
        (build_fusion_ball_background(palette), foreground),
    )


def _apply_fusion_content_foreground(
    node: Nested2Node,
    preserve_action_foreground: bool = False,
    *,
    preserve_image_foreground: bool,
) -> Nested2Node:
    """Apply fusion text color and the scene-specific content icon treatment."""
    preserve_here = preserve_action_foreground or (
        node.component_type == "Stack"
        and any(isinstance(value, dict) and bool(value.get("onClick")) for value in node.values)
    )
    children = tuple(
        _apply_fusion_content_foreground(
            child,
            preserve_here,
            preserve_image_foreground=preserve_image_foreground,
        )
        for child in node.children
    )
    should_style_text = (
        node.component_type == "Text" and not preserve_here and bool(node.values)
    )
    should_tint_image = (
        node.component_type == "Image"
        and not preserve_here
        and not preserve_image_foreground
        and bool(node.values)
    )
    if not should_style_text and not should_tint_image:
        return Nested2Node(node.component_type, node.values, children)

    values = list(node.values)
    if should_tint_image and isinstance(values[0], str):
        values[0] = _FUSION_ICON_REPLACEMENTS.get(values[0], values[0])
    options_index = next(
        (index for index in range(len(values) - 1, -1, -1) if isinstance(values[index], dict)),
        None,
    )
    style_name = "fontColor" if should_style_text else "fillColor"
    style_value = _FUSION_TEXT_COLOR if should_style_text else _FUSION_FOREGROUND_COLOR
    if options_index is None:
        values.append({style_name: style_value})
    else:
        options = dict(values[options_index])
        options[style_name] = style_value
        values[options_index] = options
    return Nested2Node(node.component_type, tuple(values), children)


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
