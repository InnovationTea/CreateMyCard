"""天气模板的日期语义、实际绑定和展示标签回归。"""

import re

import pytest
from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.registry import get_cardplan_registry


def _runtime_paths(rendered: str) -> set[str]:
    """编译中间树同时包含点式绑定与已归一化的表达式引用。"""
    paths = set()
    for reference in re.findall(r"\$\{([^}]+)\}", rendered):
        paths.add("/" + reference.strip("/").replace(".", "/"))
    return paths


@pytest.mark.parametrize(
    "template_id",
    (
        "WeatherOverviewDailyDateFull@1",
        "WeatherOverviewDailyRainFull@1",
        "WeatherOverviewDailyHealthFull@1",
        "WeatherOverviewDailyConditionWeekdayFull@1",
        "WeatherOverviewNextDayHealthFull@1",
        "WeatherOverviewDailyUvColdFull@1",
    ),
)
def test_tomorrow_templates_compile_only_first_forecast_item(template_id):
    registry = get_cardplan_registry()
    definition = registry.require_template(template_id)
    declared_paths = (*definition.required_data, *definition.optional_data)
    forecast_paths = []
    for path in declared_paths:
        if path.startswith("/daily/"):
            forecast_paths.append(path)
    assert forecast_paths
    for path in forecast_paths:
        assert path.startswith("/daily/0/")

    bindings = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.weather" + binding.path.replace("/", ".") + "}"
        if binding.path.startswith("/daily/"):
            assert binding.path.startswith("/daily/0/")
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    rendered = repr(root)
    paths = _runtime_paths(rendered)
    assert any(path.startswith("/data/weather/daily/0/") for path in paths)
    assert not any(path.startswith("/data/weather/daily/1/") for path in paths)
    assert "今日" not in rendered


def test_two_day_comparison_compiles_tomorrow_and_day_after_labels():
    registry = get_cardplan_registry()
    definition = registry.require_template("WeatherOverviewDailyCompareFull@1")
    bindings = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.weather" + binding.path.replace("/", ".") + "}"
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    rendered = repr(root)
    paths = _runtime_paths(rendered)
    assert "/data/weather/daily/0/condition" in paths
    assert "/data/weather/daily/1/condition" in paths
    assert "明天" in rendered
    assert "后天" in rendered
    assert "今天" not in rendered


@pytest.mark.parametrize("template_id", ("WeatherOverviewFull@1", "WeatherOverviewWideFull@1"))
def test_current_weather_with_first_forecast_labels_range_as_tomorrow(template_id):
    registry = get_cardplan_registry()
    definition = registry.require_template(template_id)
    bindings = {}
    for name, binding in definition.bindings.items():
        bindings[name] = "${data.weather" + binding.path.replace("/", ".") + "}"
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    rendered = repr(root)
    paths = _runtime_paths(rendered)
    assert "/data/weather/current/temperatureText" in paths
    assert "/data/weather/daily/0/temperatureRangeText" in paths
    assert "明日" in rendered
    assert "今日" not in rendered
