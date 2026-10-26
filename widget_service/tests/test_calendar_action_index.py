"""1381ce64 的参数恢复、预检及 L375 原文回放，不调用模型或端侧。"""

import copy
import json
from pathlib import Path

import pytest

from api.schemas import GenerateWidgetCardRequest
from services import compact_dsl_argument_repair as repair
from services.capability_registry import CapabilityRegistry
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_plan import compact_plan_coverage_errors, parse_compact_plan_call
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_preflight import GenerationPreflight

CALENDAR_PATH = "/data/calendar/events/0/entityId"
TEMPLATE_PATH = "/data/calendar/events/i/entityId"
FIXTURE = Path(__file__).parent / "fixtures" / "calendar_action_index_l375.dsl"


@pytest.fixture
def registry():
    return CapabilityRegistry(version="app-11.7.7.300_rom-7.0")


def _action(registry, identifier):
    event = registry.get_event_capability(identifier)
    assert event is not None
    return event.actionTemplate.model_dump(mode="json")


def _content(registry, index="0"):
    action = _action(registry, "event.viewCalendarEvent")
    args = action.get("args")
    assert isinstance(args, dict)
    args["params"] = {"entityId": "{{ ${/data/calendar/events/" + index + "/entityId} }}"}
    return {
        "userQuery": "帮我弄个卡片，看看下个会几点开始，顺便看下天气。",
        "title": "日程与天气",
        "description": "下个日程开始时间与今日天气速览",
        "size": "2x4",
        "candidateDataBindings": [
            {
                "capabilityId": "GetCalendarEvents",
                "arguments": {"futureDays": 7},
                "writeResultTo": "/data/calendar",
                "candidateOutputFields": [
                    "/events/0/title",
                    "/events/0/startDate",
                    "/events/0/dtStart",
                    "/events/0/entityId",
                ],
            },
            {
                "capabilityId": "ViewWeather",
                "arguments": {
                    "prefectureName": "南京市",
                    "districtName": "雨花台区",
                    "forecastDays": 1,
                },
                "writeResultTo": "/data/weather",
                "candidateOutputFields": [
                    "/current/temperatureText",
                    "/current/condition",
                    "/location/cityCode",
                ],
            },
        ],
        "candidateEventCandidates": [
            {"capabilityId": "event.viewCalendarEvent", "action": action},
            {
                "capabilityId": "event.open.weather",
                "action": _action(registry, "event.open.weather"),
            },
        ],
        "candidateAssetIds": ["asset.ic_weather_color", "asset.ic_calender"],
    }


def _preflight(content, registry):
    request = GenerateWidgetCardRequest(
        uid="test", device={"romVersion": "7.0"}, prdVer="11.7.8.354", **content,
    )
    return GenerationPreflight(registry).run(EditRequestNormalizer.normalize_create(request))


def _set_calendar_candidate(content, candidate):
    candidates = content.get("candidateEventCandidates")
    assert isinstance(candidates, list)
    candidates[0] = {"capabilityId": "event.viewCalendarEvent", **candidate}


@pytest.mark.parametrize("index", ["0", "2"])
@pytest.mark.parametrize("shape", ["flat", "nested_legacy", "candidate_legacy", "nested"])
def test_repair_preserves_explicit_index_and_builds_usable_action(registry, index, shape):
    content = _content(registry)
    path = CALENDAR_PATH.replace("/0/", f"/{index}/")
    candidate = {"action": {"call": "event.viewCalendarEvent", "args": {"/params/entityId": path}}}
    if shape == "nested_legacy":
        candidate = {"action": {"args": {"dynamicArguments": {"/params/entityId": path}}}}
    elif shape == "candidate_legacy":
        candidate = {"dynamicArguments": {"/params/entityId": path}}
    elif shape == "nested":
        candidate = {"action": {"args": {"params": {"entityId": "{{ ${" + path + "} }}"}}}}
    _set_calendar_candidate(content, candidate)
    original = copy.deepcopy(content)

    normalized, dropped, _warnings = repair._normalize_model_output(
        json.dumps(content),
        {},
        {},
        registry,
    )
    result = _preflight(normalized, registry)

    assert content == original
    assert dropped == []
    assert result.blocking_issues == ()
    event = next(item for item in result.effective_events if item.id == "event.viewCalendarEvent")
    assert event.call == "clickToIntent"
    assert event.args.get("params") == {"entityId": "{{ ${" + path + "} }}"}


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"params": {"entityId": 0}},
        {"/params/entityId": TEMPLATE_PATH},
        {
            "params": {"entityId": "{{ ${/data/calendar/events/i/entityId} }}"},
        },
    ],
)
def test_repair_never_reports_unresolved_template_as_success(registry, args):
    content = _content(registry)
    _set_calendar_candidate(content, {"action": {"args": args}})
    with pytest.raises(repair.CompactDslArgumentRepairError, match="实际数组下标"):
        repair._normalize_model_output(json.dumps(content), {}, {}, registry)


def test_preflight_rejects_l046_placeholder_before_generation(registry):
    result = _preflight(_content(registry, "i"), registry)
    issue = next(item for item in result.blocking_issues if item.code == "EVENT_DATA_PATH_INVALID")
    assert issue.path.endswith("/action/args/params/entityId")
    assert issue.retryable
    assert "数字下标" in issue.repairInstruction
    assert result.task_spec is None


def test_legacy_weather_expression_is_preserved(registry):
    content = _content(registry)
    weather_action = _action(registry, "event.open.weather")
    weather_args = weather_action.get("args")
    assert isinstance(weather_args, dict)
    uri = weather_args.get("uri")
    assert isinstance(uri, str)
    candidates = content.get("candidateEventCandidates")
    assert isinstance(candidates, list)
    candidates[1] = {
        "capabilityId": "event.open.weather",
        "action": {"args": {"dynamicArguments": {"/uri": uri}}},
    }
    normalized, dropped, _warnings = repair._normalize_model_output(
        json.dumps(content), {}, {}, registry,
    )
    result = _preflight(normalized, registry)
    assert dropped == []
    assert result.blocking_issues == ()
    event = next(item for item in result.effective_events if item.id == "event.open.weather")
    assert event.args == weather_args


def _plan(task_spec):
    arguments = {
        "info_required": [
            {
                "requirement": "日程标题",
                "priority": "must",
                "dataId": "/data/calendar/events/0/title",
            },
            {
                "requirement": "日程时间",
                "priority": "must",
                "dataId": "/data/calendar/events/0/dtStart",
            },
            {
                "requirement": "日程日期",
                "priority": "must",
                "dataId": "/data/calendar/events/0/startDate",
            },
            {
                "requirement": "天气温度",
                "priority": "must",
                "dataId": "/data/weather/current/temperatureText",
            },
            {
                "requirement": "天气现象",
                "priority": "must",
                "dataId": "/data/weather/current/condition",
            },
            {"requirement": "查看日程", "priority": "must", "actionId": "event.viewCalendarEvent"},
            {"requirement": "查看天气", "priority": "must", "actionId": "event.open.weather"},
        ],
        "layoutHints": ["W-split-panels"],
        "assetAssignments": {
            "actions": [
                {"actionId": "event.viewCalendarEvent", "assetId": "asset.ic_calender"},
                {"actionId": "event.open.weather", "assetId": "asset.ic_weather_color"},
            ],
            "title": {"assetId": None, "reason": "两个素材均用于动作"},
        },
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": arguments})
    return parse_compact_plan_call(raw, task_spec).plan


def test_l375_replay_original_fails_and_aligned_action_passes(registry):
    content = _content(registry)
    _set_calendar_candidate(content, {"action": {"args": {"/params/entityId": CALENDAR_PATH}}})
    normalized, dropped, _warnings = repair._normalize_model_output(
        json.dumps(content),
        {},
        {},
        registry,
    )
    assert dropped == []
    result = _preflight(normalized, registry)
    assert result.blocking_issues == ()
    assert result.task_spec is not None
    assert result.card_spec is not None
    task_spec = result.task_spec.model_dump(mode="json")
    card_spec = result.card_spec.model_dump(mode="json")
    plan = _plan(task_spec)
    original = FIXTURE.read_text(encoding="utf-8")

    broken_task = copy.deepcopy(task_spec)
    events = broken_task.get("eventCandidates")
    assert isinstance(events, list)
    for event in events:
        if event.get("id") == "event.viewCalendarEvent":
            event["args"] = _action(registry, "event.viewCalendarEvent").get("args")
    assert compact_plan_coverage_errors(original, plan, broken_task) == ()
    with pytest.raises(CompactDslValidationError) as captured:
        validate_compact_dsl(
            original, task_spec=broken_task, card_spec=card_spec, compact_plan=plan
        )
    assert TEMPLATE_PATH in str(captured.value)
    assert "not declared" in str(captured.value)

    fixed = original.replace(TEMPLATE_PATH, CALENDAR_PATH)
    assert "Expected exact onClick" in " ".join(
        compact_plan_coverage_errors(fixed, plan, broken_task)
    )
    assert compact_plan_coverage_errors(fixed, plan, task_spec) == ()
    validate_compact_dsl(fixed, task_spec=task_spec, card_spec=card_spec, compact_plan=plan)
