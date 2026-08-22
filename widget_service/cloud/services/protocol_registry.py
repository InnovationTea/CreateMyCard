# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

from app.logger import logger
from config.config import get_settings
from services.capability_registry import CapabilityRegistry
from services.json_loader import load_json

_MODULE = "[Protocol Registry]"

A2UI_FORM_PROTOCOL_PROFILE_ID = "a2ui-form-rom6.0-v1"
DESIGN_COMPACT_PROFILE_ID = "design-compact-dsl"
TERSE_DSL_NESTED2_PROFILE_ID = "terse-dsl-nested-2"
_RANGE_INDEX_FILE = "registry_ranges.json"
_DESIGN_PROMPT_FILE = "PROMPT.md"
_REFERENCE_TEMPLATE_PROMPT_2X2_FILE = "PROMPT22.md"
_DESIGN_PROMPT_2X4_FILE = "PROMPT24.md"
_DESIGN_PROTOCOL_FILE = "protocol.json"


@dataclass(frozen=True)
class ProtocolProfileSelection:
    """App/ROM 区间命中的输出协议和 Design Compact 提示词版本。"""

    protocol_profile_id: str
    design_profile_id: str
    normalized_app_version: str
    normalized_rom_version: str


def _design_prompt_file(
    size: str | None,
    *,
    use_reference_template_compact_route: bool,
) -> str:
    if not use_reference_template_compact_route:
        return _DESIGN_PROMPT_FILE
    if size in {"2x4", "4x2"}:
        return _DESIGN_PROMPT_2X4_FILE
    return _REFERENCE_TEMPLATE_PROMPT_2X2_FILE


@dataclass(frozen=True)
class ProtocolRegistryRange:
    protocol_profile_id: str
    design_profile_id: str
    app_min: Version
    app_max: Version
    rom_min: Version
    rom_max: Version

    def matches(self, app_version: Version, rom_version: Version) -> bool:
        app_matches = self.app_min <= app_version < self.app_max
        rom_matches = self.rom_min <= rom_version < self.rom_max
        return app_matches and rom_matches

    def overlaps(self, other: "ProtocolRegistryRange") -> bool:
        app_overlaps = self.app_min < other.app_max and other.app_min < self.app_max
        rom_overlaps = self.rom_min < other.rom_max and other.rom_min < self.rom_max
        return app_overlaps and rom_overlaps


class A2UIProtocolRegistry:
    def __init__(self, profile_id: str | None = None) -> None:
        """初始化 A2UI 协议注册表。

        入参：
        - profile_id：协议 profile 文件夹名；不传时使用默认配置。
        出参：无。
        """
        self.settings = get_settings()
        self.profile_id = profile_id or self.settings.protocol_profile_id

    def get_profile(self) -> dict:
        """读取 A2UI 协议 profile。

        入参：无。
        出参：协议 profile 字典，包含协议版本、catalogId、尺寸、白名单和原始 md 文档。
        """
        profile_dir = self.settings.data_root / "protocol_profiles" / self.profile_id
        if not profile_dir.exists():
            raise ValueError(f"Protocol profile not found: {self.profile_id}")
        logger.info(f"{_MODULE} protocol_profile_loading profile_id={self.profile_id}")
        protocol_md = self._read_markdown(profile_dir, "protocol.md")
        component_catalog_md = self._read_markdown(profile_dir, "component-catalog.md")
        data_binding_md = self._read_markdown(profile_dir, "data-binding.md")
        documents = {
            "protocol.md": protocol_md,
            "component-catalog.md": component_catalog_md,
            "data-binding.md": data_binding_md,
        }
        profile = {
            "id": self.profile_id,
            "version": self._extract_quoted_value(protocol_md, "version", "v0.9"),
            "format": self._extract_quoted_value(protocol_md, "format", "a2ui-form"),
            "catalogId": self._extract_quoted_value(
                protocol_md,
                "catalogId",
                "ohos.a2ui.extended.catalog.form",
            ),
            "minRomVersion": "6.0",
            "sizes": {
                "2x2": {"width": 140, "height": 140},
                "2x4": {"width": 300, "height": 140},
            },
            "componentWhitelist": self._extract_component_whitelist(component_catalog_md),
            "styleWhitelist": [
                "width",
                "height",
                "padding",
                "borderRadius",
                "clip",
                "background",
                "backgroundColor",
                "fontSize",
                "fontWeight",
                "objectFit",
            ],
            "fontSizeSteps": [10, 12, 14, 16, 18, 20, 32, 40],
            "spacingSteps": [2, 4, 6, 8, 10, 12, 14, 16],
            "documents": documents,
        }
        logger.info(
            f"{_MODULE} protocol_profile_loaded profile_id={self.profile_id} "
            f"version={profile['version']} "
            f"component_count={len(profile['componentWhitelist'])}"
        )
        return profile

    @classmethod
    def from_app_rom_versions(
        cls,
        app_version: str,
        rom_version: str,
        profiles_root: Path | None = None,
    ) -> ProtocolProfileSelection:
        """根据规范化 App/ROM 版本选择第四接口使用的协议版本。"""
        root = profiles_root or get_settings().data_root / "protocol_profiles"
        normalized_app = CapabilityRegistry.normalize_app_version(app_version)
        normalized_rom = CapabilityRegistry.normalize_rom_version(rom_version)
        app = cls._parse_runtime_version(normalized_app, "App")
        rom = cls._parse_runtime_version(normalized_rom, "ROM")
        matches = [item for item in cls._load_ranges(root) if item.matches(app, rom)]
        if len(matches) > 1:
            raise ValueError("Multiple protocol profile ranges matched the same device")
        if not matches:
            raise ValueError(
                "Protocol profile range not found: "
                f"app={normalized_app}, rom={normalized_rom}"
            )
        matched = matches[0]
        return ProtocolProfileSelection(
            protocol_profile_id=matched.protocol_profile_id,
            design_profile_id=matched.design_profile_id,
            normalized_app_version=normalized_app,
            normalized_rom_version=normalized_rom,
        )

    @classmethod
    def default_selection(
        cls,
        app_version: str,
        rom_version: str,
    ) -> ProtocolProfileSelection:
        """构造配置指定的默认协议回退结果。"""
        settings = get_settings()
        return ProtocolProfileSelection(
            protocol_profile_id=settings.protocol_profile_id,
            design_profile_id=settings.design_compact_profile_id,
            normalized_app_version=CapabilityRegistry.normalize_app_version(app_version),
            normalized_rom_version=CapabilityRegistry.normalize_rom_version(rom_version),
        )

    @classmethod
    def read_design_prompt(
        cls,
        design_profile_id: str,
        profiles_root: Path | None = None,
        size: str | None = None,
        use_reference_template_compact_route: bool = False,
    ) -> str:
        """读取版本选择结果对应的 Design Compact 完整系统提示词。"""
        root = profiles_root or get_settings().data_root / "protocol_profiles"
        prompt_path = root / design_profile_id / _design_prompt_file(
            size,
            use_reference_template_compact_route=use_reference_template_compact_route,
        )
        if not prompt_path.is_file():
            raise ValueError(f"Design Compact prompt not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    @classmethod
    def read_design_protocol_profile(
        cls,
        design_profile_id: str,
        profiles_root: Path | None = None,
    ) -> dict[str, Any]:
        """读取 Design Compact 转换器专用的目标 A2UI 协议参数。"""
        root = profiles_root or get_settings().data_root / "protocol_profiles"
        protocol_path = root / design_profile_id / _DESIGN_PROTOCOL_FILE
        if not protocol_path.is_file():
            raise ValueError(f"Design Compact protocol file not found: {protocol_path}")
        payload = load_json(protocol_path)
        if not isinstance(payload, dict):
            raise ValueError("Design Compact protocol file must contain an object")
        cls._validate_design_protocol_profile(payload, protocol_path)
        return payload

    @classmethod
    @cache
    def _load_ranges(cls, profiles_root: Path) -> list[ProtocolRegistryRange]:
        index_path = profiles_root / _RANGE_INDEX_FILE
        if not index_path.is_file():
            raise ValueError(f"Protocol profile range index not found: {index_path}")
        payload = load_json(index_path)
        if not isinstance(payload, dict):
            raise ValueError("Protocol profile range index must be an object")
        raw_ranges = payload.get("ranges")
        if not isinstance(raw_ranges, list) or not raw_ranges:
            raise ValueError("Protocol profile range index must contain non-empty ranges")
        ranges = [cls._parse_range(item, profiles_root) for item in raw_ranges]
        cls._validate_no_overlaps(ranges)
        return ranges

    @classmethod
    def _parse_range(
        cls,
        payload: Any,
        profiles_root: Path,
    ) -> ProtocolRegistryRange:
        if not isinstance(payload, dict):
            raise ValueError("Protocol profile range entry must be an object")
        protocol_profile_id = cls._required_profile_id(payload, "protocolProfileId")
        design_profile_id = cls._required_profile_id(payload, "designProfileId")
        cls._validate_profile_files(
            profiles_root,
            protocol_profile_id,
            design_profile_id,
        )
        app_min, app_max = cls._parse_interval(payload.get("appVersion"), "appVersion")
        rom_min, rom_max = cls._parse_interval(payload.get("romVersion"), "romVersion")
        return ProtocolRegistryRange(
            protocol_profile_id=protocol_profile_id,
            design_profile_id=design_profile_id,
            app_min=app_min,
            app_max=app_max,
            rom_min=rom_min,
            rom_max=rom_max,
        )

    @staticmethod
    def _required_profile_id(payload: dict, name: str) -> str:
        value = payload.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Protocol profile range entry requires {name}")
        return value

    @classmethod
    def _validate_profile_files(
        cls,
        profiles_root: Path,
        protocol_profile_id: str,
        design_profile_id: str,
    ) -> None:
        protocol_dir = profiles_root / protocol_profile_id
        if not protocol_dir.is_dir():
            raise ValueError(f"Protocol profile not found: {protocol_profile_id}")
        required_files = ("protocol.md", "component-catalog.md", "data-binding.md")
        for filename in required_files:
            profile_file = protocol_dir / filename
            if not profile_file.is_file():
                raise ValueError(f"Protocol profile file not found: {profile_file}")
        design_prompt = profiles_root / design_profile_id / _DESIGN_PROMPT_FILE
        if not design_prompt.is_file():
            raise ValueError(f"Design Compact prompt not found: {design_prompt}")
        cls.read_design_protocol_profile(design_profile_id, profiles_root)

    @staticmethod
    def _validate_design_protocol_profile(payload: dict[str, Any], path: Path) -> None:
        version = payload.get("version")
        catalog_id = payload.get("catalogId")
        sizes = payload.get("sizes")
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"Design Compact protocol version is invalid: {path}")
        if not isinstance(catalog_id, str) or not catalog_id.strip():
            raise ValueError(f"Design Compact protocol catalogId is invalid: {path}")
        if not isinstance(sizes, dict):
            raise ValueError(f"Design Compact protocol sizes are invalid: {path}")
        for size in ("2x2", "2x4"):
            dimensions = sizes.get(size)
            if not isinstance(dimensions, dict):
                raise ValueError(f"Design Compact protocol size {size} is missing: {path}")
            width = dimensions.get("width")
            height = dimensions.get("height")
            valid_dimensions = type(width) is int and type(height) is int
            if not valid_dimensions or width <= 0 or height <= 0:
                raise ValueError(f"Design Compact protocol size {size} is invalid: {path}")

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
    def _validate_no_overlaps(ranges: list[ProtocolRegistryRange]) -> None:
        for index, current in enumerate(ranges):
            for other_index in range(index + 1, len(ranges)):
                other = ranges[other_index]
                if current.overlaps(other):
                    profiles = f"{current.protocol_profile_id}, {other.protocol_profile_id}"
                    raise ValueError(f"Overlapping protocol profile ranges: {profiles}")

    def _read_markdown(self, profile_dir, filename: str) -> str:
        """读取协议版本目录下的 md 原文。

        入参：
        - profile_dir：协议版本目录。
        - filename：md 文件名。
        出参：md 原文字符串。
        """
        path = profile_dir / filename
        if not path.exists():
            raise ValueError(f"Protocol markdown not found: {path}")
        return path.read_text(encoding="utf-8")

    def _extract_quoted_value(self, markdown: str, key: str, default: str) -> str:
        """从 md 原文中提取固定字段的反引号值。

        入参：
        - markdown：协议 md 原文。
        - key：字段名，例如 version 或 catalogId。
        - default：提取不到时使用的默认值。
        出参：字段值。
        """
        match = re.search(rf"`{re.escape(key)}`[^\"“”]*[\"“]([^\"”]+)[\"”]", markdown)
        return match.group(1) if match else default

    def _extract_component_whitelist(self, component_catalog_md: str) -> list[str]:
        """从组件目录 md 中提取允许组件白名单。

        入参：
        - component_catalog_md：component-catalog.md 原文。
        出参：组件名称列表。
        """
        match = re.search(r"允许组件：(.+)", component_catalog_md)
        if not match:
            return [
                "Text",
                "Image",
                "Divider",
                "Progress",
                "Button",
                "Checkbox",
                "Row",
                "Column",
                "List",
                "Stack",
            ]
        return re.findall(r"`([^`]+)`", match.group(1))
