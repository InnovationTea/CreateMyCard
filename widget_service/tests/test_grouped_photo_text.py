"""Compiler-generated grouping must not hide known photo body text (Q52)."""

import asyncio
import copy
from unittest.mock import AsyncMock

import pytest

from services import post_layout_theme as themes
from services.capability_registry import CapabilityRegistry
from services.protocol_registry import A2UIProtocolRegistry
from services.theme_content_regions import body_text_flow_evidence
from services.validator import ArtifactValidator
from test_autumn_calendar_photos import expanded
from test_photo_asset_delivery import artifact
from test_photo_background_fallback import node_by_id
from test_uniform_photo_eligibility import (
    BLUE,
    PATHS,
    PURPLE,
    choose,
    evidence,
    photo,
    rejection,
    sample,
)

WEATHER_WIDE = {"photo-ux-wave-wide", "photo-ux-fuzzy-wide"}


def q52_artifact(saved):
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    original.cardSpec["suggestSize"] = "2x4"
    capabilities = CapabilityRegistry(version=original.meta.capabilityRegistryVersion)
    weather = capabilities.get_data_capability("ViewWeather")
    call = capabilities.get_event_capability("event.call.phone")
    assert weather is not None
    assert call is not None
    original.effectiveCapabilities["data"] = [weather.model_dump()]
    original.effectiveCapabilities["event"] = [call.actionTemplate.model_dump()]
    assets = []
    for identity in ("asset.ic_purification", "asset.phone_fill"):
        asset = capabilities.get_asset_capability(identity)
        assert asset is not None
        assets.append(asset.model_dump())
    original.effectiveCapabilities["asset"] = assets
    original.cardSpec["dataBindings"] = [
        {"capabilityId": "ViewWeather", "arguments": {}, "writeResultTo": "/data/weather"},
    ]
    return original


def q52_sample(extra_line=False):
    prefix = "/data/weather/"
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots", "orientation": "content-left"},
         ["content", "upper", "lower"]],
        ["content", "Region", {"variant": "title-hero-support"},
         ["content_title", "content_primary", "content_support"]],
        ["content_title", "SingleLineTitle",
         {"title": {"path": prefix + "location/prefectureName"}, "fontSize": 12}],
        ["content_primary", "EmphasizedData",
         {"value": {"path": prefix + "current/temperatureText"}, "fontSize": 30}],
        ["content_support", "SecondaryBody", {"columns": 1, "fontSize": 12, "items": [
            {"label": "Weather ", "value": {"path": prefix + "current/condition"}},
            {"label": "Air quality ", "value": {"path": prefix + "current/airQuality"}},
            {"label": "Today ", "value": "{{ ${/data/weather/daily/0/condition} + ' ' + "
             "${/data/weather/daily/0/temperatureRangeText} }}"},
        ]}],
        ["upper", "InfoBlock", {"variant": "slot",
         "primaryText": {"path": prefix + "location/districtName"}, "secondaryText": "District",
         "visual": {"type": "icon", "icon": "resources/base/media/ic_purification.svg"}}],
        ["lower", "CardButton", {"label": "Call", "icon": "resources/base/media/phone_fill.svg",
         "onClick": [{"call": "clickToApi", "args": {
             "intentName": "CallPhone", "params": {"phoneNumber": ""},
         }}]}],
        [prefix + "location/prefectureName", "Shanghai"],
        [prefix + "location/districtName", "Qingpu"],
        [prefix + "current/temperatureText", "29"],
        [prefix + "current/condition", "Cloudy"],
        [prefix + "current/airQuality", "Good"],
        [prefix + "daily/0/condition", "Cloudy"],
        [prefix + "daily/0/temperatureRangeText", "25 / 32"],
    ]
    if extra_line:
        support = next(row for row in rows if row[0] == "content_support")
        support[2].get("items", []).append({"label": "More ", "value": "Weather"})
    return expanded(rows, {"size": "2x4", "userQuery": "Weather", "appVersion": "99.0.0"})


@pytest.mark.parametrize("extra_line,expected", [(False, 4), (True, 5)])
def test_q52_grouped_compiler_text_keeps_four_line_main_limit(extra_line, expected):
    saved = q52_sample(extra_line)
    before = copy.deepcopy(saved.nodes)
    value = next(node for node in saved.nodes
                 if node.get("id") == "content_support_item2_value")
    assert value.get("content") == (
        "{{ 'Today ' + (${/data/weather/daily/0/condition} + ' ' + "
        "${/data/weather/daily/0/temperatureRangeText}) }}"
    )
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("content", {})
    assert flow.get("lineCount") == expected
    assert flow.get("leftAligned") is True
    for identity in WEATHER_WIDE:
        assert (rejection(saved, identity) is None) is (expected == 4)
    assert saved.nodes == before


@pytest.mark.parametrize("selected", sorted(WEATHER_WIDE))
def test_q52_selects_existing_weather_pool_without_foreground_changes(monkeypatch, selected):
    monkeypatch.setattr(themes.secrets, "choice", lambda items: selected)
    saved = q52_sample()
    before = copy.deepcopy(saved)
    result, audit = choose(saved, monkeypatch)
    assert set(audit.get("candidates", [])) == WEATHER_WIDE
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    assert saved == before
    original = q52_artifact(saved)
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=(result, audit)))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, None, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact,
    ))
    assert not audit.get("finalValidationErrors"), audit.get("finalValidationErrors")
    assert audit.get("themeId") == selected
    assert themes.foreground_signature(delivered.genui) == (
        themes.foreground_signature(original.genui)
    )
    address = photo(selected).get("remoteUrl")
    assert address
    backgrounds = []
    for node in themes.components(themes.decode(delivered.genui)):
        if node.get("component") == "Image" and node.get("id", "").startswith(themes.PREFIX):
            backgrounds.append(node.get("src"))
    assert backgrounds == [address]
    assert node_by_id(delivered.genui, "root").get("styles", {}).get(
        "backgroundColor"
    ) == "#FF1F1F99"
    for identity in ("upper", "lower"):
        styles = node_by_id(delivered.genui, identity).get("styles", {})
        assert styles.get("backgroundColor") == "#33FFFFFF"
        assert styles.get("backdropBlur") == {"radius": 20}
    for identity, expected in (
        ("content_title_title", "#CCFFFFFF"),
        ("content_primary_value", "#FFFFFFFF"),
        ("content_support_item0_label", "#99FFFFFF"),
        ("content_support_item0_value", "#FFFFFFFF"),
    ):
        assert node_by_id(delivered.genui, identity).get("styles", {}).get("fontColor") == expected


@pytest.mark.parametrize("business,subject,texture", [
    ("weather", "photo-ux-wave-square", BLUE),
    ("sleep", "photo-ux-sleep-square", PURPLE),
    ("calendar", "photo-ux-meeting-room-square", BLUE),
])
@pytest.mark.parametrize("lines", [3, 4])
def test_grouped_square_text_preserves_subject_and_texture_limits(
    business, subject, texture, lines,
):
    path = PATHS.get(business)
    saved = sample(path, lines)
    rows = themes.decode(saved.compact)
    reading = next(row for row in rows if row[0] == "reading")
    reading[2]["content"] = "{{ 'Value ' + (${" + path + "} + '') }}"
    grouped = expanded(rows, saved.task)
    for identity in (subject, texture):
        assert rejection(grouped, identity) == rejection(saved, identity)
        assert (rejection(grouped, identity) is None) is (lines == 3)


@pytest.mark.parametrize("lines", [3, 4])
@pytest.mark.parametrize("align", ["start", "center", "end"])
def test_grouped_wide_texture_preserves_whole_card_line_limit(lines, align):
    saved = sample(PATHS.get("weather"), lines, wide=True, align=align)
    rows = themes.decode(saved.compact)
    reading = next(row for row in rows if row[0] == "reading")
    reading[2]["content"] = "{{ 'Value ' + (${/data/weather/current/temperature} + '') }}"
    grouped = expanded(rows, saved.task)
    identity = BLUE.replace("square", "wide")
    assert rejection(grouped, identity) == rejection(saved, identity)
    assert (rejection(grouped, identity) is None) is (lines == 3)


@pytest.mark.parametrize("max_lines,expected", [(20, 3), (2, 2)])
def test_grouped_current_newlines_honor_explicit_clipping_not_max_lines_count(max_lines, expected):
    nodes = [{"id": "root", "component": "Text", "styles": {"maxLines": max_lines},
              "content": r"{{ 'One\n' + ('Two' + '\nThree') }}"}]
    flow = body_text_flow_evidence(nodes, {}).get("root", {})
    assert flow.get("lineCount") == expected
