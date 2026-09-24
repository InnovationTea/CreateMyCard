"""Provider Template A2UI 画廊数据集测试。

纯输出契约已固化为场景金样（Layer C）：``preview_dataset__data_tiers``
冻结 7 个关键模板的 primary/secondary/optional 数据分层目录（数据分层
驱动槽位绑定与条件省略），``preview_dataset__bundled_assets`` 冻结预览
引用的全部端侧媒体资产名集合。其余保持普通门禁：113 用例计数钉与
countsByLayout/countsBySize、surface 骨架不变量、数据分层互斥不变量、
多云天气单业务不用温度计图标、耳机 Hero 标题参数化。资产集合或数据
分层变化时按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
    validate_preview_asset_paths,
    write_template_preview_dataset,
)
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_DATA_TIER_CATALOG_TEMPLATE_IDS: tuple[str, ...] = (
    "BatteryOverviewSupport@1",
    "BluetoothDeviceOverviewChargeSupport@1",
    "BluetoothDeviceOverviewConnectionSupport@1",
    "HeartRateOverviewMinMaxFull@1",
    "WeatherOverviewHeroTitle@1",
    "WeatherOverviewTemperatureSupport@1",
    "WeatherOverviewTravelSupport@1",
)


def test_template_preview_dataset_covers_all_business_templates(tmp_path):
    manifest = write_template_preview_dataset(tmp_path)
    cases = manifest.get("cases")
    assert isinstance(cases, list)

    assert manifest.get("templateCount") == 114
    assert manifest.get("countsByLayout") == {
        "HeroTitle": 1,
        "HeroContent": 1,
        "Support": 21,
        "Compact": 12,
        "Hero": 33,
        "Full": 37,
        "WideHero": 1,
        "WideFull": 8,
    }
    assert manifest.get("countsBySize") == {"2x2": 105, "2x4": 9}
    assert len(cases) == 114
    template_ids: set[str] = set()
    for case in cases:
        template_id = case.get("templateId")
        file_name = case.get("file")
        assert isinstance(template_id, str)
        assert isinstance(file_name, str)
        template_ids.add(template_id)
        assert (tmp_path / file_name).is_file()
    assert len(template_ids) == 114
    assert {
        "BluetoothDeviceOverviewEarbudTripleFull@1",
        "BluetoothDeviceOverviewEarbudTripleHero@1",
    }.issubset(template_ids)


def test_template_preview_a2ui_has_surface_components_and_data():
    cases = build_template_preview_cases()

    for case in cases:
        assert len(case.messages) == 3
        assert "createSurface" in case.messages[0]
        assert "updateComponents" in case.messages[1]
        assert "updateDataModel" in case.messages[2]
        update_components = case.messages[1]["updateComponents"]
        assert update_components["root"] == "root"
        components = update_components["components"]
        root = next(component for component in components if component["id"] == "root")
        assert root["component"] == "Column"
        assert root["children"] == ["template_root"]
        slot = next(
            component
            for component in components
            if component["id"] == "template_root"
        )
        assert slot["styles"]["height"] == case.content_height_vp


def test_template_preview_manifest_data_tiers_are_disjoint():
    cases = build_template_preview_cases()

    for case in cases:
        counts = Counter((*case.primary_data, *case.secondary_data, *case.optional_data))
        assert all(count == 1 for count in counts.values())
        if case.template_id not in _DATA_TIER_CATALOG_TEMPLATE_IDS:
            assert case.primary_data
        assert json.dumps(case.messages, ensure_ascii=False)


def test_cloudy_weather_preview_does_not_use_thermometer_for_single_business():
    single_template_ids = {
        "WeatherOverviewCompact@1", "WeatherOverviewUvCompact@1",
        "WeatherOverviewHero@1", "WeatherOverviewFull@1",
    }
    checked: set[str] = set()
    for case in build_template_preview_cases():
        if case.template_id not in single_template_ids:
            continue
        checked.add(case.template_id)
        update = case.messages[1].get("updateComponents")
        assert isinstance(update, dict)
        components = update.get("components")
        assert isinstance(components, list)
        assert not any(component.get("component") == "Image" for component in components)
        model = case.messages[2].get("updateDataModel")
        assert isinstance(model, dict)
        value = model.get("value")
        assert isinstance(value, dict)
        data = value.get("data")
        assert isinstance(data, dict)
        weather = data.get("weather")
        assert isinstance(weather, dict)
        current = weather.get("current")
        assert isinstance(current, dict)
        assert current.get("condition") == "多云"
    assert checked == single_template_ids


def test_earphone_hero_uses_title_parameter_without_title_binding():
    case = next(
        item
        for item in build_template_preview_cases()
        if item.template_id == "BluetoothDeviceOverviewHero@1"
    )

    assert case.primary_data == ("/isConnected", "/earphoneName")
    assert case.secondary_data == ()
    assert case.optional_data == ("/leftBatteryLevel", "/rightBatteryLevel")
    assert "已链接" in json.dumps(case.messages, ensure_ascii=False)
    data_model = case.messages[2]["updateDataModel"]["value"]["data"]["earphone"]
    assert set(data_model) == {
        "isConnected",
        "earphoneName",
        "leftBatteryLevel",
        "rightBatteryLevel",
    }


@scenario("preview_dataset__data_tiers")
def _build_data_tier_catalog() -> dict[str, Any]:
    cases_by_template_id = {
        case.template_id: case for case in build_template_preview_cases()
    }
    return {
        template_id: {
            "primary": list(cases_by_template_id[template_id].primary_data),
            "secondary": list(cases_by_template_id[template_id].secondary_data),
            "optional": list(cases_by_template_id[template_id].optional_data),
        }
        for template_id in _DATA_TIER_CATALOG_TEMPLATE_IDS
    }


@scenario("preview_dataset__bundled_assets")
def _build_bundled_assets() -> dict[str, Any]:
    paths = validate_preview_asset_paths(build_template_preview_cases())
    return {"assetNames": sorted(path.rsplit("/", 1)[-1] for path in paths)}


def test_preview_dataset_scenarios_match_goldens() -> None:
    assert_golden_scenario("preview_dataset__data_tiers")
    assert_golden_scenario("preview_dataset__bundled_assets")
