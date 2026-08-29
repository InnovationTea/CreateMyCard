"""天气标题的数据分层、可选分支矩阵与紧凑布局契约（场景金样化）。

两类确定性契约已固化为场景金样（Layer C）：

- ``weather_hero__data_tiers``：WeatherOverviewHeroTitle@1 的注册元数据
  （primary/secondary/optional 数据分层，首个变体的必需/可选绑定名）；
- ``weather_hero__optional_selection``：location 绑定（城市+区县 / 仅区县 /
  仅 props 兜底 / 全缺省）× 天气绑定（双字段 / 仅天气 / 仅温度 / 无）
  共 16 个组合的解析矩阵——每组合冻结 Row 的完整 options（
  _advancedComponent、height 18、itemMargin、justifyContent、alignItems、
  clip）与每个 Text 子节点的文本和样式（fontSize 12、主题字色、
  maxLines/ellipsis、天气文本 flexShrink 0）。

原有内联断言全部迁入金样，本文件仅保留注册与金样比对入口；引擎或模板
改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

from typing import Any

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_TEMPLATE_ID = "WeatherOverviewHeroTitle@1"
_THEME_VALUES = {"supportContentColor": "#991F4799"}

_LOCATION_CASES: tuple[tuple[str, dict[str, str], dict[str, str]], ...] = (
    (
        "city_district",
        {
            "city": "${data.weather.location.prefectureName}",
            "district": "${data.weather.location.districtName}",
        },
        {"location": "受信兜底"},
    ),
    (
        "district_only",
        {"district": "${data.weather.location.districtName}"},
        {"location": "受信兜底"},
    ),
    ("props_fallback", {}, {"location": "受信兜底"}),
    ("default_text", {}, {}),
)

_WEATHER_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("both", ("condition", "temperature")),
    ("condition", ("condition",)),
    ("temperature", ("temperature",)),
    ("none", ()),
)


@scenario("weather_hero__data_tiers")
def _build_data_tiers() -> dict[str, Any]:
    definition = get_cardplan_registry().require_template(_TEMPLATE_ID)
    variant = definition.variants[0]
    return {
        "primaryData": list(definition.primary_data),
        "secondaryData": list(definition.secondary_data),
        "optionalData": list(definition.optional_data),
        "variant": {
            "requiredBindings": list(variant.required_bindings),
            "optionalBindings": list(variant.optional_bindings),
        },
    }


def _resolved_row(
    location_bindings: dict[str, str],
    props: dict[str, str],
    weather_names: tuple[str, ...],
) -> dict[str, Any]:
    definition = get_cardplan_registry().require_template(_TEMPLATE_ID)
    bindings = dict(location_bindings)
    weather_bindings = {
        "temperature": "${data.weather.current.temperatureText}",
        "condition": "${data.weather.current.condition}",
    }
    for name in weather_names:
        bindings[name] = weather_bindings[name]
    root = _instantiate_blueprint(
        definition.variants[0].root,
        props,
        bindings,
        _THEME_VALUES,
    )
    return {
        "rowOptions": dict(root.values[-1]),
        "children": [
            {"text": child.values[0], "options": dict(child.values[-1])}
            for child in root.children
        ],
    }


@scenario("weather_hero__optional_selection")
def _build_optional_selection() -> dict[str, Any]:
    return {
        f"loc_{location_key}__weather_{weather_key}": _resolved_row(
            location_bindings, props, weather_names,
        )
        for location_key, location_bindings, props in _LOCATION_CASES
        for weather_key, weather_names in _WEATHER_CASES
    }


def test_weather_hero_title_scenarios_match_goldens() -> None:
    assert_golden_scenario("weather_hero__data_tiers")
    assert_golden_scenario("weather_hero__optional_selection")
