"""Build Theme-owned deterministic 2x2 fusion-ball backgrounds."""

from __future__ import annotations

from services.fusion_ball_expander import (
    FusionBallPalette,
    build_fusion_ball_content_id,
    fusion_ball_relative_size,
)
from services.template_generation.engine.tersel_converter import Nested2Node

_ROOT_ID = "root"
_CONTENT_ROOT_ID = "root_1"
_TEMPLATE_ROOT_ID = "template_root"
_SKELETON_LAYOUT_TYPES = frozenset({"Column", "Row", "Stack"})


def build_fusion_ball_background(palette: FusionBallPalette) -> Nested2Node:
    """Return the expanded fusion-ball Tersel background tree for a 160vp card."""
    large_ball = _ball(
        "fusionBallLarge",
        210,
        palette.large,
        parent_width=180,
        parent_height=44,
    )
    medium_ball = _ball(
        "fusionBallMedium",
        160,
        palette.medium,
        parent_width=80,
        parent_height=220,
    )
    small_ball = _ball(
        "fusionBallSmall",
        100,
        palette.small,
        parent_width=195,
        parent_height=190,
    )
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": "fusionBallBackground",
                "width": fusion_ball_relative_size(160),
                "height": fusion_ball_relative_size(160),
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
                        "width": fusion_ball_relative_size(160),
                        "height": fusion_ball_relative_size(160),
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
    _validate_root_card(card)
    skeleton = _content_skeleton(card)
    overflow_content = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": build_fusion_ball_content_id(_TEMPLATE_ROOT_ID),
                "width": "matchParent",
                "height": "matchParent",
            },
        ),
        (skeleton,),
    )
    foreground = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": _TEMPLATE_ROOT_ID,
                "padding": 12,
            },
        ),
        (overflow_content,),
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


def _ball(
    component_id: str,
    diameter: int,
    color: str,
    *,
    parent_width: int,
    parent_height: int,
) -> Nested2Node:
    return Nested2Node(
        "Divider",
        (
            {
                "_id": component_id,
                "width": fusion_ball_relative_size(diameter, parent_width),
                "height": fusion_ball_relative_size(diameter, parent_height),
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
                "width": fusion_ball_relative_size(width),
                "height": fusion_ball_relative_size(height),
                "alignContent": alignment,
            },
        ),
        (ball,),
    )


def _validate_root_card(card: Nested2Node) -> None:
    is_card_root = (
        card.component_type == "Column"
        and len(card.values) == 2
        and card.values[0] == "card"
        and isinstance(card.values[1], dict)
    )
    if not is_card_root:
        raise ValueError('Fusion-ball wrapping requires Column("card", options, ...).')


def _content_skeleton(card: Nested2Node) -> Nested2Node:
    if len(card.children) != 1:
        raise ValueError("Fusion-ball template root must contain one content skeleton.")
    skeleton = card.children[0]
    if skeleton.component_type not in _SKELETON_LAYOUT_TYPES:
        raise ValueError("Fusion-ball content skeleton must be Column, Row, or Stack.")
    values = list(skeleton.values)
    if values and isinstance(values[-1], dict):
        options = dict(values[-1])
        options["_id"] = _CONTENT_ROOT_ID
        values[-1] = options
    else:
        values.append({"_id": _CONTENT_ROOT_ID})
    return Nested2Node(
        skeleton.component_type,
        tuple(values),
        skeleton.children,
    )
