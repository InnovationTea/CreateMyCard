"""Provider Template A2UI 画廊数据集测试。"""

from __future__ import annotations

import json
from collections import Counter

from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
    validate_preview_asset_paths,
    write_template_preview_dataset,
)


def test_template_preview_dataset_covers_all_business_templates(tmp_path):
    manifest = write_template_preview_dataset(tmp_path)
    cases = manifest["cases"]

    assert manifest["templateCount"] == 107
    assert manifest["countsByLayout"] == {
        "HeroTitle": 1,
        "HeroContent": 1,
        "Support": 19,
        "Compact": 13,
        "Hero": 31,
        "Full": 31,
        "WideHero": 2,
        "WideFull": 9,
    }
    assert manifest["countsBySize"] == {"2x2": 96, "2x4": 11}
    assert len(cases) == 107
    assert len({case["templateId"] for case in cases}) == 107
    assert all((tmp_path / case["file"]).is_file() for case in cases)


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


def test_template_preview_assets_are_bundled_by_genui_evaluation():
    cases = build_template_preview_cases()
    paths = validate_preview_asset_paths(cases)
    names = {path.rsplit("/", 1)[-1] for path in paths}

    assert names == {
        "battery_leaf_fill.svg",
        "calendar_fill.svg",
        "clock_fill.svg",
        "earphone_case_16644.svg",
        "externaldrive_fill.svg",
        "figure_run.svg",
        "flame_fill.svg",
        "heart_fill.svg",
        "heat_generation.svg",
        "icon_earphone.svg",
        "icon_phone.svg",
        "icon_tiktok.png",
        "l_circle_fill.svg",
        "location_north_up_right_fill.svg",
        "moon_z_fill_1.svg",
        "r_circle_fill.svg",
    }


def test_template_preview_manifest_data_tiers_are_disjoint():
    cases = build_template_preview_cases()

    for case in cases:
        counts = Counter((*case.primary_data, *case.secondary_data, *case.optional_data))
        assert all(count == 1 for count in counts.values())
        if case.template_id == "WeatherOverviewHeroTitle@1":
            assert case.primary_data == ()
            assert case.secondary_data == ()
            assert case.optional_data == (
                "/location/prefectureName", "/location/districtName",
                "/current/temperatureText", "/current/condition",
            )
        elif case.template_id == "HeartRateOverviewMinMaxFull@1":
            assert case.primary_data == (
                "/exerciseHeartRateMax",
                "/exerciseHeartRateMin",
            )
            assert case.secondary_data == ()
            assert case.optional_data == ("/updatedAt",)
        elif case.template_id == "BatteryOverviewSupport@1":
            # 充电状态与电池温度为可选数据：辅行充电优先、温度回退，电量环仍由数值电量驱动。
            assert case.primary_data == ("/batterySOC",)
            assert case.secondary_data == ()
            assert case.optional_data == (
                "/chargingStatusDesc", "/batterySOCText", "/batteryTemperatureText",
            )
        elif case.template_id == "BluetoothDeviceOverviewChargeSupport@1":
            # 电量改为可选数据：充电状态为唯一必选主字段，电量文本与电量环按条件省略。
            assert case.primary_data == ()
            assert case.secondary_data == ("/chargingStatusDesc",)
            assert case.optional_data == ("/batteryLevel",)
        elif case.template_id == "BluetoothDeviceOverviewConnectionSupport@1":
            # 连接状态为必选主数据，仓电量为可选：缺失时按条件分支省略电量行与电量环。
            assert case.primary_data == ("/isConnected",)
            assert case.secondary_data == ()
            assert case.optional_data == ("/batteryLevel",)
        elif case.template_id == "WeatherOverviewTemperatureSupport@1":
            # 天气现象为唯一必选主字段，城市、温度文本、摄氏度数值与体感温度可选。
            assert case.primary_data == ("/current/condition",)
            assert case.secondary_data == ()
            assert case.optional_data == (
                "/current/temperatureText", "/current/temperatureC",
                "/current/feelsLikeC",
                "/location/prefectureName", "/location/districtName",
            )
        else:
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
