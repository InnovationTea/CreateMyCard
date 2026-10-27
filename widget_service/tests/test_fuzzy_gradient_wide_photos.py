"""天气与倒计时新增宽图复用主焦点门禁、主体优先和等概率选择。"""

import pytest

from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_uniform_photo_eligibility import choose, rejection
from test_wide_photo_focus import focus_sample

FUZZY = "photo-ux-fuzzy-wide"
GRADIENT = "photo-ux-gradient-wide"
WAVE = "photo-ux-wave-wide"


def test_new_wide_assets_registered_with_approved_foreground_colors():
    photos = {item.get("id"): item for item in registry.registered_themes("photos")}
    cases = ((FUZZY, "weather", "FFFFFF"), (GRADIENT, "countdown", "000000"))
    for identity, business, rgb in cases:
        item = photos.get(identity)
        assert item is not None
        assert item.get("size") == "2x4"
        assert item.get("contentEligibility") == {
            "kind": "uniform", "businesses": [business], "wideLayout": "main-focus",
        }
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


@pytest.mark.parametrize("layout", ["left", "right", "top"])
@pytest.mark.parametrize("selected", [FUZZY, WAVE])
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
    assert len(calls[0]) == 2
    assert set(calls[0]) == {FUZZY, WAVE}
    assert set(audit.get("candidates", [])) == {FUZZY, WAVE}
    assert audit.get("themeId") == selected
    assert audit.get("photoSelection", {}).get("mode") == "uniform"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_countdown_wide_subject_precedes_abstract_without_holiday_name(monkeypatch, layout):
    saved = focus_sample("countdown", 4, layout)
    result, audit = choose(saved, monkeypatch)
    expected = {GRADIENT}
    if layout in {"left", "right"}:
        expected.add("photo-ux-hourglass-wide")
    assert set(audit.get("candidates", [])) == expected
    assert audit.get("themeId") in expected
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("identity,business", [(FUZZY, "countdown"), (GRADIENT, "weather"),
                                             (FUZZY, "sleep"), (GRADIENT, "calendar")])
def test_new_wide_subjects_reject_other_primary_businesses(identity, business):
    assert rejection(focus_sample(business, 1), identity)


@pytest.mark.parametrize("identity,business,expected", [
    (FUZZY, "weather", {WAVE}),
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
    _, audit = choose(focus_sample(business, 1), monkeypatch)
    assert set(audit.get("candidates", [])) == expected


@pytest.mark.parametrize("identity,business", [(FUZZY, "weather"), (GRADIENT, "countdown")])
def test_new_wide_photos_do_not_become_square_candidates(identity, business):
    saved = focus_sample(business, 1)
    saved.task["size"] = "2x2"
    assert rejection(saved, identity)
