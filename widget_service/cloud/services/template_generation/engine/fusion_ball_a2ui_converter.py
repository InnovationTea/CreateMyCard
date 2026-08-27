"""Expand the cloud-only FusionBall component in complete A2UI.

This file is intentionally self-contained so it can be copied into another project.
"""

from __future__ import annotations

import json
from typing import Any, cast

_CONTENT_ID_PREFIX = "__genui_render_component__"
_FUSION_BALL_TYPE = "FusionBall"
_FUSION_COLOR_FIELDS = ("largeColor", "mediumColor", "smallColor")
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
__all__ = ["FusionBallA2UIConversionError", "convert_a2ui_with_fusion_ball"]


class FusionBallA2UIConversionError(ValueError):
    """Raised when a cloud FusionBall cannot be expanded deterministically."""


def convert_a2ui_with_fusion_ball(a2ui: str) -> str:
    """Expand one cloud FusionBall and mark its adjacent card-content component."""
    if isinstance(a2ui, str) and '"FusionBall"' not in a2ui:
        return a2ui
    messages = _parse_complete_a2ui(a2ui)
    update_components = messages[1]["updateComponents"]
    components = update_components.get("components")
    if not isinstance(components, list) or not components:
        raise FusionBallA2UIConversionError("updateComponents.components must be non-empty.")

    fusion_matches = _find_fusion_components(components)
    if not fusion_matches:
        return a2ui
    if len(fusion_matches) != 1:
        raise FusionBallA2UIConversionError("Complete A2UI must contain at most one FusionBall.")

    fusion_index, fusion = fusion_matches[0]
    fusion_id = _required_component_id(fusion, "FusionBall")
    palette = _read_fusion_palette(fusion)
    parent = _find_fusion_parent(components, fusion_id)
    content_id = _adjacent_content_id(parent, fusion_id)
    content = _find_unique_component(components, content_id, "adjacent card content")
    _validate_content_parent(components, content_id, parent)
    marked_content_id = _marked_content_id(content_id)
    _validate_expansion_ids(
        components,
        fusion_id=fusion_id,
        content_id=content_id,
        marked_content_id=marked_content_id,
    )

    parent["children"] = [
        _expanded_child_id(child_id, fusion_id, content_id, marked_content_id)
        for child_id in parent["children"]
    ]
    content["id"] = marked_content_id
    components.pop(fusion_index)
    for offset, component in enumerate(_build_fusion_components(palette)):
        components.insert(fusion_index + offset, component)
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


def _find_fusion_components(
    components: list[Any],
) -> list[tuple[int, dict[str, Any]]]:
    return [
        (index, component)
        for index, component in enumerate(components)
        if isinstance(component, dict) and component.get("component") == _FUSION_BALL_TYPE
    ]


def _required_component_id(component: dict[str, Any], label: str) -> str:
    component_id = component.get("id")
    if not isinstance(component_id, str) or not component_id:
        raise FusionBallA2UIConversionError(f"{label} id must be a non-empty string.")
    return component_id


def _read_fusion_palette(component: dict[str, Any]) -> tuple[str, str, str]:
    expected_fields = {"id", "component", *_FUSION_COLOR_FIELDS}
    if set(component) != expected_fields:
        raise FusionBallA2UIConversionError(
            "FusionBall must contain only id, component, largeColor, mediumColor, and smallColor."
        )
    large_color = component.get("largeColor")
    medium_color = component.get("mediumColor")
    small_color = component.get("smallColor")
    palette = (large_color, medium_color, small_color)
    if any(not _is_argb_color(color) for color in palette):
        raise FusionBallA2UIConversionError("FusionBall colors must use #AARRGGBB.")
    return cast(tuple[str, str, str], palette)


def _find_fusion_parent(
    components: list[Any],
    fusion_id: str,
) -> dict[str, Any]:
    parents = _find_component_parents(components, fusion_id)
    if len(parents) != 1:
        raise FusionBallA2UIConversionError("FusionBall must have exactly one parent.")
    parent = parents[0]
    if parent.get("component") != "Stack":
        raise FusionBallA2UIConversionError("FusionBall parent must be Stack.")
    children = parent["children"]
    if not all(isinstance(child_id, str) and child_id for child_id in children):
        raise FusionBallA2UIConversionError("FusionBall parent children must be component ids.")
    return parent


def _find_component_parents(
    components: list[Any],
    component_id: str,
) -> list[dict[str, Any]]:
    parents: list[dict[str, Any]] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        children = component.get("children")
        if isinstance(children, list) and component_id in children:
            parents.append(component)
    return parents


def _adjacent_content_id(parent: dict[str, Any], fusion_id: str) -> str:
    children = parent["children"]
    fusion_index = children.index(fusion_id)
    content_index = fusion_index + 1
    if content_index >= len(children):
        raise FusionBallA2UIConversionError(
            "FusionBall must be immediately followed by its card-content component."
        )
    if len(children) != 2:
        raise FusionBallA2UIConversionError(
            "FusionBall Stack must contain only FusionBall and adjacent card content."
        )
    content_id = children[content_index]
    if content_id == fusion_id:
        raise FusionBallA2UIConversionError("FusionBall cannot be its own adjacent content.")
    return content_id


def _find_unique_component(
    components: list[Any],
    component_id: str,
    label: str,
) -> dict[str, Any]:
    matches = [
        component
        for component in components
        if isinstance(component, dict) and component.get("id") == component_id
    ]
    if len(matches) != 1:
        raise FusionBallA2UIConversionError(f"A2UI must contain exactly one {label} component.")
    return matches[0]


def _marked_content_id(component_id: str) -> str:
    if component_id.startswith(_CONTENT_ID_PREFIX):
        return component_id
    return f"{_CONTENT_ID_PREFIX}{component_id}"


def _validate_content_parent(
    components: list[Any],
    content_id: str,
    fusion_parent: dict[str, Any],
) -> None:
    parents = _find_component_parents(components, content_id)
    if len(parents) != 1 or parents[0] is not fusion_parent:
        raise FusionBallA2UIConversionError(
            "Adjacent card content must belong only to the FusionBall parent."
        )


def _expanded_child_id(
    child_id: str,
    fusion_id: str,
    content_id: str,
    marked_content_id: str,
) -> str:
    if child_id == fusion_id:
        return "fusionBallBackground"
    if child_id == content_id:
        return marked_content_id
    return child_id


def _validate_expansion_ids(
    components: list[Any],
    *,
    fusion_id: str,
    content_id: str,
    marked_content_id: str,
) -> None:
    component_ids = _component_ids(components)
    remaining_ids = component_ids - {fusion_id, content_id}
    conflicts = sorted(remaining_ids & _FUSION_BACKGROUND_COMPONENT_IDS)
    if conflicts:
        raise FusionBallA2UIConversionError(
            f"Fusion-ball component ids already exist: {', '.join(conflicts)}."
        )
    if marked_content_id in remaining_ids:
        raise FusionBallA2UIConversionError(
            f"Marked card-content id already exists: {marked_content_id}."
        )


def _serialize_messages(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")) for message in messages
    )


def _component_ids(components: list[Any]) -> set[str]:
    component_ids: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = component.get("id")
        if isinstance(component_id, str) and component_id:
            component_ids.add(component_id)
    return component_ids


def _is_argb_color(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 9 or not value.startswith("#"):
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value[1:])


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
