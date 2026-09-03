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

    assert manifest["templateCount"] == 69
    assert manifest["countsByLayout"] == {
        "HeroTitle": 1,
        "HeroContent": 1,
        "Support": 12,
        "Compact": 11,
        "Hero": 18,
        "Full": 15,
        "WideHero": 2,
        "WideFull": 9,
    }
    assert manifest["countsBySize"] == {"2x2": 58, "2x4": 11}
    assert len(cases) == 69
    assert len({case["templateId"] for case in cases}) == 69
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
        "icon_earphone.svg",
        "icon_tiktok.png",
        "icon_weather1.svg",
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
        else:
            assert case.primary_data
        assert json.dumps(case.messages, ensure_ascii=False)


def test_earphone_hero_uses_title_parameter_without_title_binding():
    case = next(
        item
        for item in build_template_preview_cases()
        if item.template_id == "BluetoothDeviceOverviewHero@1"
    )

    assert case.primary_data == ("/isConnected", "/earphoneName")
    assert case.secondary_data == ("/leftBatteryLevel", "/rightBatteryLevel")
    assert case.optional_data == ()
    assert "已连接" in json.dumps(case.messages, ensure_ascii=False)
    data_model = case.messages[2]["updateDataModel"]["value"]["data"]["earphone"]
    assert set(data_model) == {
        "isConnected",
        "earphoneName",
        "leftBatteryLevel",
        "rightBatteryLevel",
    }
