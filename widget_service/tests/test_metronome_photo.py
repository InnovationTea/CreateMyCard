"""节拍器只用于两个按钮，其他耳机音乐使用小提琴且内容区最多四行。"""

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_content_regions import photo_layout_evidence
from test_autumn_calendar_photos import expanded, photo, rejection

IDENTITY = "photo-ux-metronome-square"
VIOLIN = "photo-ux-violin-music-square"
PATH = "/data/earphone/earphoneBatteryLevel"
ICON = "resources/base/media/icon_music.svg"
ACTION = [{"call": "clickToDeeplink", "args": {
    "intentName": "Music", "bundleName": "", "abilityName": "",
    "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=favoriteSong&type=412",
}}]


def earphone_sample():
    task = {"size": "2x2", "userQuery": "耳机状态和收藏歌单", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"earphone": {}}}}
    rows = [
        ["root", "Layout", {"layout": "S-title-content-action"}, ["header", "reading", "cta"]],
        ["header", "SingleLineTitle", {"title": "耳机状态", "icon": ICON}],
        ["reading", "EmphasisText", {"mainText": {"path": PATH}, "secondaryText": "耳机电量"}],
        ["cta", "PillButton", {"label": "收藏歌单", "onClick": ACTION, "icon": ICON}],
        [PATH, "80%"],
    ]
    return expanded(rows, task)


def music_sample(with_icon=True):
    task = {"size": "2x2", "userQuery": "每日推荐和收藏歌单", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {}}}
    rows = [["root", "Layout", {"layout": "S-content-dual-action", "variant": "actions-only"},
             ["daily", "favorite"]]]
    for identity, label in (("daily", "每日推荐"), ("favorite", "收藏歌单")):
        props = {"label": label, "onClick": ACTION}
        if with_icon:
            props["icon"] = ICON
        rows.append([identity, "PillButton", props])
    return expanded(rows, task)


def test_three_body_lines_exclude_only_actual_title():
    sample = earphone_sample()
    flow = photo_layout_evidence(sample.nodes).get("textFlow", {})
    assert flow.get("root", {}).get("maxLines") == 4
    assert rejection(sample, VIOLIN) is None
    assert rejection(sample, IDENTITY) == "节拍器图片要求恰好两个可点击按钮"


@pytest.mark.parametrize("with_icon", [False, True])
def test_music_actions_only_without_header_are_allowed(with_icon):
    sample = music_sample(with_icon)
    flow = photo_layout_evidence(sample.nodes).get("textFlow", {})
    assert flow.get("root", {}).get("maxLines") == 2
    assert rejection(sample, IDENTITY) is None
    assert rejection(sample, VIOLIN) == "两个按钮的耳机音乐场景使用节拍器图片"


@pytest.mark.parametrize("lines", [1, 2, 3, 10, None])
def test_two_buttons_have_no_line_count_limit(lines):
    sample = music_sample()
    node = next(item for item in sample.nodes if item.get("id") == "daily_text")
    node.get("styles", {})["maxLines"] = lines
    assert rejection(sample, IDENTITY) is None
    assert rejection(sample, VIOLIN) is not None


@pytest.mark.parametrize("alignment", ["start", "center", "end"])
def test_no_extra_left_alignment_restriction(alignment):
    sample = earphone_sample()
    node = next(item for item in sample.nodes if item.get("id") == "reading_main")
    node.get("styles", {})["textAlign"] = alignment
    assert rejection(sample, VIOLIN) is None


@pytest.mark.parametrize("change", ["five-lines", "unknown-lines", "foreign", "static",
                                    "size", "no-layout", "explicit-fusion"])
def test_earphone_eligibility_guards(change):
    sample = earphone_sample()
    if change in {"five-lines", "unknown-lines"}:
        node = next(item for item in sample.nodes if item.get("id") == "reading_main")
        node.get("styles", {})["maxLines"] = 3 if change == "five-lines" else None
    elif change == "foreign":
        sample.compact = sample.compact.replace("/data/earphone/", "/data/phoneBattery/")
    elif change == "static":
        sample.compact = sample.compact.replace('"path":', '"literal":').replace("Music", "Clock")
    elif change == "size":
        sample.task["size"] = "2x4"
    elif change == "no-layout":
        sample.compact = ""
    else:
        sample.task["userQuery"] += "，使用融球"
    assert rejection(sample, VIOLIN) is not None


@pytest.mark.parametrize("old,new", [("Music", "Clock"), ("clickToDeeplink", "unknownCall")])
def test_music_keywords_cannot_override_non_music_action(old, new):
    sample = music_sample()
    sample.compact = sample.compact.replace(old, new, 1)
    assert rejection(sample, IDENTITY) == "音乐图片需要真实耳机内容或音乐跳转动作"


@pytest.mark.parametrize("enabled", [False, True])
def test_switch_and_foreground_preservation(monkeypatch, enabled):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    sample = music_sample()
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": IDENTITY})))
    result, audit = asyncio.run(themes.select_theme(
        sample.source, sample.task, client, final_layout=sample.compact,
    ))
    assert (audit.get("themeId") == IDENTITY) is enabled
    assert themes.foreground_signature(sample.source) == themes.foreground_signature(result)
    if enabled:
        nodes = themes.components(themes.decode(result))
        daily = next(node for node in nodes if node.get("id") == "daily")
        assert daily.get("styles", {}).get("backdropBlur") == {"radius": 20}


def test_original_asset_and_empty_obs():
    item = photo(IDENTITY)
    src = item.get("src")
    assert isinstance(src, str)
    original = Path(__file__).resolve().parents[2] / src
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    assert digest == item.get("source", {}).get("assetSha256")
    assert item.get("remoteUrl") == ""
    assert item.get("background", {}).get("objectFit") == "fill"
    assert item.get("content", {}).get("roles", {}).get("primary") == "#FFFFFFFF"


@pytest.mark.parametrize("key,value", [("maxTextLines", 4), ("includeTitle", True)])
def test_registry_rejects_line_limit_on_two_button_policy(key, value):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == IDENTITY)
    entry.get("contentEligibility", {})[key] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)
