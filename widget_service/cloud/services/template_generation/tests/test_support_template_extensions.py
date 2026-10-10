"""新增双业务信息块的真实检索、编译与可选数据边界回归。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _provider_template_binding_values,
    _serialize_node,
)
from services.template_generation.engine.cardplan.preview_dataset import _sample_value, _set_path
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.engine.tersel_converter import TerselConversionError

_BATTERY = "BatteryOverviewPluggedTypeSupport@1"
_CONNECTION = "BluetoothDeviceOverviewNameAndConnectionSupport@1"
_CHARGE = "BluetoothDeviceOverviewNameAndChargeSupport@1"
_WEATHER = "WeatherOverviewConditionSupport@1"
_TEMPLATES = (_BATTERY, _CONNECTION, _CHARGE, _WEATHER)


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _schema(
    registry: CardPlanRegistry, template_ids: tuple[str, ...],
) -> dict[str, Any]:
    schema: dict[str, Any] = {"data": {}}
    for template_id in template_ids:
        definition = registry.require_template(template_id)
        assert definition.data_domain is not None
        for name, binding in definition.bindings.items():
            if binding.path not in definition.required_data:
                continue
            _set_path(schema, definition.data_domain + binding.path, {
                "type": binding.data_type,
                "description": name,
                "sampleValue": _sample_value(definition, name, binding.data_type),
            })
    return schema


class _PlanModel:
    def __init__(self, intent: dict[str, Any], body: str) -> None:
        self.intent = intent
        self.body = body

    async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
        assert phase == "template-retrieval-query"
        return self.intent

    async def generate(self, *_args: Any, **_kwargs: Any) -> str:
        return self.body


@pytest.mark.asyncio
@pytest.mark.parametrize("template_id", _TEMPLATES)
@pytest.mark.parametrize("edge_value", [False, True])
async def test_support_minimal_fields_through_search_and_compilation(
    registry: CardPlanRegistry, template_id: str, edge_value: bool,
) -> None:
    partner = _BATTERY if template_id == _WEATHER else _WEATHER
    template_ids = (template_id, partner)
    schema = _schema(registry, template_ids)
    if template_id == _CONNECTION:
        _set_path(schema, "/data/earphone/isConnected", {
            "type": "boolean", "sampleValue": edge_value,
        })
    if template_id == _CHARGE and edge_value:
        _set_path(schema, "/data/earphone/batteryLevel", {
            "type": "integer", "sampleValue": 0,
        })
    bindings: list[CandidateDataBinding] = []
    fields_by_capability: dict[str, list[str]] = {}
    for current in template_ids:
        definition = registry.require_template(current)
        assert definition.capability_id is not None
        assert definition.data_domain is not None
        paths = list(definition.required_data)
        if current == _CHARGE and edge_value:
            paths.append("/batteryLevel")
        bindings.append(CandidateDataBinding(
            capabilityId=definition.capability_id, writeResultTo=definition.data_domain,
            candidateOutputFields=paths,
        ))
        fields_by_capability[definition.capability_id] = paths
    task = TaskSpec(
        userQuery="显示两项业务的已有信息，不需要按钮和图标", size="2x2",
        dataModelSchema=schema, eventCandidates=[], assetCandidates=[],
    )
    body = (
        'Template("TwoSupportLayout@1",{},'
        f'Template("{template_id}",{{}}),Template("{partner}",{{}}));'
    )
    model = _PlanModel({
        "requiredOutputFieldsByCapability": fields_by_capability,
        "primaryOutputFieldByCapability": {}, "action": [],
    }, body)
    card = {"suggestSize": "2x2", "dataBindings": [
        {"capabilityId": binding.capabilityId, "writeResultTo": binding.writeResultTo}
        for binding in bindings
    ]}
    output = await generate_template_a2ui(
        task, card, tuple(bindings), model, trusted_template_candidate_ids=template_ids,
    )
    assert set(template_ids).issubset(output.template_ids)
    assert "onClick" not in output.a2ui
    assert "fusionBallBackground" not in output.a2ui
    if template_id == _CONNECTION:
        assert "${/data/earphone/isConnected} ? '已连接' : '未连接'" in output.a2ui
    if template_id == _CHARGE:
        assert ("${/data/earphone/batteryLevel}" in output.a2ui) is edge_value
    if template_id == _BATTERY:
        assert "${/data/phoneBattery/batterySOC}" not in output.a2ui


@pytest.mark.parametrize("template_id", _TEMPLATES)
def test_support_rejects_each_missing_required_field(
    registry: CardPlanRegistry, template_id: str,
) -> None:
    definition = registry.require_template(template_id)
    assert definition.capability_id is not None
    assert definition.data_domain is not None
    roots = {definition.capability_id: (definition.data_domain,)}
    for missing in definition.required_data:
        schema = _schema(registry, (template_id,))
        _set_path(schema, definition.data_domain + missing, None)
        task = TaskSpec(userQuery="必选字段缺失", size="2x2", dataModelSchema=schema)
        with pytest.raises(TerselConversionError, match="binding is not declared"):
            _provider_template_binding_values(definition, definition.variants[0], task, roots)


@pytest.mark.parametrize("left", [False, True])
@pytest.mark.parametrize("right", [False, True])
@pytest.mark.parametrize("device", [False, True])
def test_earbuds_support_optional_icons_preserve_pair_and_fallback(
    registry: CardPlanRegistry, left: bool, right: bool, device: bool,
) -> None:
    definition = registry.require_template("BluetoothDeviceOverviewEarbudsSupport@1")
    parameters: dict[str, str] = {}
    for enabled, name, filename in (
        (left, "leftIcon", "l_circle_fill.svg"),
        (right, "rightIcon", "r_circle_fill.svg"),
        (device, "deviceIcon", "icon_earphone.svg"),
    ):
        if enabled:
            parameters[name] = "resources/base/media/" + filename
    bindings = {
        "left": "${data.earphone.leftBatteryLevel}",
        "right": "${data.earphone.rightBatteryLevel}",
    }
    theme = registry.themes.get("2x2-two-support")
    assert theme is not None
    root = _instantiate_blueprint(
        definition.variants[0].root, parameters, bindings, theme.reference_values,
    )
    serialized = _serialize_node(root)
    assert ("l_circle_fill.svg" in serialized) is (left and right)
    assert ("r_circle_fill.svg" in serialized) is (left and right)
    assert ("icon_earphone.svg" in serialized) is device
    assert ("'L '" in serialized) is not (left and right)
    assert "/data/earphone/leftBatteryLevel" in serialized
    assert "/data/earphone/rightBatteryLevel" in serialized


def test_new_support_preview_does_not_require_weather_icon() -> None:
    from services.template_generation.engine.cardplan.preview_dataset import (
        build_template_preview_cases,
    )

    cases = build_template_preview_cases()
    weather = next(case for case in cases if case.template_id == _WEATHER)
    assert "Image" not in json.dumps(weather.messages)
