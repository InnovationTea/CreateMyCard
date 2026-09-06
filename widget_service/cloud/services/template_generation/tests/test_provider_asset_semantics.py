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
    ("ActivityOverviewSupport@1", "stepsIcon", "figure_run.svg"),
    ("WorkoutOverviewSupport@1", "sourceIcon", "figure_run.svg"),
    ("SleepOverviewSupport@1", "sourceIcon", "moon_z_fill_1.svg"),
    ("HeartRateOverviewIconSupport@1", "sourceIcon", "heart_fill.svg"),
    ("HeartRateOverviewUpdatedIconSupport@1", "sourceIcon", "heart_fill.svg"),
    ("BluetoothDeviceOverviewEarbudsSupport@1", "deviceIcon", "icon_earphone.svg"),
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
    assert slot_count == 10


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
    if parameter == "deviceIcon":
        assert _SOURCE + "earphone_case_16644.svg" not in allowed


@pytest.mark.parametrize("template_id", (
    "WeatherOverviewTemperatureSupport@1", "WeatherOverviewTemperatureUvSupport@1",
))
def test_weather_slot_only_accepts_condition_assets(
    definitions: dict[str, TemplateDefinition],
    catalog_contract: HybridBodyContract,
    template_id: str,
) -> None:
    definition = definitions.get(template_id)
    assert definition is not None
    allowed = _parameter_allowed_asset_sources("conditionIcon", definition, catalog_contract)
    assert set(allowed) == {
        _SOURCE + "sun_max.svg", _SOURCE + "drop_1.svg",
        _SOURCE + "typhoon_fill.svg", _SOURCE + "icon_weather_wind.svg",
    }
    with pytest.raises(TerselConversionError, match="semantics"):
        _normalize_template_asset_params(
            {"conditionIcon": _SOURCE + "icon_weather_temperature1.svg"},
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


def test_gallery_both_slots_have_their_own_assets_and_cloudy_has_no_substitute(
    tmp_path: Path,
) -> None:
    manifest = write_gallery_input_dataset(tmp_path)
    provider = next(item for item in manifest.providers if item.providerSlug == "two-support")
    expected = {
        "ActivityOverviewSupport@1": "asset.figure_run",
        "WorkoutOverviewSupport@1": "asset.figure_run",
        "SleepOverviewSupport@1": "asset.moon_z_fill_1",
        "HeartRateOverviewIconSupport@1": "asset.heart_fill",
        "HeartRateOverviewUpdatedIconSupport@1": "asset.heart_fill",
        "BluetoothDeviceOverviewEarbudsSupport@1": "asset.icon_earphone",
    }
    assert len(provider.cases) == 45
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
