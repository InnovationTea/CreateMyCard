"""Background candidates and surface colors follow the theme registry, not URL uploads."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from photo_samples.weather import fixture, task
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator
from test_autumn_calendar_photos import ACTION, calendar_sample, expanded
from test_photo_asset_delivery import PHOTO_ID, artifact
from test_photo_background_fallback import node_by_id, source


@pytest.mark.parametrize("state", ["removed", "disabled", "unregistered"])
def test_uploaded_background_cannot_register_or_enable_a_theme(monkeypatch, state):
    config = registry.load_theme_registry()
    target = next(item for item in config.get("themes", []) if item.get("id") == PHOTO_ID)
    identity = PHOTO_ID
    src = target.get("background", {}).get("src")
    if state == "removed":
        config.get("themes", []).remove(target)
    elif state == "disabled":
        target["enabled"] = False
    else:
        identity = "photo-upload-only"
        src = "resources/base/media/bg_upload_only.jpg"
    address = "https://example.test/upload-only.jpg"
    monkeypatch.setattr(registry, "load_theme_registry", lambda: copy.deepcopy(config))
    monkeypatch.setattr(get_settings(), "asset_src_url_mapping", {src: address})
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    sample = fixture()
    layout = themes.encode([
        {"updateComponents": {"components": sample.nodes}},
        {"updateDataModel": {"path": "/", "value": {
            "data": {"weather": {"current": {"condition": "cloudy"}}},
        }}},
    ])
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": identity})))
    result, audit = asyncio.run(themes.select_theme(
        layout, task(), client, final_layout=sample.layout,
    ))
    prompt = client.generate.call_args.args[0]
    payload = json.loads(prompt[1].get("content"))
    assert identity not in audit.get("candidates", [])
    assert identity not in payload.get("eligiblePhotos", [])
    assert all(item.get("themeId") != identity for item in payload.get("candidates", []))
    assert audit.get("themeId") != identity
    assert "unregistered choice" in audit.get("selectorError", "")
    assert address not in json.dumps(prompt)
    assert address not in result
    assert src not in result


def test_photo_delivery_uses_registry_url_not_external_same_key_mapping(monkeypatch):
    photo = next(item for item in registry.registered_themes("photos")
                 if item.get("id") == PHOTO_ID)
    monkeypatch.setattr(get_settings(), "asset_src_url_mapping", {
        photo.get("src"): "https://example.test/external-override.jpg",
    })
    original = artifact()
    themed = themes.apply_theme(original.genui, photo, original.taskSpec, {})
    audit = {"themeId": PHOTO_ID, "theme": photo}
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=(themed, audit)))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, None, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
    ))
    assert not audit.get("finalValidationErrors"), audit
    assert node_by_id(delivered.genui, themes.PREFIX + "base").get("src") == photo.get("remoteUrl")
    assert "external-override" not in delivered.genui


@pytest.mark.parametrize("photo", [
    item for item in registry.registered_themes(include_disabled=True)
    if item.get("kind") == "photo"
], ids=lambda item: item.get("id"))
def test_registered_photo_panel_tracks_its_text_palette(photo):
    content = photo.get("content", {})
    rgb = content.get("roles", {}).get("primary", "")[3:]
    assert rgb in {"000000", "FFFFFF"}
    size = photo.get("size")
    result = themes.apply_theme(source(), photo, {"size": size}, {})
    panel = node_by_id(result, "panel").get("styles", {})
    assert panel.get("backgroundColor") == "#33" + rgb
    assert panel.get("backdropBlur") == {"radius": 20}
    assert themes.foreground_signature(result) == themes.foreground_signature(source())


@pytest.mark.parametrize("rgb,photo_id", [
    ("000000", "photo-ux-meeting-room-wide"),
    ("FFFFFF", "photo-ux-wave-wide"),
])
def test_wide_pill_info_and_card_button_use_consistent_surface_palette(rgb, photo_id):
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["main", "upper", "lower"]],
        ["main", "Region", {"variant": "title-content-action"}, ["header", "body", "action"]],
        ["header", "SingleLineTitle", {"title": "Schedule"}],
        ["body", "EmphasisText", {"mainText": "14:00", "secondaryText": "Room 1"}],
        ["action", "PillButton", {"label": "Open", "onClick": ACTION}],
        ["upper", "InfoBlock", {"variant": "slot", "primaryText": "Meeting",
                                 "secondaryText": "Room 1"}],
        ["lower", "CardButton", {"label": "Details", "onClick": ACTION}],
    ]
    sample = expanded(rows, {"size": "2x4", "appVersion": "99.0.0"})
    photo = next(item for item in registry.registered_themes("photos")
                 if item.get("id") == photo_id)
    result = themes.apply_theme(sample.source, photo, sample.task, {})
    for identity in ("upper", "lower", "action"):
        styles = node_by_id(result, identity).get("styles", {})
        assert styles.get("backgroundColor") == "#33" + rgb
        assert styles.get("backdropBlur") == {"radius": 20}
    for node in themes.components(themes.decode(result)):
        if node.get("component") == "Text":
            assert node.get("styles", {}).get("fontColor") in {
                "#FF" + rgb, "#CC" + rgb, "#99" + rgb,
            }
    assert themes.foreground_signature(result) == themes.foreground_signature(sample.source)


def test_square_black_text_button_keeps_existing_material():
    sample = calendar_sample("S-title-content-action", "PillButton")
    photo = next(item for item in registry.registered_themes("photos")
                 if item.get("id") == "photo-ux-meeting-room-square")
    result = themes.apply_theme(sample.source, photo, sample.task, {})
    styles = node_by_id(result, "action").get("styles", {})
    assert styles.get("backgroundColor") == "#33000000"
    assert styles.get("backdropBlur") == {"radius": 20}
    assert themes.foreground_signature(result) == themes.foreground_signature(sample.source)
