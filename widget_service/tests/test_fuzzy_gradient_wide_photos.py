"""天气与倒计时新增宽图复用主焦点门禁、主体优先和等概率选择。"""

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_uniform_photo_eligibility import choose, rejection
from test_wide_photo_focus import focus_sample

FUZZY = "photo-ux-pink-sunset-lake-wide"
GRADIENT = "photo-ux-gradient-wide"
WAVE = "photo-ux-mountain-sunset-lake-wide"
LOCAL_CLOUD = "photo-ux-cumulus-blue-wide"


def test_new_wide_assets_registered_with_approved_foreground_colors():
    photos = {item.get("id"): item for item in registry.registered_themes("photos")}
    cases = ((FUZZY, "weather", "FFFFFF"), (GRADIENT, "countdown", "000000"))
    for identity, business, rgb in cases:
        item = photos.get(identity)
        assert item is not None
        assert item.get("size") == "2x4"
        expected_policy = {"kind": "uniform", "businesses": [business]}
        if identity == GRADIENT:
            expected_policy["wideLayout"] = "top-focus"
        assert item.get("contentEligibility") == expected_policy
        assert item.get("selectionPriority", 0) == 0
        roles = item.get("content", {}).get("roles", {})
        assert [roles.get(role) for role in ("primary", "secondary", "tertiary")] == [
            "#FF" + rgb, "#CC" + rgb, "#99" + rgb,
        ]
        graphics = ("graphicPrimary", "graphicSecondary", "graphicTertiary")
        assert [roles.get(role) for role in graphics] == ["#FF" + rgb, "#CC" + rgb, "#99" + rgb]
        assert item.get("content", {}).get("panelBySize", {}).get("2x4") == "#33FFFFFF"
        assert roles.get("componentSecondary") == "#33FFFFFF"
        assert roles.get("componentTertiary") == "#1AFFFFFF"


@pytest.mark.parametrize("layout,selected", [
    ("left", FUZZY), ("left", WAVE), ("left", LOCAL_CLOUD),
])
@pytest.mark.parametrize("response", ["invalid", '{"themeId":"gradient-blue"}'])
def test_weather_wide_candidates_share_one_unweighted_choice(monkeypatch, layout, selected,
                                                            response):
    calls = []

    def choice(items):
        calls.append(items)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", choice)
    saved = focus_sample("weather", 4, layout)
    result, audit = choose(saved, monkeypatch, response)
    assert len(calls) == 1
    expected = {FUZZY, LOCAL_CLOUD}
    if layout != "top":
        expected.add(WAVE)
    assert set(calls[0]) == expected
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_countdown_wide_subject_precedes_abstract_without_holiday_name(monkeypatch, layout):
    saved = focus_sample("countdown", 4, layout)
    result, audit = choose(saved, monkeypatch)
    expected = {GRADIENT} if layout == "top" else set()
    if layout == "left":
        expected.add("photo-ux-glass-hourglass-wide")
    if expected:
        assert set(audit.get("candidates", [])) == expected
        assert audit.get("themeId") in expected
    else:
        assert not any(identity.startswith("photo-") for identity in audit.get("candidates", []))
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("identity,business", [(FUZZY, "countdown"), (GRADIENT, "weather"),
                                             (FUZZY, "sleep"), (GRADIENT, "calendar")])
def test_new_wide_subjects_reject_other_primary_businesses(identity, business):
    assert rejection(focus_sample(business, 1), identity)


@pytest.mark.parametrize("identity,business,expected", [
    (FUZZY, "weather", {WAVE, LOCAL_CLOUD}),
    (GRADIENT, "countdown", {"photo-ux-texture-orange-diamond-wide",
                             "photo-ux-texture-orange-diagonal-wide"}),
])
def test_disabled_new_subject_preserves_existing_fallback(monkeypatch, identity, business,
                                                        expected):
    config = registry.load_theme_registry()
    for item in config.get("themes", []):
        if item.get("id") == identity:
            item["enabled"] = False
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    layout = "left" if business == "weather" else "top"
    _, audit = choose(focus_sample(business, 1, layout), monkeypatch)
    assert set(audit.get("candidates", [])) == expected


@pytest.mark.parametrize("identity,business", [(FUZZY, "weather"), (GRADIENT, "countdown")])
def test_new_wide_photos_do_not_become_square_candidates(identity, business):
    saved = focus_sample(business, 1)
    saved.task["size"] = "2x2"
    assert rejection(saved, identity)


@pytest.mark.parametrize("variant", ["continuous", "bottom-details", "equal"])
@pytest.mark.parametrize("title", [False, True])
@pytest.mark.parametrize("identity", [WAVE, FUZZY, LOCAL_CLOUD])
def test_weather_lakes_and_cloud_reject_every_top_bottom_variant(variant, title, identity):
    saved = focus_sample("weather", 2, "top", variant, title)
    assert "左主焦点" in rejection(saved, identity)


def test_model_cannot_select_mountain_lake_for_top_bottom(monkeypatch):
    saved = focus_sample("weather", 2, "top")
    result, audit = choose(saved, monkeypatch, '{"themeId":"' + WAVE + '"}')
    assert WAVE not in audit.get("candidates", [])
    assert audit.get("themeId") != WAVE
    assert "左主焦点" in audit.get("rejected", {}).get(WAVE, "")
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
