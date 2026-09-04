# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import platform
import socket
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

from pydantic_settings import BaseSettings

from config.config_helper import ConfigHelper


def get_container_ip():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)


def _parse_json_config(value: str, fallback):
    """容错解析 IAC 注入的 JSON 字符串配置，非法或缺失时回退默认值。"""
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return fallback


class Settings(BaseSettings):
    container_ip: str = get_container_ip()
    if platform.system() == "Windows":
        LOCAL_FLAG: bool = True
        HTTP_SERVER_URL: str = "http://localhost:8080"
    else:
        LOCAL_FLAG: bool = False
        HTTP_SERVER_URL: str = f"https://{container_ip}:8080"
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    WORKSPACE_ROOT: Path = PROJECT_ROOT / "workspace"

    """配置项"""
    if LOCAL_FLAG:
        CONFIG: ConfigHelper = ConfigHelper("local")
    else:
        CONFIG: ConfigHelper = ConfigHelper("cloud")
    hag_slb_url: str = CONFIG.get("hag_slb_url")
    osms_prepare_url: str = urljoin(hag_slb_url, CONFIG.get("osms_prepare_url"))
    osms_complete_url: str = urljoin(hag_slb_url, CONFIG.get("osms_complete_url"))
    osms_query_url: str = urljoin(hag_slb_url, CONFIG.get("osms_query_url"))
    osms_delete_url: str = urljoin(hag_slb_url, CONFIG.get("osms_delete_url"))
    hag_osms_ak: str = CONFIG.get("hag_osms_ak")
    capability_registry_version: str = "app-11.7.5.205_rom-6.0"
    # src → 云侧 url 映射（JSON 字符串，缺省为空 dict）。生成 DSL 时按 src 命中替换为 url。
    asset_src_url_mapping: dict = _parse_json_config(CONFIG.get("asset.src.url.mapping"), {})
    design_compact_profile_id: str = "design-compact-dsl"
    protocol_profile_id: str = "a2ui-form-rom6.0-v1"
    mock_ids_response_path: str = "data/mock/ids_res.json"
    ids_query_url: str = CONFIG.get("ids_query_url")
    ids_calling_uid: str = "decisionhub"
    ids_dev_fake_id: str = "123**********postmantestdevFakeId"
    ids_sign_secret: str = "postman-test-secret"
    artifact_base_url: str = "https://obs.todo.local/widget"
    server_host: str = "127.0.0.1"
    server_port: int = 8855
    sts_server: str = CONFIG.get("sts_serverDomain")
    ids_request_timeout_seconds: int = 30
    ids_access_key: str = CONFIG.get("ids_access_key")
    obs_preview_supported_file_format: list = ["html"]
    obs_use_edge: bool = CONFIG.get("obs.use.edge") == "true"  # bool类型需要str转bool
    obs_expire_time: int = CONFIG.get("obs.expire.time")
    default_ohos_api_version: int = 6
    enable_artifact_validation: bool = (
        CONFIG.get("enable_artifact_validation") == "true"
    )  # bool类型需要str转bool
    enable_a2ui_model_mock: bool = (
        CONFIG.get("enable_a2ui_model_mock") == "true"
    )  # bool类型需要str转bool
    default_device_rom_version: str = "6.0"
    default_prd_version: str = "1.0.0"
    anyio_thread_pool_tokens: int = 80
    source_artifact_max_bytes: int = 20 * 1024 * 1024
    source_artifact_read_timeout_seconds: float = 35.0
    source_genui_max_chars: int = 200_000
    model_appid: str = CONFIG.get("model_appid")
    model_url: str = CONFIG.get("model_url")
    model_bid: str = CONFIG.get("model_bid")
    model_flow_id: str = CONFIG.get("model_flow_id")
    model_temperature: float = 0.4
    model_top_k: int = 1
    system_prompt: str = CONFIG.get("system.prompt")
    edit_system_prompt: str = CONFIG.get("edit.system.prompt")
    repair_system_prompt: str = CONFIG.get("repair.system.prompt")
    a2ui_form_model_backend: str = CONFIG.get("a2ui_form_model_backend")
    design_compact_model_backend: str = CONFIG.get("design_compact_model_backend")
    validation_failure_max_repair_attempts: int = CONFIG.get(
        "validation_failure_max_repair_attempts"
    )
    model_max_concurrency: int = CONFIG.get("model_max_concurrency")
    model_queue_timeout_seconds: int = CONFIG.get("model_queue_timeout_seconds")
    model_request_timeout_seconds: int = CONFIG.get("model_request_timeout_seconds")
    model_prompt_log_preview_chars: int = CONFIG.get("model_prompt_log_preview_chars")
    # 模型降级配置
    openai_master_client: str = CONFIG.get("openai_master_client")
    openai_fallback_client: str = CONFIG.get("openai_fallback_client")
    # DeepSeekPlatform 配置
    deepseek_platform_access_key: str = CONFIG.get("deepseek_platform_access_key")
    deepseek_platform_secret_key_sts_config_key: str = CONFIG.get(
        "deepseek_platform_secret_key_sts_config_key"
    )
    deepseek_platform_ws_url: str = CONFIG.get("deepseek_platform_ws_url")
    deepseek_platform_api_key: str = CONFIG.get("deepseek_platform_api_key")
    deepseek_platform_sender: str = CONFIG.get("deepseek_platform_sender")
    deepseek_platform_receiver: str = "LLM-WS"
    deepseek_platform_message_name: str = "llmRecognize"
    deepseek_platform_default_country_code: str = "CN"
    deepseek_platform_default_app_name: str = "com.huawei.hmos.vassistant"
    # 模型限流配置
    enable_model_failure_retry: bool = CONFIG.get("enable_model_failure_retry") == "true"
    model_failure_max_retry_attempts: int = CONFIG.get("model_failure_max_retry_attempts")
    fallback_model_failure_max_retry_attempts: int = CONFIG.get(
        "fallback_model_failure_max_retry_attempts"
    )
    model_failure_retry_initial_delay_seconds: float = CONFIG.get(
        "model_failure_retry_initial_delay_seconds"
    )
    model_failure_retry_max_delay_seconds: float = CONFIG.get(
        "model_failure_retry_max_delay_seconds"
    )
    model_failure_retry_backoff_multiplier: float = CONFIG.get(
        "model_failure_retry_backoff_multiplier"
    )
    model_failure_retry_jitter_ratio: float = CONFIG.get("model_failure_retry_jitter_ratio")
    enable_ids_mock: bool = CONFIG.get("enable_ids_mock") == "true"
    enable_default_capability_registry_fallback: bool = (
        CONFIG.get("enable_default_capability_registry_fallback") == "true"
    )
    enable_validation_failure_retry: bool = CONFIG.get("enable_validation_failure_retry") == "true"
    enable_widget_edit: bool = CONFIG.get("enable_widget_edit") == "true"
    enable_artifact_download_mock: bool = CONFIG.get("enable_artifact_download_mock") == "true"
    enable_widget_directive_commands: bool = (
        CONFIG.get("enable_widget_directive_commands") == "true"
    )
    enable_compact_dsl_argument_repair_fallback: bool = (
        CONFIG.get("enable_compact_dsl_argument_repair_fallback", "false") == "true"
    )
    compact_dsl_argument_repair_reminder_count: int = CONFIG.get(
        "compact_dsl_argument_repair_reminder_count",
        1,
    )
    enable_default_protocol_profile_fallback: bool = (
        CONFIG.get("enable_default_protocol_profile_fallback") == "true"
    )
    enable_openai_fallback: bool = CONFIG.get("enable_openai_fallback") == "true"
    enable_sensitive_log_fields: bool = CONFIG.get("enable_sensitive_log_fields") == "true"
    ids_installation_filter_package_names: tuple[str, ...] = (
        "com.huawei.hmsapp.totemweather",
        "com.huawei.hmos.health",
        "com.huawei.hmos.calendar",
    )

    # deepseek v4 flash model config
    deepseek_ws_url: str = CONFIG.get("deepseek_ws_url")
    deepseek_model: str = CONFIG.get("deepseek_model")
    deepseek_api_key: str = CONFIG.get("deepseek_api_key")
    deepseek_user: str = CONFIG.get("deepseek_user")
    deepseek_request_id: str = CONFIG.get("deepseek_request_id")
    deepseek_temperature: float = CONFIG.get("deepseek_temperature")
    deepseek_top_p: float = CONFIG.get("deepseek_top_p")
    deepseek_top_k: int = CONFIG.get("deepseek_top_k")
    deepseek_max_tokens: int = CONFIG.get("deepseek_max_tokens")
    deepseek_enable_thinking: bool = (
        CONFIG.get("deepseek_enable_thinking") == "true"
    )  # bool类型需要str转bool
    deepseek_include_usage: bool = (
        CONFIG.get("deepseek_include_usage") == "true"
    )  # bool类型需要str转bool
    deepseek_debug_usage: bool = (
        CONFIG.get("deepseek_debug_usage") == "true"
    )  # bool类型需要str转bool
    deepseek_recv_timeout: int = CONFIG.get("deepseek_recv_timeout")
    deepseek_platform_model_select: bool = (
        CONFIG.get("deepseek_platform_model_select") == "true"
    )  # 模型选择
    deepseek_platform_model_name: str = (
        CONFIG.get("deepseek_platform_thinking_model_name")
        if deepseek_platform_model_select
        else CONFIG.get("deepseek_platform_model_name")
    )

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
        LOG_DIR = "/opt/huawei/logs/genui-agent-service/debug"
    NOHUP_PATH = PROJECT_ROOT / "nohup.out"
