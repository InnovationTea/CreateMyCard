from __future__ import annotations

import json
from pathlib import Path

import pytest
from debug_tools.paths import DEBUG_TOOLS_ROOT, RENDER_RESOURCE_ROOT, REPOSITORY_ROOT
from debug_tools.scripts import sync_assets
from debug_tools.static_site import register_renderer_asset_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_registered_images_are_served_from_the_native_project() -> None:
    app = FastAPI()
    register_renderer_asset_routes(app)
    assets = sync_assets.registered_assets(REPOSITORY_ROOT)
    assert assets
    expected_root = DEBUG_TOOLS_ROOT / "a2ui_render/entry/src/main/resources"
    assert RENDER_RESOURCE_ROOT == expected_root
    assert list(sync_assets.TARGETS.values()) == [expected_root.parent.relative_to(REPOSITORY_ROOT)]
    with TestClient(app) as client:
        for asset in assets:
            response = client.get(f"/{asset.relative.as_posix()}")
            assert response.status_code == 200, asset.relative
            assert response.content == asset.source.read_bytes(), asset.relative


@pytest.mark.parametrize(
    "url,relative",
    [
        (
            "/resources/base/media/emoji_clean.png",
            "a2ui_render/entry/src/main/resources/base/media/emoji_clean.png",
        ),
        (
            "/background_assets/ui_plum_blossom.png",
            "card_renderer/assets/background_assets/ui_plum_blossom.png",
        ),
        (
            "/fonts/harmonyos/HarmonyOS_Sans_Regular.ttf",
            "card_renderer/assets/fonts/harmonyos/HarmonyOS_Sans_Regular.ttf",
        ),
    ],
)
def test_browser_only_assets_still_load_without_render(url: str, relative: str) -> None:
    app = FastAPI()
    register_renderer_asset_routes(app)
    with TestClient(app) as client:
        response = client.get(url)
        assert response.status_code == 200
        assert response.content == (DEBUG_TOOLS_ROOT / relative).read_bytes()
        assert client.get("/resources/base/media/missing.svg").status_code == 404
        assert client.get("/resources/%2E%2E/private.txt").status_code == 400


def test_sync_updates_one_shared_copy_and_preserves_unregistered_assets(tmp_path: Path) -> None:
    source = tmp_path / "resources/base/media/sample.svg"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"<svg/>")
    manifest = tmp_path / sync_assets.CAPABILITIES_ROOT / "test/asset_capabilities.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps([{"src": "resources/base/media/sample.svg"}]), encoding="utf-8")
    theme_path = tmp_path / sync_assets.THEMES_PATH
    theme_path.write_text(json.dumps({"themes": []}), encoding="utf-8")
    assets = sync_assets.registered_assets(tmp_path)
    target = next(iter(sync_assets.TARGETS.values()))
    destination = tmp_path / target / assets[0].relative
    extra = destination.with_name("application-icon.svg")
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"keep")
    before = sync_assets.synchronize(tmp_path, assets, write=False)
    assert len(before) == 1
    assert before[0].missing == ["resources/base/media/sample.svg"]
    sync_assets.synchronize(tmp_path, assets, write=True)
    assert destination.read_bytes() == source.read_bytes()
    assert extra.read_bytes() == b"keep"
    destination.write_bytes(b"old")
    different = sync_assets.synchronize(tmp_path, assets, write=False)
    assert different[0].different == ["resources/base/media/sample.svg"]
    sync_assets.synchronize(tmp_path, assets, write=True)
    result = sync_assets.synchronize(tmp_path, assets, write=False)
    assert not result[0].missing
    assert not result[0].different
    assert not (tmp_path / "render").exists()


def test_theme_images_are_checked_synced_and_deduplicated(tmp_path: Path) -> None:
    source = tmp_path / "resources/base/media/sleep.jpg"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"theme-image")
    manifest = tmp_path / sync_assets.CAPABILITIES_ROOT / "test/asset_capabilities.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("[]", encoding="utf-8")
    theme_path = tmp_path / sync_assets.THEMES_PATH
    theme_path.write_text(
        json.dumps(
            {
                "themes": [
                    {"background": {"colors": ["#FFFFFFFF"]}},
                    {"background": {"src": "resources/base/media/sleep.jpg"}},
                    {"background": {"src": "resources/base/media/sleep.jpg"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    assets = sync_assets.registered_assets(tmp_path)
    assert len(assets) == 1
    before = sync_assets.synchronize(tmp_path, assets, write=False)
    assert before[0].missing == ["resources/base/media/sleep.jpg"]
    sync_assets.synchronize(tmp_path, assets, write=True)
    after = sync_assets.synchronize(tmp_path, assets, write=False)
    assert not after[0].missing
    assert not after[0].different
    source.unlink()
    with pytest.raises(ValueError, match="登记素材源文件不存在"):
        sync_assets.registered_assets(tmp_path)


@pytest.mark.parametrize(
    "src", ["resources/base/media/../secret.jpg", "https://example.test/a.jpg"]
)
def test_theme_images_reject_unsafe_paths(tmp_path: Path, src: str) -> None:
    manifest = tmp_path / sync_assets.CAPABILITIES_ROOT / "test/asset_capabilities.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("[]", encoding="utf-8")
    theme_path = tmp_path / sync_assets.THEMES_PATH
    theme_path.write_text(json.dumps({"themes": [{"background": {"src": src}}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="素材路径必须位于"):
        sync_assets.registered_assets(tmp_path)
