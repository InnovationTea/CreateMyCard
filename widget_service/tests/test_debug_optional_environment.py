"""外部工具缺失时的启动、状态查询和按需失败回归。"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools import runtime_environment, static_site
from debug_tools.batch_testing import api as batch_api
from debug_tools.batch_testing import managed_config
from debug_tools.device_debug import config as device_config
from debug_tools.device_debug.commands import DeviceError
from debug_tools.end_to_end_debug.backend import server
from debug_tools.end_to_end_debug.backend.debug_agent.config import DebugSettings
from debug_tools.postprocess_plugins.device_capture.plugin import DeviceCaptureManager, run_builtin
from debug_tools.postprocess_plugins.gallery.plugin import BatchGalleryManager
from debug_tools.postprocess_plugins.validation_failure_gallery.history import (
    ValidationFailureGalleryManager,
)
from debug_tools.postprocess_plugins.validation_failure_gallery.plugin import (
    ValidationFailureGalleryManager as LegacyValidationFailureGalleryManager,
)
from debug_tools.runtime_environment import ToolchainError, load_toolchain
from fastapi.testclient import TestClient


@pytest.fixture
def missing_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "debug_tool.yaml"
    path.write_text("platform: {}\n", encoding="utf-8")
    monkeypatch.setattr(runtime_environment, "DEFAULT_CONFIG_PATH", path)
    monkeypatch.setattr(runtime_environment.shutil, "which", lambda _name: None)
    monkeypatch.setattr(device_config, "DEBUG_TOOLS_ROOT", tmp_path)
    monkeypatch.setattr(batch_api, "DEBUG_TOOLS_ROOT", tmp_path)
    return path


@pytest.mark.parametrize("mode", ["frontend", "full"])
@pytest.mark.parametrize(
    "condition", ["missing_node", "missing_deveco", "invalid_node", "missing_config"]
)
def test_application_starts_without_external_tools(
    missing_environment: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    condition: str,
) -> None:
    if condition == "missing_config":
        missing_environment.unlink()
        monkeypatch.setattr(server, "DEBUG_TOOLS_ROOT", tmp_path)
        monkeypatch.setattr(managed_config, "config_path", lambda _root: missing_environment)
    elif condition == "missing_deveco":
        node = tmp_path / "node.exe"
        node.touch()
        missing_environment.write_text(
            f"platform:\n  environment:\n    node_executable: {node.as_posix()}\n",
            encoding="utf-8",
        )
    elif condition == "invalid_node":
        missing_environment.write_text(
            "platform:\n  environment:\n    node_executable: nonexistent-node.exe\n",
            encoding="utf-8",
        )
    if mode == "frontend":
        app = static_site.create_frontend_app(trace_root=tmp_path / "traces")
    else:
        app = server.create_app(
            debug_settings=None if condition == "missing_config" else DebugSettings(),
            production_settings=SimpleNamespace(server_port=8855),
            trace_root=tmp_path / "traces",
        )
    with TestClient(app) as client:
        assert client.get("/debug/").status_code == 200
        if condition == "missing_config":
            defaults = client.get("/debug/batch/service-config/defaults")
            assert defaults.status_code == 200
            assert defaults.json().get("localConfigExists") is False
            if mode == "full":
                assert client.get("/debug/health").status_code == 200
                assert client.get("/debug/skills").status_code == 200
        response = client.get("/debug/device/environment")
        assert response.status_code == 200
        checks = response.json().get("checks")
        assert isinstance(checks, list)
        assert checks[0].get("ok") is False
        assert checks[0].get("detail")
        availability = client.get("/debug/batch/device-capture/config")
        assert availability.status_code == 200
        assert availability.json().get("available") is False
        assert availability.json().get("error")
        for endpoint in ["targets", "operations/test", "runs/test", "runs/test/logs"]:
            response = client.get(f"/debug/device/{endpoint}")
            assert response.status_code == 503
            assert response.json().get("detail")
        assert client.post("/debug/device/emulators/test/start").status_code == 503
        assert client.post("/debug/device/runs/test/cancel").status_code == 503
        response = client.post(
            "/debug/device/convert",
            json={"source": "invalid input", "format": "compact"},
        )
        assert response.status_code == 422
        response = client.post(
            "/debug/device/convert",
            json={"source": '{"createSurface":{"surfaceId":"test"}}', "format": "a2ui"},
        )
        assert response.status_code == 200
        assert response.json().get("messageCount") == 1
        with client.websocket_connect("/debug/device/targets/test/screen") as websocket:
            assert websocket.receive_json().get("status") == "error"
    assert "调试平台继续启动" in caplog.text
    assert app.state.device_jobs is None
    if condition == "missing_config":
        assert not missing_environment.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "manager_type",
    [BatchGalleryManager, ValidationFailureGalleryManager, LegacyValidationFailureGalleryManager],
)
async def test_gallery_requires_node_only_when_capturing(
    missing_environment: Path, tmp_path: Path, manager_type: type
) -> None:
    manager = manager_type(tmp_path, "http://127.0.0.1:8888/debug")
    assert manager.toolchain is None
    with pytest.raises(ToolchainError, match="未配置 Node.js"):
        await manager._capture_with_browser("http://127.0.0.1:8888/debug", tmp_path)


def test_explicit_invalid_node_does_not_fall_back(
    missing_environment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_environment.write_text(
        "platform:\n  environment:\n    node_executable: nonexistent-node.exe\n",
        encoding="utf-8",
    )

    def unexpected_lookup(_name: str) -> None:
        pytest.fail("显式路径无效时不得回退到 PATH")

    monkeypatch.setattr(runtime_environment.shutil, "which", unexpected_lookup)
    with pytest.raises(ToolchainError, match="显式配置的 Node.js 不存在"):
        load_toolchain()


@pytest.mark.asyncio
async def test_device_capture_fails_with_configuration_reason(
    missing_environment: Path, tmp_path: Path
) -> None:
    manager = DeviceCaptureManager(tmp_path)
    with pytest.raises(DeviceError, match="未配置 Node.js"):
        await run_builtin(manager, "run-one", tmp_path / "capture", {"targetId": "test"})
