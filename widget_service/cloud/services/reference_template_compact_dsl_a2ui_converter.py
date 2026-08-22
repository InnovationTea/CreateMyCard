# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Deterministically convert Design Compact DSL to standard A2UI NDJSON."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal

import services.compact_dsl_design_tokens as design_tokens
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError as BaseCompactDslConversionError,
)

ThemeMode = Literal["light", "dark"]

_A2UI_FORM_CATALOG_ID = "ohos.a2ui.extended.catalog.form"
_A2UI_ICON_BUTTON_LABEL = design_tokens.A2UI_ICON_BUTTON_LABEL
_BOTTOM_RING_ACTION_EQUIVALENT_ICON_GROUPS = (
    design_tokens.BOTTOM_RING_ACTION_EQUIVALENT_ICON_GROUPS
)
_GRADIENT_ACTION_BACKGROUNDS = design_tokens.GRADIENT_ACTION_BACKGROUNDS
_GRADIENT_ACTION_INKS = design_tokens.GRADIENT_ACTION_INKS
_ICON_ROUND_SIZE = design_tokens.ICON_ROUND_SIZE
_ROOT_LINEAR_GRADIENT_PALETTES = design_tokens.ROOT_LINEAR_GRADIENT_PALETTES
_SEMANTIC_REPAIRABLE_ROOT_GRADIENT_COLOR_SETS = (
    design_tokens.SEMANTIC_REPAIRABLE_ROOT_GRADIENT_COLOR_SETS
)
_SLEEP_ROOT_GRADIENT_COLOR_SET = design_tokens.SLEEP_ROOT_GRADIENT_COLOR_SET
_STRONG_ROOT_GRADIENT_COLOR_SETS = design_tokens.STRONG_ROOT_GRADIENT_COLOR_SETS
_TITLE_ICON_SIZE = design_tokens.TITLE_ICON_SIZE
_WEATHER_ROOT_GRADIENT_COLOR_SETS = design_tokens.WEATHER_ROOT_GRADIENT_COLOR_SETS
DesignTokenConversionError = design_tokens.DesignTokenConversionError
_design_token_convert_action_unit = design_tokens.convert_action_unit
_design_token_expand_component_design = design_tokens.expand_component_design
_design_token_resolve_tokens = design_tokens.resolve_tokens
_normalize_icon_button_stack = design_tokens.normalize_icon_button_stack
_should_preserve_original_icon_color = design_tokens.should_preserve_original_icon_color
_COMPONENT_TYPES = frozenset(
    {
        "Row",
        "Column",
        "List",
        "Stack",
        "Text",
        "Image",
        "Divider",
        "Progress",
        "RingUnit",
        "TimelineUnit",
        "Button",
        "ActionUnit",
        "Checkbox",
    }
)
_CONTAINER_TYPES = frozenset({"Row", "Column", "List", "Stack"})
_SEMANTIC_FIELDS = {
    "Text": frozenset({"content"}),
    "Image": frozenset({"src"}),
    "Progress": frozenset({"value", "total"}),
    "Button": frozenset({"label", "enabled"}),
    "ActionUnit": frozenset({"label", "enabled"}),
    "Checkbox": frozenset({"label", "value", "select"}),
}
_COMPACT_ONLY_FIELDS = {
    "Progress": frozenset({"threshold"}),
}
_REQUIRED_FIELDS = {
    "Text": "content",
    "Image": "src",
    "Progress": "value",
}
_COMMON_STYLE_PROPERTIES = frozenset(
    {
        "alignSelf",
        "aspectRatio",
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "borderColor",
        "borderRadius",
        "borderWidth",
        "clip",
        "constraintSize",
        "flexShrink",
        "height",
        "layoutWeight",
        "linearGradient",
        "margin",
        "maxHeight",
        "maxWidth",
        "minHeight",
        "minWidth",
        "opacity",
        "padding",
        "shadow",
        "visibility",
        "width",
    }
)
_COMPONENT_STYLE_PROPERTIES = {
    "Text": frozenset(
        {
            "fontColor",
            "fontSize",
            "fontWeight",
            "maxFontSize",
            "maxLines",
            "minFontSize",
            "textAlign",
            "textOverflow",
        }
    ),
    "Image": frozenset({"fillColor", "objectFit"}),
    "Divider": frozenset({"color", "strokeWidth", "vertical"}),
    "Progress": frozenset({"color", "strokeWidth", "type"}),
    "Button": frozenset(
        {
            "backgroundColor",
            "borderRadius",
            "fontColor",
            "fontSize",
            "fontWeight",
            "maxFontSize",
            "maxLines",
            "minFontSize",
        }
    ),
    "Checkbox": frozenset(
        {
            "mark",
            "selectedColor",
            "shape",
            "unSelectedColor",
        }
    ),
    "Row": frozenset({"alignItems", "itemMargin", "justifyContent"}),
    "Column": frozenset({"alignItems", "itemMargin", "justifyContent"}),
    "List": frozenset({"listDirection", "scrollBar", "space"}),
    "Stack": frozenset({"alignContent"}),
}
_COMMON_COMPACT_PROPERTIES = frozenset({"design", "onClick"})
_ACTION_UNIT_PROPERTIES = frozenset({"state", "icon", "actionInk", "actionSurface"})
_RING_UNIT_PROPERTIES = frozenset(
    {
        "state",
        "size",
        "value",
        "total",
        "centerIcon",
        "reading",
        "color",
        "backgroundColor",
    }
)
_TIMELINE_UNIT_PROPERTIES = frozenset({"color", "lineColor"})
_ACTION_UNIT_FORBIDDEN_SKIN_PROPERTIES = frozenset(
    {
        "backgroundColor",
        "borderColor",
        "borderRadius",
        "borderWidth",
        "color",
        "design",
        "fillColor",
        "fontColor",
        "fontSize",
        "fontWeight",
        "height",
        "layoutWeight",
        "linearGradient",
        "maxFontSize",
        "maxLines",
        "minFontSize",
        "opacity",
        "padding",
        "textAlign",
        "textOverflow",
        "width",
    }
)
_NUMBER_PROPERTIES = frozenset(
    {
        "borderRadius",
        "borderWidth",
        "flexShrink",
        "fontSize",
        "layoutWeight",
        "maxFontSize",
        "maxHeight",
        "maxLines",
        "maxWidth",
        "minFontSize",
        "minHeight",
        "minWidth",
        "opacity",
        "strokeWidth",
    }
)
_BOOLEAN_PROPERTIES = frozenset({"clip", "vertical"})
_STRING_PROPERTIES = frozenset(
    {
        "alignContent",
        "alignItems",
        "alignSelf",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "listDirection",
        "objectFit",
        "scrollBar",
        "shape",
        "textAlign",
        "textOverflow",
        "type",
        "visibility",
        "state",
        "icon",
        "actionInk",
        "actionSurface",
    }
)
_FORBIDDEN_PROPERTIES = frozenset({"action", "event", "submit_form"})
_FORBIDDEN_STRING_FRAGMENTS = ("{{", "$item", "$__dataModel")
_LEGACY_PATH_TEMPLATE_PATTERN = re.compile(
    r"^\s*\{\{\s*\$\{\s*(?P<path>/[^{}\s]+)\s*\}\s*\}\}\s*$"
)
_DURATION_UNIT_PATTERN = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>分钟|小时|分|时)\s*$"
)
_TEXT_JOIN_SEPARATOR_PATTERN = re.compile(r"\s*[·｜|]\s*")
_DURATION_TEXT_HERO_FALLBACK_FONT_SIZE = 24
_RING_UNIT_CENTER_ICON_STATES = frozenset({"center-icon", "without-reading"})
_RING_UNIT_CENTER_TEXT_STATES = frozenset({"center-text", "center-reading"})
_RING_UNIT_ICON_BELOW_TEXT_STATES = frozenset(
    {"center-icon-below-text", "with-reading"}
)
_RING_UNIT_STATES = frozenset(
    {
        *_RING_UNIT_CENTER_ICON_STATES,
        *_RING_UNIT_CENTER_TEXT_STATES,
        *_RING_UNIT_ICON_BELOW_TEXT_STATES,
    }
)
_RING_UNIT_SIZES = frozenset({44, 52})
_RING_READING_NUMBER_TEXT = {
    "fontSize": 16,
    "fontWeight": 700,
    "maxLines": 1,
    "flexShrink": 0,
}
_RING_READING_UNIT_TEXT = {
    "fontSize": 10,
    "fontWeight": 400,
    "opacity": 0.6,
    "maxLines": 1,
    "flexShrink": 0,
}
_TIMELINE_UNIT_DEFAULT_COLOR = "#FFE84026"
_TIMELINE_UNIT_DEFAULT_LINE_COLOR = "#1A000000"
_COMPACT_ROOT_DIMENSIONS = {
    "2x2": {"width": 160, "height": 160},
    "2x4": {"width": 320, "height": 160},
    "4x2": {"width": 320, "height": 160},
}
_A2UI_FALLBACK_DIMENSIONS = {
    "2x2": {"width": 160, "height": 160},
    "2x4": {"width": 320, "height": 160},
    "4x2": {"width": 320, "height": 160},
}


class CompactDslConversionError(BaseCompactDslConversionError):
    """Raised when valid A2UI cannot be derived from Compact DSL."""


@dataclass(frozen=True)
class ComponentRow:
    """One Compact DSL component tuple."""

    component_id: str
    component_type: str
    props: dict[str, Any]
    children: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataRow:
    """One Compact DSL data tuple."""

    path: str
    value: Any


CompactRow = ComponentRow | DataRow


@dataclass(frozen=True)
class CompactDslContextValidation:
    """Deterministic validation result for TaskSpec and CardSpec usage."""

    warnings: tuple[str, ...] = ()


def normalize_compact_dsl_design_tokens(
    compact_dsl: str,
    *,
    theme: ThemeMode = "light",
) -> str:
    """Expand the design aliases defined by the current Design Compact prompt."""
    _validate_theme(theme)
    rows = _parse_compact_rows(compact_dsl)
    _validate_component_tree(rows)
    normalized_rows: list[list[Any]] = []

    for row in rows:
        if isinstance(row, DataRow):
            normalized_rows.append([row.path, copy.deepcopy(row.value)])
            continue
        normalized = _normalize_component(row)
        normalized_rows.append(_component_to_tuple(normalized))

    return _serialize_rows(normalized_rows)


def repair_compact_dsl_binding_paths(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
) -> str:
    """Repair unique data roots or safely inline unbacked local values."""
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _validate_component_tree(rows)
    event_replacements = _event_handler_replacements(components, task_spec)
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        if event_replacements:
            return _serialize_repaired_rows(
                rows,
                event_replacements=event_replacements,
            )
        return compact_dsl

    component_paths = _component_binding_paths(components)
    paths = list(component_paths)
    paths.extend(row.path for row in data_rows)
    roots = _card_spec_data_roots(card_spec)
    data_values = {row.path: row.value for row in data_rows}
    path_replacements: dict[str, str] = {}
    literal_replacements: dict[str, Any] = {}
    for path in dict.fromkeys(paths):
        if _schema_node_at_path(schema, path) is not None:
            continue
        suffix = path
        if path == "/data" or path.startswith("/data/"):
            suffix = path[len("/data"):]
        candidates: set[str] = set()
        for root in roots:
            candidate = f"{root.rstrip('/')}{suffix}"
            if _schema_node_at_path(schema, candidate) is not None:
                candidates.add(candidate)
        if len(candidates) == 1:
            path_replacements[path] = candidates.pop()
            continue
        if not roots and path in component_paths and path in data_values:
            literal_replacements[path] = copy.deepcopy(data_values[path])

    existing_data_paths = {
        path_replacements.get(row.path, row.path)
        for row in data_rows
        if row.path not in literal_replacements
    }
    additional_data_rows: dict[str, Any] = {}
    for path in component_paths:
        if path in literal_replacements:
            continue
        repaired_path = path_replacements.get(path, path)
        if repaired_path in existing_data_paths:
            continue
        schema_node = _schema_node_at_path(schema, repaired_path)
        if not isinstance(schema_node, dict) or "sampleValue" not in schema_node:
            continue
        additional_data_rows[repaired_path] = copy.deepcopy(
            schema_node["sampleValue"]
        )
        existing_data_paths.add(repaired_path)

    if (
        not path_replacements
        and not literal_replacements
        and not event_replacements
        and not additional_data_rows
    ):
        return compact_dsl
    return _serialize_repaired_rows(
        rows,
        path_replacements=path_replacements,
        literal_replacements=literal_replacements,
        event_replacements=event_replacements,
        additional_data_rows=additional_data_rows,
    )


def _serialize_repaired_rows(
    rows: list[CompactRow],
    *,
    path_replacements: dict[str, str] | None = None,
    literal_replacements: dict[str, Any] | None = None,
    event_replacements: dict[str, dict[str, Any]] | None = None,
    additional_data_rows: dict[str, Any] | None = None,
) -> str:
    path_replacements = path_replacements or {}
    literal_replacements = literal_replacements or {}
    event_replacements = event_replacements or {}
    additional_data_rows = additional_data_rows or {}
    repaired_rows: list[list[Any]] = []
    for row in rows:
        if isinstance(row, DataRow):
            if row.path in literal_replacements:
                continue
            repaired_rows.append(
                [
                    path_replacements.get(row.path, row.path),
                    copy.deepcopy(row.value),
                ]
            )
            continue
        props = _replace_binding_paths(
            row.props,
            path_replacements,
            literal_replacements,
        )
        props = _replace_event_handlers(props, event_replacements)
        original_content = row.props.get("content")
        content = props.get("content")
        if row.component_type == "Text" and _is_path_binding(original_content):
            binding_path = original_content["path"]
            if binding_path in literal_replacements and not isinstance(content, str):
                props["content"] = str(content)
        repaired_rows.append(
            _component_to_tuple(
                ComponentRow(
                    row.component_id,
                    row.component_type,
                    props,
                    row.children,
                )
            )
        )
    for path, value in additional_data_rows.items():
        repaired_rows.append([path, copy.deepcopy(value)])
    return _serialize_rows(repaired_rows)


def validate_compact_dsl_context(
    compact_dsl: str,
    *,
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
) -> CompactDslContextValidation:
    """Validate model bindings, events and assets without another model call."""
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _validate_component_tree(rows)
    data_model = _build_data_model(data_rows)
    normalized_components = [_normalize_component(row) for row in components]
    normalized_components = _normalize_2x2_components(
        normalized_components,
        data_model,
    )
    normalized_components = _normalize_special_action_units(normalized_components)
    normalized_components = _normalize_2x2_text_palette(normalized_components)
    normalized_components = _normalize_ring_stack_children(normalized_components)
    _validate_2x2_icon_round_layout(normalized_components)
    _validate_binding_paths(normalized_components, data_model)

    binding_paths = _component_binding_paths(normalized_components)
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        raise CompactDslConversionError(
            "TaskSpec.dataModelSchema must be an object."
        )
    _validate_binding_schema_types(
        binding_paths,
        data_model,
        data_model_schema,
    )
    _validate_data_capability_roots(binding_paths, card_spec)
    _validate_asset_candidates(normalized_components, task_spec)
    _validate_event_candidates(normalized_components, task_spec)

    warnings = _unused_data_capability_warnings(binding_paths, card_spec)
    return CompactDslContextValidation(warnings=tuple(warnings))


def convert_compact_dsl_to_a2ui(
    compact_dsl: str,
    *,
    size: str,
    protocol_profile: dict[str, Any],
    theme: ThemeMode = "light",
    surface_id: str = "surface_card",
) -> str:
    """Convert one Design Compact DSL card to standard three-message A2UI."""
    _validate_theme(theme)
    _validate_surface_id(surface_id)
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _validate_component_tree(rows)
    _validate_compact_root_dimensions(components[0], size)

    data_model = _build_data_model(data_rows)
    normalized_components = [_normalize_component(row) for row in components]
    normalized_components = _normalize_2x2_components(
        normalized_components,
        data_model,
    )
    normalized_components = _normalize_special_action_units(normalized_components)
    normalized_components = _normalize_2x2_text_palette(normalized_components)
    normalized_components = _normalize_ring_stack_children(normalized_components)
    _validate_2x2_icon_round_layout(normalized_components)
    _validate_binding_paths(normalized_components, data_model)

    icon_round_button_ids = _button_ids_with_design(components, "icon-round")
    fallback_root_gradient = _fallback_root_linear_gradient(compact_dsl)
    converted_components = []
    for component in normalized_components:
        hide_label = component.component_id in icon_round_button_ids
        converted_components.extend(
            _convert_component_rows(
                component,
                hide_label=hide_label,
                fallback_root_gradient=fallback_root_gradient,
            )
        )
    version = str(protocol_profile.get("version") or "v0.9")
    messages = [
        {
            "version": version,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": _A2UI_FORM_CATALOG_ID,
                "width": 160,
                "height": 160,
            },
        },
        {
            "version": version,
            "updateComponents": {
                "surfaceId": surface_id,
                "root": "root",
                "components": converted_components,
            },
        },
        {
            "version": version,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": data_model,
            },
        },
    ]
    return _serialize_a2ui_messages(messages)


def _validate_theme(theme: str) -> None:
    if theme not in {"light", "dark"}:
        raise CompactDslConversionError(
            f'Unsupported compatibility theme "{theme}".'
        )


def _normalize_special_action_units(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    if not components or not _is_2x2_root(components[0].props):
        return components
    color_set = _root_gradient_color_set(components)
    if color_set not in _STRONG_ROOT_GRADIENT_COLOR_SETS:
        return components
    action_style = _action_style_for_root_gradient(components)
    if action_style is None:
        return components
    action_ink, action_background = action_style

    normalized: list[ComponentRow] = []
    for component in components:
        if component.component_type != "ActionUnit":
            normalized.append(component)
            continue
        props = copy.deepcopy(component.props)
        props["actionInk"] = action_ink
        props["_actionBackground"] = action_background
        if action_background == "#FFFFFFFF":
            props["actionSurface"] = "white"
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )
        )
    return normalized


def _normalize_2x2_timeline_colors(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Keep meeting timeline dots on the root Surface palette."""
    if not components or not _is_2x2_root(components[0].props):
        return components
    color_set = _root_gradient_color_set(components)
    if color_set is None:
        return components
    timeline_color = _GRADIENT_ACTION_INKS.get(color_set)
    if timeline_color is None:
        return components

    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        if not _is_timeline_dot_component(component):
            continue
        props = copy.deepcopy(component.props)
        props["borderColor"] = timeline_color
        replacements[component.component_id] = props

    if not replacements:
        return components
    return _replace_component_props(components, replacements)


def _is_timeline_dot_component(component: ComponentRow) -> bool:
    return (
        component.component_type == "Text"
        and component.component_id.endswith("_dot")
        and component.props.get("content", "") == ""
        and "borderColor" in component.props
        and _numeric_prop(component.props.get("borderRadius"), default=0) > 0
        and _numeric_prop(component.props.get("borderWidth"), default=0) > 0
    )


def _normalize_2x2_text_palette(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Use black text on light surfaces and white text on strong surfaces."""
    if not components or not _is_2x2_root(components[0].props):
        return components
    color_set = _root_gradient_color_set(components)
    use_white_text = color_set in _STRONG_ROOT_GRADIENT_COLOR_SETS
    replacements: dict[str, dict[str, Any]] = {}

    for component in components:
        if component.component_type != "Text":
            continue
        if _is_timeline_dot_component(component):
            continue
        props = copy.deepcopy(component.props)
        normalized_color = _normalized_text_font_color(
            props.get("fontColor"),
            use_white_text=use_white_text,
        )
        if normalized_color is None:
            continue
        props["fontColor"] = normalized_color
        if props != component.props:
            replacements[component.component_id] = props

    if not replacements:
        return components
    return _replace_component_props(components, replacements)


def _normalized_text_font_color(
    value: Any,
    *,
    use_white_text: bool,
) -> str | None:
    target_rgb = "FFFFFF" if use_white_text else "000000"
    default_color = "#FFFFFFFF" if use_white_text else "#E5000000"
    if not isinstance(value, str) or not value:
        return default_color
    if not value.startswith("#"):
        return default_color
    normalized = value.upper()
    if re.fullmatch(r"#[0-9A-F]{8}", normalized):
        alpha = normalized[1:3]
        if alpha == "00":
            return None
        rgb = normalized[3:]
        if rgb in {"000000", "FFFFFF"}:
            return f"#{alpha}{target_rgb}"
        return default_color
    if re.fullmatch(r"#[0-9A-F]{6}", normalized):
        rgb = normalized[1:]
        if rgb not in {"000000", "FFFFFF"}:
            return default_color
        return f"#FF{target_rgb}"
    return default_color


def _action_style_for_root_gradient(
    components: list[ComponentRow],
) -> tuple[str, str] | None:
    color_set = _root_gradient_color_set(components)
    if color_set is None:
        return None
    action_ink = _GRADIENT_ACTION_INKS.get(color_set)
    action_background = _GRADIENT_ACTION_BACKGROUNDS.get(color_set)
    if action_ink is None or action_background is None:
        return None
    return action_ink, action_background


def _normalize_ring_stack_children(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    component_types = {
        component.component_id: component.component_type
        for component in components
    }
    ring_center_ids: set[str] = set()
    normalized: list[ComponentRow] = []
    for component in components:
        if component.component_type != "Stack":
            normalized.append(_normalize_ring_center_component(component, ring_center_ids))
            continue
        children = list(component.children)
        progress_ids = [
            child for child in children if component_types.get(child) == "Progress"
        ]
        image_ids = [
            child for child in children if component_types.get(child) == "Image"
        ]
        text_ids = [
            child for child in children if component_types.get(child) == "Text"
        ]
        center_ids = image_ids + text_ids
        if not progress_ids or not center_ids:
            normalized.append(component)
            continue
        reordered_ids = set(progress_ids)
        reordered_ids.update(center_ids)
        remaining_ids = [
            child
            for child in children
            if child not in reordered_ids
        ]
        ring_center_ids.update(center_ids)
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                component.props,
                tuple(progress_ids + center_ids + remaining_ids),
            )
        )
    return normalized


def _normalize_ring_center_component(
    component: ComponentRow,
    ring_center_ids: set[str],
) -> ComponentRow:
    if component.component_id not in ring_center_ids:
        return component
    props = copy.deepcopy(component.props)
    if component.component_type == "Image":
        props["width"] = 24
        props["height"] = 24
    if component.component_type == "Text":
        props["fontSize"] = 16
    return ComponentRow(
        component.component_id,
        component.component_type,
        props,
        component.children,
    )


def _root_gradient_color_set(components: list[ComponentRow]) -> frozenset[str] | None:
    if not components:
        return None
    root = components[0]
    if root.component_id != "root":
        return None
    gradient = root.props.get("linearGradient")
    if not isinstance(gradient, dict):
        return None
    colors = gradient.get("colors")
    if not isinstance(colors, list):
        return None
    return _gradient_color_set(colors)


def _gradient_color_set(colors: list[Any]) -> frozenset[str] | None:
    normalized_colors: set[str] = set()
    for stop in colors:
        if not isinstance(stop, list) or len(stop) != 2:
            return None
        color = stop[0]
        if not isinstance(color, str):
            return None
        normalized_color = _normalize_gradient_color(color)
        if normalized_color is None:
            return None
        normalized_colors.add(normalized_color)
    return frozenset(normalized_colors)


def _normalize_gradient_color(color: str) -> str | None:
    normalized = color.strip().upper()
    if len(normalized) == 7 and normalized.startswith("#"):
        return f"#FF{normalized[1:]}"
    if len(normalized) == 9 and normalized.startswith("#"):
        return normalized
    return None


def _validate_surface_id(surface_id: str) -> None:
    if not isinstance(surface_id, str) or not surface_id.strip():
        raise CompactDslConversionError("surface_id must be a non-empty string.")


def _strip_optional_genui_fence(compact_dsl: str) -> str:
    text = compact_dsl.lstrip("\ufeff").strip()
    lines = text.splitlines()
    opening_index = _find_fence_opening(lines)
    if opening_index is None:
        return text

    closing_index = _find_fence_closing(lines, opening_index + 1)
    body_end = closing_index if closing_index is not None else len(lines)
    body = "\n".join(lines[opening_index + 1:body_end]).strip()
    if "```" in body:
        raise CompactDslConversionError(
            "Compact DSL must contain exactly one genui fence."
        )
    if closing_index is not None:
        _validate_no_additional_fence(lines[closing_index + 1:])
    return body


def _find_fence_opening(lines: list[str]) -> int | None:
    supported_openings = {
        "```",
        "```genui",
        "```json",
        "```text",
        "```designcompactdsl",
        "```design-compact-dsl",
    }
    for index, line in enumerate(lines):
        if line.strip().lower() in supported_openings:
            return index
    return None


def _find_fence_closing(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].strip() == "```":
            return index
    return None


def _validate_no_additional_fence(lines: list[str]) -> None:
    for line in lines:
        if line.strip().startswith("```"):
            raise CompactDslConversionError(
                "Compact DSL must contain exactly one genui fence."
            )


def _repair_compact_json_rows(compact_dsl: str) -> str:
    body = _strip_optional_genui_fence(compact_dsl)
    rows = _extract_top_level_array_rows(body)
    repaired_rows: list[str] = []
    for line_number, row in enumerate(rows, 1):
        repaired = _remove_trailing_json_commas(row)
        value = _parse_json_line(repaired, line_number)
        repaired_rows.append(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(repaired_rows)


def _extract_top_level_array_rows(body: str) -> list[str]:
    rows: list[str] = []
    current: list[str] = []
    expected_closers: list[str] = []
    outside: list[str] = []
    in_string = False
    escaped = False

    for char in body:
        if not expected_closers:
            if char == "[":
                _validate_text_between_rows(outside, bool(rows))
                outside = []
                current = [char]
                expected_closers = ["]"]
                in_string = False
                escaped = False
            else:
                outside.append(char)
            continue

        current.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char in {"[", "{"}:
            expected_closers.append("]" if char == "[" else "}")
            continue
        if char not in {"]", "}"}:
            continue
        if char != expected_closers[-1]:
            raise CompactDslConversionError(
                "Compact DSL contains mismatched JSON delimiters."
            )
        expected_closers.pop()
        if not expected_closers:
            rows.append("".join(current))
            current = []

    if expected_closers:
        if in_string:
            raise CompactDslConversionError(
                "Compact DSL contains an unclosed JSON string."
            )
        current.extend(reversed(expected_closers))
        rows.append("".join(current))

    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    return rows


def _validate_text_between_rows(outside: list[str], has_previous_row: bool) -> None:
    if not has_previous_row:
        return
    text = "".join(outside)
    for char in text:
        if not char.isspace() and char not in {"]", "}"}:
            raise CompactDslConversionError(
                "Compact DSL contains non-JSON text between rows."
            )


def _remove_trailing_json_commas(row: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0

    while index < len(row):
        char = row[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "," and _next_non_whitespace_is_closer(row, index + 1):
            index += 1
            continue
        output.append(char)
        index += 1

    return "".join(output)


def _next_non_whitespace_is_closer(text: str, start: int) -> bool:
    for index in range(start, len(text)):
        if text[index].isspace():
            continue
        return text[index] in {"]", "}"}
    return False


def _parse_compact_rows(compact_dsl: str) -> list[CompactRow]:
    body = _repair_compact_json_rows(compact_dsl)
    parsed_values: list[tuple[int, list[Any]]] = []
    rows: list[CompactRow] = []

    for line_number, raw_line in enumerate(body.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        value = _parse_json_line(line, line_number)
        parsed_values.append((line_number, value))

    parsed_values = _repair_model_generated_component_tree_values(parsed_values)
    for line_number, value in parsed_values:
        rows.append(_parse_row(value, line_number))

    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    _validate_button_image_children(rows)
    visible_rows = _drop_empty_image_components(rows)
    ordered_rows = _canonicalize_component_order(visible_rows)
    expanded_ring_rows = _expand_ring_units(ordered_rows)
    return _expand_timeline_units(expanded_ring_rows)


def _repair_model_generated_component_tree_values(
    values: list[tuple[int, list[Any]]],
) -> list[tuple[int, list[Any]]]:
    """Repair common model mistakes before strict component tree validation."""
    component_ids = {
        value[0]
        for _line_number, value in values
        if _looks_like_component_row_value(value)
    }
    if not component_ids:
        return values

    repaired: list[tuple[int, list[Any]]] = []
    seen_component_ids: set[str] = set()
    for line_number, value in values:
        if not _looks_like_component_row_value(value):
            repaired.append((line_number, value))
            continue
        component_id = value[0]
        if component_id in seen_component_ids:
            continue
        seen_component_ids.add(component_id)
        repaired.append((line_number, _drop_missing_child_references(value, component_ids)))

    if not repaired:
        return repaired

    first_line_number, first_value = repaired[0]
    if not _is_root_container_row_value(first_value):
        return repaired
    if len(first_value) == 4 and isinstance(first_value[3], list):
        return repaired

    inferred_children = _infer_root_children(repaired)
    if not inferred_children:
        return repaired
    root_value = [
        first_value[0],
        first_value[1],
        copy.deepcopy(first_value[2]),
        inferred_children,
    ]
    return [(first_line_number, root_value), *repaired[1:]]


def _looks_like_component_row_value(value: list[Any]) -> bool:
    return (
        len(value) in {3, 4}
        and isinstance(value[0], str)
        and not value[0].startswith("/")
        and isinstance(value[1], str)
        and isinstance(value[2], dict)
    )


def _is_root_container_row_value(value: list[Any]) -> bool:
    return (
        _looks_like_component_row_value(value)
        and value[0] == "root"
        and value[1] in _CONTAINER_TYPES
    )


def _drop_missing_child_references(
    value: list[Any],
    component_ids: set[str],
) -> list[Any]:
    if len(value) != 4 or not isinstance(value[3], list):
        return value
    repaired_children = [
        child_id
        for child_id in value[3]
        if isinstance(child_id, str) and child_id in component_ids
    ]
    if len(repaired_children) == len(value[3]):
        return value
    return [value[0], value[1], copy.deepcopy(value[2]), repaired_children]


def _infer_root_children(values: list[tuple[int, list[Any]]]) -> list[str]:
    component_ids: list[str] = []
    parented_ids: set[str] = set()
    for _line_number, value in values:
        if _looks_like_data_row(value) or _looks_like_data_def_row(value):
            break
        if not _looks_like_component_row_value(value):
            continue
        component_id = value[0]
        if component_id != "root":
            component_ids.append(component_id)
        if len(value) == 4 and isinstance(value[3], list):
            for child_id in value[3]:
                if isinstance(child_id, str):
                    parented_ids.add(child_id)
    return [component_id for component_id in component_ids if component_id not in parented_ids]


def _validate_ring_unit_parent_layout(rows: list[CompactRow]) -> None:
    components = [row for row in rows if isinstance(row, ComponentRow)]
    if not components or not _is_2x2_root(components[0].props):
        return
    data_values = {
        row.path: row.value
        for row in rows
        if isinstance(row, DataRow)
    }
    components_by_id = {
        component.component_id: component
        for component in components
    }
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in component.children
    }
    for component in components:
        if component.component_type != "RingUnit":
            continue
        parent = parent_by_child.get(component.component_id)
        if parent is None:
            continue
        sibling_types = {
            components_by_id[child_id].component_type
            for child_id in parent.children
            if child_id != component.component_id and child_id in components_by_id
        }
        if parent.component_type == "Stack" or "Image" in sibling_types:
            raise CompactDslConversionError(
                f"{component.component_id}: RingUnit must be a direct content "
                "component and must not be wrapped in Stack or overlaid with Image."
            )
        if component.props.get("state") not in _RING_UNIT_CENTER_TEXT_STATES:
            continue
        reading = component.props.get("reading")
        if not isinstance(reading, dict):
            continue
        preview = data_values.get(reading.get("path"))
        if preview is None or _ring_center_reading_fits(preview):
            continue
        raise CompactDslConversionError(
            f"{component.component_id}: center-reading preview {preview!r} does "
            "not fit a 52vp ring; use a Progress ring with center Image and "
            "render the full value outside the ring."
        )


def _ring_center_reading_fits(preview: Any) -> bool:
    if isinstance(preview, bool):
        return False
    if isinstance(preview, int):
        return 0 <= preview <= 100
    if isinstance(preview, float):
        return preview.is_integer() and 0 <= preview <= 100
    if isinstance(preview, str):
        normalized = preview.strip().removesuffix("%").strip()
        return normalized.isdigit() and len(normalized) <= 3
    return False


def _expand_ring_units(rows: list[CompactRow]) -> list[CompactRow]:
    expanded_rows: list[CompactRow] = []
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "RingUnit":
            expanded_rows.append(row)
            continue
        expanded_rows.extend(_expand_ring_unit(row))
    return expanded_rows


def _expand_ring_unit(component: ComponentRow) -> list[ComponentRow]:
    state = component.props["state"]
    size = component.props["size"]
    ring_bar = _ring_unit_bar(component.component_id, component.props)
    if state in _RING_UNIT_CENTER_ICON_STATES:
        return _expand_ring_without_reading(component, ring_bar, size)
    if state in _RING_UNIT_CENTER_TEXT_STATES:
        return _expand_ring_center_reading(component, ring_bar, size)
    return _expand_ring_with_reading(component, ring_bar, size)


def _expand_ring_without_reading(
    component: ComponentRow,
    ring_bar: ComponentRow,
    size: int,
) -> list[ComponentRow]:
    children = [ring_bar.component_id]
    rows = [
        ComponentRow(
            component.component_id,
            "Stack",
            _ring_stack_props(size),
            tuple(children),
        ),
        ring_bar,
    ]
    center_icon = component.props.get("centerIcon")
    if center_icon is None:
        return rows
    icon = _ring_center_icon(component.component_id, center_icon, size)
    children.append(icon.component_id)
    rows[0] = ComponentRow(
        rows[0].component_id,
        rows[0].component_type,
        rows[0].props,
        tuple(children),
    )
    rows.append(icon)
    return rows


def _expand_ring_center_reading(
    component: ComponentRow,
    ring_bar: ComponentRow,
    size: int,
) -> list[ComponentRow]:
    reading_id = _ring_child_id(component.component_id, "center_reading")
    rows = [
        ComponentRow(
            component.component_id,
            "Stack",
            _ring_stack_props(size),
            (ring_bar.component_id, reading_id),
        ),
        ring_bar,
    ]
    rows.extend(
        _ring_reading_rows(
            reading_id,
            component.props["reading"],
            id_prefix=component.component_id,
            font_color=component.props.get("color"),
        )
    )
    return rows


def _expand_ring_with_reading(
    component: ComponentRow,
    ring_bar: ComponentRow,
    size: int,
) -> list[ComponentRow]:
    stack_id = _ring_child_id(component.component_id, "ring_stack")
    reading_id = _ring_child_id(component.component_id, "reading_below")
    stack_children = [ring_bar.component_id]
    rows = [
        ComponentRow(
            component.component_id,
            "Column",
            {"itemMargin": 4, "alignItems": "center", "flexShrink": 0},
            (stack_id, reading_id),
        ),
        ComponentRow(
            stack_id,
            "Stack",
            _ring_stack_props(size),
            tuple(stack_children),
        ),
        ring_bar,
    ]
    center_icon = component.props.get("centerIcon")
    if center_icon is not None:
        icon = _ring_center_icon(component.component_id, center_icon, size)
        stack_children.append(icon.component_id)
        rows[1] = ComponentRow(
            rows[1].component_id,
            rows[1].component_type,
            rows[1].props,
            tuple(stack_children),
        )
        rows.append(icon)
    rows.extend(
        _ring_reading_rows(
            reading_id,
            component.props["reading"],
            id_prefix=component.component_id,
            font_color=component.props.get("color"),
        )
    )
    return rows


def _ring_unit_bar(component_id: str, props: dict[str, Any]) -> ComponentRow:
    bar_props = {
        "design": "ring",
        "width": "matchParent",
        "height": "matchParent",
        "value": copy.deepcopy(props["value"]),
        "total": copy.deepcopy(props["total"]),
    }
    for color_name in ("color", "backgroundColor"):
        if color_name in props:
            bar_props[color_name] = copy.deepcopy(props[color_name])
    return ComponentRow(
        _ring_child_id(component_id, "ring_bar"),
        "Progress",
        bar_props,
    )


def _ring_stack_props(size: int) -> dict[str, Any]:
    return {
        "width": size,
        "height": size,
        "alignContent": "center",
        "flexShrink": 0,
    }


def _ring_center_icon(
    component_id: str,
    source: str,
    size: int,
) -> ComponentRow:
    icon_size = 24 if size >= 52 else 20
    return ComponentRow(
        _ring_child_id(component_id, "center_icon"),
        "Image",
        {
            "src": source,
            "width": icon_size,
            "height": icon_size,
            "flexShrink": 0,
        },
    )


def _ring_reading_rows(
    reading_id: str,
    reading: dict[str, Any],
    *,
    id_prefix: str,
    font_color: Any = None,
) -> list[ComponentRow]:
    content = {"path": reading["path"]}
    unit = reading.get("unit")
    number_props = {"content": content, **copy.deepcopy(_RING_READING_NUMBER_TEXT)}
    unit_props = {"content": unit, **copy.deepcopy(_RING_READING_UNIT_TEXT)}
    if isinstance(font_color, str) and font_color:
        number_props["fontColor"] = font_color
        unit_props["fontColor"] = font_color
    if unit is None or unit == "":
        return [
            ComponentRow(
                reading_id,
                "Text",
                number_props,
            )
        ]

    num_id = _ring_child_id(id_prefix, "reading_num")
    unit_id = _ring_child_id(id_prefix, "reading_unit")
    return [
        ComponentRow(
            reading_id,
            "Row",
            {"alignItems": "bottom", "flexShrink": 0, "itemMargin": 0},
            (num_id, unit_id),
        ),
        ComponentRow(
            num_id,
            "Text",
            number_props,
        ),
        ComponentRow(
            unit_id,
            "Text",
            unit_props,
        ),
    ]


def _ring_child_id(component_id: str, suffix: str) -> str:
    return f"{component_id}_{suffix}"


def _expand_timeline_units(rows: list[CompactRow]) -> list[CompactRow]:
    expanded_rows: list[CompactRow] = []
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "TimelineUnit":
            expanded_rows.append(row)
            continue
        expanded_rows.extend(_expand_timeline_unit(row))
    return expanded_rows


def _expand_timeline_unit(component: ComponentRow) -> list[ComponentRow]:
    height = _numeric_prop(component.props.get("height"), default=68)
    line_height = max(height - 16, 1)
    color = component.props.get("color", _TIMELINE_UNIT_DEFAULT_COLOR)
    line_color = component.props.get(
        "lineColor",
        _TIMELINE_UNIT_DEFAULT_LINE_COLOR,
    )
    dot_id = f"{component.component_id}_dot"
    line_id = f"{component.component_id}_line"
    return [
        ComponentRow(
            component.component_id,
            "Column",
            {
                "width": component.props.get("width", 16),
                "height": height,
                "alignItems": "center",
                "justifyContent": "start",
                "flexShrink": component.props.get("flexShrink", 0),
            },
            (dot_id, line_id),
        ),
        ComponentRow(
            dot_id,
            "Text",
            {
                "content": "",
                "width": 14,
                "height": 14,
                "borderRadius": 7,
                "borderWidth": 4,
                "borderColor": color,
                "backgroundColor": "#00FFFFFF",
                "flexShrink": 0,
            },
        ),
        ComponentRow(
            line_id,
            "Divider",
            {
                "width": 1,
                "height": line_height,
                "vertical": True,
                "color": line_color,
                "strokeWidth": 1,
                "flexShrink": 0,
            },
        ),
    ]


def _normalize_2x2_components(
    components: list[ComponentRow],
    data_model: dict[str, Any] | None = None,
) -> list[ComponentRow]:
    if not components or not _is_2x2_root(components[0].props):
        return components
    data_model = data_model or {}

    # Structural safety first: these rules remove duplicate icons and normalize
    # metric text before any layout-specific policy sees the component tree.
    strong_ring_components = _normalize_strong_background_ring_components(components)
    timeline_colors = _normalize_2x2_timeline_colors(strong_ring_components)
    without_duplicate_icons = _remove_duplicate_title_action_icons(timeline_colors)
    normalized_bottom_visuals = _normalize_bottom_icon_round_visuals(
        without_duplicate_icons,
    )
    metric_texts = _normalize_2x2_metric_texts(
        normalized_bottom_visuals,
        data_model,
    )

    # Layout policies below are intentionally narrow. Prefer deleting or
    # weakening these before changing protocol validation.
    flattened_content = _flatten_2x2_content_panels(metric_texts)
    fixed_weather = _normalize_weather_fixed_layout(flattened_content)
    compact_spacing = _normalize_2x2_gold_spacing(fixed_weather)
    compact_meetings = _compact_meeting_action_layout(compact_spacing)
    compact_app_usage = _compact_app_usage_layout(compact_meetings)
    text_pair_centered = _normalize_2x2_text_pair_centered_layout(compact_app_usage)
    positioned_actions = _right_align_root_icon_round_actions(text_pair_centered)

    # Final typography pass: cap unsafe non-numeric hero text and align rows.
    compact_text = _cap_non_numeric_hero_text(positioned_actions, data_model)
    weather_units = _normalize_weather_temperature_units(compact_text, data_model)
    bottom_aligned = _bottom_align_text_rows(weather_units)
    return _normalize_value_row_text_widths(bottom_aligned, data_model)


def _normalize_2x2_metric_texts(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> list[ComponentRow]:
    duration_units = _normalize_duration_unit_texts(components, data_model)
    metric_unit_rows = _normalize_separate_metric_unit_rows(duration_units)
    return _normalize_value_row_text_widths(metric_unit_rows, data_model)


def _normalize_2x2_gold_spacing(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Apply fixed 2x2 gold spacing that should not be model-controlled."""
    title_icon_ids = _title_area_icon_ids(components)
    has_bottom_ring = _has_bottom_ring_image_stack(components)
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        props = copy.deepcopy(component.props)
        component_id = component.component_id
        if component_id == "root":
            props["padding"] = 12
            props["itemMargin"] = 8
            props["justifyContent"] = "start"
        elif component_id == "title_area" and component.component_type == "Row":
            props["width"] = 136
            props["height"] = _TITLE_ICON_SIZE
            props["alignItems"] = "center"
            props["justifyContent"] = (
                "spaceBetween" if len(component.children) > 1 else "start"
            )
            props["flexShrink"] = 0
        elif component_id in title_icon_ids and component.component_type == "Image":
            props["width"] = _TITLE_ICON_SIZE
            props["height"] = _TITLE_ICON_SIZE
            props["flexShrink"] = 0
        elif component_id in {"content_area", "text_block", "main_area"} and (
            component.component_type == "Column"
        ):
            props["itemMargin"] = (
                4 if component_id == "content_area" and has_bottom_ring else 8
            )
        elif component_id in {"bottom_area", "bottom_row"} and (
            _has_icon_round_descendant(component, components)
        ):
            props["height"] = max(
                _numeric_prop(props.get("height"), default=_ICON_ROUND_SIZE),
                _ICON_ROUND_SIZE,
            )
            props["alignItems"] = "bottom"
            props["justifyContent"] = (
                "end" if len(component.children) == 1 else "spaceBetween"
            )
        elif component_id == "action_area" and _has_single_icon_round_child(
            component,
            components,
        ):
            props["width"] = _ICON_ROUND_SIZE
            props["height"] = _ICON_ROUND_SIZE
            props["flexShrink"] = 0
        elif component_id == "action_area" and _has_single_capsule_child(
            component,
            components,
        ):
            props["width"] = "matchParent"
            props["height"] = 36
            props["flexShrink"] = 0
        if props != component.props:
            replacements[component_id] = props
    return _replace_component_props(components, replacements)


def _has_bottom_ring_image_stack(components: list[ComponentRow]) -> bool:
    components_by_id = {
        component.component_id: component
        for component in components
    }
    return any(
        component.component_id in {"bottom_area", "bottom_row"}
        and any(
            _subtree_has_ring_image_stack(child_id, components_by_id)
            for child_id in component.children
        )
        for component in components
    )


def _title_area_icon_ids(components: list[ComponentRow]) -> set[str]:
    components_by_id = {
        component.component_id: component
        for component in components
    }
    title_area = components_by_id.get("title_area")
    if title_area is None:
        return set()
    return {
        child_id
        for child_id in title_area.children
        if components_by_id.get(child_id) is not None
        and components_by_id[child_id].component_type == "Image"
    }


def _has_single_icon_round_child(
    component: ComponentRow,
    components: list[ComponentRow],
) -> bool:
    if len(component.children) != 1:
        return False
    child_id = component.children[0]
    for candidate in components:
        if candidate.component_id == child_id:
            return (
                candidate.component_type == "ActionUnit"
                and candidate.props.get("state") == "icon-round"
            )
    return False


def _has_single_capsule_child(
    component: ComponentRow,
    components: list[ComponentRow],
) -> bool:
    if len(component.children) != 1:
        return False
    child_id = component.children[0]
    for candidate in components:
        if candidate.component_id == child_id:
            return (
                candidate.component_type == "ActionUnit"
                and candidate.props.get("state") == "capsule"
            )
    return False


def _has_icon_round_descendant(
    component: ComponentRow,
    components: list[ComponentRow],
) -> bool:
    components_by_id = {
        candidate.component_id: candidate
        for candidate in components
    }
    pending = list(component.children)
    while pending:
        child_id = pending.pop()
        child = components_by_id.get(child_id)
        if child is None:
            continue
        if (
            child.component_type == "ActionUnit"
            and child.props.get("state") == "icon-round"
        ):
            return True
        pending.extend(child.children)
    return False


def _compact_meeting_action_layout(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    ids = {component.component_id for component in components}
    has_meeting = "meeting_area" in ids and "action_area" in ids
    if not has_meeting:
        return components
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        props = copy.deepcopy(component.props)
        component_id = component.component_id
        if component_id == "root":
            props["itemMargin"] = 8
        elif component_id == "date_badge_area":
            props["height"] = min(_numeric_prop(props.get("height"), default=20), 20)
        elif component_id == "title_text":
            _cap_numeric_prop(props, "fontSize", 14)
            if "height" in props:
                props["height"] = min(_numeric_prop(props.get("height"), default=20), 20)
        elif component_id in {"meeting_head", "event_time"}:
            _cap_numeric_prop(props, "fontSize", 14)
            if component_id == "meeting_head":
                props["height"] = min(_numeric_prop(props.get("height"), default=16), 16)
        elif component_id == "meeting_area":
            props.pop("height", None)
            props["width"] = 136
            props["layoutWeight"] = 1
            props["flexShrink"] = 1
            props["alignItems"] = props.get("alignItems", "center")
            props["justifyContent"] = "start"
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=6), 6)
        elif component_id == "timeline":
            props["height"] = min(_numeric_prop(props.get("height"), default=48), 48)
        elif component_id == "timeline_line":
            props["height"] = min(_numeric_prop(props.get("height"), default=32), 32)
        elif component_id == "event_title":
            _cap_numeric_prop(props, "fontSize", 20)
        elif component_id == "event_time":
            _cap_numeric_prop(props, "fontSize", 14)
        elif component_id == "event_place":
            _cap_numeric_prop(props, "fontSize", 12)
        elif component_id == "meeting_texts":
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=4), 2)
        elif component_id == "action_area":
            props["width"] = "matchParent"
            props["height"] = 36
            props["flexShrink"] = 0
        elif component_id == "cta" and component.component_type in {"Button", "Row"}:
            props["height"] = min(_numeric_prop(props.get("height"), default=36), 36)
        elif component_id == "cta_text":
            props["height"] = min(_numeric_prop(props.get("height"), default=36), 36)
        if props != component.props:
            replacements[component_id] = props
    return _replace_component_props(components, replacements)


def _compact_app_usage_layout(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    ids = {component.component_id for component in components}
    has_app_usage = "duration_row" in ids and any(
        component_id in ids
        for component_id in {"app_icon", "app_name", "duration_label", "foot_area"}
    )
    if not has_app_usage:
        return components
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        props = copy.deepcopy(component.props)
        component_id = component.component_id
        if component_id == "root":
            props["itemMargin"] = 8
        elif component_id == "content_area":
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=6), 2)
        elif component_id in {"title_icon", "app_icon"}:
            maximum = _TITLE_ICON_SIZE if component_id == "title_icon" else 28
            props["width"] = min(_numeric_prop(props.get("width"), default=maximum), maximum)
            props["height"] = min(_numeric_prop(props.get("height"), default=maximum), maximum)
        elif component_id == "app_name":
            _cap_numeric_prop(props, "fontSize", 12)
            props["height"] = min(_numeric_prop(props.get("height"), default=14), 14)
        elif component_id == "duration_row":
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=1), 1)
            props["height"] = min(_numeric_prop(props.get("height"), default=28), 28)
            props["alignItems"] = "bottom"
            props["justifyContent"] = "start"
        elif component_id == "duration_num":
            _cap_numeric_prop(props, "fontSize", 24)
        elif component_id == "duration_unit":
            _cap_numeric_prop(props, "fontSize", 12)
        elif component_id == "duration_label":
            _cap_numeric_prop(props, "fontSize", 11)
            props["height"] = min(_numeric_prop(props.get("height"), default=14), 14)
        elif component_id == "foot_area":
            props["height"] = min(_numeric_prop(props.get("height"), default=16), 16)
        elif component_id == "foot_text":
            _cap_numeric_prop(props, "fontSize", 10)
            props["height"] = min(_numeric_prop(props.get("height"), default=14), 14)
        if props != component.props:
            replacements[component_id] = props
    return _replace_component_props(components, replacements)


def _normalize_2x2_text_pair_centered_layout(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Normalize non-metric two-line content to a stable centered text skeleton."""
    components_by_id = {
        component.component_id: component
        for component in components
    }
    if _has_bottom_ring_image_stack(components):
        return components

    pair_container_id = _text_pair_content_container_id(components_by_id)
    if pair_container_id is None:
        return components

    pair_container = components_by_id[pair_container_id]
    text_ids = list(pair_container.children)
    replacements: dict[str, dict[str, Any]] = {}

    content_area = components_by_id.get("content_area")
    if content_area is not None and content_area.component_type == "Column":
        props = copy.deepcopy(content_area.props)
        props["width"] = 136
        props["layoutWeight"] = 1
        props["justifyContent"] = "center"
        props["alignItems"] = "start"
        props["itemMargin"] = 4
        props["flexShrink"] = props.get("flexShrink", 1)
        replacements["content_area"] = props

    if pair_container.component_id != "content_area":
        props = copy.deepcopy(pair_container.props)
        props["width"] = 136
        props["layoutWeight"] = props.get("layoutWeight", 1)
        props["justifyContent"] = "center"
        props["alignItems"] = "start"
        props["itemMargin"] = 4
        props["flexShrink"] = props.get("flexShrink", 1)
        replacements[pair_container.component_id] = props

    for index, text_id in enumerate(text_ids):
        text_component = components_by_id[text_id]
        props = copy.deepcopy(text_component.props)
        props["width"] = 136
        props["maxLines"] = 1
        props["textOverflow"] = "clip"
        if index == 0:
            props["fontSize"] = min(_numeric_prop(props.get("fontSize"), default=20), 20)
            props["fontWeight"] = max(_numeric_prop(props.get("fontWeight"), default=700), 700)
            if "height" in props:
                props["height"] = min(_numeric_prop(props.get("height"), default=24), 24)
        else:
            props["fontSize"] = min(_numeric_prop(props.get("fontSize"), default=12), 12)
            props["fontWeight"] = min(_numeric_prop(props.get("fontWeight"), default=400), 400)
            if "height" in props:
                props["height"] = min(_numeric_prop(props.get("height"), default=16), 16)
        replacements[text_id] = props

    return _replace_component_props(components, replacements)


def _text_pair_content_container_id(
    components_by_id: dict[str, ComponentRow],
) -> str | None:
    content_area = components_by_id.get("content_area")
    if content_area is None or content_area.component_type != "Column":
        return None
    if _is_non_metric_two_text_container(content_area, components_by_id):
        return "content_area"
    if len(content_area.children) != 1:
        return None
    child = components_by_id.get(content_area.children[0])
    if child is None or child.component_type != "Column":
        return None
    if child.component_id not in {"text_block", "description_block"}:
        return None
    if _is_non_metric_two_text_container(child, components_by_id):
        return child.component_id
    return None


def _is_non_metric_two_text_container(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if len(component.children) != 2:
        return False
    children = [components_by_id.get(child_id) for child_id in component.children]
    if any(child is None or child.component_type != "Text" for child in children):
        return False
    first = children[0]
    assert first is not None
    if _is_metric_like_text_pair_primary(first):
        return False
    return True


def _is_metric_like_text_pair_primary(component: ComponentRow) -> bool:
    component_id = component.component_id.lower()
    if any(
        token in component_id
        for token in (
            "num",
            "value",
            "duration",
            "temperature",
            "battery",
            "percent",
            "score",
            "days",
            "steps",
            "calorie",
            "usage",
            "capacity",
            "soc",
            "level",
        )
    ):
        return True
    design = str(component.props.get("design", "")).lower()
    if "hero" in design:
        return True
    content = component.props.get("content")
    if isinstance(content, (int, float)) and not isinstance(content, bool):
        return True
    if isinstance(content, str):
        return bool(re.search(r"\d", content))
    if _is_path_binding(content):
        path = str(content.get("path", "")).lower()
        return any(
            token in path
            for token in (
                "percent",
                "soc",
                "level",
                "temperature",
                "duration",
                "score",
                "steps",
                "calorie",
                "count",
                "value",
                "usage",
                "amount",
                "size",
                "memory",
                "storage",
                "battery",
            )
        )
    return False


def _flatten_2x2_content_panels(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Remove content-area backing panels and vertical app stacks in 2x2 cards."""
    components_by_id = {
        component.component_id: component
        for component in components
    }
    replacements: dict[str, dict[str, Any]] = {}
    child_updates: dict[str, tuple[str, ...]] = {}
    removed_ids: set[str] = set()

    for component in components:
        if component.component_id != "content_area" or len(component.children) != 1:
            continue

        only_child_id = component.children[0]
        only_child = components_by_id.get(only_child_id)
        if only_child is None:
            continue

        props = copy.deepcopy(component.props)
        if only_child_id in {"tray_block", "setting_block"}:
            removed_ids.add(only_child_id)
            child_updates[component.component_id] = only_child.children
            props["width"] = 136
            props["itemMargin"] = min(
                _numeric_prop(
                    props.get("itemMargin", only_child.props.get("itemMargin")),
                    default=4,
                ),
                4,
            )
            props["alignItems"] = "start"
            props["justifyContent"] = (
                "start" if only_child_id == "setting_block" else "center"
            )
            props["flexShrink"] = props.get("flexShrink", 1)
            replacements[component.component_id] = props
            continue

        if only_child_id == "app_usage_block":
            flattened_children = [
                child_id
                for child_id in ("duration_row", "app_name", "duration_label")
                if child_id in only_child.children
            ]
            if not flattened_children:
                continue
            removed_ids.update({"app_usage_block", "app_icon"})
            child_updates[component.component_id] = tuple(flattened_children)
            props["width"] = 136
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=4), 4)
            props["alignItems"] = "start"
            props["justifyContent"] = "center"
            props["flexShrink"] = props.get("flexShrink", 1)
            replacements[component.component_id] = props

    for component in components:
        props = copy.deepcopy(component.props)
        component_id = component.component_id
        if component_id.startswith("setting_row_") and component.component_type == "Row":
            props["width"] = 136
            props["height"] = min(_numeric_prop(props.get("height"), default=14), 14)
            props["alignItems"] = "bottom"
            props["justifyContent"] = "spaceBetween"
            props["flexShrink"] = 0
        elif component_id in {"tray_heading", "tray_body"} and component.component_type == "Text":
            props["width"] = 136
            _cap_numeric_prop(props, "fontSize", 14 if component_id == "tray_heading" else 12)
            props["maxLines"] = 1
            props["textOverflow"] = "clip"
        if props != component.props:
            replacements[component_id] = props

    if not replacements and not child_updates and not removed_ids:
        return components
    return _replace_component_props(
        components,
        replacements,
        child_updates=child_updates,
        removed_ids=removed_ids,
    )


def _normalize_weather_fixed_layout(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Keep 2x2 weather cards on the fixed Want/q20 layout."""
    ids = {component.component_id for component in components}
    is_weather_candidate = (
        _root_gradient_color_set(components) in _WEATHER_ROOT_GRADIENT_COLOR_SETS
        or "weather_texts" in ids
    )
    if not is_weather_candidate or "bottom_area" not in ids:
        return components
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        props = copy.deepcopy(component.props)
        component_id = component.component_id
        if component_id == "root":
            props["itemMargin"] = 8
            props["justifyContent"] = "start"
        elif component_id == "title_area":
            props["width"] = 136
            props["height"] = min(_numeric_prop(props.get("height"), default=20), 20)
            props["alignItems"] = "top"
            props["justifyContent"] = (
                "spaceBetween" if len(component.children) > 1 else "start"
            )
            props["flexShrink"] = 0
        elif component_id == "value_row":
            props["width"] = 136
            props["layoutWeight"] = 1
            props["alignItems"] = "bottom"
            props["justifyContent"] = "start"
            props["flexShrink"] = 1
        elif component_id == "bottom_area":
            props["width"] = 136
            props["height"] = min(_numeric_prop(props.get("height"), default=42), 42)
            props["alignItems"] = "bottom"
            props["justifyContent"] = (
                "spaceBetween" if len(component.children) > 1 else "start"
            )
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=8), 8)
            props["flexShrink"] = 0
        elif component_id == "weather_texts":
            props["width"] = min(_numeric_prop(props.get("width"), default=96), 96)
            props["height"] = min(_numeric_prop(props.get("height"), default=42), 42)
            props["itemMargin"] = 8
            props["justifyContent"] = "end"
            props["alignItems"] = "start"
            props["flexShrink"] = 1
        elif component_id == "action_area":
            props["width"] = _ICON_ROUND_SIZE
            props["height"] = _ICON_ROUND_SIZE
            props["flexShrink"] = 0
        elif component_id == "value_num":
            _cap_numeric_prop(props, "fontSize", 30)
        elif component_id == "value_unit":
            props["fontSize"] = 30
            props["fontWeight"] = 700
            props["padding"] = {"bottom": 0}
        elif component_id in {"condition_text", "suggestion_text", "humidity_text"}:
            _cap_numeric_prop(props, "fontSize", 12)
        if props != component.props:
            replacements[component_id] = props
    return _replace_component_props(components, replacements)


def _cap_non_numeric_hero_text(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> list[ComponentRow]:
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        if component.component_type != "Text":
            continue
        props = copy.deepcopy(component.props)
        font_size = _numeric_prop(props.get("fontSize"), default=0)
        if font_size < 28 and not _is_prominent_object_text(
            component.component_id,
            font_size,
        ):
            continue
        preview = _text_component_preview(props.get("content"), data_model)
        if _is_numeric_hero_preview(preview):
            continue
        props["fontSize"] = 20
        max_font_size = _numeric_prop(props.get("maxFontSize"), default=20)
        if max_font_size > 20:
            props["maxFontSize"] = 20
        if "height" in props:
            props["height"] = min(_numeric_prop(props.get("height"), default=24), 24)
        replacements[component.component_id] = props
    return _replace_component_props(components, replacements)


def _normalize_weather_temperature_units(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> list[ComponentRow]:
    ids = {component.component_id for component in components}
    if "value_row" not in ids or "bottom_area" not in ids:
        return components
    if not (
        _root_gradient_color_set(components) in _WEATHER_ROOT_GRADIENT_COLOR_SETS
        or "weather_texts" in ids
    ):
        return components
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        if component.component_id != "value_unit" or component.component_type != "Text":
            continue
        preview = _text_component_preview(component.props.get("content"), data_model)
        if not _is_temperature_unit_preview(preview):
            continue
        props = copy.deepcopy(component.props)
        props["fontSize"] = 30
        props["fontWeight"] = 700
        props["padding"] = {"bottom": 0}
        replacements[component.component_id] = props
    return _replace_component_props(components, replacements)


def _is_temperature_unit_preview(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip() in {"°", "℃", "°C", "°c"}


def _is_prominent_object_text(component_id: str, font_size: float) -> bool:
    if font_size < 22:
        return False
    normalized_id = component_id.lower()
    return any(
        token in normalized_id
        for token in (
            "primary_text",
            "primary_title",
            "main_text",
            "object_text",
            "entry_text",
            "heading",
            "app_name",
        )
    )


def _is_numeric_hero_preview(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip()
    if not normalized:
        return False
    return bool(
        re.fullmatch(
            r"(?:[+-]?\d+(?:\.\d+)?\s*(?:%|°C|℃|°|GB|MB|KB|B|G|M|K|"
            r"分|分钟|小时|时|天|步|次|台|个|条)?|\d{1,2}:\d{2})",
            normalized,
            flags=re.IGNORECASE,
        )
    )



def _cap_numeric_prop(props: dict[str, Any], key: str, maximum: int) -> None:
    value = props.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > maximum:
        props[key] = maximum


def _replace_component_props(
    components: list[ComponentRow],
    replacements: dict[str, dict[str, Any]],
    *,
    child_updates: dict[str, tuple[str, ...]] | None = None,
    removed_ids: set[str] | None = None,
) -> list[ComponentRow]:
    child_updates = child_updates or {}
    removed_ids = removed_ids or set()
    normalized: list[ComponentRow] = []
    for component in components:
        if component.component_id in removed_ids:
            continue
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                replacements.get(component.component_id, component.props),
                child_updates.get(component.component_id, component.children),
            )
        )
    return normalized


def _normalize_value_row_text_widths(
    components: list[ComponentRow],
    data_model: dict[str, Any] | None = None,
) -> list[ComponentRow]:
    """Keep a 2x2 hero value and its unit from each claiming the whole row."""
    data_model = data_model or {}
    components_by_id = {
        component.component_id: component
        for component in components
    }
    metric_pairs_by_row: dict[str, list[tuple[str, str]]] = {}
    metric_row_ids: set[str] = set()
    for component in components:
        normalized_id = component.component_id.lower()
        if component.component_type != "Row":
            continue
        is_metric_row = any(
            token in normalized_id
            for token in ("value_row", "metric_row", "duration_row", "temperature_row")
        )
        if is_metric_row:
            metric_row_ids.add(component.component_id)
        direct_text_ids = [
            child_id
            for child_id in component.children
            if components_by_id.get(child_id) is not None
            and components_by_id[child_id].component_type == "Text"
        ]
        metric_pairs = _adjacent_metric_text_pairs(direct_text_ids, components_by_id)
        if metric_pairs or (is_metric_row and len(direct_text_ids) >= 2):
            metric_pairs_by_row[component.component_id] = metric_pairs or [
                (direct_text_ids[0], direct_text_ids[1])
            ]

    if not metric_pairs_by_row and not metric_row_ids:
        return components
    value_text_ids = {
        text_id
        for pairs in metric_pairs_by_row.values()
        for pair in pairs
        for text_id in pair
    }
    number_text_ids = {
        number_id
        for pairs in metric_pairs_by_row.values()
        for number_id, _unit_id in pairs
    }
    unit_text_ids = {
        unit_id
        for pairs in metric_pairs_by_row.values()
        for _number_id, unit_id in pairs
    }
    normalized: list[ComponentRow] = []
    for component in components:
        if component.component_id in metric_row_ids:
            props = copy.deepcopy(component.props)
            props["alignItems"] = "bottom"
            props["justifyContent"] = "start"
            props["itemMargin"] = min(_numeric_prop(props.get("itemMargin"), default=1), 1)
            normalized.append(
                ComponentRow(
                    component.component_id,
                    component.component_type,
                    props,
                    component.children,
                )
            )
            continue
        if component.component_id not in value_text_ids:
            normalized.append(component)
            continue
        props = copy.deepcopy(component.props)
        if component.component_id in number_text_ids:
            width = _metric_number_text_width(component, data_model)
        else:
            width = _metric_unit_text_width(component, data_model)
        current_width = props.get("width")
        if current_width == "matchParent" or (
            isinstance(current_width, (int, float))
            and not isinstance(current_width, bool)
            and current_width > width
        ):
            props["width"] = width
        elif current_width is None and component.component_id in number_text_ids | unit_text_ids:
            props["width"] = width
        props["flexShrink"] = 0
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )
        )
    return normalized


def _normalize_separate_metric_unit_rows(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Fold adjacent number/unit Text children in a Column into one bottom-aligned Row."""
    components_by_id = {
        component.component_id: component
        for component in components
    }
    used_ids = set(components_by_id)
    child_updates: dict[str, tuple[str, ...]] = {}
    inserted_after: dict[str, ComponentRow] = {}

    for component in components:
        if component.component_type != "Column":
            continue
        direct_text_ids = [
            child_id
            for child_id in component.children
            if components_by_id.get(child_id) is not None
            and components_by_id[child_id].component_type == "Text"
        ]
        if len(direct_text_ids) < 2:
            continue
        pairs = _adjacent_metric_text_pairs(direct_text_ids, components_by_id)
        if not pairs:
            continue
        number_id, unit_id = pairs[0]
        row_id = _unique_child_id(f"{component.component_id}_metric_row", used_ids)
        used_ids.add(row_id)
        updated_children: list[str] = []
        child_index = 0
        while child_index < len(component.children):
            child_id = component.children[child_index]
            if (
                child_id == number_id
                and child_index + 1 < len(component.children)
                and component.children[child_index + 1] == unit_id
            ):
                updated_children.append(row_id)
                child_index += 2
                continue
            updated_children.append(child_id)
            child_index += 1
        child_updates[component.component_id] = tuple(updated_children)
        inserted_after[component.component_id] = ComponentRow(
            row_id,
            "Row",
            {
                "width": "matchParent",
                "alignItems": "bottom",
                "justifyContent": "start",
                "itemMargin": 1,
                "flexShrink": 0,
            },
            (number_id, unit_id),
        )

    if not child_updates:
        return components
    normalized: list[ComponentRow] = []
    for component in components:
        current = component
        if component.component_id in child_updates:
            current = ComponentRow(
                component.component_id,
                component.component_type,
                component.props,
                child_updates[component.component_id],
            )
        normalized.append(current)
        inserted = inserted_after.get(component.component_id)
        if inserted is not None:
            normalized.append(inserted)
    return normalized


def _adjacent_metric_text_pairs(
    text_ids: list[str],
    components_by_id: dict[str, ComponentRow],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index in range(len(text_ids) - 1):
        number_id = text_ids[index]
        unit_id = text_ids[index + 1]
        number = components_by_id[number_id]
        unit = components_by_id[unit_id]
        if not _looks_like_metric_number(number) or not _looks_like_metric_unit(unit):
            continue
        pairs.append((number_id, unit_id))
    return pairs


def _looks_like_metric_number(component: ComponentRow) -> bool:
    component_id = component.component_id.lower()
    if any(token in component_id for token in ("num", "value", "primary_text", "duration")):
        return True
    content = component.props.get("content")
    if isinstance(content, (int, float)) and not isinstance(content, bool):
        return True
    return isinstance(content, str) and bool(re.search(r"\d", content))


def _looks_like_metric_unit(component: ComponentRow) -> bool:
    component_id = component.component_id.lower()
    if "unit" in component_id:
        return True
    preview = component.props.get("content")
    return _is_metric_unit_value(preview)


def _is_metric_unit_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip() in {"%", "°", "°C", "℃", "分", "分钟", "小时", "时", "天", "步"}


def _metric_number_text_width(
    component: ComponentRow,
    data_model: dict[str, Any],
) -> int:
    font_size = _numeric_prop(component.props.get("fontSize"), default=30)
    preview = _text_component_preview(component.props.get("content"), data_model)
    if preview is None:
        preview = component.props.get("content")
    text = str(preview or "")
    digits = re.findall(r"\d", text)
    length = max(len(digits), 2)
    if "." in text:
        length += 1
    return max(34, min(82, int(font_size * length * 0.62) + 4))


def _metric_unit_text_width(
    component: ComponentRow,
    data_model: dict[str, Any],
) -> int:
    font_size = _numeric_prop(component.props.get("fontSize"), default=16)
    preview = _text_component_preview(component.props.get("content"), data_model)
    if preview is None:
        preview = component.props.get("content")
    text = str(preview or "").strip() or "%"
    return max(14, min(44, int(font_size * len(text) * 0.58) + 4))


def _normalize_duration_unit_texts(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> list[ComponentRow]:
    """Avoid rendering minute/hour unit text as a 30fp hero value."""
    large_duration_ids = _large_duration_text_ids(components, data_model)
    if not large_duration_ids:
        return components

    parent_by_child = _parent_by_child_id(components)
    children_updates: dict[str, tuple[str, ...]] = {}
    replacements: dict[str, ComponentRow] = {}
    inserted_after: dict[str, ComponentRow] = {}
    used_ids = {component.component_id for component in components}
    components_by_id = {component.component_id: component for component in components}

    for component_id, match in large_duration_ids.items():
        component = components_by_id[component_id]
        props = copy.deepcopy(component.props)
        content = props.get("content")
        if isinstance(content, str):
            parent_id = parent_by_child.get(component_id)
            if parent_id is None:
                continue
            unit_id = _unique_child_id(f"{component_id}_unit", used_ids)
            used_ids.add(unit_id)
            props["content"] = match.group("number")
            if props.get("width") == "matchParent":
                props.pop("width")
            props["flexShrink"] = 0
            replacements[component_id] = ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )
            inserted_after[component_id] = ComponentRow(
                unit_id,
                "Text",
                _duration_unit_text_props(props, match.group("unit")),
            )
            parent = components_by_id[parent_id]
            children_updates[parent_id] = _insert_child_after(
                parent.children,
                component_id,
                unit_id,
            )
            continue

        if _is_path_binding(content):
            props["fontSize"] = min(
                _numeric_prop(props.get("fontSize"), default=30),
                _DURATION_TEXT_HERO_FALLBACK_FONT_SIZE,
            )
            max_font_size = _numeric_prop(
                props.get("maxFontSize"),
                default=props["fontSize"],
            )
            if max_font_size > props["fontSize"]:
                props["maxFontSize"] = props["fontSize"]
            replacements[component_id] = ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )

    if not replacements and not inserted_after and not children_updates:
        return components

    normalized: list[ComponentRow] = []
    for component in components:
        current = replacements.get(component.component_id, component)
        if current.component_id in children_updates:
            current = ComponentRow(
                current.component_id,
                current.component_type,
                current.props,
                children_updates[current.component_id],
            )
        normalized.append(current)
        inserted = inserted_after.get(component.component_id)
        if inserted is not None:
            normalized.append(inserted)
    return normalized


def _large_duration_text_ids(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> dict[str, re.Match[str]]:
    matches: dict[str, re.Match[str]] = {}
    for component in components:
        if component.component_type != "Text":
            continue
        if _numeric_prop(component.props.get("fontSize"), default=0) < 28:
            continue
        match = _duration_unit_match(
            _text_component_preview(component.props.get("content"), data_model)
        )
        if match is not None:
            matches[component.component_id] = match
    return matches


def _text_component_preview(
    content: Any,
    data_model: dict[str, Any],
) -> Any:
    if isinstance(content, str):
        return content
    if _is_path_binding(content):
        found, value = _json_pointer_value(data_model, content["path"])
        if found:
            return value
    return None


def _duration_unit_match(value: Any) -> re.Match[str] | None:
    if not isinstance(value, str):
        return None
    return _DURATION_UNIT_PATTERN.fullmatch(value)


def _duration_unit_text_props(
    number_props: dict[str, Any],
    unit: str,
) -> dict[str, Any]:
    return {
        "content": unit,
        "fontSize": 12,
        "fontWeight": 400,
        "fontColor": number_props.get("fontColor", "#99000000"),
        "maxLines": 1,
        "textOverflow": "clip",
        "flexShrink": 0,
    }


def _numeric_prop(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    return default


def _parent_by_child_id(
    components: list[ComponentRow],
) -> dict[str, str]:
    return {
        child_id: component.component_id
        for component in components
        for child_id in component.children
    }


def _unique_child_id(seed: str, used_ids: set[str]) -> str:
    if seed not in used_ids:
        return seed
    index = 2
    while f"{seed}_{index}" in used_ids:
        index += 1
    return f"{seed}_{index}"


def _insert_child_after(
    children: tuple[str, ...],
    current_id: str,
    inserted_id: str,
) -> tuple[str, ...]:
    updated: list[str] = []
    for child_id in children:
        updated.append(child_id)
        if child_id == current_id:
            updated.append(inserted_id)
    return tuple(updated)


def _normalize_semantic_root_palette(components: list[ComponentRow]) -> None:
    """Diversify generic light-blue cards using their visible static semantics."""
    color_set = _root_gradient_color_set(components)
    if color_set not in _SEMANTIC_REPAIRABLE_ROOT_GRADIENT_COLOR_SETS:
        return
    visible_text = " ".join(
        content.lower()
        for component in components
        if component.component_type == "Text"
        for content in [component.props.get("content")]
        if isinstance(content, str)
    )
    semantic_palettes = (
        (("耳机", "音乐", "音频", "播放", "歌曲", "headphone", "music", "audio"), 5),
        (("应用", "抖音", "使用时长", "防沉迷", "app", "screen time"), 1),
        (("电话", "通话", "联系人", "call", "contact"), 3),
        (("闹钟", "倒计时", "提醒", "待办", "alarm", "countdown", "reminder"), 4),
        (("健康", "运动", "步数", "心率", "health", "sport", "steps"), 3),
        (("电量", "省电", "充电", "内存", "存储", "battery", "power", "storage"), 3),
        (("日程", "会议", "calendar", "meeting"), 0),
        (("专注", "focus"), 5),
        (("蓝牙", "网络", "连接", "bluetooth", "network", "connect"), 2),
    )
    palette_index = next(
        (
            index
            for keywords, index in semantic_palettes
            if any(keyword in visible_text for keyword in keywords)
        ),
        None,
    )
    if palette_index is None:
        return
    components[0].props["linearGradient"] = copy.deepcopy(
        _ROOT_LINEAR_GRADIENT_PALETTES[palette_index]
    )


def _validate_sleep_card_without_ring(
    components: list[ComponentRow],
) -> None:
    if _root_gradient_color_set(components) != _SLEEP_ROOT_GRADIENT_COLOR_SET:
        return
    for component in components:
        if (
            component.component_type == "Progress"
            and component.props.get("type") == "ring"
        ):
            raise CompactDslConversionError(
                f"{component.component_id}: sleep cards must not use a ring; "
                "place the score and status in a left-aligned content area "
                "and keep the icon action at the bottom right."
            )


def _validate_ring_image_action_row(
    components: list[ComponentRow],
) -> None:
    components_by_id = {
        component.component_id: component
        for component in components
    }
    for component in components:
        if component.component_type != "Row" or len(component.children) < 3:
            continue
        ring_children = {
            child_id
            for child_id in component.children
            if _subtree_has_ring_image_stack(child_id, components_by_id)
        }
        action_children = {
            child_id
            for child_id in component.children
            if _subtree_has_icon_round_action(child_id, components_by_id)
        }
        if not ring_children or not action_children:
            continue
        text_children = {
            child_id
            for child_id in component.children
            if _subtree_has_component_type(
                child_id,
                "Text",
                components_by_id,
            )
        }
        misplaced_text = text_children - ring_children - action_children
        if misplaced_text:
            names = ", ".join(sorted(misplaced_text))
            raise CompactDslConversionError(
                f"{component.component_id}: move status text ({names}) above "
                "the bottom visual row; a Want/q9 row may contain only the "
                "left ring image and the right icon-round action."
            )


def _validate_2x2_icon_round_layout(
    components: list[ComponentRow],
) -> None:
    if not components or not _is_2x2_root(components[0].props):
        return
    components_by_id = {
        component.component_id: component
        for component in components
    }
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in component.children
    }
    for component in components:
        if component.component_type != "ActionUnit":
            continue
        if component.props.get("state") != "icon-round":
            continue
        if _is_allowed_bottom_icon_round_action(
            component,
            components_by_id,
            parent_by_child,
        ):
            continue
        raise CompactDslConversionError(
            f"{component.component_id}: icon-round ActionUnit is only allowed "
            "as the final 40x40 action in weather/Want-q9/Want-q20/strong "
            "bottom action rows. Use a bottom capsule for generic text-entry "
            "cards; do not create left-text/right-icon layouts."
        )


def _is_allowed_bottom_icon_round_action(
    action: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    parent_by_child: dict[str, ComponentRow],
) -> bool:
    parent = parent_by_child.get(action.component_id)
    if parent is None:
        return False
    bottom_area = _bottom_area_for_icon_round_action(
        action,
        parent,
        parent_by_child,
    )
    if bottom_area is None:
        return False
    action_entry_id = parent.component_id if parent is not bottom_area else action.component_id
    if not bottom_area.children or bottom_area.children[-1] != action_entry_id:
        return False
    if len(bottom_area.children) == 1:
        return True
    if _subtree_contains_component_id(bottom_area, components_by_id, "weather_texts"):
        return True
    if any(
        _subtree_has_ring_image_stack(child_id, components_by_id)
        for child_id in bottom_area.children
        if child_id != action_entry_id
    ):
        return True
    return False


def _bottom_area_for_icon_round_action(
    action: ComponentRow,
    parent: ComponentRow,
    parent_by_child: dict[str, ComponentRow],
) -> ComponentRow | None:
    if parent.component_id == "bottom_area" and parent.component_type == "Row":
        return parent
    if (
        parent.component_type == "Column"
        and parent.children == (action.component_id,)
    ):
        grandparent = parent_by_child.get(parent.component_id)
        if grandparent is not None and grandparent.component_id == "bottom_area":
            return grandparent
    return None


def _subtree_contains_component_id(
    root: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    component_id: str,
) -> bool:
    pending = list(root.children)
    visited: set[str] = set()
    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        if current_id == component_id:
            return True
        component = components_by_id.get(current_id)
        if component is not None:
            pending.extend(component.children)
    return False


def _subtree_has_ring_image_stack(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    component = components_by_id.get(component_id)
    if component is None or component.component_type != "Stack":
        return False
    child_types = {
        components_by_id[child_id].component_type
        for child_id in component.children
        if child_id in components_by_id
    }
    return {"Progress", "Image"}.issubset(child_types)


def _subtree_has_icon_round_action(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    pending = [component_id]
    visited: set[str] = set()
    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        component = components_by_id.get(current_id)
        if component is None:
            continue
        if (
            component.component_type == "ActionUnit"
            and component.props.get("state") == "icon-round"
        ):
            return True
        pending.extend(component.children)
    return False


def _subtree_has_component_type(
    component_id: str,
    component_type: str,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    pending = [component_id]
    visited: set[str] = set()
    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        component = components_by_id.get(current_id)
        if component is None:
            continue
        if component.component_type == component_type:
            return True
        pending.extend(component.children)
    return False


def _normalize_bottom_icon_round_visuals(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    """Keep bottom icon-round rows on the allowed weather/text-or-ring skeleton.

    A bottom row may pair an icon-round action with weather text or a distinct
    ring image stack. Repeated/semantic-duplicate rings and plain bottom-left
    images are removed, preserving the bottom-right action.
    """
    components_by_id = {
        component.component_id: component
        for component in components
    }
    removed_ids: set[str] = set()
    child_updates: dict[str, tuple[str, ...]] = {}
    prop_replacements: dict[str, dict[str, Any]] = {}

    for component in components:
        if component.component_id not in {"bottom_area", "bottom_row"}:
            continue
        if component.component_type != "Row":
            continue
        action_entry_ids = [
            child_id
            for child_id in component.children
            if _subtree_has_icon_round_action(child_id, components_by_id)
        ]
        if not action_entry_ids:
            continue

        ring_entry_ids = [
            child_id
            for child_id in component.children
            if _subtree_has_ring_image_stack(child_id, components_by_id)
        ]
        action_icon_sources = {
            _normalized_icon_basename(src)
            for action_id in action_entry_ids
            for src in _icon_round_action_icon_sources(action_id, components_by_id)
        }
        content_has_three_text_rows = _content_text_line_count_before_component(
            component.component_id,
            components,
            components_by_id,
        ) >= 3

        removable_ids: list[str] = []
        for ring_id in ring_entry_ids:
            ring_sources = {
                _normalized_icon_basename(src)
                for src in _ring_image_icon_sources(ring_id, components_by_id)
            }
            icon_repeats_action = bool(action_icon_sources) and any(
                _icons_conflict(ring_source, action_source)
                for ring_source in ring_sources
                for action_source in action_icon_sources
            )
            if icon_repeats_action or content_has_three_text_rows:
                removable_ids.append(ring_id)

        removable_ids.extend(
            child_id
            for child_id in component.children
            if child_id not in action_entry_ids
            and child_id not in removable_ids
            and _is_plain_bottom_visual_image(child_id, components_by_id)
        )
        if not removable_ids:
            continue
        for child_id in removable_ids:
            removed_ids.update(_subtree_component_ids(child_id, components_by_id))
        updated_children = tuple(
            child_id
            for child_id in component.children
            if child_id not in removable_ids
        )
        child_updates[component.component_id] = updated_children
        props = copy.deepcopy(component.props)
        props["height"] = max(
            _numeric_prop(props.get("height"), default=_ICON_ROUND_SIZE),
            _ICON_ROUND_SIZE,
        )
        props["alignItems"] = "bottom"
        props["justifyContent"] = (
            "end" if len(updated_children) == 1 else "spaceBetween"
        )
        props["itemMargin"] = 8
        props["flexShrink"] = 0
        prop_replacements[component.component_id] = props

    if not removed_ids and not child_updates and not prop_replacements:
        return components
    return _replace_component_props(
        components,
        prop_replacements,
        child_updates=child_updates,
        removed_ids=removed_ids,
    )


def _is_plain_bottom_visual_image(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> bool:
    if _subtree_has_ring_image_stack(component_id, components_by_id):
        return False
    component = components_by_id.get(component_id)
    if component is None:
        return False
    if component.component_type == "Image":
        return True
    return (
        component.component_type in _CONTAINER_TYPES
        and _subtree_has_component_type(component_id, "Image", components_by_id)
        and not _subtree_has_component_type(component_id, "Text", components_by_id)
    )


def _icon_round_action_icon_sources(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> set[str]:
    sources: set[str] = set()
    pending = [component_id]
    visited: set[str] = set()
    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        component = components_by_id.get(current_id)
        if component is None:
            continue
        if (
            component.component_type == "ActionUnit"
            and component.props.get("state") == "icon-round"
        ):
            icon = component.props.get("icon")
            if isinstance(icon, str) and icon:
                sources.add(icon)
        pending.extend(component.children)
    return sources


def _ring_image_icon_sources(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> set[str]:
    sources: set[str] = set()
    pending = [component_id]
    visited: set[str] = set()
    while pending:
        current_id = pending.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        component = components_by_id.get(current_id)
        if component is None:
            continue
        if component.component_type == "Image":
            src = component.props.get("src")
            if isinstance(src, str) and src:
                sources.add(src)
        pending.extend(component.children)
    return sources


def _subtree_component_ids(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> set[str]:
    component_ids: set[str] = set()
    pending = [component_id]
    while pending:
        current_id = pending.pop()
        if current_id in component_ids:
            continue
        component_ids.add(current_id)
        component = components_by_id.get(current_id)
        if component is not None:
            pending.extend(component.children)
    return component_ids


def _content_text_line_count_before_component(
    component_id: str,
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
) -> int:
    root = components[0] if components else None
    if root is None or root.component_id != "root":
        return 0
    count = 0
    for child_id in root.children:
        if child_id == component_id:
            break
        if child_id in {"title_area", "title", "action_area"}:
            continue
        count += _visible_text_line_count(child_id, components_by_id)
    return count


def _visible_text_line_count(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
) -> int:
    component = components_by_id.get(component_id)
    if component is None:
        return 0
    if component.component_type == "Text":
        max_lines = _numeric_prop(component.props.get("maxLines"), default=1)
        return max(1, min(max_lines, 3))
    if component.component_type == "Row":
        return 1 if any(
            _subtree_has_component_type(child_id, "Text", components_by_id)
            for child_id in component.children
        ) else 0
    return sum(
        _visible_text_line_count(child_id, components_by_id)
        for child_id in component.children
    )


def _normalized_icon_basename(source: str) -> str:
    return source.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _icons_conflict(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return any(
        left in icon_group and right in icon_group
        for icon_group in _BOTTOM_RING_ACTION_EQUIVALENT_ICON_GROUPS
    )


def _right_align_root_icon_round_actions(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    root = components[0]
    components_by_id = {
        component.component_id: component
        for component in components
    }
    root_child_ids = set(root.children)
    action_container_ids = {
        component.component_id
        for component in components
        if component.component_id in root_child_ids
        and component.component_type == "Column"
        and _subtree_has_icon_round_action(
            component.component_id,
            components_by_id,
        )
    }
    if not action_container_ids:
        return components
    normalized: list[ComponentRow] = []
    for component in components:
        if component.component_id not in action_container_ids:
            normalized.append(component)
            continue
        props = copy.deepcopy(component.props)
        props["width"] = "matchParent"
        props["alignItems"] = "end"
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )
        )
    return normalized


def _normalize_strong_background_ring_components(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    color_set = _root_gradient_color_set(components)
    if color_set not in _STRONG_ROOT_GRADIENT_COLOR_SETS:
        return components
    normalized: list[ComponentRow] = []
    for component in components:
        props = copy.deepcopy(component.props)
        if component.component_id.endswith("_ring_bar"):
            props["color"] = "#FFFFFFFF"
            props["backgroundColor"] = "#33FFFFFF"
        if (
            component.component_type == "Text"
            and component.component_id.endswith(
                (
                    "_reading_num",
                    "_reading_unit",
                    "_center_reading",
                    "_reading_below",
                )
            )
        ):
            props["fontColor"] = "#FFFFFFFF"
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )
        )
    return normalized


def _validate_2x2_capsule_layout(components: list[ComponentRow]) -> None:
    root = components[0]
    components_by_id = {
        component.component_id: component
        for component in components
    }
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in component.children
    }
    is_weather_card = (
        _root_gradient_color_set(components) in _WEATHER_ROOT_GRADIENT_COLOR_SETS
    )
    for component in components:
        if component.component_type != "ActionUnit":
            continue
        if component.props.get("state") != "capsule":
            continue
        if is_weather_card:
            raise CompactDslConversionError(
                f"{component.component_id}: weather cards must use the compact "
                "weather layout with an optional icon-round action; do not use "
                "a full-width capsule on weather gradients."
            )
        parent = parent_by_child.get(component.component_id)
        is_direct_root_footer = (
            parent is root
            and bool(root.children)
            and root.children[-1] == component.component_id
        )
        is_isolated_root_footer = (
            parent is not None
            and parent.component_type == "Column"
            and parent.children == (component.component_id,)
            and bool(root.children)
            and root.children[-1] == parent.component_id
            and components_by_id.get(parent.component_id) is parent
        )
        if is_direct_root_footer or is_isolated_root_footer:
            continue
        raise CompactDslConversionError(
            f"{component.component_id}: capsule ActionUnit must be the final "
            "root child or the only child of a final root-level action Column; "
            "do not place a full-width capsule beside content in Row."
        )


def _remove_duplicate_title_action_icons(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    action_icons = {
        _normalized_icon_basename(icon)
        for component in components
        if component.component_type == "ActionUnit"
        for icon in [component.props.get("icon")]
        if isinstance(icon, str) and icon
    }
    if not action_icons:
        return components
    children_by_id = {
        component.component_id: component.children
        for component in components
    }
    parent_by_child = {
        child_id: component.component_id
        for component in components
        for child_id in component.children
    }
    title_region_ids = _collect_title_region_ids(components[0], children_by_id)
    removed_ids = {
        component.component_id
        for component in components
        if component.component_type == "Image"
        and any(
            _icons_conflict(
                _normalized_icon_basename(component.props.get("src", "")),
                action_icon,
            )
            for action_icon in action_icons
        )
        and (
            component.component_id in title_region_ids
            or _is_title_region_component(component.component_id, parent_by_child)
        )
    }
    if not removed_ids:
        return components
    normalized: list[ComponentRow] = []
    for component in components:
        if component.component_id in removed_ids:
            continue
        children = tuple(
            child_id
            for child_id in component.children
            if child_id not in removed_ids
        )
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                component.props,
                children,
            )
        )
    return normalized


def _collect_title_region_ids(
    root: ComponentRow,
    children_by_id: dict[str, tuple[str, ...]],
) -> set[str]:
    if root.component_id != "root" or not root.children:
        return set()
    pending = [root.children[0]]
    region_ids: set[str] = set()
    while pending:
        component_id = pending.pop()
        if component_id in region_ids:
            continue
        region_ids.add(component_id)
        pending.extend(children_by_id.get(component_id, ()))
    return region_ids


def _is_title_region_component(
    component_id: str,
    parent_by_child: dict[str, str],
) -> bool:
    current_id: str | None = component_id
    while current_id is not None:
        normalized_id = current_id.lower()
        if "title" in normalized_id or "header" in normalized_id:
            return True
        current_id = parent_by_child.get(current_id)
    return False


def _bottom_align_text_rows(
    components: list[ComponentRow],
) -> list[ComponentRow]:
    component_types = {
        component.component_id: component.component_type
        for component in components
    }
    normalized: list[ComponentRow] = []
    for component in components:
        text_count = sum(
            component_types.get(child_id) == "Text"
            for child_id in component.children
        )
        if component.component_type != "Row" or text_count < 2:
            normalized.append(component)
            continue
        props = copy.deepcopy(component.props)
        props["alignItems"] = "bottom"
        normalized.append(
            ComponentRow(
                component.component_id,
                component.component_type,
                props,
                component.children,
            )
        )
    return normalized


def _canonicalize_component_order(rows: list[CompactRow]) -> list[CompactRow]:
    components_by_id: dict[str, ComponentRow] = {}
    data_rows: list[DataRow] = []
    duplicate_ids: set[str] = set()

    for row in rows:
        if isinstance(row, DataRow):
            data_rows.append(row)
            continue
        if row.component_id in components_by_id:
            duplicate_ids.add(row.component_id)
        components_by_id[row.component_id] = row

    if duplicate_ids:
        return rows
    root = components_by_id.get("root")
    if root is None:
        return rows
    if root.component_type not in _CONTAINER_TYPES:
        return rows

    ordered_components: list[ComponentRow] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    is_complete = _append_component_preorder(
        "root",
        components_by_id,
        ordered_components,
        visiting,
        visited,
    )
    if not is_complete:
        return rows
    return [*ordered_components, *data_rows]


def _append_component_preorder(
    component_id: str,
    components_by_id: dict[str, ComponentRow],
    ordered_components: list[ComponentRow],
    visiting: set[str],
    visited: set[str],
) -> bool:
    if component_id in visiting:
        return False
    if component_id in visited:
        return False
    component = components_by_id.get(component_id)
    if component is None:
        return False

    visiting.add(component_id)
    ordered_components.append(component)
    for child_id in component.children:
        child_added = _append_component_preorder(
            child_id,
            components_by_id,
            ordered_components,
            visiting,
            visited,
        )
        if not child_added:
            return False
    visiting.remove(component_id)
    visited.add(component_id)
    return True


def _parse_json_line(line: str, line_number: int) -> list[Any]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} is invalid JSON: {exc.msg}."
        ) from exc
    if not isinstance(value, list):
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} must be a JSON array."
        )
    return value


def _parse_row(value: list[Any], line_number: int) -> CompactRow:
    if _looks_like_data_row(value):
        path = value[0]
        _decode_json_pointer(path)
        _validate_source_value(value[1], f"data row {path}")
        return DataRow(path=path, value=copy.deepcopy(value[1]))
    if _looks_like_data_def_row(value):
        props = value[2]
        path = props.get("path", "/")
        _decode_json_pointer(path)
        _validate_source_value(props["value"], f"data row {path}")
        return DataRow(path=path, value=copy.deepcopy(props["value"]))
    return _parse_component_row(value, line_number)


def _looks_like_data_row(value: list[Any]) -> bool:
    if len(value) != 2:
        return False
    return isinstance(value[0], str) and value[0].startswith("/")


def _looks_like_data_def_row(value: list[Any]) -> bool:
    if len(value) != 3:
        return False
    if value[1] != "DataDef" or not isinstance(value[2], dict):
        return False
    path = value[2].get("path", "/")
    return isinstance(path, str) and "value" in value[2]


def _parse_component_row(value: list[Any], line_number: int) -> ComponentRow:
    value = _repair_legacy_component_row(value)
    if len(value) not in {3, 4}:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} has an unsupported row shape."
        )
    component_id, component_type, props = value[:3]
    component_type, props = _repair_legacy_component_props(
        component_id,
        component_type,
        props,
    )
    _validate_component_header(
        component_id,
        component_type,
        props,
        line_number,
    )
    children = _parse_children(value, component_id, component_type)
    if not _is_empty_image_component(component_type, props):
        _validate_component_props(component_id, component_type, props)
    return ComponentRow(
        component_id=component_id,
        component_type=component_type,
        props=copy.deepcopy(props),
        children=children,
    )


def _repair_legacy_component_row(value: list[Any]) -> list[Any]:
    if len(value) not in {3, 4}:
        return value
    props = value[2]
    if not isinstance(props, dict) or "children" not in props:
        return value

    repaired_props = copy.deepcopy(props)
    props_children = repaired_props.pop("children")
    repaired_value = [value[0], value[1], repaired_props]
    if len(value) == 4:
        repaired_value.append(value[3])
        return repaired_value
    if isinstance(props_children, list):
        repaired_value.append(props_children)
        return repaired_value

    repaired_props["children"] = props_children
    return repaired_value


def _repair_legacy_component_props(
    component_id: Any,
    component_type: Any,
    props: Any,
) -> tuple[Any, Any]:
    if not isinstance(props, dict):
        return component_type, props

    repaired_props = _repair_legacy_bindings(copy.deepcopy(props))
    repaired_type = component_type
    if isinstance(component_id, str) and component_id == "root":
        repaired_props.pop("size", None)
    if "flexGrow" in repaired_props:
        if "layoutWeight" not in repaired_props:
            repaired_props["layoutWeight"] = repaired_props["flexGrow"]
        repaired_props.pop("flexGrow", None)
    _repair_dimension_aliases(repaired_props)
    _repair_axis_value_aliases(repaired_type, repaired_props)

    _repair_spacing_aliases(repaired_type, repaired_props)
    if repaired_type == "Text":
        _repair_text_value_alias(repaired_props)
    if repaired_type == "Progress":
        _repair_progress_alias_props(repaired_props)
    if repaired_type == "Ring":
        repaired_type = "Progress"
        _repair_progress_alias_props(repaired_props, default_design="ring")
    if repaired_type == "ActionUnit":
        _repair_action_unit_props(repaired_props)
    _repair_on_click_aliases(repaired_props)
    return repaired_type, repaired_props


def _repair_action_unit_props(props: dict[str, Any]) -> None:
    icon = props.get("icon")
    if props.get("state") == "capsule" and isinstance(icon, str) and not icon.strip():
        props.pop("icon", None)


def _repair_on_click_aliases(props: dict[str, Any]) -> None:
    if "onClick" not in props:
        return
    normalized = _normalize_on_click_alias(props["onClick"])
    if normalized is not None:
        props["onClick"] = normalized


def _normalize_on_click_alias(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, dict):
        return [copy.deepcopy(value)]
    if _is_on_click_pair(value):
        return [_on_click_pair_to_handler(value)]
    if isinstance(value, list):
        return _normalize_on_click_list(value)
    return None


def _is_on_click_pair(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    if len(value) != 2:
        return False
    return isinstance(value[0], str) and isinstance(value[1], dict)


def _on_click_pair_to_handler(value: list[Any]) -> dict[str, Any]:
    args = copy.deepcopy(value[1])
    if set(args) == {"args"} and isinstance(args.get("args"), dict):
        args = copy.deepcopy(args["args"])
    return {"call": value[0], "args": args}


def _normalize_on_click_list(value: list[Any]) -> list[dict[str, Any]] | None:
    if _is_on_click_pair(value):
        return [_on_click_pair_to_handler(value)]
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        normalized.append(copy.deepcopy(item))
    return normalized


def _repair_text_value_alias(props: dict[str, Any]) -> None:
    if "content" in props:
        return
    if "value" in props:
        props["content"] = props.pop("value")
    elif "text" in props:
        props["content"] = props.pop("text")


def _repair_progress_alias_props(
    props: dict[str, Any],
    *,
    default_design: str | None = None,
) -> None:
    if default_design is not None and "design" not in props and "type" not in props:
        props["design"] = default_design
    size = props.pop("size", None)
    if size is not None:
        if "width" not in props:
            props["width"] = size
        if "height" not in props:
            props["height"] = size
    _repair_progress_color_alias(props)


def _repair_progress_color_alias(props: dict[str, Any]) -> None:
    colors = props.pop("colors", None)
    if colors is None or "color" in props:
        return
    color = _first_progress_color(colors)
    if color is not None:
        props["color"] = color


def _first_progress_color(colors: Any) -> str | None:
    if not isinstance(colors, list) or not colors:
        return None
    first_color = colors[0]
    if isinstance(first_color, dict) and isinstance(first_color.get("color"), str):
        return first_color["color"]
    if isinstance(first_color, list) and first_color:
        color = first_color[0]
        if isinstance(color, str):
            return color
    return None


def _repair_dimension_aliases(props: dict[str, Any]) -> None:
    for dimension_name in ("width", "height"):
        if props.get(dimension_name) in {"100%", "stretch"}:
            props[dimension_name] = "matchParent"


def _repair_spacing_aliases(
    component_type: Any,
    props: dict[str, Any],
) -> None:
    if component_type in {"Row", "Column"} and "space" in props:
        if "itemMargin" not in props:
            props["itemMargin"] = props["space"]
        props.pop("space", None)
    elif component_type == "List" and "itemMargin" in props:
        if "space" not in props:
            props["space"] = props["itemMargin"]
        props.pop("itemMargin", None)


def _repair_axis_value_aliases(
    component_type: Any,
    props: dict[str, Any],
) -> None:
    justify_content = props.get("justifyContent")
    if justify_content == "space-between":
        props["justifyContent"] = "spaceBetween"
    elif justify_content == "space-around":
        props["justifyContent"] = "spaceAround"
    elif justify_content == "space-evenly":
        props["justifyContent"] = "spaceEvenly"
    elif justify_content == "flex-start":
        props["justifyContent"] = "start"
    elif justify_content == "flex-end":
        props["justifyContent"] = "end"

    align_items = props.get("alignItems")
    if component_type == "Row":
        if align_items in {"flex-start", "start"}:
            props["alignItems"] = "top"
        elif align_items in {"flex-end", "end"}:
            props["alignItems"] = "bottom"
        elif align_items == "baseline":
            props["alignItems"] = "bottom"
    elif component_type == "Column":
        if align_items in {"flex-start", "top"}:
            props["alignItems"] = "start"
        elif align_items in {"flex-end", "bottom"}:
            props["alignItems"] = "end"


def _repair_legacy_bindings(value: Any) -> Any:
    if isinstance(value, dict):
        legacy_path = _legacy_binding_path(value)
        if legacy_path is not None:
            return {"path": legacy_path}
        repaired: dict[str, Any] = {}
        for key, child_value in value.items():
            repaired[key] = _repair_legacy_bindings(child_value)
        return repaired
    if isinstance(value, list):
        repaired_items: list[Any] = []
        for item in value:
            repaired_items.append(_repair_legacy_bindings(item))
        return repaired_items
    if isinstance(value, str):
        match = _LEGACY_PATH_TEMPLATE_PATTERN.fullmatch(value)
        if match is not None:
            return {"path": match.group("path")}
    return value


def _legacy_binding_path(value: dict[str, Any]) -> str | None:
    if len(value) != 1:
        return None
    key, path = next(iter(value.items()))
    if not isinstance(key, str) or not isinstance(path, str):
        return None
    normalized_key = key.replace("\\", "").replace("(", "").replace(")", "")
    if "data" in normalized_key.lower() and path.startswith("/"):
        return path
    return None


def _validate_component_header(
    component_id: Any,
    component_type: Any,
    props: Any,
    line_number: int,
) -> None:
    if not isinstance(component_id, str) or not component_id:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} has an invalid component id."
        )
    if (
        not isinstance(component_type, str)
        or component_type not in _COMPONENT_TYPES
    ):
        raise CompactDslConversionError(
            f'{component_id}: unsupported component type "{component_type}".'
        )
    if not isinstance(props, dict):
        raise CompactDslConversionError(
            f"{component_id}: component props must be an object."
        )


def _parse_children(
    value: list[Any],
    component_id: str,
    component_type: str,
) -> tuple[str, ...]:
    is_container = component_type in _CONTAINER_TYPES
    if len(value) != 4:
        if is_container:
            raise CompactDslConversionError(
                f"{component_id}: {component_type} requires a children array."
            )
        return ()
    if not isinstance(value[3], list):
        raise CompactDslConversionError(
            f"{component_id}: children must be an array."
        )

    children: list[str] = []
    for child in value[3]:
        if not isinstance(child, str) or not child:
            raise CompactDslConversionError(
                f"{component_id}: every child id must be a non-empty string."
            )
        children.append(child)
    if len(children) != len(set(children)):
        raise CompactDslConversionError(
            f"{component_id}: children contain duplicate component ids."
        )
    if is_container or component_type == "Button":
        return tuple(children)
    if children:
        raise CompactDslConversionError(
            f"{component_id}: non-container components cannot have children."
        )
    return ()


def _validate_button_image_children(rows: list[CompactRow]) -> None:
    components_by_id = {
        row.component_id: row
        for row in rows
        if isinstance(row, ComponentRow)
    }
    button_icon_ids: set[str] = set()

    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        if row.component_type != "Button" or not row.children:
            continue
        if len(row.children) != 1:
            raise CompactDslConversionError(
                f"{row.component_id}: Button supports at most one Image child."
            )
        icon_id = row.children[0]
        icon = components_by_id.get(icon_id)
        if icon is None or icon.component_type != "Image":
            raise CompactDslConversionError(
                f"{row.component_id}: Button child must be an Image."
            )
        button_icon_ids.add(icon_id)

    if button_icon_ids:
        _validate_button_icon_ownership(rows, button_icon_ids)


def _drop_empty_image_components(rows: list[CompactRow]) -> list[CompactRow]:
    empty_image_ids = {
        row.component_id
        for row in rows
        if isinstance(row, ComponentRow)
        and _is_empty_image_component(row.component_type, row.props)
    }
    if not empty_image_ids:
        return rows

    visible_rows: list[CompactRow] = []
    for row in rows:
        if not isinstance(row, ComponentRow):
            visible_rows.append(row)
            continue
        if row.component_id in empty_image_ids:
            continue
        visible_rows.append(_without_children(row, empty_image_ids))
    return visible_rows


def _without_children(
    row: ComponentRow,
    removed_ids: set[str],
) -> ComponentRow:
    if not row.children:
        return row
    children = tuple(child_id for child_id in row.children if child_id not in removed_ids)
    if children == row.children:
        return row
    return ComponentRow(
        row.component_id,
        row.component_type,
        copy.deepcopy(row.props),
        children,
    )


def _is_empty_image_component(
    component_type: Any,
    props: Any,
) -> bool:
    if component_type != "Image" or not isinstance(props, dict):
        return False
    return props.get("src") == ""


def _validate_button_icon_ownership(
    rows: list[CompactRow],
    button_icon_ids: set[str],
) -> None:
    parent_counts = dict.fromkeys(button_icon_ids, 0)
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        for child_id in row.children:
            if child_id in parent_counts:
                parent_counts[child_id] += 1
    shared_icons = [
        icon_id
        for icon_id, parent_count in parent_counts.items()
        if parent_count != 1
    ]
    if shared_icons:
        icon_list = ", ".join(sorted(shared_icons))
        raise CompactDslConversionError(
            f"Button Image children must have one parent: {icon_list}."
        )


def _validate_component_props(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    for property_name in _FORBIDDEN_PROPERTIES:
        if property_name in props:
            raise CompactDslConversionError(
                f"{component_id}: legacy property {property_name} is forbidden."
            )
    if "functionCall" in props:
        raise CompactDslConversionError(
            f"{component_id}: legacy functionCall is forbidden."
        )
    if component_type in {"Row", "Column"} and "space" in props:
        raise CompactDslConversionError(
            f"{component_id}: {component_type} must use itemMargin, not space."
        )
    if component_type != "List" and "space" in props:
        raise CompactDslConversionError(
            f"{component_id}: only List supports space."
        )
    if component_type == "List" and "itemMargin" in props:
        raise CompactDslConversionError(
            f"{component_id}: List must use space, not itemMargin."
        )
    if "itemMargin" in props and component_type not in {"Row", "Column"}:
        raise CompactDslConversionError(
            f"{component_id}: only Row and Column support itemMargin."
        )
    for property_name, value in props.items():
        _resolve_tokens(property_name, value, component_id)
    _validate_allowed_component_properties(
        component_id,
        component_type,
        props,
    )
    _validate_component_property_types(component_id, props)

    required_field = _REQUIRED_FIELDS.get(component_type)
    if required_field is not None and required_field not in props:
        raise CompactDslConversionError(
            f"{component_id}: {component_type}.{required_field} is required."
        )
    if component_type == "Button":
        _validate_button_props(component_id, props)
    if component_type == "ActionUnit":
        _validate_action_unit_props(component_id, props)
    _validate_semantic_props(component_id, component_type, props)
    if "onClick" in props:
        _validate_on_click(component_id, props["onClick"])
    source_props = props
    if component_type == "RingUnit":
        source_props = {
            name: value
            for name, value in props.items()
            if name != "reading"
        }
    _validate_source_value(source_props, component_id)


def _validate_allowed_component_properties(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    allowed = set(_COMMON_STYLE_PROPERTIES)
    allowed.update(_COMMON_COMPACT_PROPERTIES)
    if component_type == "ActionUnit":
        allowed.update(_ACTION_UNIT_PROPERTIES)
    if component_type == "RingUnit":
        allowed.update(_RING_UNIT_PROPERTIES)
    if component_type == "TimelineUnit":
        allowed.update(_TIMELINE_UNIT_PROPERTIES)
    allowed.update(_SEMANTIC_FIELDS.get(component_type, frozenset()))
    allowed.update(_COMPACT_ONLY_FIELDS.get(component_type, frozenset()))
    allowed.update(_COMPONENT_STYLE_PROPERTIES.get(component_type, frozenset()))
    unknown = sorted(set(props) - allowed)
    if not unknown:
        return
    names = ", ".join(unknown)
    raise CompactDslConversionError(
        f"{component_id}: unsupported properties for {component_type}: {names}."
    )


def _validate_component_property_types(
    component_id: str,
    props: dict[str, Any],
) -> None:
    for property_name, value in props.items():
        if property_name in _NUMBER_PROPERTIES:
            _validate_number_property(component_id, property_name, value)
            continue
        if property_name in _BOOLEAN_PROPERTIES:
            if not isinstance(value, bool):
                raise CompactDslConversionError(
                    f"{component_id}: {property_name} must be boolean."
                )
            continue
        if property_name in _STRING_PROPERTIES:
            if not isinstance(value, str) or not value:
                raise CompactDslConversionError(
                    f"{component_id}: {property_name} must be a non-empty string."
                )
            continue
        if property_name in {"itemMargin", "space"}:
            _validate_number_property(component_id, property_name, value)
            continue
        if property_name in {"margin", "padding"}:
            _validate_spacing_property(component_id, property_name, value)
            continue
        if property_name in {"width", "height"}:
            _validate_dimension_property(component_id, property_name, value)


def _validate_number_property(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be numeric."
    )


def _validate_spacing_property(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    if not isinstance(value, dict):
        raise CompactDslConversionError(
            f"{component_id}: {property_name} must be numeric or an edge object."
        )
    allowed_edges = {"top", "right", "bottom", "left"}
    if set(value) - allowed_edges:
        raise CompactDslConversionError(
            f"{component_id}: {property_name} contains unsupported edges."
        )
    for edge_value in value.values():
        if not isinstance(edge_value, (int, float)) or isinstance(edge_value, bool):
            raise CompactDslConversionError(
                f"{component_id}: {property_name} edge values must be numeric."
            )


def _validate_dimension_property(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    if isinstance(value, str) and value:
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be numeric or a dimension string."
    )


def _validate_button_label(component_id: str, label: Any) -> None:
    if not isinstance(label, str) or not label.strip():
        raise CompactDslConversionError(
            f"{component_id}: Button.label must be a non-empty string."
        )


def _validate_button_props(component_id: str, props: dict[str, Any]) -> None:
    if props.get("design") == "icon-round":
        return
    _validate_button_label(component_id, props.get("label"))


def _validate_action_unit_props(component_id: str, props: dict[str, Any]) -> None:
    _validate_action_unit_skin_props(component_id, props)
    _validate_action_surface(component_id, props)
    state = props.get("state")
    if state not in {"capsule", "icon-round"}:
        raise CompactDslConversionError(
            f'{component_id}: ActionUnit.state must be "capsule" or "icon-round".'
        )
    if "onClick" not in props:
        raise CompactDslConversionError(
            f"{component_id}: ActionUnit requires an onClick event."
        )
    if state == "capsule":
        _validate_button_label(component_id, props.get("label"))
        _validate_optional_action_unit_icon(component_id, props)
        return
    if "label" in props:
        raise CompactDslConversionError(
            f"{component_id}: icon-round ActionUnit must not contain label."
        )
    _validate_required_action_unit_icon(component_id, props)


def _validate_action_surface(component_id: str, props: dict[str, Any]) -> None:
    action_surface = props.get("actionSurface")
    if action_surface is None:
        return
    if action_surface != "white":
        raise CompactDslConversionError(
            f'{component_id}: ActionUnit.actionSurface must be "white".'
        )


def _validate_action_unit_skin_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    unsupported = sorted(set(props).intersection(_ACTION_UNIT_FORBIDDEN_SKIN_PROPERTIES))
    if not unsupported:
        return
    names = ", ".join(unsupported)
    raise CompactDslConversionError(
        f"{component_id}: ActionUnit must not define skin properties: {names}."
    )


def _validate_optional_action_unit_icon(
    component_id: str,
    props: dict[str, Any],
) -> None:
    icon = props.get("icon")
    if icon is None:
        return
    if isinstance(icon, str) and not icon.strip():
        return
    _validate_image_source(component_id, icon)


def _validate_required_action_unit_icon(
    component_id: str,
    props: dict[str, Any],
) -> None:
    icon = props.get("icon")
    if icon is None:
        raise CompactDslConversionError(
            f"{component_id}: icon-round ActionUnit requires icon."
        )
    _validate_image_source(component_id, icon)


def _validate_semantic_props(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    if component_type == "Text":
        _require_literal_or_binding(
            component_id,
            "Text.content",
            props.get("content"),
            str,
        )
        return
    if component_type == "Image":
        _validate_image_source(component_id, props.get("src"))
        return
    if component_type == "Progress":
        _validate_progress_props(component_id, props)
        return
    if component_type == "RingUnit":
        _validate_ring_unit_props(component_id, props)
        return
    if component_type == "TimelineUnit":
        return
    if component_type == "Button":
        _validate_optional_bool(component_id, "Button.enabled", props)
        return
    if component_type == "ActionUnit":
        _validate_optional_bool(component_id, "ActionUnit.enabled", props)
        return
    if component_type == "Checkbox":
        _validate_checkbox_props(component_id, props)


def _require_literal_or_binding(
    component_id: str,
    property_name: str,
    value: Any,
    literal_type: type,
) -> None:
    is_literal = isinstance(value, literal_type)
    if literal_type in {int, float} and isinstance(value, bool):
        is_literal = False
    if is_literal or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} has an invalid value."
    )


def _validate_image_source(component_id: str, source: Any) -> None:
    if not isinstance(source, str) or not source:
        raise CompactDslConversionError(
            f"{component_id}: Image.src must be a non-empty local path."
        )
    if not source.startswith("resources/base/media/"):
        raise CompactDslConversionError(
            f"{component_id}: Image.src must use resources/base/media/."
        )


def _validate_progress_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    _require_numeric_or_binding(
        component_id,
        "Progress.value",
        props.get("value"),
    )
    if "total" not in props:
        raise CompactDslConversionError(
            f"{component_id}: Progress.total is required."
        )
    _require_numeric_or_binding(
        component_id,
        "Progress.total",
        props["total"],
    )


def _validate_ring_unit_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    state = props.get("state")
    size = props.get("size")
    if state not in _RING_UNIT_STATES:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.state is invalid."
        )
    if size not in _RING_UNIT_SIZES:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.size must be 44 or 52."
        )
    if state in _RING_UNIT_CENTER_TEXT_STATES and size != 52:
        raise CompactDslConversionError(
            f"{component_id}: {state} requires size 52."
        )
    _validate_ring_unit_progress(component_id, props)
    _validate_ring_unit_state_contract(component_id, props)


def _validate_ring_unit_progress(
    component_id: str,
    props: dict[str, Any],
) -> None:
    if "value" not in props:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.value is required."
        )
    if "total" not in props:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.total is required."
        )
    _require_numeric_or_binding(component_id, "RingUnit.value", props["value"])
    _require_numeric_or_binding(component_id, "RingUnit.total", props["total"])
    total = props["total"]
    if isinstance(total, (int, float)) and not isinstance(total, bool) and total <= 0:
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.total must be positive."
        )


def _validate_ring_unit_state_contract(
    component_id: str,
    props: dict[str, Any],
) -> None:
    state = props["state"]
    reading = props.get("reading")
    center_icon = props.get("centerIcon")
    if center_icon is not None:
        _validate_image_source(component_id, center_icon)
    if state in _RING_UNIT_CENTER_ICON_STATES:
        if reading is not None:
            raise CompactDslConversionError(
                f"{component_id}: {state} must not include reading."
            )
        return
    if state in _RING_UNIT_CENTER_TEXT_STATES and center_icon is not None:
        raise CompactDslConversionError(
            f"{component_id}: {state} must not include centerIcon."
        )
    _validate_ring_reading(component_id, reading)


def _validate_ring_reading(component_id: str, reading: Any) -> None:
    if not isinstance(reading, dict):
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading must be an object."
        )
    unknown_keys = set(reading) - {"path", "unit"}
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading has unsupported fields: {names}."
        )
    path = reading.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading.path must be a JSON Pointer."
        )
    _decode_json_pointer(path)
    unit = reading.get("unit")
    if unit is not None and not isinstance(unit, str):
        raise CompactDslConversionError(
            f"{component_id}: RingUnit.reading.unit must be a string."
        )


def _require_numeric_or_binding(
    component_id: str,
    property_name: str,
    value: Any,
) -> None:
    is_number = isinstance(value, (int, float))
    if isinstance(value, bool):
        is_number = False
    if is_number or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be numeric or a path binding."
    )


def _validate_optional_bool(
    component_id: str,
    property_name: str,
    props: dict[str, Any],
) -> None:
    field_name = property_name.rsplit(".", 1)[-1]
    if field_name not in props:
        return
    value = props[field_name]
    if isinstance(value, bool) or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component_id}: {property_name} must be boolean or a path binding."
    )


def _validate_checkbox_props(
    component_id: str,
    props: dict[str, Any],
) -> None:
    for property_name in ("label", "value"):
        if property_name not in props:
            continue
        _require_literal_or_binding(
            component_id,
            f"Checkbox.{property_name}",
            props[property_name],
            str,
        )
    _validate_optional_bool(component_id, "Checkbox.select", props)


def _is_path_binding(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"path"}:
        return False
    path = value.get("path")
    return isinstance(path, str) and path.startswith("/")


def _validate_on_click(component_id: str, on_click: Any) -> None:
    if not isinstance(on_click, list) or not on_click:
        raise CompactDslConversionError(
            f"{component_id}: onClick must be a non-empty array."
        )
    for handler in on_click:
        _validate_event_handler(component_id, handler)


def _validate_event_handler(component_id: str, handler: Any) -> None:
    if not isinstance(handler, dict):
        raise CompactDslConversionError(
            f"{component_id}: each onClick handler must be an object."
        )
    allowed_keys = {"call", "args"}
    unknown_keys = set(handler) - allowed_keys
    if unknown_keys:
        names = ", ".join(sorted(unknown_keys))
        raise CompactDslConversionError(
            f"{component_id}: onClick has unsupported fields: {names}."
        )
    call = handler.get("call")
    if not isinstance(call, str) or not call:
        raise CompactDslConversionError(
            f"{component_id}: onClick.call must be a non-empty string."
        )
    args = handler.get("args")
    if args is not None and not isinstance(args, dict):
        raise CompactDslConversionError(
            f"{component_id}: onClick.args must be an object."
        )


def _validate_source_value(value: Any, context: str) -> None:
    if isinstance(value, str):
        _validate_source_string(value, context)
        return
    if isinstance(value, list):
        for item in value:
            _validate_source_value(item, context)
        return
    if not isinstance(value, dict):
        return

    if "functionCall" in value:
        raise CompactDslConversionError(
            f"{context}: legacy functionCall is forbidden."
        )
    if "path" in value:
        _validate_path_binding(value, context)
        return
    for child_value in value.values():
        _validate_source_value(child_value, context)


def _validate_source_string(value: str, context: str) -> None:
    for fragment in _FORBIDDEN_STRING_FRAGMENTS:
        if fragment in value:
            raise CompactDslConversionError(
                f'{context}: forbidden binding expression "{fragment}".'
            )


def _validate_path_binding(value: dict[str, Any], context: str) -> None:
    if set(value) != {"path"}:
        raise CompactDslConversionError(
            f"{context}: a path binding must contain only the path field."
        )
    path = value.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise CompactDslConversionError(
            f"{context}: path binding must contain a JSON Pointer."
        )
    _decode_json_pointer(path)


def _validate_component_tree(
    rows: list[CompactRow],
) -> tuple[list[ComponentRow], list[DataRow]]:
    first_row = rows[0]
    if not isinstance(first_row, ComponentRow):
        raise CompactDslConversionError(
            "The root Column component is missing; model output may be truncated."
        )
    if first_row.component_id != "root" or first_row.component_type != "Column":
        first_component = (
            f"{first_row.component_id}/{first_row.component_type}"
        )
        raise CompactDslConversionError(
            "The root Column component is missing; model output may be "
            f"truncated. First parsed component: {first_component}."
        )

    components: list[ComponentRow] = []
    data_rows: list[DataRow] = []
    seen_ids: set[str] = set()
    announced_ids = {"root"}
    parent_by_child: dict[str, str] = {}

    for row in rows:
        if isinstance(row, DataRow):
            data_rows.append(row)
            continue
        _validate_component_position(row, seen_ids, announced_ids)
        seen_ids.add(row.component_id)
        components.append(row)
        _announce_children(row, announced_ids, parent_by_child)

    unresolved_ids = announced_ids - seen_ids
    if unresolved_ids:
        unresolved = ", ".join(sorted(unresolved_ids))
        raise CompactDslConversionError(
            f"Compact DSL references missing components: {unresolved}."
        )
    return components, data_rows


def _validate_component_position(
    component: ComponentRow,
    seen_ids: set[str],
    announced_ids: set[str],
) -> None:
    component_id = component.component_id
    if component_id in seen_ids:
        raise CompactDslConversionError(
            f'Duplicate Compact DSL component id "{component_id}".'
        )
    if component_id not in announced_ids:
        raise CompactDslConversionError(
            f'{component_id}: component must be declared by an earlier parent.'
        )


def _announce_children(
    component: ComponentRow,
    announced_ids: set[str],
    parent_by_child: dict[str, str],
) -> None:
    for child_id in component.children:
        if child_id == "root":
            raise CompactDslConversionError("root cannot be a child component.")
        existing_parent = parent_by_child.get(child_id)
        if existing_parent is not None:
            raise CompactDslConversionError(
                f"{child_id}: referenced by both {existing_parent} "
                f"and {component.component_id}."
            )
        parent_by_child[child_id] = component.component_id
        announced_ids.add(child_id)


def _normalize_component(component: ComponentRow) -> ComponentRow:
    props = _expand_component_design(component)
    resolved_props: dict[str, Any] = {}
    for property_name, value in props.items():
        resolved_props[property_name] = _resolve_tokens(
            property_name,
            value,
            component.component_id,
        )
    return ComponentRow(
        component_id=component.component_id,
        component_type=component.component_type,
        props=resolved_props,
        children=component.children,
    )


def _expand_component_design(component: ComponentRow) -> dict[str, Any]:
    try:
        return _design_token_expand_component_design(component)
    except DesignTokenConversionError as exc:
        raise CompactDslConversionError(str(exc)) from exc


def _resolve_tokens(
    property_name: str,
    value: Any,
    component_id: str,
) -> Any:
    try:
        return _design_token_resolve_tokens(property_name, value, component_id)
    except DesignTokenConversionError as exc:
        raise CompactDslConversionError(str(exc)) from exc


def _component_to_tuple(component: ComponentRow) -> list[Any]:
    row: list[Any] = [
        component.component_id,
        component.component_type,
        copy.deepcopy(component.props),
    ]
    if component.component_type in _CONTAINER_TYPES or component.children:
        row.append(list(component.children))
    return row


def _button_ids_with_design(
    components: list[ComponentRow],
    design: str,
) -> set[str]:
    button_ids: set[str] = set()
    for component in components:
        if component.component_type != "Button":
            continue
        if component.props.get("design") == design:
            button_ids.add(component.component_id)
    return button_ids


def _convert_component_rows(
    component: ComponentRow,
    *,
    hide_label: bool = False,
    fallback_root_gradient: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if component.component_type == "ActionUnit":
        return _convert_action_unit(component)
    return [
        _convert_component(
            component,
            hide_label=hide_label,
            fallback_root_gradient=fallback_root_gradient,
        )
    ]


def _convert_action_unit(component: ComponentRow) -> list[dict[str, Any]]:
    try:
        return _design_token_convert_action_unit(
            component,
            convert_path_bindings=_convert_path_bindings,
        )
    except DesignTokenConversionError as exc:
        raise CompactDslConversionError(str(exc)) from exc


def _convert_component(
    component: ComponentRow,
    *,
    hide_label: bool = False,
    fallback_root_gradient: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_type = _output_component_type(component, hide_label)
    converted: dict[str, Any] = {
        "id": component.component_id,
        "component": output_type,
    }
    if output_type in _CONTAINER_TYPES:
        converted["children"] = list(component.children)
    if hide_label and output_type == "Button":
        converted["label"] = _A2UI_ICON_BUTTON_LABEL

    styles: dict[str, Any] = {}
    semantic_fields = _SEMANTIC_FIELDS.get(
        component.component_type,
        frozenset(),
    )
    compact_only_fields = _COMPACT_ONLY_FIELDS.get(
        component.component_type,
        frozenset(),
    )
    for property_name, source_value in component.props.items():
        if property_name == "label" and hide_label:
            continue
        if property_name in compact_only_fields:
            continue
        value = _convert_path_bindings(source_value)
        if _move_component_property(
            converted,
            component,
            property_name,
            value,
            semantic_fields,
        ):
            continue
        styles[property_name] = value

    if component.component_id == "root":
        _normalize_root_component(
            component,
            converted,
            styles,
            fallback_root_gradient,
        )
    if _is_icon_button_stack(component, hide_label):
        _normalize_icon_button_stack(styles)
    if component.component_type == "Text":
        _normalize_text_component(converted, styles)
    if component.component_type == "Progress":
        _normalize_progress_component(styles)
    if (
        component.component_type == "Image"
        and _should_preserve_original_icon_color(converted.get("src"))
    ):
        styles.pop("fillColor", None)
    if styles:
        converted["styles"] = styles
    return converted


def _output_component_type(component: ComponentRow, hide_label: bool) -> str:
    if _is_icon_button_stack(component, hide_label):
        return "Stack"
    return component.component_type


def _is_icon_button_stack(component: ComponentRow, hide_label: bool) -> bool:
    if not hide_label or component.component_type != "Button":
        return False
    return bool(component.children)


def _normalize_text_component(
    converted: dict[str, Any],
    styles: dict[str, Any],
) -> None:
    content = converted.get("content")
    if isinstance(content, str):
        converted["content"] = _normalize_text_join_separator(content)


def _normalize_text_join_separator(content: str) -> str:
    if not any(separator in content for separator in ("·", "｜", "|")):
        return content
    return _TEXT_JOIN_SEPARATOR_PATTERN.sub(" | ", content).strip()


def _normalize_progress_component(styles: dict[str, Any]) -> None:
    if styles.get("type") == "ring":
        styles["strokeWidth"] = 6
        return
    if styles.get("type") == "linear":
        styles["height"] = 8
        styles["borderRadius"] = 4


def _normalize_root_component(
    component: ComponentRow,
    converted: dict[str, Any],
    styles: dict[str, Any],
    fallback_gradient: dict[str, Any] | None,
) -> None:
    styles["width"] = "matchParent"
    styles["height"] = "matchParent"
    if _is_2x2_root(component.props):
        styles["padding"] = 12
        styles["borderRadius"] = 20
        styles["clip"] = True
        styles["justifyContent"] = "start"
        converted["itemMargin"] = min(
            _numeric_prop(component.props.get("itemMargin"), default=8),
            8,
        )
    _normalize_root_linear_gradient(styles)
    _ensure_root_background(styles, fallback_gradient)


def _normalize_root_linear_gradient(styles: dict[str, Any]) -> None:
    del styles


def _is_2x2_root(props: dict[str, Any]) -> bool:
    return props.get("width") == 160 and props.get("height") == 160


def _ensure_root_background(
    styles: dict[str, Any],
    fallback_gradient: dict[str, Any] | None,
) -> None:
    has_background = any(
        name in styles
        for name in ("linearGradient", "backgroundColor", "backgroundImage")
    )
    if has_background:
        return
    gradient = fallback_gradient or _ROOT_LINEAR_GRADIENT_PALETTES[0]
    styles["linearGradient"] = copy.deepcopy(gradient)


def _fallback_root_linear_gradient(seed: str) -> dict[str, Any]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    palette_index = int.from_bytes(digest[:2], "big")
    palette_index %= len(_ROOT_LINEAR_GRADIENT_PALETTES)
    return copy.deepcopy(_ROOT_LINEAR_GRADIENT_PALETTES[palette_index])


def _move_component_property(
    converted: dict[str, Any],
    component: ComponentRow,
    property_name: str,
    value: Any,
    semantic_fields: frozenset[str],
) -> bool:
    if property_name in semantic_fields:
        converted[property_name] = value
        return True
    if property_name == "onClick":
        converted["onClick"] = value
        return True
    if (
        property_name == "itemMargin"
        and component.component_type in {"Row", "Column"}
    ):
        converted["itemMargin"] = value
        return True
    if property_name == "space" and component.component_type == "List":
        converted["space"] = value
        return True
    return False


def _convert_path_bindings(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"path"}:
            return f"{{{{ ${{{value['path']}}} }}}}"
        converted: dict[str, Any] = {}
        for key, child_value in value.items():
            converted[key] = _convert_path_bindings(child_value)
        return converted
    if isinstance(value, list):
        converted_items: list[Any] = []
        for item in value:
            converted_items.append(_convert_path_bindings(item))
        return converted_items
    return copy.deepcopy(value)


def _validate_compact_root_dimensions(
    root: ComponentRow,
    size: str,
) -> None:
    expected = _COMPACT_ROOT_DIMENSIONS.get(size)
    if expected is None:
        raise CompactDslConversionError(f'Unsupported Form size "{size}".')
    width = root.props.get("width")
    height = root.props.get("height")
    if width == expected["width"] and height == expected["height"]:
        return
    raise CompactDslConversionError(
        f"root dimensions must be {expected['width']}x{expected['height']} "
        f'for size "{size}".'
    )


def _surface_dimensions(
    size: str,
    protocol_profile: dict[str, Any],
) -> dict[str, int]:
    if size not in _A2UI_FALLBACK_DIMENSIONS:
        raise CompactDslConversionError(f'Unsupported Form size "{size}".')
    if size in _COMPACT_ROOT_DIMENSIONS:
        return copy.deepcopy(_COMPACT_ROOT_DIMENSIONS[size])
    sizes = protocol_profile.get("sizes")
    dimensions = _profile_dimensions(size, sizes)
    if dimensions is not None:
        return dimensions
    return copy.deepcopy(_A2UI_FALLBACK_DIMENSIONS[size])


def _profile_dimensions(
    size: str,
    sizes: Any,
) -> dict[str, int] | None:
    if not isinstance(sizes, dict):
        return None
    dimensions = sizes.get(size)
    if dimensions is None and size == "4x2":
        dimensions = sizes.get("2x4")
    if not isinstance(dimensions, dict):
        return None
    width = dimensions.get("width")
    height = dimensions.get("height")
    if not _is_positive_integer(width) or not _is_positive_integer(height):
        return None
    return {"width": width, "height": height}


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _build_data_model(data_rows: list[DataRow]) -> dict[str, Any]:
    if not data_rows:
        return {"data": {}}

    root: dict[str, Any] = {}
    data_values: dict[str, Any] = {}
    for row in data_rows:
        existing = data_values.get(row.path)
        if row.path in data_values and existing != row.value:
            raise CompactDslConversionError(
                f'{row.path}: duplicate data rows contain different values.'
            )
        data_values[row.path] = copy.deepcopy(row.value)
        _set_json_pointer(root, row.path, copy.deepcopy(row.value))
    return root


def _set_json_pointer(root: dict[str, Any], path: str, value: Any) -> None:
    tokens = _decode_json_pointer(path)
    if not tokens:
        _merge_root_data(root, value)
        return

    current: dict[str, Any] | list[Any] = root
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_token = None if is_last else tokens[index + 1]
        if isinstance(current, dict):
            current = _set_dict_pointer_part(
                current,
                token,
                next_token,
                value,
                is_last,
                path,
            )
            if is_last:
                return
            continue
        current = _set_list_pointer_part(
            current,
            token,
            next_token,
            value,
            is_last,
            path,
        )
        if is_last:
            return


def _merge_root_data(root: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        raise CompactDslConversionError(
            "Compact DSL root DataModel row must contain an object."
        )
    merged = _merge_compatible_values(root, value, "/")
    root.clear()
    root.update(merged)


def _set_dict_pointer_part(
    current: dict[str, Any],
    token: str,
    next_token: str | None,
    value: Any,
    is_last: bool,
    path: str,
) -> dict[str, Any] | list[Any]:
    if is_last:
        existing = current.get(token)
        current[token] = _merge_compatible_values(existing, value, path)
        return current

    expected_type = list if _is_array_index(next_token) else dict
    child = current.get(token)
    if child is None:
        child = expected_type()
        current[token] = child
    if not isinstance(child, expected_type):
        raise CompactDslConversionError(
            f'{path}: data path conflicts with an existing scalar value.'
        )
    return child


def _set_list_pointer_part(
    current: list[Any],
    token: str,
    next_token: str | None,
    value: Any,
    is_last: bool,
    path: str,
) -> dict[str, Any] | list[Any]:
    array_index = _parse_array_index(token, path)
    while len(current) <= array_index:
        current.append(None)
    if is_last:
        current[array_index] = _merge_compatible_values(
            current[array_index],
            value,
            path,
        )
        return current

    expected_type = list if _is_array_index(next_token) else dict
    child = current[array_index]
    if child is None:
        child = expected_type()
        current[array_index] = child
    if not isinstance(child, expected_type):
        raise CompactDslConversionError(
            f'{path}: data path conflicts with an existing scalar value.'
        )
    return child


def _merge_compatible_values(existing: Any, incoming: Any, path: str) -> Any:
    if existing is None:
        return copy.deepcopy(incoming)
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = copy.deepcopy(existing)
        for key, value in incoming.items():
            child_path = f"{path.rstrip('/')}/{key}"
            merged[key] = _merge_compatible_values(
                merged.get(key),
                value,
                child_path,
            )
        return merged
    if isinstance(existing, list) and isinstance(incoming, list):
        return _merge_lists(existing, incoming, path)
    if existing == incoming:
        return copy.deepcopy(existing)
    raise CompactDslConversionError(
        f'{path}: data rows contain incompatible values.'
    )


def _merge_lists(existing: list[Any], incoming: list[Any], path: str) -> list[Any]:
    merged = copy.deepcopy(existing)
    for index, value in enumerate(incoming):
        while len(merged) <= index:
            merged.append(None)
        child_path = f"{path.rstrip('/')}/{index}"
        merged[index] = _merge_compatible_values(
            merged[index],
            value,
            child_path,
        )
    return merged


def _validate_binding_paths(
    components: list[ComponentRow],
    data_model: dict[str, Any],
) -> None:
    for component in components:
        paths: list[str] = []
        _collect_binding_paths(component.props, paths)
        for path in paths:
            if not _json_pointer_exists(data_model, path):
                raise CompactDslConversionError(
                    f"{component.component_id}: binding path {path} "
                    "has no matching data value."
                )


def _component_binding_paths(
    components: list[ComponentRow],
) -> list[str]:
    paths: list[str] = []
    for component in components:
        _collect_binding_paths(component.props, paths)
    return list(dict.fromkeys(paths))


def _validate_binding_schema_types(
    binding_paths: list[str],
    data_model: dict[str, Any],
    data_model_schema: dict[str, Any],
) -> None:
    for path in binding_paths:
        schema_node = _schema_node_at_path(data_model_schema, path)
        if schema_node is None:
            raise CompactDslConversionError(
                f"{path}: binding path is not declared by TaskSpec.dataModelSchema."
            )
        found, value = _json_pointer_value(data_model, path)
        if not found:
            continue
        expected_type = _schema_type(schema_node)
        if expected_type is None or _value_matches_schema_type(
            value,
            expected_type,
        ):
            continue
        actual_type = _json_type_name(value)
        raise CompactDslConversionError(
            f"{path}: DataModel type {actual_type} does not match "
            f"schema type {expected_type}."
        )


def _schema_node_at_path(
    schema: Any,
    path: str,
) -> Any | None:
    current = schema
    for token in _decode_json_pointer(path):
        current = _schema_child(current, token)
        if current is None:
            return None
    return current


def _schema_child(current: Any, token: str) -> Any | None:
    if isinstance(current, list):
        if not token.isdigit() or not current:
            return None
        return current[0]
    if not isinstance(current, dict):
        return None
    if current.get("type") == "array":
        if not token.isdigit():
            return None
        return current.get("items")
    if current.get("type") == "object":
        properties = current.get("properties")
        if isinstance(properties, dict):
            return properties.get(token)
    return current.get(token)


def _schema_type(schema_node: Any) -> str | None:
    if isinstance(schema_node, list):
        return "array"
    if not isinstance(schema_node, dict):
        return None
    schema_type = schema_node.get("type")
    return schema_type if isinstance(schema_type, str) else None


def _value_matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return True


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _validate_data_capability_roots(
    binding_paths: list[str],
    card_spec: dict[str, Any],
) -> None:
    roots = _card_spec_data_roots(card_spec)
    for path in binding_paths:
        if path != "/data" and not path.startswith("/data/"):
            continue
        if any(_path_is_within(path, root) for root in roots):
            continue
        raise CompactDslConversionError(
            f"{path}: binding is not backed by CardSpec.dataBindings."
        )


def _unused_data_capability_warnings(
    binding_paths: list[str],
    card_spec: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for root in _card_spec_data_roots(card_spec):
        if any(_path_is_within(path, root) for path in binding_paths):
            continue
        warnings.append(
            f"{root}: declared data capability is not used by any component."
        )
    return warnings


def _card_spec_data_roots(card_spec: dict[str, Any]) -> list[str]:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        return []
    roots: list[str] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        root = binding.get("writeResultTo")
        if isinstance(root, str) and root.startswith("/"):
            roots.append(root)
    return roots


def _path_is_within(path: str, root: str) -> bool:
    normalized_root = root.rstrip("/")
    return path == normalized_root or path.startswith(f"{normalized_root}/")


def _validate_asset_candidates(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
) -> None:
    allowed_sources = _candidate_asset_sources(task_spec)
    for component in components:
        source = _candidate_component_asset_source(component)
        if source is None or source in allowed_sources:
            continue
        raise CompactDslConversionError(
            f'{component.component_id}: asset "{source}" is not present '
            "in TaskSpec.assetCandidates."
        )


def _candidate_component_asset_source(component: ComponentRow) -> str | None:
    if component.component_type == "Image":
        source = component.props.get("src")
    elif component.component_type == "ActionUnit":
        source = component.props.get("icon")
    else:
        return None
    return source if isinstance(source, str) and source else None


def _candidate_asset_sources(task_spec: dict[str, Any]) -> set[str]:
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return set()
    sources: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("src")
        if isinstance(source, str) and source:
            sources.add(source)
    return sources


def _validate_event_candidates(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
) -> None:
    allowed_handlers = _candidate_event_handlers(task_spec)
    allowed_keys = {_stable_json(handler) for handler in allowed_handlers}
    for component in components:
        handlers = component.props.get("onClick")
        if component.component_type in {"Button", "ActionUnit"} and handlers is None:
            raise CompactDslConversionError(
                f"{component.component_id}: component requires an onClick event."
            )
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if _stable_json(handler) in allowed_keys:
                continue
            if _matching_event_handler(handler, allowed_handlers) is not None:
                continue
            raise CompactDslConversionError(
                f"{component.component_id}: onClick is not present in "
                "TaskSpec.eventCandidates."
            )


def _candidate_event_handlers(
    task_spec: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return []
    handlers: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        handler = _candidate_event_handler(candidate)
        if handler is None:
            continue
        handlers.append(handler)
    return handlers


def _candidate_event_handler(candidate: dict[str, Any]) -> dict[str, Any] | None:
    call = candidate.get("call")
    args = candidate.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        action = candidate.get("action")
        if not isinstance(action, dict):
            return None
        call = action.get("call")
        args = action.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    return {
        "call": call,
        "args": _repair_legacy_bindings(copy.deepcopy(args)),
    }


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _event_handler_replacements(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    allowed_handlers = _candidate_event_handlers(task_spec)
    allowed_keys = {_stable_json(handler) for handler in allowed_handlers}
    replacements: dict[str, dict[str, Any]] = {}
    for component in components:
        handlers = component.props.get("onClick")
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if not isinstance(handler, dict):
                continue
            key = _stable_json(handler)
            if key in allowed_keys:
                continue
            matched = _matching_event_handler(handler, allowed_handlers)
            if matched is not None:
                replacements[key] = _merge_event_handler_bindings(
                    matched,
                    handler,
                )
    return replacements


def _matching_event_handler(
    handler: dict[str, Any],
    allowed_handlers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    call = handler.get("call")
    args = handler.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    same_call_handlers = [
        candidate
        for candidate in allowed_handlers
        if candidate.get("call") == call
    ]
    for candidate in same_call_handlers:
        candidate_args = candidate.get("args")
        if isinstance(candidate_args, dict) and _event_args_match(args, candidate_args):
            return candidate
    if len(same_call_handlers) == 1:
        return same_call_handlers[0]
    return None


def _event_args_match(
    model_args: dict[str, Any],
    candidate_args: dict[str, Any],
) -> bool:
    if _dict_subset(model_args, candidate_args):
        return True
    if _dict_subset(candidate_args, model_args):
        return True
    return False


def _dict_subset(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if _is_path_binding(left) or _is_path_binding(right):
        if not _is_path_binding(left) or not _is_path_binding(right):
            return False
        return _event_binding_paths_match(left["path"], right["path"])
    for key, value in left.items():
        if key not in right:
            return False
        right_value = right[key]
        if isinstance(value, dict) and isinstance(right_value, dict):
            if not _dict_subset(value, right_value):
                return False
            continue
        if value != right_value:
            return False
    return True


def _event_binding_paths_match(left: str, right: str) -> bool:
    left_parts = left.split("/")
    right_parts = right.split("/")
    if len(left_parts) != len(right_parts):
        return False
    for left_part, right_part in zip(left_parts, right_parts, strict=True):
        if left_part == right_part:
            continue
        if left_part == "i" and right_part.isdigit():
            continue
        if right_part == "i" and left_part.isdigit():
            continue
        return False
    return True


def _merge_event_handler_bindings(
    candidate: dict[str, Any],
    model_handler: dict[str, Any],
) -> dict[str, Any]:
    """Keep candidate static args while retaining concrete model data paths."""
    candidate_args = candidate.get("args")
    model_args = model_handler.get("args")
    if not isinstance(candidate_args, dict) or not isinstance(model_args, dict):
        return copy.deepcopy(candidate)
    return {
        "call": candidate["call"],
        "args": _merge_event_arg_bindings(candidate_args, model_args),
    }


def _merge_event_arg_bindings(candidate: Any, model_value: Any) -> Any:
    if _is_path_binding(candidate):
        if (
            _is_path_binding(model_value)
            and _event_binding_paths_match(
                candidate["path"],
                model_value["path"],
            )
        ):
            return copy.deepcopy(model_value)
        return copy.deepcopy(candidate)
    if isinstance(candidate, dict):
        model_mapping = model_value if isinstance(model_value, dict) else {}
        return {
            key: _merge_event_arg_bindings(value, model_mapping.get(key))
            for key, value in candidate.items()
        }
    if isinstance(candidate, list):
        model_items = model_value if isinstance(model_value, list) else []
        return [
            _merge_event_arg_bindings(
                value,
                model_items[index] if index < len(model_items) else None,
            )
            for index, value in enumerate(candidate)
        ]
    return copy.deepcopy(candidate)


def _replace_event_handlers(
    props: dict[str, Any],
    event_replacements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    handlers = props.get("onClick")
    if not event_replacements or not isinstance(handlers, list):
        return props

    repaired_handlers: list[Any] = []
    changed = False
    for handler in handlers:
        if isinstance(handler, dict):
            replacement = event_replacements.get(_stable_json(handler))
            if replacement is not None:
                repaired_handlers.append(copy.deepcopy(replacement))
                changed = True
                continue
        repaired_handlers.append(copy.deepcopy(handler))
    if not changed:
        return props

    repaired_props = copy.deepcopy(props)
    repaired_props["onClick"] = repaired_handlers
    return repaired_props


def _collect_binding_paths(value: Any, paths: list[str]) -> None:
    if isinstance(value, dict):
        if set(value) == {"path"}:
            paths.append(value["path"])
            return
        for child_value in value.values():
            _collect_binding_paths(child_value, paths)
        return
    if isinstance(value, list):
        for item in value:
            _collect_binding_paths(item, paths)


def _replace_binding_paths(
    value: Any,
    path_replacements: dict[str, str],
    literal_replacements: dict[str, Any],
) -> Any:
    if isinstance(value, dict):
        if set(value) == {"path"} and isinstance(value.get("path"), str):
            path = value["path"]
            if path in literal_replacements:
                return copy.deepcopy(literal_replacements[path])
            return {"path": path_replacements.get(path, path)}
        return {
            key: _replace_binding_paths(
                item,
                path_replacements,
                literal_replacements,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _replace_binding_paths(
                item,
                path_replacements,
                literal_replacements,
            )
            for item in value
        ]
    return copy.deepcopy(value)


def _json_pointer_value(
    root: dict[str, Any],
    path: str,
) -> tuple[bool, Any]:
    tokens = _decode_json_pointer(path)
    current: Any = root
    for token in tokens:
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            if not token.isdigit():
                return False, None
            index = int(token)
            if index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _json_pointer_exists(root: dict[str, Any], path: str) -> bool:
    found, _value = _json_pointer_value(root, path)
    return found


def _decode_json_pointer(path: str) -> list[str]:
    if path == "/":
        return []
    if not isinstance(path, str) or not path.startswith("/"):
        raise CompactDslConversionError(
            f'Compact DSL path "{path}" is not a JSON Pointer.'
        )
    tokens: list[str] = []
    for raw_token in path[1:].split("/"):
        _validate_pointer_escape(raw_token, path)
        tokens.append(raw_token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _validate_pointer_escape(token: str, path: str) -> None:
    index = 0
    while index < len(token):
        if token[index] != "~":
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise CompactDslConversionError(
                f'Compact DSL path "{path}" has an invalid JSON Pointer escape.'
            )
        index += 2


def _is_array_index(token: str | None) -> bool:
    return token is not None and token.isdigit()


def _parse_array_index(token: str, path: str) -> int:
    if not token.isdigit():
        raise CompactDslConversionError(
            f'Compact DSL path "{path}" contains a non-numeric list index.'
        )
    return int(token)


def _serialize_rows(rows: list[Any]) -> str:
    serialized_rows: list[str] = []
    for row in rows:
        serialized_rows.append(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(serialized_rows)


def _serialize_a2ui_messages(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for message in messages
    )
