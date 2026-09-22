"""Plan 主数据优先、实际字段使用量与稳定排序回归。"""

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.tests.test_template_plan_planner import (
    _field,
    _weather_binding,
    _weather_card_spec,
    _weather_task,
)


@pytest.mark.parametrize("focus", [None, "/current/temperatureText"])
def test_primary_data_stays_ahead_of_richer_secondary_data(focus: str | None) -> None:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"ViewWeather": ("/current/temperatureText",)},
        primaryOutputFieldByCapability={} if focus is None else {"ViewWeather": focus},
    )
    registry = get_cardplan_registry()
    search = search_template_variants(
        intent,
        _weather_task(),
        registry,
        (_weather_binding(),),
        _weather_card_spec(),
    )
    plans = plan_template_candidates(intent, search, _weather_task(), registry)
    assert plans[0].business_slots[0].template_id == "WeatherOverviewFull@1"
    if focus is not None:
        for plan in plans:
            assert focus in plan.business_slots[0].primary_matched_fields


def test_richer_templates_win_then_equal_usage_keeps_search_order() -> None:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/condition",),
        }
    )
    registry = get_cardplan_registry()
    task = _weather_task()
    search = search_template_variants(
        intent,
        task,
        registry,
        (_weather_binding(),),
        _weather_card_spec(),
    )
    plans = plan_template_candidates(intent, search, task, registry)
    assert [plan.business_slots[0].template_id for plan in plans] == [
        "WeatherOverviewHumidityFull@1",
        "WeatherOverviewUvFull@1",
        "WeatherOverviewFull@1",
    ]
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=_weather_card_spec(),
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )
    message = projection.messages[1].get("content")
    assert isinstance(message, str)
    assert "数据使用量" in message
    assert "优先选择排名靠前的 Plan" in message


@pytest.mark.parametrize("optional_state", ["available", "missing", "wrong-type", "not-candidate"])
def test_search_counts_only_usable_candidate_bindings(optional_state: str) -> None:
    task = _weather_task()
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    weather = data.get("weather")
    assert isinstance(weather, dict)
    current = weather.get("current")
    assert isinstance(current, dict)
    binding = _weather_binding()
    if optional_state == "missing":
        current.pop("airQuality")
    elif optional_state == "wrong-type":
        current["airQuality"] = _field(12, "integer")
    elif optional_state == "not-candidate":
        binding.candidateOutputFields.remove("/current/airQuality")
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/temperatureText",),
        }
    )
    result = search_template_variants(
        intent,
        task,
        get_cardplan_registry(),
        (binding,),
        _weather_card_spec(),
    )
    candidate = next(
        item
        for item in result.business_candidates[0].candidates
        if item.template_id == "WeatherOverviewFull@1"
    )
    paths = candidate.available_data_fields
    assert ("/data/weather/current/airQuality" in paths) is (optional_state == "available")
    assert len(paths) == (6 if optional_state == "available" else 5)
    assert len(paths) == len(set(paths))


def test_dual_root_usage_counts_each_real_binding_once() -> None:
    fields = ["/current/temperatureC", "/current/condition"]
    roots = ("/data/weather1", "/data/weather2")
    task = TaskSpec(
        userQuery="两个城市的天气",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather1": {
                    "current": {"temperatureC": _field(20.0, "number"), "condition": _field("晴")}
                },
                "weather2": {
                    "current": {"temperatureC": _field(25.0, "number"), "condition": _field("多云")}
                },
            }
        },
    )
    bindings = tuple(
        CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo=root,
            candidateOutputFields=fields,
        )
        for root in roots
    )
    card_spec = {
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": root} for root in roots]
    }
    result = search_template_variants(
        TemplateSearchIntent(requiredOutputFieldsByCapability={"ViewWeather": fields}),
        task,
        get_cardplan_registry(),
        bindings,
        card_spec,
    )
    candidate = result.business_candidates[0].candidates[0]
    assert candidate.template_id == "WeatherOverviewDualCityFull@1"
    assert candidate.available_data_fields == (
        "/data/weather1/current/condition",
        "/data/weather1/current/temperatureC",
        "/data/weather2/current/condition",
        "/data/weather2/current/temperatureC",
    )


def test_dual_business_plan_prefers_more_data_before_secondary_matches() -> None:
    task = _weather_task()
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    weather = data.get("weather")
    assert isinstance(weather, dict)
    current = weather.get("current")
    assert isinstance(current, dict)
    current.update({"temperatureC": _field(29.0, "number"), "feelsLikeC": _field(30.0, "number")})
    data["phoneBattery"] = {"batterySOC": _field(80, "integer")}
    weather_binding = _weather_binding()
    weather_binding.candidateOutputFields.extend(["/current/temperatureC", "/current/feelsLikeC"])
    battery_binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=["/batterySOC"],
    )
    bindings = (weather_binding, battery_binding)
    card_spec = {
        "dataBindings": [
            {"capabilityId": item.capabilityId, "writeResultTo": item.writeResultTo}
            for item in bindings
        ]
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/temperatureText", "/current/condition"),
            "GetPhoneBatteryInfo": ("/batterySOC",),
        }
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, bindings, card_spec)
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans[0].layout_template_id == "TwoSupportLayout@1"
    assert {slot.template_id for slot in plans[0].business_slots} == {
        "WeatherOverviewTemperatureSupport@1",
        "BatteryOverviewSupport@1",
    }
