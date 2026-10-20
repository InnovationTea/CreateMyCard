"""画廊受控输入的版本、素材和完整组合合同。"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

THREE_DAY_WEATHER_TEMPLATE = "WeatherOverviewThreeDayForecastFull@1"
THREE_DAY_COUNTDOWN_TEMPLATE = "CountdownOverviewEventHero@1"
THREE_DAY_LAYOUT = "WideHeroActionFullLayout"

CURRENT_TIME_SAMPLE_VALUES = {
    "/currentDate": "2026-10-20",
    "/dayOfWeek": "星期二",
    "/updatedAt": "2026-10-20 10:00:00",
}

REQUIRED_ASSET_IDS = {
    "BatteryOverviewSupportHero@1": ("asset.battery_leaf_fill",),
    "BatteryOverviewChargeStatusHero@1": ("asset.battery_leaf_fill",),
    "BluetoothDeviceOverviewEarphoneCaseHero@1": ("asset.earphone_case_16644",),
    "BluetoothDeviceOverviewEarphoneHero@1": ("asset.icon_earphone",),
    "BluetoothDeviceOverviewCaseConnectionHero@1": ("asset.earphone_case_16644",),
    "BluetoothDeviceOverviewMusicFull@1": ("asset.earphone_case_16644",),
}


def gallery_display_description(description: str) -> str:
    """只移除样例中的实现说明，不处理真实用户输入。"""
    description = re.sub(r"仅用于旧匹配失败后[^。]*。?", "", description)
    return description.replace("不代表逐条展示所有日程", "仅展示首项日程摘要")


def three_day_weather_content(
    content: dict[str, Any],
    weather_event: dict[str, Any],
    countdown_arguments: dict[str, Any],
) -> dict[str, Any]:
    """三日 Full 是宽卡内容槽，复用已支持的倒计时与天气操作组合。"""
    result = deepcopy(content)
    bindings = result.get("candidateDataBindings")
    if not isinstance(bindings, list):
        raise ValueError("three-day gallery requires weather candidate bindings")
    weather_binding: dict[str, Any] | None = None
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("capabilityId") == "ViewWeather":
            weather_binding = binding
            break
    if weather_binding is None:
        raise ValueError("three-day gallery requires ViewWeather")
    arguments = weather_binding.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("three-day weather arguments must be an object")
    arguments["forecastDays"] = 3
    bindings.append({
        "capabilityId": "GetCountdownDays",
        "writeResultTo": "/data/countdown",
        "candidateOutputFields": ["/countdownDays"],
        "arguments": deepcopy(countdown_arguments),
    })
    result.update({
        "size": "2x4",
        "candidateEventCandidates": [deepcopy(weather_event)],
        "userQuery": (
            "生成一个2×4卡片，显示返乡倒计时和未来三天天气。"
            "每天展示完整日期、星期、天气现象、温度范围和降雨概率，"
            "提供查看天气详情按钮。"
        ),
    })
    return result
