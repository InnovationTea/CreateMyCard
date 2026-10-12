"""检查全量正式模板的业务标记及其编译期内容保护边界。

业务标记与编译期保护的确定性产物已固化为场景金样（Layer C）：
``provider_marker__business_markers`` 冻结全部 provider 目录每个模板
（含布局/动作模板）的 _advancedComponent 标记清单（kind+value）、期望
家族身份与形状特例映射；``provider_marker__earbud_protection`` 冻结耳塞
Support 标记区在有/无动作下独立业务去重保留与标记剥离后的序列化产物；
``provider_marker__template_contracts`` 冻结充电 Hero 的组件树、primary
数据契约、文本绑定与字面量（禁止裸百分号与已删除 Progress）以及日历
Reminder Hero 的 secondary 数据契约；``provider_marker__charging_optional_guards``
冻结充电/健康可选状态四种组合下的完整实例化序列化。原文件全部测试函数
均已转换为金样，仅保留场景比对入口。引擎改动后按 golden 工作流
`check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _deduplicate_visible_text,
    _instantiate_blueprint,
    _is_advanced_component_region,
    _serialize_node,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.models import (
    TemplateDefinition,
    TemplateNode,
    TemplateValue,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    load_provider_bundle,
    provider_template_family_identity,
)
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_PROVIDERS_ROOT = Path(__file__).resolve().parents[1] / "resources/source/providers"
_PROVIDER_DIRECTORIES = tuple(
    path.parent for path in sorted(_PROVIDERS_ROOT.glob("*/provider.json"))
)
_SHAPE_SPECIFIC_MARKERS = {
    "WeatherOverviewTemperatureSupport@1": "WeatherOverviewTemperatureSupport",
    "WeatherOverviewTemperatureUvSupport@1": "WeatherOverviewTemperatureSupport",
    "WeatherOverviewTemperaturecoldLevelSupport@1": "WeatherOverviewTemperatureSupport",
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


@scenario("provider_marker__business_markers")
def _build_business_markers() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for provider_root in _PROVIDER_DIRECTORIES:
        for definition in load_provider_bundle(provider_root).templates:
            markers: list[dict[str, str]] = []
            for variant in definition.variants:
                for marker in _marker_values(variant.root):
                    markers.append({"kind": marker.kind, "value": marker.value})
            identity = provider_template_family_identity(definition.wire_id)
            expected = (
                _SHAPE_SPECIFIC_MARKERS.get(definition.wire_id, identity[0].partition("@")[0])
                if identity is not None
                else None
            )
            payload[definition.wire_id] = {
                "markers": markers,
                "expectedFamily": expected,
            }
    return payload


def _definition_of(provider: str, wire_id: str) -> TemplateDefinition:
    bundle = load_provider_bundle(_PROVIDERS_ROOT / provider)
    return next(item for item in bundle.templates if item.wire_id == wire_id)


def _earbud_region(with_action: bool) -> Nested2Node:
    definition = _definition_of(
        "earphone", "BluetoothDeviceOverviewEarbudsSupport@1",
    )
    params: dict[str, str] = {"deviceIcon": "resources/base/media/earphone.svg"}
    if with_action:
        params["actionId"] = "event.openBluetooth"
    return _instantiate_blueprint(
        definition.variants[0].root,
        params,
        bindings={
            "left": "${data.earphone.leftBatteryLevel}",
            "right": "${data.earphone.rightBatteryLevel}",
        },
        theme_values={"primaryColor": "#FFFFFFFF", "supportContentColor": "#99FFFFFF"},
    )


@scenario("provider_marker__earbud_protection")
def _build_earbud_protection() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for with_action in (False, True):
        region = _earbud_region(with_action)
        # 独立业务区可有相同标题，通用去重不能删除模板显式声明的内容。
        root = Nested2Node("Column", ({},), (region, region))
        task = TaskSpec(userQuery="显示耳机电量", size="2x2", dataModelSchema={"data": {}})
        deduped = _deduplicate_visible_text(root, task)
        cleaned = _strip_advanced_component_markers(root)
        payload["with_action" if with_action else "no_action"] = {
            "isAdvancedRegion": _is_advanced_component_region(region),
            "dedupPreservedBothRegions": _serialize_node(deduped) == _serialize_node(root),
            "dedupSerialized": _serialize_node(deduped),
            "strippedSerialized": _serialize_node(cleaned),
        }
    return payload


def _nodes(root: TemplateNode) -> list[TemplateNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_nodes(child))
    return nodes


@scenario("provider_marker__template_contracts")
def _build_template_contracts() -> dict[str, dict[str, Any]]:
    charging = _definition_of("battery", "BatteryOverviewChargingProgressHero@1")
    nodes = _nodes(charging.variants[0].root)
    text_bindings: list[str] = []
    text_first_values: list[dict[str, Any]] = []
    for node in nodes:
        if node.component != "Text":
            continue
        value = node.values[0]
        entry: dict[str, Any] = {"kind": value.kind}
        if value.kind == "binding":
            entry["name"] = value.name
            text_bindings.append(value.name)
        elif value.kind == "literal":
            entry["value"] = value.value
        text_first_values.append(entry)
    reminder = _definition_of("calendar", "ScheduleOverviewReminderHero@1")
    return {
        "BatteryOverviewChargingProgressHero@1": {
            "primaryData": list(charging.primary_data),
            "nodeComponents": [node.component for node in nodes],
            "textBindings": text_bindings,
            "textFirstValues": text_first_values,
        },
        "ScheduleOverviewReminderHero@1": {
            "secondaryData": sorted(reminder.secondary_data),
        },
    }


@scenario("provider_marker__charging_optional_guards")
def _build_charging_optional_guards() -> dict[str, dict[str, str]]:
    definition = _definition_of("battery", "BatteryOverviewChargingProgressHero@1")
    payload: dict[str, dict[str, str]] = {}
    for names in ((), ("charging",), ("health",), ("charging", "health")):
        bindings = {"percentText": "${data.phoneBattery.batterySOCText}"}
        for name in names:
            bindings[name] = "${data.phoneBattery." + name + "}"
        root = _instantiate_blueprint(
            definition.variants[0].root, {}, bindings,
            theme_values={"primaryColor": "#FFFFFFFF", "supportContentColor": "#99FFFFFF"},
        )
        payload["+".join(names) or "none"] = {"serialized": _serialize_node(root)}
    return payload


def test_provider_component_marker_scenarios_match_goldens() -> None:
    assert_golden_scenario("provider_marker__business_markers")
    assert_golden_scenario("provider_marker__earbud_protection")
    assert_golden_scenario("provider_marker__template_contracts")
    assert_golden_scenario("provider_marker__charging_optional_guards")
