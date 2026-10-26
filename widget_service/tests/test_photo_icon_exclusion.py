"""原色天气图标只在实际使用时排除所有图片背景，不改变前景或其它准入。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_photo_assets import excluded_foreground_assets
from test_autumn_calendar_photos import expanded
from test_holiday_weather_panel_photos import panels
from test_uniform_photo_eligibility import PATHS, sample
from test_wide_photo_focus import focus_sample

ICON = "resources/base/media/ic_weather_color.svg"
MONOCHROME = "resources/base/media/ic_weather_monochrome.svg"
URL = "https://assets.example.test/cloud.svg"
OTHER = "resources/base/media/icon_meeting.svg"
SCENARIOS = (
    "square-subject", "square-abstract", "wide-focus", "wide-abstract",
    "W-split-panels", "W-four-slots", "black-meeting", "wide-meeting", "holiday",
)


def with_icon(saved, src=ICON):
    rows = themes.decode(saved.compact)
    header = next((row for row in rows if len(row) > 2 and row[1] == "SingleLineTitle"), None)
    if header is not None:
        header[2]["icon"] = src
    else:
        # 四宫格没有标题组件，在其实际前景树中放入图标。
        saved = copy.deepcopy(saved)
        records = themes.decode(saved.source)
        nodes = themes.components(records)
        parent = next(node for node in nodes if node.get("children"))
        parent.get("children").append("weather_icon")
        nodes.append({"id": "weather_icon", "component": "Image", "src": src,
                      "styles": {"width": 20, "height": 20}})
        saved.source = themes.encode(records)
        saved.nodes = nodes
        return saved
    return expanded(rows, saved.task)


def choose(saved, response):
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps(response)))
    result, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact,
    ))
    payload = json.loads(client.generate.call_args.args[0][1].get("content"))
    client.generate.assert_awaited_once()
    return result, audit, payload


def scenario(kind):
    if kind == "holiday":
        return sample(PATHS.get("countdown"), 5, title="中秋节", align="center")
    if kind == "wide-meeting":
        return focus_sample("calendar", 1, "left")
    if kind == "square-abstract":
        return sample(PATHS.get("settings", "/data/unknown/value"), 2, align="center")
    if kind in {"W-split-panels", "W-four-slots"}:
        return panels(kind)
    if kind == "wide-focus":
        return focus_sample("weather", 1, "top")
    if kind == "wide-abstract":
        return sample("/data/unknown/value", 2, wide=True)
    business = "calendar" if kind == "black-meeting" else "weather"
    return sample(PATHS.get(business), 3)


@pytest.mark.parametrize("kind", SCENARIOS)
def test_visible_icon_excludes_all_photo_pools_before_model(monkeypatch, kind):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    clean = scenario(kind)
    _, baseline, _ = choose(clean, {})
    assert baseline.get("theme", {}).get("kind") == "photo"
    saved = with_icon(clean)
    before = copy.deepcopy(saved.nodes)
    # 即使模型仍返回原来的图片ID，也不能绕过前置排除。
    result, audit, payload = choose(saved, {"themeId": baseline.get("themeId")})
    assert payload.get("eligiblePhotos") == []
    assert all(item.get("kind") != "photo" for item in payload.get("candidates", []))
    assert audit.get("theme", {}).get("kind") != "photo"
    assert audit.get("photoAssetExclusions")
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    result_nodes = themes.components(themes.decode(result))
    assert any(node.get("src") == ICON for node in result_nodes)
    assert not any(node.get("id") == themes.PREFIX + "base" for node in result_nodes)
    assert saved.nodes == before


@pytest.mark.parametrize("kind", SCENARIOS)
def test_monochrome_cloud_preserves_eligible_photo_candidates(monkeypatch, kind):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    clean = scenario(kind)
    _, _, baseline = choose(clean, {})
    saved = with_icon(clean, MONOCHROME)
    saved.task["assetCandidates"] = [{"id": "asset.ic_weather_color", "src": ICON,
                                      "description": "蓝色渐变云朵，保留原色"}]
    result, audit, payload = choose(saved, {})
    assert payload.get("eligiblePhotos") == baseline.get("eligiblePhotos")
    assert audit.get("theme", {}).get("kind") == "photo"
    assert audit.get("photoAssetExclusions") == []
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("src", [OTHER, "resources/base/media/ic_weather_color_extra.svg"])
def test_other_icons_and_unused_asset_candidates_do_not_block(monkeypatch, src):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    saved = with_icon(scenario("square-subject"), src)
    saved.task["assetCandidates"] = [{"id": "asset.ic_weather_color", "src": ICON,
                                      "description": "蓝色渐变云朵，保留原色"}]
    _, audit, payload = choose(saved, {})
    assert audit.get("theme", {}).get("kind") == "photo"
    assert payload.get("eligiblePhotos")
    assert audit.get("photoAssetExclusions") == []


def test_mapped_delivery_url_cannot_bypass_exclusion(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    monkeypatch.setattr(get_settings(), "asset_src_url_mapping", {ICON: URL})
    saved = with_icon(scenario("square-subject"), URL)
    result, audit, payload = choose(saved, {})
    assert payload.get("eligiblePhotos") == []
    assert audit.get("photoAssetExclusions", [])[0].get("asset") == ICON
    assert any(node.get("src") == URL for node in themes.components(themes.decode(result)))


def test_disabled_photo_switch_keeps_ordinary_theme(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    saved = with_icon(scenario("square-subject"))
    _, audit, payload = choose(saved, {})
    assert audit.get("photoAssetExclusions") == []
    assert payload.get("eligiblePhotos") == []
    assert audit.get("theme", {}).get("kind") != "photo"


@pytest.mark.parametrize("src,expected", [
    (ICON, True), (URL, True), (OTHER, False), (MONOCHROME, False),
    ({"path": "/icon"}, True),
    ("{{ ${/icon} }}", True),
    ("{{ ${/useCloud} ? ${/icon} : ${/other} }}", False),
    ("{{ ${/missing} }}", False),
])
@pytest.mark.parametrize("container", ["Row", "Column", "Stack", "Button"])
def test_actual_icon_binding_in_any_foreground_area(src, expected, container):
    nodes = [
        {"id": "root", "component": "Column", "children": ["area"]},
        {"id": "area", "component": container, "children": ["used", "mention"]},
        {"id": "used", "component": "Image", "src": src},
        {"id": "mention", "component": "Text", "content": ICON},
        {"id": "unused", "component": "Image", "src": ICON},
    ]
    data = {"icon": ICON, "other": OTHER, "useCloud": False}
    before = copy.deepcopy(nodes)
    found = excluded_foreground_assets(nodes, [ICON], {ICON: URL}, data)
    assert found == ([{"componentId": "used", "asset": ICON}] if expected else [])
    assert nodes == before


def test_old_config_without_exclusion_list_is_compatible(monkeypatch):
    config = registry.load_theme_registry()
    config.get("photoEligibility", {}).pop("excludedForegroundAssets", None)
    registry.validate_registry(config)
    monkeypatch.setattr(registry, "_load_registry", lambda _path: copy.deepcopy(config))
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    _, audit, _ = choose(with_icon(scenario("square-subject")), {})
    assert audit.get("theme", {}).get("kind") == "photo"
    assert audit.get("photoAssetExclusions") == []


@pytest.mark.parametrize("response", ["not json", RuntimeError("selector unavailable")])
def test_selector_failure_keeps_all_photos_excluded(monkeypatch, response):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    saved = with_icon(scenario("square-subject"))
    generate = AsyncMock(return_value=response)
    if isinstance(response, RuntimeError):
        generate = AsyncMock(side_effect=response)
    result, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, SimpleNamespace(generate=generate), final_layout=saved.compact,
    ))
    assert audit.get("theme", {}).get("kind") != "photo"
    assert audit.get("photoAssetExclusions")
    assert audit.get("selectorError")
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("value", [[ICON, ICON], [URL], ["../cloud.svg"], [""], "all"])
def test_exclusion_configuration_requires_unique_resource_keys(value):
    config = registry.load_theme_registry()
    config.get("photoEligibility", {})["excludedForegroundAssets"] = value
    with pytest.raises(ValueError, match="excludedForegroundAssets"):
        registry.validate_registry(config)
