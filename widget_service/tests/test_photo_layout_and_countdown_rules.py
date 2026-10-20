"""宽卡图片全局边界、左电量正文计数和秋色单倒计时回归。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import subjectless_wide_theme
from services.post_layout_theme_registry import registered_themes
from services.theme_content_regions import photo_layout_evidence, photo_layout_exclusion_reason
from test_autumn_calendar_photos import AUTUMN_ID, autumn_sample, expanded, photo, rejection
from test_battery_music_photo_rules import BATTERY_PATH, WIDE, wide_battery_sample

SPLIT_REASON = "2x4左右两个大背板布局不使用图片背景"


@pytest.mark.parametrize("identity", [item.get("id") for item in registered_themes("photos")])
def test_split_panels_are_excluded_for_every_photo_business(identity):
    sample = wide_battery_sample("W-split-panels")
    theme = photo(identity)
    theme["size"] = "2x4"
    evidence = photo_layout_evidence(sample.nodes)
    assert evidence.get("sideBySidePanels") is True
    assert themes.photo_reason(theme, sample.task, evidence,
                               final_layout=sample.compact) == SPLIT_REASON


@pytest.mark.parametrize("semantic", [False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_equivalent_two_panel_tree_is_rejected_without_guessing_pixel_sizes(semantic, wrapped):
    sample = wide_battery_sample("W-split-panels")
    if wrapped:
        root = next(node for node in sample.nodes if node.get("id") == "root")
        root["id"] = "inner"
        sample.nodes.append({"id": "root", "component": "Stack", "children": ["inner"],
                             "styles": {"width": "matchParent", "height": "matchParent"}})
    evidence = photo_layout_evidence(sample.nodes)
    if semantic:
        evidence["sideBySidePanels"] = False
    final_layout = sample.compact if semantic else None
    assert photo_layout_exclusion_reason(sample.task, evidence, final_layout) == SPLIT_REASON


def test_top_bottom_and_side_slots_are_not_misclassified_as_two_big_panels():
    sample = wide_battery_sample("W-split-panels")
    root = next(node for node in sample.nodes if node.get("id") == "root")
    root["component"] = "Column"
    assert photo_layout_evidence(sample.nodes).get("sideBySidePanels") is False
    side_slots = wide_battery_sample("W-content-side-slots")
    evidence = photo_layout_evidence(side_slots.nodes)
    assert evidence.get("sideBySidePanels") is False
    assert photo_layout_exclusion_reason(side_slots.task, evidence, side_slots.compact) is None


def test_legacy_wide_pool_uses_the_same_global_exclusion():
    sample = wide_battery_sample("W-split-panels")
    evidence = photo_layout_evidence(sample.nodes)
    gate = {"eligible": True, "businesses": ["battery"]}
    theme = {"size": "2x4", "business": "battery"}
    reason = subjectless_wide_theme.background_reason(theme, sample.task, evidence, gate)
    assert reason == SPLIT_REASON


@pytest.mark.parametrize("enabled", [False, True])
def test_model_cannot_return_excluded_photo_or_change_ordinary_candidates(monkeypatch, enabled):
    sample = wide_battery_sample("W-split-panels")
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": WIDE})))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert not audit.get("themeId", "").startswith("photo-")
    assert not any(identity.startswith("photo-") for identity in audit.get("candidates", []))
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    _, baseline = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert audit.get("candidates") == baseline.get("candidates")


@pytest.mark.parametrize("left_lines,button,allowed", [(3, False, True), (3, True, False),
                                                     (2, True, True), (4, False, False)])
def test_wide_battery_counts_only_left_body_and_visible_button(left_lines, button, allowed):
    sample = wide_battery_sample("W-content-side-slots")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    if button:
        main = next(row for row in rows if row[0] == "main")
        main[2]["variant"] = "title-content-action"
        main[3].append("cta")
        rows.append(["cta", "PillButton", {"label": "设置", "onClick": [{
            "call": "clickToDeeplink", "args": {"intentName": "Settings", "uri": "battery",
                                                "bundleName": "", "abilityName": ""}}]}])
    sample = expanded(rows, sample.task)
    for node in sample.nodes:
        if node.get("id") == "reading_main":
            node.get("styles", {})["maxLines"] = left_lines
        elif node.get("id") in {"header", "upper_primary", "lower_text"}:
            node.get("styles", {})["maxLines"] = 20
    assert (rejection(sample, WIDE) is None) is allowed


@pytest.mark.parametrize("change", ["right-only", "reverse", "mixed-left", "static-primary"])
def test_wide_battery_rejects_non_battery_main_focus(change):
    sample = wide_battery_sample("W-content-side-slots")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    reading = next(row for row in rows if row[0] == "reading")
    upper = next(row for row in rows if row[0] == "upper")
    upper[2]["primaryText"] = {"path": BATTERY_PATH}
    if change == "reverse":
        rows[0][2]["orientation"] = "content-right"
    elif change == "mixed-left":
        reading[2]["secondaryText"] = {"path": "/data/weather/temperature"}
        rows.append(["/data/weather/temperature", 29])
    elif change == "static-primary":
        reading[2]["mainText"] = "手机状态"
    else:
        reading[2]["mainText"] = {"path": "/data/weather/temperature"}
        rows.append(["/data/weather/temperature", 29])
    sample = expanded(rows, sample.task)
    assert rejection(sample, WIDE) is not None


def test_wide_battery_ring_counts_its_text_not_the_graphic():
    sample = wide_battery_sample("W-content-side-slots")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    reading = next(row for row in rows if row[0] == "reading")
    reading[1] = "ProgressCircleSingle"
    reading[2] = {"value": {"path": BATTERY_PATH}, "total": 100,
                  "displayValue": {"path": BATTERY_PATH}, "label": "剩余电量",
                  "icon": "resources/base/media/battery_leaf_fill.svg"}
    sample = expanded(rows, sample.task)
    flow = photo_layout_evidence(sample.nodes).get("textFlow", {})
    assert flow.get("reading_ring", {}).get("maxLines") == 0
    assert flow.get("reading", {}).get("maxLines") == 2
    assert flow.get("main", {}).get("maxLines") == 3
    assert rejection(sample, WIDE) is None


def single_countdown(label="本周日倒计时", name=None):
    path = "/data/countdown/countdownDays"
    props = {"label": label, "value": {"path": path}, "supportingText": "天"}
    rows = [
        ["root", "Layout", {"layout": "S-center"}, ["display"]],
        ["display", "DataDisplay", props], [path, 30],
    ]
    if name is not None:
        rows[0] = ["root", "Layout", {"layout": "S-title-content"}, ["header", "display"]]
        rows[1] = ["display", "EmphasisText", {"mainText": {"path": path},
                   "secondaryText": {"path": "/data/countdown/name"}}]
        rows.append(["header", "SingleLineTitle", {"title": "倒计时"}])
        rows.append(["/data/countdown/name", name])
    task = {"size": "2x2", "userQuery": "倒计时", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"countdown": {}}}}
    return expanded(rows, task)


@pytest.mark.parametrize("label", ["本周日倒计时", "周末", "元宵节", "泼水节", "暑假假期",
                                  "Christmas", "Festival", "休假", "寒假", "元旦", "国庆"])
def test_single_holiday_countdown_matches_without_adding_panels(label):
    sample = single_countdown(label)
    assert rejection(sample, AUTUMN_ID) is None
    final = themes.apply_theme(sample.source, photo(AUTUMN_ID), sample.task, {})
    assert themes.foreground_signature(final) == themes.foreground_signature(sample.source)
    for node in themes.components(themes.decode(final)):
        if node.get("id") == "display":
            assert "backgroundColor" not in node.get("styles", {})
            assert "backdropBlur" not in node.get("styles", {})


@pytest.mark.parametrize("label,allowed", [("生日", False), ("考试", False), ("旅行", False),
                                         ("马拉松节", False), ("运动会", False), ("端午节", True),
                                         ("周日约饭倒计时", False), ("国庆出差", False)])
@pytest.mark.parametrize("bound", [False, True])
def test_single_countdown_checks_visible_name_and_business(label, allowed, bound):
    sample = single_countdown(label, label if bound else None)
    sample.task["userQuery"] = "假期倒计时"
    assert (rejection(sample, AUTUMN_ID) is None) is allowed


def test_unused_holiday_value_cannot_authorize_single_countdown():
    sample = single_countdown("生日倒计时")
    sample.compact += '\n["/data/countdown/name", "春节"]'
    assert rejection(sample, AUTUMN_ID) is not None


@pytest.mark.parametrize("name", ["马拉松", "跑步比赛", "运动会", "Marathon", "Sports"])
def test_dual_countdowns_exclude_sports_even_when_other_panel_is_holiday(name):
    sample = autumn_sample("节日和赛事倒计时", "国庆", name)
    assert rejection(sample, AUTUMN_ID) == "秋色图片不用于运动或马拉松倒计时"


def test_autumn_palette_changes_only_ink_not_existing_surfaces():
    theme = photo(AUTUMN_ID)
    expected = copy.deepcopy(photo("photo-ux-sleep-square").get("content"))
    assert theme.get("content") == expected
