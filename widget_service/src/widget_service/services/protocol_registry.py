from widget_service.core.config import get_settings
from widget_service.services.json_loader import load_json


class A2UIProtocolRegistry:
    def __init__(self, profile_id: str | None = None) -> None:
        self.settings = get_settings()
        self.profile_id = profile_id or self.settings.protocol_profile_id

    def get_profile(self) -> dict:
        path = self.settings.data_root / "protocol_profiles" / self.profile_id / "profile.json"
        if not path.exists():
            raise ValueError(f"Protocol profile not found: {self.profile_id}")
        return load_json(path)
