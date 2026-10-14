"""新增日程纯展示模板：正式编译、完整字段、零值及实际槽位预算。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.tests.test_calendar_additional_no_action_render import (
    _check_widths,
)
from services.template_generation.tests.test_calendar_no_action_template_render import (
    _natural_height,
    _styles,
    _subtree,
)


@dataclass(frozen=True)
class _Case:
    suffix: str
    size: Literal["2x2", "2x4"]
    fields: tuple[str, ...]
    event_count: int = 1
    show_count: bool = False
    mixed: bool = False

    @property
    def template_id(self) -> str:
        return f"ScheduleOverview{self.suffix}@1"

    @property
    def paths(self) -> tuple[str, ...]:
        paths = ["/eventCount"] if self.show_count else []
        for index in range(self.event_count):
            for field in self.fields:
                paths.append(f"/events/{index}/{field}")
        return tuple(paths)


_CASES = (
    _Case("EventCountNotesFull", "2x2", ("title", "dtStart", "description"), show_count=True),
    _Case(
        "EventCountThreeTimeNotesWideFull",
        "2x4",
        ("dtStart", "description"),
        event_count=3,
        show_count=True,
    ),
    _Case("DateTitleFull", "2x4", ("title", "startDate"), mixed=True),
    _Case(
        "DateCountdownReminderFull",
        "2x2",
        ("title", "dtStart", "startDate", "countdownDays", "remindTime/0"),
    ),
)
_WEATHER_PATHS = ("/location/districtName", "/current/temperatureText", "/current/condition")


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry(
        enable_fusion_ball=True,
        enabled_calendar_fallback_template_ids=tuple(case.template_id for case in _CASES),
    )


def _typed(value: str | int) -> dict[str, Any]:
    return {
        "type": "integer" if isinstance(value, int) else "string",
        "description": "真实日程展示字段",
        "sampleValue": value,
    }


def _task(case: _Case, *, long_text: bool, zero: bool) -> TaskSpec:
    events = []
    for index in range(case.event_count):
        title = f"第{index + 1}项项目评审"
        note = f"备注{index + 1}：携带评审材料"
        if long_text:
            title += "与跨部门联合评审及后续项目实施计划确认"
            note += "，会上确认负责人、预计修复时间与下一阶段安排"
        events.append(
            {
                "title": _typed(title),
                "description": _typed(note),
                "dtStart": _typed(f"{index + 9}:00"),
                "dtEnd": _typed(f"{index + 10}:00"),
                "startDate": _typed("10月16日"),
                "countdownDays": _typed(0 if zero else 3),
                "remindTime": [_typed("0" if zero else "15")],
            }
        )
    calendar = {"eventCount": _typed(0 if zero else case.event_count), "events": events}
    data: dict[str, Any] = {"calendar": calendar}
    if case.mixed:
        data["weather"] = {
            "location": {"districtName": _typed("海淀区")},
            "current": {"temperatureText": _typed("23°C"), "condition": _typed("多云")},
        }
    return TaskSpec(
        userQuery="展示这些已选日程信息，不需要按钮",
        size=case.size,
        appVersion="11.7.8.341",
        dataModelSchema={"data": data},
    )


def _compile(
    case: _Case,
    registry: CardPlanRegistry,
    *,
    long_text: bool = False,
    zero: bool = False,
) -> dict[str, dict[str, Any]]:
    task = _task(case, long_text=long_text, zero=zero)
    # 三条模板的候选故意附带标题/结束时间，证明不会因此增加展示字段。
    candidate_fields = list(case.paths)
    for index in range(case.event_count):
        for field in ("title", "dtEnd"):
            path = f"/events/{index}/{field}"
            if path not in candidate_fields:
                candidate_fields.append(path)
    bindings = [
        CandidateDataBinding(
            capabilityId="GetCalendarEvents",
            writeResultTo="/data/calendar",
            candidateOutputFields=candidate_fields,
        )
    ]
    required = {"GetCalendarEvents": case.paths}
    preferred = [case.template_id]
    if case.mixed:
        bindings.append(
            CandidateDataBinding(
                capabilityId="ViewWeather",
                writeResultTo="/data/weather",
                candidateOutputFields=list(_WEATHER_PATHS),
            )
        )
        required["ViewWeather"] = _WEATHER_PATHS
        preferred.append("WeatherOverviewFull@1")
    card = {
        "title": "日程与天气" if case.mixed else "日程",
        "description": task.userQuery,
        "suggestSize": case.size,
        "dataBindings": [binding.model_dump() for binding in bindings],
    }
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability=required)
    search = search_template_variants(
        intent, task, registry, tuple(bindings), card, preferred_template_ids=tuple(preferred)
    )
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    plan = plans[0]
    expected_layout = "SingleFocusLayout@1" if case.size == "2x2" else "WideFullOnlyLayout@1"
    if case.mixed:
        expected_layout = "WideTwoFullLayout@1"
    assert plan.layout_template_id == expected_layout
    assert set(slot.template_id for slot in plan.business_slots) == set(preferred)
    assert not plan.action_assignments
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card,
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )
    children = ",".join(f'Template("{slot.template_id}",{{}})' for slot in plan.business_slots)
    compiled = compile_ux_layout_card(
        f'Template("{plan.layout_template_id}",{{}},{children});',
        task_spec=task,
        card_spec=card,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=registry,
        enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in compiled.a2ui.splitlines() if line.strip()]
    components = messages[1].get("updateComponents", {}).get("components")
    assert isinstance(components, list)
    result = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        result[component_id] = component
    return result


def _calendar_root(case: _Case, components: dict[str, dict[str, Any]]) -> str:
    found = None
    for component in _subtree("template_root", components):
        if component.get("component") != "Column":
            continue
        component_id = component.get("id")
        assert isinstance(component_id, str)
        body = json.dumps(_subtree(component_id, components), ensure_ascii=False)
        if "/data/weather" in body:
            continue
        if all(f"/data/calendar{path}" in body for path in case.paths):
            found = component_id
    assert found is not None
    return found


def _children(
    component: dict[str, Any], components: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for child_id in component.get("children", []):
        child = components.get(child_id)
        assert isinstance(child, dict)
        result.append(child)
    return result


def _assert_date_all_day_spacing(root_id: str, components: dict[str, dict[str, Any]]) -> None:
    root = components.get(root_id)
    assert isinstance(root, dict)
    assert root.get("itemMargin") == 2
    assert _styles(root).get("justifyContent") == "spaceBetween"
    upper, lower = _children(root, components)
    upper_id, lower_id = upper.get("id"), lower.get("id")
    assert isinstance(upper_id, str) and isinstance(lower_id, str)
    assert upper.get("itemMargin") == lower.get("itemMargin") == 4
    header, title = _children(upper, components)
    assert _styles(header).get("height") == 24
    assert _styles(header).get("alignItems") == "top"
    header_text, badge = _children(header, components)
    assert _styles(header_text).get("height") == 16
    assert _styles(header_text).get("fontSize") == 12
    assert _styles(header_text).get("fontWeight") == 500
    assert _styles(badge).get("width") == _styles(badge).get("height") == 14
    assert _styles(title).get("height") == 28
    assert _styles(title).get("fontSize") == 18
    assert _styles(title).get("fontWeight") == 700
    assert _natural_height(upper_id, components) == 56
    assert _natural_height(lower_id, components) == 36
    for text in _children(lower, components):
        assert _styles(text).get("height") == 16
        assert _styles(text).get("fontSize") == 12
        assert _styles(text).get("fontWeight") == 400
        assert _styles(text).get("maxLines") == 1
    # 根内高 126，底组 36：两条辅助信息顶部与参考款同为 y=102/122。
    assert 150 - 12 - _natural_height(lower_id, components) == 102


def _assert_two_reference_rows(root_id: str, components: dict[str, dict[str, Any]]) -> None:
    root = components.get(root_id)
    assert isinstance(root, dict)
    assert root.get("itemMargin") == 10
    header, body = _children(root, components)
    assert _styles(header).get("height") == 20
    header_text, _badge = _children(header, components)
    assert _styles(header_text).get("fontSize") == 14
    assert _styles(header_text).get("fontWeight") == 400
    assert _styles(body).get("height") == 96
    assert body.get("itemMargin") == 0
    children = _children(body, components)
    assert [item.get("component") for item in children] == [
        "Row",
        "Divider",
        "Row",
        "Divider",
        "Row",
    ]
    y = 12 + 20 + 10
    row_index = 0
    for component in children:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        styles = _styles(component)
        if component.get("component") == "Row":
            assert y == (42, 80, 118)[row_index]
            assert styles.get("height") == 20
            assert component.get("itemMargin") == 24
            note, start = _children(component, components)
            note_styles, start_styles = _styles(note), _styles(start)
            assert note_styles.get("width") == 200
            assert note_styles.get("height") == 20
            assert note_styles.get("fontSize") == 12
            assert note_styles.get("fontWeight") == 700
            assert start_styles.get("width") == 52
            assert start_styles.get("height") == 16
            assert start_styles.get("fontSize") == 12
            assert start_styles.get("fontWeight") == 500
            assert start_styles.get("textAlign") == "end"
            assert start_styles.get("margin") == {"top": 2}
            assert note_styles.get("maxLines") == start_styles.get("maxLines") == 1
            assert f"/events/{row_index}/description" in str(note.get("content"))
            assert f"/events/{row_index}/dtStart" in str(start.get("content"))
            assert 12 + note_styles["width"] + component["itemMargin"] == 236
            assert y + start_styles["margin"]["top"] == (44, 82, 120)[row_index]
            row_index += 1
        else:
            assert y in {71, 109}
            assert styles.get("height") == 1
            assert styles.get("margin") == {"bottom": 8}
        y += _natural_height(component_id, components)
    assert y == 138


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
@pytest.mark.parametrize("long_text", [False, True], ids=["ordinary", "long"])
def test_requested_fields_compile_inside_the_actual_calendar_slot(
    case: _Case, long_text: bool, registry: CardPlanRegistry
) -> None:
    components = _compile(case, registry, long_text=long_text)
    root_id = _calendar_root(case, components)
    content = _subtree(root_id, components)
    texts = [item for item in content if item.get("component") == "Text"]
    serialized = json.dumps(texts, ensure_ascii=False)
    bound = set(re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", serialized))
    assert bound == set(case.paths)
    assert "今天" not in serialized
    assert _natural_height(root_id, components) <= (102 if case.mixed else 126)
    width = 110 if case.mixed else (126 if case.size == "2x2" else 276)
    _check_widths(root_id, components, width)
    for item in content:
        assert item.get("component") not in {"Button", "Image"}
        assert "onClick" not in item
        styles = _styles(item)
        assert "onClick" not in styles
        margin = styles.get("margin", {})
        if isinstance(margin, dict):
            assert all(value >= 0 for value in margin.values())
        if item.get("component") == "Text":
            font_size = styles.get("fontSize")
            assert isinstance(font_size, (int, float)) and font_size <= 18
            assert styles.get("textOverflow") == "ellipsis"
    if case.mixed:
        whole = json.dumps(list(components.values()), ensure_ascii=False)
        for path in _WEATHER_PATHS:
            assert f"/data/weather{path}" in whole
    if case.event_count == 3:
        _assert_two_reference_rows(root_id, components)
    if case.suffix == "EventCountNotesFull":
        _assert_date_all_day_spacing(root_id, components)


@pytest.mark.parametrize("case", (_CASES[0], _CASES[1], _CASES[3]), ids=lambda case: case.suffix)
def test_zero_counts_days_and_reminder_minutes_keep_dynamic_text(
    case: _Case, registry: CardPlanRegistry
) -> None:
    ordinary = _compile(case, registry)
    zero = _compile(case, registry, zero=True)
    assert zero == ordinary
    serialized = json.dumps(list(zero.values()), ensure_ascii=False)
    if case.show_count:
        assert "/data/calendar/eventCount" in serialized
    if "remindTime/0" in case.fields:
        assert "/data/calendar/events/0/countdownDays" in serialized
        assert "/data/calendar/events/0/remindTime/0" in serialized
        assert "倒计时" in serialized and "分钟提醒" in serialized


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
def test_metadata_has_exact_required_fields_and_no_optional_display(
    case: _Case, registry: CardPlanRegistry
) -> None:
    template = registry.require_template(case.template_id)
    assert set(template.required_data) == set(case.paths)
    assert not template.optional_data
    assert not template.variants[0].parameters_schema.get("properties")
    assert template.action_policy == "none"


def test_new_templates_are_hidden_from_default_registry() -> None:
    registry = CardPlanRegistry(enable_fusion_ball=True)
    for case in _CASES:
        assert case.template_id in registry.templates
        assert not registry.template_is_enabled(case.template_id)
