"""检查全量正式模板的业务标记及其编译期内容保护边界。"""

from __future__ import annotations

from pathlib import Path

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _deduplicate_visible_text,
    _instantiate_blueprint,
    _is_advanced_component_region,
    _serialize_node,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.models import TemplateNode, TemplateValue
from services.template_generation.engine.cardplan.provider_bundle import (
    load_provider_bundle,
    provider_template_family_identity,
)
from services.template_generation.engine.tersel_converter import Nested2Node

_PROVIDERS_ROOT = Path(__file__).resolve().parents[1] / "resources/source/providers"
_PROVIDER_DIRECTORIES = tuple(
    path.parent for path in sorted(_PROVIDERS_ROOT.glob("*/provider.json"))
)
_SHAPE_SPECIFIC_MARKERS = {
    "WeatherOverviewTemperatureSupport@1": "WeatherOverviewTemperatureSupport",
    "WeatherOverviewTemperatureUvSupport@1": "WeatherOverviewTemperatureSupport",
}


def _marker_values(root: TemplateNode) -> list[TemplateValue]:
    markers: list[TemplateValue] = []
    for value in root.values:
        marker = value.properties.get("_advancedComponent")
        if marker is not None:
            markers.append(marker)
    for child in root.children:
        markers.extend(_marker_values(child))
    return markers


@pytest.mark.parametrize("provider_root", _PROVIDER_DIRECTORIES, ids=lambda path: path.name)
def test_all_formal_templates_declare_only_their_business_markers(provider_root: Path) -> None:
    bundle = load_provider_bundle(provider_root)
    for definition in bundle.templates:
        for variant in definition.variants:
            markers = _marker_values(variant.root)
            if definition.capability_id is None:
                assert not markers, f"布局和动作模板不能声明业务标记：{definition.wire_id}"
                continue
            identity = provider_template_family_identity(definition.wire_id)
            assert identity is not None, definition.wire_id
            family = identity[0].partition("@")[0]
            expected = _SHAPE_SPECIFIC_MARKERS.get(definition.wire_id, family)
            assert markers, f"业务模板缺少 _advancedComponent：{definition.wire_id}"
            for marker in markers:
                assert marker.kind == "literal", definition.wire_id
                assert marker.value == expected, definition.wire_id


@pytest.mark.parametrize("with_action", (False, True))
def test_earbuds_support_marker_protects_content_and_is_stripped(with_action: bool) -> None:
    bundle = load_provider_bundle(_PROVIDERS_ROOT / "earphone")
    template_id = "BluetoothDeviceOverviewEarbudsSupport@1"
    definition = next(item for item in bundle.templates if item.wire_id == template_id)
    params = {"deviceIcon": "resources/base/media/earphone.svg"}
    if with_action:
        params["actionId"] = "event.openBluetooth"
    region = _instantiate_blueprint(
        definition.variants[0].root,
        params,
        bindings={
            "left": "${data.earphone.leftBatteryLevel}",
            "right": "${data.earphone.rightBatteryLevel}",
        },
        theme_values={"primaryColor": "#FFFFFFFF", "supportContentColor": "#99FFFFFF"},
    )
    # 独立业务区可有相同标题，通用去重不能删除模板显式声明的内容。
    root = Nested2Node("Column", ({},), (region, region))
    task = TaskSpec(userQuery="显示耳机电量", size="2x2", dataModelSchema={"data": {}})
    assert _is_advanced_component_region(region)
    assert _deduplicate_visible_text(root, task) == root

    cleaned = _strip_advanced_component_markers(root)
    assert not _is_advanced_component_region(cleaned)
    source = _serialize_node(cleaned)
    assert "_advancedComponent" not in source
    assert source.count("耳机电量") == 2


def _nodes(root: TemplateNode) -> list[TemplateNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_nodes(child))
    return nodes


def test_charging_summary_uses_percent_text_without_removed_progress() -> None:
    bundle = load_provider_bundle(_PROVIDERS_ROOT / "battery")
    definition = next(
        item for item in bundle.templates if item.wire_id == "BatteryOverviewChargingProgressHero@1"
    )
    variant = definition.variants[0]
    nodes = _nodes(variant.root)
    assert not any(node.component == "Progress" for node in nodes)
    assert definition.primary_data == ("/batterySOCText",)
    text_bindings: list[str | None] = []
    for node in nodes:
        if node.component != "Text":
            continue
        value = node.values[0]
        assert value.value != "%", "格式化电量已包含百分号，不能再次追加"
        if value.kind == "binding":
            text_bindings.append(value.name)
    assert "percentText" in text_bindings
    assert "plugged" not in text_bindings


def test_calendar_reminder_contract_matches_start_and_reminder() -> None:
    bundle = load_provider_bundle(_PROVIDERS_ROOT / "calendar")
    definition = next(
        item for item in bundle.templates if item.wire_id == "ScheduleOverviewReminderHero@1"
    )
    assert set(definition.secondary_data) == {
        "/events/0/dtStart", "/events/0/remindTime/0"
    }


@pytest.mark.parametrize("names", ((), ("charging",), ("health",), ("charging", "health")))
def test_charging_summary_guards_every_optional_status(names: tuple[str, ...]) -> None:
    bundle = load_provider_bundle(_PROVIDERS_ROOT / "battery")
    definition = next(
        item for item in bundle.templates if item.wire_id == "BatteryOverviewChargingProgressHero@1"
    )
    bindings = {"percentText": "${data.phoneBattery.batterySOCText}"}
    for name in names:
        bindings[name] = "${data.phoneBattery." + name + "}"
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, bindings,
        theme_values={"primaryColor": "#FFFFFFFF", "supportContentColor": "#99FFFFFF"},
    )
    source = _serialize_node(root)
    for name in ("charging", "health"):
        assert (f"/data/phoneBattery/{name}" in source) == (name in names)
    expected_text_count = 3 if names else 2
    assert source.count("Text(") == expected_text_count
