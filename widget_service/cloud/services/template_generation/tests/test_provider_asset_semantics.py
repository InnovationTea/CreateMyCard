"""双业务素材槽位隔离、正式资源语义及缺失图标回归。

素材槽位的确定性解析结果已固化为场景金样（Layer C）：
``provider_asset__slot_sources`` 冻结全部正式素材槽位的允许资产清单
（含单业务 Compact 的全目录放行、倒计时 timing 专属清单，以及耳塞/充电盒
互相排斥的隐式断言）；``provider_asset__weather_slot_union`` 冻结 7 个天气
模板 conditionIcon 的单/双业务并集、逐资产透传归一化与仅温度目录的收敛；
``provider_asset__slot_rejections`` 冻结温度语义资产误用、高温图标与
clock.svg 的报错类型与文案；``provider_asset__unique_match_repair`` 冻结跨
业务误用资产修复到唯一匹配资产的输入/输出/原输入保留与缺匹配报错（含
IconFixture 声明槽位的强制修复）；``provider_asset__bundle_rejections``
冻结 bundle 素材元数据校验矩阵与 legacy 无声明 bundle 的放行行为。
保留 19 个可执行素材槽位计数钉与 61 个 gallery 用例资产钉为普通测试
（出行 Support 不声明槽位由槽位计数钉间接钉住）。引擎改动后按 golden
工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

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
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)
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
# 槽位清单场景额外覆盖的单业务 Compact（全目录放行）与倒计时 timing 专属清单。
_EXTRA_SLOTS = (
    ("BatteryOverviewCompact@1", "batteryIcon", "icon_phone.svg"),
    ("CountdownOverviewSupport@1", "timerIcon", "icon_timing.svg"),
)
_WEATHER_TEMPLATES = (
    "WeatherOverviewCompact@1", "WeatherOverviewUvCompact@1",
    "WeatherOverviewTemperatureSupport@1",
    "WeatherOverviewDaily2TravelSupport@1", "WeatherOverviewTravelSupport@1",
    "WeatherOverviewHero@1", "WeatherOverviewFull@1",
)
_DUAL_WEATHER_TEMPLATES = (
    "WeatherOverviewTemperatureSupport@1",
    "WeatherOverviewDaily2TravelSupport@1",
    "WeatherOverviewTravelSupport@1",
)
_TEMPERATURE_SOURCES = (
    _SOURCE + "heat_generation.svg", _SOURCE + "icon_weather_temperature1.svg",
    _SOURCE + "icon_weather_thermometer_medium.svg", _SOURCE + "icon_weather_thermometer.svg",
)


def _definitions() -> dict[str, TemplateDefinition]:
    templates = load_provider_templates(_ROOT / "resources/source/providers")
    return {template.wire_id: template for template in templates}


def _catalog_contract() -> HybridBodyContract:
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


def _capture(build: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"error": "NO_ERROR", "result": build()}
    except Exception as exc:  # noqa: BLE001 - 场景金样冻结精确错误类型与文案
        return {"errorType": type(exc).__name__, "message": str(exc)}


@scenario("provider_asset__slot_sources")
def _build_slot_sources() -> dict[str, list[str]]:
    definitions = _definitions()
    contract = _catalog_contract()
    return {
        f"{template_id}.{parameter}": list(
            _parameter_allowed_asset_sources(parameter, definitions[template_id], contract)
        )
        for template_id, parameter, _filename in _SLOTS + _EXTRA_SLOTS
    }


@scenario("provider_asset__weather_slot_union")
def _build_weather_slot_union() -> dict[str, dict[str, Any]]:
    definitions = _definitions()
    contract = _catalog_contract()
    temperature_only = contract.model_copy(
        update={"allowed_asset_sources": tuple(_TEMPERATURE_SOURCES)}
    )
    payload: dict[str, dict[str, Any]] = {}
    for template_id in _WEATHER_TEMPLATES:
        definition = definitions[template_id]
        allowed = _parameter_allowed_asset_sources("conditionIcon", definition, contract)
        payload[template_id] = {
            "dualBusiness": template_id in _DUAL_WEATHER_TEMPLATES,
            "allowed": list(allowed),
            "identityNormalize": {
                source: _normalize_template_asset_params(
                    {"conditionIcon": source}, definition.asset_parameter_semantic_tags,
                    contract, required_parameters=frozenset(),
                )
                for source in allowed
            },
            "temperatureOnlyAllowed": list(_parameter_allowed_asset_sources(
                "conditionIcon", definition, temperature_only,
            )),
        }
    return payload


@scenario("provider_asset__slot_rejections")
def _build_slot_rejections() -> dict[str, dict[str, Any]]:
    definitions = _definitions()
    contract = _catalog_contract()
    payload: dict[str, dict[str, Any]] = {}
    for template_id in _WEATHER_TEMPLATES:
        definition = definitions[template_id]
        sources = () if template_id in _DUAL_WEATHER_TEMPLATES else _TEMPERATURE_SOURCES
        for source in sources:
            payload[f"{template_id} conditionIcon={source.rsplit('/', 1)[-1]}"] = _capture(
                lambda d=definition, s=source: _normalize_template_asset_params(
                    {"conditionIcon": s}, d.asset_parameter_semantic_tags,
                    contract, required_parameters=frozenset(),
                )
            )
        payload[f"{template_id} conditionIcon=icon_high_temperature.svg"] = _capture(
            lambda d=definition: _normalize_template_asset_params(
                {"conditionIcon": _SOURCE + "icon_high_temperature.svg"},
                d.asset_parameter_semantic_tags, contract,
                required_parameters=frozenset(),
            )
        )
    countdown = definitions["CountdownOverviewSupport@1"]
    payload["CountdownOverviewSupport@1 timerIcon=clock.svg"] = _capture(
        lambda: _normalize_template_asset_params(
            {"timerIcon": _SOURCE + "clock.svg"}, countdown.asset_parameter_semantic_tags,
            contract, required_parameters=frozenset(),
        )
    )
    return payload


@scenario("provider_asset__unique_match_repair")
def _build_unique_match_repair() -> dict[str, dict[str, Any]]:
    definitions = _definitions()
    contract = _catalog_contract()
    payload: dict[str, dict[str, Any]] = {}
    for template_id, parameter, filename in _SLOTS + _EXTRA_SLOTS:
        definition = definitions[template_id]
        wrong = _SOURCE + "drop_1.svg"
        expected = _SOURCE + filename
        pair = contract.model_copy(update={"allowed_asset_sources": (wrong, expected)})
        original: dict[str, Any] = {parameter: wrong}
        input_before = dict(original)
        result = _normalize_template_asset_params(
            original, definition.asset_parameter_semantic_tags, pair,
            required_parameters=frozenset(),
        )
        missing = contract.model_copy(update={"allowed_asset_sources": (wrong,)})
        payload[f"{template_id}.{parameter}"] = {
            "input": input_before,
            "repaired": result,
            "inputPreserved": dict(original),
            "emptyInput": _normalize_template_asset_params(
                {}, definition.asset_parameter_semantic_tags, pair,
                required_parameters=frozenset(),
            ),
            "missingMatch": _capture(
                lambda d=definition, o=dict(original), m=missing:
                    _normalize_template_asset_params(
                        o, d.asset_parameter_semantic_tags, m,
                        required_parameters=frozenset(),
                    )
            ),
        }
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_bundle(root, {"glyph": ["sleep"]})
        definition = load_provider_bundle(root).templates[0]
        limited = contract.model_copy(update={
            "allowed_asset_sources": (
                _SOURCE + "drop_1.svg", _SOURCE + "moon_z_fill_1.svg",
            )
        })
        payload["IconFixture@1.glyph"] = {
            "declaredTags": ["sleep"],
            "allowed": list(limited.allowed_asset_sources),
            "repaired": _normalize_template_asset_params(
                {"glyph": _SOURCE + "drop_1.svg"}, definition.asset_parameter_semantic_tags,
                limited, required_parameters=frozenset(),
            ),
        }
    return payload


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


_BUNDLE_INVALID_CASES = (
    ("missing_parameter", {"missing": ["steps"]}),
    ("non_asset_parameter", {"label": ["steps"]}),
    ("empty_tags", {"glyph": []}),
    ("uppercase_tag", {"glyph": ["Steps"]}),
    ("duplicate_tags", {"glyph": ["steps", "steps"]}),
    ("tag_with_space", {"glyph": ["bad tag"]}),
    ("bad_parameter_name", {"bad name": ["steps"]}),
)


@scenario("provider_asset__bundle_rejections")
def _build_bundle_rejections() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for key, semantics in _BUNDLE_INVALID_CASES:
        with TemporaryDirectory() as tmp:
            _write_bundle(Path(tmp), semantics)
            payload[key] = _capture(lambda p=Path(tmp): load_provider_bundle(p))
    with TemporaryDirectory() as tmp:
        _write_bundle(Path(tmp), None)
        definition = load_provider_bundle(Path(tmp)).templates[0]
        payload["legacy_unrestricted"] = {
            "assetParameterSemanticTags": {
                name: list(tags)
                for name, tags in definition.asset_parameter_semantic_tags.items()
            },
        }
    return payload


def test_provider_asset_scenarios_match_goldens() -> None:
    assert_golden_scenario("provider_asset__slot_sources")
    assert_golden_scenario("provider_asset__weather_slot_union")
    assert_golden_scenario("provider_asset__slot_rejections")
    assert_golden_scenario("provider_asset__unique_match_repair")
    assert_golden_scenario("provider_asset__bundle_rejections")


@pytest.fixture(scope="module")
def definitions() -> dict[str, TemplateDefinition]:
    return _definitions()


@pytest.fixture(scope="module")
def catalog_contract() -> HybridBodyContract:
    return _catalog_contract()


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
    # CountdownOverviewTravelSupport@1 不再声明 timerIcon 槽位（出行 Support 仅
    # 展示主题与剩余天数），支持模板的可执行素材槽位从 20 收敛为 19。
    assert slot_count == 19


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
    assert len(provider.cases) == 61
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
