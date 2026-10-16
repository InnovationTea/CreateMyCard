"""批跑使用实际本地目录，并补齐已有样本的渲染产物。"""

import asyncio
import json
from pathlib import Path

import pytest
from debug_tools.batch_testing import artifacts
from debug_tools.batch_testing.runner import BatchRunManager, atomic_write_json
from debug_tools.batch_testing.service_manager import resolve_artifact_workspace

ARTIFACT = '```cardspec\n{"suggestSize":"2x2"}\n```\n```genui\n'
ARTIFACT += '{"version":"v0.9","createSurface":{"surfaceId":"card"}}\n```\n'


@pytest.fixture(autouse=True)
def clear_workspace_environment(monkeypatch):
    for name in ("WIDGET_SERVICE_WORKSPACE_ROOT", "WORKSPACE_ROOT", "workspace_root"):
        monkeypatch.delenv(name, raising=False)


def configure_workspace(project_root: Path, workspace: str) -> None:
    config_path = project_root / "cloud" / "config" / "default_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f"workspace_root: {json.dumps(workspace)}\n", encoding="utf-8")


@pytest.mark.parametrize("source", ["default", "debug", "environment", "dotenv", "task"])
def test_workspace_resolution_uses_service_configuration(tmp_path, monkeypatch, source):
    configure_workspace(tmp_path, "default-artifacts")
    task_config = None
    if source == "debug":
        path = tmp_path / "debug_tools" / "debug_tool.yaml"
        path.parent.mkdir()
        path.write_text(
            "widget_backend:\n  defaults:\n    workspace_root: debug-artifacts\n",
            encoding="utf-8",
        )
    elif source == "environment":
        monkeypatch.setenv("WIDGET_SERVICE_WORKSPACE_ROOT", "environment-artifacts")
    elif source == "dotenv":
        (tmp_path / ".env").write_text(
            "WIDGET_SERVICE_WORKSPACE_ROOT=dotenv-artifacts\n",
            encoding="utf-8",
        )
    elif source == "task":
        task_config = {"workspace_root": "task-artifacts"}
    expected_source = "default" if source == "environment" else source
    assert (
        resolve_artifact_workspace(tmp_path, task_config)
        == tmp_path / f"{expected_source}-artifacts"
    )


def test_workspace_resolution_preserves_override_priority(tmp_path, monkeypatch):
    configure_workspace(tmp_path, "default-artifacts")
    config = tmp_path / "debug_tools" / "debug_tool.yaml"
    config.parent.mkdir()
    config.write_text(
        "widget_backend:\n  defaults:\n    workspace_root: debug-artifacts\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("WIDGET_SERVICE_WORKSPACE_ROOT", "environment-artifacts")
    (tmp_path / ".env").write_text(
        "WIDGET_SERVICE_WORKSPACE_ROOT=dotenv-artifacts\n",
        encoding="utf-8",
    )
    assert resolve_artifact_workspace(tmp_path) == tmp_path / "debug-artifacts"
    assert resolve_artifact_workspace(tmp_path, {"workspace_root": "task-artifacts"}) == (
        tmp_path / "task-artifacts"
    )


def test_running_snapshot_controls_artifact_and_trace_paths(tmp_path):
    project = tmp_path / "service"
    configure_workspace(project, "new-default")
    manager = BatchRunManager(
        tmp_path / "datasets",
        tmp_path / "output",
        tmp_path / "traces",
        project / "cloud",
    )
    run_dir = tmp_path / "output/run_snapshot"
    atomic_write_json(
        tmp_path / "output/executions/run_snapshot.json",
        {
            "effectiveServiceConfig": {
                "workspace_root": "original-artifacts",
                "generation_trace_root": "original-traces",
            },
        },
    )
    assert manager._artifact_roots(run_dir)[0] == project / "original-artifacts"
    assert manager._trace_importer_for_run(run_dir).trace_root == project / "original-traces"


@pytest.mark.parametrize("mock_copy", [False, True])
@pytest.mark.asyncio
async def test_batch_collects_from_configured_workspace(tmp_path, monkeypatch, mock_copy):
    project = tmp_path / "service"
    workspace = tmp_path / "custom-output"
    configure_workspace(project, str(workspace))
    storage = workspace / "mock_obs" if mock_copy else workspace
    storage.mkdir(parents=True)
    (storage / "artifact.md").write_text(ARTIFACT, encoding="utf-8")
    datasets = tmp_path / "datasets"
    atomic_write_json(datasets / "Q001.json", {"content": {"userQuery": "天气卡片"}})

    async def invoke(*_args):
        return {"status": "success", "data": {"artifactUrl": "https://obs.todo.local/artifact.md"}}

    async def import_trace(*_args):
        return {"status": "complete"}

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("本地产物不得访问网络")

    monkeypatch.setattr(artifacts, "urlopen", unexpected_network)
    manager = BatchRunManager(
        datasets,
        tmp_path / "output",
        tmp_path / "traces",
        project / "cloud",
        invoke=invoke,
    )
    monkeypatch.setattr(manager, "_import_trace", import_trace)
    started = manager.start_run(["Q001"], "ws://localhost/tools", 1, 0)
    run_id = started.get("runId")
    assert isinstance(run_id, str)
    task = manager.tasks.get(run_id)
    assert task is not None
    await asyncio.wait_for(task, 3)
    summary = manager.get_sample(run_id, "Q001").get("summary")
    assert isinstance(summary, dict)
    assert summary.get("dslAvailable") is True
    assert summary.get("error") == ""


@pytest.mark.parametrize("local_available", [False, True])
def test_existing_sample_recovers_locally_without_regeneration(
    tmp_path, monkeypatch, local_available
):
    project = tmp_path / "service"
    workspace = tmp_path / "custom-output"
    configure_workspace(project, "wrong-default")
    output = tmp_path / "output"
    run_dir = output / "run_001"
    attempt_dir = run_dir / "Q001" / "attempt_000"
    result = {
        "id": "Q001",
        "status": "success",
        "finalAttempt": 0,
        "attemptCount": 1,
        "artifactAvailable": False,
        "dslAvailable": False,
        "error": "DNS 下载失败",
        "traceStatus": "complete",
        "elapsedMs": 125.0,
    }
    atomic_write_json(run_dir / "summary.json", {"taskId": "task_001", "samples": [result]})
    atomic_write_json(run_dir / "manifest.json", {"samples": [result]})
    atomic_write_json(
        output / "tasks" / "task_001.json",
        {
            "backendMode": "managed",
            "serviceConfig": {"workspace_root": str(workspace)},
        },
    )
    atomic_write_json(run_dir / "Q001" / "result.json", result)
    atomic_write_json(attempt_dir / "result.json", result)
    atomic_write_json(
        attempt_dir / "response.json",
        {
            "status": "success",
            "data": {"artifactUrl": "https://obs.todo.local/artifact.md"},
        },
    )
    if local_available:
        workspace.mkdir()
        (workspace / "artifact.md").write_text(ARTIFACT, encoding="utf-8")

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("详情恢复不得访问网络")

    monkeypatch.setattr(artifacts, "urlopen", unexpected_network)
    manager = BatchRunManager(tmp_path / "datasets", output, tmp_path / "traces", project / "cloud")
    detail = manager.get_sample("run_001", "Q001")
    summary = detail.get("summary")
    assert isinstance(summary, dict)
    assert summary.get("dslAvailable") is local_available
    assert summary.get("status") == "success"
    assert summary.get("elapsedMs") == 125.0
    assert summary.get("attemptCount") == 1
    assert bool(summary.get("error")) is not local_available
    persisted = manager.get_run("run_001").get("samples")
    assert isinstance(persisted, list)
    assert len(persisted) == 1
    assert persisted[0].get("dslAvailable") is local_available
    if local_available:
        attempts = detail.get("attempts")
        assert isinstance(attempts, list)
        assert len(attempts) == 1
        assert isinstance(attempts[0].get("genui"), str)


def test_single_message_genui_block_remains_text():
    blocks = artifacts.parse_artifact_blocks(ARTIFACT)
    assert isinstance(blocks.get("genui"), str)
    assert isinstance(blocks.get("cardspec"), dict)


def test_local_only_download_never_falls_back_to_network(tmp_path, monkeypatch):
    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("本地恢复不得回退到网络")

    monkeypatch.setattr(artifacts, "urlopen", unexpected_network)
    with pytest.raises(FileNotFoundError, match="可信本地目录"):
        artifacts.download_artifact(
            "https://obs.todo.local/missing.md",
            tmp_path / "artifact.md",
            (tmp_path,),
            local_only=True,
        )
