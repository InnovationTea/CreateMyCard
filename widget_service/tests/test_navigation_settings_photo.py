"""导航与设置入口接入蓝色抽象图，不改变数据业务、布局和最终交付门禁。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.capability_registry import CapabilityRegistry
from services.compact_dsl_a2ui_converter import ComponentRow
from services.protocol_registry import A2UIProtocolRegistry
from services.theme_texture_eligibility import visible_business
from services.validator import ArtifactValidator
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import ACTION, choose, evidence, rejection, sample
from theme_preference_samples import preference, reply

BLUE = "photo-ux-texture-blue-"
NAVIGATION = "event.startNavigate"
SETTINGS = "event.open.settings.storage"
CAPABILITIES = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
SETTING_EVENTS = [
    "event.open.settings.dnd", "event.open.settings.bluetooth", "event.open.settings.battery",
    "event.open.settings.batteryHealth", "event.open.settings.parentControl", SETTINGS,
    "event.open.settings.dndMode", "event.open.settings.sleepMode", "event.open.settings.studyMode",
    "event.open.settings.mobileNetwork", "event.open.settings.wifi",
    "event.open.settings.mobileData", "event.open.settings.simManagement",
    "event.open.settings.hotspot", "event.open.settings.dataUsage",
    "event.open.settings.darkMode", "event.setPowerSavingMode", "event.setNearLinkMode",
    "event.setBluetoothMode", "event.setWifiMode", "event.setMobileData", "event.setLocationSwitch",
    "event.setScreenUseTimeManageSwitch", "event.setMicPermissionSwitch", "event.setSoundMode",
    "event.openFlashlight", "event.closeFlashlight",
]


def action(event_id):
    capability = CAPABILITIES.get_event_capability(event_id)
    assert capability is not None
    return capability.actionTemplate.model_dump(mode="json")


def entry_sample(event_id, lines=3, wide=False):
    saved = sample(lines=lines, wide=wide)
    rows = themes.decode(saved.compact)
    rows = [row for row in rows if not row[0].startswith("/")]
    reading = next(row for row in rows if row[0] == "reading")
    reading[2]["content"] = "\n".join(["快捷入口"] * lines)
    button = next(row for row in rows if row[0] == "button")
    button[2]["onClick"] = [action(event_id)]
    return expanded(rows, saved.task)


@pytest.mark.parametrize("event_id", SETTING_EVENTS)
def test_registered_setting_entries_and_system_controls_are_one_business(event_id):
    rows = [ComponentRow("entry", "PillButton", {"onClick": [action(event_id)]})]
    assert visible_business(rows) == "settings"


def test_navigation_and_music_remain_separate_action_businesses():
    rows = [ComponentRow("entry", "PillButton", {"onClick": [action(NAVIGATION)]})]
    assert visible_business(rows) == "navigation"
    rows[0].props["onClick"] = ACTION
    assert visible_business(rows) == "music"


@pytest.mark.parametrize("handlers", [
    [], None, {}, [None], [{"args": []}], [{"call": [], "args": {"intentName": "Settings"}}],
    [{"call": "clickToIntent", "args": {"intentName": []}}],
    [{"call": "clickToDeeplink", "args": {"intentName": "StartNavigate"}}],
    [{"call": "clickToIntent", "args": {"intentName": "UnknownSetting"}}],
    [{"call": "clickToDeeplink", "args": {"intentName": "Settings", "bundleName": "other"}}],
    [{"call": "clickToIntent", "args": {"intentName": "EnterSettingPage", "params": []}}],
    [{"call": "clickToIntent", "args": {"intentName": "SetSettingOption", "params": {
        "appBundleName": "other", "itemName": "volume_mode",
    }}}],
    [{"call": "clickToIntent", "args": {"intentName": "SetSettingSwitch", "params": {
        "appBundleName": "com.huawei.hmos.settings", "itemName": "unknown",
    }}}],
])
def test_missing_unknown_or_malformed_actions_cannot_infer_business(handlers):
    rows = [ComponentRow("entry", "Text", {"content": "导航设置", "onClick": handlers})]
    assert visible_business(rows) is None


@pytest.mark.parametrize("other", [NAVIGATION, "event.open.music", "event.call.phone"])
def test_different_action_businesses_do_not_become_single_business(other):
    second = ACTION[0] if other == "event.open.music" else action(other)
    rows = [ComponentRow("entry", "PillButton", {"onClick": [action(SETTINGS), second]})]
    assert visible_business(rows) is None


def test_multiple_settings_are_one_business_but_malformed_action_is_not_ignored():
    handlers = [action(SETTINGS), action("event.setWifiMode"), action("event.setBluetoothMode")]
    rows = [ComponentRow("entry", "PillButton", {"onClick": handlers})]
    assert visible_business(rows) == "settings"
    handlers.append(None)
    assert visible_business(rows) is None


@pytest.mark.parametrize("event_id", [NAVIGATION, SETTINGS])
@pytest.mark.parametrize("path,business", [
    ("/data/weather/current/temperature", "weather"),
    ("/data/phoneBattery/batteryLevel", "battery"),
    ("/data/dailyUsage/mostUsedApps/0/totalDuration", "app-usage"),
    ("/data/healthSport/nightSleepDurationText", "sleep"),
    ("/data/currentTime/currentDate", "calendar"),
    ("/data/navigation/unknown", None),
    ("/data/settings/unknown", None),
])
def test_visible_data_keeps_its_business_instead_of_action_business(event_id, path, business):
    rows = [ComponentRow("entry", "Text", {
        "content": {"path": path}, "onClick": [action(event_id)],
    })]
    assert visible_business(rows) == business


def test_only_blue_abstracts_add_navigation_and_settings_and_keep_enabled_states():
    matching = []
    for photo in registry.registered_themes(include_disabled=True):
        businesses = set(photo.get("contentEligibility", {}).get("businesses", []))
        if businesses & {"navigation", "settings"}:
            matching.append(photo)
            assert businesses == {"calendar", "weather", "navigation", "settings"}
            assert photo.get("pool") == "texturePhotos"
            assert photo.get("family") == "blue"
    assert len(matching) == 6
    assert [item.get("id") for item in matching if not item.get("enabled")] == [
        BLUE + "circles-wide",
    ]
    registry.validate_registry(registry.load_theme_registry())


@pytest.mark.parametrize("event_id", [NAVIGATION, SETTINGS])
@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("shape", ["diamond", "diagonal"])
def test_selection_is_uniform_blue_and_preserves_foreground(monkeypatch, event_id, wide, shape):
    saved = entry_sample(event_id, wide=wide)
    suffix = "wide" if wide else "square"
    expected = {BLUE + item + "-" + suffix for item in ("diamond", "diagonal")}
    selected = BLUE + shape + "-" + suffix
    calls = []

    def choice(items):
        assert set(items) == expected
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    result, audit = choose(saved, monkeypatch)
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert len(calls) == 1
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    scope = "main" if wide else "root"
    assert evidence(saved).get("photoBodyTextFlow", {}).get(scope, {}).get("lineCount") == 3


@pytest.mark.parametrize("event_id", [NAVIGATION, SETTINGS])
@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("lines", [1, 3, 4, 5])
def test_body_line_gate_uses_three_for_square_and_wide(event_id, wide, lines):
    saved = entry_sample(event_id, lines, wide)
    reason = rejection(saved, BLUE + "diamond-" + ("wide" if wide else "square"))
    limit = 3
    allowed = lines <= limit
    assert (reason is None) is allowed
    if not allowed:
        assert f"超过{limit}行" in reason


@pytest.mark.parametrize("event_id", [NAVIGATION, SETTINGS])
def test_fully_centered_entry_only_uses_circles(monkeypatch, event_id):
    saved = entry_sample(event_id)
    rows = themes.decode(saved.compact)
    rows[0][2].update(alignItems="center", justifyContent="center", onClick=[action(event_id)])
    rows[0][3][:] = ["reading"]
    rows = [row for row in rows if row[0] not in {"title", "button"}]
    reading = next(row for row in rows if row[0] == "reading")
    reading[2]["textAlign"] = "center"
    _, audit = choose(expanded(rows, saved.task), monkeypatch)
    assert audit.get("candidates") == [BLUE + "circles-square"]


def test_wide_main_business_works_in_left_right_and_top_layouts():
    saved = entry_sample(NAVIGATION, wide=True)
    assert rejection(saved, BLUE + "diamond-wide") is None
    rows = themes.decode(saved.compact)
    rows[0][2]["orientation"] = "content-right"
    assert rejection(expanded(rows, saved.task), BLUE + "diamond-wide") is None
    rows = [
        ["root", "Layout", {"layout": "W-top-bottom"}, ["title", "main", "details"]],
        ["title", "SingleLineTitle", {"title": "导航"}],
        ["main", "Text", {"content": "去公司", "onClick": [action(NAVIGATION)]}],
        ["details", "TextBlock", {"items": [
            {"label": "目的地", "value": "公司"}, {"label": "出行", "value": "驾车"},
        ]}],
    ]
    assert rejection(expanded(rows, saved.task), BLUE + "diamond-wide") is None


def test_unshown_actions_and_query_do_not_create_a_business():
    saved = entry_sample(SETTINGS)
    rows = themes.decode(saved.compact)
    rows[0][3].remove("button")
    rows = [row for row in rows if row[0] != "button"]
    saved.task.update(userQuery="导航和系统设置", eventCandidates=[action(NAVIGATION)])
    for color in ("blue", "purple", "orange"):
        assert rejection(expanded(rows, saved.task),
                         f"photo-ux-texture-{color}-diamond-square") is None


def test_disabled_photo_switch_still_applies(monkeypatch):
    saved = entry_sample(SETTINGS)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    _, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact,
    ))
    assert not any(item.startswith("photo-") for item in audit.get("candidates", []))


def test_two_setting_buttons_count_as_one_business_and_zero_body_lines(monkeypatch):
    rows = [
        ["root", "Layout", {"layout": "S-content-dual-action", "variant": "actions-only"},
         ["wifi", "bluetooth"]],
        ["wifi", "CardButton", {"label": "Wi-Fi开关", "onClick": [action("event.setWifiMode")]}],
        ["bluetooth", "CardButton", {
            "label": "蓝牙开关", "onClick": [action("event.setBluetoothMode")],
        }],
    ]
    saved = expanded(rows, {"size": "2x2", "userQuery": "网络开关", "appVersion": "99.0.0"})
    _, audit = choose(saved, monkeypatch)
    assert set(audit.get("candidates", [])) == {
        BLUE + "diamond-square", BLUE + "diagonal-square",
    }
    assert evidence(saved).get("photoBodyTextFlow", {}).get("root", {}).get("lineCount") == 0


@pytest.mark.parametrize("query,value,operation", [
    ("导航卡片，不要图片", "photo", "avoid"),
    ("设置入口，使用融球效果", "fusion", "prefer"),
])
def test_explicit_visual_preference_still_excludes_photos(monkeypatch, query, value, operation):
    saved = entry_sample(SETTINGS)
    saved.task["userQuery"] = query
    items = [preference("backgroundKind", value, query, operation)]
    _, audit = choose(saved, monkeypatch, reply(items))
    assert not any(item.startswith("photo-") for item in audit.get("candidates", []))
    if value == "fusion":
        assert audit.get("theme", {}).get("kind") == "gradient"
        assert audit.get("unmetPreferences") == items
        assert not audit.get("fusionEligibility", {}).get("allowedTokens")


@pytest.mark.parametrize("event_id", [NAVIGATION, SETTINGS])
@pytest.mark.parametrize("wide", [False, True])
def test_final_delivery_keeps_one_obs_image_fallback_and_colors(monkeypatch, event_id, wide):
    saved = entry_sample(event_id, wide=wide)
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    original.cardSpec["suggestSize"] = saved.task.get("size")
    original.effectiveCapabilities["event"] = [action(event_id), *ACTION]
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    client = SimpleNamespace(generate=AsyncMock(return_value="{}"))
    delivered = asyncio.run(themes.theme_artifact(
        original, saved.task, client, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact,
    ))
    suffix = "wide" if wide else "square"
    urls = set()
    for item in registry.registered_themes("texturePhotos"):
        if item.get("id") in {BLUE + "diamond-" + suffix, BLUE + "diagonal-" + suffix}:
            urls.add(item.get("remoteUrl"))
    assert node_by_id(delivered.genui, themes.PREFIX + "base").get("src") in urls
    images = []
    for node in themes.components(themes.decode(delivered.genui)):
        if node.get("component") == "Image" and node.get("src") in urls:
            images.append(node)
    assert len(images) == 1
    root_styles = node_by_id(delivered.genui, "root").get("styles", {})
    assert root_styles.get("backgroundColor") == "#FF1F1F99"
    assert node_by_id(delivered.genui, "reading").get("styles", {}).get("fontColor") == "#FFFFFFFF"
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(saved.source)
