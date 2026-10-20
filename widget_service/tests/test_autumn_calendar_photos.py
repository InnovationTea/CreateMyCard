"""秋色倒计时与放宽图标、按钮后的会议图片准入回归。"""

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.theme_content_regions import photo_layout_evidence
from services.theme_style_roles import layout_phase

CALENDAR_ID = "photo-ux-yellow-arch-square"
AUTUMN_ID = "photo-ux-autumn-square"
START = "/data/calendar/events/0/startTime"
LOCATION = "/data/calendar/events/0/location"
ICON = "resources/base/media/icon_meeting.svg"
ACTION = [{"call": "clickToDeeplink", "args": {
    "bundleName": "com.huawei.hmos.calendar", "abilityName": "", "intentName": "Calendar",
    "uri": "",
}}]


def photo(identity):
    return next(entry for entry in registry.registered_themes("photos")
                if entry.get("id") == identity)


def expanded(rows, task):
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with layout_phase(True, task):
        source = convert_compact_dsl_to_a2ui(compact, size=task.get("size"))
    nodes = themes.components(themes.decode(source))
    return SimpleNamespace(compact=compact, source=source, nodes=nodes, task=task)


def calendar_sample(layout="S-title-dual-content", button="CircleButton", with_icon=True):
    children = ["header", "primary"]
    primary = {"mainText": {"path": START}}
    rows = [
        ["root", "Layout", {"layout": layout}, children],
        ["header", "SingleLineTitle", {"title": "下一场会议", "icon": ICON}],
        ["primary", "EmphasisText", primary],
        [START, "14:00"], [LOCATION, "会议室"],
    ]
    if layout in {"S-title-dual-content", "S-title-primary-secondary-action", "S-title-anchor"}:
        children.append("support")
        rows.append(["support", "SecondaryBody", {"items": [
            {"label": "地点 ", "value": {"path": LOCATION}},
        ]}])
    if layout in {"S-title-content-action", "S-title-primary-secondary-action", "S-title-anchor"}:
        children.append("action")
        props = {"label": "进入会议", "onClick": ACTION}
        if with_icon:
            props["icon"] = ICON
        if button == "CircleButton":
            props.pop("label")
            props["accessibility"] = {"label": "进入会议"}
        rows.append(["action", button, props])
    if layout == "S-title-content":
        primary["secondaryText"] = {"path": LOCATION}
    task = {"size": "2x2", "userQuery": "下一场会议时间和地点",
            "appVersion": "11.9.9.342", "dataModelSchema": {"data": {"calendar": {}}}}
    return expanded(rows, task)


def autumn_sample(query="中秋倒计时", title="倒计时", name=None):
    path = "/data/countdown/first/countdownDays"
    other = "/data/countdown/second/countdownDays"
    panel = {"primaryText": {"path": path}, "secondaryText": title}
    rows = [
        ["root", "Layout", {"layout": "S-dual-info"}, ["first", "second"]],
        ["first", "InfoBlock", panel],
        ["second", "InfoBlock", {"primaryText": {"path": other}, "secondaryText": "考试"}],
        [path, 30], [other, 60],
    ]
    if name is not None:
        panel["secondaryText"] = {"path": "/data/countdown/first/name"}
        rows.append(["/data/countdown/first/name", name])
    task = {"size": "2x2", "userQuery": query, "appVersion": "11.9.9.342",
            "dataModelSchema": {"data": {"countdown": {}}}}
    return expanded(rows, task)


def rejection(sample, identity):
    return themes.photo_reason(photo(identity), sample.task, photo_layout_evidence(sample.nodes),
                               final_layout=sample.compact)


@pytest.mark.parametrize("layout,button,allowed", [
    ("S-title-dual-content", "CircleButton", True),
    ("S-title-content", "CircleButton", True),
    ("S-title-content-action", "PillButton", True),
    ("S-title-anchor", "CircleButton", True),
    ("S-title-primary-secondary-action", "PillButton", False),
])
def test_calendar_icons_and_buttons_keep_two_line_limit(layout, button, allowed):
    sample = calendar_sample(layout, button)
    reason = rejection(sample, CALENDAR_ID)
    assert (reason is None) is allowed
    if not allowed:
        assert reason == "拱门图片内容区文字超过两行"


def test_calendar_non_text_evidence_is_not_a_rejection():
    sample = calendar_sample()
    primary = next(node for node in sample.nodes if node.get("id") == "primary")
    primary.setdefault("children", []).append("content_icon")
    sample.nodes.append({"id": "content_icon", "component": "Image", "src": ICON})
    evidence = photo_layout_evidence(sample.nodes)
    assert len(evidence.get("nonTextIds", [])) >= 2
    assert rejection(sample, CALENDAR_ID) is None


@pytest.mark.parametrize("with_icon", [False, True])
@pytest.mark.parametrize("lines,allowed", [(1, True), (2, False), (None, False)])
def test_calendar_capsule_label_counts_but_title_does_not(with_icon, lines, allowed):
    sample = calendar_sample("S-title-content-action", "PillButton", with_icon)
    node = next(item for item in sample.nodes if item.get("id") == "primary_main")
    node.get("styles", {})["maxLines"] = lines
    flow = photo_layout_evidence(sample.nodes).get("textFlow", {})
    assert flow.get("header", {}).get("maxLines") == 1
    assert flow.get("action", {}).get("maxLines") == 1
    assert (rejection(sample, CALENDAR_ID) is None) is allowed


@pytest.mark.parametrize("alignment", ["center", "end"])
def test_calendar_buttons_do_not_exempt_business_alignment(alignment):
    sample = calendar_sample("S-title-content-action", "PillButton")
    node = next(item for item in sample.nodes if item.get("id") == "primary_main")
    node.get("styles", {})["textAlign"] = alignment
    assert rejection(sample, CALENDAR_ID) == "拱门图片内容未居左"


@pytest.mark.parametrize("change", ["size", "mixed", "static", "unknown-layout", "missing-flow"])
def test_calendar_retains_size_business_and_evidence_guards(change):
    sample = calendar_sample()
    if change == "size":
        sample.task["size"] = "2x4"
    elif change == "mixed":
        sample.task.get("dataModelSchema", {}).get("data", {})["weather"] = {}
    elif change == "static":
        sample.compact = sample.compact.replace('"path":', '"literal":')
    elif change == "unknown-layout":
        sample.compact = sample.compact.replace("S-title-dual-content", "S-center")
    else:
        sample.nodes = [node for node in sample.nodes if node.get("id") != "primary_main"]
    assert rejection(sample, CALENDAR_ID) is not None


@pytest.mark.parametrize("query,title,name,allowed", [
    ("中秋倒计时", "倒计时", None, True),
    ("国庆倒计时", "倒计时", None, True),
    ("秋日出游倒计时", "倒计时", None, True),
    ("节日倒计时", "中秋", None, True),
    ("节日倒计时", "倒计时", "国庆", True),
    ("生日倒计时", "生日", None, True),
    ("旅行和纪念日", "旅行", "纪念日", True),
    ("周日倒计时", "周日", None, True),
])
def test_autumn_dual_countdowns_do_not_restrict_names(query, title, name, allowed):
    assert (rejection(autumn_sample(query, title, name), AUTUMN_ID) is None) is allowed


@pytest.mark.parametrize("change", ["size", "foreign", "static", "no-layout"])
def test_autumn_keywords_alone_cannot_authorize_photo(change):
    sample = autumn_sample()
    if change == "size":
        sample.task["size"] = "2x4"
    elif change == "foreign":
        sample.compact = sample.compact.replace("/data/countdown/", "/data/healthSport/")
    elif change == "static":
        sample.compact = sample.compact.replace('"path":', '"literal":')
    else:
        sample.compact = ""
    assert rejection(sample, AUTUMN_ID) is not None


@pytest.mark.parametrize("change", [
    "single", "horizontal", "same-countdown", "name-only", "foreign-second",
    "non-panel", "transparent-panel", "missing-panel", "two-days-in-one-panel",
])
def test_autumn_requires_two_visible_panels_with_distinct_countdowns(change):
    sample = autumn_sample("生日和考试倒计时", "生日")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    root = next(row for row in rows if row[0] == "root")
    second = next(row for row in rows if row[0] == "second")
    if change == "single":
        root[3].remove("second")
    elif change == "horizontal":
        root[2]["layout"] = "W-split-panels"
    elif change == "same-countdown":
        second[2]["primaryText"] = {"path": "/data/countdown/first/countdownDays"}
    elif change == "name-only":
        second[2]["primaryText"] = {"path": "/data/countdown/second/name"}
    elif change == "foreign-second":
        second[2]["primaryText"] = {"path": "/data/phoneBattery/batteryLevel"}
    elif change == "non-panel":
        second[1] = "TextBlock"
    elif change == "two-days-in-one-panel":
        second[2]["secondaryText"] = {"path": "/data/countdown/third/countdownDays"}
    else:
        node = next(item for item in sample.nodes if item.get("id") == "second")
        node.get("styles", {})["backgroundColor"] = (
            "@theme:panel/0" if change == "transparent-panel" else "@theme:transparent/1"
        )
    sample.compact = '\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)
    assert rejection(sample, AUTUMN_ID) is not None


def test_autumn_white_palette_keeps_both_panel_blurs_without_changing_layout():
    sample = autumn_sample("旅行与纪念日倒计时", "旅行", "纪念日")
    final = themes.apply_theme(sample.source, photo(AUTUMN_ID), sample.task, {})
    assert themes.foreground_signature(final) == themes.foreground_signature(sample.source)
    nodes = themes.components(themes.decode(final))
    for identity in ("first", "second"):
        node = next(item for item in nodes if item.get("id") == identity)
        assert node.get("styles", {}).get("backgroundColor") == "#33FFFFFF"
        assert node.get("styles", {}).get("backdropBlur") == {"radius": 20}
    text_colors = set()
    for node in nodes:
        if node.get("component") == "Text":
            text_colors.add(node.get("styles", {}).get("fontColor"))
    assert text_colors <= {"#FFFFFFFF", "#CCFFFFFF", "#99FFFFFF"}
    assert "#FFFFFFFF" in text_colors


@pytest.mark.parametrize("identity", [AUTUMN_ID, CALENDAR_ID])
@pytest.mark.parametrize("preference", ["融球", "绒球", "纯色", "不要图片"])
def test_user_theme_preferences_take_priority(identity, preference):
    sample = autumn_sample() if identity == AUTUMN_ID else calendar_sample()
    sample.task["userQuery"] += "，使用" + preference
    assert rejection(sample, identity) == "用户明确其它主题或不要图片"


@pytest.mark.parametrize("identity", [AUTUMN_ID, CALENDAR_ID])
@pytest.mark.parametrize("enabled", [False, True])
def test_new_photos_obey_switch_and_preserve_foreground(monkeypatch, identity, enabled):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    sample = autumn_sample() if identity == AUTUMN_ID else calendar_sample()
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": identity})))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert (audit.get("themeId") == identity) is enabled
    assert themes.foreground_signature(result) == themes.foreground_signature(sample.source)
    if enabled:
        expected = {identity}
        if identity == CALENDAR_ID:
            expected.add("photo-ux-desk-lamp-calendar-square")
        assert set(audit.get("candidates", [])) == expected
        nodes = themes.components(themes.decode(result))
        root = next(node for node in nodes if node.get("id") == "root")
        expected_base = "#FF1F1F99" if identity == AUTUMN_ID else "#FFE6E6E6"
        assert root.get("styles", {}).get("backgroundColor") == expected_base
        background = next(node for node in nodes if node.get("id") == themes.PREFIX + "image")
        assert background.get("src") == photo(identity).get("src")


@pytest.mark.parametrize("identity", [AUTUMN_ID, CALENDAR_ID])
def test_new_photo_assets_empty_obs_and_complete_palette(identity):
    item = photo(identity)
    assert item.get("remoteUrl") == ""
    src = item.get("src")
    assert isinstance(src, str)
    asset = Path(__file__).resolve().parents[2] / src
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    assert digest == item.get("source", {}).get("assetSha256")
    colors = item.get("content", {}).get("roles", {})
    rgb = "FFFFFF" if identity == AUTUMN_ID else "000000"
    for color_role, alpha in (("primary", "FF"), ("secondary", "CC"), ("tertiary", "99")):
        assert colors.get(color_role) == "#" + alpha + rgb
    assert colors.get("componentSecondary") == "#33FFFFFF"
    assert item.get("content", {}).get("panelBySize") == {"2x2": "#33FFFFFF"}


@pytest.mark.parametrize("identity", [AUTUMN_ID, CALENDAR_ID])
@pytest.mark.parametrize("change", ["size", "business", "unknown-policy", "invalid-policy"])
def test_new_photo_registry_contracts(identity, change):
    config = registry.load_theme_registry()
    item = next(entry for entry in config.get("themes", []) if entry.get("id") == identity)
    if change == "size":
        item["sizes"] = ["2x4"]
    elif change == "business":
        item["business"] = "sleep"
    elif change == "unknown-policy":
        item.get("contentEligibility", {})["kind"] = "unknown"
    elif identity == AUTUMN_ID:
        item.get("contentEligibility", {})["layout"] = "S-title-content"
    else:
        item.get("contentEligibility", {})["maxTextLines"] = 3
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_default_photo_switch_is_enabled():
    config = Path(__file__).resolve().parents[1] / "cloud/config/default_config.yaml"
    values = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert values.get("enable_photo_background_theme") is True
