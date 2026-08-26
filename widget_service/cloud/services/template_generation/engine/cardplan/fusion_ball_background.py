"""Insert the cloud-only FusionBall marker for an eligible template card."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.template_generation.engine.terse_dsl_nested2_converter import Nested2Node

_CARD_CONTENT_ID = "cardContent"
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
    """Large, medium, and small ball colors read from one selected Theme."""

    large: str
    medium: str
    small: str


def build_fusion_ball_component(palette: FusionBallPalette) -> Nested2Node:
    """Return the cloud-only Tersel component carrying the Theme palette."""
    return Nested2Node(
        "FusionBall",
        (palette.large, palette.medium, palette.small),
        (),
    )


def apply_fusion_ball_component(
    card: Nested2Node,
    *,
    size: str,
    palette: FusionBallPalette | None,
) -> Nested2Node:
    """Wrap an eligible 2x2 card with a cloud-only FusionBall sibling."""
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
        (build_fusion_ball_component(palette), foreground),
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
