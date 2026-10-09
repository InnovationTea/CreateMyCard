# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Deterministically convert Design Compact DSL to standard A2UI NDJSON."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from services.compact_component_runtime import (
    CompactComponentRuntimeError,
    component_visual_recipe,
    visual_recipe_part,
)
from services.fusion_ball_expander import (
    FusionBallExpansionError,
    expand_fusion_ball_components,
    fusion_ball_palette_for_root,
)

ThemeMode = Literal["light", "dark"]

_A2UI_FORM_CATALOG_ID = "ohos.a2ui.extended.catalog.form"
_A2UI_ICON_BUTTON_LABEL = "\u200b"
COMPACT_INPUT_COMPONENT_TYPES = frozenset(
    {
        "Row",
        "Column",
        "Stack",
        "Text",
        "Image",
        "Divider",
        "ProgressCircle",
        "PillButton",
        "CircleButton",
        "CardHeader",
        "EmphasizedData",
        "InfoBlock",
        "ProgressLine2",
        "TableText",
        "TextBlock",
        "CardButton",
        "ProgressCircleSingle",
        "EventCard",
        "DataDisplay",
        "TopTextBottomValue",
        "SummaryList",
    }
)
_CONTAINER_TYPES = frozenset({"Row", "Column", "Stack"})
_SEMANTIC_FIELDS = {
    "Text": frozenset({"content"}),
    "Image": frozenset({"src"}),
    "Progress": frozenset({"value", "total"}),
    # Button is converter output for PillButton; it is not accepted as Compact input.
    "Button": frozenset({"label", "enabled"}),
}
_COMPACT_ONLY_FIELDS = {
    "Progress": frozenset({"threshold"}),
}
_COMMON_STYLE_PROPERTIES = frozenset(
    {
        "alignSelf",
        "aspectRatio",
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "backdropBlur",
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
            "textAlign",
        }
    ),
    "Row": frozenset({"alignItems", "itemMargin", "justifyContent"}),
    "Column": frozenset({"alignItems", "itemMargin", "justifyContent"}),
    "Stack": frozenset({"alignContent"}),
}
_COMMON_COMPACT_ONLY_PROPERTIES = frozenset({"accessibility", "accessibily"})
_A2UI_BINDING_EXPRESSION_PATTERN = re.compile(r"^\{\{\s*(?P<body>.*?)\s*\}\}$")
_A2UI_BINDING_PATH_PATTERN = re.compile(r"\$\{(?P<path>/[^}\s]+)\}")
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
_COLOR_PROPERTIES = frozenset(
    {
        "backgroundColor",
        "borderColor",
        "color",
        "fillColor",
        "fontColor",
        "actionInk",
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
    "palette_purple_primary": "#FF564AF7",
    "palette_blue_primary": "#FF46B1E3",
    "palette_mint_primary": "#FF61CFBE",
    "palette_green_success": "#FF64BB5C",
    "palette_lime_success": "#FFA5D61D",
    "palette_violet_primary": "#FFAC49F5",
    "palette_rose_alert": "#FFE64566",
    "palette_red_warning": "#FFE84026",
    "palette_orange_alert": "#FFED6F21",
    "palette_amber_warning": "#FFF9A01E",
    "palette_yellow_sun": "#FFF7CE00",
    "palette_purple_soft": "#FF8981F7",
    "palette_blue_soft": "#FF86C5E3",
    "palette_mint_soft": "#FF92D6CC",
    "palette_green_soft": "#FF92C48D",
    "palette_lime_soft": "#FFBDDB69",
    "palette_violet_soft": "#FFC386F0",
    "palette_rose_soft": "#FFE67C92",
    "palette_red_soft": "#FFE87361",
    "palette_orange_soft": "#FFED955F",
    "palette_amber_soft": "#FFF9BC64",
    "palette_yellow_soft": "#FFF5DC62",
    "mask_primary": "#CC000000",
    "mask_secondary": "#99000000",
    "mask_tertiary": "#66000000",
    "mask_fourth": "#33000000",
    "mask_fifth": "#19000000",
    "mask_sixth": "#0C000000",
}
_DEFAULT_ROOT_BACKGROUND = "#FFE5EDFE"
_TEXT_DESIGNS: dict[str, dict[str, Any]] = {
    "metric-display-xl": {"fontSize": 38, "fontWeight": 300},
    "metric-display-lg": {"fontSize": 38, "fontWeight": 300},
    "metric-display-md": {"fontSize": 36, "fontWeight": 700},
    "heading-primary-lg": {"fontSize": 20, "fontWeight": 700},
    "heading-primary-md": {"fontSize": 20, "fontWeight": 700},
    "heading-primary-sm": {"fontSize": 20, "fontWeight": 700},
    "heading-secondary-lg": {"fontSize": 18, "fontWeight": 500},
    "heading-secondary-md": {"fontSize": 16, "fontWeight": 500},
    "heading-secondary-sm": {"fontSize": 14, "fontWeight": 500},
    "body-emphasis-md": {"fontSize": 16, "fontWeight": 500},
    "body-regular-md": {"fontSize": 14, "fontWeight": 400},
    "body-regular-sm": {"fontSize": 12, "fontWeight": 400},
    "caption-emphasis": {"fontSize": 12, "fontWeight": 500},
    "caption-regular": {"fontSize": 10, "fontWeight": 500},
    "card-header-title": {"fontSize": 12, "fontWeight": 400},
    "metric-hero-value": {"fontSize": 30, "fontWeight": 700},
    "metric-hero-unit": {"fontSize": 12, "fontWeight": 400},
    "metadata-secondary": {"fontSize": 12, "fontWeight": 400},
}
_IMAGE_DESIGNS: dict[str, dict[str, Any]] = {
    "media-cover-square": {
        "width": "matchParent",
        "height": "matchParent",
        "aspectRatio": 1.0,
        "borderRadius": 8,
        "objectFit": "cover",
        "clip": True,
        "flexShrink": 0,
    },
    "icon-source-small": {
        "width": 20,
        "height": 20,
        "objectFit": "contain",
        "flexShrink": 0,
    },
    "icon-hero-large": {
        "width": 36,
        "height": 36,
        "objectFit": "contain",
        "flexShrink": 0,
    },
}
_PROGRESS_DESIGNS: dict[str, dict[str, Any]] = {
    "progress-linear-primary": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "progress-linear-thin": {
        "type": "linear",
        "width": "matchParent",
        "height": 4,
        "borderRadius": 2,
        "backgroundColor": "comp_background_secondary",
    },
    "progress-linear-segmented": {
        "type": "linear",
        "width": "matchParent",
        "height": 8,
        "borderRadius": 4,
        "backgroundColor": "comp_background_secondary",
    },
    "progress-linear-threshold": {
        "type": "linear",
        "width": "matchParent",
        "height": 20,
        "borderRadius": 10,
        "backgroundColor": "#6B7F91",
        "color": "#C8F000",
    },
    "progress-ring-primary": {
        "type": "ring",
        "width": "matchParent",
        "height": "matchParent",
        "strokeWidth": 6,
        "backgroundColor": "comp_background_secondary",
        "color": "palette_amber_warning",
    },
}
_DIVIDER_DESIGNS: dict[str, dict[str, Any]] = {
    "divider-hairline": {
        "strokeWidth": 1,
        "vertical": False,
        "color": "comp_divider",
    },
    "divider-thick": {
        "strokeWidth": 8,
        "vertical": False,
        "color": "comp_background_tertiary",
    },
}
_COMPONENT_DESIGNS = {
    "Text": _TEXT_DESIGNS,
    "Image": _IMAGE_DESIGNS,
    "Progress": _PROGRESS_DESIGNS,
    "Divider": _DIVIDER_DESIGNS,
}
_DESIGN_ALIASES: dict[str, dict[str, str]] = {}


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

# 外部布局只作用于组件根，不允许覆盖 Recipe 的内部字号、配色或结构。
_PLACEMENT_PROPS = frozenset({"width", "height", "layoutWeight", "flexShrink", "margin"})


def _place_high_level_root(
    original: ComponentRow,
    expanded: ComponentRow,
    parent: ComponentRow | None,
) -> ComponentRow:
    props = copy.deepcopy(expanded.props)
    if parent is not None and parent.component_type == "Row":
        if props.get("width") == "matchParent" and "width" not in original.props:
            props["layoutWeight"] = 1
    for name in _PLACEMENT_PROPS:
        if name in original.props:
            props[name] = copy.deepcopy(original.props[name])
    if "width" in original.props and "layoutWeight" not in original.props:
        props.pop("layoutWeight", None)
    return ComponentRow(expanded.component_id, expanded.component_type, props, expanded.children)


def _visual_recipe(
    component_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
) -> dict[str, Any]:
    try:
        return component_visual_recipe(component_name, size=size, variant=variant)
    except CompactComponentRuntimeError as exc:
        raise CompactDslConversionError(str(exc)) from exc


def _visual_recipe_part_for_converter(
    component_name: str,
    part_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
) -> tuple[str, dict[str, Any]]:
    try:
        return visual_recipe_part(
            component_name,
            part_name,
            size=size,
            variant=variant,
        )
    except CompactComponentRuntimeError as exc:
        raise CompactDslConversionError(str(exc)) from exc


def _visual_row(
    component_id: str,
    component_name: str,
    part_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
    props: dict[str, Any] | None = None,
    children: tuple[str, ...] = (),
) -> ComponentRow:
    component_type, styles = _visual_recipe_part_for_converter(
        component_name,
        part_name,
        size=size,
        variant=variant,
    )
    if props:
        styles.update(copy.deepcopy(props))
    return ComponentRow(component_id, component_type, styles, children)


def parse_compact_dsl_rows(compact_dsl: str) -> tuple[CompactRow, ...]:
    """Parse Design Compact DSL into the row model shared with validation."""
    return tuple(_parse_compact_rows(compact_dsl))


def build_compact_data_model(data_rows: list[DataRow]) -> dict[str, Any]:
    """Build the first-frame DataModel represented by Compact DSL data rows."""
    return _build_data_model(data_rows)


def expand_high_level_component_rows(
    components: list[ComponentRow],
    *,
    size: str,
) -> list[ComponentRow]:
    """Expand Fusion high-level rows into the existing base Compact components."""
    existing_ids = {component.component_id for component in components}
    parents: dict[str, ComponentRow] = {}
    for parent in components:
        for child_id in parent.children:
            parents[child_id] = parent
    generated_ids: set[str] = set()
    expanded: list[ComponentRow] = []
    expanders = {
        "PillButton": _expand_pill_button,
        "CircleButton": _expand_circle_button,
        "EmphasizedData": _expand_emphasized_data,
        "InfoBlock": _expand_info_block,
        "ProgressCircle": _expand_progress_circle,
        "ProgressLine2": _expand_progress_line_two,
        "TableText": _expand_table_text,
        "TextBlock": _expand_text_block,
        "CardButton": _expand_card_button,
        "ProgressCircleSingle": _expand_progress_circle_single,
        "EventCard": _expand_event_card,
        "DataDisplay": _expand_data_display,
        "TopTextBottomValue": _expand_top_text_bottom_value,
        "SummaryList": _expand_summary_list,
    }
    for component in components:
        expander = expanders.get(component.component_type)
        parent = parents.get(component.component_id)
        rows = [component] if expander is None else expander(component, size)
        if component.component_type == "CircleButton":
            _validate_circle_button_slot(parent)
        if expander is not None:
            rows[0] = _place_high_level_root(
                component, rows[0], parent
            )
        elif component.component_type == "CardHeader":
            header = ComponentRow(
                component.component_id,
                component.component_type,
                {"width": "matchParent", **component.props},
                component.children,
            )
            rows[0] = _place_high_level_root(component, header, parents.get(component.component_id))
        for index, row in enumerate(rows):
            is_original_root = index == 0 and row.component_id == component.component_id
            if not is_original_root and row.component_id in existing_ids:
                raise CompactDslConversionError(
                    f"{component.component_type} generated id {row.component_id} collides "
                    "with an existing component."
                )
            if row.component_id in generated_ids:
                raise CompactDslConversionError(
                    f"High-level component generated duplicate id {row.component_id}."
                )
            generated_ids.add(row.component_id)
            expanded.append(row)
    return expanded


def _validate_circle_button_slot(parent: ComponentRow | None) -> None:
    if (
        parent is None
        or parent.component_type != "Stack"
        or parent.props.get("width") != 40
        or parent.props.get("height") != 40
        or parent.props.get("alignContent") != "center"
    ):
        raise CompactDslConversionError(
            "CircleButton requires a centered 40x40 Stack slot."
        )


def normalize_compact_dsl_design_tokens(
    compact_dsl: str,
    *,
    theme: ThemeMode = "light",
) -> str:
    """Expand the design aliases defined by the current Design Compact prompt."""
    rows = _parse_compact_rows(compact_dsl)
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
    components, data_rows = _split_component_rows(rows)
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
            suffix = path[len("/data") :]
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

    if not path_replacements and not literal_replacements and not event_replacements:
        return compact_dsl
    return _serialize_repaired_rows(
        rows,
        path_replacements=path_replacements,
        literal_replacements=literal_replacements,
        event_replacements=event_replacements,
    )


def _serialize_repaired_rows(
    rows: list[CompactRow],
    *,
    path_replacements: dict[str, str] | None = None,
    literal_replacements: dict[str, Any] | None = None,
    event_replacements: dict[str, dict[str, Any]] | None = None,
) -> str:
    path_replacements = path_replacements or {}
    literal_replacements = literal_replacements or {}
    event_replacements = event_replacements or {}
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
    return _serialize_rows(repaired_rows)


def convert_compact_dsl_to_a2ui(
    compact_dsl: str,
    *,
    size: str,
    protocol_profile: dict[str, Any] | None = None,
    theme: ThemeMode = "light",
    surface_id: str = "surface_card",
) -> str:
    """Convert one Design Compact DSL card to standard three-message A2UI."""
    profile = protocol_profile or {"version": "v0.9"}
    rows = _parse_compact_rows(compact_dsl)
    components, data_rows = _split_component_rows(rows)
    components = expand_high_level_component_rows(components, size=size)
    validate_card_header_layout(components, size=size)
    fusion_palette = fusion_ball_palette_for_root(
        components,
        size=size,
        app_version=profile.get("appVersion"),
    )

    normalized_components = [_normalize_component(row) for row in components]
    data_model = _build_data_model(data_rows)

    icon_round_button_ids = _button_ids_with_design(components, "action-icon-round")
    converted_components = []
    for component in normalized_components:
        hide_label = component.component_id in icon_round_button_ids
        converted_components.extend(
            _convert_component_rows(
                component,
                hide_label=hide_label,
                card_size=size,
            )
        )
    if fusion_palette is not None:
        try:
            converted_components = expand_fusion_ball_components(
                converted_components,
                fusion_palette,
            )
        except FusionBallExpansionError as exc:
            raise CompactDslConversionError(str(exc)) from exc
    # Compact / Web 的缺省间距为 0，不继承宿主 Row / Column 的不同默认值。
    for converted in converted_components:
        if converted.get("component") in {"Row", "Column"}:
            converted.setdefault("itemMargin", 0)
    version = str(profile.get("version") or "v0.9")
    create_surface = {
        "surfaceId": surface_id,
        "catalogId": _A2UI_FORM_CATALOG_ID,
    }
    messages = [
        {
            "version": version,
            "createSurface": create_surface,
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


def validate_card_header_layout(components: list[ComponentRow], *, size: str) -> None:
    headers = [item for item in components if item.component_type == "CardHeader"]
    if not headers:
        return
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("CardHeader requires a 2x2 or 2x4 card.")
    for header in headers:
        _validate_high_level_props(
            header,
            required={"title", "fontColor"},
            allowed={"title", "fontColor", "icon", "fillColor"},
        )
        _validate_card_header_props(header, components)


def _validate_card_header_props(header: ComponentRow, components: list[ComponentRow]) -> None:
    title = header.props.get("title")
    valid_title = isinstance(title, str) and bool(title.strip())
    if not valid_title and not _is_path_binding(title):
        raise CompactDslConversionError(
            "CardHeader.title must be non-empty text or a path binding."
        )
    icon = header.props.get("icon")
    if "icon" in header.props and (not isinstance(icon, str) or not icon.strip()):
        raise CompactDslConversionError(
            "CardHeader.icon must be a non-empty asset path when present."
        )
    if "fillColor" in header.props and icon is None:
        raise CompactDslConversionError("CardHeader.fillColor requires icon.")
    width = header.props.get("width")
    valid_width = width == "matchParent" or _is_positive_number(width)
    if width is not None and not valid_width:
        raise CompactDslConversionError(
            "CardHeader.width must be matchParent or a positive number."
        )
    height = header.props.get("height")
    if height is not None and height != 20:
        raise CompactDslConversionError("CardHeader.height must be 20 when provided.")
    for name in ("fontColor", "fillColor"):
        if name == "fillColor" and name not in header.props:
            continue
        color = header.props.get(name)
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{8}", color):
            raise CompactDslConversionError(f"CardHeader.{name} must use #AARRGGBB.")
    generated_ids = {f"{header.component_id}_title", f"{header.component_id}_icon"}
    if any(item.component_id in generated_ids for item in components):
        raise CompactDslConversionError("CardHeader generated title/icon ids must not collide.")


def _is_positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _expand_progress_circle(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("ProgressCircle requires a 2x2 or 2x4 card.")
    allowed = {
        "externalText",
        "icon",
        "accessibility",
        "fontColor",
        "fillColor",
        "color",
        "backgroundColor",
        "width",
        "height",
    }
    _validate_high_level_props(
        component,
        required={
            "externalText",
            "icon",
            "accessibility",
            "fontColor",
            "color",
            "backgroundColor",
            "width",
            "height",
        },
        allowed=allowed,
    )
    _validate_optional_icon(component)
    for name in ("fontColor", "color", "backgroundColor"):
        _require_color(component, name)
    _validate_progress_circle_accessibility(component)

    width = component.props.get("width")
    height = component.props.get("height")
    recipe = _visual_recipe("ProgressCircle", size=size)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactDslConversionError("ProgressCircle visual recipe has invalid metrics.")
    text_height = metrics.get("externalTextHeight")
    item_margin = metrics.get("itemMargin")
    minimum_diameter = metrics.get("minimumRingDiameter")
    stroke_width = metrics.get("strokeWidth")
    numeric_metrics = (text_height, item_margin, minimum_diameter, stroke_width)
    if not all(_is_positive_number(value) for value in numeric_metrics):
        raise CompactDslConversionError("ProgressCircle visual recipe has invalid geometry.")
    if not _is_positive_number(width) or not _is_positive_number(height):
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircle width/height must be positive numbers."
        )
    ring_diameter = min(width, height - text_height - item_margin)
    if ring_diameter < minimum_diameter:
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircle width/height leave less than "
            f"{minimum_diameter}vp for the ring."
        )
    progress_value, external_text = _progress_circle_values(component)

    ring_stack_id = f"{component.component_id}_ring_stack"
    ring_id = f"{component.component_id}_ring"
    icon_id = f"{component.component_id}_icon"
    external_text_id = f"{component.component_id}_external_text"
    icon_props: dict[str, Any] = {"src": component.props["icon"]}
    if "fillColor" in component.props:
        icon_props["fillColor"] = component.props["fillColor"]
    return [
        _visual_row(
            component.component_id,
            "ProgressCircle",
            "root",
            size=size,
            props={
                "width": width,
                "height": height,
                "accessibility": copy.deepcopy(component.props["accessibility"]),
            },
            children=(ring_stack_id, external_text_id),
        ),
        _visual_row(
            ring_stack_id,
            "ProgressCircle",
            "ringStack",
            size=size,
            props={"width": ring_diameter, "height": ring_diameter},
            children=(ring_id, icon_id),
        ),
        _visual_row(
            ring_id,
            "ProgressCircle",
            "ring",
            size=size,
            props={
                "width": ring_diameter,
                "height": ring_diameter,
                "value": progress_value,
                "total": 100,
                "strokeWidth": stroke_width,
                "color": component.props["color"],
                "backgroundColor": component.props["backgroundColor"],
            },
        ),
        _visual_row(
            icon_id,
            "ProgressCircle",
            "icon",
            size=size,
            props=icon_props,
        ),
        _visual_row(
            external_text_id,
            "ProgressCircle",
            "externalText",
            size=size,
            props={
                "content": external_text,
                "width": width,
                "fontColor": component.props["fontColor"],
            },
        ),
    ]


def _validate_progress_circle_accessibility(component: ComponentRow) -> None:
    accessibility = component.props.get("accessibility")
    allowed = {"label", "description"}
    if not isinstance(accessibility, dict) or not set(accessibility).issubset(allowed):
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircle.accessibility only allows "
            "label and description."
        )
    label = accessibility.get("label")
    if not isinstance(label, str) or not label.strip():
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircle.accessibility.label must be non-empty."
        )
    description = accessibility.get("description")
    if description is not None and (
        not isinstance(description, str) or not description.strip()
    ):
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircle.accessibility.description "
            "must be non-empty."
        )


def _progress_circle_values(component: ComponentRow) -> tuple[Any, Any]:
    value = component.props.get("externalText")
    if _is_path_binding(value):
        path = value.get("path")
        return copy.deepcopy(value), f"{{{{ ${{{path}}} + '%' }}}}"
    if isinstance(value, bool):
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircle.externalText must be 0 to 100."
        )
    if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100:
        visible = str(int(value)) if float(value).is_integer() else str(value)
        return value, f"{visible}%"
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)%\s*", value)
        if match is not None:
            numeric = float(match.group(1))
            if 0 <= numeric <= 100:
                return numeric, value.strip()
    raise CompactDslConversionError(
        f"{component.component_id}: ProgressCircle.externalText must be a number, "
        "numeric percentage, or numeric PathBinding from 0 to 100."
    )


def _expand_pill_button(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("PillButton requires a 2x2 or 2x4 card.")
    allowed = {
        "label",
        "icon",
        "actionInk",
        "actionSurface",
        "fontSize",
        "fontWeight",
        "onClick",
        "width",
    }
    _validate_high_level_props(
        component,
        required={"label", "actionInk", "actionSurface", "onClick"},
        allowed=allowed,
    )
    label = component.props.get("label")
    if not isinstance(label, str) or not label.strip():
        raise CompactDslConversionError(
            f"{component.component_id}: PillButton.label must be non-empty text."
        )
    _validate_optional_icon(component)
    _validate_high_level_on_click(component)
    _require_color(component, "actionInk")
    _require_color(component, "actionSurface")
    font_size = component.props.get("fontSize")
    if font_size is not None and font_size != 14:
        raise CompactDslConversionError(
            f"{component.component_id}: PillButton.fontSize must be 14 when provided."
        )
    font_weight = component.props.get("fontWeight")
    if font_weight is not None and font_weight not in {400, 500}:
        raise CompactDslConversionError(
            f"{component.component_id}: PillButton.fontWeight must be 400 or 500."
        )
    width = component.props.get("width")
    allowed_widths = {"2x2": {"matchParent", 126}, "2x4": {"matchParent", 116, 132}}
    if width is not None and width not in allowed_widths[size]:
        raise CompactDslConversionError(
            f"{component.component_id}: PillButton.width is invalid for {size}."
        )

    _, recipe_props = _visual_recipe_part_for_converter(
        "PillButton",
        "root",
        size=size,
    )
    props = {**recipe_props, **copy.deepcopy(component.props)}
    root_props = {
        name: copy.deepcopy(value)
        for name, value in props.items()
        if name
        in {
            "width",
            "height",
            "borderRadius",
            "padding",
            "flexShrink",
            "layoutWeight",
            "margin",
        }
    }
    root_props["backgroundColor"] = props["actionSurface"]
    root_props["onClick"] = copy.deepcopy(props["onClick"])
    icon = props.get("icon")
    if not isinstance(icon, str):
        root_props.update(
            {
                "label": props["label"],
                "fontColor": props["actionInk"],
                "fontSize": props.get("fontSize", 14),
                "fontWeight": props.get("fontWeight", 500),
                "textAlign": "center",
            }
        )
        return [ComponentRow(component.component_id, "Button", root_props)]

    icon_id = f"{component.component_id}_icon"
    text_id = f"{component.component_id}_text"
    root_props.update(
        {
            "itemMargin": 8,
            "justifyContent": "center",
            "alignItems": "center",
        }
    )
    return [
        ComponentRow(
            component.component_id,
            "Row",
            root_props,
            (icon_id, text_id),
        ),
        ComponentRow(
            icon_id,
            "Image",
            {
                "src": icon,
                "width": 20,
                "height": 20,
                "objectFit": "contain",
                "flexShrink": 0,
                "fillColor": props["actionInk"],
            },
        ),
        ComponentRow(
            text_id,
            "Text",
            {
                "content": props["label"],
                "maxWidth": 96,
                "height": props.get("height", 36),
                "fontSize": props.get("fontSize", 14),
                "fontWeight": props.get("fontWeight", 500),
                "fontColor": props["actionInk"],
                "textAlign": "center",
                "maxLines": 1,
                "flexShrink": 0,
            },
        ),
    ]


def _expand_circle_button(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size != "2x2":
        raise CompactDslConversionError("CircleButton requires a 2x2 card.")
    allowed = {
        "icon",
        "accessibility",
        "actionInk",
        "actionSurface",
        "onClick",
    }
    _validate_high_level_props(
        component,
        required={"icon", "accessibility", "actionInk", "actionSurface", "onClick"},
        allowed=allowed,
    )
    _validate_optional_icon(component)
    _validate_high_level_on_click(component)
    _require_color(component, "actionInk")
    _require_color(component, "actionSurface")
    accessibility = component.props.get("accessibility")
    allowed_accessibility = {"label", "description"}
    if not isinstance(accessibility, dict) or not set(accessibility).issubset(
        allowed_accessibility
    ):
        raise CompactDslConversionError(
            f"{component.component_id}: CircleButton.accessibility only allows "
            "label and description."
        )
    label = accessibility.get("label") if isinstance(accessibility, dict) else None
    if not isinstance(label, str) or not label.strip():
        raise CompactDslConversionError(
            f"{component.component_id}: CircleButton.accessibility.label must be non-empty."
        )
    description = accessibility.get("description")
    if description is not None and (not isinstance(description, str) or not description.strip()):
        raise CompactDslConversionError(
            f"{component.component_id}: CircleButton.accessibility.description must be non-empty."
        )

    _, recipe_props = _visual_recipe_part_for_converter(
        "CircleButton",
        "root",
        size=size,
    )
    props = {**recipe_props, **copy.deepcopy(component.props)}
    icon_id = f"{component.component_id}_icon"
    root_props = {
        name: copy.deepcopy(value)
        for name, value in props.items()
        if name
        in {
            "width",
            "height",
            "borderRadius",
            "padding",
            "flexShrink",
            "layoutWeight",
            "margin",
        }
    }
    root_props.update(
        {
            "backgroundColor": props["actionSurface"],
            "alignContent": "center",
            "clip": True,
            "onClick": copy.deepcopy(props["onClick"]),
            "accessibility": copy.deepcopy(props["accessibility"]),
        }
    )
    return [
        ComponentRow(component.component_id, "Stack", root_props, (icon_id,)),
        ComponentRow(
            icon_id,
            "Image",
            {
                "src": props["icon"],
                "width": 20,
                "height": 20,
                "objectFit": "contain",
                "flexShrink": 0,
                "fillColor": props["actionInk"],
            },
        ),
    ]


def _expand_emphasized_data(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("EmphasizedData requires a 2x2 or 2x4 card.")
    allowed = {"value", "unit", "fontColor"}
    _validate_high_level_props(
        component,
        required={"value", "fontColor"},
        allowed=allowed,
    )
    _require_text_value(component, "value")
    _require_color(component, "fontColor")
    unit = component.props.get("unit")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise CompactDslConversionError(
            f"{component.component_id}: EmphasizedData.unit must be non-empty text."
        )

    value_id = f"{component.component_id}_value"
    children = [value_id]
    rows = [
        _visual_row(
            component.component_id,
            "EmphasizedData",
            "root",
            size=size,
            props={"itemMargin": 2 if unit else 0},
        ),
        _visual_row(
            value_id,
            "EmphasizedData",
            "value",
            size=size,
            props={
                "content": copy.deepcopy(component.props["value"]),
                "fontColor": component.props["fontColor"],
            },
        ),
    ]
    if unit:
        unit_id = f"{component.component_id}_unit"
        children.append(unit_id)
        rows.append(
            _visual_row(
                unit_id,
                "EmphasizedData",
                "unit",
                size=size,
                props={
                    "content": unit,
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    rows[0] = ComponentRow(
        rows[0].component_id,
        rows[0].component_type,
        rows[0].props,
        tuple(children),
    )
    return rows


def _expand_info_block(component: ComponentRow, size: str) -> list[ComponentRow]:
    allowed = {
        "variant",
        "primaryText",
        "secondaryText",
        "fontColor",
        "backgroundColor",
        "icon",
        "fillColor",
    }
    _validate_high_level_props(
        component,
        required={
            "primaryText",
            "secondaryText",
            "fontColor",
            "backgroundColor",
        },
        allowed=allowed,
    )
    _require_text_value(component, "primaryText")
    _require_text_value(component, "secondaryText")
    _require_color(component, "fontColor")
    _require_color(component, "backgroundColor")
    _validate_optional_icon(component)
    variant = component.props.get("variant")
    _info_block_profile(size, variant)
    icon = component.props.get("icon")
    copy_layout = {"layoutWeight": 1} if icon else {"width": "matchParent"}
    text_parent_id = f"{component.component_id}_text"
    icon_id = f"{component.component_id}_icon"
    primary_id = f"{component.component_id}_primary"
    secondary_id = f"{component.component_id}_secondary"
    children = [text_parent_id]
    if icon:
        children.append(icon_id)
    container_props: dict[str, Any] = {
        "backgroundColor": component.props["backgroundColor"],
    }
    root_part = "root" if icon else "rootNoVisual"
    rows = [
        _visual_row(
            component.component_id,
            "InfoBlock",
            root_part,
            size=size,
            props=container_props,
            children=tuple(children),
        ),
        _visual_row(
            text_parent_id,
            "InfoBlock",
            "copy",
            size=size,
            props=copy_layout,
            children=(primary_id, secondary_id),
        ),
    ]
    rows.extend(
        _info_block_text_rows(
            component,
            size,
            primary_id,
            secondary_id,
        )
    )
    if icon:
        image_props: dict[str, Any] = {
            "src": icon,
        }
        if "fillColor" in component.props:
            image_props["fillColor"] = component.props["fillColor"]
        rows.append(
            _visual_row(
                icon_id,
                "InfoBlock",
                "icon",
                size=size,
                props=image_props,
            )
        )
    return rows


def _info_block_profile(size: str, variant: Any) -> dict[str, Any]:
    if size == "2x2":
        if variant not in (None, "stacked"):
            raise CompactDslConversionError('2x2 InfoBlock.variant must be omitted or "stacked".')
        return _visual_recipe("InfoBlock", size=size)
    if size != "2x4" or variant not in {"slot", "aux", "small"}:
        raise CompactDslConversionError(
            '2x4 InfoBlock.variant must be "slot"; "aux" and "small" are legacy aliases.'
        )
    return _visual_recipe("InfoBlock", size=size)


def _info_block_text_rows(
    component: ComponentRow,
    size: str,
    primary_id: str,
    secondary_id: str,
) -> list[ComponentRow]:
    color = component.props["fontColor"]
    return [
        _visual_row(
            primary_id,
            "InfoBlock",
            "primary",
            size=size,
            props={
                "content": copy.deepcopy(component.props["primaryText"]),
                "fontColor": color,
            },
        ),
        _visual_row(
            secondary_id,
            "InfoBlock",
            "secondary",
            size=size,
            props={
                "content": copy.deepcopy(component.props["secondaryText"]),
                "fontColor": _color_with_alpha(color, 0.6),
            },
        ),
    ]


def _expand_progress_line_two(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size != "2x4":
        raise CompactDslConversionError("ProgressLine2 currently requires a 2x4 card.")
    allowed = {
        "value",
        "total",
        "displayValue",
        "unit",
        "fontColor",
        "color",
        "backgroundColor",
    }
    required = allowed - {"unit"}
    _validate_high_level_props(component, required=required, allowed=allowed)
    _require_text_value(component, "displayValue")
    unit = component.props.get("unit")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressLine2.unit must be non-empty text."
        )
    for name in ("fontColor", "color", "backgroundColor"):
        _require_color(component, name)
    total = component.props.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressLine2.total must be a positive number."
        )

    readout_id = f"{component.component_id}_readout"
    value_id = f"{component.component_id}_value"
    bar_id = f"{component.component_id}_bar"
    readout_children = [value_id]
    rows = [
        _visual_row(
            component.component_id,
            "ProgressLine2",
            "root",
            size=size,
            children=(readout_id, bar_id),
        ),
        _visual_row(
            readout_id,
            "ProgressLine2",
            "readout",
            size=size,
            props={"itemMargin": 2 if unit else 0},
            children=tuple(readout_children),
        ),
        _visual_row(
            value_id,
            "ProgressLine2",
            "value",
            size=size,
            props={
                "content": copy.deepcopy(component.props["displayValue"]),
                "fontColor": component.props["fontColor"],
            },
        ),
        _visual_row(
            bar_id,
            "ProgressLine2",
            "bar",
            size=size,
            props={
                "type": "linear",
                "value": copy.deepcopy(component.props["value"]),
                "total": component.props["total"],
                "color": component.props["color"],
                "backgroundColor": component.props["backgroundColor"],
            },
        ),
    ]
    if unit:
        unit_id = f"{component.component_id}_unit"
        readout_children.append(unit_id)
        rows[1] = ComponentRow(
            rows[1].component_id,
            rows[1].component_type,
            rows[1].props,
            tuple(readout_children),
        )
        rows.append(
            _visual_row(
                unit_id,
                "ProgressLine2",
                "unit",
                size=size,
                props={
                    "content": unit,
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    return rows


def _expand_table_text(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("TableText requires a 2x2 or 2x4 card.")
    items = _validate_item_component(component, minimum=2, maximum=3)
    rows: list[ComponentRow] = []
    children: list[str] = []
    for index, item in enumerate(items):
        row_id = f"{component.component_id}_row{index}"
        label_id = f"{row_id}_label"
        value_id = f"{row_id}_value"
        children.append(row_id)
        rows.extend(
            [
                _visual_row(
                    row_id,
                    "TableText",
                    "row",
                    size=size,
                    children=(label_id, value_id),
                ),
                _visual_row(
                    label_id,
                    "TableText",
                    "label",
                    size=size,
                    props={
                        "content": item["label"],
                        "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                    },
                ),
                _visual_row(
                    value_id,
                    "TableText",
                    "value",
                    size=size,
                    props={
                        "content": copy.deepcopy(item["value"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
            ]
        )
    recipe = _visual_recipe("TableText", size=size)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactDslConversionError("TableText visual recipe has invalid metrics.")
    item_margin = metrics.get("twoRowGap" if len(items) == 2 else "threeRowGap")
    root = _visual_row(
        component.component_id,
        "TableText",
        "root",
        size=size,
        props={"itemMargin": item_margin},
        children=tuple(children),
    )
    return [root, *rows]


def _expand_text_block(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size != "2x4":
        raise CompactDslConversionError("TextBlock requires a 2x4 card.")
    recipe = _visual_recipe("TextBlock", size=size)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactDslConversionError("TextBlock visual recipe has invalid metrics.")
    minimum = metrics.get("minimumItems")
    maximum = metrics.get("maximumItems")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise CompactDslConversionError("TextBlock visual recipe has invalid capacity.")
    items = _validate_item_component(component, minimum=minimum, maximum=maximum)
    children: list[str] = []
    rows: list[ComponentRow] = []
    for index, item in enumerate(items):
        item_id = f"{component.component_id}_item{index}"
        label_id = f"{item_id}_label"
        value_id = f"{item_id}_value"
        children.append(item_id)
        rows.extend(
            [
                _visual_row(
                    item_id,
                    "TextBlock",
                    "item",
                    size=size,
                    props={
                        "backgroundColor": component.props["backgroundColor"],
                    },
                    children=(label_id, value_id),
                ),
                _visual_row(
                    label_id,
                    "TextBlock",
                    "label",
                    size=size,
                    props={
                        "content": item["label"],
                        "fontColor": component.props["fontColor"],
                    },
                ),
                _visual_row(
                    value_id,
                    "TextBlock",
                    "value",
                    size=size,
                    props={
                        "content": copy.deepcopy(item["value"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
            ]
        )
    root = _visual_row(
        component.component_id,
        "TextBlock",
        "root",
        size=size,
        children=tuple(children),
    )
    return [root, *rows]


def _expand_card_button(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size != "2x4":
        raise CompactDslConversionError("CardButton requires a 2x4 card.")
    allowed = {
        "label",
        "onClick",
        "fontColor",
        "backgroundColor",
        "icon",
        "fillColor",
    }
    _validate_high_level_props(
        component,
        required={"label", "onClick", "fontColor", "backgroundColor"},
        allowed=allowed,
    )
    _require_text_value(component, "label")
    _require_color(component, "fontColor")
    _require_color(component, "backgroundColor")
    _validate_optional_icon(component)
    _validate_high_level_on_click(component)

    label_id = f"{component.component_id}_label"
    visual_id = f"{component.component_id}_visual"
    icon = component.props.get("icon")
    children = [label_id, visual_id]
    container_props: dict[str, Any] = {
        "backgroundColor": component.props["backgroundColor"],
        "onClick": copy.deepcopy(component.props["onClick"]),
    }
    rows = [
        _visual_row(
            component.component_id,
            "CardButton",
            "root",
            size=size,
            props=container_props,
            children=tuple(children),
        ),
        _visual_row(
            label_id,
            "CardButton",
            "label",
            size=size,
            props={
                "content": copy.deepcopy(component.props["label"]),
                "fontColor": component.props["fontColor"],
            },
        ),
    ]
    if icon:
        image_props: dict[str, Any] = {
            "src": icon,
        }
        if "fillColor" in component.props:
            image_props["fillColor"] = component.props["fillColor"]
        rows.append(
            _visual_row(
                visual_id,
                "CardButton",
                "icon",
                size=size,
                props=image_props,
            )
        )
    else:
        foreground = component.props["fontColor"]
        placeholder_color = _color_with_alpha(foreground, 0.2)
        rows.append(
            _visual_row(
                visual_id,
                "CardButton",
                "placeholder",
                size=size,
                props={"backgroundColor": placeholder_color},
            )
        )
    return rows


def _expand_progress_circle_single(
    component: ComponentRow,
    size: str,
) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError(
            "ProgressCircleSingle requires a 2x2 or 2x4 card."
        )
    allowed = {
        "value",
        "total",
        "icon",
        "displayValue",
        "label",
        "secondaryLabel",
        "fontColor",
        "color",
        "backgroundColor",
    }
    required = allowed - {"secondaryLabel"}
    _validate_high_level_props(component, required=required, allowed=allowed)
    _require_text_value(component, "value")
    _require_text_value(component, "displayValue")
    if not isinstance(component.props.get("label"), str) or not component.props["label"].strip():
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircleSingle.label must be non-empty text."
        )
    total = component.props.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircleSingle.total must be a positive number."
        )
    _validate_optional_icon(component)
    secondary_label = component.props.get("secondaryLabel")
    if secondary_label is not None and not _is_display_value(secondary_label):
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircleSingle.secondaryLabel must be display text."
        )
    for name in ("fontColor", "color", "backgroundColor"):
        _require_color(component, name)

    ring_stack_id = f"{component.component_id}_ring_stack"
    ring_id = f"{component.component_id}_ring"
    icon_id = f"{component.component_id}_icon"
    labels_id = f"{component.component_id}_labels"
    label_id = f"{component.component_id}_label"
    display_id = f"{component.component_id}_display"
    secondary_id = f"{component.component_id}_secondary"
    if size == "2x2":
        variant = "twoByTwoWithSecondary" if secondary_label is not None else "twoByTwo"
    else:
        variant = "withSecondary" if secondary_label is not None else None
    label_children = [label_id, display_id]
    if secondary_label is not None:
        label_children.append(secondary_id)
    rows = [
        _visual_row(
            component.component_id,
            "ProgressCircleSingle",
            "root",
            size=size,
            variant=variant,
            children=(ring_stack_id, labels_id),
        ),
        _visual_row(
            ring_stack_id,
            "ProgressCircleSingle",
            "ringStack",
            size=size,
            variant=variant,
            children=(ring_id, icon_id),
        ),
        _visual_row(
            ring_id,
            "ProgressCircleSingle",
            "ring",
            size=size,
            variant=variant,
            props={
                "type": "ring",
                "value": copy.deepcopy(component.props["value"]),
                "total": total,
                "color": component.props["color"],
                "backgroundColor": component.props["backgroundColor"],
            },
        ),
        _visual_row(
            icon_id,
            "ProgressCircleSingle",
            "icon",
            size=size,
            variant=variant,
            props={
                "src": component.props["icon"],
                "fillColor": _color_with_alpha(component.props["fontColor"], 0.6),
            },
        ),
        _visual_row(
            labels_id,
            "ProgressCircleSingle",
            "labels",
            size=size,
            variant=variant,
            children=tuple(label_children),
        ),
        _visual_row(
            label_id,
            "ProgressCircleSingle",
            "label",
            size=size,
            variant=variant,
            props={
                "content": component.props["label"],
                "fontColor": component.props["fontColor"],
            },
        ),
        _visual_row(
            display_id,
            "ProgressCircleSingle",
            "display",
            size=size,
            variant=variant,
            props={
                "content": copy.deepcopy(component.props["displayValue"]),
                "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
            },
        ),
    ]
    if secondary_label is not None:
        rows.append(
            _visual_row(
                secondary_id,
                "ProgressCircleSingle",
                "secondary",
                size=size,
                variant=variant,
                props={
                    "content": copy.deepcopy(secondary_label),
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    return rows


def _expand_event_card(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("EventCard requires a 2x2 or 2x4 card.")
    allowed = {"title", "time", "location", "fontColor"}
    required = {"title", "time", "fontColor"}
    _validate_high_level_props(component, required=required, allowed=allowed)
    _require_text_value(component, "title")
    _require_text_value(component, "time")
    if "location" in component.props:
        _require_text_value(component, "location")
    _require_color(component, "fontColor")

    has_location = "location" in component.props
    variant = "withLocation" if has_location else "withoutLocation"
    recipe = _visual_recipe("EventCard", size=size, variant=variant)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactDslConversionError("EventCard visual recipe has invalid metrics.")
    event_height = metrics.get("height")
    line_height = metrics.get("lineHeight")
    if not isinstance(event_height, int) or not isinstance(line_height, int):
        raise CompactDslConversionError("EventCard visual recipe has invalid geometry.")
    rail_id = f"{component.component_id}_rail"
    dot_id = f"{rail_id}_dot"
    line_id = f"{rail_id}_line"
    texts_id = f"{component.component_id}_texts"
    title_id = f"{component.component_id}_title"
    time_id = f"{component.component_id}_time"
    text_children = [title_id, time_id]
    if has_location:
        text_children.append(f"{component.component_id}_location")
    rows = [
        _visual_row(
            component.component_id,
            "EventCard",
            "root",
            size=size,
            variant=variant,
            props={
                "height": event_height,
                "layoutWeight": 1,
            },
            children=(rail_id, texts_id),
        ),
        _visual_row(
            rail_id,
            "EventCard",
            "rail",
            size=size,
            variant=variant,
            props={
                "height": event_height,
                "clip": True,
            },
            children=(dot_id, line_id),
        ),
        _visual_row(
            dot_id,
            "EventCard",
            "dot",
            size=size,
            variant=variant,
            props={
                "borderColor": component.props["fontColor"],
                "backgroundColor": "#00FFFFFF",
                "alignContent": "center",
            },
        ),
        _visual_row(
            line_id,
            "EventCard",
            "line",
            size=size,
            variant=variant,
            props={
                "height": line_height,
                "color": _color_with_alpha(component.props["fontColor"], 0.6),
            },
        ),
        _visual_row(
            texts_id,
            "EventCard",
            "copy",
            size=size,
            variant=variant,
            props={
                "height": event_height,
            },
            children=tuple(text_children),
        ),
        _visual_row(
            title_id,
            "EventCard",
            "title",
            size=size,
            variant=variant,
            props={
                "content": copy.deepcopy(component.props["title"]),
                "fontColor": component.props["fontColor"],
            },
        ),
        _visual_row(
            time_id,
            "EventCard",
            "meta",
            size=size,
            variant=variant,
            props={
                "content": copy.deepcopy(component.props["time"]),
                "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
            },
        ),
    ]
    if has_location:
        rows.append(
            _visual_row(
                f"{component.component_id}_location",
                "EventCard",
                "meta",
                size=size,
                variant=variant,
                props={
                    "content": copy.deepcopy(component.props["location"]),
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    return rows


def _expand_data_display(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size != "2x2":
        raise CompactDslConversionError("DataDisplay currently requires a 2x2 card.")
    allowed = {"label", "value", "supportingText", "fontColor"}
    _validate_high_level_props(component, required=allowed, allowed=allowed)
    for name in ("label", "supportingText"):
        if not isinstance(component.props.get(name), str) or not component.props[name].strip():
            raise CompactDslConversionError(
                f"{component.component_id}: DataDisplay.{name} must be non-empty text."
            )
    _require_text_value(component, "value")
    _require_color(component, "fontColor")
    secondary_color = _color_with_alpha(component.props["fontColor"], 0.6)

    label_id = f"{component.component_id}_label"
    value_id = f"{component.component_id}_value"
    supporting_id = f"{component.component_id}_supporting"
    return [
        _visual_row(
            component.component_id,
            "DataDisplay",
            "root",
            size=size,
            children=(label_id, value_id, supporting_id),
        ),
        _visual_row(
            label_id,
            "DataDisplay",
            "label",
            size=size,
            props={
                "content": component.props["label"],
                "fontColor": secondary_color,
            },
        ),
        _visual_row(
            value_id,
            "DataDisplay",
            "value",
            size=size,
            props={
                "content": copy.deepcopy(component.props["value"]),
                "fontColor": component.props["fontColor"],
            },
        ),
        _visual_row(
            supporting_id,
            "DataDisplay",
            "supporting",
            size=size,
            props={
                "content": component.props["supportingText"],
                "fontColor": secondary_color,
            },
        ),
    ]


def _expand_top_text_bottom_value(
    component: ComponentRow,
    size: str,
) -> list[ComponentRow]:
    if size != "2x4":
        raise CompactDslConversionError("TopTextBottomValue currently requires a 2x4 card.")
    allowed = {"items", "fontColor", "dividerColor"}
    _validate_high_level_props(component, required=allowed, allowed=allowed)
    _require_color(component, "fontColor")
    _require_color(component, "dividerColor")
    items = _validate_top_text_bottom_value_items(component)

    children: list[str] = []
    rows: list[ComponentRow] = []
    for index, item in enumerate(items):
        item_id = f"{component.component_id}_item{index}"
        value_id = f"{item_id}_value"
        label_id = f"{item_id}_label"
        unit_id = f"{item_id}_unit"
        if index:
            divider_id = f"{component.component_id}_divider{index - 1}"
            children.append(divider_id)
            rows.append(
                _visual_row(
                    divider_id,
                    "TopTextBottomValue",
                    "divider",
                    size=size,
                    props={
                        "color": component.props["dividerColor"],
                    },
                )
            )
        children.append(item_id)
        rows.extend(
            [
                _visual_row(
                    item_id,
                    "TopTextBottomValue",
                    "item",
                    size=size,
                    children=(label_id, value_id, unit_id),
                ),
                _visual_row(
                    label_id,
                    "TopTextBottomValue",
                    "label",
                    size=size,
                    props={
                        "content": item["label"],
                        "fontColor": component.props["fontColor"],
                    },
                ),
                _visual_row(
                    value_id,
                    "TopTextBottomValue",
                    "value",
                    size=size,
                    props={
                        "content": copy.deepcopy(item["value"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
                _visual_row(
                    unit_id,
                    "TopTextBottomValue",
                    "unit",
                    size=size,
                    props={
                        "content": item["unit"],
                        "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                    },
                ),
            ]
        )
    root = _visual_row(
        component.component_id,
        "TopTextBottomValue",
        "root",
        size=size,
        children=tuple(children),
    )
    return [root, *rows]


def _expand_summary_list(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size != "2x4":
        raise CompactDslConversionError("SummaryList currently requires a 2x4 card.")
    allowed = {"items", "fontColor", "backgroundColor"}
    _validate_high_level_props(component, required=allowed, allowed=allowed)
    _require_color(component, "fontColor")
    _require_color(component, "backgroundColor")
    items = component.props.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= 3:
        raise CompactDslConversionError(
            f"{component.component_id}: SummaryList.items requires 2 to 3 entries."
        )
    for index, item in enumerate(items):
        if not _is_display_value(item):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] must be display text."
            )

    row_ids = [f"{component.component_id}_item{index}" for index in range(len(items))]
    rows = [
        ComponentRow(
            component.component_id,
            "Column",
            {
                "width": "matchParent",
                "height": 64 if len(items) == 2 else 102,
                "itemMargin": 8,
                "alignItems": "start",
            },
            tuple(row_ids),
        )
    ]
    for index, item in enumerate(items):
        text_id = f"{row_ids[index]}_text"
        rows.extend(
            [
                ComponentRow(
                    row_ids[index],
                    "Row",
                    {
                        "width": "matchParent",
                        "height": 28,
                        "padding": {"left": 12, "right": 12},
                        "borderRadius": 8,
                        "backgroundColor": component.props["backgroundColor"],
                        "alignItems": "center",
                    },
                    (text_id,),
                ),
                ComponentRow(
                    text_id,
                    "Text",
                    {
                        "content": copy.deepcopy(item),
                        "width": "matchParent",
                        "fontSize": 12,
                        "fontWeight": 400,
                        "fontColor": component.props["fontColor"],
                        "maxLines": 1,
                    },
                ),
            ]
        )
    return rows


def _is_display_value(value: Any) -> bool:
    valid_scalar = isinstance(value, (int, float)) and not isinstance(value, bool)
    valid_text = isinstance(value, str) and bool(value.strip())
    return valid_scalar or valid_text or _is_path_binding(value)


def _validate_label_value_items(
    component: ComponentRow,
    *,
    minimum: int,
    maximum: int,
) -> list[dict[str, Any]]:
    items = component.props.get("items")
    if not isinstance(items, list) or not minimum <= len(items) <= maximum:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.items requires "
            f"{minimum} to {maximum} entries."
        )
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {"label", "value"}:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] requires label/value only."
            )
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be non-empty text."
            )
        if not _is_display_value(item.get("value")):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].value must be display text."
            )
    return items


def _validate_top_text_bottom_value_items(
    component: ComponentRow,
) -> list[dict[str, Any]]:
    items = component.props.get("items")
    if not isinstance(items, list) or len(items) != 3:
        raise CompactDslConversionError(
            f"{component.component_id}: TopTextBottomValue.items requires 3 to 3 entries."
        )
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {"label", "value", "unit"}:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] requires label/value/unit only."
            )
        label = item.get("label")
        unit = item.get("unit")
        if not isinstance(label, str) or not label.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be non-empty text."
            )
        if not isinstance(unit, str) or not unit.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].unit must be non-empty text."
            )
        if not _is_display_value(item.get("value")):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].value must be display text."
            )
    return items


def _validate_high_level_props(
    component: ComponentRow,
    *,
    required: set[str],
    allowed: set[str],
) -> None:
    if component.children:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type} must not declare children."
        )
    missing = required - set(component.props)
    if missing:
        names = ", ".join(sorted(missing))
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type} requires {names}."
        )
    unknown = set(component.props) - allowed - _PLACEMENT_PROPS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type} does not allow {names}."
        )


def _require_text_value(component: ComponentRow, name: str) -> None:
    value = component.props.get(name)
    valid_scalar = isinstance(value, (int, float)) and not isinstance(value, bool)
    valid_text = isinstance(value, str) and bool(value.strip())
    if valid_scalar or valid_text or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component.component_id}: {component.component_type}.{name} must be display text."
    )


def _require_color(component: ComponentRow, name: str) -> None:
    value = component.props.get(name)
    if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{8}", value):
        return
    raise CompactDslConversionError(
        f"{component.component_id}: {component.component_type}.{name} must use #AARRGGBB."
    )


def _color_with_alpha(color: str, opacity: float) -> str:
    alpha = round(int(color[1:3], 16) * opacity)
    return f"#{alpha:02X}{color[3:]}"


def _validate_optional_icon(component: ComponentRow) -> None:
    icon = component.props.get("icon")
    if icon is not None and (not isinstance(icon, str) or not icon.strip()):
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.icon must be non-empty."
        )
    if "fillColor" in component.props and icon is None:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.fillColor requires icon."
        )
    if "fillColor" in component.props:
        _require_color(component, "fillColor")


def _validate_high_level_on_click(component: ComponentRow) -> None:
    handlers = component.props.get("onClick")
    if not isinstance(handlers, list) or len(handlers) != 1:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.onClick must contain "
            "exactly one handler."
        )
    handler = handlers[0]
    valid_handler = isinstance(handler, dict) and set(handler) == {"call", "args"}
    if not valid_handler:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.onClick handler must "
            "contain only call and args."
        )
    call = handler.get("call")
    args = handler.get("args")
    if not isinstance(call, str) or not call.strip() or not isinstance(args, dict):
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.onClick requires a "
            "non-empty call and object args."
        )


def _validate_item_component(
    component: ComponentRow,
    *,
    minimum: int,
    maximum: int,
) -> list[dict[str, Any]]:
    allowed = {"items", "fontColor", "backgroundColor"}
    required = {"items", "fontColor"}
    if component.component_type == "TextBlock":
        required.add("backgroundColor")
    _validate_high_level_props(component, required=required, allowed=allowed)
    _require_color(component, "fontColor")
    if "backgroundColor" in required:
        _require_color(component, "backgroundColor")
    items = component.props.get("items")
    if not isinstance(items, list) or not minimum <= len(items) <= maximum:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.items requires "
            f"{minimum} to {maximum} entries."
        )
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {"label", "value"}:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] requires label/value only."
            )
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be non-empty text."
            )
        value = item.get("value")
        valid_value = isinstance(value, (int, float)) and not isinstance(value, bool)
        valid_value = valid_value or (isinstance(value, str) and bool(value.strip()))
        valid_value = valid_value or _is_path_binding(value)
        if not valid_value:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].value must be display text."
            )
    return items


def _convert_card_header(component: ComponentRow, size: str = "2x2") -> list[dict[str, Any]]:
    props = component.props
    icon = props.get("icon")
    variant = "withIcon" if icon else None
    root_type, root_styles = _visual_recipe_part_for_converter(
        "CardHeader",
        "root",
        size=size,
        variant=variant,
    )
    title_type, title_styles = _visual_recipe_part_for_converter(
        "CardHeader",
        "title",
        size=size,
        variant=variant,
    )
    root_styles.pop("_visualRecipe", None)
    title_styles.pop("_visualRecipe", None)
    item_margin = root_styles.pop("itemMargin", 0)
    title_id = f"{component.component_id}_title"
    icon_id = f"{component.component_id}_icon"
    children = [title_id, icon_id] if icon else [title_id]
    row = {
        "id": component.component_id,
        "component": root_type,
        "children": children,
        "itemMargin": item_margin,
        "styles": root_styles,
    }
    title_styles["fontColor"] = props.get("fontColor")
    title = {
        "id": title_id,
        "component": title_type,
        "content": _convert_path_bindings(props.get("title")),
        "styles": title_styles,
    }
    for name in _PLACEMENT_PROPS:
        if name in props:
            row["styles"][name] = copy.deepcopy(props[name])
    converted = [row, title]
    if icon:
        icon_type, image_styles = _visual_recipe_part_for_converter(
            "CardHeader",
            "icon",
            size=size,
            variant=variant,
        )
        image_styles.pop("_visualRecipe", None)
        if "fillColor" in props:
            image_styles["fillColor"] = props.get("fillColor")
        converted.append(
            {
                "id": icon_id,
                "component": icon_type,
                "src": icon,
                "styles": image_styles,
            }
        )
    return converted


def _strip_optional_genui_fence(compact_dsl: str) -> str:
    text = compact_dsl.lstrip("\ufeff").strip()
    lines = text.splitlines()
    opening_index = _find_fence_opening(lines)
    if opening_index is None:
        return text

    closing_index = _find_fence_closing(lines, opening_index + 1)
    body_end = closing_index if closing_index is not None else len(lines)
    body = "\n".join(lines[opening_index + 1 : body_end]).strip()
    if "```" in body:
        raise CompactDslConversionError("Compact DSL must contain exactly one genui fence.")
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


def _repair_compact_json_rows(compact_dsl: str) -> str:
    body = _strip_optional_genui_fence(compact_dsl)
    rows = _repair_line_oriented_rows(body)
    if not rows:
        rows = _extract_top_level_array_rows(body)
    repaired_values: list[list[Any]] = []
    for line_number, row in enumerate(rows, 1):
        repaired = _remove_trailing_json_commas(row)
        value = _parse_json_line(repaired, line_number)
        repaired_values.append(value)
    repaired_values = _repair_compact_row_values(repaired_values)
    repaired_rows = [
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) for value in repaired_values
    ]
    return "\n".join(repaired_rows)


def _repair_line_oriented_rows(body: str) -> list[str]:
    rows: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        candidate = line
        if not candidate.startswith("["):
            repaired = _repair_missing_opening_array(candidate)
            if repaired is None:
                continue
            candidate = repaired
        candidate = _repair_unbalanced_json_brackets(candidate)
        try:
            value = json.loads(_remove_trailing_json_commas(candidate))
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        rows.append(candidate)
    return rows


def _repair_compact_row_values(rows: list[list[Any]]) -> list[list[Any]]:
    rows = _drop_duplicate_component_values(rows)
    referenced_children = _explicit_child_ids(rows)
    repaired_rows: list[list[Any]] = []
    for index, row in enumerate(rows):
        row = _repair_omitted_container_children(row, rows, index, referenced_children)
        repaired_rows.append(row)
    return repaired_rows


def _drop_duplicate_component_values(rows: list[list[Any]]) -> list[list[Any]]:
    seen_component_ids: set[str] = set()
    repaired_rows: list[list[Any]] = []
    for row in rows:
        component_id = _component_value_id(row)
        if component_id is None:
            repaired_rows.append(row)
            continue
        if component_id in seen_component_ids:
            continue
        seen_component_ids.add(component_id)
        repaired_rows.append(row)
    return repaired_rows


def _explicit_child_ids(rows: list[list[Any]]) -> set[str]:
    child_ids: set[str] = set()
    for row in rows:
        if not _is_component_value(row):
            continue
        if len(row) != 4 or not isinstance(row[3], list):
            continue
        child_ids.update(child for child in row[3] if isinstance(child, str))
    return child_ids


def _repair_omitted_container_children(
    row: list[Any],
    rows: list[list[Any]],
    index: int,
    referenced_children: set[str],
) -> list[Any]:
    if not _is_component_value(row):
        return row
    component_id = row[0]
    component_type = row[1]
    if len(row) != 3 or component_type not in _CONTAINER_TYPES:
        return row
    child_id = _find_next_likely_child_id(component_id, rows, index + 1)
    if child_id is None or child_id in referenced_children:
        return row
    referenced_children.add(child_id)
    return [row[0], row[1], row[2], [child_id]]


def _find_next_likely_child_id(
    component_id: str,
    rows: list[list[Any]],
    start_index: int,
) -> str | None:
    for row in rows[start_index:]:
        child_id = _component_value_id(row)
        if child_id is None:
            continue
        if child_id.startswith(component_id) and child_id != component_id:
            return child_id
        return None
    return None


def _is_component_value(row: list[Any]) -> bool:
    if len(row) not in {3, 4}:
        return False
    if not isinstance(row[0], str) or not isinstance(row[1], str):
        return False
    return isinstance(row[2], dict)


def _component_value_id(row: list[Any]) -> str | None:
    if _is_component_value(row):
        return row[0]
    return None


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
            raise CompactDslConversionError("Compact DSL contains mismatched JSON delimiters.")
        expected_closers.pop()
        if not expected_closers:
            rows.append("".join(current))
            current = []

    if expected_closers:
        if in_string:
            raise CompactDslConversionError("Compact DSL contains an unclosed JSON string.")
        current.extend(reversed(expected_closers))
        rows.append("".join(current))
    if current:
        repaired_row = _repair_missing_opening_array("".join(current))
        if repaired_row is not None:
            rows.append(repaired_row)
    repaired_outside = _repair_missing_opening_array("".join(outside))
    if repaired_outside is not None:
        rows.append(repaired_outside)

    if not rows:
        raise CompactDslConversionError("Compact DSL output is empty.")
    return rows


def _repair_missing_opening_array(text: str) -> str | None:
    candidate = text.strip()
    if not candidate or candidate.startswith("["):
        return None
    if not candidate.startswith('"'):
        return None
    return _repair_unbalanced_json_brackets(f"[{candidate}")


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
    return _canonicalize_component_order(rows)


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
    unreachable_ids = sorted(set(components_by_id) - visited)
    if unreachable_ids:
        unreachable_text = ", ".join(unreachable_ids)
        raise CompactDslConversionError(
            "Component rows must form one tree rooted at root. "
            f"Unreachable component(s): {unreachable_text}. "
            "Attach each component to a reachable parent's children list."
        )
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
    original_line = line
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        line = _repair_unbalanced_json_brackets(original_line)
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            raise CompactDslConversionError(
                f"Compact DSL line {line_number} is invalid JSON: {exc.msg}."
            ) from exc
    if not isinstance(value, list):
        raise CompactDslConversionError(f"Compact DSL line {line_number} must be a JSON array.")
    return value


def _repair_unbalanced_json_brackets(text: str) -> str:
    output: list[str] = []
    expected_closers: list[str] = []
    in_string = False
    escaped = False

    for char in text.strip():
        output.append(char)
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
        if char in {"]", "}"} and expected_closers and char == expected_closers[-1]:
            expected_closers.pop()

    if in_string:
        output.append('"')
    output.extend(reversed(expected_closers))
    return "".join(output)


def _parse_row(value: list[Any], line_number: int) -> CompactRow:
    if _looks_like_data_row(value):
        path = value[0]
        _decode_json_pointer(path)
        return DataRow(path=path, value=copy.deepcopy(value[1]))
    if _looks_like_data_def_row(value):
        props = value[2]
        path = props.get("path", "/")
        _decode_json_pointer(path)
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
    component_id, component_type, props = _parse_component_header(
        component_id,
        component_type,
        props,
        line_number,
    )
    if "_visualRecipe" in props:
        raise CompactDslConversionError("_visualRecipe is reserved for internal expansion.")
    children = _parse_children(value, component_id, component_type)
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
        _repair_progress_alias_props(
            repaired_props,
            default_design="progress-ring-primary",
        )
    _repair_on_click_aliases(repaired_props)
    return repaired_type, repaired_props


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


def _parse_component_header(
    component_id: Any,
    component_type: Any,
    props: Any,
    line_number: int,
) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(component_id, str) or not component_id:
        raise CompactDslConversionError(
            f"Compact DSL line {line_number} has an invalid component id."
        )
    if not isinstance(component_type, str) or not component_type:
        raise CompactDslConversionError(
            f"{component_id}: component type must be a non-empty string."
        )
    if component_type not in COMPACT_INPUT_COMPONENT_TYPES:
        raise CompactDslConversionError(
            f"{component_id}: unsupported component type {component_type}."
        )
    if not isinstance(props, dict):
        raise CompactDslConversionError(f"{component_id}: component props must be an object.")
    return component_id, component_type, props


def _parse_children(
    value: list[Any],
    component_id: str,
    component_type: str,
) -> tuple[str, ...]:
    if len(value) != 4:
        return ()
    if not isinstance(value[3], list):
        return ()

    children: list[str] = []
    for child in value[3]:
        if isinstance(child, str) and child:
            children.append(child)
    return tuple(dict.fromkeys(children))


def _drop_empty_image_components(rows: list[CompactRow]) -> list[CompactRow]:
    empty_image_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        if _is_empty_image_component(row.component_type, row.props):
            empty_image_ids.add(row.component_id)
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


def _is_path_binding(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"path"}:
        return False
    path = value.get("path")
    return isinstance(path, str) and path.startswith("/")


def _is_simple_a2ui_binding_expression(value: str) -> bool:
    match = _A2UI_BINDING_EXPRESSION_PATTERN.fullmatch(value.strip())
    if match is None:
        return False
    parts = [part.strip() for part in match.group("body").split("+")]
    if not parts:
        return False

    has_binding = False
    for part in parts:
        if not part:
            return False
        path_match = _A2UI_BINDING_PATH_PATTERN.fullmatch(part)
        if path_match is not None:
            _decode_json_pointer(path_match.group("path"))
            has_binding = True
            continue
        if not _is_quoted_literal(part):
            return False
    return has_binding


def _is_quoted_literal(value: str) -> bool:
    if len(value) < 2 or value[0] not in {"'", '"'}:
        return False
    quote = value[0]
    if value[-1] != quote:
        return False
    escaped = False
    for char in value[1:-1]:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == quote:
            return False
    return not escaped


def _split_component_rows(
    rows: list[CompactRow],
) -> tuple[list[ComponentRow], list[DataRow]]:
    components: list[ComponentRow] = []
    data_rows: list[DataRow] = []
    seen_component_ids: set[str] = set()
    root: ComponentRow | None = None

    for row in rows:
        if isinstance(row, DataRow):
            data_rows.append(row)
            continue
        if row.component_id in seen_component_ids:
            continue
        seen_component_ids.add(row.component_id)
        if row.component_id == "root":
            root = row
            continue
        components.append(row)

    if root is None:
        raise CompactDslConversionError(
            "The root component is missing; model output may be truncated."
        )
    return [root, *components], data_rows


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
        return explicit_props

    design_aliases = _DESIGN_ALIASES.get(component.component_type, {})
    design = design_aliases.get(design, design)
    component_designs = _COMPONENT_DESIGNS.get(component.component_type)
    if component_designs is None or design not in component_designs:
        return explicit_props
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
            resolved_items.append(_resolve_tokens(property_name, item, component_id))
        return resolved_items
    if not isinstance(value, str):
        return value
    if property_name in _COLOR_PROPERTIES:
        return _COLOR_TOKENS.get(value, value)
    return value


def _resolve_gradient_stops(
    stops: list[Any],
    component_id: str,
) -> list[Any]:
    resolved_stops: list[Any] = []
    for stop in stops:
        if not isinstance(stop, list) or len(stop) != 2:
            resolved_stops.append(copy.deepcopy(stop))
            continue
        color, position = stop
        if not isinstance(color, str):
            resolved_stops.append(copy.deepcopy(stop))
            continue
        if not isinstance(position, (int, float)):
            resolved_stops.append(copy.deepcopy(stop))
            continue
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
    card_size: str = "2x2",
) -> list[dict[str, Any]]:
    if component.component_type == "CardHeader":
        return _convert_card_header(component, card_size)
    return [
        _convert_component(
            component,
            hide_label=hide_label,
        )
    ]


def _convert_component(
    component: ComponentRow,
    *,
    hide_label: bool = False,
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
        if property_name in _COMMON_COMPACT_ONLY_PROPERTIES:
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
        if _is_supported_style_property(component.component_type, property_name):
            styles[property_name] = value

    if component.component_id == "root":
        _normalize_root_component(styles)
    if _is_icon_button_stack(component, hide_label):
        _normalize_icon_button_stack(styles)
    if component.component_type == "Text":
        _normalize_text_component(styles)
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


def _normalize_icon_button_stack(styles: dict[str, Any]) -> None:
    styles["alignContent"] = "center"
    styles["clip"] = True


def _normalize_text_component(styles: dict[str, Any]) -> None:
    styles.setdefault("maxLines", 1)
    styles.setdefault("textOverflow", "clip")


def _normalize_root_component(styles: dict[str, Any]) -> None:
    styles["width"] = "matchParent"
    styles["height"] = "matchParent"
    if not any(name in styles for name in ("linearGradient", "backgroundColor", "backgroundImage")):
        styles["backgroundColor"] = _DEFAULT_ROOT_BACKGROUND


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
    if property_name == "itemMargin" and component.component_type in {"Row", "Column"}:
        converted["itemMargin"] = value
        return True
    return False


def _is_supported_style_property(component_type: str, property_name: str) -> bool:
    if property_name in _COMMON_STYLE_PROPERTIES:
        return True
    style_properties = _COMPONENT_STYLE_PROPERTIES.get(component_type, frozenset())
    return property_name in style_properties


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


def _build_data_model(data_rows: list[DataRow]) -> dict[str, Any]:
    if not data_rows:
        return {"data": {}}

    root: dict[str, Any] = {}
    data_values: dict[str, Any] = {}
    for row in data_rows:
        data_values[row.path] = copy.deepcopy(row.value)
        try:
            _set_json_pointer(root, row.path, copy.deepcopy(row.value))
        except CompactDslConversionError:
            continue
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
        return
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
        child = expected_type()
        current[token] = child
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
        child = expected_type()
        current[array_index] = child
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
    return copy.deepcopy(incoming)


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


def _component_binding_paths(
    components: list[ComponentRow],
) -> list[str]:
    paths: list[str] = []
    for component in components:
        _collect_binding_paths(component.props, paths)
    return list(dict.fromkeys(paths))


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
        index = int(token)
        if index < len(current):
            return current[index]
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


def _candidate_component_asset_source(component: ComponentRow) -> str | None:
    if component.component_type == "Image":
        source = component.props.get("src")
    elif component.component_type == "CardHeader":
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
    return {"call": call, "args": copy.deepcopy(args)}


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
                replacements[key] = copy.deepcopy(matched)
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
        candidate for candidate in allowed_handlers if candidate.get("call") == call
    ]
    for candidate in same_call_handlers:
        candidate_args = candidate.get("args")
        if isinstance(candidate_args, dict) and _event_args_match(args, candidate_args):
            return candidate
    return None


def _event_args_match(
    model_args: dict[str, Any],
    candidate_args: dict[str, Any],
) -> bool:
    if _dict_subset(model_args, candidate_args):
        return True
    return _dict_subset(candidate_args, model_args)


def _dict_subset(left: dict[str, Any], right: dict[str, Any]) -> bool:
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
    if isinstance(value, str):
        _collect_a2ui_expression_paths(value, paths)
        return
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


def _collect_a2ui_expression_paths(value: str, paths: list[str]) -> None:
    if not _is_simple_a2ui_binding_expression(value):
        return
    for match in _A2UI_BINDING_PATH_PATTERN.finditer(value):
        paths.append(match.group("path"))


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
    if isinstance(value, str):
        return _replace_a2ui_expression_paths(value, path_replacements)
    return copy.deepcopy(value)


def _replace_a2ui_expression_paths(
    value: str,
    path_replacements: dict[str, str],
) -> str:
    if not path_replacements or not _is_simple_a2ui_binding_expression(value):
        return value

    def replace_match(match: re.Match[str]) -> str:
        path = match.group("path")
        return "${" + path_replacements.get(path, path) + "}"

    return _A2UI_BINDING_PATH_PATTERN.sub(replace_match, value)


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
        raise CompactDslConversionError(f'Compact DSL path "{path}" is not a JSON Pointer.')
    tokens: list[str] = []
    for raw_token in path[1:].split("/"):
        tokens.append(raw_token.replace("~1", "/").replace("~0", "~"))
    return tokens


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
        serialized_rows.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(serialized_rows)


def main() -> int:
    args = _parse_args()
    source = sys.stdin.read() if args.stdin else Path(args.input).read_text(encoding="utf-8")
    output = convert_compact_dsl_to_a2ui(
        source,
        size=args.size,
        protocol_profile={"version": args.version},
        theme=args.theme,
        surface_id=args.surface_id,
    )
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        return 0
    print(output)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Design Compact DSL text file")
    parser.add_argument("-o", "--output", help="A2UI NDJSON output file")
    parser.add_argument("--stdin", action="store_true", help="read Design Compact DSL from stdin")
    parser.add_argument("--size", default="")
    parser.add_argument("--surface-id", default="surface_card")
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--version", default="v0.9")
    args = parser.parse_args()
    if not args.stdin and not args.input:
        parser.error("input file is required unless --stdin is used")
    return args


if __name__ == "__main__":
    raise SystemExit(main())
