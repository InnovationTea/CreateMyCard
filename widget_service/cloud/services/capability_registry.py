# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from pathlib import Path

from config.config import get_settings
from models.capability import AssetCapability, DataCapability, EventCapability
from services.json_loader import load_json

_MODULE = "[Capability Registry]"


class CapabilityRegistry:
    """从 prdVer+romVersion 文件夹加载数据能力、事件能力和素材能力。"""

    def __init__(
        self,
        version: str | None = None,
        app_version: str | None = None,
        device_rom_version: str | None = None,
    ) -> None:
        """初始化能力注册表。

        入参：
        - version：显式指定的能力版本文件夹名。
        - app_version：deviceInfo.prdVer，对应端侧业务 API 版本。
        - device_rom_version：device.romVersion，用于推导文件夹名。
        出参：无；初始化失败时抛出 ValueError。
        """
        self.settings = get_settings()
        self.version = version or self.from_app_rom_versions(
            app_version or self.settings.default_prd_version,
            device_rom_version or self.settings.default_device_rom_version,
        )
        self.version_dir = self.settings.data_root / "capabilities" / self.version
        if not self.version_dir.exists():
            raise ValueError(f"Capability registry version not found: {self.version}")

    @classmethod
    def from_app_rom_versions(cls, app_version: str, rom_version: str) -> str:
        """根据 prdVer 和 device.romVersion 生成能力版本文件夹名。

        入参：
        - app_version：deviceInfo.prdVer 字符串。
        - rom_version：device.romVersion。
        出参：形如 `app-11.7.5.205_rom-6.0` 的文件夹名。
        """
        # 文件夹名就是工具层约定的能力版本契约。
        app = cls._normalize_version_part(app_version)
        rom = cls.normalize_rom_version(rom_version)
        return f"app-{app}_rom-{rom}"

    @staticmethod
    def _normalize_version_part(value: str) -> str:
        """提取版本字符串中的数字版本片段。

        入参：
        - value：原始版本字符串。
        出参：提取后的版本号；无法提取时返回 `0`。
        """
        match = re.search(r"\d+(?:\.\d+)*", value or "")
        return match.group(0) if match else "0"

    @staticmethod
    def normalize_rom_version(value: str) -> str:
        """从 romVersion 完整字符串中提取主次版本。

        入参：
        - value：原始 ROM 版本，例如 `CLS-AL30 6.0.0.328`。
        出参：用于内部请求和能力目录的版本，例如 `6.0`。
        """
        match = re.search(r"\d+(?:\.\d+)+", value or "")
        if match:
            parts = match.group(0).split(".")
            return ".".join(parts[:2])
        number = re.search(r"\d+", value or "")
        return number.group(0) if number else "0"

    def _path(self, name: str) -> Path:
        """获取当前能力版本目录下的配置文件路径。

        入参：
        - name：配置文件名。
        出参：配置文件绝对路径。
        """
        return self.version_dir / name

    def list_data_capabilities(self) -> list[DataCapability]:
        """列出当前版本的全部数据能力。

        入参：无。
        出参：数据能力对象列表。
        """
        return [DataCapability(**item) for item in load_json(self._path("data_capabilities.json"))]

    def list_event_capabilities(self) -> list[EventCapability]:
        """列出当前版本的全部事件能力。

        入参：无。
        出参：事件能力对象列表。
        """
        return [
            EventCapability(**item) for item in load_json(self._path("event_capabilities.json"))
        ]

    def list_asset_capabilities(self) -> list[AssetCapability]:
        """列出当前版本的全部素材能力。

        入参：无。
        出参：素材能力对象列表。
        """
        return [
            AssetCapability(**item) for item in load_json(self._path("asset_capabilities.json"))
        ]

    def get_data_capability(self, capability_id: str) -> DataCapability | None:
        """按 ID 获取数据能力。

        入参：
        - capability_id：数据能力 ID。
        出参：匹配的数据能力；不存在时返回 None。
        """
        return next(
            (item for item in self.list_data_capabilities() if item.id == capability_id), None
        )

    def get_event_capability(self, capability_id: str) -> EventCapability | None:
        """按 ID 获取事件能力。

        入参：
        - capability_id：事件能力 ID。
        出参：匹配的事件能力；不存在时返回 None。
        """
        return next(
            (item for item in self.list_event_capabilities() if item.id == capability_id), None
        )

    def get_asset_capability(self, asset_id: str) -> AssetCapability | None:
        """按 ID 获取素材能力。

        入参：
        - asset_id：素材能力 ID。
        出参：匹配的素材能力；不存在时返回 None。
        """
        return next((item for item in self.list_asset_capabilities() if item.id == asset_id), None)
