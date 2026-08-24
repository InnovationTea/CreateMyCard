"""Convert complete A2UI to the fusion-ball form using only Python's standard library.

This file is intentionally self-contained so it can be copied into another project.
"""

from __future__ import annotations

import colorsys
import copy
import json
import re
from typing import Any

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
        "cardContent",
    }
)
_BACKGROUND_STYLE_KEYS = ("backgroundColor", "linearGradient")
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?$")

__all__ = ["FusionBallA2UIConversionError", "convert_a2ui_with_fusion_ball"]


class FusionBallA2UIConversionError(ValueError):
    """Raised when the input is not a supported complete A2UI card."""


def convert_a2ui_with_fusion_ball(a2ui: str, base_color: str) -> str:
    """Replace a Stack root's solid or gradient background using ``base_color``."""
    messages = _parse_complete_a2ui(a2ui)
    update_components = messages[1]["updateComponents"]
    components = update_components.get("components")
    root_id = update_components.get("root")
    if not isinstance(components, list) or not components:
        raise FusionBallA2UIConversionError("updateComponents.components must be non-empty.")
    if not isinstance(root_id, str) or not root_id:
        raise FusionBallA2UIConversionError("updateComponents.root must be a component id.")

    root_index, root = _find_root(components, root_id)
    if _already_has_fusion_background(root, components):
        return a2ui
    if root.get("component") != "Stack":
        raise FusionBallA2UIConversionError("The A2UI root component must be Stack.")
    root_styles = root.get("styles")
    root_children = root.get("children")
    if not isinstance(root_styles, dict):
        raise FusionBallA2UIConversionError("The Stack root styles must be an object.")
    if not isinstance(root_children, list) or not all(
        isinstance(child_id, str) and child_id for child_id in root_children
    ):
        raise FusionBallA2UIConversionError("The Stack root children must be an id array.")
    if root_styles.get("backgroundImage") not in (None, ""):
        raise FusionBallA2UIConversionError(
            "Fusion-ball conversion does not replace a backgroundImage."
        )
    if not any(root_styles.get(key) not in (None, "", {}) for key in _BACKGROUND_STYLE_KEYS):
        raise FusionBallA2UIConversionError(
            "The Stack root must contain backgroundColor or linearGradient."
        )

    component_ids = _component_ids(components)
    conflicts = sorted(component_ids & _FUSION_COMPONENT_IDS)
    if conflicts:
        raise FusionBallA2UIConversionError(
            f"Fusion-ball component ids already exist: {', '.join(conflicts)}."
        )

    outer_root, card_content = _split_root(root)
    try:
        fusion_components = _build_fusion_components(base_color)
    except ValueError as exc:
        raise FusionBallA2UIConversionError("base_color must use #RRGGBB or #AARRGGBB.") from exc
    components[root_index : root_index + 1] = [
        outer_root,
        *fusion_components,
        card_content,
    ]
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) for message in messages
    )


def _parse_complete_a2ui(a2ui: str) -> list[dict[str, Any]]:
    if not isinstance(a2ui, str):
        raise FusionBallA2UIConversionError("A2UI input must be a JSONL string.")
    lines = [line.strip() for line in a2ui.splitlines() if line.strip()]
    if len(lines) != 3:
        raise FusionBallA2UIConversionError("Complete A2UI must contain exactly three messages.")
    messages: list[dict[str, Any]] = []
    expected_bodies = ("createSurface", "updateComponents", "updateDataModel")
    for line_number, (line, expected_body) in enumerate(
        zip(lines, expected_bodies, strict=True),
        1,
    ):
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FusionBallA2UIConversionError(
                f"A2UI line {line_number} is not valid JSON."
            ) from exc
        if not isinstance(message, dict):
            raise FusionBallA2UIConversionError(f"A2UI line {line_number} must be a JSON object.")
        body = message.get(expected_body)
        if message.get("version") != "v0.9" or not isinstance(body, dict):
            raise FusionBallA2UIConversionError(
                f"A2UI line {line_number} must contain {expected_body} with version v0.9."
            )
        messages.append(message)
    return messages


def _find_root(
    components: list[Any],
    root_id: str,
) -> tuple[int, dict[str, Any]]:
    matches = [
        (index, component)
        for index, component in enumerate(components)
        if isinstance(component, dict) and component.get("id") == root_id
    ]
    if len(matches) != 1:
        raise FusionBallA2UIConversionError("A2UI must contain exactly one root component.")
    return matches[0]


def _already_has_fusion_background(
    root: dict[str, Any],
    components: list[Any],
) -> bool:
    children = root.get("children")
    component_ids = _component_ids(components)
    return (
        isinstance(children, list)
        and children[:1] == ["fusionBallBackground"]
        and _FUSION_COMPONENT_IDS <= component_ids
    )


def _component_ids(components: list[Any]) -> set[str]:
    return {
        component_id
        for component in components
        if isinstance(component, dict)
        for component_id in (component.get("id"),)
        if isinstance(component_id, str) and component_id
    }


def _split_root(root: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    outer_root = copy.deepcopy(root)
    card_content = copy.deepcopy(root)
    outer_styles = outer_root["styles"]
    content_styles = card_content["styles"]
    for key in _BACKGROUND_STYLE_KEYS:
        outer_styles.pop(key, None)
        content_styles.pop(key, None)
    outer_styles["padding"] = 0
    outer_styles["alignContent"] = "topStart"
    outer_root["children"] = ["fusionBallBackground", "cardContent"]

    card_content["id"] = "cardContent"
    card_content.pop("onClick", None)
    card_content.pop("accessibility", None)
    content_styles.setdefault("width", "matchParent")
    content_styles.setdefault("height", "matchParent")
    return outer_root, card_content


def _build_fusion_components(base_color: str) -> list[dict[str, Any]]:
    large_color, medium_color, small_color = _build_fusion_palette(base_color)
    return [
        _stack(
            "fusionBallBackground",
            [
                "fusionBallLargeSlot",
                "fusionBallMediumSlot",
                "fusionBallSmallSlot",
                "fusionBallGlassLayer",
            ],
            width=160,
            height=160,
            borderRadius=18,
            alignContent="topStart",
            clip=True,
        ),
        _stack(
            "fusionBallLargeSlot",
            ["fusionBallLarge"],
            width=180,
            height=44,
            alignContent="center",
        ),
        _stack(
            "fusionBallLarge",
            [],
            width=210,
            height=210,
            borderRadius=105,
            backgroundColor=large_color,
            clip=True,
        ),
        _stack(
            "fusionBallMediumSlot",
            ["fusionBallMedium"],
            width=80,
            height=220,
            alignContent="bottom",
        ),
        _stack(
            "fusionBallMedium",
            [],
            width=160,
            height=160,
            borderRadius=80,
            backgroundColor=medium_color,
            clip=True,
        ),
        _stack(
            "fusionBallSmallSlot",
            ["fusionBallSmall"],
            width=195,
            height=190,
            alignContent="bottomEnd",
        ),
        _stack(
            "fusionBallSmall",
            [],
            width=100,
            height=100,
            borderRadius=50,
            backgroundColor=small_color,
            clip=True,
        ),
        _stack(
            "fusionBallGlassLayer",
            [],
            width=160,
            height=160,
            backgroundColor="#0DFFFFFF",
            backdropBlur={"radius": 120},
        ),
    ]


def _build_fusion_palette(base_color: str) -> tuple[str, str, str]:
    red, green, blue = _parse_base_color(base_color)
    hue, saturation, brightness = colorsys.rgb_to_hsv(
        red / 255,
        green / 255,
        blue / 255,
    )
    hue_degrees = hue * 360
    large_color = _hsb_color(
        hue_degrees + 25,
        saturation * 100,
        brightness * 100 - 40,
    )
    medium_color = _rgb_color(red, green, blue)
    small_color = _hsb_color(
        hue_degrees - 25,
        saturation * 100 + 25,
        brightness * 100,
    )
    return large_color, medium_color, small_color


def _parse_base_color(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
        raise ValueError("base_color must use #RRGGBB or #AARRGGBB.")
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


def _stack(component_id: str, children: list[str], **styles: Any) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Stack",
        "children": children,
        "styles": styles,
    }
