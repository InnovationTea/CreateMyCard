"""Plan 主数据优先与数据使用量统计的场景金样回归。

两类确定性数据使用契约已固化为场景金样（Layer C）：
- plan_data__plan_preference：Plan 偏好矩阵——无/有主数据焦点时主数据优先于
  更丰富的次级数据、仅 condition 需求下的使用量排序（Humidity → Uv → Full）、
  双业务取更多真实数据优先于次级匹配，逐用例冻结布局/业务槽/主数据匹配；
- plan_data__usable_bindings：候选可用字段统计——可选字段 available / missing /
  wrong-type / not-candidate 四态与双数据根各计一次的路径清单（去重后冻结）。
第二层 prompt 中的「数据使用量」章节与「优先选择排名靠前的 Plan」文案契约
保留为内联测试（解释 Layer B 录制的 prompt 字节）。检索排序或可用字段统计
改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

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
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)
from services.template_generation.tests.test_template_plan_planner import (
    _field,
    _plan_summaries,
    _weather_binding,
    _weather_card_spec,
    _weather_task,
)


# --------------------------------------------------------------------------
# 场景：Plan 偏好（主数据优先 / 使用量排序 / 双业务更多数据）
# --------------------------------------------------------------------------


def _weather_plans_with_focus(focus: str | None) -> list[dict[str, object]]:
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"ViewWeather": ("/current/temperatureText",)},
        primaryOutputFieldByCapability={} if focus is None else {"ViewWeather": focus},
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
    return _plan_summaries(plan_template_candidates(intent, search, task, registry))


def _condition_ranking() -> list[str]:
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
    return [plan.business_slots[0].template_id for plan in plans]


def _dual_business_plans() -> list[dict[str, object]]:
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
    return _plan_summaries(plan_template_candidates(intent, search, task, registry))


@scenario("plan_data__plan_preference")
def _build_plan_preference() -> dict[str, object]:
    return {
        "primary_focus_default": {"plans": _weather_plans_with_focus(None)},
        "primary_focus_temperature": {"plans": _weather_plans_with_focus("/current/temperatureText")},
        "usage_ranking_condition": {"orderedPlanTemplates": _condition_ranking()},
        "dual_business_more_data": {"plans": _dual_business_plans()},
    }


# --------------------------------------------------------------------------
# 场景：候选可用字段统计
# --------------------------------------------------------------------------


def _usable_binding_fields(optional_state: str) -> list[str]:
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
    return sorted(candidate.available_data_fields)


def _dual_root_binding_fields() -> list[str]:
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
    return sorted(candidate.available_data_fields)


@scenario("plan_data__usable_bindings")
def _build_usable_bindings() -> dict[str, object]:
    return {
        "available": _usable_binding_fields("available"),
        "missing": _usable_binding_fields("missing"),
        "wrong_type": _usable_binding_fields("wrong-type"),
        "not_candidate": _usable_binding_fields("not-candidate"),
        "dual_root": _dual_root_binding_fields(),
    }


# --------------------------------------------------------------------------
# 保留的内联契约测试（prompt 内容契约，解释 Layer B 录制字节）
# --------------------------------------------------------------------------


def test_second_layer_prompt_declares_data_usage_preference() -> None:
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


# --------------------------------------------------------------------------
# 场景金样断言入口
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", [
    "plan_data__plan_preference",
    "plan_data__usable_bindings",
])
def test_plan_data_golden_scenarios(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
