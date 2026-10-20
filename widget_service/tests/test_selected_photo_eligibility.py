"""星轨睡眠图只匹配左侧真实睡眠业务与居左内容。"""

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.theme_content_regions import photo_layout_evidence
from services.theme_style_roles import layout_phase

IDS = {
    "sleep": "photo-ux-star-trails-wide",
}
PATHS = {
    "sleep": "/data/healthSport/nightSleepDurationText",
}


def photo(business):
    return next(item for item in registry.registered_themes("photos", include_disabled=True)
                if item.get("id") == IDS.get(business))


def fixture(business):
    path = PATHS.get(business)
    assert path is not None
    root_key = path.split("/")[2]
    task = {"size": "2x4", "userQuery": "睡眠 天气 日程",
            "appVersion": "11.9.9.342", "dataModelSchema": {"data": {root_key: {}}}}
    content = [
        ["header", "SingleLineTitle", {"title": "业务标题"}],
        ["value", "EmphasisText", {"mainText": {"path": path}, "secondaryText": "业务说明"}],
        [path, "业务数据"],
    ]
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["main", "upper", "lower"]],
        ["main", "Region", {"variant": "title-content"}, ["header", "value"]],
        ["upper", "InfoBlock", {"variant": "slot", "primaryText": "82",
                               "secondaryText": "睡眠 天气"}],
        ["lower", "InfoBlock", {"variant": "slot", "primaryText": "68%",
                               "secondaryText": "电量"}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows + content)
    with layout_phase(True, task):
        converted = convert_compact_dsl_to_a2ui(source, size=task.get("size"))
    nodes = themes.components(themes.decode(converted))
    return SimpleNamespace(task=task, source=source, nodes=nodes)


def reason(sample, business):
    return themes.photo_reason(photo(business), sample.task, photo_layout_evidence(sample.nodes),
                               final_layout=sample.source)


@pytest.mark.parametrize("business", IDS)
def test_selected_photo_accepts_real_expanded_left_layout(business):
    assert reason(fixture(business), business) is None


@pytest.mark.parametrize("business", IDS)
@pytest.mark.parametrize("alignment", ["center", "end"])
def test_selected_photo_rejects_non_left_content(business, alignment):
    sample = fixture(business)
    node = next(item for item in sample.nodes if item.get("id") == "value_main")
    node.get("styles", {})["textAlign"] = alignment
    assert reason(sample, business) is not None


@pytest.mark.parametrize("business", IDS)
@pytest.mark.parametrize("change", ["reverse", "split", "missing-slot", "foreign-main",
                                    "foreign-support", "static-main", "unknown-flow"])
def test_wide_photo_requires_left_business_not_right_slot_or_query(business, change):
    sample = fixture(business)
    if change == "reverse":
        sample.source = sample.source.replace(
            '"W-content-side-slots"', '"W-content-side-slots", "orientation":"content-right"',
        )
    elif change == "split":
        sample.source = sample.source.replace("W-content-side-slots", "W-split-panels")
    elif change == "missing-slot":
        sample.source = sample.source.replace('["main", "upper", "lower"]', '["main", "upper"]')
    elif change == "foreign-main":
        sample.source = sample.source.replace(PATHS.get(business), "/data/phoneBattery/batterySOC")
    elif change == "foreign-support":
        sample.source = sample.source.replace('"业务说明"',
                                              '{"path":"/data/healthSport/steps"}')
    elif change == "static-main":
        sample.source = sample.source.replace(
            json.dumps({"path": PATHS.get(business)}), '"睡眠天气"',
        )
    else:
        sample.nodes = [node for node in sample.nodes if node.get("id") != "value_main"]
    assert reason(sample, business) is not None


@pytest.mark.parametrize("business", IDS)
def test_two_ended_label_value_is_not_left_aligned(business):
    sample = fixture(business)
    node = next(item for item in sample.nodes if item.get("id") == "value_main")
    node.update(component="Row", children=["label", "reading"],
                styles={"justifyContent": "spaceBetween"})
    sample.nodes.extend([
        {"id": "label", "component": "Text", "content": "标签", "styles": {"maxLines": 1}},
        {"id": "reading", "component": "Text", "content": "内容", "styles": {"maxLines": 1}},
    ])
    assert reason(sample, business) is not None


@pytest.mark.parametrize("business", IDS)
@pytest.mark.parametrize("enabled", [False, True])
def test_selection_preserves_foreground_and_default_switch(monkeypatch, business, enabled):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    sample = fixture(business)
    source = themes.encode([{"updateComponents": {"components": sample.nodes}}])
    response = json.dumps({"themeId": IDS.get(business)})
    client = SimpleNamespace(generate=AsyncMock(return_value=response))
    result, audit = asyncio.run(themes.select_theme(
        source, sample.task, client, final_layout=sample.source,
    ))
    expected = enabled
    assert (audit.get("themeId") == IDS.get(business)) is expected
    assert themes.foreground_signature(result) == themes.foreground_signature(source)
    assert audit.get("deviceGeometryKnown") is False


@pytest.mark.parametrize("business", IDS)
@pytest.mark.parametrize("change", ["size", "business", "policy", "fit"])
def test_registry_rejects_inconsistent_selected_photo(business, change):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == IDS.get(business))
    if change == "size":
        entry["sizes"] = ["2x2"]
    elif change == "business":
        entry["business"] = "music"
    elif change == "policy":
        entry.get("contentEligibility", {})["unknown"] = True
    else:
        entry.get("background", {})["objectFit"] = "cover"
    with pytest.raises(ValueError):
        registry.validate_registry(config)


@pytest.mark.parametrize("business", IDS)
def test_assets_match_delivery_digest_and_keep_existing_palette_alpha(business):
    entry = photo(business)
    src = entry.get("src")
    assert isinstance(src, str)
    asset = Path(__file__).resolve().parents[2] / src
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    assert digest == entry.get("source", {}).get("assetSha256")
    source_digest = entry.get("source", {}).get("sourceSha256")
    assert isinstance(source_digest, str)
    assert len(source_digest) == 64
    roles = entry.get("content", {}).get("roles", {})
    rgb = "FFFFFF"
    assert roles.get("primary") == "#FF" + rgb
    assert roles.get("secondary") == "#CC" + rgb
    assert roles.get("tertiary") == "#99" + rgb
    assert roles.get("componentSecondary") == "#33FFFFFF"
    before = copy.deepcopy(entry)
    sample = fixture(business)
    assert reason(sample, business) is None
    assert entry == before
