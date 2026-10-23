"""UX六张新素材的业务归属、通用准入、替换清理和同级随机选择回归。"""

from pathlib import Path

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_autumn_calendar_photos import expanded
from test_uniform_photo_eligibility import PATHS, choose, photo, rejection, sample

BIRDS = "photo-ux-birds-countdown-square"
ARCH = "photo-ux-sand-arch-square"
WEATHER = "photo-ux-starfield-weather-square"
VIOLIN = "photo-ux-violin-stage-square"
BATTERY = "photo-ux-starry-sky-square"
WIDE_BATTERY = "photo-ux-starry-sky-wide"
CLOUDS = "photo-ux-clouds-weather-square"
CASES = [
    (BIRDS, ("holiday",), False),
    (ARCH, ("sport",), False),
    (WEATHER, ("weather",), False),
    (VIOLIN, ("earphone", "music"), False),
    (BATTERY, ("battery",), False),
    (WIDE_BATTERY, ("battery",), True),
]


@pytest.mark.parametrize("identity,businesses,wide", CASES)
@pytest.mark.parametrize("business", ["calendar", "countdown", "sport", "weather",
                                     "earphone", "music", "battery", "sleep"])
def test_new_photos_only_match_assigned_business(identity, businesses, wide, business):
    saved = sample(PATHS.get(business), 2, wide=wide, title="假期")
    category = "holiday" if business == "countdown" else business
    assert (rejection(saved, identity) is None) is (category in businesses)
    assert photo(identity).get("contentEligibility") == {
        "kind": "uniform", "businesses": list(businesses),
    }


@pytest.mark.parametrize("identity,businesses,wide", CASES)
@pytest.mark.parametrize("lines,allowed", [(1, True), (3, True), (4, False)])
def test_new_photos_keep_shared_line_limit_with_buttons(identity, businesses, wide, lines, allowed):
    business = "countdown" if businesses[0] == "holiday" else businesses[0]
    saved = sample(PATHS.get(business), lines, wide=wide, button=True, title="假期")
    assert (rejection(saved, identity) is None) is allowed


@pytest.mark.parametrize("identity,businesses,wide", CASES)
def test_new_photos_still_honor_explicit_no_photo_request(identity, businesses, wide):
    business = "countdown" if businesses[0] == "holiday" else businesses[0]
    saved = sample(PATHS.get(business), 1, wide=wide)
    saved.task["userQuery"] = "不要图片"
    assert rejection(saved, identity) == "用户明确其它主题或不要图片"


@pytest.mark.parametrize("identity", [
    "photo-ux-autumn-square", "photo-ux-yellow-arch-square", "photo-ux-violin-music-square",
])
def test_replaced_photos_are_removed_from_registry_and_assets(identity):
    entries = registry.registered_themes(include_disabled=True)
    assert identity not in {item.get("id") for item in entries}
    name = "bg_ux_" + identity.removeprefix("photo-ux-").replace("-", "_") + ".jpg"
    assert not (Path(__file__).parents[2] / "resources/base/media" / name).exists()


@pytest.mark.parametrize("selected", [CLOUDS, WEATHER])
def test_eligible_weather_images_share_the_same_uniform_choice(monkeypatch, selected):
    calls = []

    def choice(items):
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = sample(PATHS.get("weather"), 1, button=False)
    result, audit = choose(saved, monkeypatch)
    assert len(calls) == 1
    assert set(calls[0]) == {CLOUDS, WEATHER}
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_calendar_no_longer_uses_arch_and_can_fall_back_to_abstract(monkeypatch):
    saved = sample(PATHS.get("calendar"), 2)
    assert rejection(saved, ARCH)
    _, audit = choose(saved, monkeypatch)
    assert audit.get("candidates") == ["photo-ux-meeting-room-square"]
    saved = sample(PATHS.get("calendar"), 2, align="center")
    _, audit = choose(saved, monkeypatch)
    candidates = audit.get("candidates", [])
    assert len(candidates) == 2
    assert all(item.startswith("photo-ux-texture-blue-") for item in candidates)


def test_centered_weather_can_still_fall_back_to_abstract(monkeypatch):
    saved = sample(PATHS.get("weather"), 2, align="center")
    assert rejection(saved, CLOUDS)
    assert rejection(saved, WEATHER)
    _, audit = choose(saved, monkeypatch)
    assert audit.get("themeId", "").startswith("photo-ux-texture-blue-")


@pytest.mark.parametrize("wide", [False, True])
def test_battery_subject_precedes_abstract_without_relayout(monkeypatch, wide):
    identity = WIDE_BATTERY if wide else BATTERY
    saved = sample(PATHS.get("battery"), 3, wide=wide)
    result, audit = choose(saved, monkeypatch)
    if wide:
        assert all(not item.startswith("photo-") for item in audit.get("candidates", []))
    else:
        assert audit.get("candidates") == [identity]
        assert audit.get("themeId") == identity
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


def test_wide_battery_rejects_right_main_focus():
    saved = sample(PATHS.get("battery"), 2, wide=True)
    rows = themes.decode(saved.compact)
    rows[0][2]["orientation"] = "content-right"
    assert rejection(expanded(rows, saved.task), WIDE_BATTERY)


def test_wide_battery_does_not_match_a_square_layout():
    saved = sample(PATHS.get("battery"), 2)
    saved.task["size"] = "2x4"
    assert rejection(saved, WIDE_BATTERY)
