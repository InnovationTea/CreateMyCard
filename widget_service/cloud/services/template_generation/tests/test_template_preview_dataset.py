"""Provider Template A2UI 画廊数据集测试。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from services.capability_registry import CapabilityRegistry
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
    validate_preview_asset_paths,
    write_template_preview_dataset,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry


def test_template_preview_dataset_covers_all_business_templates(tmp_path):
    manifest = write_template_preview_dataset(tmp_path)
    cases = manifest.get("cases")
    assert isinstance(cases, list)

    assert manifest.get("templateCount") == 199
    assert manifest.get("sourceTemplateCount") == 204
    missing = manifest.get("missingTemplates")
    assert isinstance(missing, list)
    assert {item.get("templateId") for item in missing} == {
        "BatteryOverviewSupportHero@1", "BatteryOverviewChargeStatusHero@1",
        "ResourceUsageOverviewSupport@1", "ResourceUsageOverviewCompact@1",
        "ResourceUsageOverviewFull@1",
    }
    assert manifest.get("countsByLayout") == {
        "HeroTitle": 1,
        "HeroContent": 1,
        "Support": 20,
        "Compact": 23,
        "Hero": 50,
        "Full": 70,
        "WideHero": 5,
        "WideFull": 26,
        "WideHalf": 3,
    }
    assert manifest.get("countsBySize") == {"2x2": 165, "2x4": 34}
    assert len(cases) == 199
    template_ids: set[str] = set()
    for case in cases:
        template_id = case.get("templateId")
        file_name = case.get("file")
        assert isinstance(template_id, str)
        assert isinstance(file_name, str)
        template_ids.add(template_id)
        assert (tmp_path / file_name).is_file()
    assert len(template_ids) == 199
    assert {
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


def test_weather_wide_previews_use_the_weather_theme_background():
    weather_wide_ids = {
        "WeatherOverviewWideHero@1",
        "WeatherOverviewWideFull@1",
        "WeatherOverviewWideHalf@1",
    }

    cases = {
        case.template_id: case
        for case in build_template_preview_cases()
        if case.template_id in weather_wide_ids
    }

    assert set(cases) == weather_wide_ids
    for case in cases.values():
        components = case.messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        assert root["styles"]["backgroundColor"] == "#FF121259"
        assert root["styles"]["linearGradient"]["colors"] == [
            ["#FF121259", 0],
            ["#FF2B65D9", 1],
        ]


def test_template_preview_assets_are_bundled_by_genui_evaluation():
    cases = build_template_preview_cases()
    paths = validate_preview_asset_paths(cases)
    names = {path.rsplit("/", 1)[-1] for path in paths}

    assert names == {
        "battery_leaf_fill.svg",
        "bell_fill.svg",
        "calendar_fill.svg",
        "clock_fill.svg",
        "earphone_case_16644.svg",
        "drop_1.svg",
        "figure_run.svg",
        "flame_fill.svg",
        "heart_fill.svg",
        "heat_generation.svg",
        "icon_earphone.svg",
        "icon_timing.svg",
        "icon_weather_thermometer.svg",
        "l_circle_fill.svg",
        "location_north_up_right_fill.svg",
        "moon_z_fill_1.svg",
        "music_fill.svg",
        "r_circle_fill.svg",
        "sun_max.svg",
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
        elif case.template_id == "WeatherOverviewTravelSupport@1":
            assert case.primary_data == ()
            assert case.secondary_data == ()
            assert case.optional_data == (
                "/daily/4/condition",
                "/daily/4/temperatureRangeText",
                "/daily/4/rainProbabilityPercent",
                "/current/temperatureC",
                "/current/condition",
            )
        elif case.template_id == "HeartRateOverviewMinMaxFull@1":
            # 平均心率与运动类型为可选数据：存在时平均心率为大字、类型为标签，区间退为辅行。
            assert case.primary_data == (
                "/exerciseHeartRateMax",
                "/exerciseHeartRateMin",
            )
            assert case.secondary_data == ()
            assert case.optional_data == (
                "/exerciseHeartRateAvg", "/exerciseTypeName", "/updatedAt",
            )
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
                "/location/cityCode",
            )
        elif case.template_id == "BluetoothDeviceOverviewMusicCompact@1":
            # 纯歌单入口：不渲染任何耳机数据，三级数据均为空。
            assert case.primary_data == ()
            assert case.secondary_data == ()
            assert case.optional_data == ()
        elif case.business_id == "GenericMetricOverview":
            assert case.primary_data == ()
            assert case.secondary_data == ()
            model = case.messages[2].get("updateDataModel")
            assert isinstance(model, dict)
            value = model.get("value")
            assert isinstance(value, dict)
            data = value.get("data")
            assert isinstance(data, dict)
            health = data.get("healthSport")
            assert isinstance(health, dict)
            assert health.get("dailySteps") == 6200
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
    assert case.optional_data == (
        "/leftBatteryLevel", "/rightBatteryLevel",
        "/leftChargingStatusDesc", "/rightChargingStatusDesc",
    )
    assert "已链接" in json.dumps(case.messages, ensure_ascii=False)
    data_model = case.messages[2]["updateDataModel"]["value"]["data"]["earphone"]
    assert set(data_model) == {
        "isConnected",
        "earphoneName",
        "leftBatteryLevel",
        "rightBatteryLevel",
        "leftChargingStatusDesc",
        "rightChargingStatusDesc",
    }


@pytest.mark.parametrize(
    ("template_id", "icon_name"),
    [
        ("BluetoothDeviceOverviewEarphoneCaseHero@1", "earphone_case_16644.svg"),
        ("BluetoothDeviceOverviewEarphoneHero@1", "icon_earphone.svg"),
        ("BluetoothDeviceOverviewMusicFull@1", "earphone_case_16644.svg"),
    ],
)
def test_earphone_ring_previews_include_required_device_icon(template_id, icon_name):
    variant = get_cardplan_registry().require_variant(template_id, "default")
    assert variant.parameters_schema.get("required") == ["deviceIcon"]
    properties = variant.parameters_schema.get("properties")
    assert isinstance(properties, dict)
    assert set(properties) == {"deviceIcon"}
    case = next(item for item in build_template_preview_cases() if item.template_id == template_id)
    update = case.messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    ring_ids = set()
    icon_ids = set()
    for node in components:
        if node.get("component") == "Progress":
            ring_ids.add(node.get("id"))
        if node.get("component") == "Image":
            assert node.get("src") == f"resources/base/media/{icon_name}"
            styles = node.get("styles")
            assert isinstance(styles, dict)
            assert styles.get("width") == 20
            assert styles.get("height") == 20
            icon_ids.add(node.get("id"))
    assert len(icon_ids) == 1
    assert len(ring_ids) == 1
    for node in components:
        if node.get("component") != "Stack":
            continue
        children = node.get("children", [])
        if icon_ids.issubset(children):
            assert ring_ids.issubset(children)
            break
    else:
        pytest.fail("图标必须与电量环位于同一个 Stack")


def test_battery_2x2_icon_contracts_and_previews_are_required():
    registry = get_cardplan_registry()
    covered = set()
    for case in build_template_preview_cases():
        if case.business_id != "BatteryOverview" or case.size != "2x2":
            continue
        if case.layout_kind not in ("Full", "Hero", "Compact"):
            continue
        variant = registry.require_variant(case.template_id, "default")
        properties = variant.parameters_schema.get("properties")
        assert isinstance(properties, dict)
        if "batteryIcon" not in properties:
            continue
        assert "batteryIcon" in variant.parameters_schema.get("required", [])
        update = case.messages[1].get("updateComponents")
        assert isinstance(update, dict)
        components = update.get("components")
        assert isinstance(components, list)
        images = []
        for node in components:
            if node.get("component") == "Image":
                images.append(node)
        assert len(images) == 1, case.template_id
        image = images[0]
        assert image.get("src") == "resources/base/media/battery_leaf_fill.svg"
        covered.add(case.template_id)
    assert len(covered) == 10


def test_battery_wide_and_support_icons_remain_optional():
    registry = get_cardplan_registry()
    for template_id in (
        "BatteryOverviewWideFull@1",
        "BatteryOverviewChargingDiagnosticsWideFull@1",
        "BatteryOverviewStatusWideFull@1",
        "BatteryOverviewSupport@1",
        "BatteryOverviewStatusSupport@1",
    ):
        variant = registry.require_variant(template_id, "default")
        assert "batteryIcon" not in variant.parameters_schema.get("required", [])


def test_template_preview_only_references_current_registered_assets():
    capabilities_path = (
        Path(__file__).resolve().parents[3]
        / "data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json"
    )
    capabilities = json.loads(capabilities_path.read_text(encoding="utf-8"))
    registered = {asset.get("src") for asset in capabilities}
    cases = build_template_preview_cases()
    assert validate_preview_asset_paths(cases).issubset(registered)
    registry = CapabilityRegistry(version="app-11.7.5.205_rom-6.0")
    available_data = {item.id for item in registry.list_data_capabilities()}
    assert all(case.capability_id in available_data for case in cases)
    support = next(case for case in cases if case.template_id == "BatteryOverviewSupport@1")
    update = support.messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    assert all(node.get("component") != "Image" for node in components)


def test_template_preview_actions_are_bound_registered_events():
    cases = build_template_preview_cases()
    required_events = {
        "BluetoothDeviceOverviewMusicCompact@1": "event.open.music.daily",
        "BluetoothDeviceOverviewEarbudsChargingWideFull@1": "event.open.settings.bluetooth",
    }
    bound_handlers = {}
    for case in cases:
        update = case.messages[1].get("updateComponents")
        assert isinstance(update, dict)
        components = update.get("components")
        assert isinstance(components, list)
        for component in components:
            handlers = component.get("onClick", [])
            assert isinstance(handlers, list)
            for handler in handlers:
                assert handler.get("call") != "sendToAssistant"
                if case.template_id not in required_events:
                    raise AssertionError(f"unexpected optional action: {case.template_id}")
                assert case.template_id not in bound_handlers
                bound_handlers[case.template_id] = handler
    registry = CapabilityRegistry(version="app-11.7.5.205_rom-6.0")
    assert set(bound_handlers) == set(required_events)
    for template_id, event_id in required_events.items():
        event = registry.get_event_capability(event_id)
        assert event is not None
        assert bound_handlers.get(template_id) == event.actionTemplate.model_dump()
