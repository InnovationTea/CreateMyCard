"""Weather photos preserve the shared gates and honor the approved cloud priority."""

import copy
import json

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_autumn_calendar_photos import expanded
from test_clouds_photo_top_content import CLOUDS, weather_sample
from test_uniform_photo_eligibility import PATHS, choose, rejection, sample

SQUARE = "photo-ux-wave-square"
WIDE = "photo-ux-wave-wide"
STARFIELD = "photo-ux-starfield-weather-square"


@pytest.mark.parametrize("lines", [1, 2])
@pytest.mark.parametrize("response", ["invalid", json.dumps({"themeId": STARFIELD})])
def test_qualified_clouds_take_priority_over_both_other_weather_photos(
    monkeypatch, lines, response,
):
    saved = weather_sample(lines)
    for identity in (CLOUDS, SQUARE, STARFIELD):
        assert rejection(saved, identity) is None
    result, audit = choose(saved, monkeypatch, response)
    assert audit.get("candidates") == [CLOUDS]
    assert audit.get("themeId") == CLOUDS
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("selected", [SQUARE, STARFIELD])
@pytest.mark.parametrize("response", ["invalid", json.dumps({"themeId": CLOUDS})])
def test_wave_and_starfield_share_one_unweighted_draw_when_clouds_fail(
    monkeypatch, selected, response,
):
    calls = []

    def choice(items):
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = sample(PATHS.get("weather"), 3)
    assert rejection(saved, CLOUDS)
    result, audit = choose(saved, monkeypatch, response)
    assert len(calls) == 1
    assert len(calls[0]) == 2
    assert set(calls[0]) == {SQUARE, STARFIELD}
    assert set(audit.get("candidates", [])) == {SQUARE, STARFIELD}
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_disabled_clouds_do_not_override_the_shared_weather_draw(monkeypatch):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == CLOUDS)
    entry["enabled"] = False
    monkeypatch.setattr(registry, "load_theme_registry", lambda: copy.deepcopy(config))
    _, audit = choose(weather_sample(1), monkeypatch)
    assert set(audit.get("candidates", [])) == {SQUARE, STARFIELD}


@pytest.mark.parametrize("identity,wide", [(SQUARE, False), (WIDE, True)])
@pytest.mark.parametrize("lines", [1, 2, 3, 4, 5])
def test_wave_body_limit_excludes_title_and_button(identity, wide, lines):
    saved = sample(PATHS.get("weather"), lines, wide=wide)
    assert (rejection(saved, identity) is None) is (lines <= (4 if wide else 3))


@pytest.mark.parametrize("business", ["sleep", "sport", "calendar", "earphone", "battery"])
@pytest.mark.parametrize("identity,wide", [(SQUARE, False), (WIDE, True)])
def test_wave_does_not_match_other_main_businesses(identity, wide, business):
    saved = sample(PATHS.get(business), 1, wide=wide)
    assert rejection(saved, identity)


@pytest.mark.parametrize("main_weather", [False, True])
def test_wide_weather_depends_on_main_region_not_right_slot(monkeypatch, main_weather):
    main = "weather" if main_weather else "sleep"
    side = "sleep" if main_weather else "weather"
    saved = sample(PATHS.get(main), 3, wide=True)
    rows = themes.decode(saved.compact)
    upper = next(row for row in rows if row[0] == "upper")
    upper[2]["primaryText"] = {"path": PATHS.get(side)}
    rows.append([PATHS.get(side), "Side"])
    saved = expanded(rows, saved.task)
    result, audit = choose(saved, monkeypatch)
    assert (WIDE in audit.get("candidates", [])) is main_weather
    if main_weather:
        expected = {WIDE, "photo-ux-fuzzy-wide"}
        assert set(audit.get("candidates", [])) == expected
        assert audit.get("themeId") in expected
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_wide_weather_accepts_right_main_but_rejects_unrecognized_layouts():
    saved = sample(PATHS.get("weather"), 2, wide=True)
    rows = themes.decode(saved.compact)
    rows[0][2]["orientation"] = "content-right"
    assert rejection(expanded(rows, saved.task), WIDE) is None
    saved = sample(PATHS.get("weather"), 2)
    saved.task["size"] = "2x4"
    assert rejection(saved, WIDE)


@pytest.mark.parametrize("align", ["center", "end"])
def test_square_wave_still_requires_whole_body_left_alignment(align):
    assert rejection(sample(PATHS.get("weather"), 2, align=align), SQUARE)


@pytest.mark.parametrize("value", [-1, True, "1", None, 1.5])
def test_photo_priority_rejects_invalid_values(value):
    config = registry.load_theme_registry()
    entry = next(item for item in config.get("themes", []) if item.get("id") == CLOUDS)
    entry["selectionPriority"] = value
    with pytest.raises(ValueError, match="selectionPriority"):
        registry.validate_registry(config)


def test_only_clouds_have_explicit_priority():
    priorities = {}
    for item in registry.registered_themes(include_disabled=True):
        priority = item.get("selectionPriority", 0)
        if priority:
            priorities[item.get("id")] = priority
    assert priorities == {CLOUDS: 1}
