"""双业务素材槽位隔离、正式资源语义及缺失图标回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.template_generation.engine.cardplan.compiler import _normalize_template_asset_params
from services.template_generation.engine.cardplan.models import (
    HybridBodyContract,
    TemplateDefinition,
)
from services.template_generation.engine.cardplan.prompt import (
    _asset_semantic_tags,
    _parameter_allowed_asset_sources,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    load_provider_bundle,
    load_provider_templates,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.test_support.provider_gallery import write_gallery_input_dataset

_ROOT = Path(__file__).resolve().parents[1]
_ASSETS = _ROOT.parents[1] / "data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json"
_SOURCE = "resources/base/media/"
_SLOTS = (
    ("BatteryOverviewSupport@1", "batteryIcon", "icon_phone.svg"),
    ("BatteryOverviewStatusSupport@1", "batteryIcon", "bolt_fill.svg"),
    ("ActivityOverviewSupport@1", "stepsIcon", "figure_run.svg"),
    ("WorkoutOverviewSupport@1", "sourceIcon", "figure_run.svg"),
    ("SleepOverviewSupport@1", "sourceIcon", "moon_z_fill_1.svg"),
    ("HeartRateOverviewSupport@1", "heartIcon", "heart_fill.svg"),
    ("BluetoothDeviceOverviewEarbudsSupport@1", "deviceIcon", "icon_earphone.svg"),
    ("BluetoothDeviceOverviewChargeSupport@1", "deviceIcon", "earphone_case_16644.svg"),
    ("BluetoothDeviceOverviewConnectionSupport@1", "deviceIcon", "icon_earphone.svg"),
    ("ScheduleOverviewTimeSupport@1", "calendarIcon", "calendar_fill.svg"),
    ("ScheduleOverviewLocationSupport@1", "calendarIcon", "calendar_fill.svg"),
    ("ScheduleOverviewStartTimeSupport@1", "calendarIcon", "calendar_fill.svg"),
    ("ScheduleOverviewDateSupport@1", "calendarIcon", "calendar_fill.svg"),
)


@pytest.fixture(scope="module")
def definitions() -> dict[str, TemplateDefinition]:
    templates = load_provider_templates(_ROOT / "resources/source/providers")
    return {template.wire_id: template for template in templates}


@pytest.fixture(scope="module")
def catalog_contract() -> HybridBodyContract:
    assets = json.loads(_ASSETS.read_text(encoding="utf-8"))
    tags_by_source: dict[str, tuple[str, ...]] = {}
    for asset in assets:
        source = asset.get("src")
        assert isinstance(source, str)
        tags_by_source[source] = _asset_semantic_tags(asset)
    return HybridBodyContract.model_construct(
        allowed_asset_sources=tuple(tags_by_source),
        asset_semantic_tags_by_source=tags_by_source,
    )


def test_every_support_asset_slot_has_executable_semantics(
    definitions: dict[str, TemplateDefinition],
) -> None:
    slot_count = 0
    for definition in definitions.values():
        if not definition.wire_id.endswith("Support@1"):
            continue
        for name, tags in definition.asset_parameter_semantic_tags.items():
            assert tags, f"{definition.wire_id}.{name}"
            slot_count += 1
    assert slot_count == 21


@pytest.mark.parametrize(("template_id", "parameter", "filename"), _SLOTS)
def test_mixed_catalog_is_filtered_per_business_slot(
    definitions: dict[str, TemplateDefinition],
    catalog_contract: HybridBodyContract,
    template_id: str,
    parameter: str,
    filename: str,
) -> None:
    definition = definitions.get(template_id)
    assert definition is not None
    allowed = _parameter_allowed_asset_sources(parameter, definition, catalog_contract)
    assert _SOURCE + filename in allowed
    assert _SOURCE + "drop_1.svg" not in allowed
    assert _SOURCE + "icon_weather_temperature1.svg" not in allowed
    if template_id == "BluetoothDeviceOverviewEarbudsSupport@1":
        assert _SOURCE + "earphone_case_16644.svg" not in allowed
    if template_id == "BluetoothDeviceOverviewChargeSupport@1":
        assert _SOURCE + "icon_earphone.svg" not in allowed
    if template_id == "BatteryOverviewSupport@1":
        assert allowed == (_SOURCE + "icon_phone.svg",)


def test_phone_battery_support_icon_does_not_change_single_business_asset_semantics(
    definitions: dict[str, TemplateDefinition],
    catalog_contract: HybridBodyContract,
) -> None:
    definition = definitions.get("BatteryOverviewCompact@1")
    assert definition is not None
    allowed = _parameter_allowed_asset_sources("batteryIcon", definition, catalog_contract)
    assert definition.asset_parameter_semantic_tags.get("batteryIcon") == ()
    assert allowed == catalog_contract.allowed_asset_sources


@pytest.mark.parametrize("template_id", (
    "WeatherOverviewCompact@1", "WeatherOverviewUvCompact@1",
    "WeatherOverviewTemperatureSupport@1",
    "WeatherOverviewDaily2TravelSupport@1", "WeatherOverviewTravelSupport@1",
    "WeatherOverviewHero@1", "WeatherOverviewFull@1",
))
def test_weather_slot_separates_single_and_dual_business_assets(
    definitions: dict[str, TemplateDefinition],
    catalog_contract: HybridBodyContract,
    template_id: str,
) -> None:
    definition = definitions.get(template_id)
    assert definition is not None
    allowed = _parameter_allowed_asset_sources("conditionIcon", definition, catalog_contract)
    state_sources = {
        _SOURCE + "sun_max.svg", _SOURCE + "drop_1.svg",
        _SOURCE + "typhoon_fill.svg", _SOURCE + "icon_weather_wind.svg",
    }
    temperature_sources = {
        _SOURCE + "heat_generation.svg", _SOURCE + "icon_weather_temperature1.svg",
        _SOURCE + "icon_weather_thermometer_medium.svg",
        _SOURCE + "icon_weather_thermometer.svg",
    }
    dual_business = (
        template_id == "WeatherOverviewTemperatureSupport@1"
        or template_id == "WeatherOverviewDaily2TravelSupport@1"
        or template_id == "WeatherOverviewTravelSupport@1"
    )
    if dual_business:
        assert set(allowed) == state_sources | temperature_sources
    else:
        assert set(allowed) == state_sources
        for source in temperature_sources:
            with pytest.raises(TerselConversionError, match="semantics"):
                _normalize_template_asset_params(
                    {"conditionIcon": source}, definition.asset_parameter_semantic_tags,
                    catalog_contract, required_parameters=frozenset(),
                )
        temperature_only = catalog_contract.model_copy(
            update={"allowed_asset_sources": tuple(temperature_sources)}
        )
        assert _parameter_allowed_asset_sources(
            "conditionIcon", definition, temperature_only,
        ) == ()
        assert _normalize_template_asset_params(
            {}, definition.asset_parameter_semantic_tags, temperature_only,
            required_parameters=frozenset(),
        ) == {}
    for source in allowed:
        normalized = _normalize_template_asset_params(
            {"conditionIcon": source}, definition.asset_parameter_semantic_tags,
            catalog_contract, required_parameters=frozenset(),
        )
        assert normalized == {"conditionIcon": source}
    with pytest.raises(TerselConversionError, match="semantics"):
        _normalize_template_asset_params(
            {"conditionIcon": _SOURCE + "icon_high_temperature.svg"},
            definition.asset_parameter_semantic_tags,
            catalog_contract,
            required_parameters=frozenset(),
        )


@pytest.mark.parametrize("template_id", (
    "CountdownOverviewSupport@1", "CountdownOverviewTravelSupport@1",
))
def test_countdown_slot_only_accepts_timing_assets(
    definitions: dict[str, TemplateDefinition],
    catalog_contract: HybridBodyContract,
    template_id: str,
) -> None:
    definition = definitions.get(template_id)
    assert definition is not None
    allowed = _parameter_allowed_asset_sources("timerIcon", definition, catalog_contract)
    timing_sources = {
        _SOURCE + "hourglass_fill.svg",
        _SOURCE + "stopwatch_fill.svg",
        _SOURCE + "icon_timing.svg",
    }
    assert set(allowed) == timing_sources
    for source in allowed:
        normalized = _normalize_template_asset_params(
            {"timerIcon": source}, definition.asset_parameter_semantic_tags,
            catalog_contract, required_parameters=frozenset(),
        )
        assert normalized == {"timerIcon": source}
    with pytest.raises(TerselConversionError, match="semantics"):
        _normalize_template_asset_params(
            {"timerIcon": _SOURCE + "clock.svg"},
            definition.asset_parameter_semantic_tags,
            catalog_contract,
            required_parameters=frozenset(),
        )


@pytest.mark.parametrize(("template_id", "parameter", "filename"), _SLOTS)
def test_cross_business_mistake_only_repairs_to_unique_matching_asset(
    definitions: dict[str, TemplateDefinition],
    catalog_contract: HybridBodyContract,
    template_id: str,
    parameter: str,
    filename: str,
) -> None:
    definition = definitions.get(template_id)
    assert definition is not None
    expected = _SOURCE + filename
    wrong = _SOURCE + "drop_1.svg"
    contract = catalog_contract.model_copy(update={"allowed_asset_sources": (wrong, expected)})
    original = {parameter: wrong}
    result = _normalize_template_asset_params(
        original, definition.asset_parameter_semantic_tags, contract,
        required_parameters=frozenset(),
    )
    assert result == {parameter: expected}
    assert original == {parameter: wrong}
    assert _normalize_template_asset_params(
        {}, definition.asset_parameter_semantic_tags, contract, required_parameters=frozenset(),
    ) == {}
    missing = contract.model_copy(update={"allowed_asset_sources": (wrong,)})
    with pytest.raises(TerselConversionError, match="semantics"):
        _normalize_template_asset_params(
            original, definition.asset_parameter_semantic_tags, missing,
            required_parameters=frozenset(),
        )


def _write_bundle(root: Path, semantics: dict[str, list[str]] | None) -> None:
    entry: dict[str, object] = {
        "templateId": "IconFixture@1", "description": "素材测试", "entry": "icon.cardtpl",
    }
    if semantics is not None:
        entry["assetParameterSemanticTags"] = semantics
    manifest = {
        "bundleFormat": "card-provider-bundle/1",
        "providerId": "com.example.fixture",
        "providerVersion": "1.0.0",
        "templates": [entry],
        "compatibility": {
            "templateLanguage": "cardtpl/2",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "a2uiWireVersion": "v0.9",
        },
    }
    (root / "provider.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "icon.cardtpl").write_text(
        '#Template IconFixture@1(props: { glyph?: asset, label?: string })\n'
        'data = {}\nRow({}, Text("素材测试"))\n#End\n', encoding="utf-8",
    )


@pytest.mark.parametrize("semantics", (
    {"missing": ["steps"]}, {"label": ["steps"]}, {"glyph": []},
    {"glyph": ["Steps"]}, {"glyph": ["steps", "steps"]},
    {"glyph": ["bad tag"]}, {"bad name": ["steps"]},
))
def test_bundle_rejects_invalid_asset_slot_metadata(
    tmp_path: Path, semantics: dict[str, list[str]],
) -> None:
    _write_bundle(tmp_path, semantics)
    with pytest.raises(ValueError, match="asset|semantic"):
        load_provider_bundle(tmp_path)


def test_declared_asset_enforced_even_without_icon_name(
    tmp_path: Path, catalog_contract: HybridBodyContract,
) -> None:
    _write_bundle(tmp_path, {"glyph": ["sleep"]})
    definition = load_provider_bundle(tmp_path).templates[0]
    contract = catalog_contract.model_copy(update={
        "allowed_asset_sources": (_SOURCE + "drop_1.svg", _SOURCE + "moon_z_fill_1.svg"),
    })
    result = _normalize_template_asset_params(
        {"glyph": _SOURCE + "drop_1.svg"}, definition.asset_parameter_semantic_tags,
        contract, required_parameters=frozenset(),
    )
    assert result == {"glyph": _SOURCE + "moon_z_fill_1.svg"}


def test_legacy_bundle_keeps_unrestricted_asset_behavior(tmp_path: Path) -> None:
    _write_bundle(tmp_path, None)
    definition = load_provider_bundle(tmp_path).templates[0]
    assert definition.asset_parameter_semantic_tags == {"glyph": ()}


def test_gallery_both_slots_have_their_own_assets_and_cloudy_keeps_temperature_icon(
    tmp_path: Path,
) -> None:
    manifest = write_gallery_input_dataset(tmp_path)
    provider = next(item for item in manifest.providers if item.providerSlug == "two-support")
    expected = {
        "BatteryOverviewSupport@1": "asset.icon_phone",
        "BatteryOverviewStatusSupport@1": "asset.bolt_fill",
        "WeatherOverviewTemperatureSupport@1": "asset.icon_weather_thermometer",
        "WeatherOverviewDaily2TravelSupport@1": "asset.icon_weather_thermometer",
        "WeatherOverviewTravelSupport@1": "asset.icon_weather_thermometer",
        "CountdownOverviewSupport@1": "asset.icon_timing",
        "CountdownOverviewTravelSupport@1": "asset.icon_timing",
        "ActivityOverviewSupport@1": "asset.figure_run",
        "WorkoutOverviewSupport@1": "asset.figure_run",
        "SleepOverviewSupport@1": "asset.moon_z_fill_1",
        "HeartRateOverviewSupport@1": "asset.heart_fill",
        "BluetoothDeviceOverviewEarbudsSupport@1": "asset.icon_earphone",
        "BluetoothDeviceOverviewChargeSupport@1": "asset.earphone_case_16644",
        "BluetoothDeviceOverviewConnectionSupport@1": "asset.icon_earphone",
        "ScheduleOverviewTimeSupport@1": "asset.calendar_fill",
        "ScheduleOverviewLocationSupport@1": "asset.calendar_fill",
        "ScheduleOverviewStartTimeSupport@1": "asset.calendar_fill",
        "ScheduleOverviewDateSupport@1": "asset.calendar_fill",
    }
    assert len(provider.cases) == 64
    for case in provider.cases:
        payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
        content = payload.get("content")
        assert isinstance(content, dict)
        asset_ids = content.get("candidateAssetIds")
        assert isinstance(asset_ids, list)
        expected_ids: list[str] = []
        for template_id in (case.targetTemplateId, case.partnerTemplateId):
            asset_id = expected.get(template_id)
            if asset_id is not None and asset_id not in expected_ids:
                expected_ids.append(asset_id)
        assert asset_ids == expected_ids, case.caseId
        gallery_test = payload.get("galleryTest")
        assert isinstance(gallery_test, dict)
        overrides = gallery_test.get("sampleOverrides")
        assert isinstance(overrides, dict)
        assert overrides.get("/data/weather/current/condition") == "多云"
