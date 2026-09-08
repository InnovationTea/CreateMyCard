"""天气标题的可选数据、编译期分支与左右布局契约。"""

from __future__ import annotations

from typing import Any

import pytest

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.registry import get_cardplan_registry


def test_weather_hero_title_has_no_required_weather_value() -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewHeroTitle@1")
    assert definition.primary_data == ()
    assert definition.secondary_data == ()
    assert definition.optional_data == (
        "/location/prefectureName",
        "/location/districtName",
        "/current/temperatureText",
        "/current/condition",
    )
    variant = definition.variants[0]
    assert variant.required_bindings == ()
    assert variant.optional_bindings == ("city", "district", "temperature", "condition")


@pytest.mark.parametrize(
    ("location_bindings", "props", "expected_location"),
    [
        (
            {
                "city": "${data.weather.location.prefectureName}",
                "district": "${data.weather.location.districtName}",
            },
            {"location": "受信兜底"},
            "${data.weather.location.prefectureName}",
        ),
        (
            {"district": "${data.weather.location.districtName}"},
            {"location": "受信兜底"},
            "${data.weather.location.districtName}",
        ),
        ({}, {"location": "受信兜底"}, "受信兜底"),
        ({}, {}, "当前城市"),
    ],
)
@pytest.mark.parametrize(
    ("weather_names", "expected_weather"),
    [
        (
            ("condition", "temperature"),
            "{{ ${/data/weather/current/condition} + ' | ' + "
            "${/data/weather/current/temperatureText} }}",
        ),
        (("condition",), "${data.weather.current.condition}"),
        (("temperature",), "${data.weather.current.temperatureText}"),
        ((), None),
    ],
)
def test_weather_hero_title_keeps_optional_branches_and_left_right_layout(
    location_bindings: dict[str, str],
    props: dict[str, str],
    expected_location: str,
    weather_names: tuple[str, ...],
    expected_weather: str | None,
) -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewHeroTitle@1")
    bindings = dict(location_bindings)
    weather_bindings = {
        "temperature": "${data.weather.current.temperatureText}",
        "condition": "${data.weather.current.condition}",
    }
    for name in weather_names:
        binding = weather_bindings.get(name)
        assert binding is not None
        bindings[name] = binding
    root = _instantiate_blueprint(
        definition.variants[0].root, props, bindings, {"primaryColor": "#FF1F4799"}
    )
    assert root.component_type == "Row"
    options: Any = root.values[-1]
    assert isinstance(options, dict)
    assert options.get("_advancedComponent") == "WeatherOverview"
    assert options.get("height") == 24
    assert options.get("itemMargin") == 4
    assert options.get("justifyContent") == "spaceBetween"
    assert options.get("alignItems") == "top"
    assert options.get("clip") is True
    assert all(child.component_type == "Text" for child in root.children)
    expected_texts = [expected_location]
    if expected_weather is not None:
        expected_texts.append(expected_weather)
    assert [child.values[0] for child in root.children] == expected_texts
    city_options: Any = root.children[0].values[-1]
    assert city_options.get("maxLines") == 1
    assert city_options.get("textOverflow") == "ellipsis"
    for child in root.children:
        assert child.values[-1].get("fontSize") == 14
        assert child.values[-1].get("fontColor") == "#FF1F4799"
    if expected_weather is not None:
        assert root.children[1].values[-1].get("flexShrink") == 0
