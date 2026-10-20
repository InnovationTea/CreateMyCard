"""T6电量与音乐分流只读现有布局，不推测尺寸、不以关键词代替可见数据。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.compact_dsl_a2ui_converter import ComponentRow
from services.theme_content_regions import photo_layout_evidence
from services.theme_photo_eligibility import _clickable_button_count, _has_ring_progress
from test_autumn_calendar_photos import expanded, photo, rejection
from test_metronome_photo import ACTION, IDENTITY, VIOLIN, earphone_sample, music_sample

SQUARES = ["photo-ux-bulb-battery-square", "photo-ux-green-bulb-battery-square"]
WIDE = "photo-ux-green-bulb-battery-wide"
BATTERY_PATH = "/data/phoneBattery/batteryLevel"


def battery_sample():
    sample = earphone_sample()
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    task = {"size": "2x2", "userQuery": "手机电量和设置", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"phoneBattery": {}}}}
    compact = json.dumps(rows).replace("/data/earphone/earphoneBatteryLevel", BATTERY_PATH)
    return expanded(json.loads(compact), task)


@pytest.mark.parametrize("identity", SQUARES)
@pytest.mark.parametrize("lines,allowed", [(1, True), (2, False), (None, False)])
def test_square_battery_three_lines_include_button_exclude_header(identity, lines, allowed):
    sample = battery_sample()
    body = next(node for node in sample.nodes if node.get("id") == "reading_main")
    body.get("styles", {})["maxLines"] = lines
    assert (rejection(sample, identity) is None) is allowed


@pytest.mark.parametrize("identity", SQUARES)
@pytest.mark.parametrize("alignment", ["start", "center", "end"])
def test_square_battery_allows_buttons_icons_and_any_alignment(identity, alignment):
    sample = battery_sample()
    body = next(node for node in sample.nodes if node.get("id") == "reading_main")
    body.get("styles", {})["textAlign"] = alignment
    assert rejection(sample, identity) is None


@pytest.mark.parametrize("identity", [*SQUARES, WIDE])
@pytest.mark.parametrize("replacement", ["earphone", "weather", "static"])
def test_battery_requires_visible_phone_battery_not_request_or_unused_schema(identity, replacement):
    sample = battery_sample()
    if identity == WIDE:
        sample = wide_battery_sample("W-content-side-slots")
    if replacement == "static":
        sample.compact = sample.compact.replace('"path":', '"literal":')
    else:
        sample.compact = sample.compact.replace("/data/phoneBattery/", f"/data/{replacement}/")
    assert rejection(sample, identity) == "电量图片需要实际展示手机电量相关数据"


def wide_battery_sample(layout):
    children = ["main", "upper", "lower"]
    rows = [
        ["root", "Layout", {"layout": layout}, children],
        ["main", "Region", {"variant": "title-content"}, ["header", "reading"]],
        ["header", "SingleLineTitle", {"title": "设备电量"}],
        ["reading", "EmphasisText", {"mainText": {"path": BATTERY_PATH}}],
        ["upper", "InfoBlock", {"variant": "slot", "primaryText": "正常",
                                "secondaryText": "电池状态"}],
        ["lower", "CardButton", {"label": "设置", "onClick": ACTION}],
        [BATTERY_PATH, 68],
    ]
    if layout == "W-split-panels":
        children[:] = ["main", "other"]
        rows.extend([
            ["other", "Region", {"variant": "title-content"}, ["weather", "temperature"]],
            ["weather", "SingleLineTitle", {"title": "天气"}],
            ["temperature", "EmphasisText", {
                "mainText": {"path": "/data/weather/temperature"}}],
            ["/data/weather/temperature", 29],
        ])
        rows = [row for row in rows if row[0] not in {"upper", "lower"}]
    task = {"size": "2x4", "userQuery": "手机电量和天气", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"phoneBattery": {}, "weather": {}}}}
    return expanded(rows, task)


@pytest.mark.parametrize("layout", ["W-content-side-slots", "W-split-panels"])
@pytest.mark.parametrize("lines", [1, 3, 4, None])
def test_wide_battery_requires_left_focus_up_to_three_lines(layout, lines):
    sample = wide_battery_sample(layout)
    node = next(node for node in sample.nodes if node.get("id") == "reading_main")
    node.get("styles", {})["maxLines"] = lines
    allowed = layout == "W-content-side-slots" and lines in {1, 3}
    assert (rejection(sample, WIDE) is None) is allowed
    assert photo(WIDE).get("subjectlessLayout") == {
        "layout": "W-content-side-slots", "orientation": "content-left"}


@pytest.mark.parametrize("lines,allowed", [(1, True), (2, True), (3, False), (None, False)])
def test_violin_four_body_lines_limit(lines, allowed):
    sample = earphone_sample()
    body = next(node for node in sample.nodes if node.get("id") == "reading_main")
    body.get("styles", {})["maxLines"] = lines
    assert (rejection(sample, VIOLIN) is None) is allowed
    assert rejection(sample, IDENTITY) is not None


@pytest.mark.parametrize("change", ["no-event", "one-button", "root-click", "orphan", "third"])
def test_metronome_counts_reachable_clickable_buttons_not_events_or_root(change):
    sample = music_sample()
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    favorite = next(row for row in rows if row[0] == "favorite")
    if change == "no-event":
        favorite[2].pop("onClick")
    elif change in {"one-button", "root-click", "orphan"}:
        rows[0][3].remove("favorite")
        daily = next(row for row in rows if row[0] == "daily")
        daily[2]["onClick"] = ACTION * 2
        if change == "root-click":
            rows[0][2]["onClick"] = ACTION
        if change != "orphan":
            rows.remove(favorite)
    else:
        rows[0][3].append("third")
        rows.append(["third", "PillButton", {"label": "音乐", "onClick": ACTION}])
    sample.compact = "\n".join(json.dumps(row) for row in rows)
    if change == "orphan":
        assert rejection(sample, IDENTITY) == "无法解析图片内容限制所需的定稿布局"
        assert rejection(sample, VIOLIN) is not None
    else:
        assert rejection(sample, IDENTITY) == "节拍器图片要求恰好两个可点击按钮"
        assert rejection(sample, VIOLIN) is None


@pytest.mark.parametrize("kind", ["PillButton", "CircleButton", "CardButton"])
def test_metronome_recognizes_each_semantic_button_type(kind):
    sample = music_sample()
    sample.compact = sample.compact.replace("PillButton", kind)
    assert rejection(sample, IDENTITY) is None
    assert rejection(sample, VIOLIN) is not None


def test_button_counter_handles_native_button_without_counting_decorations():
    rows = [
        ComponentRow("first", "Button", {"onClick": ACTION}, []),
        ComponentRow("second", "Button", {"onClick": ACTION * 2}, []),
        ComponentRow("decoration", "Image", {}, []),
        ComponentRow("root", "Layout", {"onClick": ACTION}, []),
        ComponentRow("disabled", "Button", {}, []),
    ]
    assert _clickable_button_count(rows) == 2


@pytest.mark.parametrize("identity", [*SQUARES, WIDE, VIOLIN])
@pytest.mark.parametrize("enabled", [False, True])
def test_new_photos_respect_switch_and_preserve_foreground(monkeypatch, identity, enabled):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    if identity in SQUARES:
        monkeypatch.setattr(themes.secrets, "choice", Mock(return_value=identity))
    if identity == WIDE:
        sample = wide_battery_sample("W-content-side-slots")
    else:
        sample = earphone_sample() if identity == VIOLIN else battery_sample()
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": identity})))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert (audit.get("themeId") == identity) is enabled
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)
    address = photo(identity).get("remoteUrl")
    assert isinstance(address, str)
    assert address.startswith("https://")
    assert photo(identity).get("content", {}).get("roles", {}).get("primary") == "#FFFFFFFF"


@pytest.mark.parametrize("identity", [*SQUARES, WIDE, VIOLIN, IDENTITY])
@pytest.mark.parametrize("change", ["size", "business", "policy"])
def test_registry_checks_t6_business_size_and_policy(identity, change):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == identity)
    if change == "size":
        entry["sizes"] = ["2x2"] if identity == WIDE else ["2x4"]
        entry.get("content", {})["panelBySize"] = {"2x2": "#33FFFFFF", "2x4": "#33FFFFFF"}
    elif change == "business":
        entry["business"] = "sleep"
    else:
        entry.get("contentEligibility", {})["maxTextLines"] = 9
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_new_images_keep_existing_palette_and_default_enabled():
    reference = photo("photo-ux-sleep-square").get("content")
    for identity in [*SQUARES, VIOLIN]:
        assert photo(identity).get("content") == reference
    config = registry.load_theme_registry()
    assert config.get("photoSurfaceStyle") == {"backdropBlur": {"radius": 20}}
    field = type(get_settings()).model_fields.get("enable_photo_background_theme")
    assert field is not None and field.default is True
    assert "photo-ux-geometry-calendar-square" not in {
        item.get("id") for item in config.get("themes", [])}


def test_two_buttons_do_not_depend_on_any_text_flow_evidence():
    sample = music_sample()
    evidence = photo_layout_evidence(sample.nodes)
    evidence.pop("textFlow")
    reason = themes.photo_reason(photo(IDENTITY), sample.task, evidence,
                                 final_layout=sample.compact)
    assert reason is None


@pytest.mark.parametrize("kind,props,expected", [
    ("ProgressCircle", {}, True),
    ("ProgressCircleSingle", {}, True),
    ("Progress", {"type": "ring"}, True),
    ("Progress", {"type": "linear"}, False),
    ("InfoBlock", {"visual": {"type": "progressCircle"}}, True),
    ("InfoBlock", {"visual": {"type": "icon"}}, False),
    ("CircleButton", {"onClick": ACTION}, False),
    ("Image", {}, False),
])
def test_ring_detection_does_not_reject_icons_or_round_buttons(kind, props, expected):
    assert _has_ring_progress([ComponentRow("visual", kind, props, [])]) is expected


@pytest.mark.parametrize("identity", SQUARES)
@pytest.mark.parametrize("kind", ["ProgressCircleSingle", "InfoBlock"])
def test_square_battery_rejects_rings_in_actual_expanded_layout(identity, kind):
    props = {"value": {"path": BATTERY_PATH}, "total": 100,
             "displayValue": {"path": BATTERY_PATH}, "label": "电量",
             "icon": "resources/base/media/battery_leaf_fill.svg"}
    if kind == "InfoBlock":
        props = {"primaryText": {"path": BATTERY_PATH}, "secondaryText": "电量",
                 "visual": {"type": "progressCircle",
                            "icon": "resources/base/media/battery_leaf_fill.svg"}}
    task = {"size": "2x2", "userQuery": "电量", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"phoneBattery": {}}}}
    rows = [
        ["root", "Layout", {"layout": "S-title-content"}, ["header", "reading"]],
        ["header", "SingleLineTitle", {"title": "电量"}],
        ["reading", kind, props], [BATTERY_PATH, 68],
    ]
    if kind == "InfoBlock":
        rows = [
            ["root", "Layout", {"layout": "S-dual-info"}, ["reading", "other"]],
            ["reading", kind, props],
            ["other", "InfoBlock", {"primaryText": "正常", "secondaryText": "电池状态"}],
            [BATTERY_PATH, 68],
        ]
    sample = expanded(rows, task)
    assert rejection(sample, identity) == "方版电量图片不允许环状进度条"


def test_wide_battery_still_allows_ring_inside_info_block():
    sample = wide_battery_sample("W-content-side-slots")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    upper = next(row for row in rows if row[0] == "upper")
    upper[2].update(primaryText={"path": BATTERY_PATH}, visual={
        "type": "progressCircle", "icon": "resources/base/media/battery_leaf_fill.svg"})
    sample = expanded(rows, sample.task)
    assert rejection(sample, WIDE) is None


@pytest.mark.parametrize("chosen", SQUARES)
@pytest.mark.parametrize("model_choice", [*SQUARES, "gradient-blue", "invalid-json"])
def test_battery_uniform_choice_is_independent_of_model(monkeypatch, chosen, model_choice):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    chooser = Mock(return_value=chosen)
    monkeypatch.setattr(themes.secrets, "choice", chooser)
    sample = battery_sample()
    raw = model_choice if model_choice == "invalid-json" else json.dumps({"themeId": model_choice})
    client = SimpleNamespace(generate=AsyncMock(return_value=raw))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    chooser.assert_called_once_with(SQUARES)
    assert audit.get("themeId") == chosen
    assert set(audit.get("candidates", [])) == set(SQUARES)
    assert audit.get("photoSelection", {}).get("selected") == chosen
    assert themes.foreground_signature(result) == themes.foreground_signature(sample.source)


def test_battery_pair_has_same_policy_palette_and_equal_probability_group():
    warm = photo(SQUARES[0])
    green = photo(SQUARES[1])
    assert warm.get("contentEligibility") == green.get("contentEligibility")
    assert warm.get("content") == green.get("content")
    groups = registry.load_theme_registry().get("photoSelectionGroups", [])
    group = next(item for item in groups if item.get("id") == "battery-square")
    assert group == {"id": "battery-square", "mode": "uniform", "themeIds": SQUARES}
