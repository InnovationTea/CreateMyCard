from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WIDGET_SERVICE_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "local"
    capability_registry_version: str = "2026-07-03"
    protocol_profile_id: str = "a2ui-form-rom7-v1"
    mock_ids_response_path: str = "docs/ids_res.txt"
    artifact_base_url: str = "https://obs.todo.local/widget"

    @property
    def package_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def data_root(self) -> Path:
        return self.package_root / "data"

    @property
    def repo_root(self) -> Path:
        return self.package_root.parents[2]

    @property
    def resolved_mock_ids_response_path(self) -> Path:
        path = Path(self.mock_ids_response_path)
        if path.is_absolute():
            return path
        return (self.repo_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
