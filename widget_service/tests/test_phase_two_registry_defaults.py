"""一期目录移除后，二期在线匹配、默认回退和历史素材恢复回归。"""

import json

import pytest

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
)
from config.config import Settings, get_settings
from models.artifact import ArtifactMeta, WidgetArtifact
from services.capability_registry import CapabilityRegistry
from services.compact_dsl_argument_repair import _select_capability_registry
from services.source_artifact_repository import (
    SourceArtifactLoadResult,
    SourceArtifactRepository,
)
from services.widget_generation_service import WidgetGenerationService

PHASE_TWO = "app-11.7.7.300_rom-7.0"
VERSION_CASES = [
    ("11.7.5.205", "7.0", False),
    ("11.7.7.225", "VYG-AL00 7.0.0.105", False),
    ("11.7.7.328", "7.1", False),
    ("11.7.7.329", "7.1", False),
    ("11.7.7.329.999", "7.1", False),
    ("11.7.7.330", "CLS-AL30 6.0.0.328", True),
    ("11.7.7.331", "ALN-AL00 7.1.0.100", True),
    ("11.9.9.999", "7.9", True),
    ("12.0.0.0", "7.0", False),
    ("11.7.7.330", "8.0", False),
    ("11.7.7.330", "5.9", False),
    (None, None, False),
]


@pytest.fixture
def settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "capability_registry_version", PHASE_TWO)
    return settings


def test_default_registry_is_phase_two_and_environment_override_is_preserved(monkeypatch):
    for key in (
        "WIDGET_SERVICE_CAPABILITY_REGISTRY_VERSION",
        "CAPABILITY_REGISTRY_VERSION",
        "capability_registry_version",
    ):
        monkeypatch.delenv(key, raising=False)
    assert Settings(_env_file=None).capability_registry_version == PHASE_TWO
    monkeypatch.setenv("WIDGET_SERVICE_CAPABILITY_REGISTRY_VERSION", "custom-registry")
    assert Settings(_env_file=None).capability_registry_version == "custom-registry"


def test_online_index_contains_only_unchanged_phase_two_range(settings):
    path = settings.data_root / "capabilities" / "registry_ranges.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload.get("ranges") == [
        {
            "registryVersion": PHASE_TWO,
            "appVersion": {"minInclusive": "11.7.7.330", "maxExclusive": "12.0.0.0"},
            "romVersion": {"minInclusive": "6.0", "maxExclusive": "8.0"},
        }
    ]


@pytest.mark.parametrize("fallback_enabled", [True, False])
@pytest.mark.parametrize(("app", "rom", "matched"), VERSION_CASES)
@pytest.mark.parametrize(
    "request_type",
    [CapabilityOverviewRequest, DataCapabilitySchemasRequest, GenerateWidgetCardRequest],
)
def test_public_request_registry_selection(
    monkeypatch, settings, request_type, app, rom, matched, fallback_enabled
):
    monkeypatch.setattr(settings, "enable_default_capability_registry_fallback", fallback_enabled)
    values = {
        "uid": "test-user",
        "device": {"romVersion": settings.default_device_rom_version},
        "userQuery": "时间卡片",
        "title": "时间",
        "description": "查看时间",
        "dataCapabilityIds": ["GetCurrentTime"],
    }
    if app is not None:
        values["prdVer"] = app
    if rom is not None:
        values["device"] = {"romVersion": rom}
    request = request_type(**values)
    service = WidgetGenerationService()
    if not matched and not fallback_enabled:
        with pytest.raises(ValueError, match="range not found"):
            service._capability_registry(request)
        return
    registry = service._capability_registry(request)
    assert registry.version == PHASE_TWO
    assert registry.selection_type == ("interval" if matched else "explicit")
    assert registry.get_data_capability("GetCurrentTime") is not None


@pytest.mark.parametrize("fallback_enabled", [True, False])
@pytest.mark.parametrize(("app", "rom", "matched"), VERSION_CASES)
def test_argument_repair_registry_matches_generation(
    monkeypatch, settings, app, rom, matched, fallback_enabled
):
    monkeypatch.setattr(settings, "enable_default_capability_registry_fallback", fallback_enabled)
    payload = {"deviceInfo": {"prdVer": app}}
    content = {"romVersion": rom}
    registry, warnings = _select_capability_registry(payload, content)
    if not matched and not fallback_enabled:
        assert registry is None
        assert warnings
        return
    assert registry is not None
    assert registry.version == PHASE_TWO
    assert registry.selection_type == ("interval" if matched else "explicit")
    assert bool(warnings) is not matched
    assert registry.get_data_capability("GetCurrentTime") is not None


def test_argument_repair_prefers_content_rom_over_device_info(monkeypatch, settings):
    monkeypatch.setattr(settings, "enable_default_capability_registry_fallback", False)
    payload = {"deviceInfo": {"prdVer": "11.7.7.330", "romVersion": "8.0"}}
    registry, warnings = _select_capability_registry(payload, {"romVersion": "7.0"})
    assert registry is not None
    assert registry.version == PHASE_TWO
    assert registry.selection_type == "interval"
    assert warnings == []


def test_phase_two_index_does_not_require_phase_one_directory(tmp_path):
    root = tmp_path / "capabilities"
    (root / PHASE_TWO).mkdir(parents=True)
    source = get_settings().data_root / "capabilities" / "registry_ranges.json"
    (root / "registry_ranges.json").write_bytes(source.read_bytes())
    assert CapabilityRegistry.from_app_rom_versions("11.7.7.330", "6.0", root) == PHASE_TWO


def test_only_phase_two_snapshot_is_shipped(settings):
    root = settings.data_root / "capabilities"
    snapshots = sorted(
        path.name for path in root.iterdir() if (path / "data_capabilities.json").is_file()
    )
    assert snapshots == [PHASE_TWO]
    # Git 不记录空目录；本地补丁工具可能留下空目录，但不能留下任何一期文件。
    retired = root / "app-11.7.5.205_rom-6.0"
    assert not any(path.is_file() for path in retired.rglob("*"))
    with pytest.raises((ValueError, FileNotFoundError)):
        CapabilityRegistry(version=retired.name).list_data_capabilities()


def test_template_provider_schema_paths_are_phase_two(settings):
    providers = (
        settings.data_root.parent / "services/template_generation/resources/source/providers"
    )
    schema_count = 0
    for provider_path in providers.glob("*/provider.json"):
        provider = json.loads(provider_path.read_text(encoding="utf-8"))
        for capability in provider.get("capabilities", []):
            schema = capability.get("dataSchema")
            if schema is None:
                continue
            assert schema.get("version") == PHASE_TWO
            relative_path = schema.get("path")
            assert relative_path == f"capabilities/{PHASE_TWO}/data_capabilities.json"
            assert (settings.data_root / relative_path).is_file()
            schema_count += 1
    assert schema_count >= 7


@pytest.mark.parametrize("version", ["app-11.7.5.205_rom-6.0", PHASE_TWO])
@pytest.mark.parametrize("restore_genui", [True, False])
@pytest.mark.parametrize("mapping_hit", [True, False])
def test_historical_asset_restoration_without_old_snapshot(version, restore_genui, mapping_hit):
    original_src = "resources/base/media/drop_1.svg"
    address = "https://assets.example.test/drop.svg"
    component = {"id": "image", "component": "Image", "src": address}
    genui = json.dumps({"updateComponents": {"surfaceId": "test", "components": [component]}})
    token = json.dumps(["image", "Image", {"src": address}])
    artifact = WidgetArtifact(
        genui=genui,
        cardSpec={},
        taskSpec={"assetCandidates": [{"id": "asset.drop_1", "src": address}]},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion=version,
            createdAt=0,
        ),
    )
    original = artifact.model_copy(deep=True)
    source = SourceArtifactLoadResult(
        artifact=artifact, design_token=token, artifact_digest="original-digest",
        url_hash="hash", read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    mapping = {original_src: address} if mapping_hit else {}
    restored = SourceArtifactRepository.restore_asset_paths(
        source, mapping, restore_genui=restore_genui,
    )
    assert source.artifact == original
    assert source.design_token == token
    assert restored.artifact_digest == source.artifact_digest
    assert restored.artifact.meta.capabilityRegistryVersion == version
    assert restored.artifact.taskSpec.get("assetCandidates") == [
        {"id": "asset.drop_1", "src": original_src}
    ]
    assert restored.design_token is not None
    assert original_src in restored.design_token
    assert address not in restored.design_token
    if restore_genui:
        assert original_src in restored.artifact.genui
        assert address not in restored.artifact.genui
    else:
        assert restored.artifact.genui == genui


def test_historical_unknown_version_is_not_silently_migrated():
    artifact = WidgetArtifact(
        genui="", cardSpec={}, taskSpec={},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion="unknown-registry",
            createdAt=0,
        ),
    )
    source = SourceArtifactLoadResult(
        artifact=artifact, design_token=None, artifact_digest="digest", url_hash="hash",
        read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    with pytest.raises(ValueError, match="version not found"):
        SourceArtifactRepository.restore_asset_paths(source, {}, restore_genui=False)
