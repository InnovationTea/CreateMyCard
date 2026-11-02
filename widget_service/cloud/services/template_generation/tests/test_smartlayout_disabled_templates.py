"""关闭端侧布局优化后暴露的字段丢失与槽位分配回归。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node


def _expanded(template_id: str, omitted: tuple[str, ...] = ()) -> Nested2Node:
    definition = get_cardplan_registry().require_template(template_id)
    bindings: dict[str, str] = {}
    for name in definition.bindings:
        if name not in omitted:
            bindings[name] = "${data.sample." + name + "}"
    return _instantiate_blueprint(
        definition.variants[0].root,
        {"deviceIcon": "resources/base/media/earphone_case_16644.svg"},
        bindings,
        {
            "primaryColor": "#FF000000",
            "supportContentColor": "#FF333333",
            "progressColor": "#FF00AA00",
            "progressBackgroundColor": "#22000000",
        },
    )


def _serialized(node: Nested2Node) -> str:
    return _serialize_node(node).replace("data.sample.", "/data/sample/")


def _nodes(root: Nested2Node) -> list[Nested2Node]:
    result = [root]
    for child in root.children:
        result.extend(_nodes(child))
    return result


def _style(node: Nested2Node) -> dict:
    result: dict = {}
    for value in node.values:
        if isinstance(value, dict):
            result.update(value)
    return result


@pytest.mark.parametrize("omitted", [(), ("workoutCalories",)])
def test_workout_heart_rate_keeps_value_and_unit_in_both_branches(omitted: tuple[str, ...]):
    source = _serialized(_expanded("WorkoutOverviewHero@1", omitted))
    assert "/data/sample/heartRateAvg" in source
    assert "次/分" in source
    assert "/data/sample/duration" in source


@pytest.mark.parametrize("omitted", [(), ("alertLevel",)])
def test_weather_full_wind_does_not_depend_on_alert(omitted: tuple[str, ...]):
    source = _serialized(_expanded("WeatherOverviewHumidityWindLevelFull@1", omitted))
    for name in ("temperature", "humidity", "windDirection", "windLevel"):
        assert "/data/sample/" + name in source


@pytest.mark.parametrize("template_id", [
    "CurrentTimeOverviewUpdatedFull@1", "CurrentTimeOverviewSupport@1",
    "BluetoothDeviceOverviewMusicFull@1",
])
def test_complete_timestamp_can_wrap(template_id: str):
    timestamp_nodes = []
    for node in _nodes(_expanded(template_id)):
        if node.component_type == "Text" and "/data/sample/updated" in _serialized(node):
            timestamp_nodes.append(node)
    assert len(timestamp_nodes) == 1
    style = _style(timestamp_nodes[0])
    assert style.get("maxLines") == 2
    assert style.get("width") == "matchParent"
    assert style.get("fontSize", 0) >= 12


@pytest.mark.parametrize("template_id", [
    "BatteryOverviewSupport@1", "BluetoothDeviceOverviewChargeSupport@1",
])
def test_support_text_uses_remaining_width_and_ring_stays_fixed(template_id: str):
    nodes = _nodes(_expanded(template_id))
    text_columns = []
    rings = []
    for node in nodes:
        if node.component_type == "Column":
            text_columns.append(node)
        if node.component_type == "Stack":
            rings.append(node)
    assert len(text_columns) == 1
    assert _style(text_columns[0]).get("layoutWeight") == 1
    assert len(rings) == 1
    assert _style(rings[0]).get("width") == 40
    assert _style(rings[0]).get("flexShrink") == 0
    source = _serialized(text_columns[0])
    assert "/data/sample/percent" in source
    assert "%" in source
    assert "电量 " not in source


def test_weather_hero_all_optional_rows_fit_reference_slot():
    root = _expanded("WeatherOverviewHero@1")
    source = _serialized(root)
    names = ("city", "temperature", "feelsLike", "coldLevel", "condition",
             "airQuality", "alertLevel", "windLevel")
    for name in names:
        assert "/data/sample/" + name in source
    assert len(root.children) == 4
    heights = []
    for child in root.children:
        height = _style(child).get("height")
        assert isinstance(height, int)
        heights.append(height)
    assert sum(heights) + 2 * (len(heights) - 1) <= 82


def test_schedule_all_fields_fit_reference_content_slot():
    root = _expanded("ScheduleOverviewTitleHero@1")
    source = _serialized(root)
    for name in ("date", "title", "start", "end", "countdown"):
        assert "/data/sample/" + name in source
    heights = []
    for child in root.children:
        height = _style(child).get("height")
        assert isinstance(height, int)
        heights.append(height)
    # 显式开发参考预算；不声称云侧知道真实宿主尺寸，也不替代真机截图。
    assert sum(heights) + (len(heights) - 1) * _style(root).get("itemMargin", 0) <= 74


def test_activity_wide_hero_keeps_all_four_facts():
    source = _serialized(_expanded("ActivityOverviewWideHero@1"))
    for name in ("steps", "calories", "distance", "targetDate"):
        assert "/data/sample/" + name in source
    get_cardplan_registry().require_template("ActivityOverviewWideFull@1")


def test_all_source_template_identifiers_are_unique():
    source_root = Path(__file__).resolve().parents[1] / "resources/source/providers"
    seen: set[str] = set()
    for path in source_root.rglob("*.cardtpl"):
        for template_id in re.findall(r"^#Template\s+(\S+)\(", path.read_text(), re.MULTILINE):
            assert template_id not in seen, (path, template_id)
            seen.add(template_id)


def test_time_support_does_not_advertise_removed_optional_fields():
    definition = get_cardplan_registry().require_template("CurrentTimeOverviewSupport@1")
    assert definition.required_data == ("/updatedAt",)
    assert definition.optional_data == ()


@pytest.mark.parametrize("template_id", [
    "WeatherOverviewTravelSupport@1", "WeatherOverviewFeelsLikeWindSupport@1",
])
def test_text_only_weather_support_has_no_image_slot(template_id: str):
    definition = get_cardplan_registry().require_template(template_id)
    assert not definition.asset_parameter_semantic_tags
    assert all(node.component_type != "Image" for node in _nodes(_expanded(template_id)))
