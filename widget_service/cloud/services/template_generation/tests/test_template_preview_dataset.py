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

    assert manifest["templateCount"] == 74
    assert manifest["countsByLayout"] == {
        "HeroTitle": 1,
        "HeroContent": 1,
        "Support": 12,
        "Compact": 11,
        "Hero": 18,
        "Full": 15,
        "WideHero": 6,
        "WideFull": 10,
    }
    assert manifest["countsBySize"] == {"2x2": 58, "2x4": 16}
    assert len(cases) == 74
    assert len({case["templateId"] for case in cases}) == 74
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
        "bell_fill.svg",
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


def test_calendar_upcoming_summary_widefull_matches_q057_hierarchy():
    case = next(
        item
        for item in build_template_preview_cases()
        if item.template_id == "ScheduleOverviewUpcomingSummaryWideFull@1"
    )

    assert case.primary_data == (
        "/eventCount",
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/isAllDay",
    )
    assert case.secondary_data == ()
    assert case.optional_data == ()
    components = case.messages[1]["updateComponents"]["components"]
    header = next(component for component in components if component.get("content") == "近日安排")
    count = next(
        component
        for component in components
        if component.get("content") == "{{ ${/data/calendar/eventCount} }}"
    )
    calendar_icon = next(
        component
        for component in components
        if component.get("src") == "resources/base/media/calendar_fill.svg"
    )
    all_day = next(
        component
        for component in components
        if "isAllDay" in str(component.get("content", ""))
    )

    assert case.size == "2x4"
    assert case.content_height_vp == 136
    assert header["styles"]["fontSize"] == 12
    assert calendar_icon["styles"]["width"] == 20
    assert calendar_icon["styles"]["height"] == 20
    assert count["styles"]["fontSize"] == 20
    assert not any(component.get("component") == "Divider" for component in components)
    assert "全天日程" in all_day["content"]
    data_model = case.messages[2]["updateDataModel"]["value"]["data"]["calendar"]
    assert set(data_model) == {"eventCount", "events"}
    assert set(data_model["events"][0]) == {"title", "dtStart", "isAllDay"}


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


def test_q059_q067_q073_q077_widehero_templates_match_input_contracts():
    cases = {case.template_id: case for case in build_template_preview_cases()}
    expected = {
        "BluetoothDeviceOverviewEarbudsMusicWideHero@1": (
            "/isConnected",
            "/earphoneName",
            "/batteryLevel",
            "/updatedAt",
        ),
        "ScheduleOverviewMeetingReminderWideHero@1": (
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/eventLocation",
            "/events/0/remindTime/0",
        ),
        "BluetoothDeviceOverviewEarbudsChargingWideHero@1": (
            "/isConnected",
            "/earphoneName",
            "/batteryLevel",
            "/chargingStatusDesc",
            "/leftBatteryLevel",
            "/leftChargingStatusDesc",
            "/rightBatteryLevel",
            "/rightChargingStatusDesc",
        ),
        "ScheduleOverviewMeetingJoinWideHero@1": (
            "/events/0/dtStart",
            "/events/0/eventLocation",
            "/events/0/senderName",
            "/events/0/oneClickServiceLink",
        ),
    }

    for template_id, primary_data in expected.items():
        case = cases[template_id]
        assert case.size == "2x4"
        assert case.content_height_vp == 124
        assert case.primary_data == primary_data
        assert case.secondary_data == ()
        assert case.optional_data == ()

    music = json.dumps(
        cases["BluetoothDeviceOverviewEarbudsMusicWideHero@1"].messages,
        ensure_ascii=False,
    )
    reminder = json.dumps(
        cases["ScheduleOverviewMeetingReminderWideHero@1"].messages,
        ensure_ascii=False,
    )
    charging = json.dumps(
        cases["BluetoothDeviceOverviewEarbudsChargingWideHero@1"].messages,
        ensure_ascii=False,
    )
    meeting = json.dumps(
        cases["ScheduleOverviewMeetingJoinWideHero@1"].messages,
        ensure_ascii=False,
    )

    assert "耳机听歌" in music
    assert "充电盒电量" in music
    assert "更新于" in music
    assert "earphone_case_16644.svg" in music
    assert '"component": "Progress"' not in music
    assert '"fontSize": 16' in music
    assert '"fontSize": 14' in music
    assert "公司会议" in reminder
    assert "分钟提醒" in reminder
    assert "calendar_fill.svg" in reminder
    assert "bell_fill.svg" in reminder
    assert "location_north_up_right_fill.svg" in reminder
    assert reminder.count('"component": "Divider"') == 2
    assert '"itemMargin": 2' in reminder
    assert charging.count('"component": "Progress"') == 1
    assert '"component": "Divider"' not in charging
    assert "leftChargingStatusDesc" in charging
    assert "rightChargingStatusDesc" in charging
    assert '"component": "Divider"' not in music
    assert "需求评审" in meeting
    assert "calendar_fill.svg" in meeting
    assert meeting.count('"component": "Divider"') == 2
    assert '"itemMargin": 2' in meeting
    assert "发起人" in meeting
    assert "支持一键入会" in meeting
