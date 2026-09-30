"""出行倒计时与目的地天气模板回归。

三个出行场景已固化为场景金样（Layer C）：Q008 倒计时 + 后日天气双
Support、Q026 闹钟动作挂在倒计时胶囊、Q042 天气动作挂在天气胶囊。完整
A2UI 产物由快照整体冻结：独立业务胶囊的等价样式、全卡唯一可点击组件
及其归属与 padding、字号/字重层级、图标有无、PillAction 缺省。引擎或
模板改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

import asyncio
from typing import Any

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.test_support.golden_scenarios import (
    a2ui_messages,
    assert_golden_scenario,
    scenario,
)


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


async def _render_q008_daily2_support() -> dict[str, Any]:
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
    return a2ui_messages(output)


async def _render_q026_alarm_on_countdown_capsule() -> dict[str, Any]:
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
        '{"title":"西安出行","actionId":"event.open.clock.alarm"}),'
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
    return a2ui_messages(output)


async def _render_q042_weather_action_capsule() -> dict[str, Any]:
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
        '{"title":"出差倒计时"}),'
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
    return a2ui_messages(output)


@scenario("travel_weather__q008_daily2_support")
def _build_q008_daily2_support() -> dict:
    return asyncio.run(_render_q008_daily2_support())


@scenario("travel_weather__q026_alarm_on_countdown_capsule")
def _build_q026_alarm_on_countdown_capsule() -> dict:
    return asyncio.run(_render_q026_alarm_on_countdown_capsule())


@scenario("travel_weather__q042_weather_action_capsule")
def _build_q042_weather_action_capsule() -> dict:
    return asyncio.run(_render_q042_weather_action_capsule())


def test_q008_uses_daily2_weather_support_with_countdown() -> None:
    assert_golden_scenario("travel_weather__q008_daily2_support")


def test_q026_binds_alarm_action_to_travel_capsule() -> None:
    assert_golden_scenario("travel_weather__q026_alarm_on_countdown_capsule")


def test_q042_binds_weather_action_to_weather_capsule() -> None:
    assert_golden_scenario("travel_weather__q042_weather_action_capsule")
