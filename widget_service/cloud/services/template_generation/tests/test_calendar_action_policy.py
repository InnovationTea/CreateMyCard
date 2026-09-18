from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced.scope_planner import TemplateRouteNotApplicable
from services.template_generation.engine.cardplan.calendar_action_policy import (
    resolve_calendar_view_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    TemplateSearchResult,
    build_template_retrieval_prompt,
    search_template_variants,
)

_VIEW_EVENT = "event.viewCalendarEvent"
_TITLE_FIELDS = ("/events/0/title", "/events/0/dtStart", "/events/0/dtEnd")


@dataclass(frozen=True)
class CalendarCase:
    task: TaskSpec
    binding: CandidateDataBinding
    card: dict[str, Any]
    intent: TemplateSearchIntent


def _field(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, int):
        kind = "integer"
    else:
        kind = "string"
    return {"type": kind, "description": "日程测试字段", "sampleValue": value}


def _calendar_case(
    fields: tuple[str, ...] = _TITLE_FIELDS,
    *,
    with_location: bool = False,
    allow_fallback: bool = True,
) -> CalendarCase:
    event = {
        "title": _field("项目例会"), "dtStart": _field("14:00"), "dtEnd": _field("15:00"),
        "entityId": _field("example-event-001"), "startDate": _field("9月17日"),
        "isAllDay": _field(False), "description": _field("讨论开发计划"),
        "remindTime": [_field("15")], "senderName": _field("张先生"),
        "importantEventType": _field(1),
    }
    if with_location:
        event["eventLocation"] = _field("会议室")
    task = TaskSpec(
        userQuery="创建日历卡片，显示日程标题、开始时间和结束时间",
        size="2x2",
        eventCandidates=[EventAction(
            id=_VIEW_EVENT, call="clickToIntent",
            args={"intentName": "ViewCalendarEvent", "params": {
                "entityId": "{{ ${/data/calendar/events/0/entityId} }}",
            }},
        )],
        dataModelSchema={"data": {"calendar": {
            "events": [event], "eventCount": _field(2), "updatedAt": _field("09:00"),
        }}},
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents", writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    )
    return CalendarCase(
        task=task,
        binding=binding,
        card={"title": "日程卡片", "description": "展示日程", "suggestSize": "2x2",
              "dataBindings": [{"capabilityId": "GetCalendarEvents",
                                "writeResultTo": "/data/calendar"}]},
        intent=TemplateSearchIntent(
            requiredOutputFieldsByCapability={"GetCalendarEvents": fields},
            allowCalendarViewFallback=allow_fallback,
        ),
    )


def _search(case: CalendarCase, registry: CardPlanRegistry) -> TemplateSearchResult:
    return search_template_variants(case.intent, case.task, registry, (case.binding,), case.card)


@pytest.mark.parametrize(("fields", "template"), [
    (_TITLE_FIELDS, "ScheduleOverviewTitleHero@1"),
    (("/eventCount", "/events/0/title", "/events/0/dtStart", "/events/0/description"),
     "ScheduleOverviewEventCountDetailsHero@1"),
    (("/events/0/startDate", "/events/0/title", "/events/0/isAllDay"),
     "ScheduleOverviewDatedAllDayHero@1"),
    (("/events/0/title", "/events/0/dtStart", "/events/0/remindTime/0"),
     "ScheduleOverviewReminderHero@1"),
    (("/events/0/senderName", "/events/0/importantEventType", "/events/0/remindTime/0",
      "/updatedAt"), "ScheduleOverviewReminderDetailsHero@1"),
])
def test_calendar_hero_fallback_preserves_all_fields_and_uses_one_view_action(
    fields: tuple[str, ...], template: str,
) -> None:
    case = _calendar_case(fields)
    # Keep the Hero-only precondition with both reminder and wide-branch count Fulls.
    registry = CardPlanRegistry(disabled_template_ids=(
        "ScheduleOverviewReminderDetailsFull@1",
        "ScheduleOverviewEventCountDetailsFull@1",
    ))
    result = _search(case, registry)
    intent = resolve_calendar_view_fallback(case.intent, result, case.task, registry)
    assert intent.action_ids == (_VIEW_EVENT,)
    expected_fields = case.intent.required_output_fields_by_capability
    assert intent.required_output_fields_by_capability == expected_fields
    assert case.intent.action_ids == ()
    plans = plan_template_candidates(intent, result, case.task, registry)
    for plan in plans:
        assert plan.layout_template_id == "HeroActionLayout@1"
        assert plan.business_slots[0].template_id == template
        assert len(plan.action_assignments) == 1
        assert plan.action_assignments[0].action_id == _VIEW_EVENT


def test_matching_full_wins_even_when_hero_and_view_action_are_available() -> None:
    case = _calendar_case(with_location=True)
    registry = CardPlanRegistry()
    result = _search(case, registry)
    intent = resolve_calendar_view_fallback(case.intent, result, case.task, registry)
    assert intent is case.intent
    plans = plan_template_candidates(intent, result, case.task, registry)
    assert all(plan.layout_template_id == "SingleFocusLayout@1" for plan in plans)
    assert all(not plan.action_assignments for plan in plans)


@pytest.mark.parametrize("events", ["missing", "duplicate", "different-event", "static-id"])
def test_fallback_requires_one_approved_view_of_the_displayed_event(events: str) -> None:
    case = _calendar_case()
    registry = CardPlanRegistry()
    candidates = case.task.eventCandidates
    if events == "missing":
        candidates = []
    elif events == "duplicate":
        candidates = [*candidates, *candidates]
    else:
        entity_id = "{{ ${/data/calendar/events/1/entityId} }}"
        if events == "static-id":
            entity_id = "unrelated-fixed-event"
        candidates = [candidates[0].model_copy(update={"args": {
            "intentName": "ViewCalendarEvent", "params": {"entityId": entity_id},
        }})]
    task = case.task.model_copy(update={"eventCandidates": candidates})
    resolved = resolve_calendar_view_fallback(case.intent, _search(case, registry), task, registry)
    assert resolved is case.intent


@pytest.mark.parametrize("reason", ["forbidden", "explicit-action", "wide", "other", "multiple"])
def test_calendar_fallback_does_not_change_other_intents(reason: str) -> None:
    case = _calendar_case()
    registry = CardPlanRegistry()
    intent = case.intent
    task = case.task
    result = _search(case, registry)
    if reason == "forbidden":
        intent = intent.model_copy(update={"allow_calendar_view_fallback": False})
    elif reason == "explicit-action":
        intent = intent.model_copy(update={"action_ids": ("event.enter.meeting",)})
    elif reason == "wide":
        task = task.model_copy(update={"size": "2x4"})
        result = result.model_copy(update={"card_size": "2x4"})
    else:
        requested = {"ViewWeather": ("/current/temperatureText",)}
        if reason == "multiple":
            requested.update(intent.required_output_fields_by_capability)
        intent = intent.model_copy(update={"required_output_fields_by_capability": requested})
    assert resolve_calendar_view_fallback(intent, result, task, registry) is intent


def test_support_without_hero_cannot_trigger_default_view() -> None:
    case = _calendar_case(("/events/0/title", "/events/0/dtStart"))
    task = case.task.model_copy(update={"dataModelSchema": {"data": {"calendar": {
        "events": [{"title": _field("例会"), "dtStart": _field("14:00"),
                    "entityId": _field("example-event-001")}],
    }}}})
    case = CalendarCase(task=task, binding=case.binding, card=case.card, intent=case.intent)
    registry = CardPlanRegistry(disabled_template_ids=("ScheduleOverviewTitleHero@1",))
    result = _search(case, registry)
    # Support 能展示现有字段，但不能通过默认动作伪造数据完整的 Hero。
    assert resolve_calendar_view_fallback(case.intent, result, case.task, registry) is case.intent


def test_missing_required_data_is_not_fixed_by_adding_an_action() -> None:
    case = _calendar_case((*_TITLE_FIELDS, "/events/0/eventLocation"))
    with pytest.raises(TemplateRetrievalMiss, match="absent or untyped"):
        _search(case, CardPlanRegistry())


def test_first_layer_flag_is_semantic_optional_and_strict() -> None:
    old = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetCalendarEvents": _TITLE_FIELDS},
    )
    assert old.allow_calendar_view_fallback is False
    with pytest.raises(ValidationError):
        TemplateSearchIntent(
            requiredOutputFieldsByCapability={"GetCalendarEvents": _TITLE_FIELDS},
            allowCalendarViewFallback="false",
        )
    case = _calendar_case()
    prompt = build_template_retrieval_prompt(case.task, CardPlanRegistry(), (case.binding,))
    system = prompt[0].get("content")
    assert isinstance(system, str)
    assert "不要按钮、不需要操作" in system
    assert "没有提到按钮不等于禁止按钮" in system
    schema = json.loads(system.splitlines()[-1])
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    flag = properties.get("allowCalendarViewFallback")
    assert isinstance(flag, dict)
    assert flag.get("default") is False


@pytest.mark.asyncio
@pytest.mark.parametrize("with_full", [False, True])
async def test_default_view_reaches_second_layer_and_compiles_exactly_once(
    monkeypatch: pytest.MonkeyPatch, with_full: bool,
) -> None:
    case = _calendar_case(with_location=with_full)
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            assert phase == "template-retrieval-query"
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
            if with_full:
                return ('Template("SingleFocusLayout@1",{},'
                        'Template("ScheduleOverviewNextEventLocationFull@1",{}));')
            return ('Template("HeroActionLayout@1",{},'
                    'Template("ScheduleOverviewTitleHero@1",{}),'
                    'Template("PillAction@1",{"actionId":"event.viewCalendarEvent",'
                    '"label":"查看日程"}));')

    output = await pipeline.generate_template_a2ui(case.task, case.card, (case.binding,), Model())
    selected = output.projected_task_spec.eventCandidates
    assert len(selected) == (0 if with_full else 1)
    expected_calls = 0 if with_full else 1
    assert output.a2ui.count('"call":"clickToIntent"') == expected_calls
    if not with_full:
        assert "查看日程" in output.a2ui
        assert "/data/calendar/events/0/entityId" in output.a2ui


@pytest.mark.asyncio
async def test_explicit_no_button_never_reaches_second_layer_for_hero_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _calendar_case(allow_fallback=False)
    task = case.task.model_copy(update={"userQuery": "显示日程标题和起止时间，不要按钮"})
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            assert phase == "template-retrieval-query"
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
            pytest.fail("明确不要按钮且无Full时不得进入Hero二层")

    with pytest.raises(TemplateRouteNotApplicable, match="cannot form"):
        await pipeline.generate_template_a2ui(task, case.card, (case.binding,), Model())
