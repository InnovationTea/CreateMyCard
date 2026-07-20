# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""A2UI 卡片校验 API 的兼容适配层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.card_validation import validate_card as validate_card_api
from services.card_validation.diagnostics import Diagnostic


@dataclass(frozen=True)
class CardValidationReport:
    """兼容原有调用方的字符串校验结果。"""

    errors: list[str]
    warnings: list[str]

    def passed(self, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)


def validate_card(
    genui_text: str,
    cardspec: dict[str, Any] | str,
    strict: bool = False,
    allowed_asset_sources: set[str] | None = None,
) -> CardValidationReport:
    """通过服务内 API 校验 genui 和 CardSpec，不执行校验脚本或子进程。"""
    effective_capabilities = None
    if allowed_asset_sources is not None:
        effective_capabilities = {
            "data": [],
            "event": [],
            "asset": [{"src": source} for source in sorted(allowed_asset_sources)],
        }
    reporter = validate_card_api(
        dsl_text=genui_text,
        cardspec=cardspec,
        effective_capabilities=effective_capabilities,
    )
    errors = [_format_diagnostic(item) for item in reporter.diagnostics if item.severity == "error"]
    warnings = [
        _format_diagnostic(item) for item in reporter.diagnostics if item.severity == "warning"
    ]
    if strict:
        errors.extend(warnings)
    return CardValidationReport(errors=errors, warnings=warnings)


def _format_diagnostic(diagnostic: Diagnostic) -> str:
    location = diagnostic.file_kind
    if diagnostic.line is not None:
        location += f":{diagnostic.line}"
    if diagnostic.json_pointer:
        location += f" {diagnostic.json_pointer}"
    return f"{diagnostic.code}: {diagnostic.message} [{location}]"


if __name__ == '__main__':
    genui_text = """
    {"version":"v0.9","createSurface":{"surfaceId":"dali_weather_card","catalogId":"ohos.a2ui.extended.catalog.form","width":140,"height":140}}
    {"version":"v0.9","updateComponents":{"surfaceId":"dali_weather_card","root":"root","components":[{"id":"root","component":"Column","children":["header_row","hero_row","bottom_row"],"itemMargin":6,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#86C5E3",0],["#F9bc64",1]]},"justifyContent":"start","alignItems":"start"}},{"id":"header_row","component":"Row","children":["title_text","location_text"],"itemMargin":4,"styles":{"width":116,"height":18,"justifyContent":"start","alignItems":"center"}},{"id":"title_text","component":"Text","content":"大理天气","styles":{"width":58,"fontSize":14,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"none"}},{"id":"location_text","component":"Text","content":"云南大理","styles":{"width":54,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textOverflow":"none","textAlign":"end"}},{"id":"hero_row","component":"Row","children":["weather_icon","primary_info"],"itemMargin":6,"styles":{"width":116,"height":48,"justifyContent":"start","alignItems":"center"}},{"id":"weather_icon","component":"Image","src":"{{ ${/asset/weather_icon} }}","styles":{"width":42,"height":42,"objectFit":"contain","flexShrink":0}},{"id":"primary_info","component":"Column","children":["primary_value","primary_caption"],"itemMargin":0,"styles":{"width":68,"height":48,"justifyContent":"center","alignItems":"start"}},{"id":"primary_value","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}","styles":{"width":68,"fontSize":35,"fontWeight":700,"fontColor":"#E5000000","maxLines":1,"textOverflow":"none"}},{"id":"primary_caption","component":"Text","content":"{{ ${/data/weather/current/condition} }}","styles":{"width":68,"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textOverflow":"none"}},{"id":"bottom_row","component":"Row","children":["support_card","action_button"],"itemMargin":4,"styles":{"width":116,"height":38,"justifyContent":"start","alignItems":"center"}},{"id":"support_card","component":"Column","children":["humidity_row","wind_text"],"itemMargin":2,"styles":{"width":60,"height":38,"padding":{"top":4,"right":6,"bottom":4,"left":6},"backgroundColor":"#FFFFFFFF","borderRadius":12,"justifyContent":"center","alignItems":"start"}},{"id":"humidity_row","component":"Row","children":["humidity_icon","humidity_value"],"itemMargin":4,"styles":{"width":48,"height":14,"justifyContent":"start","alignItems":"center"}},{"id":"humidity_icon","component":"Image","src":"{{ ${/asset/humidity_icon} }}","styles":{"width":12,"height":12,"objectFit":"contain","flexShrink":0}},{"id":"humidity_value","component":"Text","content":"{{ ${/data/weather/current/humidityPercent} + '%' }}","styles":{"width":32,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","maxLines":1,"textOverflow":"none"}},{"id":"wind_text","component":"Text","content":"{{ ${/data/weather/current/windDirection} + ${/data/weather/current/windLevel} + '级' }}","styles":{"width":48,"fontSize":10,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textOverflow":"none"}},{"id":"action_button","component":"Button","label":"天气","onClick":[{"call":"clickToDeeplink","args":{"bundleName":"","abilityName":"","intentName":"Weather_CityCode","uri":"hww://www.huawei.com/totemweather?enterType=share&cityCode="}}],"styles":{"width":52,"height":32,"fontSize":12,"fontWeight":600,"fontColor":"#E5000000","backgroundColor":"#FFFFFFFF","borderRadius":16}}]}}
    {"version":"v0.9","updateDataModel":{"surfaceId":"dali_weather_card","path":"/","value":{"asset":{"weather_icon":"resources/base/media/partly_cloudy.png","humidity_icon":"resources/base/media/drop_1.svg"},"data":{"weather":{"current":{"temperatureText":"26℃","condition":"多云","humidityPercent":68,"windDirection":"东南风","windLevel":2,"airQuality":"优"},"location":{"districtName":"大理","prefectureName":"云南"},"daily":[{"date":"2026-07-15","condition":"多云","temperatureRangeText":"24℃ / 31℃"}]}},"state":{"loading":false}}}}
    """
    cardspec = {
        "title": "大理天气",
        "description": "大理天气速览",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {
                    "districtName": "大理市",
                    "forecastDays": 3,
                    "prefectureName": "大理白族自治州"
                },
                "writeResultTo": "/data/weather"
            }
        ]
    }
    result = validate_card(genui_text, cardspec)
