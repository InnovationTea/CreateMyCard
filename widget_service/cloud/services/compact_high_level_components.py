# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""高阶组件校验、Recipe 展开与共享行/绑定辅助；不依赖转换入口。"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass
from typing import Any

from services.compact_component_runtime import (
    CompactComponentRuntimeError,
    component_visual_recipe,
    visual_recipe_part,
)


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


def expand_high_level_component_rows(
    components: list[ComponentRow],
    *,
    size: str,
    data_model: dict[str, Any] | None = None,
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
        "DoubleLineTitle": _expand_double_line_title,
        "Badge": _expand_badge,
        "EmphasisText": _expand_emphasis_text,
        "SecondaryBody": _expand_secondary_body,
        "H_BarChart": _expand_h_bar_chart,
        "NumericRatioStack": _expand_numeric_ratio_stack,
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
        if expander is None:
            rows = [component]
        elif component.component_type in {
            "InfoBlock",
            "NumericRatioStack",
            "ProgressCircle",
            "ProgressLine2",
            "ProgressCircleSingle",
        }:
            rows = expander(component, size, data_model=data_model)
        else:
            rows = expander(component, size)
        if component.component_type == "CircleButton":
            _validate_circle_button_slot(parent)
        if expander is not None:
            rows[0] = _place_high_level_root(
                component, rows[0], parent
            )
        elif component.component_type == "SingleLineTitle":
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


def validate_single_line_title_layout(components: list[ComponentRow], *, size: str) -> None:
    headers = [item for item in components if item.component_type == "SingleLineTitle"]
    if not headers:
        return
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("SingleLineTitle requires a 2x2 or 2x4 card.")
    for header in headers:
        _validate_high_level_props(
            header,
            required={"title", "fontColor"},
            allowed={"title", "fontColor"},
        )
        _validate_single_line_title_props(header, components)


def _validate_single_line_title_props(header: ComponentRow, components: list[ComponentRow]) -> None:
    title = header.props.get("title")
    valid_title = isinstance(title, str) and bool(title.strip())
    if not valid_title and not _is_path_binding(title):
        raise CompactDslConversionError(
            "SingleLineTitle.title must be non-empty text or a path binding."
        )
    width = header.props.get("width")
    valid_width = width == "matchParent" or _is_positive_number(width)
    if width is not None and not valid_width:
        raise CompactDslConversionError(
            "SingleLineTitle.width must be matchParent or a positive number."
        )
    height = header.props.get("height")
    if height is not None and height != 20:
        raise CompactDslConversionError("SingleLineTitle.height must be 20 when provided.")
    color = header.props.get("fontColor")
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{8}", color):
        raise CompactDslConversionError("SingleLineTitle.fontColor must use #AARRGGBB.")
    generated_ids = {f"{header.component_id}_title"}
    if any(item.component_id in generated_ids for item in components):
        raise CompactDslConversionError("SingleLineTitle generated title id must not collide.")


def _is_positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _expand_double_line_title(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("DoubleLineTitle requires a 2x2 or 2x4 card.")
    allowed = {"title", "secondaryInfo", "fontColor"}
    _validate_high_level_props(component, required=allowed, allowed=allowed)
    _require_text_value(component, "title")
    _require_text_value(component, "secondaryInfo")
    _require_color(component, "fontColor")
    title_id = f"{component.component_id}_title"
    secondary_id = f"{component.component_id}_secondary"
    return [
        _visual_row(
            component.component_id,
            "DoubleLineTitle",
            "root",
            size=size,
            children=(title_id, secondary_id),
        ),
        _visual_row(
            title_id,
            "DoubleLineTitle",
            "title",
            size=size,
            props={
                "content": copy.deepcopy(component.props["title"]),
                "fontColor": component.props["fontColor"],
            },
        ),
        _visual_row(
            secondary_id,
            "DoubleLineTitle",
            "secondary",
            size=size,
            props={
                "content": copy.deepcopy(component.props["secondaryInfo"]),
                "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
            },
        ),
    ]


def _expand_badge(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("Badge requires a 2x2 or 2x4 card.")
    allowed = {"value", "fontColor", "backgroundColor"}
    _validate_high_level_props(component, required=allowed, allowed=allowed)
    _require_text_value(component, "value")
    _require_color(component, "fontColor")
    _require_color(component, "backgroundColor")
    return [
        _visual_row(
            component.component_id,
            "Badge",
            "root",
            size=size,
            props={
                "content": copy.deepcopy(component.props["value"]),
                "fontColor": component.props["fontColor"],
                "backgroundColor": component.props["backgroundColor"],
            },
        )
    ]


def _expand_emphasis_text(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("EmphasisText requires a 2x2 or 2x4 card.")
    allowed = {"mainText", "secondaryText", "fontColor"}
    _validate_high_level_props(
        component,
        required={"mainText", "fontColor"},
        allowed=allowed,
    )
    _require_text_value(component, "mainText")
    if "secondaryText" in component.props:
        _require_text_value(component, "secondaryText")
    _require_color(component, "fontColor")
    main_id = f"{component.component_id}_main"
    children = [main_id]
    rows = [
        _visual_row(
            main_id,
            "EmphasisText",
            "main",
            size=size,
            props={
                "content": copy.deepcopy(component.props["mainText"]),
                "fontColor": component.props["fontColor"],
            },
        )
    ]
    if "secondaryText" in component.props:
        secondary_id = f"{component.component_id}_secondary"
        children.append(secondary_id)
        rows.append(
            _visual_row(
                secondary_id,
                "EmphasisText",
                "secondary",
                size=size,
                props={
                    "content": copy.deepcopy(component.props["secondaryText"]),
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    root = _visual_row(
        component.component_id,
        "EmphasisText",
        "root",
        size=size,
        children=tuple(children),
    )
    return [root, *rows]


def _secondary_body_items(component: ComponentRow) -> list[dict[str, Any]]:
    allowed = {"items", "role", "columns", "separator", "fontColor"}
    _validate_high_level_props(
        component,
        required={"items", "fontColor"},
        allowed=allowed,
    )
    _require_color(component, "fontColor")
    items = component.props.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 4:
        raise CompactDslConversionError(
            f"{component.component_id}: SecondaryBody.items requires 1 to 4 entries."
        )
    role = component.props.get("role")
    if role is None:
        if len(items) == 1:
            raise CompactDslConversionError(
                f"{component.component_id}: single-item SecondaryBody requires role."
            )
        role = "supporting"
    if role not in {"body", "metadata", "supporting"}:
        raise CompactDslConversionError(
            f"{component.component_id}: SecondaryBody.role must be body, metadata, or supporting."
        )
    if role in {"body", "metadata"} and len(items) != 1:
        raise CompactDslConversionError(
            f"{component.component_id}: SecondaryBody role {role} requires exactly one item."
        )
    columns = component.props.get("columns", 2)
    if isinstance(columns, bool) or not isinstance(columns, int) or columns not in {1, 2}:
        raise CompactDslConversionError(
            f"{component.component_id}: SecondaryBody.columns must be 1 or 2."
        )
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not set(item) <= {"label", "value", "maxLines"}:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] allows label/value/maxLines only."
            )
        if "value" not in item or not _is_display_value(item.get("value")):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].value must be display text."
            )
        label = item.get("label")
        if label is not None and (not isinstance(label, str) or not label.strip()):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be non-empty text."
            )
        if role == "body" and label is not None:
            raise CompactDslConversionError(
                f"{component.component_id}: body SecondaryBody does not accept item labels."
            )
        max_lines = item.get("maxLines", 1)
        valid_max_lines = (
            isinstance(max_lines, int)
            and not isinstance(max_lines, bool)
            and max_lines in {1, 2}
        )
        if not valid_max_lines:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].maxLines must be 1 or 2."
            )
    separator = component.props.get("separator", " ｜ ")
    if not isinstance(separator, str) or not separator:
        raise CompactDslConversionError(
            f"{component.component_id}: SecondaryBody.separator must be non-empty text."
        )
    return items


def _secondary_body_variant(component: ComponentRow, items: list[dict[str, Any]]) -> str | None:
    role = component.props.get("role", "supporting")
    if role == "body":
        return "bodyMultiline" if items[0].get("maxLines", 1) == 2 else "body"
    if role == "metadata":
        return "metadata"
    if len(items) > 2:
        return "multiline"
    return None


def _expand_secondary_body(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("SecondaryBody requires a 2x2 or 2x4 card.")
    items = _secondary_body_items(component)
    variant = _secondary_body_variant(component, items)
    recipe = _visual_recipe("SecondaryBody", size=size, variant=variant)
    text_styles = recipe["parts"]["text"]["styles"]
    line_height = text_styles["height"] / text_styles.get("maxLines", 1)
    columns = component.props.get("columns", 2)
    rows: list[ComponentRow] = []
    root_children: list[str] = []
    separator = component.props.get("separator", " ｜ ")
    for row_index, start in enumerate(range(0, len(items), columns)):
        row_id = f"{component.component_id}_row{row_index}"
        root_children.append(row_id)
        row_children: list[str] = []
        row_items = items[start:start + columns]
        row_height = line_height * max(item.get("maxLines", 1) for item in row_items)
        for item_index, item in enumerate(row_items, start=start):
            max_lines = item.get("maxLines", 1)
            item_height = line_height * max_lines
            if row_children:
                separator_id = f"{row_id}_separator"
                row_children.append(separator_id)
                rows.append(
                    _visual_row(
                        separator_id,
                        "SecondaryBody",
                        "separator",
                        size=size,
                        variant=variant,
                        props={
                            "content": separator,
                            "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                        },
                    )
                )
            item_id = f"{component.component_id}_item{item_index}"
            row_children.append(item_id)
            text_children: list[str] = []
            label = item.get("label")
            if label is not None:
                label_id = f"{item_id}_label"
                text_children.append(label_id)
                rows.append(
                    _visual_row(
                        label_id,
                        "SecondaryBody",
                        "text",
                        size=size,
                        variant=variant,
                        props={
                            "content": label, "fontColor": component.props["fontColor"],
                            "height": line_height, "maxLines": 1, "flexShrink": 0,
                        },
                    )
                )
            value_id = f"{item_id}_value"
            text_children.append(value_id)
            rows.append(
                _visual_row(
                    value_id,
                    "SecondaryBody",
                    "text",
                    size=size,
                    variant=variant,
                    props={
                        "content": copy.deepcopy(item["value"]),
                        "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                        "height": item_height,
                        "maxLines": max_lines,
                        "layoutWeight": 1,
                    },
                )
            )
            rows.append(
                _visual_row(
                    item_id,
                    "SecondaryBody",
                    "item",
                    size=size,
                    variant=variant,
                    props={"layoutWeight": 1, "height": item_height, "alignItems": "start"},
                    children=tuple(text_children),
                )
            )
        rows.append(
            _visual_row(
                row_id,
                "SecondaryBody",
                "row",
                size=size,
                variant=variant,
                props={"height": row_height, "alignItems": "start"},
                children=tuple(row_children),
            )
        )
    root = _visual_row(
        component.component_id,
        "SecondaryBody",
        "root",
        size=size,
        variant=variant,
        children=tuple(root_children),
    )
    return [root, *rows]


def _h_bar_chart_items(component: ComponentRow) -> list[dict[str, Any]]:
    allowed = {"items", "fontColor", "barColor", "trackColor"}
    _validate_high_level_props(component, required=allowed, allowed=allowed)
    for name in ("fontColor", "barColor", "trackColor"):
        _require_color(component, name)
    items = component.props.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= 3:
        raise CompactDslConversionError(
            f"{component.component_id}: H_BarChart.items requires 2 to 3 entries."
        )
    for index, item in enumerate(items):
        required = {"label", "valueUnit", "percent"}
        if not isinstance(item, dict) or set(item) != required:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] requires label/valueUnit/percent only."
            )
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be non-empty text."
            )
        if not _is_display_value(item.get("valueUnit")):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].valueUnit must be display text."
            )
        percent = item.get("percent")
        valid_percent = isinstance(percent, (int, float)) and not isinstance(percent, bool)
        if not valid_percent or not math.isfinite(percent) or not 0 <= percent <= 100:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].percent must be between 0 and 100."
            )
    return items


def _expand_h_bar_chart(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("H_BarChart requires a 2x2 or 2x4 card.")
    items = _h_bar_chart_items(component)
    variant = "threeItems" if len(items) == 3 else None
    children: list[str] = []
    rows: list[ComponentRow] = []
    for index, item in enumerate(items):
        item_id = f"{component.component_id}_item{index}"
        meta_id = f"{item_id}_meta"
        label_id = f"{item_id}_label"
        value_id = f"{item_id}_value"
        bar_id = f"{item_id}_bar"
        children.append(item_id)
        rows.extend(
            [
                _visual_row(
                    item_id,
                    "H_BarChart",
                    "item",
                    size=size,
                    variant=variant,
                    children=(meta_id, bar_id),
                ),
                _visual_row(
                    meta_id,
                    "H_BarChart",
                    "meta",
                    size=size,
                    variant=variant,
                    children=(label_id, value_id),
                ),
                _visual_row(
                    label_id,
                    "H_BarChart",
                    "label",
                    size=size,
                    variant=variant,
                    props={"content": item["label"], "fontColor": component.props["fontColor"]},
                ),
                _visual_row(
                    value_id,
                    "H_BarChart",
                    "value",
                    size=size,
                    variant=variant,
                    props={
                        "content": copy.deepcopy(item["valueUnit"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
                _visual_row(
                    bar_id,
                    "H_BarChart",
                    "bar",
                    size=size,
                    variant=variant,
                    props={
                        "type": "linear",
                        "value": item["percent"],
                        "total": 100,
                        "color": component.props["barColor"],
                        "backgroundColor": component.props["trackColor"],
                    },
                ),
            ]
        )
    root = _visual_row(
        component.component_id,
        "H_BarChart",
        "root",
        size=size,
        variant=variant,
        children=tuple(children),
    )
    return [root, *rows]


def _numeric_ratio_items(component: ComponentRow) -> list[dict[str, Any]]:
    allowed = {"items", "direction", "fontColor", "fillColor"}
    _validate_high_level_props(
        component,
        required={"items", "fontColor", "fillColor"},
        allowed=allowed,
    )
    _require_color(component, "fontColor")
    _require_color(component, "fillColor")
    direction = component.props.get("direction", "column")
    if direction not in {"row", "column"}:
        raise CompactDslConversionError(
            f"{component.component_id}: NumericRatioStack.direction must be row or column."
        )
    items = component.props.get("items")
    if not isinstance(items, list) or len(items) != 3:
        raise CompactDslConversionError(
            f"{component.component_id}: NumericRatioStack.items requires exactly 3 entries."
        )
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not {"icon", "value"} <= set(item):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] requires icon and value."
            )
        if not set(item) <= {"icon", "value", "unit"}:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] allows icon/value/unit only."
            )
        icon = item.get("icon")
        if not isinstance(icon, str) or not icon.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].icon must be non-empty."
            )
        if not _is_display_value(item.get("value")):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].value must be display text."
            )
        unit = item.get("unit")
        if unit is not None and (not isinstance(unit, str) or not unit.strip()):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].unit must be non-empty text."
            )
    return items


def _expand_numeric_ratio_stack(
    component: ComponentRow,
    size: str,
    *,
    data_model: dict[str, Any] | None = None,
) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("NumericRatioStack requires a 2x2 or 2x4 card.")
    items = _numeric_ratio_items(component)
    direction = component.props.get("direction", "column")
    variant = "row" if direction == "row" else None
    children: list[str] = []
    rows: list[ComponentRow] = []
    for index, item in enumerate(items):
        item_id = f"{component.component_id}_item{index}"
        icon_slot_id = f"{item_id}_icon_slot"
        icon_id = f"{item_id}_icon"
        value_group_id = f"{item_id}_value_group"
        value_id = f"{item_id}_value"
        value_children = [value_id]
        item_children = [icon_slot_id, value_group_id]
        children.append(item_id)
        rows.extend(
            [
                _visual_row(
                    icon_slot_id,
                    "NumericRatioStack",
                    "iconSlot",
                    size=size,
                    variant=variant,
                    children=(icon_id,),
                ),
                _visual_row(
                    icon_id,
                    "NumericRatioStack",
                    "icon",
                    size=size,
                    variant=variant,
                    props={"src": item["icon"], "fillColor": component.props["fillColor"]},
                ),
                _visual_row(
                    value_id,
                    "NumericRatioStack",
                    "value",
                    size=size,
                    variant=variant,
                    props={
                        "content": copy.deepcopy(item["value"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
            ]
        )
        unit = item.get("unit")
        value = item.get("value")
        if unit is None and isinstance(value, (int, float)) and not isinstance(value, bool):
            unit = "%"
        if unit is None and _is_path_binding(value):
            found, initial_value = _json_pointer_value(
                data_model or {},
                value.get("path"),
            )
            if found and isinstance(initial_value, (int, float)) and not isinstance(
                initial_value,
                bool,
            ):
                unit = "%"
        if unit is not None:
            unit_id = f"{item_id}_unit"
            value_children.append(unit_id)
            rows.append(
                _visual_row(
                    unit_id,
                    "NumericRatioStack",
                    "value",
                    size=size,
                    variant=variant,
                    props={"content": unit, "fontColor": component.props["fontColor"]},
                )
            )
        rows.append(
            _visual_row(
                value_group_id,
                "NumericRatioStack",
                "valueGroup",
                size=size,
                variant=variant,
                children=tuple(value_children),
            )
        )
        rows.append(
            _visual_row(
                item_id,
                "NumericRatioStack",
                "item",
                size=size,
                variant=variant,
                children=tuple(item_children),
            )
        )
    root = _visual_row(
        component.component_id,
        "NumericRatioStack",
        "root",
        size=size,
        variant=variant,
        children=tuple(children),
    )
    return [root, *rows]


def _expand_progress_circle(
    component: ComponentRow,
    size: str,
    *,
    data_model: dict[str, Any] | None = None,
) -> list[ComponentRow]:
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
    progress_value, external_text = _progress_circle_values(
        component,
        data_model=data_model,
    )

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


def _progress_circle_values(
    component: ComponentRow,
    *,
    data_model: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    value = component.props.get("externalText")
    if _is_path_binding(value):
        path = value.get("path")
        progress_value = _normalized_progress_binding(
            component,
            "externalText",
            value,
            total=100,
            data_model=data_model,
        )
        found, initial_value = _json_pointer_value(data_model or {}, path)
        if found and isinstance(initial_value, str):
            return progress_value, copy.deepcopy(value)
        return progress_value, f"{{{{ ${{{path}}} + '%' }}}}"
    numeric_value = _normalized_progress_literal(
        component,
        "externalText",
        value,
        total=100,
    )
    if isinstance(value, str):
        return numeric_value, value.strip()
    visible = str(numeric_value)
    return numeric_value, f"{visible}%"


def _normalized_progress_binding(
    component: ComponentRow,
    prop_name: str,
    value: Any,
    *,
    total: int | float,
    data_model: dict[str, Any] | None,
) -> Any:
    if not _is_path_binding(value):
        return _normalized_progress_literal(
            component,
            prop_name,
            value,
            total=total,
        )
    path = value.get("path")
    found, initial_value = _json_pointer_value(data_model or {}, path)
    if not found:
        return copy.deepcopy(value)
    if not isinstance(initial_value, (int, float, str)) or isinstance(
        initial_value,
        bool,
    ):
        return copy.deepcopy(value)
    numeric_value = _normalized_progress_literal(
        component,
        prop_name,
        initial_value,
        total=total,
    )
    if not isinstance(initial_value, str):
        return copy.deepcopy(value)
    derived_path = f"/__display{path}/progressValue"
    if data_model is not None:
        _set_json_pointer(data_model, derived_path, numeric_value)
    return {"path": derived_path}


def _normalized_progress_literal(
    component: ComponentRow,
    prop_name: str,
    value: Any,
    *,
    total: int | float,
) -> int | float:
    if isinstance(value, bool):
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.{prop_name} "
            "must be a finite number or complete numeric percentage."
        )
    if isinstance(value, (int, float)) and math.isfinite(value):
        numeric_value = float(value)
    elif isinstance(value, str):
        match = re.fullmatch(
            r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([%％]?)\s*",
            value,
        )
        if match is None:
            raise CompactDslConversionError(
                f"{component.component_id}: {component.component_type}.{prop_name} "
                "must be a finite number or complete numeric percentage."
            )
        numeric_value = float(match.group(1))
        if match.group(2):
            numeric_value = min(100.0, max(0.0, numeric_value)) * float(total) / 100.0
    else:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.{prop_name} "
            "must be a finite number or complete numeric percentage."
        )
    if not math.isfinite(numeric_value) or numeric_value < 0 or numeric_value > total:
        raise CompactDslConversionError(
            f"{component.component_id}: {component.component_type}.{prop_name} "
            f"must resolve between 0 and total ({total})."
        )
    return int(numeric_value) if numeric_value.is_integer() else numeric_value


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
    if unit is not None:
        _require_string_display_value(component, "unit")

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
                    "content": copy.deepcopy(unit),
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


def _expand_info_block(
    component: ComponentRow,
    size: str,
    *,
    data_model: dict[str, Any] | None = None,
) -> list[ComponentRow]:
    allowed = {
        "variant",
        "primaryText",
        "secondaryText",
        "unit",
        "visual",
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
    legacy_icon = component.props.get("icon")
    if legacy_icon is not None and (
        not isinstance(legacy_icon, str) or not legacy_icon.strip()
    ):
        raise CompactDslConversionError(
            f"{component.component_id}: InfoBlock.icon must be non-empty."
        )
    if "fillColor" in component.props:
        _require_color(component, "fillColor")
    unit = component.props.get("unit")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise CompactDslConversionError(
            f"{component.component_id}: InfoBlock.unit must be non-empty text."
        )
    variant = component.props.get("variant")
    _info_block_profile(size, variant)
    visual = component.props.get("visual")
    if visual is not None and "icon" in component.props:
        raise CompactDslConversionError(
            f"{component.component_id}: InfoBlock.visual and legacy icon are mutually exclusive."
        )
    if visual is None and "icon" in component.props:
        visual = {"type": "icon", "icon": component.props["icon"]}
    visual_type: str | None = None
    visual_icon: str | None = None
    if visual is not None:
        if not isinstance(visual, dict) or set(visual) - {"type", "icon", "color"}:
            raise CompactDslConversionError(
                f"{component.component_id}: InfoBlock.visual has unsupported fields."
            )
        visual_type = visual.get("type")
        visual_icon = visual.get("icon")
        if visual_type not in {"icon", "progressCircle"}:
            raise CompactDslConversionError(
                f"{component.component_id}: InfoBlock.visual.type must be icon or progressCircle."
            )
        if not isinstance(visual_icon, str) or not visual_icon.strip():
            raise CompactDslConversionError(
                f"{component.component_id}: InfoBlock.visual.icon must be non-empty."
            )
        color_mode = visual.get("color")
        if color_mode is not None and (visual_type != "icon" or color_mode != "native"):
            raise CompactDslConversionError(
                f"{component.component_id}: InfoBlock.visual.color only supports native icons."
            )
    copy_layout = {"layoutWeight": 1} if visual_type else {"width": "matchParent"}
    text_parent_id = f"{component.component_id}_text"
    primary_id = f"{component.component_id}_primary"
    secondary_id = f"{component.component_id}_secondary"
    children = [text_parent_id]
    visual_id = f"{component.component_id}_visual"
    if visual_type:
        children.append(visual_id)
    container_props: dict[str, Any] = {
        "backgroundColor": component.props["backgroundColor"],
    }
    root_part = "root" if visual_type else "rootNoVisual"
    primary_children: tuple[str, ...] = ()
    text_children = [primary_id, secondary_id]
    if unit is not None:
        primary_value_id = f"{primary_id}_value"
        unit_id = f"{primary_id}_unit"
        primary_children = (primary_value_id, unit_id)
        text_children[0] = f"{primary_id}_row"
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
            children=tuple(text_children),
        ),
    ]
    if unit is None:
        rows.extend(_info_block_text_rows(component, size, primary_id, secondary_id))
    else:
        rows.extend(
            [
                _visual_row(
                    text_children[0],
                    "InfoBlock",
                    "primaryRow",
                    size=size,
                    children=primary_children,
                ),
                _visual_row(
                    primary_children[0],
                    "InfoBlock",
                    "primaryValue",
                    size=size,
                    props={
                        "content": copy.deepcopy(component.props["primaryText"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
                _visual_row(
                    primary_children[1],
                    "InfoBlock",
                    "unit",
                    size=size,
                    props={
                        "content": unit,
                        "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                    },
                ),
                _visual_row(
                    secondary_id,
                    "InfoBlock",
                    "secondary",
                    size=size,
                    props={
                        "content": copy.deepcopy(component.props["secondaryText"]),
                        "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                    },
                ),
            ]
        )
    if visual_type == "icon":
        image_props: dict[str, Any] = {"src": visual_icon}
        if visual.get("color") != "native":
            image_props["fillColor"] = component.props.get(
                "fillColor",
                component.props["fontColor"],
            )
        rows.append(
            _visual_row(
                visual_id,
                "InfoBlock",
                "icon",
                size=size,
                props=image_props,
            )
        )
    elif visual_type == "progressCircle":
        progress_id = f"{visual_id}_progress"
        icon_id = f"{visual_id}_icon"
        progress_value = _normalized_progress_binding(
            component,
            "primaryText",
            component.props["primaryText"],
            total=100,
            data_model=data_model,
        )
        rows.extend(
            [
                _visual_row(
                    visual_id,
                    "InfoBlock",
                    "progressStack",
                    size=size,
                    children=(progress_id, icon_id),
                ),
                _visual_row(
                    progress_id,
                    "InfoBlock",
                    "progress",
                    size=size,
                    props={
                        "type": "ring",
                        "value": progress_value,
                        "total": 100,
                        "color": component.props["fontColor"],
                        "backgroundColor": _color_with_alpha(
                            component.props["fontColor"],
                            0.2,
                        ),
                    },
                ),
                _visual_row(
                    icon_id,
                    "InfoBlock",
                    "progressIcon",
                    size=size,
                    props={
                        "src": visual_icon,
                        "fillColor": component.props.get(
                            "fillColor",
                            _color_with_alpha(component.props["fontColor"], 0.6),
                        ),
                    },
                ),
            ]
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


def _expand_progress_line_two(
    component: ComponentRow,
    size: str,
    *,
    data_model: dict[str, Any] | None = None,
) -> list[ComponentRow]:
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
    if unit is not None:
        _require_string_display_value(component, "unit")
    for name in ("fontColor", "color", "backgroundColor"):
        _require_color(component, name)
    total = component.props.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressLine2.total must be a positive number."
        )
    progress_value = _normalized_progress_binding(
        component,
        "value",
        component.props["value"],
        total=total,
        data_model=data_model,
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
                "value": progress_value,
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
                    "content": copy.deepcopy(unit),
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    return rows


def _expand_table_text(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("TableText requires a 2x2 or 2x4 card.")
    items = _validate_item_component(component, minimum=2, maximum=3)
    variant = "compact" if len(items) == 3 else None
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
                    variant=variant,
                    children=(label_id, value_id),
                ),
                _visual_row(
                    label_id,
                    "TableText",
                    "label",
                    size=size,
                    variant=variant,
                    props={
                        "content": copy.deepcopy(item["label"]),
                        "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                    },
                ),
                _visual_row(
                    value_id,
                    "TableText",
                    "value",
                    size=size,
                    variant=variant,
                    props={
                        "content": copy.deepcopy(item["value"]),
                        "fontColor": component.props["fontColor"],
                    },
                ),
            ]
        )
    recipe = _visual_recipe("TableText", size=size, variant=variant)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactDslConversionError("TableText visual recipe has invalid metrics.")
    item_margin = metrics.get("twoRowGap" if len(items) == 2 else "threeRowGap")
    root = _visual_row(
        component.component_id,
        "TableText",
        "root",
        size=size,
        variant=variant,
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
                        "content": copy.deepcopy(item["label"]),
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
    *,
    data_model: dict[str, Any] | None = None,
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
    _require_text_value(component, "label")
    total = component.props.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        raise CompactDslConversionError(
            f"{component.component_id}: ProgressCircleSingle.total must be a positive number."
        )
    progress_value = _normalized_progress_binding(
        component,
        "value",
        component.props["value"],
        total=total,
        data_model=data_model,
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
                "value": progress_value,
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
                "content": copy.deepcopy(component.props["label"]),
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


def _event_card_items(component: ComponentRow) -> tuple[list[dict[str, Any]], bool]:
    allowed = {"items", "title", "time", "location", "density", "fontColor"}
    _validate_high_level_props(
        component,
        required={"fontColor"},
        allowed=allowed,
    )
    _require_color(component, "fontColor")
    density = component.props.get("density")
    if density not in {None, "compact"}:
        raise CompactDslConversionError(
            f"{component.component_id}: EventCard.density must be compact when present."
        )
    has_items = "items" in component.props
    has_legacy = "title" in component.props or "time" in component.props
    if has_items and has_legacy:
        raise CompactDslConversionError(
            f"{component.component_id}: EventCard.items cannot be combined with title/time."
        )
    if has_items:
        items = component.props.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 2:
            raise CompactDslConversionError(
                f"{component.component_id}: EventCard.items requires 1 to 2 entries."
            )
    else:
        if "title" not in component.props or "time" not in component.props:
            raise CompactDslConversionError(
                f"{component.component_id}: EventCard requires items or title/time."
            )
        item = {
            "title": component.props["title"],
            "time": component.props["time"],
        }
        if "location" in component.props:
            item["location"] = component.props["location"]
        items = [item]
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not {"title", "time"} <= set(item):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] requires title and time."
            )
        if not set(item) <= {"title", "time", "location"}:
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}] allows title/time/location only."
            )
        for name in ("title", "time"):
            if not _is_display_value(item.get(name)):
                raise CompactDslConversionError(
                    f"{component.component_id}: items[{index}].{name} must be display text."
                )
        if "location" in item and not _is_display_value(item.get("location")):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].location must be display text."
            )
    return items, density == "compact"


def _event_card_item_rows(
    component: ComponentRow,
    item: dict[str, Any],
    *,
    item_id: str,
    size: str,
    compact: bool,
    multiple: bool,
) -> tuple[list[ComponentRow], int]:
    has_location = "location" in item
    variant = "compact" if compact else ("withLocation" if has_location else "withoutLocation")
    recipe = _visual_recipe("EventCard", size=size, variant=variant)
    metrics = recipe.get("metrics")
    if not isinstance(metrics, dict):
        raise CompactDslConversionError("EventCard visual recipe has invalid metrics.")
    event_height = metrics.get("height")
    line_height = metrics.get("lineHeight")
    if not isinstance(event_height, int) or not isinstance(line_height, int):
        raise CompactDslConversionError("EventCard visual recipe has invalid geometry.")
    rail_id = f"{item_id}_rail"
    dot_id = f"{rail_id}_dot"
    line_id = f"{rail_id}_line"
    texts_id = f"{item_id}_texts"
    title_id = f"{item_id}_title"
    time_id = f"{item_id}_time"
    text_children = [title_id, time_id]
    meta_row_id = f"{item_id}_meta"
    location_id = f"{item_id}_location"
    if compact:
        text_children = [title_id, meta_row_id]
    elif has_location:
        text_children.append(location_id)
    rows = [
        _visual_row(
            item_id,
            "EventCard",
            "item" if multiple else "root",
            size=size,
            variant=variant,
            props={"height": event_height},
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
                "content": copy.deepcopy(item["title"]),
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
                "content": copy.deepcopy(item["time"]),
                "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
            },
        ),
    ]
    if compact:
        meta_children = [time_id]
        if has_location:
            separator_id = f"{meta_row_id}_separator"
            meta_children.extend([separator_id, location_id])
            rows.extend(
                [
                    _visual_row(
                        separator_id,
                        "EventCard",
                        "separator",
                        size=size,
                        variant=variant,
                        props={
                            "content": "｜",
                            "fontColor": _color_with_alpha(
                                component.props["fontColor"],
                                0.6,
                            ),
                        },
                    ),
                    _visual_row(
                        location_id,
                        "EventCard",
                        "meta",
                        size=size,
                        variant=variant,
                        props={
                            "content": copy.deepcopy(item["location"]),
                            "fontColor": _color_with_alpha(
                                component.props["fontColor"],
                                0.6,
                            ),
                        },
                    ),
                ]
            )
        rows.append(
            _visual_row(
                meta_row_id,
                "EventCard",
                "metaRow",
                size=size,
                variant=variant,
                children=tuple(meta_children),
            )
        )
    elif has_location:
        rows.append(
            _visual_row(
                location_id,
                "EventCard",
                "meta",
                size=size,
                variant=variant,
                props={
                    "content": copy.deepcopy(item["location"]),
                    "fontColor": _color_with_alpha(component.props["fontColor"], 0.6),
                },
            )
        )
    return rows, event_height


def _expand_event_card(component: ComponentRow, size: str) -> list[ComponentRow]:
    if size not in {"2x2", "2x4"}:
        raise CompactDslConversionError("EventCard requires a 2x2 or 2x4 card.")
    items, compact = _event_card_items(component)
    rows: list[ComponentRow] = []
    item_ids: list[str] = []
    total_height = 0
    for index, item in enumerate(items):
        if len(items) == 1:
            item_id = component.component_id
        else:
            item_id = f"{component.component_id}_item{index}"
        item_rows, item_height = _event_card_item_rows(
            component,
            item,
            item_id=item_id,
            size=size,
            compact=compact,
            multiple=len(items) > 1,
        )
        rows.extend(item_rows)
        item_ids.append(item_id)
        total_height += item_height
    if len(items) == 1:
        return rows
    total_height += 8
    root = _visual_row(
        component.component_id,
        "EventCard",
        "multiRoot",
        size=size,
        props={"height": total_height},
        children=tuple(item_ids),
    )
    return [root, *rows]


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
        if not _is_display_value(label):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be display text."
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


def _require_string_display_value(component: ComponentRow, name: str) -> None:
    value = component.props.get(name)
    valid_text = isinstance(value, str) and bool(value.strip())
    if valid_text or _is_path_binding(value):
        return
    raise CompactDslConversionError(
        f"{component.component_id}: {component.component_type}.{name} must be string display text."
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
        if not _is_display_value(label):
            raise CompactDslConversionError(
                f"{component.component_id}: items[{index}].label must be display text."
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


def _convert_single_line_title(component: ComponentRow, size: str = "2x2") -> list[dict[str, Any]]:
    props = component.props
    root_type, root_styles = _visual_recipe_part_for_converter(
        "SingleLineTitle",
        "root",
        size=size,
    )
    title_type, title_styles = _visual_recipe_part_for_converter(
        "SingleLineTitle",
        "title",
        size=size,
    )
    root_styles.pop("_visualRecipe", None)
    title_styles.pop("_visualRecipe", None)
    item_margin = root_styles.pop("itemMargin", 0)
    title_id = f"{component.component_id}_title"
    row = {
        "id": component.component_id,
        "component": root_type,
        "children": [title_id],
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
    return [row, title]


def _is_path_binding(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"path"}:
        return False
    path = value.get("path")
    return isinstance(path, str) and path.startswith("/")


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
