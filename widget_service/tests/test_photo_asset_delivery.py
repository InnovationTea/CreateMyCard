"""图片交付复用素材映射，模型不接收URL，历史编辑保留可恢复的原路径。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from models.artifact import ArtifactMeta, WidgetArtifact
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.protocol_registry import A2UIProtocolRegistry
from services.source_artifact_repository import SourceArtifactLoadResult, SourceArtifactRepository
from services.theme_layout_summary import theme_description
from services.validator import ArtifactValidator
from test_photo_background_fallback import node_by_id, source
from test_weather_photo_eligibility import fixture, task

PHOTO_ID = "photo-ux-clouds-weather-square"
ADDRESS = "https://hagres-drcn.dbankcdn.com/assets/theme-test.jpg?version=1"
ICON = "resources/base/media/drop_1.svg"


def photo_config(address):
    config = registry.load_theme_registry()
    photo = next(item for item in config.get("themes", []) if item.get("id") == PHOTO_ID)
    photo.get("background", {})["remoteUrl"] = address
    return config


def configure(monkeypatch, address):
    config = photo_config(address)
    registry.validate_registry(config)
    monkeypatch.setattr(registry, "load_theme_registry", lambda: copy.deepcopy(config))
    return next(item for item in registry.registered_themes("photos")
                if item.get("id") == PHOTO_ID)


def artifact():
    return WidgetArtifact(
        genui=source(),
        cardSpec={"title": "天气", "description": "图片交付", "suggestSize": "2x2"},
        taskSpec={"size": "2x2", "userQuery": "天气", "appVersion": "11.7.7.331"},
        effectiveCapabilities={"asset": [], "data": [], "event": []},
        meta=ArtifactMeta(protocolProfileId="a2ui-form-rom6.0-v1",
                          capabilityRegistryVersion="app-11.7.7.300_rom-7.0", createdAt=0),
    )


@pytest.mark.parametrize(("pool", "count"), [("photos", 21), ("texturePhotos", 18)])
def test_current_photos_have_obs_addresses(pool, count):
    photos = registry.registered_themes(pool, include_disabled=True)
    assert len(photos) == count
    addresses = set()
    for photo in photos:
        address = photo.get("remoteUrl")
        assert isinstance(address, str)
        assert address.startswith("https://lfcontentcenterdev.hwcloudtest.cn/")
        assert address.endswith(".jpg")
        addresses.add(address)
    assert len(addresses) == len(photos)


@pytest.mark.parametrize(("photo_id", "size"), [
    (item.get("id"), item.get("size")) for item in registry.registered_themes()
    if item.get("kind") == "photo"
])
def test_registered_photo_sources_pass_existing_final_asset_validation(monkeypatch, photo_id, size):
    photo = next(item for item in registry.registered_themes()
                 if item.get("id") == photo_id)
    original = artifact()
    original.taskSpec["size"] = size
    original.cardSpec["suggestSize"] = size
    result = themes.apply_theme(original.genui, photo, original.taskSpec, {})
    audit = {"themeId": photo.get("id"), "theme": photo}
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=(result, audit)))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, None, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
    ))
    assert not audit.get("finalValidationErrors"), audit
    expected = photo.get("remoteUrl") or photo.get("src")
    assert isinstance(expected, str)
    assert node_by_id(delivered.genui, themes.PREFIX + "image").get("src") == expected
    assert node_by_id(delivered.genui, themes.PREFIX + "base").get("src") == expected
    assert node_by_id(delivered.genui, "root").get("styles", {}).get("backgroundColor")
    assert delivered.taskSpec.get("assetCandidates") == [
        {"id": photo_id, "src": expected, "description": "主题背景"},
    ]


@pytest.mark.parametrize("address", ["", ADDRESS])
def test_registry_accepts_empty_or_https_delivery_address(address):
    registry.validate_registry(photo_config(address))


@pytest.mark.parametrize("address", [
    None, 1, " ", "http://example.test/photo.jpg", "//example.test/photo.jpg",
    "file:///photo.jpg", "data:image/png;base64,AA", "https:///photo.jpg",
    "https://example.test", "https://user:secret@example.test/photo.jpg",
    "https://example.test/photo.jpg#part", "https://example.test/p hoto.jpg",
    "https://example.test/pho\x00to.jpg",
])
def test_registry_rejects_invalid_delivery_address(address):
    with pytest.raises(ValueError):
        registry.validate_registry(photo_config(address))


@pytest.mark.parametrize("address", ["", ADDRESS])
@pytest.mark.parametrize("rgb", ["000000", "FFFFFF"])
def test_final_delivery_maps_only_photo_and_preserves_fallback(monkeypatch, address, rgb):
    photo = configure(monkeypatch, address)
    original = artifact()
    original_copy = original.model_copy(deep=True)
    result = themes.apply_theme(original.genui, photo, original.taskSpec,
                                {"text": {"color": "#FF" + rgb}})
    audit = {"themeId": PHOTO_ID, "theme": photo}
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=(result, audit)))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, None, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
    ))
    assert not audit.get("finalValidationErrors"), audit
    assert audit.get("themeId") == PHOTO_ID
    expected = address or photo.get("src")
    assert node_by_id(delivered.genui, themes.PREFIX + "image").get("src") == expected
    assert node_by_id(delivered.genui, themes.PREFIX + "base").get("src") == expected
    assert delivered.taskSpec.get("assetCandidates") == [
        {"id": PHOTO_ID, "src": expected, "description": "主题背景"},
    ]
    before = themes.decode(result)
    after = themes.decode(delivered.genui)
    for node in themes.components(after):
        if node.get("component") == "Image" and node.get("src") == address:
            node["src"] = photo.get("src")
    assert before == after
    styles = node_by_id(delivered.genui, "root").get("styles", {})
    assert styles.get("backgroundColor") == "#FF8FADCC"
    assert "linearGradient" not in styles
    assert "fusionBall" not in delivered.genui
    assert original == original_copy


def test_unapproved_remote_host_uses_existing_theme_failure_fallback(monkeypatch):
    photo = configure(monkeypatch, "https://unapproved.example.test/photo.jpg")
    original = artifact()
    result = themes.apply_theme(original.genui, photo, original.taskSpec, {})
    audit = {"themeId": PHOTO_ID, "theme": photo}
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=(result, audit)))
    delivered = asyncio.run(themes.theme_artifact(
        original, original.taskSpec, None, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
    ))
    assert any("ASSET_REMOTE_URL_FORBIDDEN" in error
               for error in audit.get("finalValidationErrors", []))
    assert audit.get("themeId") == "gradient-blue"
    assert "unapproved.example.test" not in delivered.genui
    assert delivered.taskSpec == original.taskSpec


@pytest.mark.parametrize("enabled", [False, True])
def test_theme_prompt_never_receives_remote_url(monkeypatch, enabled):
    photo = configure(monkeypatch, ADDRESS)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", enabled)
    sample = fixture()
    client = SimpleNamespace(generate=AsyncMock(return_value=json.dumps({"themeId": PHOTO_ID})))
    layout = themes.encode([
        {"updateComponents": {"components": sample.nodes}},
        {"updateDataModel": {"path": "/", "value": {
            "data": {"weather": {"current": {"condition": "多云"}}},
        }}},
    ])
    result, audit = asyncio.run(themes.select_theme(
        layout, task(), client, final_layout=sample.layout,
    ))
    assert (audit.get("themeId") in {PHOTO_ID, "photo-ux-starfield-weather-square"}) is enabled
    assert ADDRESS not in json.dumps(theme_description(photo))
    assert ADDRESS not in json.dumps(client.generate.call_args.args)
    assert ADDRESS not in result


@pytest.mark.parametrize("restore_genui", [False, True])
@pytest.mark.parametrize("disabled", [False, True])
@pytest.mark.parametrize("current_address", ["", ADDRESS + "changed"])
def test_historical_photo_restores_after_url_rotation_or_disable(
    monkeypatch, restore_genui, disabled, current_address,
):
    config = photo_config(current_address)
    photo = next(item for item in config.get("themes", []) if item.get("id") == PHOTO_ID)
    photo["enabled"] = not disabled
    canonical = photo.get("background", {}).get("src")
    monkeypatch.setattr(registry, "load_theme_registry", lambda: copy.deepcopy(config))
    original = artifact()
    original.genui = themes.encode([{"updateComponents": {"components": [
        {"id": "background", "component": "Image", "src": ADDRESS},
        {"id": "icon", "component": "Image", "src": ICON},
        {"id": "text", "component": "Text", "content": ADDRESS},
    ]}}])
    original.taskSpec["assetCandidates"] = [{"id": PHOTO_ID, "src": ADDRESS}]
    token = json.dumps(["background", "Image", {"src": ADDRESS}])
    saved = original.model_copy(deep=True)
    loaded = SourceArtifactLoadResult(
        artifact=original, design_token=token, artifact_digest="unchanged-digest", url_hash="hash",
        read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    restored = SourceArtifactRepository.restore_asset_paths(loaded, {}, restore_genui=restore_genui)
    assert restored.artifact.taskSpec.get("assetCandidates") == [{"id": PHOTO_ID, "src": canonical}]
    assert restored.design_token is not None and canonical in restored.design_token
    expected = canonical if restore_genui else ADDRESS
    assert node_by_id(restored.artifact.genui, "background").get("src") == expected
    assert node_by_id(restored.artifact.genui, "icon").get("src") == ICON
    assert node_by_id(restored.artifact.genui, "text").get("content") == ADDRESS
    assert original == saved
    assert loaded.design_token == token
    assert restored.artifact_digest == loaded.artifact_digest


@pytest.mark.parametrize("identity", [None, [], {}, "asset.drop_1"])
def test_non_theme_candidates_do_not_load_theme_registry(monkeypatch, identity):
    def forbidden(*_args, **_kwargs):
        pytest.fail("普通素材恢复不应依赖主题配置")

    monkeypatch.setattr("services.source_artifact_repository.registered_themes", forbidden)
    original = artifact()
    original.taskSpec["assetCandidates"] = [{"id": identity, "src": ICON}]
    loaded = SourceArtifactLoadResult(
        artifact=original, design_token=None, artifact_digest="digest", url_hash="hash",
        read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    restored = SourceArtifactRepository.restore_asset_paths(loaded, {}, restore_genui=False)
    assert restored.artifact.taskSpec == original.taskSpec
