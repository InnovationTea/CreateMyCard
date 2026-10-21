"""倒计时图片配色回归，以及共用的倒计时与会议样例。"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.theme_content_regions import photo_layout_evidence
from services.theme_style_roles import layout_phase

COUNTDOWN_ID = "photo-ux-birds-countdown-square"
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
    data = themes.decode(sample.source)[-1].get("updateDataModel", {}).get("value")
    evidence = photo_layout_evidence(sample.nodes, data, final_layout=sample.compact)
    return themes.photo_reason(photo(identity), sample.task, evidence,
                               final_layout=sample.compact)


def test_countdown_white_palette_keeps_both_panel_blurs_without_changing_layout():
    sample = autumn_sample("旅行与纪念日倒计时", "旅行", "纪念日")
    final = themes.apply_theme(sample.source, photo(COUNTDOWN_ID), sample.task, {})
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


@pytest.mark.parametrize("preference", ["融球", "绒球", "纯色", "不要图片"])
def test_user_theme_preferences_take_priority(preference):
    sample = autumn_sample()
    sample.task["userQuery"] += "，使用" + preference
    assert rejection(sample, COUNTDOWN_ID) == "用户明确其它主题或不要图片"


def test_default_photo_switch_is_enabled():
    config = Path(__file__).resolve().parents[1] / "cloud/config/default_config.yaml"
    values = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert values.get("enable_photo_background_theme") is True
