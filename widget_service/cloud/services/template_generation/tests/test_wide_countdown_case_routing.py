"""2x4 倒计时组合的检索、布局选择、动作归属和编译回归。"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.models import TemplateRouteSelection
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    UxMixedPromptProjection,
    build_ux_mixed_prompt,
)
from services.template_generation.engine.cardplan.business_actions import (
    supports_business_action,
)
from services.template_generation.engine.cardplan.compiler import (
    HybridCompilation,
    compile_ux_layout_card,
)
from services.template_generation.engine.cardplan.models import ActionBinding
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalQuery,
    TemplateSearchIntent,
    search_template_variants,
)

_CALENDAR_FULL = "ScheduleOverviewEventCountTwoEventsFull@1"
_COUNTDOWN_COMPACT = "CountdownOverviewTargetCompact@1"
_COUNTDOWN_DETAIL_FULL = "CountdownOverviewTargetDetailFull@1"
_COUNTDOWN_EVENT_HERO = "CountdownOverviewEventHero@1"
_COUNTDOWN_DEPARTURE_HERO = "CountdownOverviewDepartureHero@1"
_HEALTH_FULL = "ActivityOverviewTrainingSummaryFull@1"
_WEATHER_THREE_DAY_FULL = "WeatherOverviewThreeDayForecastFull@1"
_WEATHER_DESTINATION_FULL = "WeatherOverviewDestinationDayFull@1"
_COUNTDOWN_ICON = "resources/base/media/stopwatch_fill.svg"
_RUN_ICON = "resources/base/media/figure_run.svg"
_TARGET_BODY_WIDTH = 300 - 2 * 12
_TARGET_BODY_HEIGHT = 150 - 2 * 12
_TARGET_HALF_WIDTH = (_TARGET_BODY_WIDTH - 8) // 2
_TARGET_MASK_CONTENT_WIDTH = _TARGET_HALF_WIDTH - 2 * 12
_TARGET_MASK_CONTENT_HEIGHT = _TARGET_BODY_HEIGHT - 2 * 12


@dataclass(frozen=True)
class _WideCase:
    task_spec: TaskSpec
    query: TemplateRetrievalQuery
    bindings: tuple[CandidateDataBinding, ...]
    card_spec: dict[str, Any]


@dataclass(frozen=True)
class _RoutedCase:
    registry: CardPlanRegistry
    selection: TemplateRouteSelection
    projection: UxMixedPromptProjection


def _field(value: Any, data_type: str = "string") -> dict[str, Any]:
    return {
        "type": data_type,
        "description": "测试可信字段",
        "sampleValue": value,
    }


def _binding(
    capability_id: str,
    write_result_to: str,
    fields: tuple[str, ...],
) -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId=capability_id,
        writeResultTo=write_result_to,
        candidateOutputFields=list(fields),
    )


def _card_spec(title: str, bindings: tuple[CandidateDataBinding, ...]) -> dict[str, Any]:
    data_bindings: list[dict[str, str]] = []
    for binding in bindings:
        data_bindings.append(
            {
                "capabilityId": binding.capabilityId,
                "writeResultTo": binding.writeResultTo,
            }
        )
    return {
        "title": title,
        "description": "2x4 倒计时组合测试",
        "suggestSize": "2x4",
        "dataBindings": data_bindings,
    }


def _calendar_action(event_index: int) -> EventAction:
    return EventAction(
        id="event.viewCalendarEvent",
        description="查看日程",
        call="clickToIntent",
        args={
            "intentName": "ViewCalendarEvent",
            "params": {
                "entityId": (f"{{{{ ${{/data/calendar/events/{event_index}/entityId}} }}}}")
            },
        },
    )


def _calendar_countdown_case() -> _WideCase:
    countdown_fields = ("/countdownDays",)
    calendar_fields = (
        "/eventCount",
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/entityId",
        "/events/1/title",
        "/events/1/dtStart",
    )
    bindings = (
        _binding("GetCountdownDays", "/data/countdown", countdown_fields),
        _binding("GetCalendarEvents", "/data/calendar", calendar_fields),
    )
    task_spec = TaskSpec(
        userQuery="显示2026年9月30日上线倒计时和最近两场会议，点击查看第一场日程",
        size="2x4",
        eventCandidates=[_calendar_action(0)],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field(15, "integer")},
                "calendar": {
                    "eventCount": _field(2, "integer"),
                    "events": [
                        {
                            "title": _field("功能验收会"),
                            "dtStart": _field("10:00"),
                            "entityId": _field("event-0"),
                        },
                        {
                            "title": _field("发布排期会"),
                            "dtStart": _field("15:00"),
                            "entityId": _field("event-1"),
                        },
                    ],
                },
            }
        },
    )
    display_calendar_fields = tuple(
        field for field in calendar_fields if not field.endswith("/entityId")
    )
    query = TemplateRetrievalQuery(
        themeId="meeting-paper-neutral",
        requiredOutputFieldsByCapability={
            "GetCountdownDays": countdown_fields,
            "GetCalendarEvents": display_calendar_fields,
        },
        action=("event.viewCalendarEvent",),
    )
    return _WideCase(task_spec, query, bindings, _card_spec("上线准备", bindings))


def _weather_action() -> EventAction:
    return EventAction(
        id="event.open.weather",
        description="查看天气",
        call="clickToDeeplink",
        args={
            "intentName": "Weather_CityCode",
            "bundleName": "",
            "abilityName": "",
            "uri": (
                "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
                "+ ${/data/weather/location/cityCode} }}"
            ),
        },
    )


def _three_day_weather_case() -> _WideCase:
    countdown_fields = ("/countdownDays",)
    weather_fields: list[str] = []
    daily: list[dict[str, dict[str, Any]]] = []
    for index in range(3):
        weather_fields.extend(
            (
                f"/daily/{index}/date",
                f"/daily/{index}/weekday",
                f"/daily/{index}/condition",
                f"/daily/{index}/temperatureRangeText",
                f"/daily/{index}/rainProbabilityPercent",
            )
        )
        daily.append(
            {
                "date": _field(f"2026-10-0{index + 1}"),
                "weekday": _field(f"星期{index + 1}"),
                "condition": _field("多云"),
                "temperatureRangeText": _field("20~28℃"),
                "rainProbabilityPercent": _field("30%"),
            }
        )
    candidate_weather_fields = (*weather_fields, "/location/cityCode")
    bindings = (
        _binding("GetCountdownDays", "/data/countdown", countdown_fields),
        _binding("ViewWeather", "/data/weather", candidate_weather_fields),
    )
    task_spec = TaskSpec(
        userQuery="国庆回重庆老家，显示返乡倒计时和未来三天天气，点击查看天气",
        size="2x4",
        eventCandidates=[_weather_action()],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field(16, "integer")},
                "weather": {
                    "location": {"cityCode": _field("101040100")},
                    "daily": daily,
                },
            }
        },
    )
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "GetCountdownDays": countdown_fields,
            "ViewWeather": tuple(weather_fields),
        },
        action=("event.open.weather",),
    )
    return _WideCase(task_spec, query, bindings, _card_spec("重庆返乡", bindings))


def _phone_action() -> EventAction:
    return EventAction(
        id="event.call.phone",
        description="给妈妈打电话",
        call="clickToApi",
        args={
            "intentName": "CallPhone",
            "params": {"phoneNumber": ""},
        },
    )


def _destination_weather_case() -> _WideCase:
    countdown_fields = ("/countdownDays",)
    weather_fields = (
        "/daily/3/temperatureRangeText",
        "/daily/3/rainProbabilityPercent",
        "/daily/3/airQuality",
    )
    daily = []
    for _ in range(4):
        daily.append(
            {
                "temperatureRangeText": _field("18~27℃"),
                "rainProbabilityPercent": _field("20%"),
                "airQuality": _field("优"),
            }
        )
    bindings = (
        _binding("GetCountdownDays", "/data/countdown", countdown_fields),
        _binding("ViewWeather", "/data/weather", weather_fields),
    )
    task_spec = TaskSpec(
        userQuery="显示回家倒计时和出发日天气，点击给妈妈打电话",
        size="2x4",
        eventCandidates=[_phone_action()],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field(3, "integer")},
                "weather": {"daily": daily},
            }
        },
    )
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={
            "GetCountdownDays": countdown_fields,
            "ViewWeather": weather_fields,
        },
        action=("event.call.phone",),
    )
    return _WideCase(task_spec, query, bindings, _card_spec("回家看望", bindings))


def _health_action() -> EventAction:
    return EventAction(
        id="event.open.health.sport",
        description="进入锻炼记录",
        call="clickToDeeplink",
        args={
            "intentName": "Health",
            "bundleName": "",
            "abilityName": "",
            "uri": "huaweischeme://healthapp/home/sport?sportType=2",
        },
    )


def _health_countdown_case() -> _WideCase:
    countdown_fields = ("/countdownDays",)
    health_fields = (
        "/dailySteps",
        "/exerciseDurationText",
        "/exerciseHeartRateAvg",
    )
    bindings = (
        _binding("GetCountdownDays", "/data/countdown", countdown_fields),
        _binding("GetHealthAndSportSummary", "/data/healthSport", health_fields),
    )
    task_spec = TaskSpec(
        userQuery="显示马拉松倒计时、步数、跑步时长和心率，点击进入锻炼记录",
        size="2x4",
        eventCandidates=[_health_action()],
        assetCandidates=[
            {
                "src": _COUNTDOWN_ICON,
                "description": "秒表倒计时图标",
            },
            {
                "src": _RUN_ICON,
                "description": "跑步和锻炼入口图标",
                "sceneTags": ["running", "health"],
            },
        ],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field(61, "integer")},
                "healthSport": {
                    "dailySteps": _field(6200, "integer"),
                    "exerciseDurationText": _field("1小时23分"),
                    "exerciseHeartRateAvg": _field(135, "integer"),
                },
            }
        },
    )
    query = TemplateRetrievalQuery(
        themeId="race-sunrise-action",
        requiredOutputFieldsByCapability={
            "GetCountdownDays": countdown_fields,
            "GetHealthAndSportSummary": health_fields,
        },
        action=("event.open.health.sport",),
    )
    return _WideCase(task_spec, query, bindings, _card_spec("马拉松备赛", bindings))


def _route(case: _WideCase) -> _RoutedCase:
    registry = get_cardplan_registry()
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability=case.query.required_output_fields_by_capability,
        action=case.query.action_ids,
    )
    search_result = search_template_variants(
        intent,
        case.task_spec,
        registry,
        case.bindings,
        case.card_spec,
    )
    plans = plan_template_candidates(intent, search_result, case.task_spec, registry)
    selection = TemplateRouteSelection(
        scope=planner_scope(plans),
        componentCandidates=planner_component_candidates(plans),
        actionIds=intent.action_ids,
        requiredTemplateGroups=planner_required_template_groups(plans),
        requiredOutputFieldsByCapability=intent.required_output_fields_by_capability,
    )
    projection = build_ux_mixed_prompt(
        task_spec=case.task_spec,
        card_spec=case.card_spec,
        scope=selection.scope,
        component_candidates=selection.component_candidates,
        required_template_groups=selection.required_template_groups,
        template_plans=plans,
        registry=registry,
    )
    return _RoutedCase(registry, selection, projection)


def _only_action(projection: UxMixedPromptProjection) -> ActionBinding:
    bindings = projection.contract.action_bindings
    assert len(bindings) == 1
    return bindings[0]


def _action_props(action: ActionBinding, *, icon: str | None = None) -> str:
    props = {"actionId": action.action_id, "label": action.display_label}
    if icon is not None:
        props["icon"] = icon
    return json.dumps(props, ensure_ascii=False, separators=(",", ":"))


def _compile(
    case: _WideCase,
    routed: _RoutedCase,
    source: str,
) -> HybridCompilation:
    title = case.card_spec.get("title")
    assert isinstance(title, str)
    return compile_ux_layout_card(
        source,
        task_spec=case.task_spec,
        contract=routed.projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=routed.registry,
        business_title=title,
        card_spec=case.card_spec,
        enable_data_bindings=True,
    )


def _a2ui_components(compilation: HybridCompilation) -> tuple[dict[str, Any], ...]:
    components: list[dict[str, Any]] = []
    for line in compilation.a2ui.splitlines():
        if not line.strip():
            continue
        message = json.loads(line)
        update = message.get("updateComponents")
        if not isinstance(update, dict):
            continue
        items = update.get("components")
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                components.append(item)
    return tuple(components)


def _components_by_id(compilation: HybridCompilation) -> dict[str, dict[str, Any]]:
    return {
        component["id"]: component
        for component in _a2ui_components(compilation)
        if isinstance(component.get("id"), str)
    }


def _assert_target_height_budget(compilation: HybridCompilation) -> None:
    assert compilation.stats.estimated_height_vp <= _TARGET_BODY_HEIGHT
    assert compilation.stats.space_constrained is False


def _content_layout(components_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = components_by_id.get("root")
    foreground = components_by_id.get("template_root")
    layout = components_by_id.get("__genui_render_component__root_1")
    assert root is not None
    assert foreground is not None
    assert layout is not None
    assert root.get("children") == ["template_root"]
    assert root.get("styles", {}).get("padding") == 0
    assert foreground.get("children") == ["__genui_render_component__root_1"]
    assert foreground.get("styles", {}).get("padding") == 12
    return layout


def test_q068_routes_two_fulls_and_embeds_the_calendar_action() -> None:
    case = _calendar_countdown_case()
    routed = _route(case)
    selection = routed.selection

    assert selection.scope.advanced_component_ids == (
        "CountdownOverview",
        "CalendarOverview",
    )
    assert len(selection.required_template_groups) == 2
    countdown_group, calendar_group = selection.required_template_groups
    assert countdown_group == (_COUNTDOWN_DETAIL_FULL,)
    assert selection.component_candidates[0].available_template_ids == countdown_group
    assert all(
        provider_template_layout_kind(template_id) == "Full" for template_id in countdown_group
    )
    assert calendar_group == (_CALENDAR_FULL,)
    assert routed.projection.allowed_layout_ids == ("WideTwoFullLayout",)
    assert "PillAction@1" not in routed.projection.contract.allowed_template_ids

    action = _only_action(routed.projection)
    calendar_props = json.dumps(
        {"actionId": action.action_id},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    source = (
        'Template("WideTwoFullLayout@1",{},'
        f'Template("{_COUNTDOWN_DETAIL_FULL}",{{}}),'
        f'Template("{_CALENDAR_FULL}",{calendar_props}));'
    )
    compilation = _compile(case, routed, source)

    assert compilation.stats.action_used_ids == (action.action_id,)
    assert _CALENDAR_FULL in compilation.stats.template_used_ids
    assert "WideTwoFullLayout@1" in compilation.stats.template_used_ids
    assert compilation.stats.max_depth == 9
    _assert_target_height_budget(compilation)

    components_by_id = _components_by_id(compilation)
    layout_root = _content_layout(components_by_id)
    assert layout_root.get("itemMargin") == 8
    assert len(layout_root["children"]) == 2
    for panel_id in layout_root["children"]:
        panel = components_by_id[panel_id]
        assert panel["styles"].get("layoutWeight") == 1
        content = components_by_id[panel["children"][0]]
        assert content["styles"].get("padding") == 12
    assert _TARGET_HALF_WIDTH == 134
    assert _TARGET_MASK_CONTENT_WIDTH == 110
    assert _TARGET_MASK_CONTENT_HEIGHT == 102

    calendar_bodies = []
    for component in components_by_id.values():
        styles = component.get("styles", {})
        if component.get("component") != "Column":
            continue
        if styles.get("height") != 76:
            continue
        if styles.get("constraintSize", {}).get("maxWidth") == 112:
            calendar_bodies.append(component)
    assert len(calendar_bodies) == 1
    calendar_body = calendar_bodies[0]
    assert calendar_body["styles"].get("width") == "matchParent"
    event_rows = [components_by_id[item] for item in calendar_body["children"]]
    assert len(event_rows) == 2
    assert all(row["styles"].get("width") == "matchParent" for row in event_rows)
    assert all(row["styles"].get("height") == 34 for row in event_rows)
    assert 16 + 76 <= _TARGET_MASK_CONTENT_HEIGHT

    event_text_columns: list[dict[str, Any]] = []
    timeline_dots: list[dict[str, Any]] = []
    for component in _a2ui_components(compilation):
        styles = component.get("styles")
        if component.get("component") == "Column" and isinstance(styles, dict):
            is_event_text_stack = styles.get("height") == 34 and component.get("itemMargin") == 0
            if is_event_text_stack and len(component.get("children", ())) == 2:
                event_text_columns.append(component)
        if component.get("component") != "Divider":
            continue
        if not isinstance(styles, dict):
            continue
        if styles.get("width") == 8 and styles.get("height") == 8:
            timeline_dots.append(styles)
    assert len(event_text_columns) == 2
    assert len(timeline_dots) == 2
    for styles in timeline_dots:
        assert styles.get("borderRadius") == 4
        assert styles.get("borderWidth") == 1.5
        assert styles.get("color") == "#00FFFFFF"
        assert styles.get("borderColor") != "#00FFFFFF"


@pytest.mark.parametrize(
    ("case_factory", "weather_template", "countdown_template"),
    (
        (_three_day_weather_case, _WEATHER_THREE_DAY_FULL, _COUNTDOWN_EVENT_HERO),
        (
            _destination_weather_case,
            _WEATHER_DESTINATION_FULL,
            _COUNTDOWN_DEPARTURE_HERO,
        ),
    ),
)
def test_weather_full_and_countdown_hero_keep_the_action_at_the_layout_root(
    case_factory: Callable[[], _WideCase],
    weather_template: str,
    countdown_template: str,
) -> None:
    case = case_factory()
    routed = _route(case)
    selection = routed.selection

    assert selection.scope.advanced_component_ids == (
        "WeatherOverview",
        "CountdownOverview",
    )
    assert len(selection.required_template_groups) == 2
    weather_group, countdown_group = selection.required_template_groups
    assert weather_group == (weather_template,)
    assert countdown_group == (countdown_template,)
    assert selection.component_candidates[0].available_template_ids == weather_group
    assert selection.component_candidates[1].available_template_ids == countdown_group
    assert all(
        provider_template_layout_kind(template_id) == "Hero" for template_id in countdown_group
    )
    assert routed.projection.allowed_layout_ids == ("WideHeroActionFullLayout",)
    assert "PillAction@1" in routed.projection.contract.allowed_template_ids

    action = _only_action(routed.projection)
    weather_definition = routed.registry.require_template(weather_template)
    assert not supports_business_action(weather_definition, action, "2x4")
    source = (
        'Template("WideHeroActionFullLayout@1",{},'
        f'Template("{weather_template}",{{}}),'
        f'Template("{countdown_template}",{{}}),'
        f'Template("PillAction@1",{_action_props(action)}));'
    )
    compilation = _compile(case, routed, source)

    assert compilation.stats.action_used_ids == (action.action_id,)
    assert weather_template in compilation.stats.template_used_ids
    assert countdown_template in compilation.stats.template_used_ids
    _assert_target_height_budget(compilation)

    components_by_id = _components_by_id(compilation)
    layout_root = _content_layout(components_by_id)
    hero_action_column = components_by_id[layout_root["children"][0]]
    assert hero_action_column.get("itemMargin") == 8
    hero_slot = components_by_id[hero_action_column["children"][0]]
    action_slot = components_by_id[hero_action_column["children"][1]]
    assert hero_slot["styles"].get("height") == 82
    assert action_slot["styles"].get("height") == 36
    target_hero_height = _TARGET_BODY_HEIGHT - 8 - 36
    assert target_hero_height == 82
    assert 62 <= target_hero_height

    weather_panel = components_by_id[layout_root["children"][1]]
    weather_content = components_by_id[weather_panel["children"][0]]
    assert weather_content["styles"].get("padding") == 12
    weather_root = components_by_id[weather_content["children"][0]]

    if weather_template == _WEATHER_DESTINATION_FULL:
        assert weather_root.get("itemMargin") == 11
        weather_header = components_by_id[weather_root["children"][0]]
        weather_details = components_by_id[weather_root["children"][1]]
        assert weather_header["styles"].get("height") == 37
        assert weather_details["styles"].get("layoutWeight") == 1
        detail_rows = [components_by_id[item] for item in weather_details["children"]]
        assert len(detail_rows) == 3
        assert all(row["styles"].get("height") == 16 for row in detail_rows)
        assert 37 + 11 + 3 * 16 <= _TARGET_MASK_CONTENT_HEIGHT
        return

    components = _a2ui_components(compilation)
    component_source = json.dumps(
        components,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    daily_summaries: list[str] = []
    for component in components:
        content = component.get("content")
        if isinstance(content, str) and "/daily/" in content:
            daily_summaries.append(content)
    assert len(daily_summaries) == 15
    weather_rows = [components_by_id[item] for item in weather_root["children"]]
    assert len(weather_rows) == 4
    assert [row["styles"].get("height") for row in weather_rows] == [16, 24, 24, 24]
    total_height = sum(row["styles"].get("height", 0) for row in weather_rows)
    total_height += sum(row["styles"].get("margin", {}).get("top", 0) for row in weather_rows)
    assert total_height <= _TARGET_MASK_CONTENT_HEIGHT
    assert weather_root["styles"].get("constraintSize", {}).get("maxHeight") <= 102
    for day_group in weather_rows[1:]:
        detail_rows = [components_by_id[item] for item in day_group["children"]]
        assert len(detail_rows) == 2
        assert all(row["styles"].get("height") == 12 for row in detail_rows)
        assert all(row["styles"].get("width") == "matchParent" for row in detail_rows)
    temperature_texts = []
    for component in components:
        if component.get("component") != "Text" or not isinstance(component.get("content"), str):
            continue
        if "temperatureRangeText" in component["content"]:
            temperature_texts.append(component)
    assert len(temperature_texts) == 3
    assert all(item["styles"].get("width", 0) >= 50 for item in temperature_texts)
    assert not any(
        item.get("component") == "Stack"
        and item.get("styles", {}).get("width") == 26
        and item.get("styles", {}).get("clip") is True
        for item in components
    )
    for day_index in range(3):
        assert f"/daily/{day_index}/date" in component_source
        assert f"/daily/{day_index}/weekday" in component_source
        assert f"/daily/{day_index}/condition" in component_source
        assert f"/daily/{day_index}/rainProbabilityPercent" in component_source
        assert f"/daily/{day_index}/temperatureRangeText" in component_source


def test_generic_weather_countdown_keeps_both_mirrored_layouts() -> None:
    original = _three_day_weather_case()
    generic_task = original.task_spec.model_copy(
        update={
            "userQuery": "显示项目倒计时和未来三天天气，点击查看天气",
        }
    )
    case = _WideCase(
        generic_task,
        original.query,
        original.bindings,
        original.card_spec,
    )
    routed = _route(case)

    countdown_group = routed.selection.required_template_groups[1]
    assert _COUNTDOWN_EVENT_HERO in countdown_group
    assert _COUNTDOWN_DEPARTURE_HERO in countdown_group
    assert routed.projection.allowed_layout_ids == (
        "WideFullHeroActionLayout",
        "WideHeroActionFullLayout",
    )


def test_q084_routes_health_full_countdown_compact_and_compact_action() -> None:
    case = _health_countdown_case()
    routed = _route(case)
    selection = routed.selection

    assert selection.scope.advanced_component_ids == (
        "ActivityOverview",
        "CountdownOverview",
    )
    assert selection.required_template_groups == (
        (_HEALTH_FULL,),
        (_COUNTDOWN_COMPACT,),
    )
    assert routed.projection.allowed_layout_ids == ("WideFullTwoCompactLayout",)
    assert "CompactAction@1" in routed.projection.contract.allowed_template_ids

    action = _only_action(routed.projection)
    source = (
        'Template("WideFullTwoCompactLayout@1",{"compactRows":true},'
        f'Template("{_HEALTH_FULL}",{{}}),'
        f'Template("{_COUNTDOWN_COMPACT}",'
        f'{{"countdownIcon":"{_COUNTDOWN_ICON}"}}),'
        f'Template("CompactAction@1",{_action_props(action, icon=_RUN_ICON)}));'
    )
    compilation = _compile(case, routed, source)

    assert compilation.stats.action_used_ids == (action.action_id,)
    assert _HEALTH_FULL in compilation.stats.template_used_ids
    assert _COUNTDOWN_COMPACT in compilation.stats.template_used_ids
    _assert_target_height_budget(compilation)

    components_by_id = _components_by_id(compilation)
    layout_root = _content_layout(components_by_id)
    health_slot = components_by_id[layout_root["children"][0]]
    compact_column = components_by_id[layout_root["children"][1]]
    assert compact_column.get("itemMargin") == 12
    compact_slots = [components_by_id[item] for item in compact_column["children"]]
    assert len(compact_slots) == 2
    assert all(slot["styles"].get("height") == 57 for slot in compact_slots)
    assert 57 * 2 + 12 == _TARGET_BODY_HEIGHT

    health_root = components_by_id[health_slot["children"][0]]
    assert health_root["styles"].get("justifyContent") == "spaceBetween"
    health_groups = [components_by_id[item] for item in health_root["children"]]
    assert [group["styles"].get("height") for group in health_groups] == [76, 36]
    assert 76 + 36 <= _TARGET_BODY_HEIGHT

    image_sources = {
        component.get("src")
        for component in _a2ui_components(compilation)
        if component.get("component") == "Image"
    }
    assert _COUNTDOWN_ICON in image_sources


@pytest.mark.parametrize("event_index", (1, 2))
def test_calendar_multi_event_action_must_target_the_clickable_displayed_event(
    event_index: int,
) -> None:
    registry = get_cardplan_registry()
    definition = registry.require_template(_CALENDAR_FULL)
    positive_task = _calendar_countdown_case().task_spec
    positive_bindings = action_bindings(positive_task)
    assert len(positive_bindings) == 1
    assert supports_business_action(definition, positive_bindings[0], "2x4")

    negative_task = positive_task.model_copy(
        update={"eventCandidates": [_calendar_action(event_index)]}
    )
    negative_bindings = action_bindings(negative_task)
    assert len(negative_bindings) == 1
    assert not supports_business_action(definition, negative_bindings[0], "2x4")
