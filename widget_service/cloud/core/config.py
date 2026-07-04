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
    capability_registry_version: str = "app-1.0.0_rom-7.0.0"
    protocol_profile_id: str = "a2ui-form-rom7-v1"
    mock_ids_response_path: str = "docs/ids_res.txt"
    artifact_base_url: str = "https://obs.todo.local/widget"

    @property
    def package_root(self) -> Path:
        """获取 Python 包根目录。

        入参：无。
        出参：`src/widget_service` 的绝对路径。
        """
        return Path(__file__).resolve().parents[1]

    @property
    def data_root(self) -> Path:
        """获取服务配置数据目录。

        入参：无。
        出参：`src/widget_service/data` 的绝对路径。
        """
        return self.package_root / "data"

    @property
    def repo_root(self) -> Path:
        """获取仓库根目录。

        入参：无。
        出参：当前项目仓库根路径。
        """
        return self.package_root.parents[2]

    @property
    def resolved_mock_ids_response_path(self) -> Path:
        """获取 mock IDS 响应文件路径。

        入参：无。
        出参：解析后的 `docs/ids_res.txt` 绝对路径。
        """
        path = Path(self.mock_ids_response_path)
        if path.is_absolute():
            return path
        return (self.repo_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。

    入参：无。
    出参：缓存后的 Settings 对象。
    """
    return Settings()
