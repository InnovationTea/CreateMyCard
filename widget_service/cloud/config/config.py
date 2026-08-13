# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import platform
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_APP_VERSION = ".".join(("11", "7", "5", "205"))
_DEFAULT_CAPABILITY_REGISTRY_VERSION = f"app-{_DEFAULT_APP_VERSION}_rom-6.0"
_DEFAULT_LLMCLIENT_HOST = ".".join(("10", "32", "101", "24"))
_DEFAULT_LLMCLIENT_WS_URL = (
    f"ws://{_DEFAULT_LLMCLIENT_HOST}:18087/llm/websocket/openai/chat/completions"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WIDGET_SERVICE_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "local"
    enable_sensitive_log_fields: bool = True
    capability_registry_version: str = _DEFAULT_CAPABILITY_REGISTRY_VERSION
    enable_default_capability_registry_fallback: bool = True
    ids_installation_filter_package_names: tuple[str, ...] = (
        "com.huawei.hmos.health.core",
    )
    protocol_profile_id: str = "a2ui-form-rom6.0-v1"
    design_compact_profile_id: str = "design-compact-dsl"
    enable_default_protocol_profile_fallback: bool = True
    enable_ids_mock: bool = True
    mock_ids_response_path: str = "data/mock/ids_res.json"
    ids_query_url: str = "http://{{ip}}:{{port}}/hiai/ids/databus/v1/kvcommondata/query"
    ids_calling_uid: str = "decisionhub"
    ids_dev_fake_id: str = "123**********postmantestdevFakeId"
    ids_access_key: str = "23232323232"
    ids_secret_key: str = "22222"
    ids_request_timeout_seconds: float = 5.0
    default_device_rom_version: str = "6.0"
    default_prd_version: str = _DEFAULT_APP_VERSION
    enable_a2ui_model_mock: bool = True
    a2ui_form_model_backend: Literal["mep", "openai"] = "mep"
    design_compact_model_backend: Literal["mep", "openai"] = "openai"
    openai_master_client: Literal["deepseek_platform", "llmclient"] = "deepseek_platform"
    openai_fallback_client: Literal["deepseek_platform", "llmclient"] = "llmclient"
    enable_openai_fallback: bool = True
    # DeepSeek Platform 使用 STS 中的 SK 签名；普通配置中只保存 AK 和 STS key 名。
    deepseek_platform_access_key: str = ""
    deepseek_platform_secret_key_sts_config_key: str = "genui.deepseek.platform.secret.key"
    deepseek_platform_ws_url: str = ""
    deepseek_platform_model_name: str = "AGENT-DEEPSEEK-V4-FLASH"
    deepseek_platform_api_key: str = "AccessService"
    deepseek_platform_sender: str = "superagent"
    deepseek_platform_receiver: str = "LLM-WS"
    deepseek_platform_message_name: str = "llmRecognize"
    deepseek_platform_default_country_code: str = "CN"
    deepseek_platform_default_app_name: str = "com.huawei.hmos.vassistant"
    # llmclient 使用的 DeepSeek 兼容 WebSocket 请求参数；默认值保持原客户端行为。
    deepseek_api_key: str = "AccessService"
    deepseek_model: str = "deepseek-ai/DeepSeek-V4-Flash"
    deepseek_ws_url: str = _DEFAULT_LLMCLIENT_WS_URL
    deepseek_user: str = "genui_user"
    deepseek_request_id: str = "genui_ui"
    deepseek_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    deepseek_top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    deepseek_top_k: int = Field(default=1, ge=1)
    deepseek_max_tokens: int = Field(default=128_000, ge=1)
    deepseek_enable_thinking: bool = False
    deepseek_include_usage: bool = True
    deepseek_debug_usage: bool = True
    deepseek_recv_timeout: int = Field(default=120, ge=1)
    system_prompt_file: str = "docs/system_prompt.txt"
    edit_system_prompt_file: str = "docs/edit_system_prompt.txt"
    repair_system_prompt_file: str = "docs/repair_system_prompt.txt"
    model_prompt_log_preview_chars: int = Field(default=30, ge=0, le=1000)
    model_appid: str = ""
    model_url: str = ""
    model_path: str = "/"
    model_name: str = ""
    model_bid: str = ""
    model_flow_id: str = ""
    model_temperature: float = 0.4
    model_top_k: int = 1
    model_max_concurrency: int = Field(default=20, ge=1, le=200)
    model_queue_timeout_seconds: float = Field(default=120.0, gt=0)
    model_request_timeout_seconds: float = Field(default=120.0, gt=0)
    enable_artifact_validation: bool = True
    # 模型调用异常按异步指数退避重试；与 DSL error 触发定向 repair 的开关相互独立。
    enable_model_failure_retry: bool = False
    model_failure_max_retry_attempts: int = Field(default=1, ge=1, le=10)
    fallback_model_failure_max_retry_attempts: int = Field(default=1, ge=1, le=10)
    model_failure_retry_initial_delay_seconds: float = Field(default=1.0, gt=0.0, le=300.0)
    model_failure_retry_max_delay_seconds: float = Field(default=30.0, gt=0.0, le=600.0)
    model_failure_retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    model_failure_retry_jitter_ratio: float = Field(default=0.2, ge=0.0, lt=1.0)
    enable_validation_failure_retry: bool = False
    validation_failure_max_repair_attempts: int = Field(default=1, ge=1, le=10)
    enable_widget_edit: bool = False
    enable_widget_directive_commands: bool = False
    artifact_base_url: str = "https://obs.todo.local/widget"
    enable_artifact_download_mock: bool = True
    source_artifact_max_bytes: int = 2 * 1024 * 1024
    source_artifact_read_timeout_seconds: float = 5.0
    source_genui_max_chars: int = 200_000
    server_host: str = "localhost"
    server_port: int = 8855
    anyio_thread_pool_tokens: int = 80
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    WORKSPACE_ROOT: Path = PROJECT_ROOT / "workspace"

    @model_validator(mode="after")
    def validate_model_failure_retry_delays(self) -> "Settings":
        """保证退避上限不小于首次等待时间。"""
        max_delay = self.model_failure_retry_max_delay_seconds
        initial_delay = self.model_failure_retry_initial_delay_seconds
        if max_delay < initial_delay:
            raise ValueError("model failure retry max delay must not be less than initial delay")
        if self.openai_master_client == self.openai_fallback_client:
            raise ValueError("OpenAI master and fallback clients must be different")
        return self

    if platform.system() == "Windows":
        LOCAL_FLAG: bool = True
        HTTP_SERVER_URL: str = "http://localhost:8080"
    else:
        LOCAL_FLAG: bool = False
        HTTP_SERVER_URL: str = "https://localhost:8080"

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
    def repository_root(self) -> Path:
        """获取包含 docs 和 widget_service 的项目根目录。"""
        return self.package_root.parent.parent

    def _resolve_repository_file(self, configured_path: str) -> Path:
        path = Path(configured_path)
        if path.is_absolute():
            return path.resolve()
        return (self.repository_root / path).resolve()

    @property
    def resolved_system_prompt_file(self) -> Path:
        """获取首次生成系统提示词文件路径。"""
        return self._resolve_repository_file(self.system_prompt_file)

    @property
    def resolved_edit_system_prompt_file(self) -> Path:
        """获取编辑模式系统提示词文件路径。"""
        return self._resolve_repository_file(self.edit_system_prompt_file)

    @property
    def resolved_repair_system_prompt_file(self) -> Path:
        """获取校验错误修复提示词文件路径。"""
        return self._resolve_repository_file(self.repair_system_prompt_file)

    @property
    def system_prompt(self) -> str:
        """从配置文件读取首次生成系统提示词。"""
        return self.resolved_system_prompt_file.read_text(encoding="utf-8")

    @property
    def edit_system_prompt(self) -> str:
        """从配置文件读取编辑模式系统提示词。"""
        return self.resolved_edit_system_prompt_file.read_text(encoding="utf-8")

    @property
    def repair_system_prompt(self) -> str:
        """从配置文件读取校验错误修复提示词。"""
        return self.resolved_repair_system_prompt_file.read_text(encoding="utf-8")

    @property
    def resolved_mock_ids_response_path(self) -> Path:
        """获取 mock IDS 响应文件路径。

        入参：无。
        出参：解析后的 `cloud/data/mock/ids_res.json` 绝对路径。
        """
        path = Path(self.mock_ids_response_path)
        if path.is_absolute():
            return path
        return (self.package_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。

    入参：无。
    出参：缓存后的 Settings 对象。
    """
    return Settings()


class LoggingConfig:
    PROJECT_ROOT = get_settings().PROJECT_ROOT
    if get_settings().LOCAL_FLAG:
        LOG_DIR = PROJECT_ROOT / "logs"
    else:
        LOG_DIR = "/opt/test/logs/genui-agent-service/debug"
    NOHUP_PATH = PROJECT_ROOT / "nohup.out"
