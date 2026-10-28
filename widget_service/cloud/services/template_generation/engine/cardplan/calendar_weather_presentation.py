"""仅调整已明确识别的日程与基础天气组合，不增减展示字段。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import Any

from services.template_generation.engine.tersel_converter import Nested2Node

from .parser import ParsedCall

_LAYOUT = "WideTwoFullLayout@1"
_WEATHER = "WeatherOverviewFull@1"
_CALENDAR = "ScheduleOverviewDateTitleFull@1"
_WEATHER_NODES = frozenset({"Row", "Column", "Stack", "Text"})
_INTERACTIVE_NODES = frozenset(
    {"Button", "Checkbox", "PillAction", "IconAction", "LargeIconAction", "ActionTile"}
)
_FIELD_ROLES = (
    ("/location/districtName", "city"),
    ("/location/prefectureName", "city"),
    ("/current/temperatureText", "temperature"),
    ("/current/condition", "condition"),
)


def center_calendar_weather_full(
    expanded: Nested2Node, composition: ParsedCall, *, size: str
) -> Nested2Node:
    """准确命中且只有三个天气绑定时重排；其它已展开产物原样返回。"""
    if size != "2x4":
        return expanded
    if not _is_target_composition(composition):
        return expanded
    if expanded.component_type != "WideTwoFullLayout" or len(expanded.children) != 2:
        return expanded
    if _has_image_or_action(expanded):
        return expanded
    weather_index = next(
        index for index, child in enumerate(composition.children) if child.name == _WEATHER
    )
    weather = expanded.children[weather_index]
    texts = _basic_weather_texts(weather)
    if not texts:
        return expanded
    centered = _centered_weather(weather, texts)
    children = list(expanded.children)
    children[weather_index] = centered
    return replace(expanded, children=tuple(children))


def _is_target_composition(composition: ParsedCall) -> bool:
    if composition.kind != "template" or composition.name != _LAYOUT:
        return False
    if len(composition.children) != 2:
        return False
    for child in composition.children:
        if child.kind != "template" or child.children:
            return False
    return {child.name for child in composition.children} == {_WEATHER, _CALENDAR}


def _walk(node: Nested2Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _has_action_value(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.startswith("on") or key in {"action", "actionId", "events"}:
                return True
            if _has_action_value(item):
                return True
    elif isinstance(value, (tuple, list)):
        return any(_has_action_value(item) for item in value)
    return False


def _has_image_or_action(root: Nested2Node) -> bool:
    for node in _walk(root):
        if node.component_type == "Image" or node.component_type in _INTERACTIVE_NODES:
            return True
        if _has_action_value(node.values):
            return True
    return False


def _binding_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        for path in re.findall(r"\$\{([^{}]*)\}", value):
            if path.startswith("data."):
                path = "/" + path.replace(".", "/")
            paths.append(path)
    elif isinstance(value, dict):
        for item in value.values():
            paths.extend(_binding_paths(item))
    elif isinstance(value, (tuple, list)):
        for item in value:
            paths.extend(_binding_paths(item))
    return paths


def _basic_weather_texts(weather: Nested2Node) -> dict[str, Nested2Node]:
    texts: dict[str, Nested2Node] = {}
    roots: set[str] = set()
    all_paths: list[str] = []
    text_paths: list[str] = []
    for node in _walk(weather):
        if node.component_type not in _WEATHER_NODES:
            return {}
        all_paths.extend(_binding_paths(node.values))
        if node.component_type != "Text":
            continue
        if not node.values or not isinstance(node.values[0], str):
            return {}
        paths = _binding_paths(node.values[0])
        if len(paths) != 1 or node.children:
            return {}
        path = paths[0]
        matched = False
        for suffix, role in _FIELD_ROLES:
            if not path.startswith("/data/") or not path.endswith(suffix):
                continue
            if role in texts:
                return {}
            roots.add(path.removesuffix(suffix))
            texts[role] = node
            text_paths.append(path)
            matched = True
            break
        if not matched:
            return {}
    if len(roots) != 1 or set(texts) != {"city", "temperature", "condition"}:
        return {}
    if Counter(all_paths) != Counter(text_paths):
        return {}
    return texts


def _with_options(node: Nested2Node, additions: dict[str, Any]) -> Nested2Node:
    values = list(node.values)
    index = next((i for i, value in enumerate(values) if isinstance(value, dict)), None)
    options = dict(values[index]) if index is not None else {}
    options.update(additions)
    if index is None:
        values.append(options)
    else:
        values[index] = options
    return replace(node, values=tuple(values))


def _centered_weather(weather: Nested2Node, texts: dict[str, Nested2Node]) -> Nested2Node:
    children = []
    for role, height, font_size, weight in (
        ("city", 16, 12, 500),
        ("temperature", 58, 38, 700),
        ("condition", 16, 12, 400),
    ):
        text = texts.get(role)
        assert text is not None  # 调用前已验证三个角色恰好各一个。
        children.append(
            _with_options(
                text,
                {
                    "width": "matchParent",
                    "height": height,
                    "fontSize": font_size,
                    "fontWeight": weight,
                    "textAlign": "center",
                    "maxLines": 1,
                    "textOverflow": "ellipsis",
                },
            )
        )
    root = _with_options(
        weather,
        {
            "width": "matchParent",
            "height": 102,
            "itemMargin": 6,
            "justifyContent": "spaceBetween",
            "alignItems": "center",
        },
    )
    return replace(root, component_type="Column", children=tuple(children))
