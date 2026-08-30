"""Build Theme-owned deterministic 2x2 fusion-ball backgrounds."""

from __future__ import annotations

from typing import Any

from services.fusion_ball_expander import (
    FUSION_BALL_CONTENT_ID,
    FusionBallPalette,
)
from services.template_generation.engine.tersel_converter import Nested2Node

_ROOT_ID = "root"
_SKELETON_LAYOUT_TYPES = frozenset({"Column", "Row", "Stack"})
_BACKGROUND_STYLE_KEYS = frozenset(
    {
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "linearGradient",
    }
)


def build_fusion_ball_background(palette: FusionBallPalette) -> Nested2Node:
    """Return the expanded fusion-ball Tersel background tree for a 160vp card."""
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
                "Divider",
                (
                    {
                        "_id": "fusionBallGlassLayer",
                        "width": 160,
                        "height": 160,
                        "strokeWidth": 0,
                        "color": "#00000000",
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
) -> Nested2Node:
    """Expand an eligible 2x2 card into standard Tersel components."""
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
            "width": 160,
            "height": 160,
        }
    )
    foreground = Nested2Node(
        card.component_type,
        (foreground_options,),
        card.children,
    )
    root_options = {
        "_id": _ROOT_ID,
        "padding": 0,
        "borderRadius": 18,
        "alignContent": "topStart",
        "clip": True,
        "backgroundColor": "#00000000",
    }
    return Nested2Node(
        "Stack",
        ("card", root_options),
        (build_fusion_ball_background(palette), foreground),
    )


def _ball(component_id: str, diameter: int, color: str) -> Nested2Node:
    return Nested2Node(
        "Divider",
        (
            {
                "_id": component_id,
                "width": diameter,
                "height": diameter,
                "strokeWidth": 0,
                "color": "#00000000",
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


def mark_fusion_ball_content_skeleton(skeleton: Nested2Node) -> Nested2Node:
    """Place the overflow marker on the layout inside the 12vp card inset."""
    if skeleton.component_type not in _SKELETON_LAYOUT_TYPES:
        raise ValueError("Fusion-ball content skeleton must be Column, Row, or Stack.")
    values = list(skeleton.values)
    if values and isinstance(values[-1], dict):
        options = dict(values[-1])
        options["_id"] = FUSION_BALL_CONTENT_ID
        values[-1] = options
    else:
        values.append({"_id": FUSION_BALL_CONTENT_ID})
    return Nested2Node(
        skeleton.component_type,
        tuple(values),
        skeleton.children,
    )
