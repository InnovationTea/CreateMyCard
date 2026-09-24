"""日程详情分组、保留的时间轴及最终预览 A2UI 几何回归。

九个日历模板在无参 / 带参（headerLabel、calendarIcon 按 variant 参数
schema 就绪时注入）下的完整蓝图渲染已固化为场景金样（Layer C，
``calendar_geometry__*``）：详情分组的两段 Column 结构、页眉可选图标
占位、时间轴轨道宽度、行高与逐层文本样式由快照整体冻结。最终预览 A2UI
的逐模板几何断言与 Layer A 模板金样逐字节重复，已退役。通过 monkeypatch
preview_dataset 注入参数的预览构建路径仍为内联精度断言。
"""

from __future__ import annotations

from typing import Any

import pytest

from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan import preview_dataset
from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)
from services.template_generation.tests.test_calendar_requested_case_templates import (
    _node_payload,
    _template_slug,
    _walk,
)

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


_OPTIONAL_HEADER_PARAMS = {
    "headerLabel": "日程安排",
    "calendarIcon": "resources/base/media/calendar_fill.svg",
}


def _with_params(variant: Any) -> dict[str, str]:
    params: dict[str, str] = {}
    properties = variant.parameters_schema.get("properties")
    assert isinstance(properties, dict)
    for name, value in _OPTIONAL_HEADER_PARAMS.items():
        if name in properties:
            params[name] = value
    return params


def _geometry_payload(template_id: str) -> dict[str, Any]:
    registry = get_cardplan_registry()
    definition = registry.require_template(template_id)
    variant = definition.variants[0]
    bindings = {
        name: "${data.calendar" + binding.path.replace("/", ".") + "}"
        for name, binding in definition.bindings.items()
    }
    theme = registry.theme_reference_values("2x2-two-support")
    params = _with_params(variant)
    return {
        "templateId": template_id,
        "noParams": _node_payload(_instantiate_blueprint(variant.root, {}, bindings, theme)),
        "withParams": {
            "appliedParams": params,
            "root": _node_payload(
                _instantiate_blueprint(variant.root, params, bindings, theme)
            ),
        },
    }


def _register_geometry_scenarios() -> None:
    for template_id in _TEMPLATES:
        def _build(template_id: str = template_id) -> dict[str, Any]:
            return _geometry_payload(template_id)

        scenario(f"calendar_geometry__{_template_slug(template_id)}")(_build)


_register_geometry_scenarios()


@pytest.mark.parametrize("template_id", _TEMPLATES)
def test_calendar_geometry_matches_golden_scenarios(template_id: str) -> None:
    assert_golden_scenario(f"calendar_geometry__{_template_slug(template_id)}")


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
