"""天气分隔符与运动健康紧凑模板的绑定、图标及排版回归。"""

import pytest

from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.tersel_converter import Nested2Node


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _nodes(root: Nested2Node, kind: str) -> list[Nested2Node]:
    result = [root] if root.component_type == kind else []
    for child in root.children:
        result.extend(_nodes(child, kind))
    return result


@pytest.mark.parametrize("with_icon", (False, True))
@pytest.mark.parametrize("template_id", (
    "HeartRateOverviewCompact@1", "SleepOverviewCompact@1",
    "SleepOverviewScoreCompact@1", "WorkoutOverviewTypeDurationCompact@1",
))
def test_health_compact_typography_and_optional_icon(
    registry: CardPlanRegistry, template_id: str, with_icon: bool,
) -> None:
    definition = registry.require_template(template_id)
    bindings = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.healthSport." + binding.path.removeprefix("/") + "}"
    params = {}
    has_icon = with_icon and template_id != "HeartRateOverviewCompact@1"
    if has_icon:
        params["sourceIcon"] = "resources/base/media/fixture.svg"
    root = _instantiate_blueprint(
        definition.variants[0].root, params, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    text = _serialize_node(root)
    for expression in bindings.values():
        assert expression in text
    assert "onClick" not in text
    images = _nodes(root, "Image")
    assert len(images) == int(has_icon)
    texts = _nodes(root, "Text")
    if template_id == "HeartRateOverviewCompact@1":
        assert root.values[-1].get("justifyContent") == "center"
        assert [node.values[-1].get("fontSize") for node in texts] == [12, 20, 12]
        return
    assert [node.values[-1].get("fontSize") for node in texts] == [16, 12]
    if template_id == "SleepOverviewCompact@1":
        assert "height" not in texts[0].values[-1]
        assert root.children[0].values[-1].get("justifyContent") == "spaceBetween"
        icon_size = 20
    elif template_id == "SleepOverviewScoreCompact@1":
        ring = _nodes(root, "Progress")[0].values[-1]
        assert ring.get("width") == ring.get("height") == 36
        assert ring.get("strokeWidth") == 4
        assert ring.get("total") == 100
        assert "sleepScore" in str(ring.get("value"))
        stack = _nodes(root, "Stack")[0].values[-1]
        assert stack.get("width") == stack.get("height") == 36
        icon_size = 16
    else:
        assert root.values[-1].get("itemMargin") == 2
        assert root.values[-1].get("justifyContent") == "spaceBetween"
        assert root.children[0].values[-1].get("itemMargin") == 2
        assert [node.values[-1].get("height") for node in texts] == [20, 16]
        icon_size = 24
    if images:
        styles = images[0].values[-1]
        assert styles.get("width") == styles.get("height") == icon_size


@pytest.mark.parametrize(("suffix", "metric", "label"), (
    ("Humidity", "humidity", "湿度"), ("AirQuality", "airQuality", "空气质量"),
))
def test_weather_separator_preserves_spaces_and_metric_binding(
    registry: CardPlanRegistry, suffix: str, metric: str, label: str,
) -> None:
    definition = registry.require_template(f"WeatherOverviewTemperature{suffix}Support@1")
    bindings = {
        "temperature": "${data.weather.temperatureText}",
        "condition": "${data.weather.condition}",
        metric: "${data.weather." + metric + "}",
    }
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    text = _serialize_node(root)
    assert " | " + label in text
    assert "/data/weather/condition" in text
    assert "/data/weather/" + metric in text
    if suffix == "Humidity":
        assert "%" in text


def test_weather_health_previews_use_device_supported_alignments() -> None:
    checked = 0
    for case in build_template_preview_cases():
        if case.provider_id not in {"com.huawei.weather.cli", "com.huawei.health-sport.cli"}:
            continue
        checked += 1
        for message in case.messages:
            for component in message.get("updateComponents", {}).get("components", []):
                styles = component.get("styles", {})
                assert styles.get("textAlign") not in {"left", "right"}, case.template_id
                if component.get("component") == "Row":
                    assert styles.get("alignItems") not in {"start", "end"}, case.template_id
    assert checked == 92


@pytest.mark.parametrize("feels_like", (False, True))
@pytest.mark.parametrize("cold_level", (False, True))
@pytest.mark.parametrize("air_quality", (False, True))
def test_weather_hero_preserves_optional_metrics(
    registry: CardPlanRegistry, feels_like: bool, cold_level: bool, air_quality: bool,
) -> None:
    definition = registry.require_template("WeatherOverviewHero@1")
    bindings = {
        "temperature": "${data.weather.current.temperatureText}",
        "condition": "${data.weather.current.condition}",
    }
    optional = (
        (feels_like, "feelsLike", "feelsLikeC"),
        (cold_level, "coldLevel", "coldLevel"),
        (air_quality, "airQuality", "airQuality"),
    )
    for present, name, path in optional:
        if present:
            bindings[name] = "${data.weather.current." + path + "}"
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    text = _serialize_node(root)
    text = text.replace("data.weather.current.", "/data/weather/current/")
    assert "/data/weather/current/temperatureText" in text
    assert "/data/weather/current/condition" in text
    for present, _name, path in optional:
        assert ("/data/weather/current/" + path in text) == present
    assert ("感冒风险" in text) == cold_level
