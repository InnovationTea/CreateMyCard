"""Current date cards share calendar photos without classifying all time fields as calendar."""

import pytest

from photo_samples.common import expanded
from services import post_layout_theme as themes
from services.compact_high_level_components import ComponentRow
from services.theme_texture_eligibility import visible_business
from test_uniform_photo_eligibility import BLUE, choose, evidence, rejection, sample

DATE = "/data/currentTime/currentDate"
WEEKDAY = "/data/currentTime/dayOfWeek"
LUNAR = "/data/currentTime/lunarDate"
MEETING = "photo-ux-meeting-room-square"


def current_date_card():
    rows = [
        ["root", "Layout", {"layout": "S-title-content"}, ["title", "content"]],
        ["title", "SingleLineTitle", {"title": "今日日历"}],
        ["content", "Group", {"variant": "hero-support"}, ["primary", "support"]],
        ["primary", "EmphasisText", {"mainText": {"path": DATE},
                                    "secondaryText": {"path": WEEKDAY}, "fontSize": 18}],
        ["support", "SecondaryBody", {"items": [{"label": "农历 ", "value": {"path": LUNAR}}],
                                      "fontSize": 14}],
        [DATE, "2026-10-22"], [WEEKDAY, "星期四"], [LUNAR, "九月十三"],
    ]
    return expanded(rows, {"size": "2x2", "userQuery": "添加一个简单明了清晰的小日历卡片",
                           "appVersion": "11.7.8.990"})


def test_current_date_card_is_three_lines_and_matches_calendar_subject(monkeypatch):
    saved = current_date_card()
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("root", {})
    assert flow.get("lineCount") == 3
    assert flow.get("leftAligned") is True
    assert rejection(saved, MEETING) is None
    assert rejection(saved, BLUE) is None
    final, audit = choose(saved, monkeypatch)
    expected = {MEETING, "photo-ux-meeting-room-brown-chairs-square",
                "photo-ux-meeting-room-green-chairs-square"}
    assert audit.get("themeId") in expected
    assert set(audit.get("candidates", [])) == expected
    assert themes.foreground_signature(final) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("path", [DATE, WEEKDAY, LUNAR])
def test_registered_date_fields_are_calendar(path):
    rows = [ComponentRow("date", "Text", {"content": {"path": path}})]
    assert visible_business(rows) == "calendar"


@pytest.mark.parametrize("path", [
    "/data/currentTime/updatedAt", "/data/currentTime/currentTime",
    "/data/currentTime/unknown", "/data/weather/currentDate",
])
def test_unknown_time_fields_and_other_businesses_do_not_become_calendar(path):
    rows = [ComponentRow("date", "Text", {"content": {"path": path}})]
    assert visible_business(rows) != "calendar"


def test_date_plus_weather_is_not_a_single_calendar_business():
    rows = [
        ComponentRow("date", "Text", {"content": {"path": DATE}}),
        ComponentRow("weather", "Text", {"content": {"path": "/data/weather/condition"}}),
    ]
    assert visible_business(rows) is None


def test_calendar_date_keeps_line_and_alignment_gates():
    assert "超过3行" in rejection(sample(DATE, lines=4), MEETING)
    assert "整体居左" in rejection(sample(DATE, lines=3, align="center"), MEETING)
