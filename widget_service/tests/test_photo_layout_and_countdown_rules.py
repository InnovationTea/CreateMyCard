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
from test_autumn_calendar_photos import COUNTDOWN_ID, expanded, photo
from test_battery_music_photo_rules import wide_battery_sample

SPLIT_REASON = "2x4左右两个大背板布局不使用图片背景"


@pytest.mark.parametrize("identity", [item.get("id") for item in registered_themes("photos")])
def test_split_panels_only_admit_explicit_weather_panel_policy(identity):
    sample = wide_battery_sample("W-split-panels")
    theme = photo(identity)
    theme["size"] = "2x4"
    evidence = photo_layout_evidence(sample.nodes)
    assert evidence.get("sideBySidePanels") is True
    reason = themes.photo_reason(theme, sample.task, evidence, final_layout=sample.compact)
    policy = theme.get("contentEligibility", {})
    if policy.get("kind") == "weather-panels":
        assert reason is None
    elif policy.get("kind") == "holiday-countdown":
        assert reason == "此图片仅用于2x2单业务节假日倒计时，每个展示对象均须属于节假日"
    elif policy.get("wideLayout") == "main-focus":
        assert reason == "2x4图片需要明确主焦点，不支持双大背板或无主次布局"
    elif theme.get("contentEligibility", {}).get("wideLayout") == "side-focus":
        assert reason == "2x4图片需要左右主焦点加另一侧上下双槽，不支持上下或双大背板布局"
    else:
        assert reason == "2x4图片需要左主焦点和右侧上下两个背板"


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
def test_model_cannot_return_excluded_subject_but_ice_can_match(monkeypatch, enabled):
    sample = wide_battery_sample("W-split-panels")
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    rejected_subject = "photo-ux-airplane-tarmac-wide"
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({
        "themeId": rejected_subject,
    })))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert rejected_subject not in audit.get("candidates", [])
    assert audit.get("themeId") != rejected_subject
    if enabled:
        assert audit.get("themeId") == "photo-ux-ice-wide"
    else:
        assert not any(identity.startswith("photo-") for identity in audit.get("candidates", []))
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    _, baseline = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    if not enabled:
        assert audit.get("candidates") == baseline.get("candidates")


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


def test_countdown_palette_changes_only_ink_not_existing_surfaces():
    theme = photo(COUNTDOWN_ID)
    expected = copy.deepcopy(photo("photo-ux-sleep-square").get("content"))
    assert theme.get("content") == expected
