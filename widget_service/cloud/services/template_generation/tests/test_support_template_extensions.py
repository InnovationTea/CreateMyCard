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
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.engine.pipeline import (
    TemplateRouteNotApplicable,
    generate_template_a2ui,
)
from services.template_generation.engine.tersel_converter import TerselConversionError

_BATTERY = "BatteryOverviewPluggedTypeSupport@1"
_CONNECTION = "BluetoothDeviceOverviewNameAndConnectionSupport@1"
_CHARGE = "BluetoothDeviceOverviewNameAndChargeSupport@1"
_WEATHER = "WeatherOverviewConditionSupport@1"
_WEATHER_TEXT_TEMPLATES = (
    "WeatherOverviewTemperatureConditionSupport@1",
    "WeatherOverviewTemperatureHumiditySupport@1",
    "WeatherOverviewTemperatureAirQualitySupport@1",
)
_TEMPLATES = (_BATTERY, _CONNECTION, _CHARGE, _WEATHER, *_WEATHER_TEXT_TEMPLATES)


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
    partner = _BATTERY if template_id.startswith("WeatherOverview") else _WEATHER
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
    if template_id == "WeatherOverviewTemperatureHumiditySupport@1" and edge_value:
        _set_path(schema, "/data/weather/current/humidityPercent", {
            "type": "number", "sampleValue": 0,
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
    weather_icon = "resources/base/media/sun_max.svg"
    earphone_icon = "resources/base/media/icon_earphone.svg"
    task = TaskSpec(
        userQuery="显示两项业务的已有信息，不需要按钮", size="2x2",
        dataModelSchema=schema, eventCandidates=[], assetCandidates=[
            {"src": weather_icon, "description": "晴天天气图标", "sceneTags": ["weather", "sunny"]},
            {"src": earphone_icon, "description": "耳机图标", "sceneTags": ["bluetooth-device"]},
        ],
    )
    parameters = {_WEATHER: {"conditionIcon": weather_icon}}
    parameters[_CHARGE] = {"bluetoothIconOrDeviceIcon": earphone_icon}
    current_parameters = json.dumps(parameters.get(template_id, {}))
    partner_parameters = json.dumps(parameters.get(partner, {}))
    body = (
        'Template("TwoSupportLayout@1",{},'
        f'Template("{template_id}",{current_parameters}),'
        f'Template("{partner}",{partner_parameters}));'
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
        assert (earphone_icon in output.a2ui) is not edge_value
    if template_id == _BATTERY:
        assert "${/data/phoneBattery/batterySOC}" not in output.a2ui
    if template_id in _WEATHER_TEXT_TEMPLATES:
        assert "${/data/weather/current/temperatureText}" in output.a2ui
        assert "${/data/weather/current/condition}" in output.a2ui
        assert "当前城市" in output.a2ui
        assert "{data.humidity}" not in output.a2ui
        assert "{data.airQuality}" not in output.a2ui
        assert ("${/data/weather/current/humidityPercent}" in output.a2ui) is (
            template_id == "WeatherOverviewTemperatureHumiditySupport@1"
        )
        assert ("${/data/weather/current/airQuality}" in output.a2ui) is (
            template_id == "WeatherOverviewTemperatureAirQualitySupport@1"
        )


@pytest.mark.parametrize("template_id", _WEATHER_TEXT_TEMPLATES)
@pytest.mark.parametrize(
    ("city", "district", "location", "expected"),
    [
        (True, True, "深圳市", "${data.weather.location.prefectureName}"),
        (False, True, "深圳市", "${data.weather.location.districtName}"),
        (False, False, "深圳市", "深圳市"),
        (False, False, None, "当前城市"),
    ],
)
def test_weather_text_support_city_fallback(
    registry: CardPlanRegistry, template_id: str,
    city: bool, district: bool, location: str | None, expected: str,
) -> None:
    definition = registry.require_template(template_id)
    schema = _schema(registry, (template_id,))
    for present, name in ((city, "prefectureName"), (district, "districtName")):
        if present:
            _set_path(schema, "/data/weather/location/" + name, {"type": "string"})
    task = TaskSpec(userQuery="天气城市兜底", size="2x2", dataModelSchema=schema)
    bindings = _provider_template_binding_values(
        definition, definition.variants[0], task, {"ViewWeather": ("/data/weather",)},
    )
    params = {} if location is None else {"location": location}
    root = _instantiate_blueprint(
        definition.variants[0].root, params, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )
    title = root.children[0].children[0].children[0]
    assert expected in title.values[0]
    assert definition.optional_data == (
        "/location/prefectureName", "/location/districtName",
    )
    assert definition.supported_event_ids == ("event.open.weather",)


@pytest.mark.parametrize(
    ("extra_fields", "expected"),
    [
        ((), _WEATHER_TEXT_TEMPLATES),
        (("/current/humidityPercent",), ("WeatherOverviewTemperatureHumiditySupport@1",)),
        (("/current/airQuality",), ("WeatherOverviewTemperatureAirQualitySupport@1",)),
        (("/current/humidityPercent", "/current/airQuality"), ()),
    ],
)
def test_weather_text_support_search_preserves_requested_metrics(
    registry: CardPlanRegistry, extra_fields: tuple[str, ...], expected: tuple[str, ...],
) -> None:
    schema = _schema(registry, _WEATHER_TEXT_TEMPLATES)
    task = TaskSpec(userQuery="天气指标", size="2x2", dataModelSchema=schema)
    paths = ("/current/temperatureText", "/current/condition", *extra_fields)
    binding = CandidateDataBinding(
        capabilityId="ViewWeather", writeResultTo="/data/weather",
        candidateOutputFields=list(paths),
    )
    result = search_template_variants(
        TemplateSearchIntent(requiredOutputFieldsByCapability={"ViewWeather": paths}),
        task, registry, (binding,), {
            "suggestSize": "2x2",
            "dataBindings": [
                {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"},
            ],
        },
    )
    actual: set[str] = set()
    for group in result.business_candidates:
        for candidate in group.candidates:
            if candidate.template_id in _WEATHER_TEXT_TEMPLATES:
                actual.add(candidate.template_id)
    assert actual == set(expected)


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
    if left and right:
        assert '"margin":{"left":4}' in serialized
    assert ("icon_earphone.svg" in serialized) is device
    assert ("'L '" in serialized) is not (left and right)
    assert "/data/earphone/leftBatteryLevel" in serialized
    assert "/data/earphone/rightBatteryLevel" in serialized


def test_new_support_preview_requires_matching_weather_icon() -> None:
    from services.template_generation.engine.cardplan.preview_dataset import (
        build_template_preview_cases,
    )

    cases = build_template_preview_cases()
    weather = next(case for case in cases if case.template_id == _WEATHER)
    assert "resources/base/media/sun_max.svg" in json.dumps(weather.messages)
    assert "晴" in json.dumps(weather.messages, ensure_ascii=False)


@pytest.mark.asyncio
async def test_weather_support_is_unavailable_without_matching_icon(
    registry: CardPlanRegistry,
) -> None:
    schema = _schema(registry, (_WEATHER, _BATTERY))
    task = TaskSpec(userQuery="显示天气现象和手机充电状态", size="2x2", dataModelSchema=schema)
    bindings = (
        CandidateDataBinding(
            capabilityId="ViewWeather", writeResultTo="/data/weather",
            candidateOutputFields=["/current/condition"],
        ),
        CandidateDataBinding(
            capabilityId="GetPhoneBatteryInfo", writeResultTo="/data/phoneBattery",
            candidateOutputFields=["/batterySOCText", "/chargingStatusDesc", "/pluggedTypeDesc"],
        ),
    )
    model = _PlanModel({
        "requiredOutputFieldsByCapability": {
            "ViewWeather": ["/current/condition"],
            "GetPhoneBatteryInfo": ["/batterySOCText", "/chargingStatusDesc", "/pluggedTypeDesc"],
        },
        "primaryOutputFieldByCapability": {}, "action": [],
    }, 'Template("TwoSupportLayout@1",{},'
       'Template("WeatherOverviewConditionSupport@1",{}),'
       'Template("BatteryOverviewPluggedTypeSupport@1",{}));')
    with pytest.raises(TemplateRouteNotApplicable):
        await generate_template_a2ui(
            task, {"suggestSize": "2x2"}, bindings, model,
            trusted_template_candidate_ids=(_WEATHER, _BATTERY),
        )


def test_battery_text_support_has_no_asset_parameter(registry: CardPlanRegistry) -> None:
    definition = registry.require_template(_BATTERY)
    assert definition.asset_parameter_semantic_tags == {}
    properties = definition.variants[0].parameters_schema.get("properties")
    assert isinstance(properties, dict)
    assert "batteryOrChangeIcon" not in properties
