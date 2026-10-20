"""小花天气图采用经确认的布局准入，保持其它图片及未知尺寸规则。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_content_regions import photo_layout_evidence

PHOTO_ID = "photo-ux-water-lily-square"
WEATHER_PATH = "/data/weather/current/condition"


def photo():
    return next(item for item in registry.registered_themes("photos")
                if item.get("id") == PHOTO_ID)


def task():
    return {"size": "2x2", "userQuery": "普通天气卡片",
            "dataModelSchema": {"data": {"weather": {"current": {
                "condition": {"type": "string"},
            }}}}}


def fixture(layout="S-title-content", alignment="start", lines=1, path=WEATHER_PATH):
    actions = {"S-title-anchor": "CircleButton", "S-title-content-action": "PillButton",
               "S-title-primary-secondary-action": "PillButton"}
    children = ["header", "reading"]
    rows = [
        ["root", "Layout", {"layout": layout}, children],
        ["header", "SingleLineTitle", {"title": "天气"}],
        ["reading", "EmphasisText", {"mainText": {"path": path}}],
    ]
    nodes = [
        {"id": "root", "component": "Column", "children": children,
         "styles": {"width": "matchParent", "height": "matchParent", "alignItems": "start"}},
        {"id": "header", "component": "Text", "content": "天气",
         "styles": {"maxLines": 1}},
        {"id": "reading", "component": "Text", "content": "{{ ${" + path + "} }}",
         "styles": {"maxLines": lines, "textAlign": alignment}},
    ]
    if layout in actions:
        children.append("action")
        rows.append(["action", actions.get(layout), {"label": "查看天气"}])
        nodes.append({"id": "action", "component": "Text", "content": "查看天气",
                      "styles": {"maxLines": 1, "textAlign": "center"}})
    return SimpleNamespace(layout="\n".join(json.dumps(row) for row in rows), nodes=nodes)


@pytest.mark.parametrize("layout", [
    "S-title-content", "S-title-dual-content",
])
def test_weather_left_aligned_layout_without_buttons_matches(layout):
    sample = fixture(layout)
    evidence = photo_layout_evidence(sample.nodes)
    assert themes.photo_reason(photo(), task(), evidence, final_layout=sample.layout) is None
    assert photo().get("subjectless") is False
    assert evidence.get("deviceGeometryKnown") is False


@pytest.mark.parametrize("layout", [
    "S-center", "S-dual-info", "S-title-dual-column-action", "W-content-side-slots", "unknown",
    "S-title-anchor", "S-title-content-action", "S-title-primary-secondary-action",
])
def test_weather_rejects_other_layouts(layout):
    sample = fixture(layout)
    assert themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) is not None


@pytest.mark.parametrize("alignment", ["center", "end"])
@pytest.mark.parametrize("layout", ["S-title-content", "S-title-dual-content"])
def test_weather_checks_content_alignment_even_in_bottom_layout(alignment, layout):
    sample = fixture(layout, alignment)
    assert themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) == "小花图片的天气内容未居左"


def test_bottom_weather_content_does_not_inherit_sleep_three_line_limit():
    sample = fixture(alignment="start", lines=4)
    assert themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) is None


@pytest.mark.parametrize("layout", ["S-title-content", "S-title-dual-content"])
@pytest.mark.parametrize("value_alignment, distribution, matches", [
    ("start", "start", True), ("end", "spaceBetween", False),
    ("start", "spaceBetween", False),
])
def test_weather_checks_label_and_value_alignment(layout, value_alignment, distribution, matches):
    sample = fixture(layout)
    rows = [json.loads(line) for line in sample.layout.splitlines()]
    rows[2] = ["reading", "TableText", {"items": [
        {"label": "空气质量", "value": {"path": WEATHER_PATH}},
    ]}]
    sample.layout = "\n".join(json.dumps(row) for row in rows)
    sample.nodes[2] = {"id": "reading", "component": "Column", "children": ["reading_row"],
                       "styles": {"alignItems": "start"}}
    sample.nodes.extend([
        {"id": "reading_row", "component": "Row", "children": ["label", "value"],
         "styles": {"justifyContent": distribution}},
        {"id": "label", "component": "Text", "content": "空气质量",
         "styles": {"maxLines": 1, "textAlign": "start"}},
        {"id": "value", "component": "Text", "content": "良",
         "styles": {"maxLines": 1, "textAlign": value_alignment}},
    ])
    reason = themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                                 final_layout=sample.layout)
    assert (reason is None) is matches


@pytest.mark.parametrize("extra", ["phoneBattery", "calendar", "healthSport", "countdown"])
def test_weather_rejects_other_business_roots(extra):
    request = task()
    request.get("dataModelSchema", {}).get("data", {})[extra] = {}
    sample = fixture()
    assert themes.photo_reason(photo(), request, photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) is not None


@pytest.mark.parametrize("path", [
    "/data/weather/current/alertLevel", "/data/weather/daily/1/rainProbabilityPercent",
    "/data/weather/daily/1/precipitation", "/data/phoneBattery/level",
])
def test_weather_rejects_foreign_bindings_and_special_weather(path):
    sample = fixture(path=path)
    assert themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) is not None


@pytest.mark.parametrize("query", ["天气预警", "明天降雨", "纯色天气", "不要背景图"])
def test_weather_respects_user_preferences_and_weather_scenes(query):
    request = task()
    request["userQuery"] = query
    sample = fixture()
    assert themes.photo_reason(photo(), request, photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) is not None


@pytest.mark.parametrize("change", ["size", "schema", "layout", "lines", "viewport"])
def test_weather_requires_complete_semantics_not_guessed_geometry(change):
    request = task()
    sample = fixture()
    evidence = photo_layout_evidence(sample.nodes)
    if change == "size":
        request["size"] = "2x4"
    elif change == "schema":
        request["dataModelSchema"] = {}
    elif change == "layout":
        sample.layout = None
    elif change == "lines":
        evidence.get("textFlow", {}).get("reading", {})["maxLines"] = None
    else:
        evidence["deviceGeometryKnown"] = True
    assert themes.photo_reason(photo(), request, evidence, final_layout=sample.layout) is not None


@pytest.mark.parametrize("component", ["CircleButton", "PillButton", "CardButton"])
@pytest.mark.parametrize("location", ["header", "content", "bottom"])
def test_weather_rejects_every_button_type_even_without_click_handler(component, location):
    sample = fixture()
    rows = [json.loads(line) for line in sample.layout.splitlines()]
    rows.append(["action", component, {"label": "查看天气"}])
    if location == "header":
        rows[1].append(["action"])
    elif location == "content":
        rows[2].append(["action"])
    else:
        rows[0][3].append("action")
    sample.layout = "\n".join(json.dumps(row) for row in rows)
    reason = themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                                 final_layout=sample.layout)
    assert reason == "小花图片不允许任何按钮或独立可点击控件"


@pytest.mark.parametrize("identity", ["header", "reading"])
def test_weather_rejects_clickable_content_without_button_type(identity):
    sample = fixture()
    rows = [json.loads(line) for line in sample.layout.splitlines()]
    for row in rows:
        if row[0] == identity:
            row[2]["onClick"] = [{"call": "clickToDeeplink", "args": {}}]
    sample.layout = "\n".join(json.dumps(row) for row in rows)
    reason = themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                                 final_layout=sample.layout)
    assert reason == "小花图片不允许任何按钮或独立可点击控件"


@pytest.mark.parametrize("component, clickable", [
    ("Button", False), ("Button", True), ("Stack", True), ("Image", True),
])
def test_weather_rejects_buttons_in_final_a2ui_evidence(component, clickable):
    sample = fixture()
    handler = [{"call": "clickToDeeplink", "args": {}}] if clickable else []
    sample.nodes.append({"id": "action", "component": component,
                         "onClick": handler})
    reason = themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                                 final_layout=sample.layout)
    assert reason == "小花图片不允许任何按钮或独立可点击控件"


def test_weather_allows_decorative_icon_and_existing_whole_card_event():
    sample = fixture()
    handler = [{"call": "clickToDeeplink", "args": {}}]
    rows = [json.loads(line) for line in sample.layout.splitlines()]
    rows[0][2]["onClick"] = handler
    rows[1][2]["icon"] = "resources/base/media/sun_max.svg"
    sample.layout = "\n".join(json.dumps(row) for row in rows)
    sample.nodes[0]["onClick"] = handler
    sample.nodes.append({"id": "header_icon", "component": "Image", "styles": {}})
    assert themes.photo_reason(photo(), task(), photo_layout_evidence(sample.nodes),
                               final_layout=sample.layout) is None


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("layout", ["S-title-content", "S-title-anchor", "S-title-content-action"])
def test_weather_selection_preserves_foreground_and_does_not_render(monkeypatch, enabled, layout):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    process = AsyncMock(side_effect=RuntimeError("Cloud must not measure a guessed viewport"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", process)
    sample = fixture(layout)
    source = themes.encode([{"updateComponents": {"components": sample.nodes}}])
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": PHOTO_ID})))
    result, audit = asyncio.run(themes.select_theme(
        source, task(), client, final_layout=sample.layout,
    ))
    weather_ids = {PHOTO_ID, "photo-ux-flowers-weather-square"}
    assert (audit.get("themeId") in weather_ids) is (enabled and layout == "S-title-content")
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
    assert audit.get("deviceGeometryKnown") is False
    process.assert_not_called()


@pytest.mark.parametrize("change", [
    {"business": "sleep"}, {"sizes": ["2x4"]},
    {"contentEligibility": {"kind": "weather-square", "layouts": {"S-center": "left"}}},
    {"contentEligibility": {"kind": "weather-square", "layouts": {"S-title-content": "bottom"}}},
    {"contentEligibility": {"kind": "weather-square", "layouts": {"S-title-anchor": "left"}}},
    {"contentEligibility": {"kind": "weather-square",
                            "layouts": {"S-title-content-action": "left"}}},
    {"contentEligibility": {"kind": "weather-square",
                            "layouts": {"S-title-primary-secondary-action": "left"}}},
    {"contentEligibility": {"kind": "weather-square"}},
])
def test_weather_registry_rejects_inconsistent_policy(change):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == PHOTO_ID)
    entry.update(change)
    with pytest.raises(ValueError):
        registry.validate_registry(config)


def test_weather_uses_existing_white_foreground_without_new_overlays():
    config = registry.load_theme_registry()
    sleep = next(item for item in config.get("themes", [])
                 if item.get("id") == "photo-ux-sleep-square")
    entry = next(item for item in config.get("themes", []) if item.get("id") == PHOTO_ID)
    assert entry.get("content") == sleep.get("content")
    assert entry.get("background", {}).get("objectFit") == "fill"
