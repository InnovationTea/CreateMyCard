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

from .managed_config import (
    canonical_name,
    config_path,
    read_configuration,
    runtime_values,
    sensitive,
    validate_changes,
    yaml_document,
)
from .runner import atomic_write_json

_ENV_PREFIX = "WIDGET_SERVICE_"
_NONNEGATIVE_FIELDS = {
    "compact_dsl_interface_retry_count",
    "fallback_model_failure_max_retry_attempts",
    "model_failure_max_retry_attempts",
    "validation_failure_max_repair_attempts",
}

_BATCH_CONFIG: dict[str, tuple[str, type, Any]] = {
    "concurrency": ("concurrency", int, 4),
    "maxRetries": ("max_retries", int, 1),
    "requestTimeoutSeconds": ("request_timeout_seconds", float, 300.0),
    "traceRoot": ("trace_root", str, "workspace/traces"),
}


def _debug_tool_config(project_root: Path) -> dict[str, Any]:
    return yaml_document(config_path(project_root))


def _canonical_name(name: str) -> str:
    return canonical_name(name)


def _environment_name(name: str) -> str:
    return f"{_ENV_PREFIX}{_canonical_name(name).upper()}"


def _coerce(value: object, template: Any) -> Any:
    if template is None:
        return value
    if isinstance(template, bool):
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"无法解析布尔配置: {value}")
    if isinstance(template, int):
        if isinstance(value, bool):
            raise ValueError("布尔值不能作为整数配置")
        return int(value)
    if isinstance(template, float):
        if isinstance(value, bool):
            raise ValueError("布尔值不能作为数值配置")
        return float(value)
    if isinstance(template, (dict, list, tuple)) and isinstance(value, str):
        return json.loads(value)
    if isinstance(template, str):
        return str(value)
    return value


def _mapping(value: object, description: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"debug_tool.yaml 中 {description} 必须是对象")
    return {str(key): item for key, item in value.items()}


def load_service_defaults(project_root: Path) -> dict[str, Any]:
    return read_configuration(project_root).public()


def resolve_artifact_workspace(
    project_root: Path,
    service_config: dict[str, Any] | None = None,
) -> Path:
    values = service_config or {}
    if "workspace_root" not in values:
        values = read_configuration(project_root).values
    value = values.get("workspace_root", project_root / "cloud/workspace")
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError("微服务 workspace_root 必须是非空路径")
    workspace = Path(value)
    if not workspace.is_absolute():
        workspace = project_root / workspace
    return workspace.resolve()


def load_batch_defaults(project_root: Path) -> dict[str, Any]:
    yaml_config = _debug_tool_config(project_root)
    section = yaml_config.get("batch_testing")
    batch_config = section if isinstance(section, dict) else {}
    result: dict[str, Any] = {}
    for public_name, (yaml_name, _value_type, default) in _BATCH_CONFIG.items():
        try:
            raw_value = batch_config.get(yaml_name, default)
            result[public_name] = _coerce(raw_value, default)
        except (TypeError, ValueError):
            result[public_name] = default
    concurrency = result.get("concurrency")
    if (
        not isinstance(concurrency, int)
        or isinstance(concurrency, bool)
        or not 1 <= concurrency <= 16
    ):
        raise ValueError("debug_tool.yaml 中 batch_testing.concurrency 必须在 1 到 16 之间")
    max_retries = result.get("maxRetries")
    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 0 <= max_retries <= 5
    ):
        raise ValueError("debug_tool.yaml 中 batch_testing.max_retries 必须在 0 到 5 之间")
    request_timeout = result.get("requestTimeoutSeconds")
    if not isinstance(request_timeout, (int, float)) or not 1 <= request_timeout <= 3600:
        raise ValueError(
            "debug_tool.yaml 中 batch_testing.request_timeout_seconds 必须在 1 到 3600 之间"
        )
    trace_root = result.get("traceRoot")
    if not isinstance(trace_root, str) or not trace_root.strip():
        raise ValueError("debug_tool.yaml 中 batch_testing.trace_root 不能为空")
    return result


def validate_service_config(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    """仅返回合法的批跑临时覆盖，不固化默认值。"""
    configuration = read_configuration(project_root)
    result = validate_changes(configuration, config, exposed=True)
    _validate_nonnegative_fields(result)
    return result


def _validate_nonnegative_fields(config: dict[str, Any]) -> None:
    for name in _NONNEGATIVE_FIELDS:
        value = config.get(name)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} 必须是非负整数")


def _service_startup_timeout(project_root: Path) -> float:
    config = _debug_tool_config(project_root)
    batch = _mapping(config.get("batch_testing"), "batch_testing")
    timeout = _coerce(batch.get("service_startup_timeout_seconds", 30.0), 30.0)
    if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 300:
        raise ValueError(
            "debug_tool.yaml 中 batch_testing.service_startup_timeout_seconds 必须在 1 到 300 之间"
        )
    return float(timeout)


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
        self.last_public_config: dict[str, Any] | None = None
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
        configuration = read_configuration(self.project_root)
        configuration.values.update(validate_changes(configuration, config, exposed=True))
        validated = runtime_values(configuration)
        public_config: dict[str, Any] = {}
        for name, value in validated.items():
            if sensitive(name):
                continue
            if name.endswith("system_prompt"):
                value = configuration.values.get(name)
            public_config[name] = value
        self.last_public_config = public_config
        _validate_nonnegative_fields(validated)
        fingerprint = hashlib.sha256(
            json.dumps(validated, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if self.service is not None:
            running = self.service.process.returncode is None
            if running and self.service.fingerprint == fingerprint:
                public_config.update(server_host="127.0.0.1", server_port=self.service.port)
                return managed_endpoint(self.service.port)
            await self.stop()
        port = self._find_available_port()
        public_config.update(server_host="127.0.0.1", server_port=port)

        log_root = self.output_root / "service_logs"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / f"service_{fingerprint[:12]}.log"
        self.last_log_path = log_path
        environment = os.environ.copy()
        for key in list(environment):
            if canonical_name(key) in validated:
                del environment[key]
        for name, value in validated.items():
            environment[_environment_name(name)] = self._environment_value(value)
            if name.endswith("system_prompt"):
                environment[f"{_environment_name(name)}_FILE"] = self._environment_value(value)
        environment[f"{_ENV_PREFIX}SERVER_HOST"] = "127.0.0.1"
        environment[f"{_ENV_PREFIX}SERVER_PORT"] = str(port)
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
        await self._wait_until_ready(port, _service_startup_timeout(self.project_root))
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
        raise RuntimeError(f"受管微服务启动超时，无法访问 {url}，日志: {self.last_log_path}")

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
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
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
