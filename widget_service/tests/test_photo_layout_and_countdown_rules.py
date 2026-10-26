"""宽卡图片全局边界、左电量正文计数和秋色单倒计时回归。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from photo_samples.battery import WIDE, wide_battery_sample
from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import subjectless_wide_theme
from services.post_layout_theme_registry import registered_themes
from services.theme_content_regions import photo_layout_evidence, photo_layout_exclusion_reason
from test_autumn_calendar_photos import COUNTDOWN_ID, photo

SPLIT_REASON = "2x4左右两个大背板布局不使用图片背景"


@pytest.mark.parametrize("identity", [item.get("id") for item in registered_themes("photos")])
def test_split_panels_are_excluded_for_every_photo_business(identity):
    sample = wide_battery_sample("W-split-panels")
    theme = photo(identity)
    theme["size"] = "2x4"
    evidence = photo_layout_evidence(sample.nodes)
    assert evidence.get("sideBySidePanels") is True
    reason = themes.photo_reason(theme, sample.task, evidence, final_layout=sample.compact)
    if theme.get("contentEligibility", {}).get("wideLayout") == "main-focus":
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
@pytest.mark.parametrize("selected_shape", [WIDE, "photo-ux-texture-blue-diagonal-wide"])
def test_model_cannot_return_excluded_subject_but_abstract_can_match(
    monkeypatch, enabled, selected_shape,
):
    sample = wide_battery_sample("W-split-panels")
    subjects = []
    for theme in registered_themes("photos"):
        if theme.get("size") == "2x4":
            subjects.append(theme)
    assert subjects
    excluded_subject = subjects[0].get("id")
    assert isinstance(excluded_subject, str)

    # 测试固定蓝色，再分别抽中两种形状；不依赖颜色或形状的随机结果。
    random_options = []

    def choose_shape(options):
        random_options.append(tuple(options))
        if "blue" in options:
            return "blue"
        assert selected_shape in options
        return selected_shape

    monkeypatch.setattr(themes.secrets, "choice", choose_shape)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    client = SimpleNamespace(generate=AsyncMock(
        return_value=json.dumps({"themeId": excluded_subject}),
    ))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert audit.get("themeId") != excluded_subject
    assert excluded_subject not in audit.get("candidates", [])
    assert excluded_subject in audit.get("rejected", {})
    if enabled:
        assert random_options
        assert selected_shape in audit.get("candidates", [])
        assert audit.get("themeId") == selected_shape
        assert audit.get("theme", {}).get("pool") == "texturePhotos"
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
