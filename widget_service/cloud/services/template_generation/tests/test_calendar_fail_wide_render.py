"""补充宽日程形态：正式编译、完整索引、可选字段及显式参考尺寸预算。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import combinations
from typing import Any

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
    _text_styles,
)


@dataclass(frozen=True)
class _Case:
    suffix: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    mixed: bool = False

    @property
    def template_id(self) -> str:
        return f"ScheduleOverview{self.suffix}@1"


_CASES = (
    _Case(
        "DateAllDayWideFull",
        ("/events/0/startDate", "/events/0/title", "/events/0/isAllDay"),
    ),
    _Case(
        "TwoEventsWideFull",
        ("/events/0/dtStart", "/events/1/dtStart"),
        (
            "/events/0/title",
            "/events/1/title",
            "/events/0/dtEnd",
            "/events/1/dtEnd",
            "/events/0/eventLocation",
            "/events/1/eventLocation",
        ),
    ),
    _Case(
        "LocationDescriptionEndWideFull",
        ("/events/0/description", "/events/0/dtEnd", "/events/0/eventLocation"),
    ),
    _Case(
        "AllDayLocationWideFull",
        ("/events/0/isAllDay", "/events/0/eventLocation"),
        ("/events/0/title", "/events/0/timeZone"),
    ),
    _Case(
        "EventCountThreeDetailsWideFull",
        (
            "/eventCount",
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/description",
            "/events/1/title",
            "/events/1/dtStart",
            "/events/1/description",
            "/events/2/title",
            "/events/2/dtStart",
            "/events/2/description",
        ),
    ),
    _Case("TitleLocationHero", ("/events/0/title", "/events/0/eventLocation"), mixed=True),
)
_SAMPLES: dict[str, str | int | bool] = {
    "startDate": "10月23日",
    "title": "项目评审",
    "dtStart": "14:00",
    "dtEnd": "15:00",
    "description": "携带评审材料",
    "eventLocation": "研发三层会议室",
    "timeZone": "Asia/Shanghai",
    "isAllDay": True,
}


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry(
        enable_fusion_ball=True,
        enabled_calendar_fallback_template_ids=tuple(case.template_id for case in _CASES),
    )


def _typed(value: str | int | bool) -> dict[str, Any]:
    kind = "string"
    if isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, int):
        kind = "integer"
    return {"type": kind, "description": "日程展示字段", "sampleValue": value}


def _task(
    case: _Case,
    selected: tuple[str, ...],
    *,
    long_text: bool,
    zero: bool,
) -> TaskSpec:
    events: list[dict[str, Any]] = []
    calendar: dict[str, Any] = {"events": events}
    for path in (*case.required, *selected):
        if path == "/eventCount":
            calendar["eventCount"] = _typed(0 if zero else 3)
            continue
        _, _, index_text, name = path.split("/")
        index = int(index_text)
        while len(events) <= index:
            events.append({})
        value = _SAMPLES.get(name)
        assert value is not None
        if long_text and isinstance(value, str):
            value += "，跨部门联合评审及后续安排确认"
        if zero and isinstance(value, bool):
            value = False
        events[index][name] = _typed(value)
    data: dict[str, Any] = {"calendar": calendar}
    if case.mixed:
        data["weather"] = {"current": {"condition": _typed("多云")}}
    return TaskSpec(
        userQuery="显示已选日程信息，不需要按钮",
        size="2x4",
        appVersion="11.7.8.341",
        dataModelSchema={"data": data},
    )


def _compile(
    case: _Case,
    selected: tuple[str, ...],
    registry: CardPlanRegistry,
    *,
    long_text: bool = False,
    zero: bool = False,
) -> dict[str, dict[str, Any]]:
    task = _task(case, selected, long_text=long_text, zero=zero)
    paths = (*case.required, *selected)
    bindings = [
        CandidateDataBinding(
            capabilityId="GetCalendarEvents",
            writeResultTo="/data/calendar",
            candidateOutputFields=list(paths),
        )
    ]
    required = {"GetCalendarEvents": paths}
    preferred = [case.template_id]
    if case.mixed:
        weather_paths = ("/current/condition",)
        required["ViewWeather"] = weather_paths
        bindings.append(
            CandidateDataBinding(
                capabilityId="ViewWeather",
                writeResultTo="/data/weather",
                candidateOutputFields=list(weather_paths),
            )
        )
        preferred.append("WeatherOverviewConditionHero@1")
    card = {
        "title": "日程与天气" if case.mixed else "日程",
        "description": task.userQuery,
        "suggestSize": "2x4",
        "dataBindings": [binding.model_dump() for binding in bindings],
    }
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability=required)
    search = search_template_variants(
        intent, task, registry, tuple(bindings), card, preferred_template_ids=tuple(preferred)
    )
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    plan = plans[0]
    layout = "WideTwoFocusLayout@1" if case.mixed else "WideFullOnlyLayout@1"
    assert plan.layout_template_id == layout
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
        f'Template("{layout}",{{}},{children});',
        task_spec=task,
        card_spec=card,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=registry,
        enable_data_bindings=True,
    )
    messages = [json.loads(line) for line in compiled.a2ui.splitlines() if line.strip()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    result = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        result[component_id] = component
    return result


def _calendar_root(
    case: _Case,
    components: dict[str, dict[str, Any]],
    selected: tuple[str, ...] = (),
) -> str:
    found = None
    for component in _subtree("template_root", components):
        if component.get("component") != "Column":
            continue
        component_id = component.get("id")
        assert isinstance(component_id, str)
        body = json.dumps(_subtree(component_id, components), ensure_ascii=False)
        if "/data/weather" in body:
            continue
        if all(f"/data/calendar{path}" in body for path in (*case.required, *selected)):
            found = component_id
    assert found is not None
    return found


def _assert_geometry_and_fields(
    case: _Case,
    selected: tuple[str, ...],
    components: dict[str, dict[str, Any]],
) -> None:
    calendar_root = _calendar_root(case, components, selected)
    content = _subtree(calendar_root, components)
    texts = [item for item in content if item.get("component") == "Text"]
    actual_paths = set(re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", json.dumps(texts)))
    assert actual_paths == set((*case.required, *selected))
    slot_width, slot_height = (108, 102) if case.mixed else (276, 126)
    assert _natural_height(calendar_root, components) <= slot_height
    _check_widths(calendar_root, components, slot_width)
    assert _natural_height("template_root", components) <= 150
    for component in content:
        assert component.get("component") not in {"Button", "Image"}
        assert "onClick" not in component
        styles = _styles(component)
        assert "onClick" not in styles
        if component.get("component") == "Text":
            font_size = styles.get("fontSize")
            assert isinstance(font_size, (float, int))
            title_path = "/data/calendar/events/0/title"
            is_centered_title = (
                case.template_id == "ScheduleOverviewTitleLocationHero@1"
                and title_path in json.dumps(component.get("content"))
            )
            assert font_size <= (24 if is_centered_title else 18)
            assert styles.get("fontColor")
            assert styles.get("maxLines") in {1, 2}
            assert styles.get("textOverflow") == "ellipsis"
    for path in (*case.required, *selected):
        assert _text_styles(content, path)
    if case.suffix == "TwoEventsWideFull":
        _assert_two_event_binding_isolation(case, selected, content, components)


def _assert_two_event_binding_isolation(
    case: _Case,
    selected: tuple[str, ...],
    content: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> None:
    panels = []
    for component in content:
        if component.get("component") != "Column":
            continue
        if _styles(component).get("borderRadius") == 12:
            panels.append(component)
    assert len(panels) == 2
    for index, panel in enumerate(panels):
        panel_id = panel.get("id")
        assert isinstance(panel_id, str)
        body = json.dumps(_subtree(panel_id, components))
        actual = set(re.findall(r"/data/calendar(/[A-Za-z0-9/]+)", body))
        expected = set()
        for path in (*case.required, *selected):
            if path.startswith(f"/events/{index}/"):
                expected.add(path)
        assert actual == expected


def _optional_cases() -> list[tuple[_Case, tuple[str, ...]]]:
    result = []
    for case in _CASES:
        for count in range(len(case.optional) + 1):
            for selected in combinations(case.optional, count):
                result.append((case, selected))
    return result


@pytest.mark.parametrize(("case", "selected"), _optional_cases())
def test_every_optional_combination_compiles_with_complete_fields(
    case: _Case,
    selected: tuple[str, ...],
    registry: CardPlanRegistry,
) -> None:
    components = _compile(case, selected, registry)
    _assert_geometry_and_fields(case, selected, components)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
def test_long_text_keeps_all_bindings_inside_reference_slot(
    case: _Case, registry: CardPlanRegistry
) -> None:
    components = _compile(case, case.optional, registry, long_text=True)
    _assert_geometry_and_fields(case, case.optional, components)


@pytest.mark.parametrize("case", (_CASES[0], _CASES[3], _CASES[4]), ids=lambda case: case.suffix)
def test_false_all_day_and_zero_count_remain_runtime_bindings(
    case: _Case, registry: CardPlanRegistry
) -> None:
    ordinary = _compile(case, case.optional, registry)
    zero = _compile(case, case.optional, registry, zero=True)
    assert zero == ordinary
    body = json.dumps(_subtree("template_root", zero), ensure_ascii=False)
    if "/events/0/isAllDay" in case.required:
        assert "全天" in body and "非全天" in body
        assert "/data/calendar/events/0/isAllDay" in body
    else:
        assert "/data/calendar/eventCount" in body


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
def test_metadata_declares_exact_required_and_optional_paths(
    case: _Case, registry: CardPlanRegistry
) -> None:
    template = registry.require_template(case.template_id)
    assert set(template.required_data) == set(case.required)
    assert set(template.optional_data) == set(case.optional)
    assert not template.variants[0].parameters_schema.get("properties")
    assert template.action_policy == "none"


def test_six_variants_are_hidden_from_normal_template_search() -> None:
    ordinary = CardPlanRegistry(enable_fusion_ball=True)
    for case in _CASES:
        assert case.template_id in ordinary.templates
        assert not ordinary.template_is_enabled(case.template_id)


def test_three_details_has_three_separate_rows_without_losing_notes(
    registry: CardPlanRegistry,
) -> None:
    case = _CASES[4]
    components = _compile(case, (), registry)
    root_id = _calendar_root(case, components)
    content = _subtree(root_id, components)
    root = components.get(root_id)
    assert isinstance(root, dict)
    assert root.get("itemMargin") == 8
    rows = []
    for component in content:
        styles = _styles(component)
        assert "borderWidth" not in styles
        assert not styles.get("vertical")
        is_row = component.get("component") == "Row"
        if is_row and styles.get("borderRadius") == 8 and styles.get("backgroundColor"):
            assert styles.get("height") == 30
            assert styles.get("width") == "matchParent"
            rows.append(component)
    assert len(rows) == 3
    row_ids = [row.get("id") for row in rows]
    list_containers = [component for component in content if component.get("children") == row_ids]
    assert len(list_containers) == 1
    assert list_containers[0].get("itemMargin") == 6
    for index, row in enumerate(rows):
        row_id = row.get("id")
        assert isinstance(row_id, str)
        row_content = _subtree(row_id, components)
        texts = [component for component in row_content if component.get("component") == "Text"]
        assert len(texts) == 2
        main, time = texts
        main_content = json.dumps(main.get("content"), ensure_ascii=False)
        assert f"/data/calendar/events/{index}/title" in main_content
        assert f"/data/calendar/events/{index}/description" in main_content
        assert "·" in main_content
        assert f"/data/calendar/events/{index}/dtStart" in json.dumps(time.get("content"))
        for other in set(range(3)) - {index}:
            assert f"/data/calendar/events/{other}/" not in json.dumps(row_content)
        for text, weight in ((main, 500), (time, 400)):
            style = _styles(text)
            assert style.get("fontSize") == 12
            assert style.get("fontWeight") == weight
            assert style.get("height") == 16
            assert style.get("maxLines") == 1


@pytest.mark.parametrize("auxiliary_rows", (1, 2, 3))
def test_two_events_preserve_two_equally_weighted_columns(
    registry: CardPlanRegistry, auxiliary_rows: int
) -> None:
    case = _CASES[1]
    selected = ("/events/0/title", "/events/1/title")
    if auxiliary_rows >= 2:
        selected += ("/events/0/eventLocation", "/events/1/eventLocation")
    if auxiliary_rows == 3:
        selected += ("/events/0/dtEnd", "/events/1/dtEnd")
    components = _compile(case, selected, registry)
    content = _subtree(_calendar_root(case, components, selected), components)
    panels = []
    for component in content:
        styles = _styles(component)
        if component.get("component") == "Column" and styles.get("borderRadius") == 12:
            assert styles.get("layoutWeight") == 1
            assert styles.get("height") == "matchParent"
            assert styles.get("justifyContent") == "center"
            assert styles.get("backgroundColor")
            panels.append(component)
    assert len(panels) == 2
    panel_ids = [panel.get("id") for panel in panels]
    panel_rows = [component for component in content if component.get("children") == panel_ids]
    assert len(panel_rows) == 1
    assert panel_rows[0].get("itemMargin") == 12
    for index, panel in enumerate(panels):
        panel_id = panel.get("id")
        assert isinstance(panel_id, str)
        rendered = json.dumps(_subtree(panel_id, components))
        for path in (*case.required, *selected):
            if path.startswith(f"/events/{index}/"):
                assert f"/data/calendar{path}" in rendered
        assert f"/data/calendar/events/{1 - index}/" not in rendered
        panel_content = _subtree(panel_id, components)
        dots = []
        for component in panel_content:
            style = _styles(component)
            if style.get("borderWidth") == 1.5:
                assert style.get("width") == style.get("height") == 8
                dots.append(component)
        assert len(dots) == 1
        for path in (*case.required, *selected):
            if not path.startswith(f"/events/{index}/"):
                continue
            text_styles = _text_styles(panel_content, path)
            assert len(text_styles) == 1
            style = text_styles[0]
            expected = (14, 700, 20) if path.endswith("/title") else (10, 400, 14)
            assert (style.get("fontSize"), style.get("fontWeight"), style.get("height")) == expected
            assert style.get("width") == "matchParent"
            assert style.get("maxLines") == 1


def test_mixed_calendar_uses_centered_three_level_reference(registry: CardPlanRegistry) -> None:
    case = _CASES[5]
    components = _compile(case, (), registry)
    root_id = _calendar_root(case, components)
    root = components.get(root_id)
    assert isinstance(root, dict)
    assert root.get("itemMargin") == 6
    assert _natural_height(root_id, components) == 102
    content = _subtree(root_id, components)
    texts = [component for component in content if component.get("component") == "Text"]
    assert len(texts) == 3
    for text, size, height in zip(texts, (12, 24, 12), (16, 58, 16), strict=True):
        style = _styles(text)
        assert style.get("fontSize") == size
        assert style.get("height") == height
        assert style.get("width") == "matchParent"
        assert style.get("textAlign") == "center"
        assert style.get("maxLines") == 1
