"""受管配置优先级、保存事务和真实 Settings 兼容回归。"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from debug_tools.batch_testing import managed_config, service_manager
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.managed_config import (
    ConfigConflict,
    read_configuration,
    runtime_values,
    save_configuration,
    validate_changes,
)
from debug_tools.batch_testing.service_manager import ManagedServiceController
from debug_tools.batch_testing.task_manager import BatchTaskManager
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "widget_service"
    config_dir = root / "cloud/config"
    config_dir.mkdir(parents=True)
    (config_dir / "default_config.yaml").write_text(
        "model_max_concurrency: 8\n"
        "enable_model_failure_retry: false\n"
        "system.prompt: '@file:prompt.txt'\n"
        "obs.expire.time: 100\n"
        "asset.src.url.mapping: {}\n"
        "server_port: 8855\n"
        "unknown_legacy: null\n",
        encoding="utf-8",
    )
    (config_dir / "prompt.txt").write_text("测试提示词\n", encoding="utf-8")
    (root / ".env").write_text(
        "WIDGET_SERVICE_MODEL_MAX_CONCURRENCY=12\n"
        "WIDGET_SERVICE_DEEPSEEK_API_KEY=test-private-value\n"
        "WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY=true\n",
        encoding="utf-8",
    )
    debug_dir = tmp_path / "debug_tools"
    debug_dir.mkdir()
    (debug_dir / "debug_tool.yaml").write_text(
        "# 文件注释\nplatform:\n  server:\n    port: 8888 # 保留注释\n"
        "widget_backend:\n  exposed:\n"
        "    model_max_concurrency: 20 # 参数注释\n"
        "  defaults:\n    enable_model_failure_retry: false\n",
        encoding="utf-8",
    )
    return root


def test_precedence_and_public_metadata(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIDGET_SERVICE_MODEL_MAX_CONCURRENCY", "99")
    monkeypatch.setenv("WIDGET_SERVICE_OBS_EXPIRE_TIME", "999")
    monkeypatch.setenv("WIDGET_SERVICE_MODEL_TEMPERATURE", "0.3")
    config = read_configuration(project)
    assert config.values.get("model_max_concurrency") == 20
    assert config.values.get("enable_model_failure_retry") is False
    assert config.values.get("obs_expire_time") == 100
    assert config.values.get("model_temperature") == 0.3
    config.values.update(validate_changes(config, {"MODEL_MAX_CONCURRENCY": 30}, exposed=True))
    assert runtime_values(config).get("model_max_concurrency") == 30
    public = config.public()
    encoded = json.dumps(public)
    assert "test-private-value" not in encoded
    assert "DEEPSEEK_API_KEY" in encoded
    values = public.get("values")
    assert isinstance(values, dict)
    assert values.get("unknown_legacy", "missing") is None
    fields = public.get("fields")
    assert isinstance(fields, list)
    for item in fields:
        if item.get("name") in {"server_port", "deepseek_api_key", "unknown_legacy"}:
            assert item.get("editable") is False
            assert item.get("readOnlyReason")


def test_env_beats_default_when_yaml_omits_field(project: Path) -> None:
    path = project.parent / "debug_tools/debug_tool.yaml"
    path.write_text("widget_backend: {}\n", encoding="utf-8")
    config = read_configuration(project)
    assert config.values.get("model_max_concurrency") == 12
    assert config.sources.get("model_max_concurrency") == ".env"


def test_prefixed_alias_wins_and_boolean_spellings_work(project: Path) -> None:
    (project.parent / "debug_tools/debug_tool.yaml").write_text(
        "widget_backend: {}\n", encoding="utf-8"
    )
    (project / ".env").write_text(
        "WIDGET_SERVICE_MODEL_MAX_CONCURRENCY=30\nMODEL_MAX_CONCURRENCY=1\n"
        "WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY=on\n",
        encoding="utf-8",
    )
    config = read_configuration(project)
    assert config.values.get("model_max_concurrency") == 30
    assert config.values.get("enable_model_failure_retry") is True
    (project / ".env").write_text("BROKEN='unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="格式错误"):
        read_configuration(project)


def test_prompt_modules_are_expanded_without_stale_cache(project: Path) -> None:
    actual_root = Path(__file__).resolve().parents[1]
    default = managed_config.yaml_document(actual_root / "cloud/config/default_config.yaml")
    reference = default.get("system.prompt")
    assert isinstance(reference, str)
    assert reference.startswith("@prompt:")
    config = read_configuration(project)
    config.values["system_prompt"] = reference
    config.directories["system_prompt"] = actual_root / "cloud/config"
    result = runtime_values(config)
    prompt = result.get("system_prompt")
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert not prompt.startswith("@prompt:")


@pytest.mark.parametrize("name", ["server_port", "deepseek_api_key", "unknown_legacy", "new_field"])
def test_reject_readonly_and_unknown_updates(project: Path, name: str) -> None:
    config = read_configuration(project)
    with pytest.raises(ValueError, match="不允许修改"):
        save_configuration(project, {name: 1}, config.version)


def test_reject_nonexposed_override(project: Path) -> None:
    config = read_configuration(project)
    with pytest.raises(ValueError, match="不允许修改"):
        validate_changes(config, {"enable_model_failure_retry": True}, exposed=True)


@pytest.mark.parametrize("value", [True, 1.5, "1.5", None, "not-a-number"])
def test_invalid_integer_does_not_modify_file(project: Path, value: Any) -> None:
    path = project.parent / "debug_tools/debug_tool.yaml"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="配置类型错误"):
        save_configuration(
            project, {"model_max_concurrency": value}, read_configuration(project).version
        )
    assert path.read_bytes() == before


def test_save_updates_existing_group_and_adds_defaults(project: Path) -> None:
    config = read_configuration(project)
    env_before = (project / ".env").read_bytes()
    defaults_path = project / "cloud/config/default_config.yaml"
    defaults_before = defaults_path.read_bytes()
    result = save_configuration(
        project,
        {"model_max_concurrency": 25, "OBS_EXPIRE_TIME": 200},
        config.version,
    )
    sources = result.get("sources")
    assert isinstance(sources, dict)
    assert sources.get("obs_expire_time") == "debug_tool.yaml"
    path = project.parent / "debug_tools/debug_tool.yaml"
    content = path.read_text(encoding="utf-8")
    assert "# 文件注释" in content
    assert "port: 8888 # 保留注释" in content
    assert "model_max_concurrency: 25 # 参数注释" in content
    assert "obs_expire_time: 200" in content
    assert result.get("exposedKeys") == ["model_max_concurrency"]
    assert (project / ".env").read_bytes() == env_before
    assert defaults_path.read_bytes() == defaults_before


def test_noop_and_conflict(project: Path) -> None:
    config = read_configuration(project)
    path = project.parent / "debug_tools/debug_tool.yaml"
    before = path.stat().st_mtime_ns
    save_configuration(project, {"model_max_concurrency": 20}, config.version)
    assert path.stat().st_mtime_ns == before
    path.write_text(path.read_text(encoding="utf-8") + "# 外部修改\n", encoding="utf-8")
    with pytest.raises(ConfigConflict):
        save_configuration(project, {"model_max_concurrency": 30}, config.version)


def test_failed_replace_preserves_original(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = project.parent / "debug_tools/debug_tool.yaml"
    before = path.read_bytes()

    def fail_replace(*_args: object) -> None:
        raise OSError("测试写入失败")

    monkeypatch.setattr(managed_config.os, "replace", fail_replace)
    with pytest.raises(OSError):
        save_configuration(
            project, {"model_max_concurrency": 30}, read_configuration(project).version
        )
    assert path.read_bytes() == before
    assert not list(path.parent.glob(".debug-config-*"))


def test_references_and_json_preserve_runtime_types(project: Path) -> None:
    config = read_configuration(project)
    assert runtime_values(config).get("system_prompt") == "测试提示词\n"
    config.values.update(
        validate_changes(config, {"asset_src_url_mapping": {"a": "b"}}, exposed=False)
    )
    assert runtime_values(config).get("asset_src_url_mapping") == {"a": "b"}
    path = project.parent / "debug_tools/debug_tool.yaml"
    before = path.read_bytes()
    with pytest.raises(OSError):
        save_configuration(project, {"system_prompt": "@file:missing.txt"}, config.version)
    assert path.read_bytes() == before


def test_duplicate_alias_and_malformed_yaml_are_errors(project: Path) -> None:
    path = project.parent / "debug_tools/debug_tool.yaml"
    path.write_text(
        "widget_backend:\n  defaults:\n    OBS_EXPIRE_TIME: 1\n"
        "  exposed:\n    obs.expire.time: 2\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="参数重复"):
        read_configuration(project)
    path.write_text("widget_backend: [", encoding="utf-8")
    with pytest.raises(ValueError, match="配置文件解析失败"):
        read_configuration(project)


def test_save_api_roundtrip_and_rejections(project: Path) -> None:
    manager = BatchTaskManager(
        project.parent / "Datasets",
        project.parent / "output",
        project.parent / "traces",
        project / "cloud",
    )
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    with TestClient(app) as client:
        endpoint = "/debug/batch/service-config/defaults"
        response = client.get(endpoint)
        assert response.status_code == 200
        version = response.json().get("version")
        saved = client.patch(
            endpoint, json={"version": version, "changes": {"obs_expire_time": 250}}
        )
        assert saved.status_code == 200
        assert saved.json().get("sources", {}).get("obs_expire_time") == "debug_tool.yaml"
        conflict = client.patch(
            endpoint, json={"version": version, "changes": {"obs_expire_time": 300}}
        )
        assert conflict.status_code == 409
        rejected = client.patch(
            endpoint,
            json={
                "version": saved.json().get("version"),
                "changes": {"deepseek_api_key": "blocked"},
            },
        )
        assert rejected.status_code == 422
        manual = client.post(
            "/debug/batch/connections/managed/start",
            json={
                "serviceConfig": {"model_max_concurrency": 1},
            },
        )
        assert manual.status_code == 409


def test_config_is_accepted_by_actual_settings() -> None:
    root = Path(__file__).resolve().parents[1]
    config = read_configuration(root)
    config.values["model_max_concurrency"] = 23
    values = runtime_values(config)
    environment = os.environ.copy()
    for name, value in values.items():
        key = f"WIDGET_SERVICE_{name.upper()}"
        environment[key] = ManagedServiceController._environment_value(value)
        if name.endswith("system_prompt"):
            environment[f"{key}_FILE"] = environment.get(key, "")
    script = (
        "from config.config import Settings; s=Settings(); "
        "assert s.model_max_concurrency == 23; "
        "assert isinstance(s.asset_src_url_mapping, dict); "
        "assert not s.system_prompt.startswith('@'); print('settings-ok')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root / "cloud",
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # 不把 Settings 验证错误中的潜在敏感输入输出到测试报告。
    assert completed.returncode == 0, "真实 Settings 加载失败"
    assert "settings-ok" in completed.stdout


def test_lifecycle_fingerprint_detects_file_changes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, str]] = []

    class Process:
        pid = 123
        returncode: int | None = None

        def terminate(self) -> None:
            self.returncode = 0

        async def wait(self) -> int:
            return 0

    class Identity:
        def create_time(self) -> float:
            return 1.0

    async def create(*_command: str, **options: Any) -> Process:
        calls.append(options.get("env", {}))
        return Process()

    async def ready(_port: int, _timeout: float) -> None:
        return None

    monkeypatch.setattr(service_manager.asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(service_manager.psutil, "Process", lambda _pid: Identity())
    controller = ManagedServiceController(project, project.parent / "output")
    monkeypatch.setattr(controller, "_wait_until_ready", ready)
    monkeypatch.setattr(controller, "_find_available_port", lambda: 43123)

    async def exercise() -> None:
        await controller.ensure({})
        await controller.ensure({})
        assert len(calls) == 1
        (project / "cloud/config/prompt.txt").write_text("已改变提示词\n", encoding="utf-8")
        await controller.ensure({})
        assert len(calls) == 2
        config = read_configuration(project)
        save_configuration(project, {"model_max_concurrency": 28}, config.version)
        await controller.ensure({})
        assert len(calls) == 3
        assert calls[-1].get("WIDGET_SERVICE_MODEL_MAX_CONCURRENCY") == "28"
        assert calls[-1].get("WIDGET_SERVICE_SERVER_PORT") == "43123"
        assert calls[-1].get("WIDGET_SERVICE_SERVER_HOST") == "127.0.0.1"
        await controller.stop()

    asyncio.run(exercise())


@pytest.mark.parametrize("exists", [True, False])
def test_local_config_presence_is_independent_of_backend_fields(
    project: Path, exists: bool
) -> None:
    path = project.parent / "debug_tools/debug_tool.yaml"
    if exists:
        path.write_text("platform: {}\n", encoding="utf-8")
    else:
        path.unlink()
    assert read_configuration(project).public().get("localConfigExists") is exists
