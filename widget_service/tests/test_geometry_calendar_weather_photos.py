"""纯文字会议和天气等概率选图；不依赖端侧像素，不改变布局。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.theme_content_regions import photo_layout_evidence
from test_autumn_calendar_photos import calendar_sample, photo, rejection
from test_weather_photo_eligibility import fixture, task

CALENDAR = "photo-ux-desk-lamp-calendar-square"
WEATHER = ["photo-ux-water-lily-square", "photo-ux-flowers-weather-square"]


@pytest.mark.parametrize("alignment", ["start", "center", "end"])
@pytest.mark.parametrize("lines", [1, 3, 5])
def test_desk_lamp_calendar_allows_header_icon_and_unrestricted_body_text(alignment, lines):
    sample = calendar_sample("S-title-content")
    node = next(item for item in sample.nodes if item.get("id") == "primary_main")
    node.get("styles", {}).update(textAlign=alignment, maxLines=lines)
    assert rejection(sample, CALENDAR) is None
    final = themes.apply_theme(sample.source, photo(CALENDAR), sample.task, {})
    assert themes.foreground_signature(final) == themes.foreground_signature(sample.source)
    assert photo(CALENDAR).get("content", {}).get("roles", {}).get("primary") == "#FF000000"


@pytest.mark.parametrize("change", [
    "content-icon", "orphan-icon", "chart", "pill", "circle", "clickable-text",
    "mixed", "static-body", "missing-header", "wide",
])
def test_desk_lamp_calendar_rejects_non_text_body_and_other_business(change):
    if change in {"pill", "circle"}:
        layout = "S-title-content-action" if change == "pill" else "S-title-anchor"
        component = "PillButton" if change == "pill" else "CircleButton"
        sample = calendar_sample(layout, component)
    else:
        sample = calendar_sample("S-title-content")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    body = next(row for row in rows if row[0] == "primary")
    if change in {"content-icon", "orphan-icon", "chart"}:
        component = "ProgressCircle" if change == "chart" else "Image"
        sample.nodes.append({"id": "visual", "component": component})
        if change != "orphan-icon":
            parent = next(node for node in sample.nodes if node.get("id") == "primary")
            parent.setdefault("children", []).append("visual")
    elif change == "clickable-text":
        body[2]["onClick"] = [{"call": "open"}]
    elif change == "mixed":
        body[2]["secondaryText"] = {"path": "/data/phoneBattery/level"}
    elif change == "static-body":
        body[2] = {"mainText": "下午开会"}
    elif change == "missing-header":
        header = next(row for row in rows if row[0] == "header")
        header[1] = "TextBlock"
    elif change == "wide":
        sample.task["size"] = "2x4"
    sample.compact = '\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)
    assert rejection(sample, CALENDAR) is not None


def test_desk_lamp_calendar_allows_whole_card_click_not_independent_button():
    sample = calendar_sample("S-title-content")
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    rows[0][2]["onClick"] = [{"call": "open"}]
    root = next(node for node in sample.nodes if node.get("id") == "root")
    root["onClick"] = [{"call": "open"}]
    sample.compact = '\n'.join(json.dumps(row) for row in rows)
    assert rejection(sample, CALENDAR) is None


@pytest.mark.parametrize("layout,alignment,allowed", [
    ("S-title-content", "start", True), ("S-title-dual-content", "start", True),
    ("S-title-content", "end", False), ("S-title-content-action", "start", False),
])
def test_two_weather_photos_have_identical_eligibility(layout, alignment, allowed):
    sample = fixture(layout, alignment)
    evidence = photo_layout_evidence(sample.nodes)
    for identity in WEATHER:
        reason = themes.photo_reason(photo(identity), task(), evidence, final_layout=sample.layout)
        assert (reason is None) is allowed
    first_policy = photo(WEATHER[0]).get("contentEligibility")
    assert first_policy == photo(WEATHER[1]).get("contentEligibility")
    assert photo(WEATHER[0]).get("content") == photo(WEATHER[1]).get("content")


@pytest.mark.parametrize("chosen", WEATHER)
@pytest.mark.parametrize("model_choice", [*WEATHER, "gradient-blue", "invalid-json"])
def test_weather_uniform_choice_cannot_be_biased_by_model(monkeypatch, chosen, model_choice):
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    chooser = Mock(return_value=chosen)
    monkeypatch.setattr(themes.secrets, "choice", chooser)
    sample = fixture()
    source = themes.encode([{"updateComponents": {"components": sample.nodes}}])
    raw = model_choice if model_choice == "invalid-json" else json.dumps({"themeId": model_choice})
    client = SimpleNamespace(generate=AsyncMock(return_value=raw))
    final, audit = asyncio.run(themes.select_theme(
        source, task(), client, final_layout=sample.layout,
    ))
    chooser.assert_called_once_with(WEATHER)
    assert audit.get("themeId") == chosen
    assert set(audit.get("candidates", [])) == set(WEATHER)
    assert audit.get("photoSelection", {}).get("selected") == chosen
    assert themes.foreground_signature(final) == themes.foreground_signature(source)


@pytest.mark.parametrize("ids", [[WEATHER[0]], [CALENDAR], []])
def test_uniform_choice_never_adds_ineligible_photos_or_changes_other_business(monkeypatch, ids):
    chooser = Mock(side_effect=AssertionError("No equivalent candidates"))
    monkeypatch.setattr(themes.secrets, "choice", chooser)
    selected = ids[0] if ids else "gradient-blue"
    candidates = [photo(identity) for identity in ids]
    result, audit = themes.select_equivalent_photo(selected, candidates)
    assert result == selected
    assert audit == {}
    chooser.assert_not_called()


@pytest.mark.parametrize("change", ["missing", "standard", "duplicate", "other-business", "mode"])
def test_selection_group_rejects_inconsistent_configuration(change):
    config = registry.load_theme_registry()
    groups = config.get("photoSelectionGroups", [])
    assert groups
    group = groups[0]
    if change == "mode":
        group["mode"] = "model"
    elif change == "duplicate":
        groups.append(copy.deepcopy(group))
    else:
        replacement = {"missing": "missing", "standard": "gradient-blue",
                       "other-business": CALENDAR}.get(change)
        assert replacement
        group["themeIds"] = [WEATHER[0], replacement]
    with pytest.raises(ValueError):
        registry.validate_registry(config)
