"""补回现存图标，旧能力快照与其它能力必须保持不变。"""

import json
from pathlib import Path

import pytest

from config.config import get_settings
from services.capability_registry import CapabilityRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRIES = ROOT / "cloud/data/capabilities"
VERSIONS = ("app-11.7.5.205_rom-6.0", "app-11.7.7.300_rom-7.0")
ASSET_ID = "asset.icon_weather_temperature1"
ASSET_PATH = "resources/base/media/icon_weather_temperature1.svg"


@pytest.mark.parametrize("version", VERSIONS)
def test_revision_only_adds_original_temperature_asset(version: str) -> None:
    original = REGISTRIES / version
    revision = REGISTRIES / f"{version}-assets-r1"
    for filename in ("data_capabilities.json", "event_capabilities.json"):
        old_text = (original / filename).read_text(encoding="utf-8")
        new_text = (revision / filename).read_text(encoding="utf-8")
        assert json.loads(old_text) == json.loads(new_text)
        assert [line.rstrip() for line in old_text.splitlines()] == new_text.splitlines()
    old_assets = json.loads((original / "asset_capabilities.json").read_text(encoding="utf-8"))
    new_assets = json.loads((revision / "asset_capabilities.json").read_text(encoding="utf-8"))
    retained = [item for item in new_assets if item.get("id") != ASSET_ID]
    assert retained == old_assets
    additions = [item for item in new_assets if item.get("id") == ASSET_ID]
    assert len(additions) == 1
    asset = additions[0]
    assert asset.get("src") == ASSET_PATH
    assert "保留原色" in asset.get("description", "")
    assert "禁止染色" in asset.get("description", "")
    assert (ROOT.parent / ASSET_PATH).is_file()


@pytest.mark.parametrize("version", VERSIONS)
def test_explicit_historical_registry_remains_available(version: str) -> None:
    legacy = CapabilityRegistry(version=version)
    assert legacy.get_asset_capability(ASSET_ID) is None
    current = CapabilityRegistry(version=f"{version}-assets-r1")
    restored = current.get_asset_capability(ASSET_ID)
    assert restored is not None
    assert restored.src == ASSET_PATH
    assert current.get_asset_capability("asset.nonexistent") is None


def test_default_fallback_and_intervals_use_asset_revision() -> None:
    assert get_settings().capability_registry_version == f"{VERSIONS[0]}-assets-r1"
    for app, version in (("11.7.5.205", VERSIONS[0]), ("11.7.7.330", VERSIONS[1])):
        current = CapabilityRegistry(app_version=app, device_rom_version="7.0")
        assert current.version == f"{version}-assets-r1"
        assert current.get_asset_capability(ASSET_ID) is not None
