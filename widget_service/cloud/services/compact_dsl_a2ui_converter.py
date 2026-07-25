# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Deterministic Compact DSL design-token expansion and A2UI conversion."""

from __future__ import annotations

import copy
import json
from typing import Any, Literal

ThemeMode = Literal["light", "dark"]

_COMPONENT_TYPES = {
    "Text",
    "Image",
    "Divider",
    "Progress",
    "Button",
    "Checkbox",
    "Row",
    "Column",
    "List",
    "Stack",
}
_CONTAINER_TYPES = {"Row", "Column", "List", "Stack"}

_COLOR_TOKEN_VALUES: dict[str, tuple[str, str]] = {
    "font_primary": ("#E5000000", "#E5FFFFFF"),
    "font_secondary": ("#99000000", "#99FFFFFF"),
    "font_tertiary": ("#66000000", "#66FFFFFF"),
    "font_emphasize": ("#FF0A59F7", "#FF5291FF"),
    "font_on_primary": ("#FFFFFFFF", "#FFFFFFFF"),
    "warning": ("#FFE84026", "#FFD94838"),
    "alert": ("#FFED6F21", "#FFDB6B42"),
    "confirm": ("#FF64BB5C", "#FF5BA854"),
    "icon_primary": ("#E5000000", "#E5FFFFFF"),
    "icon_secondary": ("#99000000", "#99FFFFFF"),
    "icon_tertiary": ("#66000000", "#66FFFFFF"),
    "icon_emphasize": ("#FF0A59F7", "#FF5291FF"),
    "icon_on_primary": ("#FFFFFFFF", "#FFFFFFFF"),
    "background_primary": ("#FFFFFFFF", "#FF000000"),
    "background_emphasize": ("#FF0A59F7", "#FF317AF7"),
    "comp_background_list_card": ("#FFFFFFFF", "#19FFFFFF"),
    "comp_background_tertiary": ("#0C000000", "#19FFFFFF"),
    "comp_background_secondary": ("#19000000", "#19FFFFFF"),
    "comp_background_emphasize": ("#FF0A59F7", "#FF317AF7"),
    "comp_background_primary_contrary": ("#FFFFFFFF", "#FFE5E5E5"),
    "comp_divider": ("#33000000", "#33FFFFFF"),
    "container40": ("#66000000", "#66FFFFFF"),
    "primary50": ("#7F000000", "#7FFFFFFF"),
    "multi_color_01": ("#FF564AF7", "#FF5F58C7"),
    "multi_color_02": ("#FF46B1E3", "#FF4796C4"),
    "multi_color_03": ("#FF61CFBE", "#FF5AADA0"),
    "multi_color_04": ("#FF64BB5C", "#FF5BA854"),
    "multi_color_05": ("#FFA5D61D", "#FF86AD53"),
    "multi_color_06": ("#FFAC49F5", "#FF8C55C2"),
    "multi_color_07": ("#FFE64566", "#FFD64966"),
    "multi_color_08": ("#FFE84026", "#FFD94838"),
    "multi_color_09": ("#FFED6F21", "#FFDB6B42"),
    "multi_color_10": ("#FFF9A01E", "#FFE08C3A"),
    "multi_color_11": ("#FFF7CE00", "#FFD1A738"),
    "multi_color_aux_01": ("#FF8981F7", "#FF5550A6"),
    "multi_color_aux_02": ("#FF86C5E3", "#FF467794"),
    "multi_color_aux_03": ("#FF92D6CC", "#FF4C7A73"),
    "multi_color_aux_04": ("#FF92C48D", "#FF5C8059"),
    "multi_color_aux_05": ("#FFBDDB69", "#FF6B8052"),
    "multi_color_aux_06": ("#FFC386F0", "#FF634794"),
    "multi_color_aux_07": ("#FFE67C92", "#FFA14A5C"),
    "multi_color_aux_08": ("#FFE87361", "#FF9C554B"),
    "multi_color_aux_09": ("#FFED955F", "#FF9E644F"),
    "multi_color_aux_10": ("#FFF9BC64", "#FF9E7349"),
    "multi_color_aux_11": ("#FFF5DC62", "#FF997E39"),
    "mask_primary": ("#CC000000", "#CC000000"),
    "mask_secondary": ("#99000000", "#99000000"),
    "mask_tertiary": ("#66000000", "#66000000"),
    "mask_fourth": ("#33000000", "#33000000"),
    "mask_fifth": ("#19000000", "#19000000"),
    "mask_sixth": ("#0C000000", "#0C000000"),
}

_RADIUS_TOKENS = {
    "corner_radius_level2": 4,
    "corner_radius_level4": 8,
    "corner_radius_level6": 12,
    "corner_radius_level7": 14,
    "corner_radius_level8": 16,
    "corner_radius_level9": 18,
    "corner_radius_level10": 20,
    "corner_radius_level12": 24,
}

_SPACING_TOKENS = {
    "padding_level1": 2,
    "padding_level2": 4,
    "padding_level4": 8,
    "padding_level6": 12,
    "padding_level8": 16,
    "padding_level10": 20,
    "padding_level12": 24,
}

_FONT_SIZE_TOKENS = {
    "Display_L": 56,
    "Display_M": 48,
    "Display_S": 38,
    "Title_L": 30,
    "Title_M": 24,
    "Title_S": 20,
    "Subtitle_L": 18,
    "Subtitle_M": 16,
    "Subtitle_S": 14,
    "Body_L": 16,
    "Body_M": 14,
    "Body_S": 12,
    "Caption_L": 12,
    "Caption_M": 10,
}

_FONT_WEIGHT_TOKENS = {
    "font_weight_light": 300,
    "font_weight_regular": 400,
    "font_weight_medium": 500,
    "font_weight_bold": 700,
    "thin": 100,
    "light": 300,
    "normal": 400,
    "regular": 400,
    "medium": 500,
    "bold": 700,
    "bolder": 900,
}

_TEXT_DESIGNS: dict[str, dict[str, Any]] = {
    "display-l": {"fontSize": 56, "fontWeight": 300},
    "display-m": {"fontSize": 48, "fontWeight": 300},
    "display-s": {"fontSize": 38, "fontWeight": 300},
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
    "default": {
        "height": 40,
        "borderRadius": 20,
        "padding": {"left": 16, "top": 8, "right": 16, "bottom": 8},
        "backgroundColor": "comp_background_tertiary",
        "fontColor": "font_emphasize",
        "fontSize": 16,
        "fontWeight": 500,
    },
    "primary": {
        "height": 40,
        "borderRadius": 20,
        "padding": {"left": 16, "top": 8, "right": 16, "bottom": 8},
        "backgroundColor": "comp_background_emphasize",
        "fontColor": "font_on_primary",
        "fontSize": 16,
        "fontWeight": 500,
    },
    "icon": {
        "width": 48,
        "height": 48,
        "borderRadius": 24,
        "padding": 12,
        "backgroundColor": "comp_background_tertiary",
        "flexShrink": 0,
    },
    "default-sm": {
        "height": 28,
        "borderRadius": 14,
        "padding": {"left": 8, "top": 4, "right": 8, "bottom": 4},
        "backgroundColor": "comp_background_tertiary",
        "fontColor": "font_emphasize",
        "fontSize": 14,
        "fontWeight": 500,
    },
    "primary-sm": {
        "height": 28,
        "borderRadius": 14,
        "padding": {"left": 8, "top": 4, "right": 8, "bottom": 4},
        "backgroundColor": "comp_background_emphasize",
        "fontColor": "font_on_primary",
        "fontSize": 14,
        "fontWeight": 500,
    },
    "icon-sm": {
        "width": 40,
        "height": 40,
        "borderRadius": 20,
        "padding": 8,
        "backgroundColor": "comp_background_tertiary",
        "flexShrink": 0,
    },
}

_PROGRESS_DESIGNS: dict[str, dict[str, Any]] = {
    "linear": {
        "type": "linear",
        "height": 4,
        "borderRadius": 2,
        "backgroundColor": "comp_background_secondary",
        "color": "background_emphasize",
    },
    "eclipse": {
        "type": "eclipse",
        "width": 20,
        "height": 20,
        "color": "comp_background_secondary",
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
        "selectedColor": "comp_background_emphasize",
        "unSelectedColor": "icon_tertiary",
        "mark": {
            "strokeColor": "icon_on_primary",
            "size": 20,
            "strokeWidth": 2,
        },
        "shape": "circle",
    }
}

_COMPONENT_DESIGNS = {
    "Text": _TEXT_DESIGNS,
    "Button": _BUTTON_DESIGNS,
    "Progress": _PROGRESS_DESIGNS,
    "Divider": _DIVIDER_DESIGNS,
    "Checkbox": _CHECKBOX_DESIGNS,
}

_COLOR_PROPERTIES = {
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
_SPACING_PROPERTIES = {
    "height",
    "itemMargin",
    "margin",
    "maxHeight",
    "maxWidth",
    "minHeight",
    "minWidth",
    "padding",
    "size",
    "space",
    "strokeWidth",
    "width",
}

_SEMANTIC_FIELDS = {
    "Text": {"content"},
    "Image": {"src"},
    "Progress": {"value", "total"},
    "Button": {"label", "enabled"},
    "Checkbox": {"label", "value", "group", "select"},
}


class CompactDslConversionError(ValueError):
    """Raised when valid A2UI cannot be derived from Compact DSL."""


def normalize_compact_dsl_design_tokens(
    compact_dsl: str,
    *,
    theme: ThemeMode = "light",
) -> str:
    """Expand component designs and semantic tokens to explicit Compact props."""
    _validate_theme(theme)
    rows = _parse_compact_rows(compact_dsl)
    normalized_rows: list[list[Any]] = []
    for row in rows:
        if not _is_component_row(row):
            normalized_rows.append(row)
            continue
        normalized_rows.append(_normalize_component_row(row, theme))
    return _serialize_rows(normalized_rows)


def convert_compact_dsl_to_a2ui(
    compact_dsl: str,
    *,
    size: str,
    protocol_profile: dict[str, Any],
    theme: ThemeMode = "light",
    surface_id: str = "surface_card",
) -> str:
    """Convert Compact DSL NDJSON to standard three-message A2UI JSONL."""
    normalized = normalize_compact_dsl_design_tokens(compact_dsl, theme=theme)
    rows = _parse_compact_rows(normalized)
    components: list[dict[str, Any]] = []
    data_rows: list[list[Any]] = []
    component_ids: set[str] = set()

    for row in rows:
        if _is_component_row(row):
            component = _convert_component(row)
            component_id = str(component.get("id"))
            if component_id in component_ids:
                raise CompactDslConversionError(
                    f'Duplicate Compact DSL component id "{component_id}".'
                )
            component_ids.add(component_id)
            components.append(component)
            continue
        data_rows.append(row)

    if not components:
        raise CompactDslConversionError("Compact DSL does not contain components.")
    root_id = "root"
    if root_id not in component_ids:
        raise CompactDslConversionError('Compact DSL does not contain root component "root".')

    dimensions = _surface_dimensions(size, protocol_profile)
    version = str(protocol_profile.get("version") or "v0.9")
    catalog_id = str(
        protocol_profile.get("catalogId") or "ohos.a2ui.extended.catalog.form"
    )
    data_model = _build_data_model(data_rows)

    messages = [
        {
            "version": version,
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": catalog_id,
                "width": dimensions["width"],
                "height": dimensions["height"],
            },
        },
        {
            "version": version,
            "updateComponents": {
                "surfaceId": surface_id,
                "root": root_id,
                "components": components,
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
        raise CompactDslConversionError(f'Unsupported design token theme "{theme}".')


def _parse_compact_rows(compact_dsl: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for line_number, raw_line in enumerate(compact_dsl.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CompactDslConversionError(
                f"Compact DSL line {line_number} is invalid JSON: {exc}."
            ) from exc
        if not isinstance(row, list):
            raise CompactDslConversionError(
                f"Compact DSL line {line_number} must be a JSON array."
            )
        if not _is_component_row(row) and not _is_data_row(row):
            raise CompactDslConversionError(
                f"Compact DSL line {line_number} has an unsupported row shape."
            )
        rows.append(row)
    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    return rows


def _is_component_row(row: list[Any]) -> bool:
    if len(row) not in {3, 4}:
        return False
    if not isinstance(row[0], str) or not isinstance(row[1], str):
        return False
    if row[1] not in _COMPONENT_TYPES or not isinstance(row[2], dict):
        return False
    if row[1] in _CONTAINER_TYPES:
        return len(row) == 4 and isinstance(row[3], list)
    return len(row) == 3


def _is_data_row(row: list[Any]) -> bool:
    return len(row) == 2 and isinstance(row[0], str) and row[0].startswith("/")


def _normalize_component_row(row: list[Any], theme: ThemeMode) -> list[Any]:
    component_id = row[0]
    component_type = row[1]
    props = _expand_component_design(component_id, component_type, row[2])
    resolved_props: dict[str, Any] = {}
    for key, value in props.items():
        resolved_props[key] = _resolve_style_tokens(key, value, theme)

    normalized = [component_id, component_type, resolved_props]
    if component_type in _CONTAINER_TYPES:
        normalized.append(copy.deepcopy(row[3]))
    return normalized


def _expand_component_design(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
) -> dict[str, Any]:
    explicit_props = copy.deepcopy(props)
    design = explicit_props.pop("design", None)
    if design is None:
        return explicit_props
    if not isinstance(design, str) or not design:
        raise CompactDslConversionError(
            f'{component_id}: design must be a non-empty string.'
        )
    component_designs = _COMPONENT_DESIGNS.get(component_type)
    if component_designs is None or design not in component_designs:
        raise CompactDslConversionError(
            f'{component_id}: unsupported {component_type}.design "{design}".'
        )
    expanded = copy.deepcopy(component_designs[design])
    for key, value in explicit_props.items():
        expanded[key] = _merge_values(expanded.get(key), value)
    return expanded


def _resolve_style_tokens(
    property_name: str,
    value: Any,
    theme: ThemeMode,
) -> Any:
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for child_name, child_value in value.items():
            nested_property_name = child_name
            if property_name in {"margin", "padding"}:
                nested_property_name = property_name
            resolved[child_name] = _resolve_style_tokens(
                nested_property_name,
                child_value,
                theme,
            )
        return resolved
    if isinstance(value, list):
        if property_name == "colors":
            return _resolve_gradient_stops(value, theme)
        resolved_items: list[Any] = []
        for item in value:
            resolved_items.append(_resolve_style_tokens(property_name, item, theme))
        return resolved_items
    if not isinstance(value, str):
        return value

    if property_name in _COLOR_PROPERTIES:
        return _resolve_color(value, theme)
    if property_name == "borderRadius":
        return _RADIUS_TOKENS.get(value, value)
    if property_name in _SPACING_PROPERTIES:
        return _SPACING_TOKENS.get(value, value)
    if property_name == "fontSize":
        return _FONT_SIZE_TOKENS.get(value, value)
    if property_name == "fontWeight":
        return _FONT_WEIGHT_TOKENS.get(value, value)
    return value


def _resolve_gradient_stops(stops: list[Any], theme: ThemeMode) -> list[Any]:
    resolved_stops: list[Any] = []
    for stop in stops:
        if not isinstance(stop, list) or not stop:
            resolved_stops.append(copy.deepcopy(stop))
            continue
        resolved_stop = copy.deepcopy(stop)
        color = resolved_stop[0]
        if isinstance(color, str):
            resolved_stop[0] = _resolve_color(color, theme)
        resolved_stops.append(resolved_stop)
    return resolved_stops


def _resolve_color(value: str, theme: ThemeMode) -> str:
    color_pair = _COLOR_TOKEN_VALUES.get(value)
    if color_pair is None:
        return value
    if theme == "dark":
        return color_pair[1]
    return color_pair[0]


def _convert_component(row: list[Any]) -> dict[str, Any]:
    component_id = row[0]
    component_type = row[1]
    props = row[2]
    component: dict[str, Any] = {
        "id": component_id,
        "component": component_type,
    }
    styles: dict[str, Any] = {}

    if component_type in _CONTAINER_TYPES:
        component["children"] = copy.deepcopy(row[3])

    semantic_fields = _SEMANTIC_FIELDS.get(component_type, set())
    for key, source_value in props.items():
        value = _convert_path_bindings(source_value)
        if key == "space" and component_type in {"Row", "Column", "Stack"}:
            component["itemMargin"] = value
            continue
        if key == "space" and component_type == "List":
            component["space"] = value
            continue
        if key == "wrap" and component_type == "Row":
            component["wrap"] = value
            continue
        if key == "action" and component_type == "Button":
            component["onClick"] = _convert_button_action(value, component_id)
            continue
        if key == "onClick":
            component["onClick"] = _convert_on_click(value, component_id)
            continue
        if key in semantic_fields:
            component[key] = value
            continue
        styles[key] = value

    if component_id == "root":
        styles["width"] = "matchParent"
        styles["height"] = "matchParent"
    if styles:
        component["styles"] = styles
    return component


def _convert_button_action(action: Any, component_id: str) -> list[dict[str, Any]]:
    if not isinstance(action, dict):
        raise CompactDslConversionError(
            f"{component_id}: Button.action must be an object."
        )
    function_call = action.get("functionCall")
    if not isinstance(function_call, dict):
        raise CompactDslConversionError(
            f"{component_id}: Button.action.functionCall must be an object."
        )
    return [_convert_event_handler(function_call, component_id)]


def _convert_on_click(on_click: Any, component_id: str) -> list[dict[str, Any]]:
    if not isinstance(on_click, list):
        raise CompactDslConversionError(
            f"{component_id}: onClick must be an array."
        )
    handlers: list[dict[str, Any]] = []
    for handler in on_click:
        if not isinstance(handler, dict):
            raise CompactDslConversionError(
                f"{component_id}: each onClick handler must be an object."
            )
        handlers.append(_convert_event_handler(handler, component_id))
    return handlers


def _convert_event_handler(
    handler: dict[str, Any],
    component_id: str,
) -> dict[str, Any]:
    call = handler.get("call")
    args = handler.get("args")
    if not isinstance(call, str) or not call:
        raise CompactDslConversionError(
            f"{component_id}: event call must be a non-empty string."
        )
    if not isinstance(args, dict):
        raise CompactDslConversionError(
            f"{component_id}: event args must be an object."
        )
    event_handler: dict[str, Any] = {
        "call": call,
        "args": _convert_path_bindings(args),
    }
    alias = handler.get("as")
    if isinstance(alias, str) and alias:
        event_handler["as"] = alias
    condition = handler.get("condition")
    if condition is not None:
        event_handler["condition"] = _convert_path_bindings(condition)
    return event_handler


def _convert_path_bindings(value: Any) -> Any:
    if isinstance(value, dict):
        path = value.get("path")
        if set(value) == {"path"} and isinstance(path, str):
            return f"{{{{ ${{{path}}} }}}}"
        converted: dict[str, Any] = {}
        for key, child_value in value.items():
            converted[key] = _convert_path_bindings(child_value)
        return converted
    if isinstance(value, list):
        converted_items: list[Any] = []
        for item in value:
            converted_items.append(_convert_path_bindings(item))
        return converted_items
    return value


def _surface_dimensions(
    size: str,
    protocol_profile: dict[str, Any],
) -> dict[str, int]:
    sizes = protocol_profile.get("sizes")
    if isinstance(sizes, dict):
        dimensions = sizes.get(size)
        if isinstance(dimensions, dict):
            width = dimensions.get("width")
            height = dimensions.get("height")
            if isinstance(width, int) and isinstance(height, int):
                return {"width": width, "height": height}
    if size == "2x2":
        return {"width": 140, "height": 140}
    if size == "2x4":
        return {"width": 300, "height": 140}
    raise CompactDslConversionError(f'Unsupported Form size "{size}".')


def _build_data_model(data_rows: list[list[Any]]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for row in data_rows:
        _set_json_pointer(root, row[0], copy.deepcopy(row[1]))
    return root


def _set_json_pointer(root: dict[str, Any], path: str, value: Any) -> None:
    tokens = _decode_json_pointer(path)
    if not tokens:
        if not isinstance(value, dict):
            raise CompactDslConversionError(
                "Compact DSL root DataModel row must contain an object."
            )
        merged = _merge_values(root, value)
        root.clear()
        root.update(merged)
        return

    current: dict[str, Any] | list[Any] = root
    for index, token in enumerate(tokens):
        is_last = index == len(tokens) - 1
        next_token = None if is_last else tokens[index + 1]
        if isinstance(current, dict):
            if is_last:
                current[token] = _merge_values(current.get(token), value)
                return
            expected: dict[str, Any] | list[Any]
            expected = [] if _is_array_index(next_token) else {}
            child = current.get(token)
            if not isinstance(child, type(expected)):
                child = expected
                current[token] = child
            current = child
            continue

        array_index = _parse_array_index(token, path)
        while len(current) <= array_index:
            current.append(None)
        if is_last:
            current[array_index] = _merge_values(current[array_index], value)
            return
        expected = [] if _is_array_index(next_token) else {}
        child = current[array_index]
        if not isinstance(child, type(expected)):
            child = expected
            current[array_index] = child
        current = child


def _decode_json_pointer(path: str) -> list[str]:
    if path == "/":
        return []
    if not path.startswith("/"):
        raise CompactDslConversionError(
            f'Compact DSL DataModel path "{path}" is not a JSON Pointer.'
        )
    tokens: list[str] = []
    for token in path[1:].split("/"):
        tokens.append(token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _is_array_index(token: str | None) -> bool:
    return token is not None and token.isdigit()


def _parse_array_index(token: str, path: str) -> int:
    if not token.isdigit():
        raise CompactDslConversionError(
            f'Compact DSL DataModel path "{path}" contains a non-numeric list index.'
        )
    return int(token)


def _merge_values(existing: Any, incoming: Any) -> Any:
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = copy.deepcopy(existing)
        for key, value in incoming.items():
            merged[key] = _merge_values(merged.get(key), value)
        return merged
    return copy.deepcopy(incoming)


def _serialize_rows(rows: list[Any]) -> str:
    serialized: list[str] = []
    for row in rows:
        serialized.append(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(serialized)
