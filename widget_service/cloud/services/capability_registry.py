# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

from config.config import get_settings
from models.capability import AssetCapability, DataCapability, EventCapability
from services.json_loader import load_json

_MODULE = "[Capability Registry]"
_RANGE_INDEX_FILE = "registry_ranges.json"


@dataclass(frozen=True)
class CapabilityRegistryRange:
    registry_version: str
    app_min: Version
    app_max: Version
    rom_min: Version
    rom_max: Version

    def matches(self, app_version: Version, rom_version: Version) -> bool:
        app_matches = self.app_min <= app_version < self.app_max
        rom_matches = self.rom_min <= rom_version < self.rom_max
        return app_matches and rom_matches

    def overlaps(self, other: "CapabilityRegistryRange") -> bool:
        app_overlaps = self.app_min < other.app_max and other.app_min < self.app_max
        rom_overlaps = self.rom_min < other.rom_max and other.rom_min < self.rom_max
        return app_overlaps and rom_overlaps


class CapabilityRegistry:
    """按 App/ROM 二维版本区间加载数据、事件和素材能力。"""

    def __init__(
        self,
        version: str | None = None,
        app_version: str | None = None,
        device_rom_version: str | None = None,
    ) -> None:
        self.settings = get_settings()
        requested_app = app_version or self.settings.default_prd_version
        requested_rom = device_rom_version or self.settings.default_device_rom_version
        self.normalized_app_version = self.normalize_app_version(requested_app)
        self.normalized_rom_version = self.normalize_rom_version(requested_rom)
        self.selection_type = "explicit" if version else "interval"
        self.version = version or self.from_app_rom_versions(requested_app, requested_rom)
        self.version_dir = self.settings.data_root / "capabilities" / self.version
        if not self.version_dir.exists():
            raise ValueError(f"Capability registry version not found: {self.version}")

    @classmethod
    def from_app_rom_versions(
        cls,
        app_version: str,
        rom_version: str,
        capabilities_root: Path | None = None,
    ) -> str:
        """根据规范化后的 App/ROM 版本选择唯一命中的能力目录。"""
        root = capabilities_root or get_settings().data_root / "capabilities"
        app = cls._parse_runtime_version(cls.normalize_app_version(app_version), "App")
        rom = cls._parse_runtime_version(cls.normalize_rom_version(rom_version), "ROM")
        matches = [item for item in cls._load_ranges(root) if item.matches(app, rom)]
        if len(matches) > 1:
            raise ValueError("Multiple capability registry ranges matched the same device")
        if not matches:
            normalized_app = cls.normalize_app_version(app_version)
            normalized_rom = cls.normalize_rom_version(rom_version)
            raise ValueError(
                "Capability registry range not found: "
                f"app={normalized_app}, rom={normalized_rom}"
            )
        return matches[0].registry_version

    @classmethod
    def requested_version_label(cls, app_version: str, rom_version: str) -> str:
        """生成未命中区间时用于响应和排障的版本标签。"""
        app = cls.normalize_app_version(app_version)
        rom = cls.normalize_rom_version(rom_version)
        return f"app-{app}_rom-{rom}"

    @classmethod
    @cache
    def _load_ranges(cls, capabilities_root: Path) -> list[CapabilityRegistryRange]:
        index_path = capabilities_root / _RANGE_INDEX_FILE
        if not index_path.is_file():
            raise ValueError(f"Capability registry range index not found: {index_path}")
        payload = load_json(index_path)
        if not isinstance(payload, dict):
            raise ValueError("Capability registry range index must be an object")
        raw_ranges = payload.get("ranges")
        if not isinstance(raw_ranges, list) or not raw_ranges:
            raise ValueError("Capability registry range index must contain non-empty ranges")
        ranges = [cls._parse_range(item, capabilities_root) for item in raw_ranges]
        cls._validate_no_overlaps(ranges)
        return ranges

    @classmethod
    def _parse_range(
        cls,
        payload: Any,
        capabilities_root: Path,
    ) -> CapabilityRegistryRange:
        if not isinstance(payload, dict):
            raise ValueError("Capability registry range entry must be an object")
        registry_version = payload.get("registryVersion")
        if not isinstance(registry_version, str) or not registry_version.strip():
            raise ValueError("Capability registry range entry requires registryVersion")
        registry_dir = capabilities_root / registry_version
        if not registry_dir.is_dir():
            raise ValueError(f"Capability registry version not found: {registry_version}")
        app_min, app_max = cls._parse_interval(payload.get("appVersion"), "appVersion")
        rom_min, rom_max = cls._parse_interval(payload.get("romVersion"), "romVersion")
        return CapabilityRegistryRange(
            registry_version=registry_version,
            app_min=app_min,
            app_max=app_max,
            rom_min=rom_min,
            rom_max=rom_max,
        )

    @classmethod
    def _parse_interval(cls, payload: Any, name: str) -> tuple[Version, Version]:
        if not isinstance(payload, dict):
            raise ValueError(f"{name} range must be an object")
        minimum = cls._parse_config_version(payload.get("minInclusive"), f"{name}.minInclusive")
        maximum = cls._parse_config_version(payload.get("maxExclusive"), f"{name}.maxExclusive")
        if minimum >= maximum:
            raise ValueError(f"{name} minInclusive must be less than maxExclusive")
        return minimum, maximum

    @staticmethod
    def _parse_config_version(value: Any, name: str) -> Version:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty version string")
        try:
            return Version(value)
        except InvalidVersion as error:
            raise ValueError(f"Invalid {name}: {value}") from error

    @staticmethod
    def _parse_runtime_version(value: str, name: str) -> Version:
        try:
            return Version(value)
        except InvalidVersion as error:
            raise ValueError(f"Invalid normalized {name} version: {value}") from error

    @staticmethod
    def _validate_no_overlaps(ranges: list[CapabilityRegistryRange]) -> None:
        for index, current in enumerate(ranges):
            for other_index in range(index + 1, len(ranges)):
                other = ranges[other_index]
                if current.overlaps(other):
                    versions = f"{current.registry_version}, {other.registry_version}"
                    raise ValueError(f"Overlapping capability registry ranges: {versions}")

    @staticmethod
    def normalize_app_version(value: str) -> str:
        """从 App 版本字符串中提取完整数字版本。"""
        match = re.search(r"\d+(?:\.\d+)*", value or "")
        return match.group(0) if match else "0"

    @staticmethod
    def normalize_rom_version(value: str) -> str:
        """从完整 romVersion 中提取主次版本，例如 6.0。"""
        match = re.search(r"\d+(?:\.\d+)+", value or "")
        if match:
            parts = match.group(0).split(".")
            return ".".join(parts[:2])
        number = re.search(r"\d+", value or "")
        return number.group(0) if number else "0"

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
