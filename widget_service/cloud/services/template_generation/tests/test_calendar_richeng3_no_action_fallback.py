"""richeng3 单日程和日程天气补充分支的正式编译与拒绝边界。"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any, NamedTuple

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.cardplan.calendar_mixed_no_action_policy import (
    plan_calendar_weather_no_action_fallback,
)
from services.template_generation.engine.cardplan.calendar_no_action_policy import (
    plan_calendar_no_action_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    build_template_retrieval_prompt,
)
from services.template_generation.tests.test_calendar_full_extensions import CalendarInputs, _inputs

_CAP = "GetCalendarEvents"
_WEATHER = "ViewWeather"
_TITLE = "/events/0/title"
_START = "/events/0/dtStart"
_DATE = "/events/0/startDate"
_END = "/events/0/dtEnd"
_LOCATION = "/events/0/eventLocation"
_DAYS = "/events/0/countdownDays"
_REMINDER = "/events/0/remindTime/0"
_VIEW = "event.viewCalendarEvent"
_WEATHER_FIELDS = ("/location/districtName", "/current/temperatureText", "/current/condition")


@lru_cache(maxsize=16)
def _registry(**kwargs: Any) -> CardPlanRegistry:
    return CardPlanRegistry(**kwargs)


class Case(NamedTuple):
    suffix: str
    size: str
    fields: tuple[str, ...]
    query: str


_CASES = (
    Case(
        "EventCountNotesFull",
        "2x2",
        ("/eventCount", _TITLE, _START, "/events/0/description"),
        "看看今天有几条日程、标题、开始时间和备注内容",
    ),
    Case(
        "DatedMeetingWideFull",
        "2x4",
        (_DATE, _START, _LOCATION),
        "把那个安排的日期、几点、在哪儿都显示出来",
    ),
    Case(
        "DateCountdownReminderFull",
        "2x2",
        (_TITLE, _START, _DATE, _DAYS, _REMINDER),
        "显示下个日程标题、开始时间、开始日期、倒计时天数和提前提醒时间",
    ),
)
_PER_EVENT_QUERIES = (
    pytest.param("显示日程数量，逐项展示日程标题、开始时间和备注", id="per_item"),
    pytest.param("显示日程数量，以及日程各自的标题、开始时间和备注", id="each_event"),
    pytest.param(
        "不用逐项显示日期，但要逐项展示日程标题、开始时间和备注，并显示日程数量",
        id="negated_then_positive_per_item",
    ),
    pytest.param(
        "不要只显示第一条日程，逐项展示日程标题、开始时间和备注，并显示日程数量",
        id="negated_first_only",
    ),
    pytest.param(
        "不要再只显示第一条日程，逐项展示日程标题、开始时间和备注，并显示日程数量",
        id="negated_first_only_again",
    ),
    pytest.param(
        "不允许只显示第一条日程，逐项展示日程标题、开始时间和备注，并显示日程数量",
        id="forbidden_first_only",
    ),
)


def _event(schema: dict[str, Any]) -> dict[str, Any]:
    data = schema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    events = calendar.get("events")
    assert isinstance(events, list)
    event = events[0]
    assert isinstance(event, dict)
    return event


def _case(case: Case, *, view_candidate: bool = False) -> CalendarInputs:
    fields = (_DATE, _TITLE, _START, _END, _LOCATION) if case.size == "2x4" else case.fields
    supported = tuple(path for path in fields if path != _DAYS)
    task, bindings, card, intent = _inputs(supported, view_candidate=view_candidate)
    schema = deepcopy(task.dataModelSchema)
    if _DAYS in fields:
        _event(schema)["countdownDays"] = {"type": "integer", "sampleValue": 0}
    task = task.model_copy(
        update={
            "size": case.size,
            "userQuery": case.query,
            "dataModelSchema": schema,
        }
    )
    bindings = (bindings[0].model_copy(update={"candidateOutputFields": list(fields)}),)
    card["suggestSize"] = case.size
    intent = intent.model_copy(
        update={
            "required_output_fields_by_capability": {_CAP: case.fields},
            "allow_calendar_view_fallback": False,
        }
    )
    return CalendarInputs(task, bindings, card, intent)


def _event_count_inputs(query: str, event_count: int = 3) -> CalendarInputs:
    inputs = _case(_CASES[0])
    schema = deepcopy(inputs.task.dataModelSchema)
    data = schema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    first_event = _event(schema)
    events = []
    authorized = ["/eventCount"]
    for index in range(event_count):
        events.append(deepcopy(first_event))
        for field in ("title", "dtStart", "description"):
            authorized.append(f"/events/{index}/{field}")
    calendar["events"] = events
    count_field = calendar.get("eventCount")
    assert isinstance(count_field, dict)
    count_field["sampleValue"] = event_count
    task = inputs.task.model_copy(update={"userQuery": query, "dataModelSchema": schema})
    binding = inputs.bindings[0].model_copy(update={"candidateOutputFields": authorized})
    return inputs._replace(task=task, bindings=(binding,))


def _mixed() -> CalendarInputs:
    task, bindings, card, intent = _inputs((_TITLE, _DATE))
    schema = deepcopy(task.dataModelSchema)
    data = schema.get("data")
    assert isinstance(data, dict)
    data["weather"] = {
        "location": {"districtName": {"type": "string", "sampleValue": "青浦区"}},
        "current": {
            "temperatureText": {"type": "string", "sampleValue": "29℃"},
            "condition": {"type": "string", "sampleValue": "多云"},
        },
    }
    task = task.model_copy(
        update={
            "size": "2x4",
            "userQuery": "看看日程是几号、标题和天气",
            "dataModelSchema": schema,
        }
    )
    bindings = (
        *bindings,
        CandidateDataBinding(
            capabilityId=_WEATHER,
            writeResultTo="/data/weather",
            candidateOutputFields=list(_WEATHER_FIELDS),
        ),
    )
    card["suggestSize"] = "2x4"
    card_bindings = card.get("dataBindings")
    assert isinstance(card_bindings, list)
    card_bindings.append({"capabilityId": _WEATHER, "writeResultTo": "/data/weather"})
    intent = intent.model_copy(
        update={
            "required_output_fields_by_capability": {
                _CAP: (_TITLE, _DATE),
                _WEATHER: _WEATHER_FIELDS,
            },
            "allow_calendar_view_fallback": False,
        }
    )
    return CalendarInputs(task, bindings, card, intent)


def _fallback(inputs: CalendarInputs, registry: CardPlanRegistry, **kwargs: Any) -> Any:
    method = (
        plan_calendar_weather_no_action_fallback
        if len(inputs.bindings) == 2
        else (plan_calendar_no_action_fallback)
    )
    return method(inputs.intent, inputs.task, registry, inputs.bindings, inputs.card, **kwargs)


def _configure(monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry) -> None:
    controls = TemplateControls(
        schemaVersion="template-controls/1",
        firstLayerComponentSelector="search",
    )
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: controls)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _flag: registry)


async def _compile(inputs: CalendarInputs, layout: str, templates: tuple[str, ...]) -> Any:
    class Model:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return inputs.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            children = ",".join(f'Template("{target}",{{}})' for target in templates)
            return f'Template("{layout}",{{}},{children});'

    return await pipeline.generate_template_a2ui(inputs.task, inputs.card, inputs.bindings, Model())


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
@pytest.mark.parametrize("view_candidate", [False, True])
@pytest.mark.asyncio
async def test_new_single_shapes_formally_compile_all_fields_without_action(
    monkeypatch: pytest.MonkeyPatch,
    case: Case,
    view_candidate: bool,
) -> None:
    inputs = _case(case, view_candidate=view_candidate)
    original = deepcopy(inputs)
    registry = _registry()
    _configure(monkeypatch, registry)
    target = f"ScheduleOverview{case.suffix}@1"
    fallback = _fallback(inputs, registry)
    assert fallback is not None
    assert fallback.intent == inputs.intent
    layout = "SingleFocusLayout@1" if case.size == "2x2" else "WideFullOnlyLayout@1"
    output = await _compile(inputs, layout, (target,))
    assert target in output.template_ids
    assert output.projected_task_spec.eventCandidates == []
    assert '"call":"clickToIntent"' not in output.a2ui
    assert '"Button"' not in output.a2ui
    for field in inputs.bindings[0].candidateOutputFields:
        assert f"/data/calendar{field}" in output.a2ui
    assert inputs == original


@pytest.mark.parametrize("query", _PER_EVENT_QUERIES)
def test_event_count_single_fallback_rejects_per_event_requests(query: str) -> None:
    inputs = _event_count_inputs(query)
    original = deepcopy(inputs)
    assert _fallback(inputs, _registry()) is None
    assert inputs == original


@pytest.mark.parametrize("query", _PER_EVENT_QUERIES)
@pytest.mark.asyncio
async def test_per_event_requests_do_not_compile_as_first_event_only(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    inputs = _event_count_inputs(query)
    original = deepcopy(inputs)
    _configure(monkeypatch, _registry())
    with pytest.raises(pipeline.TemplateRouteNotApplicable):
        await _compile(inputs, "SingleFocusLayout@1", ("ScheduleOverviewEventCountNotesFull@1",))
    assert inputs == original


@pytest.mark.parametrize(
    ("event_count", "query"),
    [
        pytest.param(1, _CASES[0].query, id="original_84f7"),
        pytest.param(
            3,
            "显示日程数量，只看下一项的标题、开始时间和备注",
            id="next_event_with_multiple_inputs",
        ),
        pytest.param(
            3,
            "不要逐项展示日程，只看下一项的标题、开始时间和备注，并显示日程数量",
            id="negated_per_item",
        ),
        pytest.param(
            3,
            "不用显示日程各自的标题、开始时间和备注，只看下一项，并显示日程数量",
            id="negated_each_event",
        ),
        pytest.param(
            3,
            "显示日程各自的标题、开始时间和备注，但仅显示第一条日程及日程数量",
            id="each_event_limited_to_first",
        ),
        pytest.param(
            3,
            "显示日程数量，下个日程的标题、开始时间和备注两个字段各自一行",
            id="next_event_fields_on_separate_lines",
        ),
        pytest.param(
            3,
            "显示日程数量，下个日程的标题、开始时间和备注逐项展示",
            id="next_event_fields_itemized",
        ),
    ],
)
def test_event_count_single_fallback_preserves_first_event_requests(
    event_count: int, query: str
) -> None:
    inputs = _event_count_inputs(query, event_count)
    original = deepcopy(inputs)
    fallback = _fallback(inputs, _registry())
    assert fallback is not None
    assert fallback.intent == inputs.intent
    assert inputs == original


@pytest.mark.asyncio
async def test_date_title_and_weather_compile_as_two_complete_businesses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _mixed()
    original = deepcopy(inputs)
    registry = _registry()
    _configure(monkeypatch, registry)
    fallback = _fallback(inputs, registry)
    assert fallback is not None
    assert fallback.intent == inputs.intent
    targets = ("ScheduleOverviewDateTitleFull@1", "WeatherOverviewFull@1")
    output = await _compile(inputs, "WideTwoFullLayout@1", targets)
    assert set(targets).issubset(output.template_ids)
    assert output.projected_task_spec.eventCandidates == []
    assert '"Button"' not in output.a2ui
    for binding in inputs.bindings:
        for field in binding.candidateOutputFields:
            assert f"{binding.writeResultTo}{field}" in output.a2ui
    assert inputs == original


@pytest.mark.parametrize(
    "suffix", ["EventCountNotesFull", "DateCountdownReminderFull", "DateTitleFull"]
)
def test_new_ids_are_hidden_from_ordinary_registry_and_first_prompt(suffix: str) -> None:
    inputs = _mixed()
    registry = _registry()
    target = f"ScheduleOverview{suffix}@1"
    assert target in registry.templates
    assert not registry.template_is_enabled(target)
    assert target not in str(
        build_template_retrieval_prompt(inputs.task, registry, inputs.bindings)
    )


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
@pytest.mark.parametrize(
    "mode", ["candidate", "schema", "type", "extra", "action", "query_action", "multiple"]
)
def test_single_branches_preserve_authorization_types_and_complete_intent(
    case: Case, mode: str
) -> None:
    inputs = _case(case, view_candidate=True)
    task, bindings, card, intent = inputs
    schema = deepcopy(task.dataModelSchema)
    if mode == "candidate":
        bindings = (
            bindings[0].model_copy(
                update={
                    "candidateOutputFields": [
                        path for path in bindings[0].candidateOutputFields if path != _TITLE
                    ],
                }
            ),
        )
    elif mode == "schema":
        _event(schema).pop("title")
    elif mode == "type":
        _event(schema)["title"] = {"type": "object", "sampleValue": {}}
    elif mode == "extra":
        intent = intent.model_copy(
            update={
                "required_output_fields_by_capability": {
                    _CAP: (*case.fields, "/events/0/timeZone")
                },
            }
        )
    elif mode == "action":
        intent = intent.model_copy(update={"action_ids": (_VIEW,)})
    elif mode == "query_action":
        task = task.model_copy(update={"userQuery": task.userQuery + "，点击打开日历"})
    elif mode == "multiple":
        task = task.model_copy(update={"userQuery": task.userQuery + "，展示每条日程"})
    task = task.model_copy(update={"dataModelSchema": schema})
    assert _fallback(CalendarInputs(task, bindings, card, intent), _registry()) is None


@pytest.mark.parametrize(
    "query",
    [
        "只显示日期、开始时间和地点",
        "仅展示日期、开始时间和地点",
        "日期、开始时间和地点，不要标题",
        "日期、开始时间和地点，不要结束时间",
        "日期、开始时间和地点，不显示额外信息",
        "日期、开始时间和地点，禁止其他信息",
        "only date, start and location, nothing else",
        "我只要日期、开始时间和地点",
        "仅需日期、开始时间和地点",
        "仅日期、开始时间和地点",
    ],
)
def test_three_field_reuse_rejects_explicit_extra_context_prohibition(query: str) -> None:
    inputs = _case(_CASES[1])
    task = inputs.task.model_copy(update={"userQuery": query})
    assert _fallback(inputs._replace(task=task), _registry()) is None


@pytest.mark.parametrize("missing", [_TITLE, _END])
@pytest.mark.parametrize("mode", ["candidate", "schema", "type"])
@pytest.mark.asyncio
async def test_three_field_reuse_requires_real_authorized_title_and_end(
    monkeypatch: pytest.MonkeyPatch, missing: str, mode: str
) -> None:
    inputs = _case(_CASES[1])
    if mode == "candidate":
        binding = inputs.bindings[0].model_copy(
            update={
                "candidateOutputFields": [
                    path for path in inputs.bindings[0].candidateOutputFields if path != missing
                ],
            }
        )
        inputs = inputs._replace(bindings=(binding,))
    else:
        schema = deepcopy(inputs.task.dataModelSchema)
        key = missing.rsplit("/", 1)[-1]
        if mode == "schema":
            _event(schema).pop(key)
        else:
            _event(schema)[key] = {"type": "array", "items": {"type": "string"}}
        inputs = inputs._replace(task=inputs.task.model_copy(update={"dataModelSchema": schema}))
    original = deepcopy(inputs)
    result = _fallback(inputs, _registry())
    if missing == _END and mode == "schema":
        # 结束时间现在可缺省；存在的标题仍须真实、授权且类型正确。
        assert result is not None
        assert result.intent == inputs.intent
        _configure(monkeypatch, _registry())
        target = "ScheduleOverviewDatedMeetingWideFull@1"
        output = await _compile(inputs, "WideFullOnlyLayout@1", (target,))
        assert target in output.template_ids
        for path in (_TITLE, _DATE, _START, _LOCATION):
            assert f"/data/calendar{path}" in output.a2ui
        assert f"/data/calendar{_END}" not in output.a2ui
    else:
        assert result is None
    assert inputs == original


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.suffix)
@pytest.mark.parametrize(
    "restriction", ["disabled_provider", "disabled_template", "trusted_template", "trusted_action"]
)
def test_single_retry_keeps_controls_and_trusted_scope(case: Case, restriction: str) -> None:
    target = f"ScheduleOverview{case.suffix}@1"
    options: dict[str, Any] = {}
    kwargs: dict[str, Any] = {}
    if restriction == "disabled_provider":
        options["disabled_provider_ids"] = ("com.huawei.calendar.cli",)
    elif restriction == "disabled_template":
        options["disabled_template_ids"] = (target,)
    elif restriction == "trusted_template":
        kwargs["trusted_template_candidate_ids"] = ("ScheduleOverviewTitleTimeFull@1",)
    else:
        kwargs["trusted_template_action_ids"] = (_VIEW,)
    assert _fallback(_case(case), _registry(**options), **kwargs) is None


@pytest.mark.parametrize(
    "mode",
    [
        "size",
        "calendar_extra",
        "weather_extra",
        "weather_candidate",
        "weather_schema",
        "weather_type",
        "weather_empty",
        "third_business",
        "wrong_capability",
        "root_mismatch",
        "invalid_root",
        "action",
        "query_action",
        "multiple",
    ],
)
def test_mixed_branch_does_not_drop_or_replace_business_requirements(mode: str) -> None:
    task, bindings, card, intent = _mixed()
    schema = deepcopy(task.dataModelSchema)
    required = dict(intent.required_output_fields_by_capability)
    data = schema.get("data")
    assert isinstance(data, dict)
    weather = data.get("weather")
    assert isinstance(weather, dict)
    current = weather.get("current")
    assert isinstance(current, dict)
    if mode == "size":
        task = task.model_copy(update={"size": "2x2"})
        card["suggestSize"] = "2x2"
    elif mode == "calendar_extra":
        required[_CAP] = (_TITLE, _DATE, _DAYS)
    elif mode == "weather_extra":
        required[_WEATHER] = (*_WEATHER_FIELDS, "/current/humidity")
    elif mode == "weather_empty":
        required[_WEATHER] = ()
    elif mode == "weather_candidate":
        bindings = (
            bindings[0],
            bindings[1].model_copy(update={"candidateOutputFields": list(_WEATHER_FIELDS[:-1])}),
        )
    elif mode == "weather_schema":
        current.pop("condition")
    elif mode == "weather_type":
        current["condition"] = {"type": "object", "sampleValue": {}}
    elif mode == "third_business":
        required["GetBattery"] = ("/level",)
    elif mode == "wrong_capability":
        required.pop(_WEATHER)
        required["GetBattery"] = _WEATHER_FIELDS
        bindings = (bindings[0], bindings[1].model_copy(update={"capabilityId": "GetBattery"}))
    elif mode == "root_mismatch":
        bindings = (bindings[0], bindings[1].model_copy(update={"writeResultTo": "/data/other"}))
    elif mode == "invalid_root":
        rows = card.get("dataBindings")
        assert isinstance(rows, list)
        rows[1]["writeResultTo"] = ["/data/weather"]
    elif mode == "action":
        intent = intent.model_copy(update={"action_ids": (_VIEW,)})
    elif mode == "query_action":
        task = task.model_copy(update={"userQuery": task.userQuery + "，点击打开日历"})
    elif mode == "multiple":
        task = task.model_copy(update={"userQuery": task.userQuery + "，展示每条日程"})
    task = task.model_copy(update={"dataModelSchema": schema})
    intent = intent.model_copy(update={"required_output_fields_by_capability": required})
    assert _fallback(CalendarInputs(task, bindings, card, intent), _registry()) is None


@pytest.mark.parametrize(
    "restriction", ["calendar", "weather", "target", "weather_template", "trusted", "action"]
)
def test_mixed_retry_keeps_provider_template_and_trusted_controls(restriction: str) -> None:
    target = "ScheduleOverviewDateTitleFull@1"
    options: dict[str, Any] = {}
    kwargs: dict[str, Any] = {}
    if restriction in {"calendar", "weather"}:
        options["disabled_provider_ids"] = (f"com.huawei.{restriction}.cli",)
    elif restriction == "target":
        options["disabled_template_ids"] = (target,)
    elif restriction == "weather_template":
        kwargs["trusted_template_candidate_ids"] = (target, "WeatherOverviewFull@1")
        options["disabled_template_ids"] = ("WeatherOverviewFull@1",)
    elif restriction == "trusted":
        kwargs["trusted_template_candidate_ids"] = (target,)
    else:
        kwargs["trusted_template_action_ids"] = (_VIEW,)
    assert _fallback(_mixed(), _registry(**options), **kwargs) is None


@pytest.mark.asyncio
async def test_original_success_never_calls_new_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = _inputs((_TITLE, _START), view_candidate=True)
    registry = _registry()
    _configure(monkeypatch, registry)

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("原匹配成功，不得进入新增后备")

    monkeypatch.setattr(pipeline, "plan_calendar_no_action_fallback", forbidden)
    monkeypatch.setattr(pipeline, "plan_calendar_list_no_action_fallback", forbidden)
    monkeypatch.setattr(pipeline, "plan_calendar_weather_no_action_fallback", forbidden)
    target = "ScheduleOverviewTitleTimeFull@1"
    output = await _compile(inputs, "SingleFocusLayout@1", (target,))
    assert target in output.template_ids
    assert output.projected_task_spec.eventCandidates == []


@pytest.mark.parametrize("case", [_CASES[0], _CASES[2]], ids=lambda case: case.suffix)
@pytest.mark.parametrize("request_text", ["全文", "禁止省略", "不要截断", "full text"])
def test_new_small_cards_reject_full_text_requirements(case: Case, request_text: str) -> None:
    inputs = _case(case)
    task = inputs.task.model_copy(update={"userQuery": inputs.task.userQuery + "，" + request_text})
    assert _fallback(inputs._replace(task=task), _registry()) is None


@pytest.mark.parametrize("case", [_CASES[0], _CASES[2]], ids=lambda case: case.suffix)
def test_new_small_cards_reject_english_full_text_attached_to_chinese(case: Case) -> None:
    inputs = _case(case)
    task = inputs.task.model_copy(update={"userQuery": inputs.task.userQuery + "full text"})
    assert _fallback(inputs._replace(task=task), _registry()) is None
