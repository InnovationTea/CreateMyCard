"""新增日程形态仅补原匹配失败，保留字段、动作和旧成功路径。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, NamedTuple

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_action_policy import (
    resolve_calendar_view_fallback,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_VIEW = "event.viewCalendarEvent"
_TITLE = "/events/0/title"
_START = "/events/0/dtStart"
_END = "/events/0/dtEnd"
_DATE = "/events/0/startDate"
_LOCATION = "/events/0/eventLocation"
_ALL_DAY = "/events/0/isAllDay"
_REMINDER = "/events/0/remindTime/0"
_DETAILS = (
    "/events/0/senderName",
    "/events/0/importantEventType",
    _REMINDER,
    "/updatedAt",
)
_DATED_MEETING = (_DATE, _TITLE, _START, _END, _LOCATION)


class Case(NamedTuple):
    case_id: str
    size: str
    suffix: str
    query: str
    fields: tuple[str, ...]


_CASES = (
    Case(
        "802e",
        "2x2",
        "ReminderStartFull",
        "显示日程标题、开始时间和提前提醒分钟数",
        (_TITLE, _START, _REMINDER),
    ),
    Case("84c9", "2x2", "DateEndFull", "看看时区日程的标题、日期和结束时间", (_TITLE, _DATE, _END)),
    Case(
        "84d4", "2x4", "ReminderDetailsWideFull", "显示邀请人、重要程度、提醒和更新时间", _DETAILS
    ),
    Case(
        "8889", "2x2", "AllDayLocationFull", "显示异地日程的全天状态和地点", (_ALL_DAY, _LOCATION)
    ),
    Case("888e", "2x2", "ReminderStartFull", "显示下个安排的时间和提前提醒", (_START, _REMINDER)),
    Case(
        "9547",
        "2x2",
        "AllDayLocationFull",
        "看看时区日程的标题、是不是全天、在哪儿",
        (_TITLE, _ALL_DAY, _LOCATION),
    ),
    Case(
        "95d9",
        "2x2",
        "DateAllDayFull",
        "显示日程开始日期、标题，再标一下是否全天日程",
        (_DATE, _TITLE, _ALL_DAY),
    ),
    Case("a2a2", "2x2", "TitleStartFull", "做个卡片，显示日程标题和开始时间", (_TITLE, _START)),
    Case(
        "a6c4",
        "2x4",
        "DatedMeetingWideFull",
        "显示日程开始日期、标题、开始结束时间和地点",
        _DATED_MEETING,
    ),
    Case(
        "aa3c",
        "2x2",
        "DateStartLocationFull",
        "把那个安排的日期、几点、在哪儿都显示出来",
        (_DATE, _START, _LOCATION),
    ),
    Case(
        "aeb5",
        "2x2",
        "DateStartLocationFull",
        "加个卡片到桌面，显示那天的日程详情",
        (_TITLE, _DATE, _START, _LOCATION),
    ),
    Case(
        "aed3",
        "2x4",
        "DatedMeetingWideFull",
        "搞个完整日程卡片，看看日期、标题、时间段和地点",
        _DATED_MEETING,
    ),
    Case(
        "bfdb", "2x2", "TitleStartFull", "加个卡片到桌面，显示日程名称和开始时间", (_TITLE, _START)
    ),
)
_MINIMAL = (_CASES[7], _CASES[4], _CASES[6], _CASES[1], _CASES[3], _CASES[9], _CASES[2], _CASES[8])
_NEW_IDS = tuple(f"ScheduleOverview{case.suffix}@1" for case in _MINIMAL)


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _case(case: Case, *, view_candidate: bool = False) -> CalendarInputs:
    task, bindings, card, intent = _inputs(case.fields, view_candidate=view_candidate)
    task = task.model_copy(update={"size": case.size, "userQuery": case.query})
    card["suggestSize"] = case.size
    return CalendarInputs(task, bindings, card, intent)


def _fallback(inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    return plan_calendar_no_action_fallback(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card, **kwargs
    )


def _old_plans(inputs: CalendarInputs, registry: CardPlanRegistry) -> Any:
    found = search_template_variants(
        inputs.intent, inputs.task, registry, inputs.bindings, inputs.card
    )
    resolved = resolve_calendar_view_fallback(inputs.intent, found, inputs.task, registry)
    return plan_template_candidates(resolved, found, inputs.task, registry)


def _pipeline_registry(monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry) -> None:
    controls = TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search"
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.case_id)
@pytest.mark.asyncio
async def test_richeng_thirteen_intents_compile_only_after_original_miss(
    monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry, case: Case
) -> None:
    inputs = _case(case, view_candidate=case.case_id in {"a6c4", "aa3c", "aeb5", "aed3"})
    with pytest.raises(TemplateRetrievalMiss):
        _old_plans(inputs, registry)
    original = deepcopy(inputs)
    _pipeline_registry(monkeypatch, registry)
    calls: list[Any] = []

    def record(*args: Any, **kwargs: Any) -> Any:
        calls.append(args[0])
        return plan_calendar_no_action_fallback(*args, **kwargs)

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", record)
    target = f"ScheduleOverview{case.suffix}@1"
    layout = "SingleFocusLayout@1" if case.size == "2x2" else "WideFullOnlyLayout@1"

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return f'Template("{layout}",{{}},Template("{target}",{{}}));'

    output = await pipeline.generate_template_a2ui(
        inputs.task, inputs.card, inputs.bindings, Model()
    )
    assert calls == [inputs.intent]
    assert target in output.template_ids
    assert layout in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"call":"clickToIntent"' not in output.a2ui
    assert inputs == original


@pytest.mark.parametrize("case", _MINIMAL, ids=lambda case: case.suffix)
@pytest.mark.parametrize("view_candidate", [False, True])
def test_candidate_button_does_not_become_an_action(
    registry: CardPlanRegistry, case: Case, view_candidate: bool
) -> None:
    inputs = _case(case, view_candidate=view_candidate)
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.intent == inputs.intent
    assert result.plans[0].business_slots[0].template_id == f"ScheduleOverview{case.suffix}@1"
    assert result.plans[0].action_assignments == ()


def test_default_registry_and_first_prompt_hide_all_eight(registry: CardPlanRegistry) -> None:
    inputs = _case(_MINIMAL[0])
    prompt = str(build_template_retrieval_prompt(inputs.task, registry, inputs.bindings))
    for target in _NEW_IDS:
        assert not registry.template_is_enabled(target)
        assert target not in prompt
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(
            inputs.intent,
            inputs.task,
            registry,
            inputs.bindings,
            inputs.card,
            preferred_template_ids=(_NEW_IDS[0],),
        )


@pytest.mark.asyncio
async def test_950a_keeps_original_plan_and_never_calls_fallback(
    monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry
) -> None:
    task, bindings, card, intent = _inputs((_TITLE, _DATE, _START, _LOCATION), view_candidate=True)
    schema = deepcopy(task.dataModelSchema)
    _first_event(schema)["countdownDays"] = {"type": "integer", "sampleValue": 2}
    task = task.model_copy(update={"dataModelSchema": schema})
    bindings = (
        bindings[0].model_copy(
            update={
                "candidateOutputFields": [
                    *bindings[0].candidateOutputFields,
                    "/events/0/countdownDays",
                ]
            }
        ),
    )
    task = task.model_copy(update={"userQuery": "帮我整个卡片，看看下一个安排是什么时候、在哪儿"})
    intent = intent.model_copy(
        update={"required_output_fields_by_capability": {_CAP: (_START, _LOCATION)}}
    )
    inputs = CalendarInputs(task, bindings, card, intent)
    plans = _old_plans(inputs, registry)
    assert plans[0].layout_template_id == "SingleFocusLayout@1"
    assert plans[0].business_slots[0].template_id == "ScheduleOverviewNextEventLocationFull@1"
    assert plans[0].action_assignments == ()
    _pipeline_registry(monkeypatch, registry)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("950a原匹配成功，不得调用任何无按钮补充分支")

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", forbidden)
    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", forbidden)

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                'Template("SingleFocusLayout@1",{},'
                'Template("ScheduleOverviewNextEventLocationFull@1",{}));'
            )

    output = await pipeline.generate_template_a2ui(task, card, bindings, Model())
    assert "ScheduleOverviewNextEventLocationFull@1" in output.template_ids
    assert not set(_NEW_IDS).intersection(output.template_ids)


@pytest.mark.parametrize("case", _MINIMAL, ids=lambda case: case.suffix)
def test_missing_required_candidate_or_wrong_size_cannot_match(
    registry: CardPlanRegistry, case: Case
) -> None:
    inputs = _case(case)
    reduced = inputs.bindings[0].model_copy(
        update={"candidateOutputFields": list(case.fields[:-1])}
    )
    assert _fallback(inputs._replace(bindings=(reduced,)), registry) is None
    wrong_size = "2x4" if case.size == "2x2" else "2x2"
    wrong = inputs._replace(task=inputs.task.model_copy(update={"size": wrong_size}))
    result = _fallback(wrong, registry)
    # 另一尺寸可以具有自己的完整形态，但不能错误选中原尺寸的目标。
    if result is not None:
        assert result.plans[0].business_slots[0].template_id != f"ScheduleOverview{case.suffix}@1"


@pytest.mark.parametrize("extras", [(), (_TITLE,), (_END,), (_TITLE, _END)])
def test_requested_optional_fields_are_covered_and_require_authorization(
    registry: CardPlanRegistry, extras: tuple[str, ...]
) -> None:
    case = Case(
        "optional",
        "2x2",
        "DateStartLocationFull",
        "显示日程信息",
        (_DATE, _START, _LOCATION, *extras),
    )
    inputs = _case(case)
    result = _fallback(inputs, registry)
    assert result is not None
    assert set(result.plans[0].business_slots[0].covered_explicit_fields) == set(case.fields)
    if extras:
        reduced = inputs.bindings[0].model_copy(
            update={"candidateOutputFields": [_DATE, _START, _LOCATION]}
        )
        assert _fallback(inputs._replace(bindings=(reduced,)), registry) is None


@pytest.mark.parametrize("extra", ["/events/1/title", "/eventCount", "/events/0/description"])
def test_extra_requested_fields_are_never_removed(registry: CardPlanRegistry, extra: str) -> None:
    inputs = _inputs((_TITLE, _START, extra))
    assert _fallback(inputs, registry) is None


@pytest.mark.parametrize(
    "query",
    [
        "显示标题和开始时间，点击查看详情",
        "不需要按钮，但点击卡片打开日历",
        "显示标题和开始时间，并编辑这个日程",
        "显示每条日程的日期、标题、时间和地点",
        "显示两项日程的日期、标题、时间和地点",
        "显示各日程的日期、标题、时间和地点",
        "显示日期、标题、时间和地点，共两项",
    ],
)
def test_new_templates_reject_explicit_actions_and_multiple_events(
    registry: CardPlanRegistry, query: str
) -> None:
    inputs = _case(_CASES[8])
    task = inputs.task.model_copy(update={"userQuery": query})
    assert _fallback(inputs._replace(task=task), registry) is None


@pytest.mark.parametrize(
    "query",
    [
        "无需打开日历，显示日程标题和开始时间",
        "不要查看详情按钮，只显示标题和开始时间",
        "添加卡片到桌面，显示日程标题和开始时间",
    ],
)
def test_no_action_queries_remain_allowed(registry: CardPlanRegistry, query: str) -> None:
    inputs = _case(_CASES[7])
    assert (
        _fallback(
            inputs._replace(task=inputs.task.model_copy(update={"userQuery": query})), registry
        )
        is not None
    )


def test_actions_trusted_candidates_and_disabled_controls_remain_effective(
    registry: CardPlanRegistry,
) -> None:
    inputs = _case(_CASES[7], view_candidate=True)
    target = "ScheduleOverviewTitleStartFull@1"
    action_intent = inputs.intent.model_copy(update={"action_ids": (_VIEW,)})
    assert _fallback(inputs._replace(intent=action_intent), registry) is None
    assert _fallback(inputs, registry, trusted_template_action_ids=(_VIEW,)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(target,)) is not None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(_NEW_IDS[1],)) is None
    assert _fallback(inputs, registry, trusted_template_candidate_ids=(target, _NEW_IDS[1])) is None
    assert _fallback(inputs, CardPlanRegistry(disabled_template_ids=(target,))) is None
    disabled = CardPlanRegistry(disabled_provider_ids=("com.huawei.calendar.cli",))
    assert _fallback(inputs, disabled) is None


def test_mixed_capability_or_distinct_roots_are_rejected(registry: CardPlanRegistry) -> None:
    inputs = _case(_CASES[7])
    other = CandidateDataBinding(capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/battery")
    assert _fallback(inputs._replace(bindings=(*inputs.bindings, other)), registry) is None
    card = {
        **inputs.card,
        "dataBindings": [{"capabilityId": _CAP, "writeResultTo": "/data/anotherCalendar"}],
    }
    assert _fallback(inputs._replace(card=card), registry) is None
    intent = inputs.intent.model_copy(
        update={
            "required_output_fields_by_capability": {
                _CAP: (_TITLE, _START),
                "GetPhoneBatteryInfo": ("/level",),
            }
        }
    )
    assert _fallback(inputs._replace(intent=intent), registry) is None


def _first_event(schema: dict[str, Any]) -> dict[str, Any]:
    data = schema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    events = calendar.get("events")
    assert isinstance(events, list) and events
    event = events[0]
    assert isinstance(event, dict)
    return event


@pytest.mark.parametrize(
    ("case", "field", "value", "bad_type"),
    [
        (_CASES[3], "isAllDay", False, "string"),
        (_CASES[2], "importantEventType", 0, "boolean"),
    ],
)
def test_false_and_zero_are_valid_but_wrong_types_are_rejected(
    registry: CardPlanRegistry, case: Case, field: str, value: Any, bad_type: str
) -> None:
    inputs = _case(case)
    schema = deepcopy(inputs.task.dataModelSchema)
    leaf = _first_event(schema).get(field)
    assert isinstance(leaf, dict)
    leaf["sampleValue"] = value
    task = inputs.task.model_copy(update={"dataModelSchema": schema})
    assert _fallback(inputs._replace(task=task), registry) is not None
    leaf["type"] = bad_type
    assert _fallback(inputs._replace(task=task), registry) is None


def test_second_event_is_not_silently_dropped(registry: CardPlanRegistry) -> None:
    inputs = _case(_CASES[11])
    schema = deepcopy(inputs.task.dataModelSchema)
    first = deepcopy(_first_event(schema))
    data = schema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    events = calendar.get("events")
    assert isinstance(events, list)
    events.append(first)
    second_fields = tuple(field.replace("/events/0/", "/events/1/") for field in _DATED_MEETING)
    bindings = (
        inputs.bindings[0].model_copy(
            update={"candidateOutputFields": list((*_DATED_MEETING, *second_fields))}
        ),
    )
    inputs = inputs._replace(
        task=inputs.task.model_copy(update={"dataModelSchema": schema}), bindings=bindings
    )
    # aed3本次明确首项的意图可以匹配；不是完整列表成功的断言。
    assert _fallback(inputs, registry) is not None
    intent = inputs.intent.model_copy(
        update={"required_output_fields_by_capability": {_CAP: (*_DATED_MEETING, *second_fields)}}
    )
    assert _fallback(inputs._replace(intent=intent), registry) is None
    task = inputs.task.model_copy(update={"userQuery": "显示每条日程的日期、标题、时间段和地点"})
    assert _fallback(inputs._replace(task=task), registry) is None


@pytest.mark.parametrize(
    ("size", "fields", "target"),
    [
        ("2x2", ("/events/0/senderName", _REMINDER), "SourceReminderFull"),
        ("2x4", ("/events/0/timeZone", _START, _LOCATION), "TimezoneWideFull"),
        ("2x4", ("/eventCount", "/events/0/description"), "EventCountDetailsWideFull"),
        ("2x4", (_START, _REMINDER), "ReminderWideFull"),
    ],
)
def test_existing_single_fallback_shapes_keep_their_original_templates(
    registry: CardPlanRegistry, size: str, fields: tuple[str, ...], target: str
) -> None:
    inputs = _case(Case("old", size, target, "展示下个日程的信息", fields))
    result = _fallback(inputs, registry)
    assert result is not None
    assert result.plans[0].business_slots[0].template_id == f"ScheduleOverview{target}@1"
