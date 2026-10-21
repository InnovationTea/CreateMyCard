"""Post-layout fusion must retain the native renderer's overflow marker."""

import copy

import pytest

from config.config import get_settings
from services import post_layout_theme as themes
from services.fusion_ball_expander import build_fusion_ball_content_id
from services.square_photo_expansion import expand_square
from services.theme_style_roles import role
from theme_photo_samples import expansion_photo

FOREGROUND_ID = build_fusion_ball_content_id("root")
TASK = {"size": "2x2", "appVersion": "99.0.0", "userQuery": "Sleep"}
FUSION_THEME_IDS = [theme.get("id") for theme in themes.registered_themes("standard")
                    if theme.get("kind") == "fusion"]


@pytest.fixture(autouse=True)
def enable_fusion(monkeypatch):
    config = get_settings().CONFIG
    original_get = config.get

    def configured(key, default=None):
        return "1.0.0" if key == "fusion_ball_min_prd_version" else original_get(key, default)

    monkeypatch.setattr(config, "get", configured)


def layout_source(root_type="Column"):
    records = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "card", "root": "root", "components": [
                {"id": "root", "component": root_type, "children": ["duration", "action"],
                 "styles": {"width": "matchParent", "height": "matchParent", "padding": 12,
                            "borderRadius": 20, "clip": True}},
                {"id": "duration", "component": "Text",
                 "content": "{{ ${/data/sleep/duration} }}",
                 "styles": {"fontSize": 18, "fontColor": role("primary")}},
                {"id": "action", "component": "Stack", "children": [],
                 "onClick": [{"call": "open", "args": {"target": "alarm"}}],
                 "styles": {"width": 40, "height": 40, "borderRadius": 20,
                            "backgroundColor": role("componentSecondary")}},
            ],
        }},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "card", "path": "/", "value": {"data": {"sleep": {"duration": "7h1m"}}},
        }},
    ]
    return themes.encode(records)


def fusion_theme(token="fusion-ball-schedule-blue"):
    return next(item for item in themes.presets(TASK) if item.get("id") == token)


def node_by_id(source, identity):
    return next(node for node in themes.components(themes.decode(source))
                if node.get("id") == identity)


@pytest.mark.parametrize("token", FUSION_THEME_IDS)
@pytest.mark.parametrize("root_type", ["Column", "Row", "Stack"])
def test_fusion_retains_renderer_marker_and_original_foreground(token, root_type):
    source = layout_source(root_type)
    theme = fusion_theme(token)
    result = themes.apply_theme(source, theme, TASK, {})
    root = node_by_id(result, "root")
    assert root.get("children") == ["fusionBallBackground", FOREGROUND_ID]
    assert root.get("styles", {}).get("backgroundColor") == "#00000000"
    foreground = node_by_id(result, FOREGROUND_ID)
    assert foreground.get("component") == root_type
    assert foreground.get("styles") == node_by_id(source, "root").get("styles")
    assert foreground.get("children") == ["duration", "action"]
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
    original_action = node_by_id(source, "action").get("onClick")
    assert original_action == node_by_id(result, "action").get("onClick")
    assert themes.decode(source)[-1] == themes.decode(result)[-1]
    backgrounds = []
    for node in themes.components(themes.decode(result)):
        if node.get("id") in themes.FUSION_IDS:
            backgrounds.append(node)
    assert backgrounds == themes.fusion_background(theme, TASK)
    assert "__post_theme_foreground" not in result


def test_signature_accepts_legacy_foreground_marker_without_changing_content():
    source = layout_source()
    result = themes.decode(themes.apply_theme(source, fusion_theme(), TASK, {}))
    for node in themes.components(result):
        if node.get("id") == "root":
            node["children"] = ["fusionBallBackground", "__post_theme_foreground"]
        elif node.get("id") == FOREGROUND_ID:
            node["id"] = "__post_theme_foreground"
    assert themes.foreground_signature(source) == themes.foreground_signature(themes.encode(result))


@pytest.mark.parametrize("mutation", ["geometry", "text", "action", "binding"])
def test_marker_does_not_hide_foreground_mutations(mutation):
    source = layout_source()
    result = themes.decode(themes.apply_theme(source, fusion_theme(), TASK, {}))
    nodes = themes.components(result)
    foreground = next(node for node in nodes if node.get("id") == FOREGROUND_ID)
    duration = next(node for node in nodes if node.get("id") == "duration")
    action = next(node for node in nodes if node.get("id") == "action")
    if mutation == "geometry":
        foreground.setdefault("styles", {})["padding"] = 8
    elif mutation == "text":
        duration["content"] = "changed"
    elif mutation == "action":
        action["onClick"] = []
    else:
        duration["content"] = "{{ ${/data/sleep/other} }}"
    assert themes.foreground_signature(source) != themes.foreground_signature(themes.encode(result))


def test_reserved_foreground_id_is_rejected():
    records = themes.decode(layout_source())
    themes.components(records).append({"id": FOREGROUND_ID, "component": "Column", "children": []})
    with pytest.raises(ValueError, match="Theme must only be applied once"):
        themes.apply_theme(themes.encode(records), fusion_theme(), TASK, {})


def test_fusion_cannot_be_applied_twice():
    result = themes.apply_theme(layout_source(), fusion_theme(), TASK, {})
    with pytest.raises(ValueError, match="Theme must only be applied once"):
        themes.apply_theme(result, fusion_theme(), TASK, {})


@pytest.mark.parametrize("kind", ["gradient", "solid"])
def test_normal_themes_do_not_add_renderer_marker(kind):
    source = layout_source()
    theme = next(item for item in themes.presets(TASK) if item.get("kind") == kind)
    result = themes.apply_theme(source, theme, TASK, {})
    assert FOREGROUND_ID not in result
    assert themes.foreground_signature(source) == themes.foreground_signature(result)


@pytest.mark.parametrize("pool", ["photos", "subjectlessWidePhotos", "squareExpansions"])
def test_photo_wrappers_remain_unchanged(pool):
    if pool == "photos":
        entries = themes.registered_themes(pool, include_disabled=True)
        assert entries
        theme = copy.deepcopy(entries[0])
    else:
        assert not themes.registered_themes(pool, include_disabled=True)
        theme = expansion_photo()
        if pool == "subjectlessWidePhotos":
            theme.update(pool=pool, composition="native", subjectless=True)
    theme["kind"] = "photo"
    source = layout_source()
    if pool == "squareExpansions":
        result = expand_square(source, theme, TASK)
    else:
        result = themes.apply_theme(source, theme, {**TASK, "size": theme.get("size")}, {})
    assert FOREGROUND_ID not in result
    assert node_by_id(result, "__post_theme_foreground").get("component") == "Column"
    assert themes.foreground_signature(source) == themes.foreground_signature(result)
