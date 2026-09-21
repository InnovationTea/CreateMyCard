from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest

from models.capability import DataCapability, Dependencies
from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.task_spec_builder import TaskSpecBuilder
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced.scope_planner import TemplateRouteNotApplicable
from services.template_generation.engine.cardplan import template_retrieval as retrieval
from services.template_generation.engine.cardplan.calendar_field_paths import (
    calendar_reminder_aliases,
    normalize_calendar_reminder_bindings,
)
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    build_template_retrieval_prompt,
    normalize_calendar_reminder_intent,
    search_template_variants,
)

_CAPABILITY = "GetCalendarEvents"
_PARENT = "/events/0/remindTime"
_LEAF = f"{_PARENT}/0"
_VIEW = "event.viewCalendarEvent"
_HERO_FIELDS = ("/events/0/title", "/events/0/dtStart", _PARENT)
_DETAIL_FIELDS = (
    "/events/0/senderName", "/events/0/importantEventType", _PARENT, "/updatedAt",
)


def _field(value: Any, kind: str = "string") -> dict[str, Any]:
    return {"type": kind, "description": "日程字段", "sampleValue": value}


def _binding(fields: tuple[str, ...]) -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId=_CAPABILITY, writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    )


def _task(binding: CandidateDataBinding, *, with_action: bool = True) -> TaskSpec:
    properties = {
        "title": _field("产品评审"), "dtStart": _field("14:00"),
        "dtEnd": _field("15:00"), "entityId": _field("event-001"),
        "eventLocation": _field("会议室"), "senderName": _field("张先生"),
        "importantEventType": _field(1, "integer"),
        "remindTime": {"type": "array", "items": _field("15")},
    }
    capability = DataCapability(
        id=_CAPABILITY, description="日程", defaultWriteResultTo="/data/calendar",
        outputSchema={"type": "object", "properties": {
            "events": {"type": "array", "items": {
                "type": "object", "properties": properties,
            }},
            "updatedAt": _field("09:00"),
        }},
        dependencies=Dependencies(),
    )
    events = [EventAction(
        id=_VIEW, call="clickToIntent",
        args={"intentName": "ViewCalendarEvent", "params": {
            "entityId": "{{ ${/data/calendar/events/0/entityId} }}",
        }},
    )] if with_action else []
    return TaskSpecBuilder().build(
        user_query="显示日程及提醒分钟数", size="2x2", effective_bindings=[binding],
        effective_data_capabilities=[capability], event_candidates=events, asset_candidates=[],
    )


def _event(task: TaskSpec) -> dict[str, Any]:
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    events = calendar.get("events")
    assert isinstance(events, list) and events
    event = events[0]
    assert isinstance(event, dict)
    return event


def _card(bindings: tuple[CandidateDataBinding, ...]) -> dict[str, Any]:
    return {
        "title": "日历", "description": "显示日程及提醒分钟数", "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": item.capabilityId, "writeResultTo": item.writeResultTo}
            for item in bindings
        ],
    }


def _intent(fields: tuple[str, ...], *, focus: str | None = None) -> TemplateSearchIntent:
    return TemplateSearchIntent(
        requiredOutputFieldsByCapability={_CAPABILITY: fields},
        primaryOutputFieldByCapability={_CAPABILITY: focus} if focus else {},
        allowCalendarViewFallback=True,
    )


def test_builder_projection_and_first_layer_whitelist_agree_without_mutating_input() -> None:
    binding = _binding(_HERO_FIELDS)
    task = _task(binding)
    original = (task.model_dump(), binding.model_dump())
    reminder = _event(task).get("remindTime")
    assert isinstance(reminder, list) and reminder[0] == _field("15")
    prompt = build_template_retrieval_prompt(task, get_cardplan_registry(), (binding,))
    content = prompt[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    whitelist = payload.get("candidateOutputFieldsByCapability")
    assert isinstance(whitelist, dict)
    assert whitelist.get(_CAPABILITY) == sorted((*_HERO_FIELDS[:2], _LEAF))
    candidates = payload.get("candidateDataBindings")
    assert isinstance(candidates, list)
    assert candidates[0].get("candidateOutputFields") == [*_HERO_FIELDS[:2], _LEAF]
    assert original == (task.model_dump(), binding.model_dump())


def test_normalization_preserves_order_deduplicates_alias_and_updates_focus() -> None:
    fields = (_PARENT, "/events/0/title", _LEAF)
    binding = _binding(fields)
    task = _task(binding)
    intent = _intent(fields, focus=_PARENT).model_copy(update={"action_ids": (_VIEW,)})
    normalized = normalize_calendar_reminder_intent(intent, task, (binding,))
    bindings = normalize_calendar_reminder_bindings(task, (binding,))
    assert normalized.required_output_fields_by_capability == {
        _CAPABILITY: (_LEAF, "/events/0/title"),
    }
    assert normalized.primary_output_field_by_capability == {_CAPABILITY: _LEAF}
    assert normalized.action_ids == (_VIEW,) and normalized.allow_calendar_view_fallback
    assert bindings[0].candidateOutputFields == [_LEAF, "/events/0/title"]
    assert normalize_calendar_reminder_intent(normalized, task, (binding,)) is normalized
    assert normalize_calendar_reminder_bindings(task, bindings) is bindings
    assert intent.required_output_fields_by_capability.get(_CAPABILITY) == fields


@pytest.mark.parametrize("path", [_LEAF, f"{_PARENT}/1", f"{_PARENT}/2"])
def test_explicit_reminder_indices_are_unchanged(path: str) -> None:
    binding = _binding((path,))
    task = _task(binding)
    bindings = (binding,)
    intent = _intent((path,), focus=path)
    assert normalize_calendar_reminder_bindings(task, bindings) is bindings
    assert normalize_calendar_reminder_intent(intent, task, bindings) is intent


def test_parent_and_explicit_second_reminder_keep_distinct_indices_and_values() -> None:
    second = f"{_PARENT}/1"
    binding = _binding((_PARENT, second))
    task = _task(binding)
    _event(task)["remindTime"] = [_field("15"), _field("30")]
    snapshot = task.model_dump()
    normalized = normalize_calendar_reminder_bindings(task, (binding,))
    intent = normalize_calendar_reminder_intent(_intent((_PARENT, second)), task, (binding,))
    assert normalized[0].candidateOutputFields == [_LEAF, second]
    assert intent.required_output_fields_by_capability.get(_CAPABILITY) == (_LEAF, second)
    assert task.model_dump() == snapshot


@pytest.mark.parametrize("reminder", [
    None, [], "15", _field("15"), {}, [{"minutes": _field("15")}],
    [[_field("15")]], [None, _field("15")], [{"type": "object"}],
    [{"type": ["string"]}], [_field("15"), {"minutes": _field("30")}],
])
def test_missing_or_non_scalar_arrays_are_not_aliased(reminder: Any) -> None:
    binding = _binding(_HERO_FIELDS)
    task = _task(binding)
    _event(task)["remindTime"] = reminder
    bindings = (binding,)
    assert calendar_reminder_aliases(task, bindings) == {}
    assert normalize_calendar_reminder_bindings(task, bindings) is bindings


@pytest.mark.parametrize("scope", ["other_field", "other_capability", "wide"])
def test_other_fields_businesses_and_sizes_are_unchanged(scope: str) -> None:
    binding = _binding(_HERO_FIELDS)
    task = _task(binding)
    if scope == "other_field":
        _event(task)["tags"] = [_field("重要")]
        binding = _binding(("/events/0/tags",))
    elif scope == "other_capability":
        binding = binding.model_copy(update={"capabilityId": "OtherCalendar"})
    else:
        task = task.model_copy(update={"size": "2x4"})
    bindings = (binding,)
    assert normalize_calendar_reminder_bindings(task, bindings) is bindings


def test_event_index_is_preserved_without_falling_back_to_first_event() -> None:
    parent = "/events/1/remindTime"
    binding = _binding((parent,))
    task = _task(binding)
    assert calendar_reminder_aliases(task, (binding,)) == {parent: f"{parent}/0"}
    assert calendar_reminder_aliases(task, (_binding((_PARENT,)),)) == {}
    intent = _intent((parent,))
    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        search_template_variants(
            intent, task, get_cardplan_registry(), (binding,), _card((binding,)),
        )


def test_alias_requires_the_same_projection_at_every_binding_root() -> None:
    first = _binding(_HERO_FIELDS)
    task = _task(first)
    second = first.model_copy(update={"writeResultTo": "/data/otherCalendar"})
    bindings = (first, second)
    assert calendar_reminder_aliases(task, bindings) == {}
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    data["otherCalendar"] = deepcopy(data.get("calendar"))
    assert calendar_reminder_aliases(task, bindings) == {_PARENT: _LEAF}


@pytest.mark.parametrize(("candidate", "requested", "error"), [
    (_PARENT, f"{_PARENT}/1", "must come from candidates"),
    (_LEAF, _PARENT, "must come from candidates"),
    (f"{_PARENT}/1", f"{_PARENT}/1", "no provider template"),
])
def test_alias_does_not_expand_authorization_or_collapse_explicit_indices(
    candidate: str, requested: str, error: str,
) -> None:
    binding = _binding((*_HERO_FIELDS[:2], candidate))
    task = _task(binding)
    with pytest.raises(TemplateRetrievalMiss, match=error):
        search_template_variants(
            _intent((*_HERO_FIELDS[:2], requested)), task, get_cardplan_registry(),
            (binding,), _card((binding,)),
        )


def test_valid_array_with_wrong_template_type_is_still_rejected() -> None:
    binding = _binding(_HERO_FIELDS)
    task = _task(binding)
    _event(task)["remindTime"] = [_field(15, "integer")]
    assert calendar_reminder_aliases(task, (binding,)) == {_PARENT: _LEAF}
    with pytest.raises(TemplateRetrievalMiss, match="no provider template"):
        search_template_variants(
            _intent(_HERO_FIELDS), task, get_cardplan_registry(), (binding,), _card((binding,)),
        )


@pytest.mark.parametrize(("fields", "template"), [
    (_HERO_FIELDS, "ScheduleOverviewReminderHero@1"),
    (_DETAIL_FIELDS, "ScheduleOverviewReminderDetailsHero@1"),
])
@pytest.mark.parametrize("model_uses_parent", [False, True])
@pytest.mark.asyncio
async def test_reminder_shorthand_compiles_through_real_pipeline(
    monkeypatch: pytest.MonkeyPatch, fields: tuple[str, ...], template: str,
    model_uses_parent: bool,
) -> None:
    binding = _binding(fields)
    task = _task(binding)
    snapshot = (task.model_dump(), binding.model_dump())
    canonical = tuple(_LEAF if field == _PARENT else field for field in fields)
    required = fields if model_uses_parent else canonical
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    # The trusted-template restriction must see canonical paths, before it can drop fields.
    real_search = pipeline.search_template_variants

    def checked_search(intent: TemplateSearchIntent, *args: Any, **kwargs: Any) -> Any:
        assert intent.required_output_fields_by_capability.get(_CAPABILITY) == canonical
        assert intent.primary_output_field_by_capability.get(_CAPABILITY) == _LEAF
        return real_search(intent, *args, **kwargs)

    monkeypatch.setattr(pipeline, "search_template_variants", checked_search)

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            assert phase == "template-retrieval-query"
            focus = _PARENT if model_uses_parent else _LEAF
            return _intent(required, focus=focus).model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                f'Template("HeroActionLayout@1",{{}},Template("{template}",{{}}),'
                f'Template("PillAction@1",{{"actionId":"{_VIEW}","label":"查看日程"}}));'
            )

    output = await pipeline.generate_template_a2ui(
        task, _card((binding,)), (binding,), Model(), trusted_template_candidate_ids=(template,),
    )
    assert template in output.template_ids
    assert "/data/calendar/events/0/remindTime/0" in output.a2ui
    assert output.a2ui.count('"call":"clickToIntent"') == 1
    assert snapshot == (task.model_dump(), binding.model_dump())


@pytest.mark.asyncio
async def test_missing_view_candidate_still_stops_at_planner_without_matching_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding(_DETAIL_FIELDS)
    task = _task(binding, with_action=False)
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    registry = CardPlanRegistry(
        disabled_template_ids=("ScheduleOverviewReminderDetailsFull@1",),
    )
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _enabled: registry)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return _intent(_DETAIL_FIELDS).model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            pytest.fail("缺少查看事件时不得生成按钮")

    with pytest.raises(TemplateRouteNotApplicable, match="cannot form"):
        await pipeline.generate_template_a2ui(task, _card((binding,)), (binding,), Model())


@pytest.mark.parametrize("fields", [
    (*_HERO_FIELDS[:2], _LEAF),
    (*_DETAIL_FIELDS[:2], _LEAF, "/updatedAt"),
    ("/events/0/title", "/events/0/dtStart", "/events/0/dtEnd"),
    ("/events/0/title", "/events/0/dtStart", "/events/0/dtEnd", "/events/0/eventLocation"),
])
def test_existing_calendar_candidates_and_plans_equal_pre_fix_behavior(
    monkeypatch: pytest.MonkeyPatch, fields: tuple[str, ...],
) -> None:
    binding = _binding(fields)
    task = _task(binding)
    intent = _intent(fields).model_copy(update={"action_ids": (_VIEW,)})
    registry = get_cardplan_registry()
    args = (intent, task, registry, (binding,), _card((binding,)))
    result = search_template_variants(*args)
    plans = plan_template_candidates(intent, result, task, registry)
    prompt = build_template_retrieval_prompt(task, registry, (binding,))
    with monkeypatch.context() as context:
        context.setattr(retrieval, "normalize_calendar_reminder_bindings", lambda _t, b: b)
        context.setattr(retrieval, "normalize_calendar_reminder_intent", lambda i, _t, _b: i)
        baseline = search_template_variants(*args)
        baseline_plans = plan_template_candidates(intent, baseline, task, registry)
        baseline_prompt = build_template_retrieval_prompt(task, registry, (binding,))
    assert result == baseline
    assert plans == baseline_plans
    assert prompt == baseline_prompt


@pytest.mark.parametrize("required", [(), _HERO_FIELDS[:2]])
def test_unused_reminder_candidate_does_not_change_existing_candidates_or_plans(
    monkeypatch: pytest.MonkeyPatch, required: tuple[str, ...],
) -> None:
    binding = _binding(_HERO_FIELDS)
    task = _task(binding)
    intent = _intent(required).model_copy(update={"action_ids": (_VIEW,)})
    registry = get_cardplan_registry()
    assert normalize_calendar_reminder_intent(intent, task, (binding,)) is intent
    args = (intent, task, registry, (binding,), _card((binding,)))
    result = search_template_variants(*args)
    plans = plan_template_candidates(intent, result, task, registry)
    with monkeypatch.context() as context:
        context.setattr(retrieval, "normalize_calendar_reminder_bindings", lambda _t, b: b)
        context.setattr(retrieval, "normalize_calendar_reminder_intent", lambda i, _t, _b: i)
        baseline = search_template_variants(*args)
        baseline_plans = plan_template_candidates(intent, baseline, task, registry)
    gained_fields: set[str] = set()
    for group, prior_group in zip(
        result.business_candidates, baseline.business_candidates, strict=True,
    ):
        assert group.capability_id == prior_group.capability_id
        assert group.business_id == prior_group.business_id
        assert group.explicit_fields == prior_group.explicit_fields
        for candidate, prior in zip(group.candidates, prior_group.candidates, strict=True):
            assert candidate.template_id == prior.template_id
            assert candidate.covered_explicit_fields == prior.covered_explicit_fields
            assert set(prior.available_data_fields).issubset(candidate.available_data_fields)
            gained_fields.update(
                set(candidate.available_data_fields) - set(prior.available_data_fields)
            )
    assert gained_fields == {binding.writeResultTo + _LEAF}
    assert plans == baseline_plans
