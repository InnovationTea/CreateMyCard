# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
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
    capability_registry_version: str = "ohos-36_rom-7.0.0"
    protocol_profile_id: str = "a2ui-form-rom7-v1"
    mock_ids_response_path: str = "docs/ids_res.txt"
    ids_query_url: str = "http://{{ip}}:{{port}}/hiai/ids/databus/v1/kvcommondata/query"
    ids_calling_uid: str = "decisionhub"
    ids_dev_fake_id: str = "123**********postmantestdevFakeId"
    ids_access_key: str = "23232323232"
    ids_secret_key: str = "22222"
    ids_request_timeout_seconds: float = 5.0
    default_device_rom_version: str = "ALN-AL00 7.0.0.36"
    default_ohos_api_version: int = 36
    enable_artifact_validation: bool = True
    artifact_base_url: str = "https://obs.todo.local/widget"
    server_host: str = "127.0.0.1"
    server_port: int = 8855

    @property
    def package_root(self) -> Path:
        """获取 Python 包根目录。

        入参：无。
        出参：`cloud` 包目录的绝对路径。
        """
        return Path(__file__).resolve().parents[1]

    @property
    def data_root(self) -> Path:
        """获取服务配置数据目录。

        入参：无。
        出参：`cloud/data` 的绝对路径。
        """
        return self.package_root / "data"

    @property
    def repo_root(self) -> Path:
        """获取仓库根目录。

        入参：无。
        出参：当前项目仓库根路径。
        """
        return self.package_root.parents[1]

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
