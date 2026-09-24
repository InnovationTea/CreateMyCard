"""Build Theme-owned deterministic 2x2/2x4 fusion-ball backgrounds."""

from __future__ import annotations

from services.fusion_ball_expander import (
    FUSION_BALL_SIZES,
    FusionBallPalette,
    build_fusion_ball_content_id,
    fusion_ball_layout,
    fusion_ball_relative_size,
)
from services.template_generation.engine.tersel_converter import Nested2Node

_ROOT_ID = "root"
_CONTENT_ROOT_ID = "root_1"
_TEMPLATE_ROOT_ID = "template_root"
_SKELETON_LAYOUT_TYPES = frozenset({"Column", "Row", "Stack"})


def build_fusion_ball_background(
    palette: FusionBallPalette,
    *,
    size: str = "2x2",
) -> Nested2Node:
    """Return the expanded fusion-ball Tersel background tree for one card size."""
    (canvas_width, canvas_height), slots = fusion_ball_layout(size)
    ball_colors = {
        "fusionBallLarge": palette.large,
        "fusionBallMedium": palette.medium,
        "fusionBallSmall": palette.small,
    }
    slot_nodes: list[Nested2Node] = []
    for slot_id, ball_id, slot_width, slot_height, alignment, diameter in slots:
        ball_color = ball_colors.get(ball_id)
        if ball_color is None:
            raise KeyError(f"Unknown fusion-ball component id: {ball_id}")
        ball = _ball(
            ball_id,
            diameter,
            ball_color,
            parent_width=slot_width,
            parent_height=slot_height,
        )
        slot_nodes.append(
            _ball_slot(
                slot_id,
                fusion_ball_relative_size(slot_width, canvas_width),
                fusion_ball_relative_size(slot_height, canvas_height),
                alignment,
                ball,
            ),
        )
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": "fusionBallBackground",
                "width": "100%",
                "height": "100%",
                "borderRadius": 18,
                "alignContent": "topStart",
                "clip": True,
            },
        ),
        (
            *slot_nodes,
            Nested2Node(
                "Divider",
                (
                    {
                        "_id": "fusionBallGlassLayer",
                        "width": "100%",
                        "height": "100%",
                        "strokeWidth": 0,
                        "color": "#00000000",
                        "backgroundColor": "#0DFFFFFF",
                        "backdropBlur": {"radius": 210},
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
    """Expand an eligible 2x2/2x4 card into standard Tersel components."""
    if size not in FUSION_BALL_SIZES or palette is None:
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
        (build_fusion_ball_background(palette, size=size), foreground),
    )


def apply_content_safe_inset(
    card: Nested2Node,
    *,
    size: str,
) -> Nested2Node:
    """Move the safe inset off a supported template skeleton and mark it for overflow."""
    if size not in {"2x2", "2x4"}:
        return card
    _validate_root_card(card)
    if len(card.children) != 1:
        return card
    if card.children[0].component_type not in _SKELETON_LAYOUT_TYPES:
        return card
    skeleton = _content_skeleton(
        card, component_id=build_fusion_ball_content_id(_CONTENT_ROOT_ID)
    )
    root_options = dict(card.values[1])
    safe_inset = root_options.pop("padding", 12)
    root_options.pop("itemMargin", None)
    root_options.pop("alignItems", None)
    root_options.pop("justifyContent", None)
    root_options["padding"] = 0
    root_options.setdefault("alignContent", "topStart")
    foreground = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": _TEMPLATE_ROOT_ID,
                "padding": safe_inset,
            },
        ),
        (skeleton,),
    )
    return Nested2Node("Stack", ("card", root_options), (foreground,))


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
    width: str,
    height: str,
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


def _validate_root_card(card: Nested2Node) -> None:
    is_card_root = (
        card.component_type == "Column"
        and len(card.values) == 2
        and card.values[0] == "card"
        and isinstance(card.values[1], dict)
    )
    if not is_card_root:
        raise ValueError('Fusion-ball wrapping requires Column("card", options, ...).')


def _content_skeleton(
    card: Nested2Node, *, component_id: str = _CONTENT_ROOT_ID
) -> Nested2Node:
    if len(card.children) != 1:
        raise ValueError("Fusion-ball template root must contain one content skeleton.")
    skeleton = card.children[0]
    if skeleton.component_type not in _SKELETON_LAYOUT_TYPES:
        raise ValueError("Fusion-ball content skeleton must be Column, Row, or Stack.")
    values = list(skeleton.values)
    if values and isinstance(values[-1], dict):
        options = dict(values[-1])
        options["_id"] = component_id
        values[-1] = options
    else:
        values.append({"_id": component_id})
    return Nested2Node(
        skeleton.component_type,
        tuple(values),
        skeleton.children,
    )
