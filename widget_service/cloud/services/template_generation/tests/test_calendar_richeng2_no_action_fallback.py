"""两种日程宽卡仅补旧失败，保留授权、字段与已有成功路径。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.tests.test_calendar_additional_no_action_fallback import (
    _fallback,
    _first_event,
    _old_plans,
    _pipeline_registry,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_TITLE = "/events/0/title"
_START = "/events/0/dtStart"
_END = "/events/0/dtEnd"
_DATE = "/events/0/startDate"
_LOCATION = "/events/0/eventLocation"
_COUNTDOWN = "/events/0/countdownDays"
_VIEW = "event.viewCalendarEvent"
_TITLE_TARGET = "ScheduleOverviewTitleTimeWideFull@1"
_DATED_TARGET = "ScheduleOverviewDatedMeetingWideFull@1"
_TITLE_FIELDS = (_TITLE, _START)
_DATE_FIELDS = (_DATE, _START, _END, _LOCATION)
_FIVE_FIELDS = (_DATE, _TITLE, _START, _END, _LOCATION)
_REQUIRED_CASES = (
    (_TITLE_TARGET, _TITLE),
    (_TITLE_TARGET, _START),
    (_DATED_TARGET, _TITLE),
    (_DATED_TARGET, _DATE),
    (_DATED_TARGET, _START),
    (_DATED_TARGET, _END),
    (_DATED_TARGET, _LOCATION),
)


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _case(target: str, *, view_candidate: bool = False) -> CalendarInputs:
    if target == _TITLE_TARGET:
        available = (*_TITLE_FIELDS, _DATE)
        requested = _TITLE_FIELDS
        query = "搞个卡片，看看下个评审会是什么、几点开始"
    else:
        available = _FIVE_FIELDS
        requested = _DATE_FIELDS
        query = "月末要开评审会，帮我弄个卡片看看日期时间和地点"
    task, bindings, card, intent = _inputs(available, view_candidate=view_candidate)
    if target == _TITLE_TARGET:
        schema = deepcopy(task.dataModelSchema)
        _first_event(schema)["countdownDays"] = {"type": "integer", "sampleValue": 2}
        task = task.model_copy(update={"dataModelSchema": schema})
        binding = bindings[0].model_copy(
            update={"candidateOutputFields": [*bindings[0].candidateOutputFields, _COUNTDOWN]}
        )
        bindings = (binding,)
    intent = intent.model_copy(update={"required_output_fields_by_capability": {_CAP: requested}})
    if target == _TITLE_TARGET:
        intent = intent.model_copy(update={"primary_output_field_by_capability": {_CAP: _TITLE}})
    task = task.model_copy(update={"size": "2x4", "userQuery": query})
    card["suggestSize"] = "2x4"
    return CalendarInputs(task, bindings, card, intent)


@pytest.mark.parametrize("target", [_TITLE_TARGET, _DATED_TARGET])
@pytest.mark.parametrize("view_candidate", [False, True])
@pytest.mark.asyncio
async def test_two_wide_shapes_compile_only_after_original_miss(
    monkeypatch: pytest.MonkeyPatch,
    registry: CardPlanRegistry,
    target: str,
    view_candidate: bool,
) -> None:
    inputs = _case(target, view_candidate=view_candidate)
    original = deepcopy(inputs)
    with pytest.raises(TemplateRetrievalMiss):
        _old_plans(inputs, registry)
    _pipeline_registry(monkeypatch, registry)
    calls: list[Any] = []

    def record(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0])
        return plan_calendar_no_action_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", record)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("WideFullOnlyLayout@1",{{}},Template("{target}",{{}}));'

    output = await pipeline.generate_template_a2ui(
        inputs.task, inputs.card, inputs.bindings, Model()
    )
    assert calls == [original.intent]
    assert output.template_ids == (target, "WideFullOnlyLayout@1")
    assert output.projected_task_spec.eventCandidates == []
    assert '"component":"Button"' not in output.a2ui
    assert '"call":"clickToIntent"' not in output.a2ui
    if target == _TITLE_TARGET:
        event = _first_event(output.projected_task_spec.dataModelSchema)
        assert set(event) == {"title", "dtStart"}
        assert "startDate" not in output.a2ui
        assert "countdownDays" not in output.a2ui
    else:
        assert "/data/calendar/events/0/title" in output.a2ui
    assert inputs == original


def test_title_wide_needs_only_two_authorized_fields(registry: CardPlanRegistry) -> None:
    inputs = _inputs(_TITLE_FIELDS)
    inputs = inputs._replace(task=inputs.task.model_copy(update={"size": "2x4"}))
    inputs.card["suggestSize"] = "2x4"
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.plans[0].business_slots[0].template_id == _TITLE_TARGET
    assert result.intent == inputs.intent


def test_title_wide_is_hidden_from_default_search_and_prompt(registry: CardPlanRegistry) -> None:
    inputs = _case(_TITLE_TARGET)
    assert not registry.template_is_enabled(_TITLE_TARGET)
    prompt = str(build_template_retrieval_prompt(inputs.task, registry, inputs.bindings))
    assert _TITLE_TARGET not in prompt
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(
            inputs.intent,
            inputs.task,
            registry,
            inputs.bindings,
            inputs.card,
            preferred_template_ids=(_TITLE_TARGET,),
        )


@pytest.mark.parametrize(("target", "field"), _REQUIRED_CASES)
@pytest.mark.parametrize("missing_from", ["candidate", "schema"])
def test_every_template_required_field_must_exist_and_be_authorized(
    registry: CardPlanRegistry, target: str, field: str, missing_from: str
) -> None:
    inputs = _case(target)
    if missing_from == "candidate":
        fields = list(inputs.bindings[0].candidateOutputFields)
        fields.remove(field)
        binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": fields})
        inputs = inputs._replace(bindings=(binding,))
    else:
        schema = deepcopy(inputs.task.dataModelSchema)
        _first_event(schema).pop(field.rsplit("/", 1)[-1])
        inputs = inputs._replace(task=inputs.task.model_copy(update={"dataModelSchema": schema}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(("target", "field"), _REQUIRED_CASES)
def test_wrong_declared_type_cannot_match(
    registry: CardPlanRegistry, target: str, field: str
) -> None:
    inputs = _case(target)
    schema = deepcopy(inputs.task.dataModelSchema)
    leaf = _first_event(schema).get(field.rsplit("/", 1)[-1])
    assert isinstance(leaf, dict)
    leaf.update(type="integer", sampleValue=0)
    inputs = inputs._replace(task=inputs.task.model_copy(update={"dataModelSchema": schema}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize("target", [_TITLE_TARGET, _DATED_TARGET])
@pytest.mark.parametrize("extra", [_COUNTDOWN, "/eventCount", "/events/1/title"])
def test_extra_requested_fields_are_not_dropped(
    registry: CardPlanRegistry, target: str, extra: str
) -> None:
    inputs = _case(target)
    fields = inputs.intent.required_output_fields_by_capability.get(_CAP)
    assert fields is not None
    intent = inputs.intent.model_copy(
        update={"required_output_fields_by_capability": {_CAP: (*fields, extra)}}
    )
    assert _fallback(inputs._replace(intent=intent), registry) is None


@pytest.mark.parametrize("target", [_TITLE_TARGET, _DATED_TARGET])
@pytest.mark.parametrize(
    "query",
    [
        "显示日程信息，点击查看详情",
        "不需要按钮但要点击卡片打开日历",
        "显示每条日程的信息",
        "显示各日程的日期和时间",
        "显示两项日程的信息",
    ],
)
def test_explicit_actions_and_multiple_events_still_reject(
    registry: CardPlanRegistry, target: str, query: str
) -> None:
    inputs = _case(target)
    inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize("target", [_TITLE_TARGET, _DATED_TARGET])
def test_actions_and_trusted_scope_cannot_be_bypassed(
    registry: CardPlanRegistry, target: str
) -> None:
    inputs = _case(target, view_candidate=True)
    intent = inputs.intent.model_copy(update={"action_ids": (_VIEW,)})
    assert _fallback(inputs._replace(intent=intent), registry) is None
    assert _fallback(inputs, registry, trusted_template_action_ids=(_VIEW,)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(target,)) is not None
    other = _DATED_TARGET if target == _TITLE_TARGET else _TITLE_TARGET
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(other,)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(target, other)) is None


@pytest.mark.parametrize("target", [_TITLE_TARGET, _DATED_TARGET])
def test_disabled_template_and_provider_controls_remain_effective(target: str) -> None:
    inputs = _case(target)
    assert _fallback(inputs, CardPlanRegistry(disabled_template_ids=(target,))) is None
    disabled = CardPlanRegistry(disabled_provider_ids=("com.huawei.calendar.cli",))
    assert _fallback(inputs, disabled) is None


@pytest.mark.parametrize("target", [_TITLE_TARGET, _DATED_TARGET])
def test_mixed_business_and_distinct_roots_still_reject(
    registry: CardPlanRegistry, target: str
) -> None:
    inputs = _case(target)
    other = CandidateDataBinding(capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/battery")
    assert _fallback(inputs._replace(bindings=(*inputs.bindings, other)), registry) is None
    card = {
        **inputs.card,
        "dataBindings": [{"capabilityId": _CAP, "writeResultTo": "/data/anotherCalendar"}],
    }
    assert _fallback(inputs._replace(card=card), registry) is None
    required = dict(inputs.intent.required_output_fields_by_capability)
    required["GetPhoneBatteryInfo"] = ("/level",)
    intent = inputs.intent.model_copy(update={"required_output_fields_by_capability": required})
    assert _fallback(inputs._replace(intent=intent), registry) is None


def test_existing_five_field_branch_preserves_original_intent(registry: CardPlanRegistry) -> None:
    inputs = _case(_DATED_TARGET)
    intent = inputs.intent.model_copy(
        update={"required_output_fields_by_capability": {_CAP: _FIVE_FIELDS}}
    )
    inputs = inputs._replace(intent=intent)
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.intent == inputs.intent
    assert result.plans[0].business_slots[0].template_id == _DATED_TARGET
    assert set(result.plans[0].business_slots[0].covered_explicit_fields) == set(_FIVE_FIELDS)


@pytest.mark.parametrize(
    ("target", "old_template"),
    [
        (_TITLE_TARGET, "ScheduleOverviewTitleTimeFull@1"),
        (_DATED_TARGET, "ScheduleOverviewDateFull@1"),
    ],
)
@pytest.mark.asyncio
async def test_existing_square_success_never_calls_new_fallback(
    monkeypatch: pytest.MonkeyPatch,
    registry: CardPlanRegistry,
    target: str,
    old_template: str,
) -> None:
    inputs = _case(target, view_candidate=True)
    inputs = inputs._replace(task=inputs.task.model_copy(update={"size": "2x2"}))
    inputs.card["suggestSize"] = "2x2"
    plans = _old_plans(inputs, registry)
    assert plans[0].business_slots[0].template_id == old_template
    _pipeline_registry(monkeypatch, registry)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("原小卡已匹配，不得调用宽卡 fallback")

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", forbidden)
    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", forbidden)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("SingleFocusLayout@1",{{}},Template("{old_template}",{{}}));'

    output = await pipeline.generate_template_a2ui(
        inputs.task, inputs.card, inputs.bindings, Model()
    )
    assert output.template_ids == (old_template, "SingleFocusLayout@1")
