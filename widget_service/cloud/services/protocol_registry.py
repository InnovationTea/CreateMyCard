from core.config import get_settings
from services.json_loader import load_json


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
        出参：协议 profile 字典，包含协议版本、catalogId、尺寸和白名单。
        """
        path = self.settings.data_root / "protocol_profiles" / self.profile_id / "profile.json"
        if not path.exists():
            raise ValueError(f"Protocol profile not found: {self.profile_id}")
        return load_json(path)
