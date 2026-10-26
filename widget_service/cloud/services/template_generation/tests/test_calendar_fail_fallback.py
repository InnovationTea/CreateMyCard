"""失败语料新增入口的正式检索、规划、编译及授权边界。"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any, NamedTuple

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_list_no_action_policy import (
    plan_calendar_list_no_action_fallback,
)
from services.template_generation.engine.cardplan.calendar_mixed_no_action_policy import (
    plan_calendar_weather_no_action_fallback,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    build_template_retrieval_prompt,
)
from services.template_generation.tests.test_calendar_additional_no_action_fallback import (
    _old_plans,
    _pipeline_registry,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_WEATHER = "ViewWeather"
_TITLE = "/events/0/title"
_START = "/events/0/dtStart"
_END = "/events/0/dtEnd"
_DATE = "/events/0/startDate"
_LOCATION = "/events/0/eventLocation"
_ALL_DAY = "/events/0/isAllDay"
_ZONE = "/events/0/timeZone"
_NOTES = "/events/0/description"
_REMINDER = "/events/0/remindTime/0"
_DETAILS = ("/events/0/senderName", "/events/0/importantEventType", _REMINDER)
_VIEW = "event.viewCalendarEvent"


class Case(NamedTuple):
    name: str
    size: str
    suffix: str
    fields: tuple[str, ...]
    query: str
    context: tuple[str, ...] = ()
    route: str = "single"

    @property
    def target(self) -> str:
        return f"ScheduleOverview{self.suffix}@1"


def _rows(count: int, roles: tuple[str, ...], *, with_count: bool = False) -> tuple[str, ...]:
    fields = ["/eventCount"] if with_count else []
    for index in range(count):
        for role in roles:
            fields.append(f"/events/{index}/{role}")
    return tuple(fields)


_CASES = (
    Case("no_date", "2x2", "DateAllDayFull", (_TITLE, _ALL_DAY), "显示日程标题和全天状态"),
    Case("date_end", "2x2", "DateEndFull", (_DATE, _END), "显示日程日期和结束时间", (_TITLE,)),
    Case(
        "reminder_three", "2x4", "ReminderDetailsWideFull", _DETAILS, "显示发起人、重要程度和提醒"
    ),
    Case(
        "location_start",
        "2x4",
        "DatedMeetingWideFull",
        (_START, _LOCATION),
        "显示下一场日程的开始时间和地点",
        (_TITLE,),
    ),
    Case(
        "dated_no_end",
        "2x4",
        "DatedMeetingWideFull",
        (_TITLE, _DATE, _START, _LOCATION),
        "显示日程标题、日期、开始时间和地点",
    ),
    Case(
        "wide_date_all_day",
        "2x4",
        "DateAllDayWideFull",
        (_DATE, _TITLE, _ALL_DAY),
        "显示日程日期、标题和全天状态",
    ),
    Case(
        "wide_location_notes_end",
        "2x4",
        "LocationDescriptionEndWideFull",
        (_NOTES, _END, _LOCATION),
        "显示下一场日程备注、结束时间和地点",
    ),
    Case(
        "wide_all_day_location",
        "2x4",
        "AllDayLocationWideFull",
        (_ALL_DAY, _LOCATION),
        "显示下一场日程是不是全天和地点",
    ),
    Case(
        "wide_all_day_context",
        "2x4",
        "AllDayLocationWideFull",
        (_TITLE, _ZONE, _ALL_DAY, _LOCATION),
        "显示日程标题、时区、全天状态和地点",
    ),
    Case(
        "two_start",
        "2x4",
        "TwoEventsWideFull",
        _rows(2, ("dtStart",)),
        "显示两件事的开始时间",
        route="list",
    ),
    Case(
        "two_title_start",
        "2x4",
        "TwoEventsWideFull",
        _rows(2, ("title", "dtStart")),
        "分别显示两场会议的标题和开始时间",
        route="list",
    ),
    Case(
        "two_full",
        "2x4",
        "TwoEventsWideFull",
        _rows(2, ("title", "dtStart", "dtEnd", "eventLocation")),
        "分别显示两场会议的标题、开始结束时间和地点",
        route="list",
    ),
    Case(
        "three_details",
        "2x4",
        "EventCountThreeDetailsWideFull",
        _rows(3, ("title", "dtStart", "description"), with_count=True),
        "显示日程数量和三场会议各自的标题、开始时间、备注",
        route="list",
    ),
    Case(
        "mixed_location",
        "2x4",
        "TitleLocationHero",
        (_TITLE, _LOCATION),
        "显示日程标题、地点和天气状况",
        route="mixed",
    ),
)
_BY_NAME = {case.name: case for case in _CASES}
_ROUTES = {
    "single": plan_calendar_no_action_fallback,
    "list": plan_calendar_list_no_action_fallback,
    "mixed": plan_calendar_weather_no_action_fallback,
}
_REPRESENTATIVES = (_CASES[0], _CASES[9], _CASES[-1])


@lru_cache(maxsize=12)
def _registry(**kwargs: Any) -> CardPlanRegistry:
    return CardPlanRegistry(**kwargs)


def _calendar(schema: dict[str, Any]) -> dict[str, Any]:
    data = schema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    return calendar


def _case(case: Case, *, view_candidate: bool = False) -> CalendarInputs:
    candidates = tuple(dict.fromkeys((*case.fields, *case.context)))
    local_fields: list[str] = []
    for path in candidates:
        parts = path.split("/")
        local = "/events/0/" + "/".join(parts[3:]) if path.startswith("/events/") else path
        if local not in local_fields:
            local_fields.append(local)
    task, bindings, card, intent = _inputs(tuple(local_fields), view_candidate=view_candidate)
    schema = deepcopy(task.dataModelSchema)
    calendar = _calendar(schema)
    old_events = calendar.get("events")
    assert isinstance(old_events, list)
    first = old_events[0]
    assert isinstance(first, dict)
    events: list[dict[str, Any]] = []
    for path in candidates:
        if not path.startswith("/events/"):
            continue
        parts = path.split("/")
        index = int(parts[2])
        while len(events) <= index:
            events.append({})
        leaf = first.get(parts[3])
        assert leaf is not None
        events[index][parts[3]] = deepcopy(leaf)
    if view_candidate:
        entity = first.get("entityId")
        assert entity is not None
        events[0]["entityId"] = deepcopy(entity)
    calendar["events"] = events
    task = task.model_copy(
        update={"size": case.size, "userQuery": case.query, "dataModelSchema": schema}
    )
    binding = bindings[0].model_copy(update={"candidateOutputFields": list(candidates)})
    card["suggestSize"] = case.size
    intent = intent.model_copy(
        update={
            "required_output_fields_by_capability": {_CAP: case.fields},
            "allow_calendar_view_fallback": False,
        }
    )
    result = CalendarInputs(task, (binding,), card, intent)
    return _with_weather(result) if case.route == "mixed" else result


def _with_weather(inputs: CalendarInputs) -> CalendarInputs:
    schema = deepcopy(inputs.task.dataModelSchema)
    data = schema.get("data")
    assert isinstance(data, dict)
    data["weather"] = {"current": {"condition": {"type": "string", "sampleValue": "多云"}}}
    task = inputs.task.model_copy(update={"dataModelSchema": schema})
    binding = CandidateDataBinding(
        capabilityId=_WEATHER,
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )
    card = deepcopy(inputs.card)
    card_bindings = card.get("dataBindings")
    assert isinstance(card_bindings, list)
    card_bindings.append({"capabilityId": _WEATHER, "writeResultTo": "/data/weather"})
    required = dict(inputs.intent.required_output_fields_by_capability)
    required[_WEATHER] = ("/current/condition",)
    intent = inputs.intent.model_copy(update={"required_output_fields_by_capability": required})
    return CalendarInputs(task, (*inputs.bindings, binding), card, intent)


def _fallback(case: Case, inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    method = _ROUTES.get(case.route)
    assert method is not None
    original = deepcopy(inputs)
    result = method(inputs.intent, inputs.task, registry, inputs.bindings, inputs.card, **kwargs)
    assert inputs == original
    return result


async def _compile(inputs: CalendarInputs, plan: Any) -> Any:
    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            children = []
            for slot in plan.business_slots:
                children.append(f'Template("{slot.template_id}",{{}})')
            return f'Template("{plan.layout_template_id}",{{}},{",".join(children)});'

    return await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.name)
@pytest.mark.asyncio
async def test_new_entries_compile_after_old_miss_without_losing_fields(
    monkeypatch: pytest.MonkeyPatch, case: Case
) -> None:
    inputs = _case(case)
    original = deepcopy(inputs)
    registry = _registry()
    with pytest.raises(TemplateRetrievalMiss):
        _old_plans(inputs, registry)
    result = _fallback(case, inputs, registry)
    assert result is not None
    assert result.intent == inputs.intent
    plan = result.plans[0]
    assert case.target in tuple(slot.template_id for slot in plan.business_slots)
    assert plan.action_assignments == ()
    _pipeline_registry(monkeypatch, registry)
    selected: list[str] = []
    method = _ROUTES.get(case.route)
    assert method is not None

    def record(*args: Any, **kwargs: Any) -> Any:
        fallback = method(*args, **kwargs)
        if fallback is not None:
            selected.append(case.target)
        return fallback

    monkeypatch.setattr(pipeline, method.__name__, record)
    output = await _compile(inputs, plan)
    assert selected == [case.target]
    assert case.target in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"Button"' not in output.a2ui
    assert "clickToIntent" not in output.a2ui
    for binding in inputs.bindings:
        for path in binding.candidateOutputFields:
            assert f"{binding.writeResultTo}{path}" in output.a2ui
    assert inputs == original


@pytest.mark.parametrize("case", _REPRESENTATIVES, ids=lambda case: case.name)
def test_candidate_button_does_not_require_an_action(case: Case) -> None:
    inputs = _case(case, view_candidate=True)
    result = _fallback(case, inputs, _registry())
    assert result is not None
    assert result.intent.action_ids == ()
    assert result.plans[0].action_assignments == ()


def _blocked_input(inputs: CalendarInputs, reason: str) -> CalendarInputs:
    result = deepcopy(inputs)
    if reason == "selected_action":
        result = result._replace(intent=result.intent.model_copy(update={"action_ids": (_VIEW,)}))
    elif reason == "explicit_action":
        result = result._replace(
            task=result.task.model_copy(update={"userQuery": "显示日程并添加查看详情按钮"})
        )
    elif reason == "wrong_size":
        result = result._replace(task=result.task.model_copy(update={"size": "1x1"}))
    elif reason == "card_root_mismatch":
        bindings = result.card.get("dataBindings")
        assert isinstance(bindings, list)
        bindings[0]["writeResultTo"] = "/data/otherCalendar"
    elif reason == "missing_candidate":
        first = result.bindings[0]
        updated = first.model_copy(
            update={"candidateOutputFields": first.candidateOutputFields[1:]}
        )
        result = result._replace(bindings=(updated, *result.bindings[1:]))
    elif reason == "untyped_field":
        events = _calendar(result.task.dataModelSchema).get("events")
        assert isinstance(events, list)
        first_role = next(iter(events[0]))
        events[0][first_role] = {"sampleValue": "存在样例但没有类型"}
    elif reason == "extra_binding":
        result = result._replace(bindings=(*result.bindings, result.bindings[0]))
    else:
        raise AssertionError(reason)
    return result


@pytest.mark.parametrize("case", _REPRESENTATIVES, ids=lambda case: case.name)
@pytest.mark.parametrize(
    "reason",
    (
        "selected_action",
        "explicit_action",
        "wrong_size",
        "card_root_mismatch",
        "missing_candidate",
        "untyped_field",
        "extra_binding",
    ),
)
def test_new_routes_keep_input_and_authorization_boundaries(case: Case, reason: str) -> None:
    inputs = _blocked_input(_case(case, view_candidate=True), reason)
    assert _fallback(case, inputs, _registry()) is None


@pytest.mark.parametrize("case", _REPRESENTATIVES, ids=lambda case: case.name)
@pytest.mark.parametrize(
    "restriction", ("disabled", "provider", "trusted_template", "trusted_action", "trusted_layout")
)
def test_new_routes_respect_controls_and_trusted_scope(case: Case, restriction: str) -> None:
    registry = _registry()
    kwargs: dict[str, Any] = {}
    if restriction == "disabled":
        registry = _registry(disabled_template_ids=(case.target,))
    elif restriction == "provider":
        registry = _registry(disabled_provider_ids=("com.huawei.calendar.cli",))
    elif restriction == "trusted_template":
        kwargs["trusted_template_candidate_ids"] = ("ScheduleOverviewTitleHero@1",)
    elif restriction == "trusted_action":
        kwargs["trusted_template_action_ids"] = (_VIEW,)
    else:
        kwargs["trusted_template_layout_ids"] = ("not-an-allowed-layout",)
    assert _fallback(case, _case(case), registry, **kwargs) is None


@pytest.mark.parametrize(
    ("name", "context", "query"),
    (
        ("no_date", (_DATE,), "显示日程标题和全天状态，不要日期"),
        ("date_end", (), "只显示日程日期和结束时间"),
        ("date_end", (), "显示日程日期和结束时间，不要标题"),
        ("reminder_three", ("/updatedAt",), "显示发起人、重要程度和提醒，不要更新时间"),
        ("location_start", (), "只显示日程开始时间和地点"),
        ("location_start", (_DATE,), "显示开始时间和地点，不要日期"),
        ("wide_all_day_location", (_ZONE,), "显示全天状态和地点，不要时区"),
        ("two_start", _rows(2, ("title",)), "只显示两件事的开始时间"),
        ("two_start", _rows(2, ("eventLocation",)), "显示两件事的开始时间，不要地点"),
    ),
)
def test_exclusive_queries_reject_candidate_only_extra_display(
    name: str, context: tuple[str, ...], query: str
) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    case = case._replace(context=(*case.context, *context), query=query)
    assert _fallback(case, _case(case), _registry()) is None


@pytest.mark.parametrize("name", ("no_date", "reminder_three", "two_start"))
def test_exclusive_queries_allow_exact_display_without_extra_context(name: str) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    case = case._replace(query="只" + case.query)
    assert _fallback(case, _case(case), _registry()) is not None


@pytest.mark.parametrize("name", ("date_end", "location_start"))
def test_context_title_requires_explicit_candidate_authorization(name: str) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    authorized = _case(case)
    first = authorized.bindings[0]
    candidates = [path for path in first.candidateOutputFields if path != _TITLE]
    denied = authorized._replace(
        bindings=(first.model_copy(update={"candidateOutputFields": candidates}),)
    )
    assert _fallback(case, denied, _registry()) is None


@pytest.mark.parametrize("name", ("two_start", "three_details"))
@pytest.mark.parametrize(
    "reason", ("array_short", "extra_event", "asymmetric", "first_only", "wrong_count", "full_text")
)
def test_lists_never_discard_an_item_or_invent_an_array_entry(name: str, reason: str) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    inputs = _case(case)
    events = _calendar(inputs.task.dataModelSchema).get("events")
    assert isinstance(events, list)
    if reason == "array_short":
        events.pop()
    elif reason == "extra_event":
        events.append(deepcopy(events[0]))
    elif reason == "asymmetric":
        selected = list(case.fields)
        selected.remove("/events/1/dtStart")
        intent = inputs.intent.model_copy(
            update={"required_output_fields_by_capability": {_CAP: tuple(selected)}}
        )
        inputs = inputs._replace(intent=intent)
    else:
        queries = {
            "first_only": "只显示第一条日程的时间和备注",
            "wrong_count": "显示四件事的时间和备注",
            "full_text": "显示日程备注全文，不要省略",
        }
        query = queries.get(reason)
        assert query is not None
        inputs = inputs._replace(task=inputs.task.model_copy(update={"userQuery": query}))
    assert _fallback(case, inputs, _registry()) is None
    assert (
        plan_calendar_no_action_fallback(
            inputs.intent, inputs.task, _registry(), inputs.bindings, inputs.card
        )
        is None
    )


@pytest.mark.parametrize("name", ("two_start", "three_details"))
@pytest.mark.parametrize(
    "query",
    (
        "只看下一个日程的开始时间和备注",
        "仅显示最近一条日程的开始时间和备注",
    ),
)
def test_new_lists_do_not_override_an_explicit_next_event_request(name: str, query: str) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    case = case._replace(query=query)
    assert _fallback(case, _case(case), _registry()) is None


@pytest.mark.parametrize(
    ("name", "query"),
    (
        ("location_start", "显示两件事的开始时间和地点"),
        ("no_date", "显示三件事的标题和全天状态"),
        ("reminder_three", "显示2件事的发起人、重要程度和提醒"),
    ),
)
def test_new_single_routes_do_not_reduce_explicit_multiple_matters(name: str, query: str) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    case = case._replace(query=query)
    assert _fallback(case, _case(case), _registry()) is None


@pytest.mark.parametrize("count", ("一", "1", "01"))
def test_single_matter_remains_eligible(count: str) -> None:
    case = _BY_NAME.get("location_start")
    assert case is not None
    case = case._replace(query=f"显示{count}件事的开始时间和地点")
    assert _fallback(case, _case(case), _registry()) is not None


@pytest.mark.asyncio
async def test_each_event_with_only_one_typed_entry_remains_unmatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 本例没有候选标题，无法显示摘要模板的“首项：”范围标签，仍须拒绝。
    case = Case(
        "unresolved_each",
        "2x4",
        "EventCountDetailsWideFull",
        ("/eventCount", _START, _NOTES),
        "今天有哪些日程，各是几点、备注是什么，显示日程数量",
    )
    inputs = _case(case)
    original = deepcopy(inputs)
    _pipeline_registry(monkeypatch, _registry())

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            raise AssertionError("不完整的逐条需求不能进入第二层编译")

    with pytest.raises(pipeline.TemplateRouteNotApplicable):
        await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())
    assert inputs == original


@pytest.mark.parametrize(
    ("suffix", "size", "fields"),
    (
        ("DateAllDayFull", "2x2", (_TITLE, _DATE, _ALL_DAY)),
        ("ReminderDetailsWideFull", "2x4", (*_DETAILS, "/updatedAt")),
        ("DatedMeetingWideFull", "2x4", (_TITLE, _DATE, _START, _END, _LOCATION)),
    ),
)
@pytest.mark.asyncio
async def test_original_complete_inputs_still_plan_and_compile(
    monkeypatch: pytest.MonkeyPatch, suffix: str, size: str, fields: tuple[str, ...]
) -> None:
    case = Case("complete", size, suffix, fields, "展示下个日程详情")
    inputs = _case(case)
    original = deepcopy(inputs)
    result = _fallback(case, inputs, _registry())
    assert result is not None
    _pipeline_registry(monkeypatch, _registry())
    output = await _compile(inputs, result.plans[0])
    assert case.target in output.template_ids
    for path in fields:
        assert f"/data/calendar{path}" in output.a2ui
    assert inputs == original


def test_calendar_query_candidate_rule_is_present_in_calendar_scopes() -> None:
    for case in (_CASES[0], _CASES[-1]):
        inputs = _case(case)
        original = deepcopy(inputs)
        messages = build_template_retrieval_prompt(inputs.task, _registry(), inputs.bindings)
        assert "日历展示需求与候选分离" in str(messages)
        assert inputs == original


def test_calendar_query_candidate_rule_does_not_leak_to_other_businesses() -> None:
    inputs = _case(_CASES[0])
    scopes = (
        (_WEATHER, "weather", "/current/condition", {"current": {"condition": {"type": "string"}}}),
        ("GetPhoneBatteryInfo", "battery", "/batterySOC", {"batterySOC": {"type": "integer"}}),
    )
    for capability, root, path, schema in scopes:
        task = inputs.task.model_copy(update={"dataModelSchema": {"data": {root: schema}}})
        binding = CandidateDataBinding(
            capabilityId=capability, writeResultTo=f"/data/{root}", candidateOutputFields=[path]
        )
        messages = build_template_retrieval_prompt(task, _registry(), (binding,))
        assert "日历展示需求与候选分离" not in str(messages)


@pytest.mark.parametrize("name", ("no_date", "two_start"))
@pytest.mark.asyncio
async def test_schema_only_optional_fields_cannot_be_restored_as_display(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    inputs = _case(case)
    events = _calendar(inputs.task.dataModelSchema).get("events")
    assert isinstance(events, list)
    extra = "startDate" if name == "no_date" else "title"
    for event in events:
        event[extra] = {"type": "string", "sampleValue": "schema中有但未经候选授权"}
    original = deepcopy(inputs)
    assert _fallback(case, inputs, _registry()) is None
    _pipeline_registry(monkeypatch, _registry())

    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            raise AssertionError("候选外的可选字段不能通过投影重新变成展示字段")

    with pytest.raises(pipeline.TemplateRouteNotApplicable):
        await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())
    assert inputs == original


@pytest.mark.parametrize(
    "query",
    (
        "逐项展示日程标题和地点，以及天气状况",
        "显示日程各自的标题和地点，以及天气状况",
        "显示两件事的标题和地点，以及天气状况",
    ),
)
def test_new_calendar_weather_entry_cannot_reduce_multiple_events_to_first(query: str) -> None:
    case = _BY_NAME.get("mixed_location")
    assert case is not None
    case = case._replace(query=query)
    assert _fallback(case, _case(case), _registry()) is None


@pytest.mark.parametrize("end_authorized", (False, True))
@pytest.mark.asyncio
async def test_old_three_field_dated_entry_keeps_context_authorized(
    monkeypatch: pytest.MonkeyPatch, end_authorized: bool
) -> None:
    context = (_TITLE, _END) if end_authorized else (_TITLE,)
    case = Case(
        "old_three_fields",
        "2x4",
        "DatedMeetingWideFull",
        (_DATE, _START, _LOCATION),
        "显示安排的日期、开始时间和地点",
        context,
    )
    inputs = _case(case)
    events = _calendar(inputs.task.dataModelSchema).get("events")
    assert isinstance(events, list)
    if not end_authorized:
        events[0]["dtEnd"] = {"type": "string", "sampleValue": "18:00"}
    original = deepcopy(inputs)
    registry = _registry()
    with pytest.raises(TemplateRetrievalMiss):
        _old_plans(inputs, registry)
    result = _fallback(case, inputs, registry)
    _pipeline_registry(monkeypatch, registry)
    if end_authorized:
        assert result is not None
        output = await _compile(inputs, result.plans[0])
        assert case.target in output.template_ids
        for path in (*case.fields, *context):
            assert f"/data/calendar{path}" in output.a2ui
    else:
        assert result is None

        class Model:
            async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
                return inputs.intent.model_dump(mode="json", by_alias=True)

            async def generate(self, *_args: Any, **_kwargs: Any) -> str:
                raise AssertionError("旧三字段入口不能恢复未经候选授权的结束时间")

        with pytest.raises(pipeline.TemplateRouteNotApplicable):
            await pipeline.generate_template_a2ui(
                inputs.task, inputs.card, inputs.bindings, Model()
            )
    assert inputs == original


@pytest.mark.parametrize(
    ("name", "path"),
    (
        ("no_date", _DATE),
        ("reminder_three", "/updatedAt"),
        ("two_start", "/events/0/title"),
    ),
)
def test_optional_fields_with_incompatible_types_stay_unmatched(name: str, path: str) -> None:
    case = _BY_NAME.get(name)
    assert case is not None
    context = _rows(2, ("title",)) if name == "two_start" else (path,)
    inputs = _case(case._replace(context=(*case.context, *context)))
    calendar = _calendar(inputs.task.dataModelSchema)
    incompatible = {"type": "array", "items": {"type": "string"}}
    if path == "/updatedAt":
        calendar["updatedAt"] = incompatible
    else:
        events = calendar.get("events")
        assert isinstance(events, list)
        events[0][path.rsplit("/", 1)[-1]] = incompatible
    assert _fallback(case, inputs, _registry()) is None
