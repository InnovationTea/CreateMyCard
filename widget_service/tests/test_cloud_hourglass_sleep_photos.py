"""新增素材沿用既有准入，保留旧睡眠图，云图停用与睡眠OBS交付均显式验证。"""

import hashlib
from pathlib import Path

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_clouds_photo_top_content import weather_sample
from test_holiday_weather_panel_photos import panels
from test_photo_icon_exclusion import with_icon
from test_uniform_photo_eligibility import PATHS, choose, photo, rejection, sample
from test_wide_photo_focus import focus_sample
from theme_preference_samples import preference, reply

HOURGLASS = "photo-ux-hourglass-square"
HOURGLASS_WIDE = "photo-ux-hourglass-wide"
SLEEP = "photo-ux-sleep-new-square"
SLEEP_WIDE = "photo-ux-sleep-new-wide"
CLOUDS = ("photo-ux-cloud-square", "photo-ux-cloud-wide")
ENABLED = (HOURGLASS, HOURGLASS_WIDE, SLEEP, SLEEP_WIDE)
DELIVERY_FILES = {
    CLOUDS[0]: "310cbbc7dc6b4752bf38c0e88a5087c1.jpg",
    CLOUDS[1]: "25ec17b9e36c4a16834a95319f1c24e8.jpg",
    HOURGLASS: "ef44837f61cd47949f7c4eebea9ef222.jpg",
    HOURGLASS_WIDE: "0b6a28db9fac47da8d2f1b6e65500e03.jpg",
    SLEEP: "a81b453ae4e342869f450aa1296a0c1e.jpg",
    SLEEP_WIDE: "96e20efa1a7f4296a6ec52cd62560a0e.jpg",
}


def matching_sample(identity):
    business = "countdown" if identity.startswith("photo-ux-hourglass") else "sleep"
    if identity.endswith("wide"):
        return focus_sample(business, 4, "left")
    return sample(PATHS.get(business), 3, title="生日" if business == "countdown" else "睡眠")


@pytest.mark.parametrize("identity", [*ENABLED, *CLOUDS])
def test_downloaded_assets_match_registry_and_both_repository_copies(identity):
    item = photo(identity)
    root = Path(__file__).parents[2]
    src = item.get("src")
    assert isinstance(src, str)
    local = root / src
    renderer = root / "debug_tools/a2ui_render/entry/src/main" / src
    data = local.read_bytes()
    assert data == renderer.read_bytes()
    assert hashlib.sha256(data).hexdigest() == item.get("source", {}).get("assetSha256")
    assert len(data) == item.get("source", {}).get("assetBytes")
    expected_file = DELIVERY_FILES.get(identity)
    assert expected_file is not None
    assert item.get("remoteUrl", "").endswith("/" + expected_file)


def test_sleep_original_assets_and_urls_remain_separate():
    for size, old_file in (
        ("square", "b7096a154b63450bb5008c7ddf03de86.jpg"),
        ("wide", "4ae3f781c7504b06b69e54a721928264.jpg"),
    ):
        old = photo("photo-ux-sleep-" + size)
        new = photo("photo-ux-sleep-new-" + size)
        assert old.get("src", "").endswith("bg_ux_sleep_" + size + ".jpg")
        assert old.get("remoteUrl", "").endswith("/" + old_file)
        assert old.get("source", {}).get("assetSha256") != new.get("source", {}).get("assetSha256")
        assert new.get("src", "").endswith("bg_ux_bed_" + size + ".jpg")
        assert new.get("remoteUrl") != old.get("remoteUrl")


@pytest.mark.parametrize("identity,business", [(HOURGLASS, "countdown"), (SLEEP, "sleep")])
@pytest.mark.parametrize("align", ["start", "center", "end"])
@pytest.mark.parametrize("lines", [1, 3, 4])
def test_square_keeps_three_line_left_aligned_rule(identity, business, align, lines):
    saved = sample(PATHS.get(business), lines, align=align)
    assert (rejection(saved, identity) is None) is (align == "start" and lines <= 3)


@pytest.mark.parametrize("title", ["生日", "考试", "旅行", "中秋节"])
def test_hourglass_allows_non_holiday_names_and_keeps_foreground(monkeypatch, title):
    saved = sample(PATHS.get("countdown"), 3, title=title)
    assert rejection(saved, HOURGLASS) is None
    expected = {HOURGLASS, "photo-ux-glass-hourglass-square"}
    selected = HOURGLASS
    if title == "中秋节":
        selected = "photo-ux-birds-countdown-square"
        expected = {selected}
    monkeypatch.setattr(themes.secrets, "choice", lambda items: selected)
    result, audit = choose(saved, monkeypatch)
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") == selected
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("identity,business", [
    (HOURGLASS_WIDE, "countdown"), (SLEEP_WIDE, "sleep"),
])
@pytest.mark.parametrize("layout", ["left", "right", "top"])
@pytest.mark.parametrize("lines", [1, 4, 5])
def test_wide_accepts_only_side_focus_with_four_main_lines(identity, business, layout, lines):
    saved = focus_sample(business, lines, layout)
    assert (rejection(saved, identity) is None) is (layout != "top" and lines <= 4)


@pytest.mark.parametrize("identity,business", [
    (HOURGLASS_WIDE, "sleep"), (SLEEP_WIDE, "countdown"),
])
def test_wide_never_borrows_business_from_auxiliary_region(identity, business):
    assert rejection(focus_sample(business, 1, "left"), identity)
    for layout in ("W-split-panels", "W-four-slots"):
        assert rejection(panels(layout, lines=1), identity)


@pytest.mark.parametrize("business,new,old", [
    ("sleep", SLEEP_WIDE, "photo-ux-sleep-wide"),
    ("countdown", HOURGLASS_WIDE, "photo-ux-gradient-wide"),
])
@pytest.mark.parametrize("pick_new", [False, True])
def test_wide_same_level_candidates_are_selected_without_weights(monkeypatch, business, new,
                                                               old, pick_new):
    selected = new if pick_new else old
    calls = []

    def choice(items):
        calls.append(list(items))
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = focus_sample(business, 4, "left")
    result, audit = choose(saved, monkeypatch)
    assert len(calls) == 1
    expected = {new, old}
    if business == "countdown":
        expected.add("photo-ux-glass-hourglass-wide")
    assert len(calls[0]) == len(expected)
    assert set(calls[0]) == expected
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("identity", ENABLED)
def test_new_images_obey_user_no_photo_and_colored_icon_exclusion(monkeypatch, identity):
    saved = matching_sample(identity)
    assert rejection(saved, identity) is None
    saved.task["userQuery"] = "不要图片"
    preferences = [preference("backgroundKind", "photo", "不要图片", "avoid")]
    _, audit = choose(saved, monkeypatch, reply(preferences))
    assert all(not item.startswith("photo-") for item in audit.get("candidates", []))
    saved.task["userQuery"] = "显示状态"
    _, audit = choose(with_icon(saved), monkeypatch)
    assert audit.get("photoAssetExclusions")
    assert all(not item.startswith("photo-") for item in audit.get("candidates", []))


@pytest.mark.parametrize("saved", [weather_sample(1), focus_sample("weather", 1, "left")])
def test_pending_clouds_never_enter_candidates_even_if_model_returns_them(monkeypatch, saved):
    enabled = {item.get("id") for item in registry.registered_themes("photos")}
    for identity in CLOUDS:
        assert photo(identity).get("enabled") is False
        assert identity not in enabled
        _, audit = choose(saved, monkeypatch, '{"themeId":"' + identity + '"}')
        assert identity not in audit.get("candidates", [])
        assert audit.get("themeId") != identity
