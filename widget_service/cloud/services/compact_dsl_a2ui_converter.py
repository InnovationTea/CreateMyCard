# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Deterministically convert Design Compact DSL to standard A2UI NDJSON."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Literal

ThemeMode = Literal["light", "dark"]

_A2UI_FORM_CATALOG_ID = "ohos.a2ui.extended.catalog.form"
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
        "Button",
        "Checkbox",
    }
)
_CONTAINER_TYPES = frozenset({"Row", "Column", "List", "Stack"})
_SEMANTIC_FIELDS = {
    "Text": frozenset({"content"}),
    "Image": frozenset({"src"}),
    "Progress": frozenset({"value", "total"}),
    "Button": frozenset({"label", "enabled"}),
    "Checkbox": frozenset({"label", "value", "select"}),
}
_COMPACT_ONLY_FIELDS = {
    "Progress": frozenset({"threshold"}),
}
_REQUIRED_FIELDS = {
    "Text": "content",
    "Image": "src",
    "Progress": "value",
    "Button": "label",
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
    }
)
_FORBIDDEN_PROPERTIES = frozenset({"action", "event", "submit_form"})
_FORBIDDEN_STRING_FRAGMENTS = ("{{", "$item", "$__dataModel")
_LEGACY_TOKEN_PREFIXES = (
    "padding_level",
    "corner_radius_level",
    "font_weight_",
)
_LEGACY_FONT_SIZE_TOKENS = frozenset(
    {
        "Display_L",
        "Display_M",
        "Display_S",
        "Title_L",
        "Title_M",
        "Title_S",
        "Subtitle_L",
        "Subtitle_M",
        "Subtitle_S",
        "Body_L",
        "Body_M",
        "Body_S",
        "Caption_L",
        "Caption_M",
    }
)
_TOKEN_AWARE_PROPERTIES = frozenset(
    {
        "borderRadius",
        "fontSize",
        "fontWeight",
        "height",
        "itemMargin",
        "margin",
        "maxHeight",
        "maxWidth",
        "minHeight",
        "minWidth",
        "padding",
        "space",
        "strokeWidth",
        "width",
    }
)
_COLOR_PROPERTIES = frozenset(
    {
        "backgroundColor",
        "borderColor",
        "color",
        "fillColor",
        "fontColor",
        "selectedColor",
        "shadowColor",
        "strokeColor",
        "unSelectedColor",
    }
)
_COLOR_TOKENS = {
    "font_primary": "#E5000000",
    "font_secondary": "#99000000",
    "font_tertiary": "#66000000",
    "font_emphasize": "#FF0A59F7",
    "font_on_primary": "#FFFFFFFF",
    "warning": "#FFE84026",
    "alert": "#FFED6F21",
    "confirm": "#FF64BB5C",
    "icon_primary": "#E5000000",
    "icon_secondary": "#99000000",
    "icon_tertiary": "#66000000",
    "icon_fourth": "#33000000",
    "icon_emphasize": "#FF0A59F7",
    "icon_on_primary": "#FFFFFFFF",
    "icon_on_secondary": "#99FFFFFF",
    "icon_on_tertiary": "#66FFFFFF",
    "icon_on_fourth": "#33FFFFFF",
    "background_primary": "#FFFFFFFF",
    "background_emphasize": "#FF0A59F7",
    "comp_background_list_card": "#FFFFFFFF",
    "comp_background_emphasize": "#FF0A59F7",
    "comp_background_tertiary": "#0C000000",
    "comp_background_secondary": "#19000000",
    "comp_background_primary_contrary": "#FFFFFFFF",
    "comp_divider": "#33000000",
    "container40": "#66000000",
    "primary50": "#7F000000",
    "multi_color_01": "#FF564AF7",
    "multi_color_02": "#FF46B1E3",
    "multi_color_03": "#FF61CFBE",
    "multi_color_04": "#FF64BB5C",
    "multi_color_05": "#FFA5D61D",
    "multi_color_06": "#FFAC49F5",
    "multi_color_07": "#FFE64566",
    "multi_color_08": "#FFE84026",
    "multi_color_09": "#FFED6F21",
    "multi_color_10": "#FFF9A01E",
    "multi_color_11": "#FFF7CE00",
    "multi_color_aux_01": "#FF8981F7",
    "multi_color_aux_02": "#FF86C5E3",
    "multi_color_aux_03": "#FF92D6CC",
    "multi_color_aux_04": "#FF92C48D",
    "multi_color_aux_05": "#FFBDDB69",
    "multi_color_aux_06": "#FFC386F0",
    "multi_color_aux_07": "#FFE67C92",
    "multi_color_aux_08": "#FFE87361",
    "multi_color_aux_09": "#FFED955F",
    "multi_color_aux_10": "#FFF9BC64",
    "multi_color_aux_11": "#FFF5DC62",
    "mask_primary": "#CC000000",
    "mask_secondary": "#99000000",
    "mask_tertiary": "#66000000",
    "mask_fourth": "#33000000",
    "mask_fifth": "#19000000",
    "mask_sixth": "#0C000000",
}
_TEXT_DESIGNS: dict[str, dict[str, Any]] = {
    "display-l": {"fontSize": 56, "fontWeight": 300},
    "display-m": {"fontSize": 48, "fontWeight": 300},
    "display-s": {"fontSize": 36, "fontWeight": 700},
    "title-l": {"fontSize": 30, "fontWeight": 700},
    "title-m": {"fontSize": 24, "fontWeight": 700},
    "title-s": {"fontSize": 20, "fontWeight": 700},
    "subtitle-l": {"fontSize": 18, "fontWeight": 500},
    "subtitle-m": {"fontSize": 16, "fontWeight": 500},
    "subtitle-s": {"fontSize": 14, "fontWeight": 500},
    "body-l": {"fontSize": 16, "fontWeight": 500},
    "body-m": {"fontSize": 14, "fontWeight": 400},
    "body-s": {"fontSize": 12, "fontWeight": 400},
    "caption-l": {"fontSize": 12, "fontWeight": 500},
    "caption-m": {"fontSize": 10, "fontWeight": 500},
}
_BUTTON_DESIGNS: dict[str, dict[str, Any]] = {
    "capsule": {
        "width": "matchParent",
        "height": 36,
        "borderRadius": 20,
        "padding": {"left": 8, "top": 0, "right": 8, "bottom": 0},
        "backgroundColor": "comp_background_tertiary",
        "fontColor": "font_emphasize",
        "fontSize": 14,
        "fontWeight": 500,
        "maxFontSize": 14,
        "minFontSize": 12,
        "maxLines": 1,
        "flexShrink": 0,
    },
    "icon-round": {
        "width": 30,
        "height": 30,
        "borderRadius": 15,
        "padding": 0,
        "backgroundColor": "comp_background_tertiary",
        "flexShrink": 0,
    },
}
_IMAGE_DESIGNS: dict[str, dict[str, Any]] = {
    "icon-lg": {
        "width": "matchParent",
        "height": "matchParent",
        "aspectRatio": 1.0,
        "borderRadius": 8,
        "objectFit": "cover",
        "clip": True,
        "flexShrink": 0,
    },
}
_PROGRESS_DESIGNS: dict[str, dict[str, Any]] = {
    "linear-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "linear-bar-small": {
        "type": "linear",
        "width": "matchParent",
        "height": 4,
        "borderRadius": 2,
        "backgroundColor": "comp_background_secondary",
    },
    "segmented-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "threshold-bar": {
        "type": "linear",
        "width": "matchParent",
        "height": 20,
        "borderRadius": 10,
        "backgroundColor": "#6B7F91",
        "color": "#C8F000",
    },
    "ring": {
        "type": "ring",
        "width": "matchParent",
        "height": "matchParent",
        "strokeWidth": 6,
        "backgroundColor": "comp_background_secondary",
        "color": "multi_color_10",
    },
}
_DIVIDER_DESIGNS: dict[str, dict[str, Any]] = {
    "line": {
        "strokeWidth": 1,
        "vertical": False,
        "color": "comp_divider",
    },
    "bar": {
        "strokeWidth": 8,
        "vertical": False,
        "color": "comp_background_tertiary",
    },
}
_CHECKBOX_DESIGNS: dict[str, dict[str, Any]] = {
    "default": {
        "width": 20,
        "height": 20,
        "borderRadius": 10,
        "selectedColor": "#FF0A59F7",
        "unSelectedColor": "#66000000",
        "mark": {
            "strokeColor": "#FFFFFFFF",
            "size": 20,
            "strokeWidth": 2,
        },
        "shape": "circle",
    },
    "check": {
        "width": 16,
        "height": 16,
        "borderRadius": 4,
        "selectedColor": "icon_on_fourth",
        "unSelectedColor": "icon_tertiary",
        "mark": {
            "strokeColor": "icon_on_primary",
            "size": 16,
            "strokeWidth": 2,
        },
        "shape": "rounded_square",
    },
}
_COMPONENT_DESIGNS = {
    "Text": _TEXT_DESIGNS,
    "Image": _IMAGE_DESIGNS,
    "Button": _BUTTON_DESIGNS,
    "Progress": _PROGRESS_DESIGNS,
    "Divider": _DIVIDER_DESIGNS,
    "Checkbox": _CHECKBOX_DESIGNS,
}
_COMPACT_ROOT_DIMENSIONS = {
    "2x2": {"width": 160, "height": 160},
    "2x4": {"width": 320, "height": 160},
    "4x2": {"width": 320, "height": 160},
}
_A2UI_FALLBACK_DIMENSIONS = {
    "2x2": {"width": 140, "height": 140},
    "2x4": {"width": 300, "height": 140},
    "4x2": {"width": 300, "height": 140},
}


class CompactDslConversionError(ValueError):
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
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
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

    if not path_replacements and not literal_replacements:
        return compact_dsl
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
    normalized_components = [_normalize_component(row) for row in components]
    data_model = _build_data_model(data_rows)
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

    normalized_components = [_normalize_component(row) for row in components]
    data_model = _build_data_model(data_rows)
    _validate_binding_paths(normalized_components, data_model)

    converted_components = []
    for component in normalized_components:
        converted_components.append(_convert_component(component))

    dimensions = _surface_dimensions(size, protocol_profile)
    version = str(protocol_profile.get("version") or "v0.9")
    messages = [
        {
            "version": version,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": _A2UI_FORM_CATALOG_ID,
                "width": dimensions["width"],
                "height": dimensions["height"],
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
    return _serialize_rows(messages)


def _validate_theme(theme: str) -> None:
    if theme not in {"light", "dark"}:
        raise CompactDslConversionError(
            f'Unsupported compatibility theme "{theme}".'
        )


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
    supported_openings = {"```", "```genui", "```json"}
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
    rows: list[CompactRow] = []

    for line_number, raw_line in enumerate(body.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        value = _parse_json_line(line, line_number)
        rows.append(_parse_row(value, line_number))

    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    degraded_rows = _degrade_button_image_children(rows)
    return _canonicalize_component_order(degraded_rows)


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
    if root.component_type != "Column":
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
    if len(visited) != len(components_by_id):
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
    return _parse_component_row(value, line_number)


def _looks_like_data_row(value: list[Any]) -> bool:
    if len(value) != 2:
        return False
    return isinstance(value[0], str) and value[0].startswith("/")


def _parse_component_row(value: list[Any], line_number: int) -> ComponentRow:
    if len(value) not in {3, 4}:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} has an unsupported row shape."
        )
    component_id, component_type, props = value[:3]
    _validate_component_header(
        component_id,
        component_type,
        props,
        line_number,
    )
    children = _parse_children(value, component_id, component_type)
    _validate_component_props(component_id, component_type, props)
    return ComponentRow(
        component_id=component_id,
        component_type=component_type,
        props=copy.deepcopy(props),
        children=children,
    )


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


def _degrade_button_image_children(
    rows: list[CompactRow],
) -> list[CompactRow]:
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

    if not button_icon_ids:
        return rows

    _validate_button_icon_ownership(rows, button_icon_ids)
    degraded_rows: list[CompactRow] = []
    for row in rows:
        if isinstance(row, ComponentRow) and row.component_id in button_icon_ids:
            continue
        if isinstance(row, ComponentRow) and row.component_type == "Button":
            row = ComponentRow(
                component_id=row.component_id,
                component_type=row.component_type,
                props=row.props,
            )
        degraded_rows.append(row)
    return degraded_rows


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
        _validate_button_label(component_id, props.get("label"))
    _validate_semantic_props(component_id, component_type, props)
    if "onClick" in props:
        _validate_on_click(component_id, props["onClick"])
    _validate_source_value(props, component_id)


def _validate_allowed_component_properties(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> None:
    allowed = set(_COMMON_STYLE_PROPERTIES)
    allowed.update(_COMMON_COMPACT_PROPERTIES)
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
    if component_type == "Button":
        _validate_optional_bool(component_id, "Button.enabled", props)
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
    explicit_props = copy.deepcopy(component.props)
    design = explicit_props.pop("design", None)
    if design is None:
        return explicit_props
    if not isinstance(design, str) or not design:
        raise CompactDslConversionError(
            f"{component.component_id}: design must be a non-empty string."
        )

    component_designs = _COMPONENT_DESIGNS.get(component.component_type)
    if component_designs is None or design not in component_designs:
        raise CompactDslConversionError(
            f"{component.component_id}: unsupported "
            f'{component.component_type}.design "{design}".'
        )
    expanded = copy.deepcopy(component_designs[design])
    for property_name, value in explicit_props.items():
        expanded[property_name] = copy.deepcopy(value)
    return expanded


def _resolve_tokens(
    property_name: str,
    value: Any,
    component_id: str,
) -> Any:
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for child_name, child_value in value.items():
            nested_name = child_name
            if property_name in {"margin", "padding"}:
                nested_name = property_name
            resolved[child_name] = _resolve_tokens(
                nested_name,
                child_value,
                component_id,
            )
        return resolved
    if isinstance(value, list):
        if property_name == "colors":
            return _resolve_gradient_stops(value, component_id)
        resolved_items: list[Any] = []
        for item in value:
            resolved_items.append(
                _resolve_tokens(property_name, item, component_id)
            )
        return resolved_items
    if not isinstance(value, str):
        return value
    if property_name in _COLOR_PROPERTIES:
        return _COLOR_TOKENS.get(value, value)
    if property_name in _TOKEN_AWARE_PROPERTIES:
        _reject_legacy_style_token(component_id, property_name, value)
    return value


def _resolve_gradient_stops(
    stops: list[Any],
    component_id: str,
) -> list[Any]:
    resolved_stops: list[Any] = []
    for stop in stops:
        if not isinstance(stop, list) or len(stop) != 2:
            raise CompactDslConversionError(
                f"{component_id}: each gradient color must be [color, position]."
            )
        color, position = stop
        if not isinstance(color, str):
            raise CompactDslConversionError(
                f"{component_id}: gradient colors must be strings."
            )
        if not isinstance(position, (int, float)):
            raise CompactDslConversionError(
                f"{component_id}: gradient positions must be numbers."
            )
        resolved_stops.append([_COLOR_TOKENS.get(color, color), position])
    return resolved_stops


def _reject_legacy_style_token(
    component_id: str,
    property_name: str,
    value: str,
) -> None:
    is_legacy_prefix = value.startswith(_LEGACY_TOKEN_PREFIXES)
    is_legacy_font_size = value in _LEGACY_FONT_SIZE_TOKENS
    if is_legacy_prefix or is_legacy_font_size:
        raise CompactDslConversionError(
            f'{component_id}: legacy token "{value}" is not defined by PROMPT.md '
            f"for {property_name}."
        )


def _component_to_tuple(component: ComponentRow) -> list[Any]:
    row: list[Any] = [
        component.component_id,
        component.component_type,
        copy.deepcopy(component.props),
    ]
    if component.component_type in _CONTAINER_TYPES:
        row.append(list(component.children))
    return row


def _convert_component(component: ComponentRow) -> dict[str, Any]:
    converted: dict[str, Any] = {
        "id": component.component_id,
        "component": component.component_type,
    }
    if component.component_type in _CONTAINER_TYPES:
        converted["children"] = list(component.children)

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
        styles["width"] = "matchParent"
        styles["height"] = "matchParent"
    if styles:
        converted["styles"] = styles
    return converted


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
        if component.component_type != "Image":
            continue
        source = component.props.get("src")
        if source in allowed_sources:
            continue
        raise CompactDslConversionError(
            f'{component.component_id}: Image.src "{source}" is not present '
            "in TaskSpec.assetCandidates."
        )


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
        if component.component_type == "Button" and handlers is None:
            raise CompactDslConversionError(
                f"{component.component_id}: Button requires an onClick event."
            )
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if _stable_json(handler) in allowed_keys:
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
        call = candidate.get("call")
        args = candidate.get("args")
        if not isinstance(call, str) or not isinstance(args, dict):
            continue
        handlers.append({"call": call, "args": args})
    return handlers


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
