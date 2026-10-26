"""A17仅启用出行左右主次、正文居下，不放开上下布局或其它主体图。"""

import pytest

from photo_samples.common import expanded
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from test_uniform_photo_eligibility import PATHS, choose, evidence, rejection, sample
from test_wide_photo_focus import focus_sample

AIRPLANE = "photo-ux-airplane-tarmac-wide"


def travel_sample(lines=3, orientation="content-left", align="start", button=False):
    saved = sample(PATHS.get("travel"), lines, wide=True, button=button, align=align)
    rows = themes.decode(saved.compact)
    rows[0][2]["orientation"] = orientation
    return expanded(rows, saved.task)


def test_a17_enabled_with_side_focus_and_bottom_only():
    enabled = {item.get("id"): item for item in registry.registered_themes("photos")}
    item = enabled.get(AIRPLANE)
    assert item is not None
    assert item.get("contentEligibility") == {
        "kind": "uniform", "businesses": ["travel"],
        "wideLayout": "side-focus", "placement": "bottom",
    }


@pytest.mark.parametrize("orientation", ["content-left", "content-right"])
@pytest.mark.parametrize("lines", [1, 3, 4, 5])
@pytest.mark.parametrize("align", ["start", "center", "end"])
def test_a17_bottom_body_counts_actual_lines_without_horizontal_restriction(
    orientation, lines, align,
):
    saved = travel_sample(lines, orientation, align)
    assert (rejection(saved, AIRPLANE) is None) is (lines <= 4)
    assert evidence(saved).get("photoBodyTextFlow", {}).get("main", {}).get("lineCount") == lines


@pytest.mark.parametrize("orientation", ["content-left", "content-right"])
def test_a17_selection_preserves_foreground_and_registered_asset(orientation, monkeypatch):
    saved = travel_sample(4, orientation)
    result, audit = choose(saved, monkeypatch)
    assert audit.get("candidates") == [AIRPLANE]
    assert audit.get("themeId") == AIRPLANE
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    nodes = themes.components(themes.decode(result))
    images = []
    for node in nodes:
        if node.get("id", "").startswith(themes.PREFIX) and node.get("component") == "Image":
            images.append(node)
    assert len(images) == 1
    assert images[0].get("src") == audit.get("theme", {}).get("src")
    assert audit.get("theme", {}).get("remoteUrl", "").startswith("https://")
    root = next(node for node in nodes if node.get("id") == "root")
    assert root.get("styles", {}).get("backgroundColor") == "#FF1F1F99"


@pytest.mark.parametrize("orientation", ["content-left", "content-right"])
@pytest.mark.parametrize("variant", ["title-content-action", "title-hero-support", "center"])
def test_a17_rejects_non_bottom_main_body(orientation, variant):
    saved = travel_sample(1, orientation, button=variant == "title-content-action")
    rows = themes.decode(saved.compact)
    main = next(row for row in rows if row[0] == "main")
    main[2]["variant"] = variant
    if variant == "title-hero-support":
        main[3].append("support")
        rows.append(["support", "Text", {"content": "底部辅助说明"}])
    elif variant == "center":
        main[3] = ["reading"]
        rows = [row for row in rows if row[0] != "title"]
    assert rejection(expanded(rows, saved.task), AIRPLANE)


@pytest.mark.parametrize("variant", ["continuous", "bottom-details", "equal"])
def test_a17_rejects_top_bottom_layout(variant):
    assert rejection(focus_sample("travel", 1, "top", variant), AIRPLANE)


@pytest.mark.parametrize("business", ["weather", "calendar", "countdown", "sleep"])
def test_a17_does_not_use_query_or_auxiliary_business(business):
    saved = sample(PATHS.get(business), 1, wide=True, button=False)
    saved.task["userQuery"] = "航班出行，机场图"
    assert rejection(saved, AIRPLANE)


def test_a17_square_and_empty_body_are_rejected():
    assert rejection(sample(PATHS.get("travel"), 1, button=False), AIRPLANE)
    assert rejection(travel_sample(0), AIRPLANE)


def test_a17_rejects_two_large_panels():
    path = PATHS.get("travel")
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]]]
    for side in ("left", "right"):
        rows.extend([
            [side, "Region", {"variant": "title-content"}, [side + "_title", side + "_text"]],
            [side + "_title", "SingleLineTitle", {"title": "航班"}],
            [side + "_text", "Text", {"content": {"path": path}}],
        ])
    rows.append([path, "MU1234"])
    saved = expanded(rows, {"size": "2x4", "userQuery": "出行", "appVersion": "99.0.0"})
    assert rejection(saved, AIRPLANE)


def test_a17_recognizes_flight_data_and_preserves_disable_switch(monkeypatch):
    saved = sample("/data/flight/flightNumber", 1, wide=True, button=False)
    assert rejection(saved, AIRPLANE) is None
    config = registry.load_theme_registry()
    for item in config.get("themes", []):
        if item.get("id") == AIRPLANE:
            item["enabled"] = False
    monkeypatch.setattr(registry, "load_theme_registry", lambda: config)
    _, audit = choose(saved, monkeypatch)
    assert AIRPLANE not in audit.get("candidates", [])


def test_only_a17_receives_new_side_focus_policy():
    configured = []
    for item in registry.registered_themes(include_disabled=True):
        if item.get("contentEligibility", {}).get("wideLayout") == "side-focus":
            configured.append(item.get("id"))
    assert configured == [AIRPLANE]


@pytest.mark.parametrize("field,value", [("wideLayout", "side-focus"), ("placement", "bottom")])
@pytest.mark.parametrize("pool,size", [("photos", "2x2"), ("texturePhotos", "2x2")])
def test_a17_new_rules_cannot_be_applied_to_square_photos(field, value, pool, size):
    config = registry.load_theme_registry()
    item = next(item for item in config.get("themes", [])
                if item.get("pool") == pool and item.get("sizes") == [size])
    item.get("contentEligibility", {})[field] = value
    with pytest.raises(ValueError):
        registry.validate_registry(config)
