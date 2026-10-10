"""分组会议详情的文本契约、可选时间及实际 A2UI 回归。"""

from __future__ import annotations

import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from models.generation import TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.scope_planner import (
    _template_has_satisfiable_variant,
)
from services.template_generation.engine.cardplan.compiler import (
    _serialize_effective_document,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_case,
    _build_data_schema,
    _preview_root,
)
from services.template_generation.engine.cardplan.provider_bundle import provider_template_admission
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import convert_tersel_to_a2ui
from services.template_generation.tests.test_calendar_requested_case_templates import (
    _expanded,
    _options,
    _walk,
)

_TEMPLATE_ID = "ScheduleOverviewMeetingSenderFull@1"


@pytest.mark.parametrize("params", [{}, {"title": 42}, {"headerLabel": "今日日程"}])
def test_meeting_requires_string_title_and_rejects_legacy_header(params: dict[str, Any]) -> None:
    definition = get_cardplan_registry().require_template(_TEMPLATE_ID)
    schema = definition.variants[0].parameters_schema
    assert list(Draft202012Validator(schema).iter_errors(params))
    assert not list(Draft202012Validator(schema).iter_errors({"title": "今日日程"}))


def test_meeting_contract_covers_time_and_location_without_dynamic_title() -> None:
    definition = get_cardplan_registry().require_template(_TEMPLATE_ID)
    assert definition.primary_data == ("/events/0/dtStart",)
    assert definition.secondary_data == ("/events/0/eventLocation",)
    assert definition.optional_data == ("/events/0/dtEnd", "/events/0/oneClickServiceLink")
    assert set(definition.bindings) == {"start", "end", "location", "joinLink"}


def test_meeting_static_title_does_not_require_a_runtime_title_field() -> None:
    registry = get_cardplan_registry()
    definition = registry.require_template(_TEMPLATE_ID)
    task = TaskSpec(
        userQuery="展示会议时间和地点", size="2x2",
        dataModelSchema=_build_data_schema(definition),
    )
    assert _template_has_satisfiable_variant(_TEMPLATE_ID, task, registry)


@pytest.mark.parametrize("title", [None, "", "   ", 42, "今日日程"])
def test_meeting_admission_requires_a_trusted_card_title(title: Any) -> None:
    definition = get_cardplan_registry().require_template(_TEMPLATE_ID)
    task = TaskSpec(
        userQuery="展示会议时间和地点", size="2x2",
        dataModelSchema=_build_data_schema(definition),
    )
    card = {"title": title, "dataBindings": [{
        "capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar",
    }]}
    admission = provider_template_admission(definition, task, card)
    assert admission.admitted is (title == "今日日程")


@pytest.mark.parametrize("with_end", [False, True])
@pytest.mark.parametrize("title", ["今日日程", "跨时区项目联合评审及下一阶段计划安排"])
def test_grouped_meeting_preserves_optional_time_and_final_a2ui(
    with_end: bool, title: str,
) -> None:
    omitted = frozenset() if with_end else frozenset({"end"})
    root = _expanded(_TEMPLATE_ID, omitted=omitted, props={"title": title})
    options = _options(root)
    assert options.get("_advancedComponent") == "ScheduleOverview"
    assert options.get("justifyContent") == "spaceBetween"
    assert options.get("alignItems") == "center"
    assert options.get("itemMargin") == 0
    assert len(root.children) == 2
    top, location = root.children
    assert top.component_type == "Column"
    assert _options(top).get("itemMargin") == 8
    assert _options(top).get("margin") == {"top": 4}
    assert _options(top).get("justifyContent") == "start"
    assert _options(top).get("alignItems") == "center"
    assert len(top.children) == 2
    label, time_row = top.children
    assert time_row.component_type == "Row"
    assert _options(time_row).get("width") == "matchParent"
    assert _options(time_row).get("height") == 58
    assert _options(time_row).get("flexShrink") == 1
    assert _options(time_row).get("justifyContent") == "center"
    assert _options(time_row).get("alignItems") == "center"
    assert len(time_row.children) == 1
    time = time_row.children[0]
    assert label.values[0] == title
    assert _options(label).get("textAlign") == "center"
    for text, font_size, min_font_size in ((label, 16, 12), (location, 12, 10)):
        assert _options(text).get("fontSize") == font_size
        assert _options(text).get("maxFontSize") == font_size
        assert _options(text).get("minFontSize") == min_font_size
        assert _options(text).get("maxLines") == 2
        assert _options(text).get("fontWeight") == 500
    time_size = 24 if with_end else 30
    time_min_size = 16 if with_end else 24
    assert _options(time).get("fontSize") == time_size
    assert _options(time).get("maxFontSize") == time_size
    assert _options(time).get("minFontSize") == time_min_size
    assert "height" not in _options(time)
    assert "flexShrink" not in _options(time)
    assert _options(time).get("maxLines") == 1
    assert "margin" not in _options(time)
    assert _options(time).get("fontWeight") == 800
    assert not any(node.component_type == "Divider" for node in _walk(root))

    definition = get_cardplan_registry().require_template(_TEMPLATE_ID)
    task = TaskSpec(
        userQuery="展示会议时间和地点", size="2x4", dataModelSchema=_build_data_schema(definition),
    )
    preview_root = _preview_root(_strip_advanced_component_markers(root), 136, {})
    document = _serialize_effective_document(preview_root, task, True)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    a2ui = convert_tersel_to_a2ui(
        document, size="2x4", protocol_profile=profile,
        task_spec=task.model_dump(mode="json"),
    )
    messages = [json.loads(line) for line in a2ui.splitlines() if line.strip()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    texts = [component for component in components if component.get("component") == "Text"]
    assert len(texts) == 3
    assert texts[0].get("content") == title
    expression = texts[1].get("content")
    assert isinstance(expression, str)
    assert "/events/0/dtStart" in expression
    assert ("/events/0/dtEnd" in expression) is with_end
    assert ("'-'" in expression) is with_end
    assert " - " not in expression
    assert "/events/0/title" not in a2ui
    rows = [component for component in components if component.get("component") == "Row"]
    assert len(rows) == 1
    time_row_styles = rows[0].get("styles")
    assert isinstance(time_row_styles, dict)
    assert time_row_styles.get("height") == 58
    assert time_row_styles.get("flexShrink") == 1
    assert time_row_styles.get("justifyContent") == "center"
    assert time_row_styles.get("alignItems") == "center"
    assert rows[0].get("children") == [texts[1].get("id")]
    top_group = next(
        component for component in components
        if component.get("children") == [texts[0].get("id"), rows[0].get("id")]
    )
    top_styles = top_group.get("styles")
    assert isinstance(top_styles, dict)
    assert top_styles.get("justifyContent") == "start"
    assert top_styles.get("alignItems") == "center"
    font_sizes = (16, time_size, 12)
    min_font_sizes = (12, time_min_size, 10)
    for index, text in enumerate(texts):
        styles = text.get("styles")
        assert isinstance(styles, dict)
        assert styles.get("maxLines") == (1 if index == 1 else 2)
        assert styles.get("fontSize") == font_sizes[index]
        assert styles.get("maxFontSize") == font_sizes[index]
        assert styles.get("minFontSize") == min_font_sizes[index]
        assert styles.get("textOverflow") == "ellipsis"
        if index == 1:
            assert "height" not in styles
            assert "flexShrink" not in styles


def test_meeting_preview_supplies_required_trusted_title() -> None:
    registry = get_cardplan_registry()
    definition = registry.require_template(_TEMPLATE_ID)
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    case = _build_case("centered-meeting", definition, profile, registry)
    update = case.messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    assert any(component.get("content") == "UI需求评审会" for component in components)
