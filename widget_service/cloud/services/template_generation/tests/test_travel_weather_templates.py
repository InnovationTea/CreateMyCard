"""出行倒计时与目的地天气模板回归。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.pipeline import generate_template_a2ui


def _a2ui_components(a2ui: str) -> list[dict[str, Any]]:
    for line in a2ui.splitlines():
        message = json.loads(line)
        update_components = message.get("updateComponents")
        if not isinstance(update_components, dict):
            continue
        components = update_components.get("components")
        if isinstance(components, list):
            return components
    raise AssertionError("A2UI updateComponents message not found")


def _component_for_content(a2ui: str, expected_content: str) -> dict[str, Any]:
    for component in _a2ui_components(a2ui):
        if component.get("content") == expected_content:
            return component
    raise AssertionError(f"A2UI component not found for content: {expected_content}")


def _parent_component(a2ui: str, child: dict[str, Any]) -> dict[str, Any]:
    child_id = child.get("id")
    for component in _a2ui_components(a2ui):
        if child_id in component.get("children", []):
            return component
    raise AssertionError(f"A2UI parent component not found for child: {child_id}")


def _business_capsule(a2ui: str, descendant: dict[str, Any]) -> dict[str, Any]:
    current = descendant
    while True:
        current = _parent_component(a2ui, current)
        styles = current.get("styles", {})
        is_capsule = (
            current.get("component") == "Row"
            and styles.get("layoutWeight") == 1
            and styles.get("backgroundColor") is not None
            and styles.get("borderRadius") is not None
        )
        if is_capsule:
            return current


def _assert_equal_independent_business_capsules(
    a2ui: str,
    first_descendant: dict[str, Any],
    second_descendant: dict[str, Any],
) -> None:
    first_capsule = _business_capsule(a2ui, first_descendant)
    second_capsule = _business_capsule(a2ui, second_descendant)
    assert first_capsule.get("id") != second_capsule.get("id")

    first_styles = first_capsule.get("styles", {})
    second_styles = second_capsule.get("styles", {})
    assert first_styles.get("backgroundColor") == second_styles.get("backgroundColor")
    assert first_styles.get("borderRadius") == second_styles.get("borderRadius")

    content_region = _parent_component(a2ui, first_capsule)
    assert content_region.get("id") == _parent_component(a2ui, second_capsule).get("id")
    assert content_region.get("itemMargin") == 8


def _action_owner_before_capsule(
    a2ui: str,
    descendant: dict[str, Any],
) -> dict[str, Any] | None:
    capsule = _business_capsule(a2ui, descendant)
    current = descendant
    while current.get("id") != capsule.get("id"):
        if current.get("onClick"):
            return current
        current = _parent_component(a2ui, current)
    return None


def _assert_only_click_action_is_on(a2ui: str, expected_owner: dict[str, Any]) -> None:
    clickable = []
    for component in _a2ui_components(a2ui):
        if component.get("onClick"):
            clickable.append(component)
    assert len(clickable) == 1
    assert clickable[0].get("id") == expected_owner.get("id")
    on_click = clickable[0].get("onClick")
    assert isinstance(on_click, list)
    assert on_click[0].get("call") == "clickToDeeplink"


def _field(data_type: str, sample_value: object) -> dict[str, object]:
    return {
        "type": data_type,
        "description": "出行模板测试字段",
        "sampleValue": sample_value,
    }


_THERMOMETER_ASSET = {
    "src": "resources/base/media/icon_weather_thermometer.svg",
    "description": "样式：黑色的温度计图标；适用：天气温度、当前气温或温差变化。",
}

_TIMING_ASSET = {
    "src": "resources/base/media/icon_timing.svg",
    "description": "样式：秒表实心图标；适用：计时、倒计时或时限。",
}


def _daily_schema(index: int, fields: dict[str, dict[str, object]]) -> list[object]:
    daily: list[object] = []
    for _unused in range(index):
        daily.append({})
    daily.append(fields)
    return daily


def _bindings(
    weather_fields: tuple[str, ...],
    *,
    forecast_days: int,
) -> tuple[CandidateDataBinding, CandidateDataBinding]:
    return (
        CandidateDataBinding(
            capabilityId="GetCountdownDays",
            arguments={"targetDate": "2026-09-01"},
            writeResultTo="/data/countdown",
            candidateOutputFields=["/countdownDays"],
        ),
        CandidateDataBinding(
            capabilityId="ViewWeather",
            arguments={"prefectureName": "北京市", "forecastDays": forecast_days},
            writeResultTo="/data/weather",
            candidateOutputFields=list(weather_fields),
        ),
    )


def _card_spec(
    bindings: tuple[CandidateDataBinding, CandidateDataBinding],
    *,
    title: str = "出行天气",
) -> dict[str, Any]:
    data_bindings: list[dict[str, Any]] = []
    for binding in bindings:
        data_bindings.append(
            {
                "capabilityId": binding.capabilityId,
                "arguments": binding.arguments,
                "writeResultTo": binding.writeResultTo,
            }
        )
    return {
        "title": title,
        "description": "出发倒计时和目的地天气",
        "suggestSize": "2x2",
        "dataBindings": data_bindings,
    }


class _TravelTemplateModel:
    def __init__(
        self,
        required_weather_fields: tuple[str, ...],
        action_id: str | None,
        body: str,
    ) -> None:
        self.required_weather_fields = required_weather_fields
        self.action_id = action_id
        self.body = body

    async def generate_json(
        self,
        _prompt: list[dict[str, str]],
        **_kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "requiredOutputFieldsByCapability": {
                "GetCountdownDays": ["/countdownDays"],
                "ViewWeather": list(self.required_weather_fields),
            },
            "action": self.action_id,
        }

    async def generate(
        self,
        _prompt: list[dict[str, str]],
        *_args: Any,
        **_kwargs: Any,
    ) -> str:
        return self.body


@pytest.mark.asyncio
async def test_q008_uses_daily2_weather_support_with_countdown() -> None:
    weather_fields = (
        "/daily/2/condition",
        "/daily/2/temperatureRangeText",
    )
    bindings = _bindings(weather_fields, forecast_days=3)
    task_spec = TaskSpec(
        userQuery="显示出发倒计时和后日天气、温度范围",
        size="2x2",
        assetCandidates=[_TIMING_ASSET, _THERMOMETER_ASSET],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field("integer", 2)},
                "weather": {
                    "daily": _daily_schema(
                        2,
                        {
                            "condition": _field("string", "多云"),
                            "temperatureRangeText": _field("string", "25℃ / 32℃"),
                        },
                    )
                },
            }
        },
    )
    body = (
        'Template("TwoSupportLayout@1",{},'
        'Template("CountdownOverviewSupport@1",'
        '{"timerIcon":"resources/base/media/icon_timing.svg"}),'
        'Template("WeatherOverviewDaily2TravelSupport@1",'
        '{"conditionIcon":"resources/base/media/icon_weather_thermometer.svg"}));'
    )
    model = _TravelTemplateModel(weather_fields, None, body)

    output = await generate_template_a2ui(
        task_spec,
        _card_spec(bindings),
        bindings,
        model,
    )

    assert "WeatherOverviewDaily2TravelSupport@1" in output.template_ids
    assert "CountdownOverviewSupport@1" in output.template_ids
    assert "${/data/weather/daily/2/condition}" in output.a2ui
    assert "${/data/weather/daily/2/temperatureRangeText}" in output.a2ui
    assert output.a2ui.count('"backgroundColor":"#1A2E529E"') == 2
    assert "resources/base/media/icon_timing.svg" in output.a2ui
    assert "resources/base/media/icon_weather_thermometer.svg" in output.a2ui


@pytest.mark.asyncio
async def test_q026_binds_alarm_action_to_travel_capsule() -> None:
    weather_fields = (
        "/daily/4/condition",
        "/daily/4/temperatureRangeText",
        "/daily/4/rainProbabilityPercent",
    )
    bindings = _bindings(weather_fields, forecast_days=5)
    task_spec = TaskSpec(
        userQuery="显示倒计时和出发日天气，点击设置闹钟",
        size="2x2",
        assetCandidates=[_TIMING_ASSET, _THERMOMETER_ASSET],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field("integer", 4)},
                "weather": {
                    "daily": _daily_schema(
                        4,
                        {
                            "condition": _field("string", "小雨"),
                            "temperatureRangeText": _field("string", "20℃ / 28℃"),
                            "rainProbabilityPercent": _field("string", "60%"),
                        },
                    )
                },
            }
        },
        eventCandidates=[
            EventAction(
                id="event.open.clock.alarm",
                call="clickToDeeplink",
                args={
                    "intentName": "Clock",
                    "bundleName": "com.huawei.hmos.clock",
                    "abilityName": "com.huawei.hmos.clock.phone",
                    "uri": "",
                },
            )
        ],
    )
    body = (
        'Template("TwoSupportLayout@1",{},'
        'Template("CountdownOverviewTravelSupport@1",'
        '{"title":"西安出行","actionId":"event.open.clock.alarm",'
        '"timerIcon":"resources/base/media/icon_timing.svg"}),'
        'Template("WeatherOverviewTravelSupport@1",'
        '{"conditionIcon":"resources/base/media/icon_weather_thermometer.svg"}));'
    )
    model = _TravelTemplateModel(weather_fields, "event.open.clock.alarm", body)

    output = await generate_template_a2ui(
        task_spec,
        _card_spec(bindings, title="西安出行"),
        bindings,
        model,
    )

    assert "CountdownOverviewTravelSupport@1" in output.template_ids
    assert "WeatherOverviewTravelSupport@1" in output.template_ids
    assert "PillAction@1" not in output.template_ids
    assert "${/data/weather/daily/4/condition}" in output.a2ui
    assert "${/data/weather/daily/4/rainProbabilityPercent}" in output.a2ui
    assert "clickToDeeplink" in output.a2ui
    assert "resources/base/media/icon_timing.svg" in output.a2ui
    assert "resources/base/media/icon_weather_thermometer.svg" in output.a2ui
    condition = _component_for_content(
        output.a2ui,
        "{{ ${/data/weather/daily/4/condition} }}",
    )
    temperature = _component_for_content(
        output.a2ui,
        "{{ ${/data/weather/daily/4/temperatureRangeText} }}",
    )
    rain_probability = _component_for_content(
        output.a2ui,
        "{{ '降雨概率 ' + ${/data/weather/daily/4/rainProbabilityPercent} }}",
    )
    # 基底布局以温度范围为主行、天气现象与降雨概率为副行。
    assert temperature.get("styles", {}).get("fontSize") == 14
    assert temperature.get("styles", {}).get("fontWeight") == 700
    assert condition.get("styles", {}).get("fontSize") == 10
    assert rain_probability.get("styles", {}).get("fontSize") == 10
    travel_title = _component_for_content(output.a2ui, "西安出行")
    assert travel_title.get("styles", {}).get("fontSize") == 10
    assert _parent_component(output.a2ui, travel_title).get("itemMargin") == 3
    assert _parent_component(output.a2ui, temperature).get("itemMargin") == 3
    countdown = _component_for_content(
        output.a2ui,
        "{{ '剩余' + ${/data/countdown/countdownDays} + '天' }}",
    )
    assert countdown.get("styles", {}).get("fontSize") == 14
    _assert_equal_independent_business_capsules(
        output.a2ui,
        travel_title,
        condition,
    )
    travel_action = _action_owner_before_capsule(output.a2ui, travel_title)
    assert travel_action is not None
    assert travel_action.get("styles", {}).get("padding") == {"left": 8, "right": 8}
    assert _action_owner_before_capsule(output.a2ui, condition) is None
    _assert_only_click_action_is_on(output.a2ui, travel_action)


@pytest.mark.asyncio
async def test_q042_binds_weather_action_to_weather_capsule() -> None:
    weather_fields = ("/current/temperatureC", "/current/condition")
    bindings = _bindings(weather_fields, forecast_days=1)
    task_spec = TaskSpec(
        userQuery="显示出发倒计时和北京天气，点击查看天气详情",
        size="2x2",
        assetCandidates=[_TIMING_ASSET, _THERMOMETER_ASSET],
        dataModelSchema={
            "data": {
                "countdown": {"countdownDays": _field("integer", 79)},
                "weather": {
                    "current": {
                        "temperatureC": _field("number", 29),
                        "condition": _field("string", "多云"),
                    },
                    "location": {"cityCode": _field("string", "101010100")},
                },
            }
        },
        eventCandidates=[
            EventAction(
                id="event.open.weather",
                call="clickToDeeplink",
                args={
                    "intentName": "Weather_CityCode",
                    "bundleName": "",
                    "abilityName": "",
                    "uri": "{{ ${/data/weather/location/cityCode} }}",
                },
            )
        ],
    )
    # Planner 评分偏向主数据匹配的基础温度 Support，原子计划不包含出行天气组合。
    body = (
        'Template("TwoSupportLayout@1",{},'
        'Template("CountdownOverviewTravelSupport@1",'
        '{"title":"出差倒计时","timerIcon":"resources/base/media/icon_timing.svg"}),'
        'Template("WeatherOverviewTemperatureSupport@1",'
        '{"actionId":"event.open.weather",'
        '"conditionIcon":"resources/base/media/icon_weather_thermometer.svg"}));'
    )
    model = _TravelTemplateModel(weather_fields, "event.open.weather", body)

    output = await generate_template_a2ui(
        task_spec,
        _card_spec(bindings, title="出差倒计时"),
        bindings,
        model,
    )

    assert "CountdownOverviewTravelSupport@1" in output.template_ids
    assert "WeatherOverviewTemperatureSupport@1" in output.template_ids
    assert "PillAction@1" not in output.template_ids
    assert "${/data/weather/current/temperatureC}" in output.a2ui
    assert "${/data/weather/current/condition}" in output.a2ui
    assert "${/data/weather/location/cityCode}" in output.a2ui
    assert "resources/base/media/icon_timing.svg" in output.a2ui
    assert "resources/base/media/icon_weather_thermometer.svg" in output.a2ui
    condition = _component_for_content(
        output.a2ui,
        "{{ ${/data/weather/current/condition} }}",
    )
    temperature = _component_for_content(
        output.a2ui,
        "{{ ${/data/weather/current/temperatureC} + '℃' }}",
    )
    # 基础温度 Support 主行为城市与温度（14vp），天气现象为辅助行（12vp）。
    assert temperature.get("styles", {}).get("fontSize") == 14
    assert temperature.get("styles", {}).get("fontWeight") == 700
    assert condition.get("styles", {}).get("fontSize") == 12
    travel_title = _component_for_content(output.a2ui, "出差倒计时")
    assert travel_title.get("styles", {}).get("fontSize") == 10
    assert _parent_component(output.a2ui, travel_title).get("itemMargin") == 3
    assert _parent_component(output.a2ui, temperature).get("itemMargin") == 2
    countdown = _component_for_content(
        output.a2ui,
        "{{ '剩余' + ${/data/countdown/countdownDays} + '天' }}",
    )
    assert countdown.get("styles", {}).get("fontSize") == 14
    _assert_equal_independent_business_capsules(
        output.a2ui,
        travel_title,
        temperature,
    )
    assert _action_owner_before_capsule(output.a2ui, travel_title) is None
    weather_action = _action_owner_before_capsule(output.a2ui, temperature)
    assert weather_action is not None
    expected_padding = {"left": 8, "right": 8, "top": 0, "bottom": 0}
    assert weather_action.get("styles", {}).get("padding") == expected_padding
    _assert_only_click_action_is_on(output.a2ui, weather_action)
