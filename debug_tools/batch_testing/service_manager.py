"""批量测试受管微服务配置与子进程生命周期。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import psutil
import yaml

from .runner import atomic_write_json

_ENV_PREFIX = "WIDGET_SERVICE_"
@dataclass(frozen=True)
class ServiceConfigField:
    env_suffix: str
    yaml_section: str
    yaml_name: str
    value_type: type
    default: Any
    exposed: bool = True


_SERVICE_CONFIG: dict[str, ServiceConfigField] = {
    "startupTimeoutSeconds": ServiceConfigField(
        "DEBUG_SERVICE_STARTUP_TIMEOUT_SECONDS",
        "batch_testing",
        "service_startup_timeout_seconds",
        float,
        30.0,
        False,
    ),
    "enableGenerationTraceRecording": ServiceConfigField(
        "ENABLE_GENERATION_TRACE_RECORDING",
        "batch_testing",
        "enable_generation_trace_recording",
        bool,
        False,
        False,
    ),
    "generationTraceRoot": ServiceConfigField(
        "GENERATION_TRACE_ROOT",
        "batch_testing",
        "trace_root",
        str,
        "workspace/traces",
        False,
    ),
    "enableA2uiModelMock": ServiceConfigField(
        "ENABLE_A2UI_MODEL_MOCK",
        "batch_testing",
        "enable_a2ui_model_mock",
        bool,
        True,
    ),
    "designCompactModelBackend": ServiceConfigField(
        "DESIGN_COMPACT_MODEL_BACKEND",
        "model",
        "design_compact_model_backend",
        str,
        "openai",
    ),
    "openaiMasterClient": ServiceConfigField(
        "OPENAI_MASTER_CLIENT", "model", "openai_master_client", str, "deepseek_official_http"
    ),
    "openaiFallbackClient": ServiceConfigField(
        "OPENAI_FALLBACK_CLIENT", "model", "openai_fallback_client", str, "llmclient"
    ),
    "deepseekOfficialHttpModel": ServiceConfigField(
        "DEEPSEEK_OFFICIAL_HTTP_MODEL",
        "model",
        "deepseek_official_http_model",
        str,
        "deepseek-flash",
    ),
    "deepseekOfficialHttpTemperature": ServiceConfigField(
        "DEEPSEEK_OFFICIAL_HTTP_TEMPERATURE",
        "model",
        "deepseek_official_http_temperature",
        float,
        0.7,
    ),
    "deepseekOfficialHttpTopP": ServiceConfigField(
        "DEEPSEEK_OFFICIAL_HTTP_TOP_P", "model", "deepseek_official_http_top_p", float, 0.9
    ),
    "deepseekOfficialHttpMaxTokens": ServiceConfigField(
        "DEEPSEEK_OFFICIAL_HTTP_MAX_TOKENS", "model", "deepseek_official_http_max_tokens", int, 8192
    ),
    "deepseekOfficialHttpEnableThinking": ServiceConfigField(
        "DEEPSEEK_OFFICIAL_HTTP_ENABLE_THINKING",
        "model",
        "deepseek_official_http_enable_thinking",
        bool,
        False,
    ),
    "modelMaxConcurrency": ServiceConfigField(
        "MODEL_MAX_CONCURRENCY", "model", "model_max_concurrency", int, 20, False
    ),
    "modelQueueTimeoutSeconds": ServiceConfigField(
        "MODEL_QUEUE_TIMEOUT_SECONDS", "model", "model_queue_timeout_seconds", float, 120.0, False
    ),
    "modelRequestTimeoutSeconds": ServiceConfigField(
        "MODEL_REQUEST_TIMEOUT_SECONDS",
        "model",
        "model_request_timeout_seconds",
        float,
        120.0,
        False,
    ),
    "enableModelFailureRetry": ServiceConfigField(
        "ENABLE_MODEL_FAILURE_RETRY", "model", "enable_model_failure_retry", bool, False
    ),
    "modelFailureMaxRetryAttempts": ServiceConfigField(
        "MODEL_FAILURE_MAX_RETRY_ATTEMPTS", "model", "model_failure_max_retry_attempts", int, 1
    ),
    "fallbackModelFailureMaxRetryAttempts": ServiceConfigField(
        "FALLBACK_MODEL_FAILURE_MAX_RETRY_ATTEMPTS",
        "model",
        "fallback_model_failure_max_retry_attempts",
        int,
        1,
    ),
    "enableOpenaiFallback": ServiceConfigField(
        "ENABLE_OPENAI_FALLBACK", "model", "enable_openai_fallback", bool, True
    ),
    "enableValidationFailureRetry": ServiceConfigField(
        "ENABLE_VALIDATION_FAILURE_RETRY",
        "batch_testing",
        "enable_validation_failure_retry",
        bool,
        False,
    ),
    "validationFailureMaxRepairAttempts": ServiceConfigField(
        "VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS",
        "batch_testing",
        "validation_failure_max_repair_attempts",
        int,
        1,
    ),
    "enableCompactDslInterfaceRetry": ServiceConfigField(
        "ENABLE_COMPACT_DSL_INTERFACE_RETRY",
        "batch_testing",
        "enable_compact_dsl_interface_retry",
        bool,
        False,
    ),
    "compactDslInterfaceRetryCount": ServiceConfigField(
        "COMPACT_DSL_INTERFACE_RETRY_COUNT",
        "batch_testing",
        "compact_dsl_interface_retry_count",
        int,
        1,
    ),
    "enableArtifactValidation": ServiceConfigField(
        "ENABLE_ARTIFACT_VALIDATION",
        "batch_testing",
        "enable_artifact_validation",
        bool,
        True,
        False,
    ),
    "enableArtifactDownloadMock": ServiceConfigField(
        "ENABLE_ARTIFACT_DOWNLOAD_MOCK",
        "batch_testing",
        "enable_artifact_download_mock",
        bool,
        True,
        False,
    ),
}

_BATCH_CONFIG: dict[str, tuple[str, type, Any]] = {
    "concurrency": ("concurrency", int, 4),
    "maxRetries": ("max_retries", int, 1),
    "requestTimeoutSeconds": ("request_timeout_seconds", float, 300.0),
    "traceRoot": ("trace_root", str, "workspace/traces"),
}


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _debug_agent_config(project_root: Path) -> dict[str, Any]:
    relative = Path("debug_tools/end_to_end_debug/backend/debug_agent.yaml")
    candidates = (project_root / relative, project_root.parent / relative)
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _yaml_value(config: dict[str, Any], section_name: str, field_name: str, default: Any) -> Any:
    section = config.get(section_name)
    if not isinstance(section, dict):
        return default
    return section.get(field_name, default)


def _coerce(value: object, value_type: type, default: Any) -> Any:
    if value is None:
        return default
    if value_type is bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"无法解析布尔配置: {value}")
    if value_type is int:
        if isinstance(value, bool):
            raise ValueError("布尔值不能作为整数配置")
        return int(value)
    if value_type is float:
        if isinstance(value, bool):
            raise ValueError("布尔值不能作为数值配置")
        return float(value)
    return str(value)


def load_service_defaults(project_root: Path) -> dict[str, Any]:
    """只读取允许下发到浏览器的非敏感配置。"""

    yaml_config = _debug_agent_config(project_root)
    dotenv = _parse_env_file(project_root / ".env")
    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for public_name, field in _SERVICE_CONFIG.items():
        if not field.exposed:
            continue
        environment_name = f"{_ENV_PREFIX}{field.env_suffix}"
        raw_value = _yaml_value(
            yaml_config,
            field.yaml_section,
            field.yaml_name,
            field.default,
        )
        source = "debug_agent.yaml"
        if environment_name in dotenv:
            raw_value = dotenv[environment_name]
            source = ".env"
        if environment_name in os.environ:
            raw_value = os.environ[environment_name]
            source = "environment"
        try:
            values[public_name] = _coerce(raw_value, field.value_type, field.default)
        except (TypeError, ValueError):
            values[public_name] = field.default
            source = "default_invalid_override"
        sources[public_name] = source
    return {"values": values, "sources": sources}


def load_batch_defaults(project_root: Path) -> dict[str, Any]:
    yaml_config = _debug_agent_config(project_root)
    section = yaml_config.get("batch_testing")
    batch_config = section if isinstance(section, dict) else {}
    result: dict[str, Any] = {}
    for public_name, (yaml_name, value_type, default) in _BATCH_CONFIG.items():
        try:
            result[public_name] = _coerce(batch_config.get(yaml_name), value_type, default)
        except (TypeError, ValueError):
            result[public_name] = default
    concurrency = result.get("concurrency")
    if (
        not isinstance(concurrency, int)
        or isinstance(concurrency, bool)
        or not 1 <= concurrency <= 16
    ):
        raise ValueError("debug_agent.yaml 中 batch_testing.concurrency 必须在 1 到 16 之间")
    max_retries = result.get("maxRetries")
    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 0 <= max_retries <= 5
    ):
        raise ValueError("debug_agent.yaml 中 batch_testing.max_retries 必须在 0 到 5 之间")
    request_timeout = result.get("requestTimeoutSeconds")
    if not isinstance(request_timeout, (int, float)) or not 1 <= request_timeout <= 3600:
        raise ValueError(
            "debug_agent.yaml 中 batch_testing.request_timeout_seconds 必须在 1 到 3600 之间"
        )
    trace_root = result.get("traceRoot")
    if not isinstance(trace_root, str) or not trace_root.strip():
        raise ValueError("debug_agent.yaml 中 batch_testing.trace_root 不能为空")
    return result


def _resolved_service_config(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    yaml_config = _debug_agent_config(project_root)
    dotenv = _parse_env_file(project_root / ".env")
    result: dict[str, Any] = {}
    for public_name, field in _SERVICE_CONFIG.items():
        environment_name = f"{_ENV_PREFIX}{field.env_suffix}"
        raw_value = _yaml_value(
            yaml_config,
            field.yaml_section,
            field.yaml_name,
            field.default,
        )
        if environment_name in dotenv:
            raw_value = dotenv[environment_name]
        if environment_name in os.environ:
            raw_value = os.environ[environment_name]
        if field.exposed and public_name in config:
            raw_value = config.get(public_name)
        result[public_name] = _coerce(raw_value, field.value_type, field.default)
    startup_timeout = result.get("startupTimeoutSeconds")
    if not isinstance(startup_timeout, (int, float)) or not 1 <= startup_timeout <= 300:
        raise ValueError(
            "debug_agent.yaml 中 batch_testing.service_startup_timeout_seconds "
            "必须在 1 到 300 之间"
        )
    for name in (
        "modelMaxConcurrency",
        "modelFailureMaxRetryAttempts",
        "fallbackModelFailureMaxRetryAttempts",
        "validationFailureMaxRepairAttempts",
        "compactDslInterfaceRetryCount",
    ):
        value = result.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} 必须是非负整数")
    return result


def validate_service_config(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    defaults = load_service_defaults(project_root)["values"]
    exposed_names = {name for name, field in _SERVICE_CONFIG.items() if field.exposed}
    unknown = sorted(set(config).difference(exposed_names))
    if unknown:
        raise ValueError(f"包含不支持的微服务配置: {', '.join(unknown)}")
    result = dict(defaults)
    for public_name, raw_value in config.items():
        field = _SERVICE_CONFIG[public_name]
        result[public_name] = _coerce(raw_value, field.value_type, field.default)
    for name in (
        "modelFailureMaxRetryAttempts",
        "fallbackModelFailureMaxRetryAttempts",
        "validationFailureMaxRepairAttempts",
        "compactDslInterfaceRetryCount",
    ):
        value = result.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} 必须是非负整数")
    return result


def managed_endpoint(port: int) -> str:
    return f"ws://127.0.0.1:{port}/api/v1/ws/tools"


@dataclass
class ManagedService:
    process: asyncio.subprocess.Process
    fingerprint: str
    config: dict[str, Any]
    log_path: Path
    create_time: float
    port: int


class ManagedServiceController:
    """只管理由当前调试平台启动并可证明身份的微服务进程。"""

    def __init__(self, project_root: Path, output_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.output_root = output_root.resolve()
        self.state_path = self.output_root / "managed_service.json"
        self.service: ManagedService | None = None
        self.last_log_path: Path | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def recover_orphan(self) -> None:
        if not self.state_path.is_file():
            return
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            pid = int(state.get("pid"))
            create_time = float(state.get("createTime"))
            process = psutil.Process(pid)
            command = " ".join(process.cmdline()).lower()
            matches = abs(process.create_time() - create_time) < 1.0
            matches = matches and "start_websocket_server.py" in command
            if matches:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, 5)
                except psutil.TimeoutExpired:
                    process.kill()
        except (OSError, ValueError, TypeError, json.JSONDecodeError, psutil.Error):
            pass
        self.state_path.unlink(missing_ok=True)

    async def ensure(self, config: dict[str, Any]) -> str:
        async with self._lifecycle_lock:
            return await self._ensure(config)

    async def _ensure(self, config: dict[str, Any]) -> str:
        overrides = validate_service_config(config, self.project_root)
        validated = _resolved_service_config(overrides, self.project_root)
        fingerprint = hashlib.sha256(
            json.dumps(validated, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if self.service is not None:
            running = self.service.process.returncode is None
            if running and self.service.fingerprint == fingerprint:
                return managed_endpoint(self.service.port)
            await self.stop()
        port = self._find_available_port()

        log_root = self.output_root / "service_logs"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / f"service_{fingerprint[:12]}.log"
        self.last_log_path = log_path
        environment = os.environ.copy()
        environment[f"{_ENV_PREFIX}SERVER_HOST"] = "127.0.0.1"
        environment[f"{_ENV_PREFIX}SERVER_PORT"] = str(port)
        for public_name, value in validated.items():
            suffix = _SERVICE_CONFIG[public_name].env_suffix
            if suffix == "DEBUG_SERVICE_STARTUP_TIMEOUT_SECONDS":
                continue
            environment[f"{_ENV_PREFIX}{suffix}"] = self._environment_value(value)
        command = [sys.executable, str(self.project_root / "cloud" / "start_websocket_server.py")]
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        log_handle = log_path.open("ab")
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.project_root,
                env=environment,
                stdout=log_handle,
                stderr=asyncio.subprocess.STDOUT,
                creationflags=creation_flags,
            )
        finally:
            log_handle.close()
        create_time = psutil.Process(process.pid).create_time()
        self.service = ManagedService(process, fingerprint, validated, log_path, create_time, port)
        atomic_write_json(
            self.state_path,
            {
                "pid": process.pid,
                "createTime": create_time,
                "fingerprint": fingerprint,
                "command": command,
                "logPath": str(log_path),
                "port": port,
            },
        )
        await self._wait_until_ready(port, float(validated["startupTimeoutSeconds"]))
        return managed_endpoint(port)

    async def status(self) -> dict[str, Any]:
        service = self.service
        if service is None or service.process.returncode is not None:
            return {
                "available": False,
                "detail": "尚未启动",
                "logPath": str(self.last_log_path) if self.last_log_path else "",
            }
        available, detail = await probe_service_health(managed_endpoint(service.port))
        return {
            "available": available,
            "detail": detail,
            "endpoint": managed_endpoint(service.port),
            "logPath": str(service.log_path),
        }

    async def stop(self) -> None:
        service = self.service
        self.service = None
        if service is not None and service.process.returncode is None:
            service.process.terminate()
            try:
                await asyncio.wait_for(service.process.wait(), timeout=8.0)
            except TimeoutError:
                service.process.kill()
                await service.process.wait()
        self.state_path.unlink(missing_ok=True)

    async def _wait_until_ready(self, port: int, timeout_seconds: float) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        url = f"http://127.0.0.1:{port}/health"
        async with httpx.AsyncClient(timeout=1.0, trust_env=False) as client:
            while asyncio.get_running_loop().time() < deadline:
                service = self.service
                if service is None or service.process.returncode is not None:
                    exit_code = None if service is None else service.process.returncode
                    await self.stop()
                    raise RuntimeError(
                        f"受管微服务在健康检查前退出（退出码 {exit_code}），"
                        f"日志: {self.last_log_path}"
                    )
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.2)
        await self.stop()
        raise RuntimeError(
            f"受管微服务启动超时，无法访问 {url}，日志: {self.last_log_path}"
        )

    @staticmethod
    def _find_available_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.bind(("127.0.0.1", 0))
            port = connection.getsockname()[1]
        return int(port)

    @staticmethod
    def _environment_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)


async def probe_service_health(tool_ws_base_url: str) -> tuple[bool, str]:
    """将工具 WebSocket 根地址映射到微服务 /health 并执行一次探活。"""

    normalized = tool_ws_base_url.strip()
    if not normalized:
        return False, "未配置地址"
    try:
        parts = urlsplit(normalized)
    except ValueError as exc:
        return False, f"地址无效: {exc}"
    if parts.scheme not in {"ws", "wss", "http", "https"} or not parts.hostname:
        return False, "地址必须是完整的 ws/wss/http/https URL"
    http_scheme = "https" if parts.scheme in {"wss", "https"} else "http"
    health_url = urlunsplit((http_scheme, parts.netloc, "/health", "", ""))
    try:
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            response = await client.get(health_url)
        if response.status_code == 200:
            return True, f"{health_url} 返回 200"
        return False, f"{health_url} 返回 {response.status_code}"
    except httpx.HTTPError as exc:
        return False, f"{health_url} 无法访问: {type(exc).__name__}"
