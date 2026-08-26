"""Convert complete A2UI to the fusion-ball form using only Python's standard library.

This file is intentionally self-contained so it can be copied into another project.
"""

from __future__ import annotations

import copy
import json
from typing import Any

_CARD_CONTENT_ID = "cardContent"
_LEGACY_CARD_CONTENT_ID = "__genui_render_component__cardContent"
_FUSION_BACKGROUND_COMPONENT_IDS = frozenset(
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
_FUSION_COMPONENT_IDS = _FUSION_BACKGROUND_COMPONENT_IDS | {_CARD_CONTENT_ID}
_LEGACY_FUSION_COMPONENT_IDS = _FUSION_BACKGROUND_COMPONENT_IDS | {_LEGACY_CARD_CONTENT_ID}
_RESERVED_FUSION_COMPONENT_IDS = _FUSION_COMPONENT_IDS | {_LEGACY_CARD_CONTENT_ID}
_BACKGROUND_STYLE_KEYS = ("backgroundColor", "linearGradient")
_FUSION_FOREGROUND_COLOR = "#FFFFFFFF"
_FUSION_TEXT_COLOR = "#CCFFFFFF"
_FUSION_ICON_REPLACEMENTS = {
    "resources/base/media/icon_weather1.svg": "resources/base/media/icon_weather1_foreground.svg",
}
_FUSION_BALL_PALETTES = {
    "weather": ("#003399", "#0089BF", "#4174D9"),
    "health-sport": ("#B33C24", "#FF8833", "#F7E6C3"),
    "sleep": ("#43388C", "#5761D9", "#B398D9"),
}

__all__ = ["FusionBallA2UIConversionError", "convert_a2ui_with_fusion_ball"]


class FusionBallA2UIConversionError(ValueError):
    """Raised when the input is not a supported complete A2UI card."""


def convert_a2ui_with_fusion_ball(a2ui: str, scene: str) -> str:
    """Replace a Stack root background using one approved scene palette."""
    palette = _fusion_palette(scene)
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
    if _has_legacy_fusion_background(root, components):
        _upgrade_legacy_card_content_id(root, components)
        return _serialize_messages(messages)
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
    conflicts = sorted(component_ids & _RESERVED_FUSION_COMPONENT_IDS)
    if conflicts:
        raise FusionBallA2UIConversionError(
            f"Fusion-ball component ids already exist: {', '.join(conflicts)}."
        )

    _apply_fusion_content_foreground(
        components,
        root_children,
        preserve_image_foreground=scene == "weather",
    )
    outer_root, card_content = _split_root(root)
    fusion_components = _build_fusion_components(palette)
    components[root_index : root_index + 1] = [
        outer_root,
        *fusion_components,
        card_content,
    ]
    return _serialize_messages(messages)


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
    return _has_fusion_background(root, components, _CARD_CONTENT_ID, _FUSION_COMPONENT_IDS)


def _has_legacy_fusion_background(
    root: dict[str, Any],
    components: list[Any],
) -> bool:
    return _has_fusion_background(
        root,
        components,
        _LEGACY_CARD_CONTENT_ID,
        _LEGACY_FUSION_COMPONENT_IDS,
    )


def _has_fusion_background(
    root: dict[str, Any],
    components: list[Any],
    content_id: str,
    expected_component_ids: frozenset[str],
) -> bool:
    children = root.get("children")
    component_ids = _component_ids(components)
    return (
        isinstance(children, list)
        and children == ["fusionBallBackground", content_id]
        and expected_component_ids <= component_ids
    )


def _upgrade_legacy_card_content_id(
    root: dict[str, Any],
    components: list[Any],
) -> None:
    root["children"] = ["fusionBallBackground", _CARD_CONTENT_ID]
    for component in components:
        if isinstance(component, dict) and component.get("id") == _LEGACY_CARD_CONTENT_ID:
            component["id"] = _CARD_CONTENT_ID
            return


def _serialize_messages(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) for message in messages
    )


def _component_ids(components: list[Any]) -> set[str]:
    return {
        component_id
        for component in components
        if isinstance(component, dict)
        for component_id in (component.get("id"),)
        if isinstance(component_id, str) and component_id
    }


def _apply_fusion_content_foreground(
    components: list[Any],
    root_children: list[str],
    *,
    preserve_image_foreground: bool,
) -> None:
    """Apply fusion text color and the scene-specific content icon treatment."""
    component_by_id = {
        component["id"]: component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    visited: set[str] = set()

    def visit(component_id: str, preserve_action_foreground: bool = False) -> None:
        if component_id in visited:
            return
        visited.add(component_id)
        component = component_by_id.get(component_id)
        if component is None:
            return
        preserve_here = preserve_action_foreground or bool(component.get("onClick"))
        component_type = component.get("component")
        if component_type == "Text" and not preserve_here:
            styles = component.get("styles")
            if not isinstance(styles, dict):
                styles = {}
                component["styles"] = styles
            styles["fontColor"] = _FUSION_TEXT_COLOR
        should_tint_image = (
            component_type == "Image"
            and not preserve_here
            and not preserve_image_foreground
        )
        if should_tint_image:
            source = component.get("src")
            if isinstance(source, str):
                component["src"] = _FUSION_ICON_REPLACEMENTS.get(source, source)
            styles = component.get("styles")
            if not isinstance(styles, dict):
                styles = {}
                component["styles"] = styles
            styles["fillColor"] = _FUSION_FOREGROUND_COLOR
        children = component.get("children")
        if isinstance(children, list):
            for child_id in children:
                if isinstance(child_id, str):
                    visit(child_id, preserve_here)

    for child_id in root_children:
        visit(child_id)


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
    outer_root["children"] = ["fusionBallBackground", _CARD_CONTENT_ID]

    card_content["id"] = _CARD_CONTENT_ID
    card_content.pop("onClick", None)
    card_content.pop("accessibility", None)
    content_styles.setdefault("width", "matchParent")
    content_styles.setdefault("height", "matchParent")
    return outer_root, card_content


def _fusion_palette(scene: str) -> tuple[str, str, str]:
    try:
        return _FUSION_BALL_PALETTES[scene]
    except (KeyError, TypeError) as exc:
        raise FusionBallA2UIConversionError(
            "scene must be weather, health-sport, or sleep."
        ) from exc


def _build_fusion_components(palette: tuple[str, str, str]) -> list[dict[str, Any]]:
    large_color, medium_color, small_color = palette
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


def _stack(component_id: str, children: list[str], **styles: Any) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Stack",
        "children": children,
        "styles": styles,
    }
