# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Convert 2x4 Design Compact DSL rows to A2UI Form JSONL.

This converter is intentionally small and deterministic. It targets the 2x4
visual patterns from the high-water examples in ``dingran0810/2x4`` and expands
the local high-level components ActionUnit, RingUnit, TimelineUnit, and
ProgressUnit.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from services.compact_dsl_a2ui_converter import CompactDslConversionError

ThemeMode = Literal["light", "dark"]

_SURFACE_ID = "surface_card"
_CATALOG_ID = "ohos.a2ui.extended.catalog.form"
_CARD_WIDTH = 320
_CARD_HEIGHT = 160
_CONTAINER_COMPONENTS = {"Stack", "Column", "Row"}
_NON_CONTAINER_COMPONENTS = {
    "Text",
    "Image",
    "Divider",
    "Checkbox",
    "ActionUnit",
    "RingUnit",
    "TimelineUnit",
    "ProgressUnit",
}
_BINDING_RE = re.compile(r"^\{\{\s*\$\{([^}]+)\}\s*\}\}$")
_INLINE_BINDING_RE = re.compile(r"\{\{\s*(?:\$\{\s*)?(/[^}\s]+)\s*(?:\}\s*)?\}\}")
_TEXT_JOIN_SEPARATOR_RE = re.compile(r"\s*[·｜|]\s*")
_TIMELINE_UNIT_DEFAULT_COLOR = "#FFE84026"
_TIMELINE_UNIT_DEFAULT_LINE_COLOR = "#1A000000"

_LIGHT_GRADIENTS = {
    "blue": {
        "angle": 180,
        "colors": [["#FFE1ECFF", 0], ["#FFF3F7FF", 0.58], ["#FFFFFFFF", 1]],
    },
    "cream": {
        "angle": 180,
        "colors": [["#FFFFF1C7", 0], ["#FFFFF9E6", 0.58], ["#FFFFFFFF", 1]],
    },
    "orange": {
        "angle": 180,
        "colors": [["#FFFFE4D2", 0], ["#FFFFF5EC", 0.58], ["#FFFFFFFF", 1]],
    },
    "green": {
        "angle": 180,
        "colors": [["#FFDDF5E8", 0], ["#FFF1FAF5", 0.58], ["#FFFFFFFF", 1]],
    },
    "pink": {
        "angle": 180,
        "colors": [["#FFFFE2E9", 0], ["#FFFFF4F7", 0.58], ["#FFFFFFFF", 1]],
    },
    "lavender": {
        "angle": 180,
        "colors": [["#FFEDE4FF", 0], ["#FFF8F4FF", 0.58], ["#FFFFFFFF", 1]],
    },
    "cyan": {
        "angle": 180,
        "colors": [["#FFDFF7FA", 0], ["#FFF2FBFC", 0.58], ["#FFFFFFFF", 1]],
    },
}
_SEMANTIC_REPAIRABLE_GRADIENT_COLOR_SETS = frozenset(
    {
        frozenset({"#FFE1ECFF", "#FFF3F7FF", "#FFFFFFFF"}),
        frozenset({"#FFF6FAFF", "#FFFCFDFF", "#FFFFFFFF"}),
    }
)

class CompactDsl2x4ConversionError(CompactDslConversionError):
    """Raised when a 2x4 compact DSL cannot be converted."""


@dataclass(frozen=True)
class ComponentRow:
    component_id: str
    component_type: str
    props: dict[str, Any]
    children: list[str]


def convert_compact_dsl_2x4_to_a2ui(
    compact_dsl: str,
    *,
    size: str = "2x4",
    protocol_profile: dict[str, Any] | None = None,
    theme: ThemeMode = "light",
    surface_id: str = _SURFACE_ID,
    allow_actions: bool = True,
    allow_bindings: bool = True,
    event_candidates: list[Any] | None = None,
) -> str:
    """Convert one 2x4 Design Compact DSL card to A2UI JSONL."""
    del protocol_profile, theme
    if size not in {"2x4", "4x2"}:
        raise CompactDsl2x4ConversionError(f'Unsupported 2x4 size "{size}".')

    rows = _parse_rows(compact_dsl)
    if not allow_bindings:
        rows = _inline_data_bindings(rows)
    if not allow_actions:
        rows = _remove_action_units(rows)
    components, data_rows = _split_rows(rows)
    _validate_components(components)
    _repair_semantic_root_gradient(components)
    components = _repair_component_geometry(components)
    available_widths = _child_available_widths(components)
    a2ui_components = _convert_components(
        components,
        event_candidates=event_candidates,
        available_widths=available_widths,
    )
    a2ui_components = _repair_expanded_component_geometry(a2ui_components)
    update_data = _build_data_model(data_rows)

    messages = [
        _create_surface(surface_id),
        _update_components(surface_id, a2ui_components),
        _update_data_model(surface_id, update_data),
    ]
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for message in messages
    )


def _parse_rows(compact_dsl: str) -> list[list[Any]]:
    body = _strip_markdown_fence(compact_dsl)
    parsed = _load_json_or_scan(body)
    rows = _coerce_rows(parsed)
    if not rows:
        raise CompactDsl2x4ConversionError("Compact DSL is empty.")
    return rows


def _repair_semantic_root_gradient(components: list[ComponentRow]) -> None:
    """Replace only generic blue defaults with a semantic light palette."""
    root = components[0]
    current = root.props.get("linearGradient")
    color_set = _gradient_color_set(current)
    if current is not None and color_set not in _SEMANTIC_REPAIRABLE_GRADIENT_COLOR_SETS:
        return
    visible_text = " ".join(
        content.lower()
        for component in components
        if component.component_type == "Text"
        for content in [component.props.get("content")]
        if isinstance(content, str)
    )
    palette_rules = (
        (("耳机", "音乐", "音频", "歌曲", "播放", "headphone", "music", "audio"), "lavender"),
        (
            ("蓝牙", "网络", "连接", "定位", "设置", "bluetooth", "network", "connect", "setting"),
            "cyan",
        ),
        (
            (
                "会议地点",
                "会议详情",
                "跨时区",
                "全天日程",
                "会议信息",
                "location",
                "timezone",
                "meeting detail",
            ),
            "pink",
        ),
        (("提醒", "待办", "准备", "专注", "闹钟", "reminder", "task", "focus", "alarm"), "cream"),
        (("健康", "运动", "步数", "能量", "睡眠", "health", "sport", "steps", "sleep"), "green"),
        (
            (
                "存储",
                "内存",
                "容量",
                "倒计时",
                "训练",
                "storage",
                "memory",
                "countdown",
                "training",
            ),
            "orange",
        ),
        (("应用", "抖音", "使用时长", "防沉迷", "app", "screen time"), "pink"),
    )
    palette_name = next(
        (
            name
            for keywords, name in palette_rules
            if any(keyword in visible_text for keyword in keywords)
        ),
        None,
    )
    if palette_name is not None:
        root.props["linearGradient"] = copy.deepcopy(_LIGHT_GRADIENTS[palette_name])


def _gradient_color_set(value: Any) -> frozenset[str] | None:
    if not isinstance(value, dict):
        return None
    colors = value.get("colors")
    if not isinstance(colors, list):
        return None
    normalized = {
        str(item[0]).upper()
        for item in colors
        if isinstance(item, list) and item
    }
    return frozenset(normalized) if normalized else None


def _strip_markdown_fence(text: str) -> str:
    stripped = text.lstrip("\ufeff").strip()
    lines = stripped.splitlines()
    if not lines or not lines[0].strip().startswith("```"):
        return stripped
    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "```":
            closing_index = index
            break
    end_index = closing_index if closing_index is not None else len(lines)
    return "\n".join(lines[1:end_index]).strip()


def _load_json_or_scan(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return _scan_json_rows(stripped)


def _scan_json_rows(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    rows: list[Any] = []
    index = 0
    while index < len(text):
        index = _skip_separators(text, index)
        if index >= len(text):
            break
        if text[index] != "[":
            raise CompactDsl2x4ConversionError(
                f"Compact DSL line starts with unsupported character {text[index]!r}."
            )
        try:
            row, end_index = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise CompactDsl2x4ConversionError(str(exc)) from exc
        rows.append(row)
        index = end_index
    return rows


def _skip_separators(text: str, index: int) -> int:
    while index < len(text) and text[index] in {" ", "\t", "\r", "\n", ","}:
        index += 1
    return index


def _coerce_rows(value: Any) -> list[list[Any]]:
    if _looks_like_row(value):
        return [value]
    if isinstance(value, list) and all(_looks_like_row(item) for item in value):
        return value
    raise CompactDsl2x4ConversionError("Compact DSL has an unsupported row shape.")


def _looks_like_row(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    if len(value) == 2 and isinstance(value[0], str) and value[0].startswith("/"):
        return True
    if len(value) in {3, 4}:
        return isinstance(value[0], str) and isinstance(value[1], str)
    return False


def _split_rows(rows: list[list[Any]]) -> tuple[list[ComponentRow], list[list[Any]]]:
    components: list[ComponentRow] = []
    data_rows: list[list[Any]] = []
    for row in rows:
        if len(row) == 2 and isinstance(row[0], str) and row[0].startswith("/"):
            data_rows.append(row)
            continue
        components.append(_parse_component_row(row))
    return components, data_rows


def _inline_data_bindings(rows: list[list[Any]]) -> list[list[Any]]:
    values_by_path = {
        row[0]: row[1]
        for row in rows
        if len(row) == 2 and isinstance(row[0], str) and row[0].startswith("/")
    }
    output: list[list[Any]] = []
    for row in rows:
        if len(row) == 2 and isinstance(row[0], str) and row[0].startswith("/"):
            continue
        cloned = copy.deepcopy(row)
        if len(cloned) >= 3 and isinstance(cloned[2], dict):
            cloned[2] = _inline_binding_value(cloned[2], values_by_path, "")
        output.append(cloned)
    return output


def _inline_binding_value(
    value: Any,
    values_by_path: dict[str, Any],
    parent_key: str,
) -> Any:
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str):
            sample = values_by_path.get(path)
            unit = value.get("unit", "")
            if parent_key in {"value", "total"}:
                return _numeric_sample(sample)
            if isinstance(unit, str) and unit:
                return f"{_string_sample(sample)}{unit}"
            return _string_sample(sample)
        return {
            key: _inline_binding_value(item, values_by_path, key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _inline_binding_value(item, values_by_path, parent_key)
            for item in value
        ]
    return value


def _numeric_sample(value: Any) -> int | float:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            number_text = match.group(0)
            return float(number_text) if "." in number_text else int(number_text)
    return 0


def _string_sample(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _remove_action_units(rows: list[list[Any]]) -> list[list[Any]]:
    components = [_parse_component_row(row) for row in rows if not _is_data_row(row)]
    removed_ids = {
        component.component_id
        for component in components
        if component.component_type == "ActionUnit"
    }
    if not removed_ids:
        return rows

    changed = True
    while changed:
        changed = False
        for component in components:
            if component.component_id in removed_ids:
                continue
            remaining_children = [
                child for child in component.children if child not in removed_ids
            ]
            if _should_remove_empty_container(component, remaining_children):
                removed_ids.add(component.component_id)
                changed = True

    output: list[list[Any]] = []
    for row in rows:
        if _is_data_row(row):
            output.append(row)
            continue
        if row[0] in removed_ids:
            continue
        cloned = copy.deepcopy(row)
        if len(cloned) == 4:
            cloned[3] = [child for child in cloned[3] if child not in removed_ids]
        output.append(cloned)
    return output


def _is_data_row(row: list[Any]) -> bool:
    return len(row) == 2 and isinstance(row[0], str) and row[0].startswith("/")


def _should_remove_empty_container(
    component: ComponentRow,
    remaining_children: list[str],
) -> bool:
    if remaining_children or component.component_id in {"root", "content_root"}:
        return False
    return component.component_type in {"Column", "Row"}


def _parse_component_row(row: list[Any]) -> ComponentRow:
    if len(row) not in {3, 4}:
        raise CompactDsl2x4ConversionError(f"{row[0]}: unsupported component row.")
    component_id, component_type, props = row[:3]
    if not isinstance(component_id, str) or not component_id:
        raise CompactDsl2x4ConversionError("component id must be a non-empty string.")
    if not isinstance(component_type, str) or not component_type:
        raise CompactDsl2x4ConversionError(f"{component_id}: component type is empty.")
    if not isinstance(props, dict):
        raise CompactDsl2x4ConversionError(f"{component_id}: props must be an object.")

    children: list[str] = []
    if len(row) == 4:
        raw_children = row[3]
        if not isinstance(raw_children, list) or not all(
            isinstance(item, str) for item in raw_children
        ):
            raise CompactDsl2x4ConversionError(
                f"{component_id}: children must be a string list."
            )
        children = raw_children
    return ComponentRow(component_id, component_type, props, children)


def _validate_components(components: list[ComponentRow]) -> None:
    if not components:
        raise CompactDsl2x4ConversionError("No component rows found.")
    first = components[0]
    if first.component_id != "root" or first.component_type not in {"Stack", "Column"}:
        raise CompactDsl2x4ConversionError('The first component must be ["root","Stack",...].')

    declared: set[str] = set()
    expected_children: set[str] = set()
    for component in components:
        if component.component_id in declared:
            raise CompactDsl2x4ConversionError(f"{component.component_id}: duplicate id.")
        if component.component_type not in _CONTAINER_COMPONENTS | _NON_CONTAINER_COMPONENTS:
            raise CompactDsl2x4ConversionError(
                f"{component.component_id}: unsupported component {component.component_type}."
            )
        if _requires_children(component) and not component.children:
            raise CompactDsl2x4ConversionError(
                f"{component.component_id}: container must declare children."
            )
        if component.component_type in _NON_CONTAINER_COMPONENTS and component.children:
            raise CompactDsl2x4ConversionError(
                f"{component.component_id}: non-container components cannot have children."
            )
        if component.component_id != "root" and component.component_id not in expected_children:
            raise CompactDsl2x4ConversionError(
                f"{component.component_id}: component must be declared by an earlier parent."
            )
        declared.add(component.component_id)
        expected_children.update(component.children)


def _requires_children(component: ComponentRow) -> bool:
    if component.component_type in {"Column", "Row"}:
        return True
    return component.component_type == "Stack" and component.component_id == "root"


def _repair_component_geometry(components: list[ComponentRow]) -> list[ComponentRow]:
    props_by_id = {
        component.component_id: dict(component.props)
        for component in components
    }
    component_by_id = {
        component.component_id: component
        for component in components
    }
    _compact_progress_detail_layouts(components, component_by_id, props_by_id)
    _compact_root_vertical_layouts(components, component_by_id, props_by_id)
    for component in components:
        if component.component_type == "Row":
            _fit_row_children(component, component_by_id, props_by_id)
        elif component.component_type == "Column":
            _fit_column_child_widths(component, component_by_id, props_by_id)
    return [
        ComponentRow(
            component.component_id,
            component.component_type,
            props_by_id[component.component_id],
            component.children,
        )
        for component in components
    ]


def _repair_expanded_component_geometry(
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    repaired = _remove_emoji_text_components(components)
    repaired = _remove_repeated_action_icons(repaired)
    component_by_id = {
        str(component.get("id")): component
        for component in repaired
        if isinstance(component.get("id"), str)
    }
    _normalize_linear_progress_heights(repaired)
    _expand_sparse_linear_progress_cards(repaired, component_by_id)
    _grow_expanded_container_heights("root", component_by_id, set())
    content_root = component_by_id.get("content_root")
    if content_root is not None:
        _fit_expanded_surface_height(content_root, component_by_id)
    _expand_static_text_widths(repaired)
    _fit_expanded_component_widths("root", component_by_id, set())
    return repaired


def _normalize_linear_progress_heights(components: list[dict[str, Any]]) -> None:
    linear_progresses = [
        component
        for component in components
        if component.get("component") == "Progress"
        and _expanded_styles(component).get("type") == "linear"
    ]
    if not linear_progresses:
        return
    height = 4 if len(linear_progresses) >= 3 else 8
    radius = 2 if height == 4 else 4
    for progress in linear_progresses:
        styles = _expanded_styles(progress)
        styles["height"] = height
        styles["borderRadius"] = radius


def _expand_sparse_linear_progress_cards(
    components: list[dict[str, Any]],
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in _expanded_children(component)
    }
    for component in components:
        if component.get("component") != "Column":
            continue
        children = _expanded_children(component)
        if len(children) != 3:
            continue
        child_components = [component_by_id.get(child_id) for child_id in children]
        if any(child is None for child in child_components):
            continue
        progress, first_detail, second_detail = child_components
        if not _is_sparse_linear_progress_group(progress, first_detail, second_detail):
            continue
        parent = parent_by_child.get(str(component.get("id")))
        if parent is None or _expanded_parent_has_action(parent, component_by_id):
            continue
        component["itemMargin"] = 12
        _expanded_styles(component)["height"] = 96
        _expanded_styles(first_detail)["height"] = 32
        _expanded_styles(second_detail)["height"] = 32


def _is_sparse_linear_progress_group(
    progress: dict[str, Any] | None,
    first_detail: dict[str, Any] | None,
    second_detail: dict[str, Any] | None,
) -> bool:
    if progress is None or first_detail is None or second_detail is None:
        return False
    progress_styles = _expanded_styles(progress)
    progress_is_linear = progress.get("component") == "Progress"
    progress_is_linear = progress_is_linear and progress_styles.get("type") == "linear"
    details_are_rows = first_detail.get("component") == "Row"
    details_are_rows = details_are_rows and second_detail.get("component") == "Row"
    first_height = _expanded_numeric_height(first_detail)
    second_height = _expanded_numeric_height(second_detail)
    return progress_is_linear and details_are_rows and max(first_height, second_height) <= 20


def _expanded_parent_has_action(
    parent: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> bool:
    for child_id in _expanded_children(parent):
        child = component_by_id.get(child_id)
        if child is not None and child.get("onClick") is not None:
            return True
        if _is_action_area_id(child_id):
            return True
    return False


def _remove_emoji_text_components(
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    removed_ids = {
        str(component.get("id"))
        for component in components
        if component.get("component") == "Text"
        and _is_emoji_only_text(component.get("content"))
    }
    if not removed_ids:
        return components
    return _remove_expanded_components(components, removed_ids)


def _remove_repeated_action_icons(
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in _expanded_children(component)
    }
    regular_sources = {
        component.get("src")
        for component in components
        if component.get("component") == "Image"
        and parent_by_child.get(str(component.get("id")), {}).get("onClick") is None
    }
    removed_ids = {
        str(component.get("id"))
        for component in components
        if component.get("component") == "Image"
        and component.get("src") in regular_sources
        and parent_by_child.get(str(component.get("id")), {}).get("onClick") is not None
    }
    if not removed_ids:
        return components
    return _remove_expanded_components(components, removed_ids)


def _remove_expanded_components(
    components: list[dict[str, Any]],
    removed_ids: set[str],
) -> list[dict[str, Any]]:
    repaired = [
        component
        for component in components
        if component.get("id") not in removed_ids
    ]
    for component in repaired:
        children = component.get("children")
        if isinstance(children, list):
            component["children"] = [child for child in children if child not in removed_ids]
    return repaired


def _is_emoji_only_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    characters = [
        character
        for character in value.strip()
        if character not in {"\ufe0f", "\u200d"}
    ]
    if not characters:
        return False
    is_emoji = [
        ord(character) >= 0x1F000 or 0x2600 <= ord(character) <= 0x27BF
        for character in characters
    ]
    return any(is_emoji) and all(is_emoji)


def _grow_expanded_container_heights(
    component_id: str,
    component_by_id: dict[str, dict[str, Any]],
    visited: set[str],
) -> None:
    if component_id in visited:
        return
    component = component_by_id.get(component_id)
    if component is None:
        return
    visited.add(component_id)
    for child_id in _expanded_children(component):
        _grow_expanded_container_heights(child_id, component_by_id, visited)
    required_height = _expanded_children_layout_height(component, component_by_id)
    if required_height <= 0 or component_id in {"root", "content_root"}:
        return
    styles = _expanded_styles(component)
    current_height = styles.get("height")
    if not isinstance(current_height, int | float) or current_height < required_height:
        styles["height"] = required_height


def _fit_expanded_surface_height(
    content_root: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    component_type = content_root.get("component")
    if component_type == "Column":
        _fit_expanded_column_height(content_root, _CARD_HEIGHT, component_by_id)
        return
    if component_type != "Row":
        return
    styles = _expanded_styles(content_root)
    available_height = _CARD_HEIGHT - _vertical_padding(styles.get("padding"))
    for child_id in _expanded_children(content_root):
        child = component_by_id.get(child_id)
        if child is None:
            continue
        child_height = _expanded_numeric_height(child)
        if child_height > available_height:
            _fit_expanded_container_height(child, available_height, component_by_id)


def _fit_expanded_container_height(
    component: dict[str, Any],
    target_height: int,
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    component_type = component.get("component")
    if component_type == "Column":
        _fit_expanded_column_height(component, target_height, component_by_id)
    elif component_type in {"Row", "Stack"}:
        _fit_expanded_row_height(component, target_height, component_by_id)


def _fit_expanded_column_height(
    component: dict[str, Any],
    target_height: int,
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    styles = _expanded_styles(component)
    available_height = target_height - _vertical_padding(styles.get("padding"))
    if available_height <= 0:
        return
    if _expanded_column_children_height(component, component_by_id) > available_height:
        _cap_expanded_item_margin(component, 4)
    if _expanded_column_children_height(component, component_by_id) > available_height:
        _shrink_expanded_child_container_slack(component, component_by_id)
    if _expanded_column_children_height(component, component_by_id) > available_height:
        _shrink_expanded_direct_text_heights(component, available_height, component_by_id)
    if _expanded_column_children_height(component, component_by_id) > available_height:
        _cap_expanded_item_margin(component, 2)
    required_height = _expanded_children_layout_height(component, component_by_id)
    current_height = styles.get("height")
    fits_target = required_height <= target_height
    if isinstance(current_height, int | float) and fits_target:
        styles["height"] = min(current_height, target_height)


def _fit_expanded_row_height(
    component: dict[str, Any],
    target_height: int,
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    styles = _expanded_styles(component)
    available_height = target_height - _vertical_padding(styles.get("padding"))
    if available_height <= 0:
        return
    for child_id in _expanded_children(component):
        child = component_by_id.get(child_id)
        if child is None:
            continue
        if _expanded_numeric_height(child) > available_height:
            _fit_expanded_container_height(child, available_height, component_by_id)
    required_height = _expanded_children_layout_height(component, component_by_id)
    current_height = styles.get("height")
    fits_target = required_height <= target_height
    if isinstance(current_height, int | float) and fits_target:
        styles["height"] = min(current_height, target_height)


def _cap_expanded_item_margin(component: dict[str, Any], maximum: int) -> None:
    item_margin = component.get("itemMargin")
    if isinstance(item_margin, int | float) and item_margin > maximum:
        component["itemMargin"] = maximum


def _shrink_expanded_child_container_slack(
    component: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    for child_id in _expanded_children(component):
        child = component_by_id.get(child_id)
        if child is None or child.get("component") not in _CONTAINER_COMPONENTS:
            continue
        if child.get("onClick") is not None:
            continue
        required_height = _expanded_children_layout_height(child, component_by_id)
        child_styles = _expanded_styles(child)
        current_height = child_styles.get("height")
        can_shrink = isinstance(current_height, int | float) and required_height > 0
        if can_shrink and current_height > required_height:
            child_styles["height"] = required_height


def _shrink_expanded_direct_text_heights(
    component: dict[str, Any],
    available_height: int,
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    text_children: list[tuple[dict[str, Any], int]] = []
    for child_id in _expanded_children(component):
        child = component_by_id.get(child_id)
        if child is None or child.get("component") != "Text":
            continue
        styles = _expanded_styles(child)
        current_height = styles.get("height")
        if not isinstance(current_height, int | float):
            continue
        minimum_height = _minimum_text_height(styles.get("fontSize"))
        if current_height > minimum_height:
            text_children.append((styles, minimum_height))
    overflow = _expanded_column_children_height(component, component_by_id) - available_height
    for styles, minimum_height in text_children:
        if overflow <= 0:
            break
        current_height = int(styles["height"])
        reduction = min(overflow, current_height - minimum_height)
        styles["height"] = current_height - reduction
        overflow -= reduction


def _minimum_text_height(font_size: Any) -> int:
    if not isinstance(font_size, int | float):
        return 16
    if font_size <= 10:
        return 14
    if font_size <= 12:
        return 16
    if font_size <= 14:
        return 18
    if font_size <= 16:
        return 20
    if font_size <= 18:
        return 22
    return int(font_size * 1.2)


def _expanded_column_children_height(
    component: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> int:
    child_heights = [
        _expanded_numeric_height(component_by_id[child_id])
        for child_id in _expanded_children(component)
        if child_id in component_by_id
    ]
    if not child_heights:
        return 0
    item_margin = _number(component.get("itemMargin"), default=0)
    return sum(child_heights) + item_margin * (len(child_heights) - 1)


def _expanded_children_layout_height(
    component: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> int:
    children = [
        component_by_id[child_id]
        for child_id in _expanded_children(component)
        if child_id in component_by_id
    ]
    if not children:
        return 0
    styles = _expanded_styles(component)
    padding = _vertical_padding(styles.get("padding"))
    if component.get("component") == "Column":
        return padding + _expanded_column_children_height(component, component_by_id)
    child_height = max(_expanded_numeric_height(child) for child in children)
    return padding + child_height


def _expanded_numeric_height(component: dict[str, Any]) -> int:
    height = _expanded_styles(component).get("height")
    return int(height) if isinstance(height, int | float) else 0


def _expanded_styles(component: dict[str, Any]) -> dict[str, Any]:
    styles = component.get("styles")
    if isinstance(styles, dict):
        return styles
    styles = {}
    component["styles"] = styles
    return styles


def _expanded_children(component: dict[str, Any]) -> list[str]:
    children = component.get("children")
    if not isinstance(children, list):
        return []
    return [child for child in children if isinstance(child, str)]


def _expand_static_text_widths(components: list[dict[str, Any]]) -> None:
    for component in components:
        if component.get("component") != "Text":
            continue
        content = component.get("content")
        if not isinstance(content, str) or not content or "{{" in content:
            continue
        styles = _expanded_styles(component)
        width = styles.get("width")
        font_size = styles.get("fontSize")
        if not isinstance(width, int | float) or not isinstance(font_size, int | float):
            continue
        estimated_width = _estimated_static_text_width(content, float(font_size))
        if width < estimated_width:
            styles["width"] = estimated_width


def _estimated_static_text_width(content: str, font_size: float) -> int:
    width = 0.0
    for character in content:
        if unicodedata.east_asian_width(character) in {"W", "F"}:
            width += font_size
        else:
            width += font_size * 0.62
    estimated_width = int(width + 2.999)
    is_two_wide_characters = len(content) == 2 and all(
        unicodedata.east_asian_width(character) in {"W", "F"}
        for character in content
    )
    return max(28, estimated_width) if is_two_wide_characters else estimated_width


def _fit_expanded_component_widths(
    component_id: str,
    component_by_id: dict[str, dict[str, Any]],
    visited: set[str],
) -> None:
    if component_id in visited:
        return
    component = component_by_id.get(component_id)
    if component is None:
        return
    visited.add(component_id)
    component_type = component.get("component")
    if component_type in {"Column", "Stack"}:
        _cap_expanded_column_child_widths(component, component_by_id)
    elif component_type == "Row":
        _fit_expanded_row_width(component, component_by_id)
    for child_id in _expanded_children(component):
        _fit_expanded_component_widths(child_id, component_by_id, visited)


def _cap_expanded_column_child_widths(
    component: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    styles = _expanded_styles(component)
    width = styles.get("width")
    if not isinstance(width, int | float):
        return
    available_width = int(width - _horizontal_padding(styles.get("padding")))
    if available_width <= 0:
        return
    for child_id in _expanded_children(component):
        child = component_by_id.get(child_id)
        if child is None:
            continue
        child_styles = _expanded_styles(child)
        child_width = child_styles.get("width")
        if isinstance(child_width, int | float) and child_width > available_width:
            child_styles["width"] = available_width


def _fit_expanded_row_width(
    component: dict[str, Any],
    component_by_id: dict[str, dict[str, Any]],
) -> None:
    styles = _expanded_styles(component)
    width = styles.get("width")
    children = [
        component_by_id[child_id]
        for child_id in _expanded_children(component)
        if child_id in component_by_id
    ]
    if not isinstance(width, int | float) or len(children) < 2:
        return
    child_widths = [_expanded_styles(child).get("width") for child in children]
    if not all(isinstance(child_width, int | float) for child_width in child_widths):
        return
    numeric_widths = [float(child_width) for child_width in child_widths]
    available_width = float(width) - _horizontal_padding(styles.get("padding"))
    item_margin = _number(component.get("itemMargin"), default=0)
    total_width = sum(numeric_widths) + item_margin * (len(children) - 1)
    if total_width <= available_width:
        return
    overflow = int(total_width - available_width)
    flexible_children = [
        child
        for child in children
        if child.get("component") not in {"Image", "Divider", "Checkbox", "Progress"}
    ]
    for child in sorted(
        flexible_children,
        key=lambda item: float(_expanded_styles(item).get("width", 0)),
        reverse=True,
    ):
        if overflow <= 0:
            break
        child_styles = _expanded_styles(child)
        current_width = int(child_styles["width"])
        minimum_width = 24 if child.get("component") == "Text" else 32
        reduction = min(overflow, max(0, current_width - minimum_width))
        child_styles["width"] = current_width - reduction
        overflow -= reduction


def _compact_progress_detail_layouts(
    components: list[ComponentRow],
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> None:
    parent_by_child = {
        child_id: component
        for component in components
        for child_id in component.children
    }
    for component in components:
        if component.component_type != "Column" or len(component.children) < 3:
            continue
        progress_children = [
            component_by_id[child_id]
            for child_id in component.children
            if child_id in component_by_id
            and component_by_id[child_id].component_type == "ProgressUnit"
        ]
        if len(progress_children) != 1:
            continue
        progress = progress_children[0]
        progress_props = props_by_id[progress.component_id]
        if progress_props.get("state") != "numeric-single-caption":
            continue
        parent = parent_by_child.get(component.component_id)
        if parent is not None and any(_is_action_area_id(child) for child in parent.children):
            continue
        progress_props["state"] = "numeric-single"
        required_height = _required_column_height(component, component_by_id, props_by_id)
        if 0 < required_height <= 104:
            props_by_id[component.component_id]["height"] = required_height


def _compact_root_vertical_layouts(
    components: list[ComponentRow],
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> None:
    for component in components:
        if component.component_id != "content_root" or component.component_type != "Column":
            continue
        root_props = props_by_id[component.component_id]
        safe_height = _CARD_HEIGHT - _vertical_padding(root_props.get("padding"))
        if _required_column_height(component, component_by_id, props_by_id) <= safe_height:
            continue
        for child_id in component.children:
            child = component_by_id.get(child_id)
            if child is not None:
                _compact_single_todo_area(child, component_by_id, props_by_id)
        child_height = _children_height_sum(component, component_by_id, props_by_id)
        gap_count = max(0, len(component.children) - 1)
        if gap_count == 0 or child_height >= safe_height:
            continue
        current_margin = _number(root_props.get("itemMargin"), default=0)
        fitted_margin = int((safe_height - child_height) // gap_count)
        root_props["itemMargin"] = max(4, min(current_margin, fitted_margin))


def _compact_single_todo_area(
    component: ComponentRow,
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> None:
    if "todo" not in component.component_id.lower() or len(component.children) != 2:
        return
    if component.component_type != "Column":
        return
    props = props_by_id[component.component_id]
    height = props.get("height")
    if isinstance(height, int | float) and height > 56:
        props["height"] = 56
    props["itemMargin"] = min(_number(props.get("itemMargin"), default=4), 4)
    for child_id in component.children:
        child = component_by_id.get(child_id)
        if child is None:
            continue
        child_props = props_by_id[child_id]
        child_name = child_id.lower()
        if "title" in child_name:
            _cap_numeric_style(child_props, "height", 16)
        elif "item" in child_name:
            _cap_numeric_style(child_props, "height", 36)
            child_props["padding"] = _compact_vertical_padding(child_props.get("padding"), 6)


def _compact_vertical_padding(value: Any, maximum: int) -> Any:
    if isinstance(value, int | float):
        return min(value, maximum)
    if not isinstance(value, dict):
        return value
    compact = dict(value)
    for key in ("top", "bottom"):
        side = compact.get(key)
        if isinstance(side, int | float):
            compact[key] = min(side, maximum)
    return compact


def _required_column_height(
    component: ComponentRow,
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> int:
    child_height = _children_height_sum(component, component_by_id, props_by_id)
    if child_height <= 0:
        return 0
    item_margin = _number(props_by_id[component.component_id].get("itemMargin"), default=0)
    return child_height + item_margin * max(0, len(component.children) - 1)


def _children_height_sum(
    component: ComponentRow,
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> int:
    return sum(
        _estimated_component_height(component_by_id[child_id], props_by_id[child_id])
        for child_id in component.children
        if child_id in component_by_id
    )


def _estimated_component_height(component: ComponentRow, props: dict[str, Any]) -> int:
    if component.component_type == "ProgressUnit":
        return {
            "bar": 8,
            "numeric-single": 48,
            "numeric-single-caption": 74,
            "plain": 36,
        }.get(str(props.get("state", "bar")), 0)
    height = props.get("height")
    return int(height) if isinstance(height, int | float) else 0


def _vertical_padding(value: Any) -> int:
    if isinstance(value, int | float):
        return int(value * 2)
    if not isinstance(value, dict):
        return 0
    top = value.get("top", 0)
    bottom = value.get("bottom", 0)
    top_value = int(top) if isinstance(top, int | float) else 0
    bottom_value = int(bottom) if isinstance(bottom, int | float) else 0
    return top_value + bottom_value


def _fit_row_children(
    parent: ComponentRow,
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> None:
    parent_props = props_by_id[parent.component_id]
    parent_width = parent_props.get("width")
    if not isinstance(parent_width, int | float) or len(parent.children) < 2:
        return
    child_props = [
        props_by_id[child_id]
        for child_id in parent.children
        if child_id in component_by_id
    ]
    if len(child_props) != len(parent.children):
        return
    child_widths = [props.get("width") for props in child_props]
    if not all(isinstance(width, int | float) for width in child_widths):
        return
    numeric_widths = [float(width) for width in child_widths]
    available_width = float(parent_width) - _horizontal_padding(parent_props.get("padding"))
    item_margin = _number(parent_props.get("itemMargin"), default=0)
    total_width = sum(numeric_widths) + item_margin * (len(child_props) - 1)
    if total_width <= available_width:
        return
    if max(numeric_widths) == min(numeric_widths):
        fitted_width = int(
            (available_width - item_margin * (len(child_props) - 1)) // len(child_props)
        )
        if fitted_width > 0:
            for props in child_props:
                props["width"] = fitted_width
        return
    overflow = int(total_width - available_width)
    flexible_children = [
        (component_by_id[child_id], props_by_id[child_id])
        for child_id in parent.children
        if component_by_id[child_id].component_type not in {"Image", "Divider", "Checkbox"}
    ]
    for child, props in sorted(
        flexible_children,
        key=lambda item: float(item[1]["width"]),
        reverse=True,
    ):
        if overflow <= 0:
            break
        minimum = 24 if child.component_type == "Text" else 32
        current_width = int(props["width"])
        reduction = min(overflow, max(0, current_width - minimum))
        props["width"] = current_width - reduction
        overflow -= reduction


def _fit_column_child_widths(
    parent: ComponentRow,
    component_by_id: dict[str, ComponentRow],
    props_by_id: dict[str, dict[str, Any]],
) -> None:
    parent_props = props_by_id[parent.component_id]
    parent_width = parent_props.get("width")
    if not isinstance(parent_width, int | float):
        return
    available_width = int(parent_width - _horizontal_padding(parent_props.get("padding")))
    if available_width <= 0:
        return
    for child_id in parent.children:
        if child_id not in component_by_id:
            continue
        child_width = props_by_id[child_id].get("width")
        if isinstance(child_width, int | float) and child_width > available_width:
            props_by_id[child_id]["width"] = available_width


def _horizontal_padding(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value) * 2
    if not isinstance(value, dict):
        return 0.0
    left = value.get("left", 0)
    right = value.get("right", 0)
    left_value = float(left) if isinstance(left, int | float) else 0.0
    right_value = float(right) if isinstance(right, int | float) else 0.0
    return left_value + right_value


def _child_available_widths(components: list[ComponentRow]) -> dict[str, int]:
    available_widths: dict[str, int] = {}
    for component in components:
        width = component.props.get("width")
        if not isinstance(width, int | float):
            continue
        available = int(float(width) - _horizontal_padding(component.props.get("padding")))
        if available <= 0:
            continue
        for child in component.children:
            available_widths[child] = available
    return available_widths


def _convert_components(
    components: list[ComponentRow],
    *,
    event_candidates: list[Any] | None,
    available_widths: dict[str, int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for component in components:
        if component.component_type == "ActionUnit":
            output.extend(
                _convert_action_unit(
                    component,
                    event_candidates,
                    available_width=available_widths.get(component.component_id),
                )
            )
        elif component.component_type == "RingUnit":
            output.extend(_convert_ring_unit(component))
        elif component.component_type == "TimelineUnit":
            output.extend(_convert_timeline_unit(component))
        elif component.component_type == "ProgressUnit":
            output.extend(_convert_progress_unit(component))
        else:
            output.append(_convert_basic_component(component))
            if component.component_type == "Stack" and not component.children:
                output.append(_stack_spacer_text(component.component_id))
    return output


def _convert_basic_component(component: ComponentRow) -> dict[str, Any]:
    props = dict(component.props)
    result: dict[str, Any] = {
        "id": component.component_id,
        "component": component.component_type,
    }

    if component.component_type in _CONTAINER_COMPONENTS:
        result["children"] = component.children or _fallback_stack_children(component)
    if "content" in props:
        result["content"] = _convert_content(props.pop("content"))
    if "src" in props:
        result["src"] = props.pop("src")
    if "label" in props:
        result["label"] = props.pop("label")
    if "onClick" in props:
        result["onClick"] = _repair_event_binding_expressions(props.pop("onClick"))
    if "enabled" in props:
        result["enabled"] = props.pop("enabled")
    if "itemMargin" in props:
        result["itemMargin"] = props.pop("itemMargin")

    styles = _normalize_styles(component, props)
    if styles:
        result["styles"] = styles
    return result


def _fallback_stack_children(component: ComponentRow) -> list[str]:
    if component.component_type == "Stack":
        return [f"{component.component_id}_spacer_text"]
    return []


def _stack_spacer_text(component_id: str) -> dict[str, Any]:
    return {
        "id": f"{component_id}_spacer_text",
        "component": "Text",
        "content": ".",
        "styles": {"width": 1, "height": 1, "fontSize": 1, "fontColor": "#00FFFFFF"},
    }


def _normalize_styles(component: ComponentRow, props: dict[str, Any]) -> dict[str, Any]:
    styles = dict(props)
    if component.component_id == "root":
        styles["width"] = "matchParent"
        styles["height"] = "matchParent"
        styles.setdefault("borderRadius", 20)
        styles.setdefault("clip", True)
        styles.setdefault("alignContent", "center")
        styles.setdefault("linearGradient", _default_gradient())
        styles["linearGradient"] = _normalize_gradient(styles["linearGradient"])
        styles["constraintSize"] = {
            "minWidth": _CARD_WIDTH,
            "maxWidth": _CARD_WIDTH,
            "minHeight": _CARD_HEIGHT,
            "maxHeight": _CARD_HEIGHT,
        }
    elif _is_action_container(component):
        styles["height"] = 32
        styles["flexShrink"] = 0
    elif _is_body_content_area(component):
        _cap_numeric_style(styles, "height", 104)
    return styles


def _is_action_container(component: ComponentRow) -> bool:
    if component.component_type not in {"Column", "Row"}:
        return False
    return _is_action_area_id(component.component_id)


def _is_action_area_id(component_id: str) -> bool:
    component_id = component_id.lower()
    fixed_action_ids = {"action_area", "actions_area", "cta_area", "footer_action_area"}
    return component_id in fixed_action_ids or component_id.endswith("_action_area")


def _is_body_content_area(component: ComponentRow) -> bool:
    component_id = component.component_id.lower()
    return component_id in {"content_area", "body_area", "main_area"}


def _cap_numeric_style(styles: dict[str, Any], key: str, maximum: int) -> None:
    value = styles.get(key)
    if isinstance(value, (int, float)) and value > maximum:
        styles[key] = maximum


def _convert_content(content: Any) -> Any:
    if isinstance(content, dict) and isinstance(content.get("path"), str):
        return _binding(content["path"])
    if isinstance(content, str):
        return _repair_inline_binding_content(_normalize_text_join_separators(content))
    return content


def _normalize_text_join_separators(content: str) -> str:
    """Use the review-required separator for multiple inline text fragments."""
    if not any(separator in content for separator in ("·", "｜", "|")):
        return content
    return _TEXT_JOIN_SEPARATOR_RE.sub(" | ", content).strip()


def _binding(path: str) -> str:
    return "{{ ${" + path + "} }}"


def _repair_inline_binding_content(content: str) -> str:
    match = _BINDING_RE.match(content)
    if match:
        return _binding(match.group(1).strip())

    parts: list[str] = []
    last_index = 0
    for match in _INLINE_BINDING_RE.finditer(content):
        literal = content[last_index:match.start()]
        if literal:
            parts.append(_a2ui_string_literal(literal))
        parts.append("${" + match.group(1).strip() + "}")
        last_index = match.end()

    if not parts:
        return content

    suffix = content[last_index:]
    if suffix:
        parts.append(_a2ui_string_literal(suffix))
    return "{{ " + " + ".join(parts) + " }}"


def _a2ui_string_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return "'" + escaped + "'"


def _convert_action_unit(
    component: ComponentRow,
    event_candidates: list[Any] | None,
    *,
    available_width: int | None,
) -> list[dict[str, Any]]:
    props = component.props
    state = props.get("state")
    label = props.get("label")
    if not isinstance(label, str) or not label.strip():
        raise CompactDsl2x4ConversionError(
            f"{component.component_id}: ActionUnit requires label."
        )
    on_click = _resolved_on_click(props.get("onClick"), event_candidates)
    if not isinstance(on_click, list) or not on_click:
        raise CompactDsl2x4ConversionError(
            f"{component.component_id}: ActionUnit requires non-empty onClick."
        )

    ink = _action_ink(props.get("actionInk"))
    background = _action_background(props.get("actionSurface"), ink)
    if state == "tile":
        return _convert_tile_action_unit(component, label, on_click, ink, background)
    if state != "capsule":
        raise CompactDsl2x4ConversionError(
            f"{component.component_id}: unsupported ActionUnit state {state!r}."
        )

    width = _capsule_width(available_width)
    icon = props.get("icon")
    children = []
    output = []

    if isinstance(icon, str) and icon.strip():
        icon_id = f"{component.component_id}_icon"
        children.append(icon_id)
        output.append(
            {
                "id": icon_id,
                "component": "Image",
                "src": icon,
                "styles": {
                    "width": 18,
                    "height": 18,
                    "objectFit": "contain",
                    "flexShrink": 0,
                    "fillColor": ink,
                },
            }
        )

    text_id = f"{component.component_id}_text"
    children.append(text_id)
    output.append(
        {
            "id": text_id,
            "component": "Text",
            "content": label,
            "styles": {
                "fontSize": 14,
                "fontWeight": 700,
                "fontColor": ink,
                "maxLines": 1,
                "textOverflow": "ellipsis",
                "textAlign": "center",
                "height": 20,
                "width": max(1, width - 42) if len(children) > 1 else max(1, width - 28),
            },
        }
    )

    row = {
        "id": component.component_id,
        "component": "Row",
        "children": children,
        "itemMargin": 4,
        "onClick": on_click,
        "styles": {
            "width": width,
            "height": 32,
            "borderRadius": 16,
            "backgroundColor": background,
            "justifyContent": "center",
            "alignItems": "center",
            "flexShrink": 0,
        },
    }
    return [row, *output]


def _convert_tile_action_unit(
    component: ComponentRow,
    label: str,
    on_click: list[Any],
    ink: str,
    background: str,
) -> list[dict[str, Any]]:
    icon = _required_string(component.props.get("icon"), component.component_id, "icon")
    width = _clamped_number(component.props.get("width"), default=72, minimum=64, maximum=80)
    height = _clamped_number(component.props.get("height"), default=112, minimum=80, maximum=112)
    icon_id = f"{component.component_id}_icon"
    text_id = f"{component.component_id}_text"
    return [
        {
            "id": component.component_id,
            "component": "Column",
            "children": [icon_id, text_id],
            "itemMargin": 8,
            "onClick": on_click,
            "styles": {
                "width": width,
                "height": height,
                "padding": 8,
                "borderRadius": 12,
                "backgroundColor": background,
                "justifyContent": "center",
                "alignItems": "center",
                "flexShrink": 0,
            },
        },
        {
            "id": icon_id,
            "component": "Image",
            "src": icon,
            "styles": {
                "width": 20,
                "height": 20,
                "objectFit": "contain",
                "fillColor": ink,
                "flexShrink": 0,
            },
        },
        {
            "id": text_id,
            "component": "Text",
            "content": label,
            "styles": {
                "width": width - 16,
                "height": 36,
                "fontSize": 12,
                "fontWeight": 600,
                "fontColor": ink,
                "maxLines": 2,
                "textOverflow": "ellipsis",
                "textAlign": "center",
            },
        },
    ]


def _capsule_width(available_width: int | None) -> int:
    if available_width is None:
        return 136
    return max(1, min(136, available_width))


def _clamped_number(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    number = _number(value, default=default)
    return max(minimum, min(maximum, number))


def _convert_timeline_unit(component: ComponentRow) -> list[dict[str, Any]]:
    height = _number(component.props.get("height"), default=68)
    width = _number(component.props.get("width"), default=16)
    color = component.props.get("color", _TIMELINE_UNIT_DEFAULT_COLOR)
    line_color = component.props.get("lineColor", _TIMELINE_UNIT_DEFAULT_LINE_COLOR)
    if not isinstance(color, str) or not color.startswith("#"):
        color = _TIMELINE_UNIT_DEFAULT_COLOR
    if not isinstance(line_color, str) or not line_color.startswith("#"):
        line_color = _TIMELINE_UNIT_DEFAULT_LINE_COLOR

    dot_id = f"{component.component_id}_dot"
    line_id = f"{component.component_id}_line"
    return [
        {
            "id": component.component_id,
            "component": "Column",
            "children": [dot_id, line_id],
            "styles": {
                "width": width,
                "height": height,
                "alignItems": "center",
                "justifyContent": "start",
                "flexShrink": 0,
            },
        },
        {
            "id": dot_id,
            "component": "Text",
            "content": "",
            "styles": {
                "width": 14,
                "height": 14,
                "borderRadius": 7,
                "borderWidth": 4,
                "borderColor": color,
                "backgroundColor": "#00FFFFFF",
                "flexShrink": 0,
            },
        },
        {
            "id": line_id,
            "component": "Divider",
            "styles": {
                "width": 1,
                "height": max(height - 16, 1),
                "vertical": True,
                "color": line_color,
                "strokeWidth": 1,
                "flexShrink": 0,
            },
        },
    ]


def _resolved_on_click(value: Any, event_candidates: list[Any] | None) -> Any:
    normalized_value = _repair_event_binding_expressions(value)
    if event_candidates:
        allowed_handlers = [
            handler
            for candidate in event_candidates
            for handler in [_event_candidate_to_handler(candidate)]
            if handler
        ]
        if not allowed_handlers:
            return normalized_value
        if _handler_allowed(normalized_value, allowed_handlers):
            return normalized_value
        return [_repair_event_binding_expressions(allowed_handlers[0])]
    return normalized_value


def _repair_event_binding_expressions(value: Any) -> Any:
    """Convert legacy template strings in action args back to Compact DSL path objects."""
    if isinstance(value, str):
        match = _BINDING_RE.match(value)
        if match:
            return {"path": match.group(1).strip()}
        return value
    if isinstance(value, list):
        return [_repair_event_binding_expressions(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _repair_event_binding_expressions(item)
            for key, item in value.items()
        }
    return value


def _handler_allowed(value: Any, allowed_handlers: list[dict[str, Any]]) -> bool:
    if not isinstance(value, list):
        return False
    allowed_keys = {_event_handler_key(candidate) for candidate in allowed_handlers}
    return any(
        isinstance(handler, dict) and _event_handler_key(handler) in allowed_keys
        for handler in value
    )


def _event_handler_key(handler: dict[str, Any]) -> str:
    return json.dumps(
        {
            "call": handler.get("call"),
            "args": handler.get("args", {}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _event_candidate_to_handler(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "model_dump"):
        candidate = candidate.model_dump(mode="json", exclude_none=True)
    if not isinstance(candidate, dict):
        return {}
    action = candidate.get("action")
    if isinstance(action, dict):
        candidate = action
    call = candidate.get("call")
    if not isinstance(call, str) or not call:
        return {}
    return {
        "call": call,
        "args": candidate.get("args", {}),
    }


def _action_ink(value: Any) -> str:
    if isinstance(value, str) and value.startswith("#"):
        return value
    return "#FF0A59F7"


def _action_background(value: Any, ink: str) -> str:
    if isinstance(value, str) and value.startswith("#"):
        return value
    if value == "white":
        return "#33FFFFFF"
    return _color_with_alpha(ink, "1A")


def _color_with_alpha(color: str, alpha: str) -> str:
    if len(color) == 9:
        return f"#{alpha}{color[-6:]}"
    if len(color) == 7:
        return f"#{alpha}{color[-6:]}"
    return "#1A0A59F7"


def _convert_ring_unit(component: ComponentRow) -> list[dict[str, Any]]:
    props = component.props
    state = props.get("state")
    size = _number(props.get("size"), default=80)
    value = _progress_value(props.get("value"))
    total = _progress_value(props.get("total", 100))
    color = _ring_color(props.get("color"))
    stroke_width = _ring_stroke_width(size)

    if state == "center-text":
        return _ring_center_text(component, size, value, total, color, stroke_width)
    if state == "center-icon":
        return _ring_center_icon(component, size, value, total, color, stroke_width)
    if state == "center-icon-below-text":
        return _ring_center_icon_below_text(
            component,
            size,
            value,
            total,
            color,
            stroke_width,
        )
    raise CompactDsl2x4ConversionError(
        f"{component.component_id}: unsupported RingUnit state {state!r}."
    )


def _ring_center_text(
    component: ComponentRow,
    size: int,
    value: Any,
    total: Any,
    color: str,
    stroke_width: int,
) -> list[dict[str, Any]]:
    reading = _reading_text(component.props.get("reading"), fallback=value)
    return [
        _ring_stack(
            component.component_id,
            [f"{component.component_id}_ring", f"{component.component_id}_reading"],
            size,
        ),
        _ring_progress(f"{component.component_id}_ring", value, total, size, color, stroke_width),
        {
            "id": f"{component.component_id}_reading",
            "component": "Text",
            "content": reading,
            "styles": {
                "width": size,
                "height": 24,
                "fontSize": _ring_font_size(size),
                "fontWeight": 800,
                "fontColor": "#E5000000",
                "maxLines": 1,
                "textOverflow": "clip",
                "textAlign": "center",
            },
        },
    ]


def _ring_center_icon(
    component: ComponentRow,
    size: int,
    value: Any,
    total: Any,
    color: str,
    stroke_width: int,
) -> list[dict[str, Any]]:
    icon = _required_string(component.props.get("centerIcon"), component.component_id, "centerIcon")
    icon_size = max(16, min(28, size // 2))
    return [
        _ring_stack(
            component.component_id,
            [f"{component.component_id}_ring", f"{component.component_id}_icon"],
            size,
        ),
        _ring_progress(f"{component.component_id}_ring", value, total, size, color, stroke_width),
        {
            "id": f"{component.component_id}_icon",
            "component": "Image",
            "src": icon,
            "styles": {
                "width": icon_size,
                "height": icon_size,
                "objectFit": "contain",
                "flexShrink": 0,
            },
        },
    ]


def _ring_center_icon_below_text(
    component: ComponentRow,
    size: int,
    value: Any,
    total: Any,
    color: str,
    stroke_width: int,
) -> list[dict[str, Any]]:
    stack_id = f"{component.component_id}_stack"
    text_id = f"{component.component_id}_reading"
    return [
        {
            "id": component.component_id,
            "component": "Column",
            "children": [stack_id, text_id],
            "itemMargin": 2,
            "styles": {
                "width": size,
                "height": size + 18,
                "justifyContent": "center",
                "alignItems": "center",
                "flexShrink": 0,
            },
        },
        *_ring_center_icon(
            ComponentRow(
                stack_id,
                "RingUnit",
                {
                    **component.props,
                    "state": "center-icon",
                    "size": size,
                },
                [],
            ),
            size,
            value,
            total,
            color,
            stroke_width,
        ),
        {
            "id": text_id,
            "component": "Text",
            "content": _reading_text(component.props.get("reading"), fallback=value),
            "styles": {
                "width": size,
                "height": 16,
                "fontSize": 10,
                "fontWeight": 700,
                "fontColor": "#E5000000",
                "maxLines": 1,
                "textOverflow": "clip",
                "textAlign": "center",
            },
        },
    ]


def _ring_stack(component_id: str, children: list[str], size: int) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Stack",
        "children": children,
        "styles": {
            "width": size,
            "height": size,
            "alignContent": "center",
            "flexShrink": 0,
        },
    }


def _ring_progress(
    component_id: str,
    value: Any,
    total: Any,
    size: int,
    color: str,
    stroke_width: int,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Progress",
        "value": value,
        "total": total,
        "styles": {
            "type": "ring",
            "width": size,
            "height": size,
            "strokeWidth": stroke_width,
            "backgroundColor": "#FFE2E3E5",
            "color": color,
            "flexShrink": 0,
        },
    }


def _convert_progress_unit(component: ComponentRow) -> list[dict[str, Any]]:
    props = component.props
    state = props.get("state", "bar")
    value = _progress_value(props.get("value"))
    total = _progress_value(props.get("total", 100))
    color = _progress_color(props.get("color"))

    if state == "bar":
        return [_linear_progress(component.component_id, value, total, color)]
    if state in {"numeric-single", "numeric-single-caption"}:
        return _progress_numeric_single(component, value, total, color, state)
    if state == "plain":
        return _progress_plain(component, value, total, color)
    raise CompactDsl2x4ConversionError(
        f"{component.component_id}: unsupported ProgressUnit state {state!r}."
    )


def _progress_numeric_single(
    component: ComponentRow,
    value: Any,
    total: Any,
    color: str,
    state: str,
) -> list[dict[str, Any]]:
    reading = _reading_text(component.props.get("reading"), fallback=value)
    children = [f"{component.component_id}_reading", f"{component.component_id}_bar"]
    output = [
        _progress_column(component.component_id, children),
        {
            "id": f"{component.component_id}_reading",
            "component": "Text",
            "content": reading,
            "styles": _text_style(26, 800, height=32),
        },
        _linear_progress(f"{component.component_id}_bar", value, total, color),
    ]
    if state == "numeric-single-caption" and "caption" in component.props:
        caption_id = f"{component.component_id}_caption"
        output[0]["children"].append(caption_id)
        output.append(
            {
                "id": caption_id,
                "component": "Text",
                "content": _convert_content(component.props["caption"]),
                "styles": _text_style(12, 400, color="#99000000", height=18),
            }
        )
    return output


def _progress_plain(
    component: ComponentRow,
    value: Any,
    total: Any,
    color: str,
) -> list[dict[str, Any]]:
    label = _convert_content(component.props.get("label", "进度"))
    return [
        _progress_column(
            component.component_id,
            [f"{component.component_id}_label", f"{component.component_id}_bar"],
        ),
        {
            "id": f"{component.component_id}_label",
            "component": "Text",
            "content": label,
            "styles": _text_style(14, 700, height=20),
        },
        _linear_progress(f"{component.component_id}_bar", value, total, color),
    ]


def _progress_column(component_id: str, children: list[str]) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Column",
        "children": children,
        "itemMargin": 8,
        "styles": {
            "width": "matchParent",
            "justifyContent": "start",
            "alignItems": "start",
            "flexShrink": 0,
        },
    }


def _linear_progress(component_id: str, value: Any, total: Any, color: str) -> dict[str, Any]:
    return {
        "id": component_id,
        "component": "Progress",
        "value": value,
        "total": total,
        "styles": {
            "type": "linear",
            "width": "matchParent",
            "height": 8,
            "borderRadius": 4,
            "backgroundColor": "#19000000",
            "color": color,
            "flexShrink": 0,
        },
    }


def _text_style(
    font_size: int,
    font_weight: int,
    *,
    color: str = "#E5000000",
    height: int = 20,
) -> dict[str, Any]:
    return {
        "fontSize": font_size,
        "fontWeight": font_weight,
        "fontColor": color,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "textAlign": "start",
        "width": "matchParent",
        "height": height,
    }


def _reading_text(reading: Any, *, fallback: Any) -> Any:
    if isinstance(reading, dict):
        path = reading.get("path")
        unit = reading.get("unit", "")
        if isinstance(path, str):
            text = _binding(path)
            if isinstance(unit, str) and unit:
                return text + unit
            return text
    return fallback


def _progress_value(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("path"), str):
        return _binding(value["path"])
    if value is None:
        raise CompactDsl2x4ConversionError("progress value must not be empty.")
    return value


def _number(value: Any, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _ring_font_size(size: int) -> int:
    if size >= 92:
        return 28
    if size >= 80:
        return 22
    if size >= 52:
        return 16
    return 10


def _ring_stroke_width(size: int) -> int:
    if size >= 92:
        return 8
    if size >= 80:
        return 7
    if size >= 52:
        return 6
    return 5


def _ring_color(value: Any) -> str:
    mapping = {
        "green": "#FF64BB5C",
        "blue": "#FF3FBAFF",
        "orange": "#FFFF8616",
        "red": "#FFE94B6A",
        "purple": "#FF3FBAFF",
        "multi_color_04": "#FF64BB5C",
        "multi_color_10": "#FFE94B6A",
    }
    if isinstance(value, str) and value.startswith("#"):
        return value
    if isinstance(value, str):
        return mapping.get(value, "#FF64BB5C")
    return "#FF64BB5C"


def _progress_color(value: Any) -> str:
    mapping = {
        "green": "#FF64BB5C",
        "blue": "#FF0A59F7",
        "orange": "#FFFF8616",
        "red": "#FFE94B6A",
        "purple": "#FF0A59F7",
        "multi_color_04": "#FF0A59F7",
        "multi_color_10": "#FFE94B6A",
    }
    if isinstance(value, str) and value.startswith("#"):
        return value
    if isinstance(value, str):
        return mapping.get(value, "#FF0A59F7")
    return "#FF0A59F7"


def _required_string(value: Any, component_id: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompactDsl2x4ConversionError(f"{component_id}: {field} must be a non-empty string.")
    return value


def _build_data_model(data_rows: list[list[Any]]) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for path, value in data_rows:
        _set_path(root, path, value)
    return root or {"data": {}}


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    keys = [part for part in path.strip("/").split("/") if part]
    if not keys:
        return
    current: Any = root
    for key in keys[:-1]:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[keys[-1]] = value


def _create_surface(surface_id: str) -> dict[str, Any]:
    return {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": surface_id,
            "catalogId": _CATALOG_ID,
        },
    }


def _update_components(surface_id: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": surface_id,
            "root": "root",
            "components": components,
        },
    }


def _update_data_model(surface_id: str, data_model: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": surface_id,
            "path": "/",
            "value": data_model,
        },
    }


def _default_gradient() -> dict[str, Any]:
    return copy.deepcopy(_LIGHT_GRADIENTS["blue"])


def _normalize_gradient(value: Any) -> Any:
    if not isinstance(value, dict):
        return _default_gradient()
    colors = value.get("colors")
    if not isinstance(colors, list):
        return value
    normalized_colors = tuple(
        str(item[0]).upper()
        for item in colors
        if isinstance(item, list) and item
    )
    legacy_near_white = (
        "#FFF6FAFF",
        "#FFFCFDFF",
        "#FFFFFFFF",
    )
    if normalized_colors == legacy_near_white:
        return _default_gradient()
    color_text = " ".join(normalized_colors)
    if any(token in color_text for token in ("#FF8E2DE2", "#FFA94BFF", "#FFC471ED")):
        return {
            "angle": 180,
            "colors": [
                ["#FFDCE9FF", 0],
                ["#FFF3F7FF", 0.58],
                ["#FFFFFFFF", 1],
            ],
        }
    return value


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Convert 2x4 compact DSL to A2UI JSONL.")
    parser.add_argument(
        "input",
        nargs="?",
        help="Input compact DSL file. stdin is used if omitted.",
    )
    args = parser.parse_args()
    source = open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    print(convert_compact_dsl_2x4_to_a2ui(source))
