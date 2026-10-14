from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from debug_tools.batch_testing import service_manager
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.runner import (
    BatchRunManager,
    apply_request_overrides,
)
from debug_tools.batch_testing.service_manager import (
    ManagedServiceController,
    load_batch_defaults,
    load_service_defaults,
)
from debug_tools.batch_testing.task_manager import BatchTaskManager
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _request(query: str) -> dict[str, Any]:
    return {
        "content": {"userQuery": query, "bundleName": "sample.bundle"},
        "deviceInfo": {"locale": "zh-CN", "prdVer": "1.0"},
        "pagination": {"limit": 5, "start": ""},
        "session": {"sessionId": "source", "interactionId": "1"},
        "userAuth": {"user": {"userId": "source"}},
        "version": "1.0",
        "bundleName": "sample.bundle",
    }


def _write_dataset(root: Path, dataset_id: str, sample_id: str = "Q001") -> Path:
    dataset = root / dataset_id
    dataset.mkdir(parents=True)
    (dataset / f"{sample_id}.json").write_text(
        json.dumps(_request(f"query-{sample_id}"), ensure_ascii=False),
        encoding="utf-8",
    )
    return dataset


class FakeServiceController:
    def __init__(self) -> None:
        self.stop_count = 0

    async def recover_orphan(self) -> None:
        return None

    async def ensure(self, _config: dict[str, Any]) -> str:
        return "ws://127.0.0.1:8855/api/v1/ws/tools"

    async def stop(self) -> None:
        self.stop_count += 1

    async def status(self) -> dict[str, Any]:
        return {"available": False, "detail": "尚未启动"}


class FakeGalleryManager:
    def __init__(self) -> None:
        self.started: list[str] = []

    def status(self, run_id: str) -> dict[str, Any]:
        status = "ready" if run_id in self.started else "not_started"
        return {"status": status}

    def start(self, run_id: str, *, force: bool = False) -> dict[str, Any]:
        if run_id not in self.started:
            self.started.append(run_id)
        return {"status": "ready", "force": force}

    async def close(self) -> None:
        return None

    def gallery_path(self, _run_id: str) -> Path:
        raise KeyError


class FakeDeviceCaptureManager:
    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.not_requested_runs: list[str] = []
        self.on_terminal: Any = None

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def availability(self) -> dict[str, Any]:
        return {"configured": True, "available": True, "reason": ""}

    async def require_available(self) -> None:
        return None

    def enqueue(self, run_id: str, *, retry: bool = False) -> dict[str, Any]:
        self.enqueued.append(run_id)
        return {"status": "queued", "retry": retry}

    def not_requested(self, run_id: str) -> dict[str, Any]:
        self.not_requested_runs.append(run_id)
        return {"status": "not_requested"}

    def status(self, run_id: str) -> dict[str, Any]:
        return {
            "status": "ready" if run_id in self.enqueued else "not_requested",
            "items": [],
        }

    def sample(self, _run_id: str, sample_id: str) -> dict[str, Any]:
        return {"id": sample_id, "status": "not_requested"}

    def build_gallery(self, run_id: str) -> dict[str, Any]:
        return {"url": f"/debug/batch/runs/{run_id}/device-gallery.html"}

    def gallery_path(self, _run_id: str) -> Path:
        raise KeyError

    def image_path(self, _run_id: str, _sample_id: str, _kind: str) -> Path:
        raise KeyError


def _task_payload(dataset_id: str) -> dict[str, Any]:
    return {
        "name": "天气回归",
        "datasetId": dataset_id,
        "sampleIds": ["Q001"],
        "requestOverrides": {"locale": "en-US", "bundleName": "override.bundle"},
        "backendMode": "deployed",
        "toolWsBaseUrl": "ws://127.0.0.1:8855/api/v1/ws/tools",
        "serviceConfig": {},
    }


def test_dataset_root_lists_direct_child_folders_only(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    dataset = _write_dataset(datasets_root, "request_dataset")
    nested = dataset / "nested"
    nested.mkdir()
    (nested / "Q999.json").write_text("{}", encoding="utf-8")
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )

    datasets = manager.list_datasets()
    samples = manager.dataset_samples("request_dataset")

    assert datasets == [
        {
            "id": "request_dataset",
            "name": "request_dataset",
            "sampleCount": 1,
            "validSampleCount": 1,
            "invalidSampleCount": 0,
        }
    ]
    assert [sample["id"] for sample in samples] == ["Q001"]


def test_request_overrides_update_public_fields_without_mutating_source() -> None:
    source = _request("hello")

    result = apply_request_overrides(
        source,
        {
            "protocolVersion": "2.0",
            "bundleName": "new.bundle",
            "deviceId": "device-1",
            "locale": "en-US",
            "paginationLimit": 9,
        },
    )

    assert result["version"] == "2.0"
    assert result["bundleName"] == "new.bundle"
    assert result["content"]["bundleName"] == "new.bundle"
    assert result["content"]["odid"] == "device-1"
    assert result["deviceInfo"]["deviceId"] == "device-1"
    assert result["deviceInfo"]["locale"] == "en-US"
    assert result["pagination"]["limit"] == 9
    assert source["bundleName"] == "sample.bundle"
    assert "odid" not in source["content"]


def test_service_defaults_never_return_sensitive_keys(tmp_path: Path) -> None:
    config_path = (
        tmp_path / "debug_tools" / "end_to_end_debug" / "backend" / "debug_agent.yaml"
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "model:\n"
        "  openai_master_client: llmclient\n"
        "  model_max_concurrency: 12\n"
        "batch_testing:\n"
        "  concurrency: 3\n"
        "  request_timeout_seconds: 240\n"
        "  trace_root: custom/traces\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "WIDGET_SERVICE_OPENAI_MASTER_CLIENT=deepseek_official_http\n"
        "WIDGET_SERVICE_DEEPSEEK_OFFICIAL_HTTP_API_KEY=secret-value\n",
        encoding="utf-8",
    )

    result = load_service_defaults(tmp_path)
    batch_defaults = load_batch_defaults(tmp_path)

    assert result["values"]["openaiMasterClient"] == "deepseek_official_http"
    assert "modelMaxConcurrency" not in result["values"]
    assert batch_defaults["concurrency"] == 3
    assert batch_defaults["requestTimeoutSeconds"] == 240.0
    assert batch_defaults["traceRoot"] == "custom/traces"
    serialized = json.dumps(result)
    assert "API_KEY" not in serialized
    assert "secret-value" not in serialized


def test_task_definition_is_persisted_and_repeatable(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )

    task = manager.create_task(_task_payload("request_dataset"))
    first = manager.enqueue(task["taskId"])
    second = manager.enqueue(task["taskId"])

    assert first["runId"] != second["runId"]
    assert first["total"] == 1
    assert first["completed"] == 0
    assert manager.get_task(task["taskId"])["runCount"] == 2
    persisted = json.loads(
        (tmp_path / "output" / "tasks" / f"{task['taskId']}.json").read_text(encoding="utf-8")
    )
    assert persisted["requestOverrides"]["locale"] == "en-US"
    assert "enableDeviceCapture" not in persisted
    assert "latestRun" not in persisted

    persisted["enableDeviceCapture"] = True
    task_path = tmp_path / "output" / "tasks" / f"{task['taskId']}.json"
    task_path.write_text(json.dumps(persisted), encoding="utf-8")
    assert "enableDeviceCapture" not in manager.get_task(task["taskId"])
    assert "enableDeviceCapture" not in manager.copy_task(task["taskId"])


@pytest.mark.asyncio
async def test_continue_run_skips_success_and_respects_total_retry_limit(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    dataset = _write_dataset(datasets_root, "request_dataset", "Q001")
    (dataset / "Q002.json").write_text(
        json.dumps(_request("query-Q002"), ensure_ascii=False),
        encoding="utf-8",
    )
    invoked_interactions: list[str] = []

    async def invoke(_endpoint: str, payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
        session = payload.get("session")
        assert isinstance(session, dict)
        interaction_id = session.get("interactionId")
        assert isinstance(interaction_id, str)
        invoked_interactions.append(interaction_id)
        return {"status": "unsupported", "errorCode": "UNSUPPORTED", "data": {}}

    output_root = tmp_path / "output"
    run_manager = BatchRunManager(
        datasets_root,
        output_root,
        tmp_path / "traces",
        tmp_path / "cloud",
        invoke=invoke,
    )
    run_manager.trace_importer.is_terminal = lambda _uid: True  # type: ignore[method-assign]
    run_manager.trace_importer.import_trace = (  # type: ignore[method-assign]
        lambda _uid, _destination, _blob_root: {
            "status": "missing",
            "recordCount": 0,
            "sourceSchemaVersion": "",
            "summary": {"totalDurationMs": 0.0},
        }
    )
    run_id = "batch_resume_test"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True)
    summary = {
        "runId": run_id,
        "status": "cancelled",
        "concurrency": 2,
        "maxRetries": 1,
        "timeoutSeconds": 30.0,
        "taskId": "task_1",
        "datasetId": "request_dataset",
        "backendMode": "deployed",
        "samples": [
            {"id": "Q001", "sequence": 1, "status": "success", "attemptCount": 1},
            {"id": "Q002", "sequence": 2, "status": "cancelled", "attemptCount": 1},
        ],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    run_manager.continue_run(
        run_id,
        "ws://127.0.0.1:8855/api/v1/ws/tools",
        dataset_root=dataset,
        service_status="external",
        request_overrides={},
    )
    runner_task = run_manager.tasks.get(run_id)
    assert runner_task is not None
    await runner_task

    result = run_manager.get_run(run_id)
    samples = result.get("samples")
    assert isinstance(samples, list)
    assert len(samples) == 2
    assert invoked_interactions == ["Q002-001"]
    first_sample = samples[0]
    second_sample = samples[1]
    assert isinstance(first_sample, dict)
    assert isinstance(second_sample, dict)
    assert first_sample.get("status") == "success"
    assert first_sample.get("attemptCount") == 1
    assert second_sample.get("attemptCount") == 2

    result.update({"status": "cancelled"})
    second_sample["status"] = "cancelled"
    (run_dir / "summary.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="重试上限"):
        run_manager.continue_run(
            run_id,
            "ws://127.0.0.1:8855/api/v1/ws/tools",
            dataset_root=dataset,
            service_status="external",
            request_overrides={},
        )


@pytest.mark.asyncio
async def test_continue_never_started_run_requeues_all_samples(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )
    task = manager.create_task(_task_payload("request_dataset"))
    execution = manager.enqueue(str(task.get("taskId")))
    run_id = execution.get("runId")
    assert isinstance(run_id, str)

    stopped = await manager.stop_run(run_id)
    continued = manager.continue_run(run_id)

    assert stopped.get("status") == "cancelled"
    assert continued.get("status") == "queued"
    assert continued.get("continueRun") is False
    queue = manager.scheduler_state().get("queue")
    assert isinstance(queue, list)
    assert len(queue) == 1
    queued_run = queue[0]
    assert isinstance(queued_run, dict)
    assert queued_run.get("runId") == run_id


def test_delete_task_removes_definition_executions_and_run_files(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    output_root = tmp_path / "output"
    manager = BatchTaskManager(
        datasets_root,
        output_root,
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )
    task = manager.create_task(_task_payload("request_dataset"))
    task_id = str(task.get("taskId"))
    execution = manager.enqueue(task_id)
    run_id = str(execution.get("runId"))
    manager.queue.remove(run_id)
    execution["status"] = "completed"
    manager._write_execution(execution)
    manager._persist_scheduler()
    run_dir = output_root / run_id
    run_dir.mkdir()
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")

    manager.delete_task(task_id)

    assert not (output_root / "tasks" / f"{task_id}.json").exists()
    assert not (output_root / "executions" / f"{run_id}.json").exists()
    assert not run_dir.exists()
    with pytest.raises(KeyError):
        manager.get_task(task_id)


def test_delete_task_rejects_queued_execution(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )
    task = manager.create_task(_task_payload("request_dataset"))
    task_id = str(task.get("taskId"))
    manager.enqueue(task_id)

    with pytest.raises(RuntimeError, match="正在排队或运行"):
        manager.delete_task(task_id)

    assert manager.get_task(task_id).get("taskId") == task_id


def test_create_and_enqueue_adds_first_execution_after_existing_queue(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )

    first = manager.create_and_enqueue(_task_payload("request_dataset"))
    second = manager.create_and_enqueue(_task_payload("request_dataset"))
    first_latest = first.get("latestRun")
    second_latest = second.get("latestRun")

    assert first.get("runCount") == 1
    assert isinstance(first_latest, dict)
    assert first_latest.get("status") == "queued"
    assert first_latest.get("queuePosition") == 1
    assert second.get("runCount") == 1
    assert isinstance(second_latest, dict)
    assert second_latest.get("status") == "queued"
    assert second_latest.get("queuePosition") == 2
    queue = manager.scheduler_state().get("queue")
    assert isinstance(queue, list)
    assert [item.get("taskId") for item in queue if isinstance(item, dict)] == [
        first.get("taskId"),
        second.get("taskId"),
    ]
@pytest.mark.asyncio
async def test_scheduler_runs_only_one_execution_and_advances_queue(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    active = 0
    maximum_active = 0

    async def invoke(_endpoint: str, _payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return {"status": "unsupported", "errorCode": "UNSUPPORTED", "data": {}}

    run_manager = BatchRunManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        invoke=invoke,
    )
    run_manager.trace_importer.is_terminal = lambda _uid: True  # type: ignore[method-assign]
    run_manager.trace_importer.import_trace = (  # type: ignore[method-assign]
        lambda _uid, _destination, _blob_root: {
            "status": "missing",
            "recordCount": 0,
            "sourceSchemaVersion": "",
            "summary": {"totalDurationMs": 0.0},
        }
    )
    controller = FakeServiceController()
    gallery = FakeGalleryManager()
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        run_manager=run_manager,
        service_controller=controller,  # type: ignore[arg-type]
        gallery_manager=gallery,  # type: ignore[arg-type]
    )
    task = manager.create_task(_task_payload("request_dataset"))
    first = manager.enqueue(task["taskId"])
    second = manager.enqueue(task["taskId"])

    await manager.start()
    for _ in range(100):
        state = manager.scheduler_state()
        if state["activeRunId"] is None and not state["queue"]:
            break
        await asyncio.sleep(0.01)
    await manager.close()

    assert maximum_active == 1
    assert manager.get_run(first["runId"])["status"] == "completed"
    assert manager.get_run(second["runId"])["status"] == "completed"
    task_view = manager.get_task(task["taskId"])
    assert task_view["latestRun"]["completed"] == 1
    assert task_view["latestRun"]["success"] == 0
    assert task_view["latestRun"]["failed"] == 1
    assert gallery.started == []
    assert controller.stop_count >= 1


@pytest.mark.asyncio
async def test_postprocessing_only_starts_after_manual_request(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")

    async def invoke(_endpoint: str, _payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
        return {"status": "unsupported", "errorCode": "UNSUPPORTED", "data": {}}

    run_manager = BatchRunManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        invoke=invoke,
    )
    run_manager.trace_importer.is_terminal = lambda _uid: True  # type: ignore[method-assign]
    run_manager.trace_importer.import_trace = (  # type: ignore[method-assign]
        lambda _uid, _destination, _blob_root: {
            "status": "missing",
            "recordCount": 0,
            "sourceSchemaVersion": "",
            "summary": {"totalDurationMs": 0.0},
        }
    )
    capture = FakeDeviceCaptureManager()
    gallery = FakeGalleryManager()
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        run_manager=run_manager,
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
        gallery_manager=gallery,  # type: ignore[arg-type]
        device_capture_manager=capture,  # type: ignore[arg-type]
    )
    task = manager.create_task(_task_payload("request_dataset"))
    first = manager.enqueue(str(task.get("taskId")))
    second = manager.enqueue(str(task.get("taskId")))

    await manager.start()
    for _ in range(100):
        scheduler = manager.scheduler_state()
        if scheduler.get("activeRunId") is None and not scheduler.get("queue"):
            break
        await asyncio.sleep(0.01)
    first_run_id = first.get("runId")
    second_run_id = second.get("runId")
    assert isinstance(first_run_id, str)
    assert isinstance(second_run_id, str)
    assert manager.get_run(first_run_id).get("status") == "completed"
    assert manager.get_run(second_run_id).get("status") == "completed"
    assert capture.enqueued == []
    assert gallery.started == []

    postprocess_result = manager.postprocess_manager.enqueue(
        first_run_id,
        ["browser-gallery", "device-gallery"],
    )
    await manager.postprocess_manager.queue.join()

    assert postprocess_result.get("status") == "queued"
    assert gallery.started == [first_run_id]
    assert capture.enqueued == [first_run_id]
    await manager.close()


def test_restart_marks_active_interrupted_and_pauses_remaining_queue(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    output_root = tmp_path / "output"
    manager = BatchTaskManager(
        datasets_root,
        output_root,
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )
    task = manager.create_task(_task_payload("request_dataset"))
    first = manager.enqueue(task["taskId"])
    second = manager.enqueue(task["taskId"])
    atomic_state = {
        "paused": False,
        "activeRunId": first["runId"],
        "queue": [second["runId"]],
    }
    (output_root / "scheduler.json").write_text(json.dumps(atomic_state), encoding="utf-8")

    restarted = BatchTaskManager(
        datasets_root,
        output_root,
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )

    assert restarted.scheduler_state()["paused"] is True
    assert restarted.scheduler_state()["queue"][0]["runId"] == second["runId"]
    assert restarted.get_run(first["runId"])["status"] == "interrupted"


def test_task_api_exposes_datasets_tasks_copy_and_scheduler(tmp_path: Path) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    capture = FakeDeviceCaptureManager()
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
        device_capture_manager=capture,  # type: ignore[arg-type]
    )
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    client = TestClient(app)

    datasets = client.get("/debug/batch/datasets")
    samples = client.get("/debug/batch/datasets/request_dataset/samples")
    created = client.post("/debug/batch/tasks", json=_task_payload("request_dataset"))
    obsolete_payload = _task_payload("request_dataset")
    obsolete_payload["enableDeviceCapture"] = True
    obsolete = client.post("/debug/batch/tasks", json=obsolete_payload)
    task_id = created.json()["taskId"]
    copied = client.post(f"/debug/batch/tasks/{task_id}/copy")
    queued = client.post(f"/debug/batch/tasks/{task_id}/runs")
    scheduler = client.get("/debug/batch/scheduler")
    capture_config = client.get("/debug/batch/device-capture/config")
    run_id = str(created.json().get("latestRun", {}).get("runId") or "")
    plugins = client.get("/debug/batch/postprocess/plugins")
    postprocess = client.post(
        f"/debug/batch/runs/{run_id}/postprocess",
        json={"pluginIds": ["browser-gallery", "device-gallery"], "configs": {}},
    )
    old_gallery = client.post(f"/debug/batch/runs/{run_id}/gallery")
    old_device_capture = client.post(f"/debug/batch/runs/{run_id}/device-capture")

    assert datasets.status_code == 200
    assert samples.json()["items"][0]["id"] == "Q001"
    assert created.status_code == 201
    assert obsolete.status_code == 422
    created_body = created.json()
    created_latest = created_body.get("latestRun")
    assert created_body.get("runCount") == 1
    assert isinstance(created_latest, dict)
    assert created_latest.get("status") == "queued"
    assert copied.status_code == 201
    assert copied.json()["taskId"] != task_id
    assert copied.json().get("runCount") == 0
    assert queued.status_code == 202
    assert scheduler.json()["queue"][0]["taskId"] == task_id
    assert len(scheduler.json()["queue"]) == 2
    assert capture_config.status_code == 200
    assert capture_config.json().get("available") is True
    plugin_ids = {item.get("id") for item in plugins.json().get("items", [])}
    assert {"browser-gallery", "device-gallery"}.issubset(plugin_ids)
    assert postprocess.status_code == 202
    assert postprocess.json().get("status") == "waiting"
    assert old_gallery.status_code == 404
    assert old_device_capture.status_code == 404

    deletable = client.post("/debug/batch/tasks", json=_task_payload("request_dataset"))
    deletable_id = deletable.json().get("taskId")
    deletable_run = deletable.json().get("latestRun")
    assert isinstance(deletable_id, str)
    assert isinstance(deletable_run, dict)
    deletable_run_id = deletable_run.get("runId")
    assert isinstance(deletable_run_id, str)
    manager.queue.remove(deletable_run_id)
    deletable_run["status"] = "cancelled"
    manager._write_execution(deletable_run)
    manager._persist_scheduler()
    deleted = client.delete(f"/debug/batch/tasks/{deletable_id}")
    missing = client.get(f"/debug/batch/tasks/{deletable_id}")

    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_connection_api_reports_status_and_starts_managed_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    datasets_root = tmp_path / "Datasets"
    _write_dataset(datasets_root, "request_dataset")
    manager = BatchTaskManager(
        datasets_root,
        tmp_path / "output",
        tmp_path / "traces",
        tmp_path / "cloud",
        service_controller=FakeServiceController(),  # type: ignore[arg-type]
    )

    async def fake_probe(_url: str) -> tuple[bool, str]:
        return True, "health ok"

    monkeypatch.setattr("debug_tools.batch_testing.api.probe_service_health", fake_probe)
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    client = TestClient(app)

    status = client.post(
        "/debug/batch/connections/status",
        json={"toolWsBaseUrl": "ws://service.example/api/v1/ws/tools"},
    )
    started = client.post(
        "/debug/batch/connections/managed/start",
        json={"serviceConfig": {"enableA2uiModelMock": True}},
    )

    assert status.status_code == 200
    assert status.json()["mainAgent"]["available"] is True
    assert status.json()["deployedService"]["available"] is True
    assert started.status_code == 200
    assert started.json()["deployedService"]["detail"] == "health ok"


def test_managed_service_selects_an_available_loopback_port(tmp_path: Path) -> None:
    import socket

    project_root = tmp_path / "widget_service"
    project_root.mkdir()
    controller = ManagedServiceController(project_root, tmp_path / "output")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        occupied_port = listener.getsockname()[1]
        selected_port = controller._find_available_port()

    assert selected_port != occupied_port
    assert 1 <= selected_port <= 65535
    assert controller.service is None


@pytest.mark.asyncio
async def test_managed_service_injects_the_selected_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "widget_service"
    start_script = project_root / "cloud" / "start_websocket_server.py"
    start_script.parent.mkdir(parents=True)
    start_script.write_text("", encoding="utf-8")
    captured_environment: dict[str, str] = {}

    class FakeAsyncProcess:
        pid = 4321
        returncode = None

        def terminate(self) -> None:
            self.returncode = 0

        async def wait(self) -> int:
            return 0

    class FakePsutilProcess:
        @staticmethod
        def create_time() -> float:
            return 123.0

    async def create_process(*_command: str, **options: Any) -> FakeAsyncProcess:
        captured_environment.update(options.get("env", {}))
        return FakeAsyncProcess()

    async def ready(_port: int, _timeout: float) -> None:
        return None

    monkeypatch.setattr(service_manager.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(service_manager.psutil, "Process", lambda _pid: FakePsutilProcess())
    controller = ManagedServiceController(project_root, tmp_path / "output")
    monkeypatch.setattr(controller, "_find_available_port", lambda: 43123)
    monkeypatch.setattr(controller, "_wait_until_ready", ready)

    endpoint = await controller.ensure({})

    assert endpoint == "ws://127.0.0.1:43123/api/v1/ws/tools"
    assert captured_environment["WIDGET_SERVICE_SERVER_PORT"] == "43123"
    assert controller.service is not None
    assert controller.service.port == 43123
