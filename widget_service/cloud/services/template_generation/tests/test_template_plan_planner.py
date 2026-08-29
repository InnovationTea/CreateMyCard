"""Plan 规划与检索选择契约的场景金样回归。

确定性规划/检索契约已固化为场景金样（Layer C）：
- plan_planner__semantic_action_icon：语义动作图标判定矩阵（事件是否选中 ×
  素材描述语义），逐用例冻结布尔结果；
- plan_planner__search_selections：各查询族解析出的 Plan 集合（布局、业务槽、
  主数据匹配字段、动作归属与业务位次）、可选字段模板的候选覆盖与检索结果
  集形态，整体冻结；
- plan_planner__wind_time_optionality：updatedAt 可选/必填的检索矩阵，缺失
  必填字段时的 TemplateRetrievalMiss 报文同样冻结；
- plan_planner__dual_city_runtime_roots：双城市第二数据根类型校验矩阵
  （非 number 根的检索报错与 number 根的 Plan 解析各占一态）；
- plan_planner__cross_plan_mix_rejected：合法 Plan 命中的 planId 与跨 Plan
  混用动作被校验器拒绝的 TerselConversionError 报文。
第一层 prompt 协议字段契约与第二层「有界原子 Plan + 禁止跨 Plan 混用」的
prompt 内容契约保留为内联测试（它们解释 Layer B 录制的 prompt 字节）。
引擎或检索改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

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
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    _has_semantic_action_icon,
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateBusinessCandidates,
    TemplateRetrievalMiss,
    TemplateSearchCandidate,
    TemplateSearchIntent,
    TemplateSearchResult,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)


# --------------------------------------------------------------------------
# 共享构造器（plan_data 用例复用）
# --------------------------------------------------------------------------


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


def _plan_summaries(plans: tuple[TemplatePlan, ...]) -> list[dict[str, object]]:
    """把 Plan 集合压缩成可冻结的稳定摘要（布局/业务槽/主数据匹配/动作归属）。"""

    return [
        {
            "layout": plan.layout_template_id,
            "slots": [
                {
                    "template": slot.template_id,
                    "business": slot.business_id,
                    "primaryMatched": sorted(slot.primary_matched_fields),
                }
                for slot in plan.business_slots
            ],
            "actions": sorted(
                (
                    {
                        "action": item.action_id,
                        "consumer": item.consumer,
                        "businessPosition": item.business_position,
                    }
                    for item in plan.action_assignments
                ),
                key=lambda item: (item["action"], item["consumer"]),
            ),
        }
        for plan in plans
    ]


# --------------------------------------------------------------------------
# 场景：语义动作图标判定矩阵
# --------------------------------------------------------------------------

_SEMANTIC_ICON_CASES: dict[str, tuple[bool, str]] = {
    "selected_power_saving": (True, "默认黑色的电池图标，适用省电模式、节能电池"),
    "deselected_power_saving": (False, "默认黑色的电池图标，适用省电模式、节能电池"),
    "selected_sun": (True, "默认黑色的太阳图标，适用晴天"),
    "selected_generic_battery": (True, "默认黑色的电池图标，适用电量展示"),
}


@scenario("plan_planner__semantic_action_icon")
def _build_semantic_action_icon() -> dict[str, bool]:
    result: dict[str, bool] = {}
    for key, (selected, description) in _SEMANTIC_ICON_CASES.items():
        task = TaskSpec(
            userQuery="显示手机电量", size="2x2", dataModelSchema={},
            eventCandidates=[EventAction(
                id="event.setPowerSavingMode", call="clickToIntent", args={},
            )],
            assetCandidates=[
                {"src": "resources/base/media/example.svg", "description": description}
            ],
        )
        selected_ids = ("event.setPowerSavingMode",) if selected else ()
        result[key] = _has_semantic_action_icon(task, selected_ids)
    return result


# --------------------------------------------------------------------------
# 场景：updatedAt 可选性与双城市数据根校验矩阵
# --------------------------------------------------------------------------


def _wind_time_search(has_updated_at: bool, requires_updated_at: bool) -> dict[str, object]:
    weather = {
        "location": {"prefectureName": _field("深圳市")},
        "current": {"windDirection": _field("东南风"), "windLevel": _field(2, "integer")},
    }
    fields = ["/location/prefectureName", "/current/windDirection", "/current/windLevel"]
    required = list(fields)
    if has_updated_at:
        weather["updatedAt"] = _field("09:00")
        fields.append("/updatedAt")
    if requires_updated_at:
        required.append("/updatedAt")
    task = TaskSpec(
        userQuery="查看城市风况", size="2x2", dataModelSchema={"data": {"weather": weather}},
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather", writeResultTo="/data/weather", candidateOutputFields=fields,
    )
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"ViewWeather": tuple(required)})
    try:
        result = search_template_variants(
            intent, task, get_cardplan_registry(), (binding,), _weather_card_spec(),
        )
    except TemplateRetrievalMiss as error:
        return {"errorType": type(error).__name__, "message": str(error)}
    return {
        "candidates": [
            candidate.template_id
            for business in result.business_candidates
            for candidate in business.candidates
        ],
    }


@scenario("plan_planner__wind_time_optionality")
def _build_wind_time_optionality() -> dict[str, object]:
    return {
        "optional_present": _wind_time_search(True, False),
        "required_present": _wind_time_search(True, True),
        "optional_missing": _wind_time_search(False, False),
        "required_missing": _wind_time_search(False, True),
    }


def _dual_city_search(second_temperature: str) -> dict[str, object]:
    second_current: dict[str, object] = {"condition": _field("小雨")}
    if second_temperature != "missing":
        value: object = 25 if second_temperature == "number" else "25"
        second_current["temperatureC"] = _field(value, second_temperature)
    task = TaskSpec(
        userQuery="显示成都和上海的温度及天气现象",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather1": {
                    "current": {
                        "temperatureC": _field(29, "number"),
                        "condition": _field("多云"),
                    },
                },
                "weather2": {"current": second_current},
            },
        },
    )
    fields = ("/current/temperatureC", "/current/condition")
    bindings = tuple(
        CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo=root,
            candidateOutputFields=list(fields),
        )
        for root in ("/data/weather1", "/data/weather2")
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": binding.capabilityId, "writeResultTo": binding.writeResultTo}
            for binding in bindings
        ],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"ViewWeather": fields},
    )
    registry = get_cardplan_registry()
    try:
        result = search_template_variants(intent, task, registry, bindings, card_spec)
    except TemplateRetrievalMiss as error:
        return {"errorType": type(error).__name__, "message": str(error)}
    candidates = result.business_candidates[0].candidates
    return {
        "coveredExplicitFields": list(candidates[0].covered_explicit_fields),
        "candidates": [candidate.template_id for candidate in candidates],
        "plans": _plan_summaries(plan_template_candidates(intent, result, task, registry)),
    }


@scenario("plan_planner__dual_city_runtime_roots")
def _build_dual_city_runtime_roots() -> dict[str, object]:
    return {
        "number": _dual_city_search("number"),
        "string": _dual_city_search("string"),
        "missing": _dual_city_search("missing"),
    }


# --------------------------------------------------------------------------
# 场景：各查询族解析出的 Plan 选择与候选覆盖
# --------------------------------------------------------------------------


def _wind_full_plans() -> list[dict[str, object]]:
    task = TaskSpec(
        userQuery="显示风向、风力等级和城市名称的天气卡片",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"prefectureName": _field("上海市")},
                    "current": {
                        "windDirection": _field("东南风"),
                        "windLevel": _field(2, "integer"),
                    },
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/location/prefectureName",
            "/current/windDirection",
            "/current/windLevel",
        ],
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": (
                "/location/prefectureName",
                "/current/windDirection",
                "/current/windLevel",
            )
        }
    )
    registry = get_cardplan_registry()
    result = search_template_variants(intent, task, registry, (binding,), card_spec)
    return _plan_summaries(plan_template_candidates(intent, result, task, registry))


def _activity_full_plans() -> list[dict[str, object]]:
    task = TaskSpec(
        userQuery="做个卡片，显示今天总步数",
        size="2x2",
        dataModelSchema={
            "data": {
                "healthSport": {"dailySteps": _field(6200, "integer")},
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetHealthAndSportSummary",
        writeResultTo="/data/healthSport",
        candidateOutputFields=["/dailySteps"],
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "GetHealthAndSportSummary", "writeResultTo": "/data/healthSport"}
        ],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetHealthAndSportSummary": ("/dailySteps",)},
        primaryOutputFieldByCapability={"GetHealthAndSportSummary": "/dailySteps"},
    )
    registry = get_cardplan_registry()
    result = search_template_variants(intent, task, registry, (binding,), card_spec)
    return _plan_summaries(plan_template_candidates(intent, result, task, registry))


def test_heart_rate_updated_full_supports_update_time_action_less_card() -> None:
    task = TaskSpec(
        userQuery="显示运动平均心率和更新时间的卡片",
        size="2x2",
        dataModelSchema={
            "data": {
                "healthSport": {
                    "exerciseHeartRateAvg": _field(135, "integer"),
                    "updatedAt": _field("2026-08-06 09:00"),
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetHealthAndSportSummary",
        writeResultTo="/data/healthSport",
        candidateOutputFields=["/exerciseHeartRateAvg", "/updatedAt"],
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {"capabilityId": "GetHealthAndSportSummary", "writeResultTo": "/data/healthSport"}
        ],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "GetHealthAndSportSummary": ("/exerciseHeartRateAvg", "/updatedAt"),
        },
        primaryOutputFieldByCapability={"GetHealthAndSportSummary": "/exerciseHeartRateAvg"},
    )
    registry = get_cardplan_registry()
    result = search_template_variants(intent, task, registry, (binding,), card_spec)
    plans = plan_template_candidates(intent, result, task, registry)

    assert plans
    assert plans[0].layout_template_id == "SingleFocusLayout@1"
    assert plans[0].business_slots[0].template_id == "HeartRateOverviewUpdatedFull@1"


def _weather_primary_plans() -> list[dict[str, object]]:
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
    registry = get_cardplan_registry()
    result = search_template_variants(
        intent,
        _weather_task(),
        registry,
        (_weather_binding(),),
        _weather_card_spec(),
    )
    return _plan_summaries(
        plan_template_candidates(intent, result, _weather_task(), registry)
    )


def _optional_only_weather_coverage() -> dict[str, object]:
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
    return {
        "explicitFields": sorted(weather.explicit_fields),
        "candidates": {
            candidate.template_id: sorted(candidate.covered_explicit_fields)
            for candidate in weather.candidates
        },
        "resultKeys": sorted(result.model_dump(by_alias=True)),
    }


def _support_plans() -> tuple[TemplatePlan, ...]:
    action_id = "event.open.weather"
    task_spec = TaskSpec(
        userQuery="同时显示天气和手机电量，点击查看天气",
        size="2x2",
        dataModelSchema={},
        eventCandidates=[
            EventAction(
                id=action_id,
                displayLabel="天气详情",
                call="clickToDeeplink",
                args={
                    "intentName": "Weather_CityCode",
                    "bundleName": "",
                    "abilityName": "",
                    "uri": (
                        "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode='"
                        " + ${/data/weather/location/cityCode} }}"
                    ),
                },
            )
        ],
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/temperatureText",),
            "GetPhoneBatteryInfo": ("/batterySOC",),
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
                capabilityId="GetPhoneBatteryInfo",
                businessId="BatteryOverview",
                explicitFields=("/batterySOC",),
                candidates=(
                    TemplateSearchCandidate(
                        templateId="BatteryOverviewSupport@1",
                        coveredExplicitFields=("/batterySOC",),
                    ),
                ),
            ),
        ),
    )
    return plan_template_candidates(intent, result, task_spec, get_cardplan_registry())


def _dual_support_two_action_plans() -> list[dict[str, object]]:
    action_ids = ("event.open.settings.battery", "event.viewCalendarEvent")
    task_spec = TaskSpec(
        userQuery="同时显示手机电量和下一个日程，并支持分别查看详情",
        size="2x2",
        dataModelSchema={},
        eventCandidates=[
            EventAction(
                id="event.open.settings.battery",
                displayLabel="电池设置",
                call="clickToDeeplink",
                args={
                    "intentName": "Settings",
                    "bundleName": "com.huawei.hmos.settings",
                    "abilityName": "com.huawei.hmos.settings.MainAbility",
                    "uri": "battery",
                },
            ),
            EventAction(
                id="event.viewCalendarEvent",
                displayLabel="查看日程",
                call="clickToIntent",
                args={
                    "intentName": "ViewCalendarEvent",
                    "params": {"entityId": "{{ ${/data/calendar/events/0/entityId} }}"},
                },
            ),
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
                        templateId="ScheduleOverviewTimeSupport@1",
                        coveredExplicitFields=(
                            "/events/0/title",
                            "/events/0/dtStart",
                        ),
                    ),
                ),
            ),
        ),
    )
    return _plan_summaries(
        plan_template_candidates(intent, result, task_spec, get_cardplan_registry())
    )


@scenario("plan_planner__search_selections")
def _build_search_selections() -> dict[str, object]:
    return {
        "wind_full_no_action": {"plans": _wind_full_plans()},
        "activity_full_steps_only": {"plans": _activity_full_plans()},
        "weather_primary_temperature": {"plans": _weather_primary_plans()},
        "optional_only_weather": {"coverage": _optional_only_weather_coverage()},
        "support_action_vertical": {"plans": _plan_summaries(_support_plans())},
        "support_two_actions": {"plans": _dual_support_two_action_plans()},
    }


# --------------------------------------------------------------------------
# 场景：跨 Plan 混用动作被校验器拒绝
# --------------------------------------------------------------------------


def _support_plan_contract(plans: tuple[TemplatePlan, ...]) -> HybridBodyContract:
    action_id = plans[0].action_assignments[0].action_id
    return HybridBodyContract(
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
        action_bindings=action_bindings(TaskSpec(
            userQuery="查看天气",
            size="2x2",
            dataModelSchema={},
            eventCandidates=[EventAction(
                id=action_id,
                call="clickToDeeplink",
                args={"uri": "{{ ${/data/weather/location/cityCode} }}"},
            )],
        )),
        content_action_ids=(action_id,),
        limits=HybridLimits(
            max_raw_components=16,
            max_expanded_components=64,
            max_nesting_depth=8,
            vertical_budget_vp=128,
        ),
    )


@scenario("plan_planner__cross_plan_mix_rejected")
def _build_cross_plan_mix_rejected() -> dict[str, object]:
    plans = _support_plans()
    contract = _support_plan_contract(plans)
    registry = get_cardplan_registry()
    action_id = plans[0].action_assignments[0].action_id
    valid_source = (
        'Template("TwoSupportLayout@1",{},'
        'Template("WeatherOverviewTemperatureSupport@1",'
        f'{{"actionId":"{action_id}"}}),'
        'Template("BatteryOverviewSupport@1",{}));'
    )
    matched_plan_id = _validate_allowed_template_plan(
        parse_ux_layout_card(valid_source), contract, registry,
    )
    mixed_source = (
        'Template("TwoSupportLayout@1",{},'
        'Template("WeatherOverviewTemperatureSupport@1",'
        f'{{"actionId":"{action_id}"}}),'
        'Template("BatteryOverviewSupport@1",'
        f'{{"actionId":"{action_id}"}}));'
    )
    try:
        _validate_allowed_template_plan(parse_ux_layout_card(mixed_source), contract, registry)
        mixed_error: dict[str, str] = {"error": "NO_ERROR"}
    except TerselConversionError as error:
        mixed_error = {"errorType": type(error).__name__, "message": str(error)}
    return {
        "matchedPlanId": matched_plan_id,
        "planCount": len(plans),
        "mixedError": mixed_error,
    }


# --------------------------------------------------------------------------
# 保留的内联契约测试（prompt 内容契约，解释 Layer B 录制字节）
# --------------------------------------------------------------------------


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
        "allowCalendarViewFallback",
    }


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


# --------------------------------------------------------------------------
# 场景金样断言入口
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", [
    "plan_planner__semantic_action_icon",
    "plan_planner__wind_time_optionality",
    "plan_planner__dual_city_runtime_roots",
    "plan_planner__search_selections",
    "plan_planner__cross_plan_mix_rejected",
])
def test_plan_planner_golden_scenarios(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
