from pathlib import Path

from widget_service.core.config import get_settings
from widget_service.models.capability import AssetCapability, DataCapability, EventCapability
from widget_service.services.json_loader import load_json


class CapabilityRegistry:
    def __init__(self, version: str | None = None) -> None:
        self.settings = get_settings()
        self.version = version or self.settings.capability_registry_version
        self.version_dir = self.settings.data_root / "capabilities" / self.version
        if not self.version_dir.exists():
            raise ValueError(f"Capability registry version not found: {self.version}")

    def _path(self, name: str) -> Path:
        return self.version_dir / name

    def list_data_capabilities(self) -> list[DataCapability]:
        return [DataCapability(**item) for item in load_json(self._path("data_capabilities.json"))]

    def list_event_capabilities(self) -> list[EventCapability]:
        return [
            EventCapability(**item) for item in load_json(self._path("event_capabilities.json"))
        ]

    def list_asset_capabilities(self) -> list[AssetCapability]:
        return [
            AssetCapability(**item) for item in load_json(self._path("asset_capabilities.json"))
        ]

    def get_data_capability(self, capability_id: str) -> DataCapability | None:
        return next(
            (item for item in self.list_data_capabilities() if item.id == capability_id), None
        )

    def get_event_capability(self, capability_id: str) -> EventCapability | None:
        return next(
            (item for item in self.list_event_capabilities() if item.id == capability_id), None
        )

    def get_asset_capability(self, asset_id: str) -> AssetCapability | None:
        return next((item for item in self.list_asset_capabilities() if item.id == asset_id), None)
