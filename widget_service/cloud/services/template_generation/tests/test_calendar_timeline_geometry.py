"""日程详情分组、保留的时间轴及最终预览 A2UI 几何回归。"""

from __future__ import annotations

from typing import Any

import pytest

from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan import preview_dataset
from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.tests.test_calendar_requested_case_templates import _walk

_DETAIL_TEMPLATES = (
    "ScheduleOverviewLocationDescriptionEndFull@1",
    "ScheduleOverviewNextEventLocationFull@1",
    "ScheduleOverviewTimezoneTimeFull@1",
    "ScheduleOverviewDateLocationFull@1",
)

_TEMPLATES = (
    "ScheduleOverviewLocationDescriptionEndFull@1",
    "ScheduleOverviewEventCountDetailsHero@1",
    "ScheduleOverviewDatedAllDayHero@1",
    "ScheduleOverviewTimezoneDateEndFull@1",
    "ScheduleOverviewTimezoneAllDayFull@1",
    "ScheduleOverviewReminderHero@1",
    *_DETAIL_TEMPLATES[1:],
)
_TIMEZONE_TEMPLATES = frozenset(_TEMPLATES[3:5])


def _options(node: Nested2Node) -> dict[str, Any]:
    options = next((value for value in reversed(node.values) if isinstance(value, dict)), None)
    assert isinstance(options, dict)
    return options


def _texts(node: Nested2Node) -> list[Nested2Node]:
    result = [node] if node.component_type == "Text" else []
    for child in node.children:
        result.extend(_texts(child))
    return result


def _assert_detail_geometry(root: Nested2Node, *, with_icon: bool) -> None:
    assert root.component_type == "Column"
    assert _options(root).get("width") == "matchParent"
    assert _options(root).get("justifyContent") == "spaceBetween"
    assert len(root.children) == 2
    top, bottom = root.children
    assert top.component_type == bottom.component_type == "Column"
    assert _options(top).get("width") == _options(bottom).get("width") == "matchParent"
    assert _options(top).get("itemMargin") == 8
    assert _options(bottom).get("itemMargin") == 0
    assert len(top.children) == len(bottom.children) == 2
    header, main = top.children
    assert header.component_type == "Row"
    assert _options(header).get("width") == "matchParent"
    assert _options(header).get("height") == 20
    assert _options(header).get("itemMargin") == 4
    assert len(header.children) == (2 if with_icon else 1)
    label = header.children[0]
    label_options = _options(label)
    assert label.component_type == "Text"
    assert label_options.get("layoutWeight") == 1
    assert "width" not in label_options
    assert label_options.get("height") == 16
    assert label_options.get("fontSize") == 12
    assert label_options.get("fontWeight") == 700
    constraints = label_options.get("constraintSize")
    assert isinstance(constraints, dict)
    assert constraints.get("minWidth") == 0
    if with_icon:
        icon = header.children[1]
        assert icon.component_type == "Image"
        assert _options(icon).get("width") == _options(icon).get("height") == 20
        assert _options(icon).get("flexShrink") == 0
    assert main.component_type == "Text"
    assert _options(main).get("height") == 28
    assert _options(main).get("fontSize") == 20
    assert _options(main).get("fontWeight") == 700
    for auxiliary in bottom.children:
        assert auxiliary.component_type == "Text"
        options = _options(auxiliary)
        assert options.get("height") == 16
        assert options.get("fontSize") == 12
        assert options.get("minFontSize") == 10
        assert options.get("fontWeight") == 400
    for text in _texts(root):
        assert _options(text).get("maxLines") == 1
        assert _options(text).get("textOverflow") == "ellipsis"
    assert not any(node.component_type == "Divider" for node in _walk(root))


def _assert_timeline(row: Nested2Node, template_id: str) -> None:
    assert row.component_type == "Row"
    assert len(row.children) == 2
    rail, content = row.children
    assert rail.component_type == content.component_type == "Column"
    assert _options(rail).get("width") == 8
    content_options = _options(content)
    assert "width" not in content_options
    assert "layoutWeight" not in content_options
    texts = _texts(content)
    timezone = template_id in _TIMEZONE_TEMPLATES
    assert len(texts) == (4 if timezone else 3)
    assert _options(texts[0]).get("height") == 20
    assert _options(texts[0]).get("fontSize") == 14
    reminder = template_id == "ScheduleOverviewReminderHero@1"
    assert _options(texts[0]).get("fontWeight") == (700 if reminder else 500)
    for index, text in enumerate(texts):
        options = _options(text)
        assert "width" not in options
        assert options.get("maxLines") == 1
        assert options.get("textOverflow") == "ellipsis"
        if index > 0:
            assert options.get("height") == 14
            assert options.get("fontSize") == 10
            assert options.get("fontWeight") == 400
    if reminder:
        assert content_options.get("height") == "matchParent"
        assert isinstance(_options(row).get("height"), str)
    else:
        height = 70 if timezone else 54
        assert _options(row).get("height") == height
        assert _options(rail).get("height") == height
        padding = _options(rail).get("padding")
        assert isinstance(padding, dict)
        assert padding.get("bottom") == 2
        assert _options(rail.children[-1]).get("height") == (50 if timezone else 34)
        if not timezone:
            assert content_options.get("height") == 54
    if template_id == "ScheduleOverviewEventCountDetailsHero@1":
        assert "width" not in _options(row)


@pytest.mark.parametrize("template_id", _TEMPLATES)
@pytest.mark.parametrize("with_props", (False, True))
def test_calendar_keeps_user_geometry(template_id: str, with_props: bool) -> None:
    registry = get_cardplan_registry()
    definition = registry.require_template(template_id)
    variant = definition.variants[0]
    bindings: dict[str, str] = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.calendar" + binding.path.replace("/", ".") + "}"
    params: dict[str, str] = {}
    properties = variant.parameters_schema.get("properties")
    assert isinstance(properties, dict)
    if with_props:
        if "headerLabel" in properties:
            params["headerLabel"] = "日程安排"
        if "calendarIcon" in properties:
            params["calendarIcon"] = "resources/base/media/calendar_fill.svg"
    root = _instantiate_blueprint(
        variant.root, params, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    if template_id in _DETAIL_TEMPLATES:
        _assert_detail_geometry(root, with_icon=with_props)
    else:
        _assert_timeline(root.children[-1], template_id)


@pytest.fixture(scope="module")
def preview_messages() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for case in build_template_preview_cases():
        if case.template_id in _TEMPLATES:
            result[case.template_id] = list(case.messages)
    assert set(result) == set(_TEMPLATES)
    return result


def _node_from_components(
    component_id: str, components: dict[str, dict[str, Any]],
) -> Nested2Node:
    component = components.get(component_id)
    assert isinstance(component, dict)
    kind = component.get("component")
    assert isinstance(kind, str)
    styles = component.get("styles")
    assert isinstance(styles, dict)
    options = dict(styles)
    if "itemMargin" in component:
        options["itemMargin"] = component.get("itemMargin")
    children = component.get("children", [])
    assert isinstance(children, list)
    nodes = tuple(_node_from_components(child, components) for child in children)
    return Nested2Node(kind, (component.get("content"), options), nodes)


def _components_by_id(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    assert len(messages) == 3
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    by_id: dict[str, dict[str, Any]] = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        by_id[component_id] = component
    return by_id


def _detail_content(by_id: dict[str, dict[str, Any]]) -> Nested2Node:
    slot = by_id.get("template_root")
    assert isinstance(slot, dict)
    children = slot.get("children")
    assert isinstance(children, list) and len(children) == 1
    return _node_from_components(children[0], by_id)


@pytest.mark.parametrize("template_id", _TEMPLATES)
def test_calendar_final_a2ui_keeps_geometry(
    template_id: str, preview_messages: dict[str, list[dict[str, Any]]],
) -> None:
    messages = preview_messages.get(template_id)
    assert isinstance(messages, list)
    by_id = _components_by_id(messages)
    if template_id in _DETAIL_TEMPLATES:
        content = _detail_content(by_id)
        header = content.children[0].children[0]
        _assert_detail_geometry(content, with_icon=len(header.children) == 2)
        return
    timelines: list[Nested2Node] = []
    for component in by_id.values():
        if component.get("component") != "Row":
            continue
        children = component.get("children")
        if not isinstance(children, list) or len(children) != 2:
            continue
        rail = by_id.get(children[0])
        assert isinstance(rail, dict)
        styles = rail.get("styles")
        assert isinstance(styles, dict)
        if rail.get("component") == "Column" and styles.get("width") == 8:
            component_id = component.get("id")
            assert isinstance(component_id, str)
            timelines.append(_node_from_components(component_id, by_id))
    assert len(timelines) == 1
    _assert_timeline(timelines[0], template_id)


@pytest.mark.parametrize("template_id", _DETAIL_TEMPLATES)
@pytest.mark.parametrize("header_label", [None, "跨时区项目联合评审及下一阶段计划安排"])
@pytest.mark.parametrize("with_icon", [False, True])
def test_detail_final_a2ui_reserves_icon_space_for_long_headers(
    monkeypatch: pytest.MonkeyPatch,
    template_id: str,
    header_label: str | None,
    with_icon: bool,
) -> None:
    props: dict[str, Any] = {}
    if header_label is not None:
        props["headerLabel"] = header_label
    if with_icon:
        props["calendarIcon"] = "resources/base/media/calendar_fill.svg"
    monkeypatch.setattr(preview_dataset, "_template_parameters", lambda _definition: props)
    registry = get_cardplan_registry()
    definition = registry.require_template(template_id)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    preview = preview_dataset._build_case("detail-header", definition, profile, registry)
    content = _detail_content(_components_by_id(list(preview.messages)))
    _assert_detail_geometry(content, with_icon=with_icon)
    label = content.children[0].children[0].children[0]
    assert label.values[0] == (header_label or "下一个日程")
