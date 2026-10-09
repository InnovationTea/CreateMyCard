# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from services.multi_step_generation.jsx_runner.data_processing import (
    _format_binding_value,
    prepare_task,
)


def test_weather_rain_probability_uses_percent_display_unit_without_changing_value():
    binding_id = "weather.daily.4.rainProbabilityPercent"

    assert _format_binding_value(binding_id, 60) == ("60%", True)
    assert _format_binding_value(binding_id, "60%") == ("60%", False)

    prepared = prepare_task(
        {
            "id": "weather-rain",
            "size": "2x2",
            "data": [
                {
                    "id": binding_id,
                    "path": "/data/weather/daily/4/rainProbabilityPercent",
                    "type": "number",
                    "description": "白天降雨概率数值",
                    "value": 60,
                }
            ],
        }
    )

    prompt_item = prepared.prompt_task["data"][0]
    assert prompt_item["type"] == "number"
    assert prompt_item["value"] == 60
    assert "unit=“%”" in prompt_item["description"]
