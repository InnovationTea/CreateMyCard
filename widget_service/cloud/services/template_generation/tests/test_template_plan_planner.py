from __future__ import annotations

import json

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    build_ux_mixed_prompt,
)
from services.template_generation.engine.cardplan.compiler import (
    _validate_allowed_template_plan,
)
from services.template_generation.engine.cardplan.models import (
    HybridBodyContract,
    HybridLimits,
    TemplatePlan,
)
from services.template_generation.engine.cardplan.parser import parse_ux_layout_card
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateBusinessCandidates,
    TemplateSearchCandidate,
    TemplateSearchIntent,
    TemplateSearchResult,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.engine.tersel_converter import TerselConversionError


def _field(value: object, data_type: str = "string") -> dict[str, object]:
    return {"type": data_type, "description": "trusted", "sampleValue": value}


def _weather_task() -> TaskSpec:
    return TaskSpec(
        userQuery="显示青浦区温度和空气质量，温度是主信息",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {
                        "prefectureName": _field("上海市"),
                        "districtName": _field("青浦区"),
                    },
                    "current": {
                        "temperatureText": _field("29°C"),
                        "condition": _field("多云"),
                        "airQuality": _field("良"),
                        "coldLevel": _field("低"),
                        "humidityPercent": _field(70.0, "number"),
                        "uvIndex": _field("中等"),
                    },
                }
            }
        },
    )


def _weather_binding() -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/location/prefectureName",
            "/location/districtName",
            "/current/temperatureText",
            "/current/condition",
            "/current/airQuality",
            "/current/coldLevel",
            "/current/humidityPercent",
            "/current/uvIndex",
        ],
    )


def _weather_card_spec() -> dict[str, object]:
    return {
        "title": "天气速览",
        "description": "温度和空气质量",
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}
        ],
    }


def test_first_layer_contract_contains_only_fields_focus_and_actions() -> None:
    messages = build_template_retrieval_prompt(
        _weather_task(),
        get_cardplan_registry(),
        (_weather_binding(),),
    )

    system_content = messages[0].get("content")
    user_content = messages[1].get("content")
    assert isinstance(system_content, str)
    assert isinstance(user_content, str)
    payload = json.loads(user_content)
    schema = json.loads(system_content.splitlines()[-1])
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    assert "themes" not in payload
    assert "themeFirstLayerRules" not in payload
    assert set(properties) == {
        "requiredOutputFieldsByCapability",
        "primaryOutputFieldByCapability",
        "action",
    }


def test_search_keeps_optional_only_template_and_reports_concise_coverage() -> None:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/location/districtName",
                "/current/temperatureText",
                "/current/condition",
            )
        }
    )

    result = search_template_variants(
        intent,
        _weather_task(),
        get_cardplan_registry(),
        (_weather_binding(),),
        _weather_card_spec(),
    )

    weather = next(
        item
        for item in result.business_candidates
        if item.business_id == "WeatherOverview"
    )
    candidates = {item.template_id: item for item in weather.candidates}
    hero_title = candidates.get("WeatherOverviewHeroTitle@1")
    assert hero_title is not None
    assert hero_title.covered_explicit_fields == weather.explicit_fields
    assert set(result.model_dump(by_alias=True)) == {"cardSize", "businessCandidates"}


def test_single_business_planner_prefers_explicit_primary_data_match() -> None:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/current/temperatureText",
                "/current/airQuality",
                "/location/districtName",
            )
        },
        primaryOutputFieldByCapability={
            "ViewWeather": "/current/temperatureText"
        },
    )
    result = search_template_variants(
        intent,
        _weather_task(),
        get_cardplan_registry(),
        (_weather_binding(),),
        _weather_card_spec(),
    )

    plans = plan_template_candidates(
        intent,
        result,
        _weather_task(),
        get_cardplan_registry(),
    )

    assert len(plans) <= 3
    assert tuple(slot.template_id for slot in plans[0].business_slots) == (
        "WeatherOverviewFull@1",
    )
    assert all(
        "/current/temperatureText" in plan.business_slots[0].primary_matched_fields
        for plan in plans
    )


def test_second_layer_receives_only_bounded_atomic_plans() -> None:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/current/temperatureText",
                "/current/airQuality",
                "/location/districtName",
            )
        },
        primaryOutputFieldByCapability={
            "ViewWeather": "/current/temperatureText"
        },
    )
    task_spec = _weather_task()
    registry = get_cardplan_registry()
    search_result = search_template_variants(
        intent,
        task_spec,
        registry,
        (_weather_binding(),),
        _weather_card_spec(),
    )
    plans = plan_template_candidates(intent, search_result, task_spec, registry)

    projection = build_ux_mixed_prompt(
        task_spec=task_spec,
        card_spec=_weather_card_spec(),
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )

    second_layer_content = projection.messages[1].get("content")
    assert isinstance(second_layer_content, str)
    plan_line = next(
        line
        for line in second_layer_content.splitlines()
        if line.startswith("planCandidates=")
    )
    prompt_plans = json.loads(plan_line.removeprefix("planCandidates="))
    assert 1 <= len(prompt_plans) <= 3
    assert projection.contract.allowed_template_plans == plans
    assert "不得跨 Plan 混用" in second_layer_content


def _support_plans() -> tuple[TemplatePlan, ...]:
    action_id = "event.open.weather"
    task_spec = TaskSpec(
        userQuery="同时显示天气和应用时长，点击查看天气",
        size="2x2",
        dataModelSchema={},
        eventCandidates=[
            EventAction(
                id=action_id,
                displayLabel="天气详情",
                call="clickToIntent",
                args={"intentName": "Weather"},
            )
        ],
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/temperatureText",),
            "GetAppUsageDuration": ("/appUsage/durationText",),
        },
        action=(action_id,),
    )
    result = TemplateSearchResult(
        cardSize="2x2",
        businessCandidates=(
            TemplateBusinessCandidates(
                capabilityId="ViewWeather",
                businessId="WeatherOverview",
                explicitFields=("/current/temperatureText",),
                candidates=(
                    TemplateSearchCandidate(
                        templateId="WeatherOverviewTemperatureSupport@1",
                        coveredExplicitFields=("/current/temperatureText",),
                    ),
                ),
            ),
            TemplateBusinessCandidates(
                capabilityId="GetAppUsageDuration",
                businessId="AppUsageOverview",
                explicitFields=("/appUsage/durationText",),
                candidates=(
                    TemplateSearchCandidate(
                        templateId="AppUsageOverviewSupport@1",
                        coveredExplicitFields=("/appUsage/durationText",),
                    ),
                ),
            ),
        ),
    )
    return plan_template_candidates(intent, result, task_spec, get_cardplan_registry())


def test_planner_can_assign_action_to_vertical_business_template() -> None:
    plans = _support_plans()

    assert 1 <= len(plans) <= 3
    assert all(plan.layout_template_id == "TwoSupportLayout@1" for plan in plans)
    assert all(
        assignment.consumer == "business-template"
        for plan in plans
        for assignment in plan.action_assignments
    )


def test_planner_composes_new_provider_supports_and_consumes_two_actions() -> None:
    action_ids = ("event.open.battery", "event.open.calendar")
    task_spec = TaskSpec(
        userQuery="同时显示手机电量和下一个日程，并支持分别查看详情",
        size="2x2",
        dataModelSchema={},
        eventCandidates=[
            EventAction(
                id=action_id,
                displayLabel="查看详情",
                call="clickToIntent",
                args={"intentName": action_id},
            )
            for action_id in action_ids
        ],
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
            "GetCalendarEvents": ("/events/0/title", "/events/0/dtStart"),
        },
        action=action_ids,
    )
    result = TemplateSearchResult(
        cardSize="2x2",
        businessCandidates=(
            TemplateBusinessCandidates(
                capabilityId="GetPhoneBatteryInfo",
                businessId="BatteryOverview",
                explicitFields=("/batterySOC", "/chargingStatusDesc"),
                candidates=(
                    TemplateSearchCandidate(
                        templateId="BatteryOverviewSupport@1",
                        coveredExplicitFields=(
                            "/batterySOC",
                            "/chargingStatusDesc",
                        ),
                    ),
                ),
            ),
            TemplateBusinessCandidates(
                capabilityId="GetCalendarEvents",
                businessId="CalendarOverview",
                explicitFields=("/events/0/title", "/events/0/dtStart"),
                candidates=(
                    TemplateSearchCandidate(
                        templateId="ScheduleOverviewSupport@1",
                        coveredExplicitFields=(
                            "/events/0/title",
                            "/events/0/dtStart",
                        ),
                    ),
                ),
            ),
        ),
    )

    plans = plan_template_candidates(
        intent,
        result,
        task_spec,
        get_cardplan_registry(),
    )

    assert plans
    assert all(plan.layout_template_id == "TwoSupportLayout@1" for plan in plans)
    assert all(
        {slot.template_id for slot in plan.business_slots}
        == {"BatteryOverviewSupport@1", "ScheduleOverviewSupport@1"}
        for plan in plans
    )
    assert all(
        {assignment.business_position for assignment in plan.action_assignments}
        == {0, 1}
        for plan in plans
    )
    assert all(
        assignment.consumer == "business-template"
        for plan in plans
        for assignment in plan.action_assignments
    )


def test_validator_rejects_cross_plan_action_assignment_mix() -> None:
    plans = _support_plans()
    assert len(plans) >= 2
    action_id = plans[0].action_assignments[0].action_id
    contract = HybridBodyContract(
        theme_profile_id="2x2-two-support",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=(),
        allowed_asset_sources=(),
        trusted_literals=(),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        allowed_template_plans=plans,
        limits=HybridLimits(
            max_raw_components=16,
            max_expanded_components=64,
            max_nesting_depth=8,
            vertical_budget_vp=128,
        ),
    )
    valid_source = (
        'Template("TwoSupportLayout@1",{},'
        'Template("WeatherOverviewTemperatureSupport@1",'
        f'{{"actionId":"{action_id}"}}),'
        'Template("AppUsageOverviewSupport@1",{}));'
    )
    matched_plan_id = _validate_allowed_template_plan(
        parse_ux_layout_card(valid_source),
        contract,
        get_cardplan_registry(),
    )
    assert matched_plan_id == plans[0].plan_id

    mixed_source = (
        'Template("TwoSupportLayout@1",{},'
        'Template("WeatherOverviewTemperatureSupport@1",'
        f'{{"actionId":"{action_id}"}}),'
        'Template("AppUsageOverviewSupport@1",'
        f'{{"actionId":"{action_id}"}}));'
    )

    with pytest.raises(TerselConversionError, match="exactly one atomic Template Plan"):
        _validate_allowed_template_plan(
            parse_ux_layout_card(mixed_source),
            contract,
            get_cardplan_registry(),
        )
