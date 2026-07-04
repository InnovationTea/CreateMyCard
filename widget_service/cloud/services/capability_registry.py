import re
from pathlib import Path

from core.config import get_settings
from models.capability import AssetCapability, DataCapability, EventCapability
from services.json_loader import load_json


class CapabilityRegistry:
    """从 appVersion+romVersion 文件夹加载数据能力、事件能力和素材能力。"""

    def __init__(
        self,
        version: str | None = None,
        app_version: str | None = None,
        rom_version: str | None = None,
    ) -> None:
        """初始化能力注册表。

        入参：
        - version：显式指定的能力版本文件夹名。
        - app_version：工具入参中的应用版本，用于推导文件夹名。
        - rom_version：工具入参中的 ROM 版本，用于推导文件夹名。
        出参：无；初始化失败时抛出 ValueError。
        """
        self.settings = get_settings()
        self.version = version or self.from_app_rom_versions(
            app_version or "1.0.0",
            rom_version or "7.0.0",
        )
        self.version_dir = self.settings.data_root / "capabilities" / self.version
        if not self.version_dir.exists():
            raise ValueError(f"Capability registry version not found: {self.version}")

    @classmethod
    def from_app_rom_versions(cls, app_version: str, rom_version: str) -> str:
        """根据 appVersion 和 romVersion 生成能力版本文件夹名。

        入参：
        - app_version：应用版本。
        - rom_version：ROM 版本。
        出参：形如 `app-1.0.0_rom-7.0.0` 的文件夹名。
        """
        # 文件夹名就是工具层约定的能力版本契约。
        app = cls._normalize_version_part(app_version)
        rom = cls._normalize_version_part(rom_version)
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
