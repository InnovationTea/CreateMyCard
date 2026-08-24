"""Convert one complete 2x2 A2UI card to the fusion-ball surface form."""

from __future__ import annotations

import copy
import json
from typing import Any

from .cardplan.fusion_ball_background import (
    build_fusion_ball_background,
    theme_color_from_root_styles,
)
from .terse_dsl_nested2_converter import Nested2Node

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


class FusionBallA2UIConversionError(ValueError):
    """Raised when the input is not a supported complete A2UI card."""


def convert_a2ui_with_fusion_ball(a2ui: str, *, size: str) -> str:
    """Replace a 2x2 Stack root's solid or gradient background with fusion balls."""
    if size == "2x4":
        return a2ui
    if size != "2x2":
        raise FusionBallA2UIConversionError('size must be "2x2" or "2x4".')

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

    try:
        theme_color = theme_color_from_root_styles(root_styles)
    except ValueError as exc:
        raise FusionBallA2UIConversionError(
            "The Stack root background does not contain a supported hex color."
        ) from exc

    outer_root, card_content = _split_root(root)
    fusion_components = _build_fusion_components(theme_color)
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


def _build_fusion_components(theme_color: str) -> list[dict[str, Any]]:
    background = build_fusion_ball_background(theme_color)
    components: list[dict[str, Any]] = []
    _lower_fusion_node(background, components)
    return components


def _lower_fusion_node(
    node: Nested2Node,
    components: list[dict[str, Any]],
) -> None:
    styles = dict(node.values[-1])
    component_id = styles.pop("_id")
    child_ids = [child.values[-1]["_id"] for child in node.children]
    components.append(
        {
            "id": component_id,
            "component": node.component_type,
            "children": child_ids,
            "styles": styles,
        }
    )
    for child in node.children:
        _lower_fusion_node(child, components)
