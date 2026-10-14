"""批量测试任务定义、持久化队列与单任务调度。"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

from ..postprocess_plugins.device_capture import DeviceCaptureManager
from ..postprocess_plugins.device_capture import run_builtin as run_device_capture_plugin
from ..postprocess_plugins.gallery import BatchGalleryManager
from ..postprocess_plugins.gallery import run_builtin as run_gallery_plugin
from ..postprocess_plugins.validation_failure_gallery import (
    ValidationFailureGalleryManager,
)
from ..postprocess_plugins.validation_failure_gallery import (
    run_builtin as run_validation_failure_gallery_plugin,
)
from .postprocess import PostprocessManager
from .runner import BatchRunManager, atomic_write_json, discover_datasets, utc_now
from .service_manager import (
    ManagedServiceController,
    load_batch_defaults,
    load_service_defaults,
    validate_service_config,
)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_TERMINAL_STATUSES = {"completed", "cancelled", "failed", "interrupted"}


class BatchTaskManager:
    """持久化任务并确保任意时刻只运行一个批量测试执行。"""

    def __init__(
        self,
        datasets_root: Path,
        output_root: Path,
        trace_root: Path,
        cloud_root: Path,
        *,
        run_manager: BatchRunManager | None = None,
        service_controller: ManagedServiceController | None = None,
        gallery_manager: BatchGalleryManager | None = None,
        validation_failure_gallery_manager: ValidationFailureGalleryManager | None = None,
        device_capture_manager: DeviceCaptureManager | None = None,
        postprocess_manager: PostprocessManager | None = None,
        gallery_base_url: str = "http://127.0.0.1:8888/debug",
    ) -> None:
        self.datasets_root = datasets_root.resolve()
        self.output_root = output_root.resolve()
        self.project_root = cloud_root.parent.resolve()
        self.batch_defaults = load_batch_defaults(self.project_root)
        self.tasks_root = self.output_root / "tasks"
        self.executions_root = self.output_root / "executions"
        self.scheduler_path = self.output_root / "scheduler.json"
        self.run_manager = run_manager or BatchRunManager(
            self.datasets_root,
            self.output_root,
            trace_root,
            cloud_root,
        )
        self.service_controller = service_controller or ManagedServiceController(
            self.project_root,
            self.output_root,
        )
        self.gallery_manager = gallery_manager or BatchGalleryManager(
            self.output_root,
            gallery_base_url,
        )
        self.validation_failure_gallery_manager = (
            validation_failure_gallery_manager
            or ValidationFailureGalleryManager(self.output_root, gallery_base_url)
        )
        self.device_capture_manager = device_capture_manager or DeviceCaptureManager(
            self.output_root,
        )
        plugins_root = Path(__file__).resolve().parents[1] / "postprocess_plugins"
        self.postprocess_manager = postprocess_manager or PostprocessManager(
            self.output_root,
            plugins_root,
            builtin_runners={
                "browser-gallery": partial(run_gallery_plugin, self.gallery_manager),
                "validation-failure-gallery": partial(
                    run_validation_failure_gallery_plugin,
                    self.validation_failure_gallery_manager,
                ),
                "device-gallery": partial(
                    run_device_capture_plugin,
                    self.device_capture_manager,
                ),
            },
        )
        self.queue: list[str] = []
        self.active_run_id: str | None = None
        self.paused = False
        self._wake = asyncio.Event()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._closing = False
        self._load_scheduler_state()

    async def start(self) -> None:
        await self.service_controller.recover_orphan()
        await self.device_capture_manager.start()
        await self.postprocess_manager.start()
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def close(self) -> None:
        self._closing = True
        self._wake.set()
        if self.active_run_id is not None:
            try:
                await self.run_manager.cancel_run(self.active_run_id)
            except KeyError:
                pass
        if self._scheduler_task is not None:
            await self._scheduler_task
        await self.postprocess_manager.close()
        await self.device_capture_manager.close()
        await self.gallery_manager.close()
        await self.service_controller.stop()

    def list_datasets(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if not self.datasets_root.is_dir():
            return items
        for path in sorted(self.datasets_root.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_dir() or not _IDENTIFIER_PATTERN.fullmatch(path.name):
                continue
            samples = discover_datasets(path)
            items.append(
                {
                    "id": path.name,
                    "name": path.name,
                    "sampleCount": len(samples),
                    "validSampleCount": sum(1 for sample in samples if sample.valid),
                    "invalidSampleCount": sum(1 for sample in samples if not sample.valid),
                }
            )
        return items

    def dataset_samples(self, dataset_id: str) -> list[dict[str, Any]]:
        path = self._dataset_path(dataset_id)
        return [item.public_dict() for item in discover_datasets(path)]

    def service_defaults(self) -> dict[str, Any]:
        return load_service_defaults(self.project_root)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        dataset_id = str(payload.get("datasetId") or "")
        dataset_path = self._dataset_path(dataset_id)
        available = {item.sample_id: item for item in discover_datasets(dataset_path)}
        sample_ids = self._validate_sample_ids(payload.get("sampleIds"), available)
        name = str(payload.get("name") or "").strip()
        if not name:
            name = f"{dataset_id} · {datetime.now().strftime('%m-%d %H:%M')}"
        if len(name) > 120:
            raise ValueError("任务名称不能超过 120 个字符")
        backend_mode = str(payload.get("backendMode") or "deployed")
        if backend_mode not in {"deployed", "managed"}:
            raise ValueError("后端模式必须是 deployed 或 managed")
        deployed_url = str(payload.get("toolWsBaseUrl") or "").strip()
        service_config: dict[str, Any] = {}
        if backend_mode == "deployed":
            from .runner import normalize_endpoint

            normalize_endpoint(deployed_url)
        else:
            raw_config = payload.get("serviceConfig")
            if not isinstance(raw_config, dict):
                raw_config = {}
            service_config = validate_service_config(raw_config, self.project_root)
            deployed_url = ""
        request_overrides = self._validate_request_overrides(payload.get("requestOverrides"))
        concurrency = int(self.batch_defaults.get("concurrency", 4))
        max_retries = int(self.batch_defaults.get("maxRetries", 1))
        timeout_seconds = float(self.batch_defaults.get("requestTimeoutSeconds", 300.0))
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        task = {
            "taskId": task_id,
            "name": name,
            "datasetId": dataset_id,
            "sampleIds": sample_ids,
            "sampleCount": len(sample_ids),
            "requestOverrides": request_overrides,
            "concurrency": concurrency,
            "maxRetries": max_retries,
            "timeoutSeconds": timeout_seconds,
            "backendMode": backend_mode,
            "toolWsBaseUrl": deployed_url,
            "serviceConfig": service_config,
            "createdAt": now,
            "updatedAt": now,
        }
        self.tasks_root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.tasks_root / f"{task_id}.json", task)
        return self._task_public(task)

    def create_and_enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.create_task(payload)
        task_id = task.get("taskId")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError("新建批量测试任务缺少任务标识")
        self.enqueue(task_id)
        return self.get_task(task_id)

    def copy_task(self, task_id: str) -> dict[str, Any]:
        source = self._read_task(task_id)
        copied = dict(source)
        copied.pop("taskId", None)
        copied.pop("createdAt", None)
        copied.pop("updatedAt", None)
        copied.pop("enableDeviceCapture", None)
        copied["name"] = f"{source.get('name', task_id)}（副本）"
        return self.create_task(copied)

    def list_tasks(self) -> list[dict[str, Any]]:
        tasks = [self._task_public(task) for task in self._all_tasks()]
        return sorted(tasks, key=lambda item: str(item.get("updatedAt", "")), reverse=True)

    def get_task(self, task_id: str) -> dict[str, Any]:
        task = self._task_public(self._read_task(task_id))
        task["runs"] = self._task_runs(task_id)
        return task

    def delete_task(self, task_id: str) -> None:
        self._read_task(task_id)
        executions = self._task_execution_records(task_id)
        active_statuses = {"queued", "preparing", "running", "stopping"}
        if any(str(item.get("status") or "") in active_statuses for item in executions):
            raise RuntimeError("任务正在排队或运行，无法删除")
        for execution in executions:
            run_id = str(execution.get("runId") or "")
            if self._has_active_postprocess(run_id):
                raise RuntimeError("任务仍在执行后处理，无法删除")

        for execution in executions:
            run_id = str(execution.get("runId") or "")
            if not _IDENTIFIER_PATTERN.fullmatch(run_id):
                continue
            run_dir = (self.output_root / run_id).resolve()
            if run_dir.is_relative_to(self.output_root) and run_dir.is_dir():
                shutil.rmtree(run_dir)
            execution_path = self.executions_root / f"{run_id}.json"
            execution_path.unlink(missing_ok=True)
            self.run_manager.runs.pop(run_id, None)
            self.run_manager.tasks.pop(run_id, None)

        task_path = self.tasks_root / f"{task_id}.json"
        task_path.unlink()

    def legacy_runs(self) -> list[dict[str, Any]]:
        return [run for run in self.run_manager.list_runs() if not run.get("taskId")]

    def enqueue(self, task_id: str) -> dict[str, Any]:
        task = self._read_task(task_id)
        run_token = uuid.uuid4().hex[:8]
        run_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_token}"
        execution = {
            "runId": run_id,
            "taskId": task_id,
            "status": "queued",
            "createdAt": utc_now(),
            "startedAt": None,
            "finishedAt": None,
            "queuePosition": len(self.queue) + 1,
            "backendMode": task.get("backendMode"),
            "serviceStatus": "pending",
            "total": int(task.get("sampleCount", len(task.get("sampleIds") or []))),
            "completed": 0,
            "success": 0,
            "degraded": 0,
            "failed": 0,
            "cancelled": 0,
        }
        self.executions_root.mkdir(parents=True, exist_ok=True)
        self._write_execution(execution)
        self.queue.append(run_id)
        self._touch_task(task)
        self._persist_scheduler()
        self._wake.set()
        return execution

    def continue_run(self, run_id: str) -> dict[str, Any]:
        execution = self._read_execution(run_id)
        if str(execution.get("status") or "") not in {"cancelled", "interrupted"}:
            raise ValueError("只有已停止或已中断的任务可以继续执行")
        if run_id in self.queue or run_id == self.active_run_id:
            raise RuntimeError("任务已在队列中或正在执行")
        run = self.get_run(run_id)
        max_retries = int(run.get("maxRetries", 0))
        samples = run.get("samples")
        has_started = isinstance(samples, list)
        resumable = not has_started
        if isinstance(samples, list):
            for sample in samples:
                if not isinstance(sample, dict):
                    continue
                status = str(sample.get("status") or "")
                attempt_count = int(sample.get("attemptCount") or 0)
                if status in {"queued", "running", "cancelled"} and attempt_count <= max_retries:
                    resumable = True
                    break
        if not resumable:
            raise ValueError("没有未执行或中断且仍在重试上限内的样本")
        execution["status"] = "queued"
        execution["finishedAt"] = None
        execution["queuePosition"] = len(self.queue) + 1
        execution["continueRun"] = has_started
        self._write_execution(execution)
        self.queue.append(run_id)
        self._persist_scheduler()
        self._wake.set()
        return execution

    async def stop_run(self, run_id: str) -> dict[str, Any]:
        execution = self._read_execution(run_id)
        if run_id in self.queue:
            self.queue.remove(run_id)
            execution["status"] = "cancelled"
            execution["finishedAt"] = utc_now()
            execution["queuePosition"] = None
            self._write_execution(execution)
            self._persist_scheduler()
            return execution
        if run_id == self.active_run_id:
            execution["status"] = "stopping"
            self._write_execution(execution)
            await self.run_manager.cancel_run(run_id)
            return execution
        return execution

    def scheduler_state(self) -> dict[str, Any]:
        queued: list[dict[str, Any]] = []
        for position, run_id in enumerate(self.queue, start=1):
            try:
                execution = self._read_execution(run_id)
            except KeyError:
                continue
            execution["queuePosition"] = position
            queued.append(execution)
        active = None
        if self.active_run_id:
            try:
                active = self._execution_public(self.active_run_id)
            except KeyError:
                active = None
        return {
            "paused": self.paused,
            "activeRunId": self.active_run_id,
            "active": active,
            "queue": queued,
        }

    def resume(self) -> dict[str, Any]:
        self.paused = False
        self._persist_scheduler()
        self._wake.set()
        return self.scheduler_state()

    def get_run(self, run_id: str) -> dict[str, Any]:
        try:
            run = self.run_manager.get_run(run_id)
        except KeyError:
            return self._execution_public(run_id)
        execution = self._read_execution_optional(run_id)
        if execution:
            run.update(
                {
                    "status": execution.get("status", run.get("status")),
                    "queuePosition": execution.get("queuePosition"),
                    "backendMode": execution.get("backendMode", run.get("backendMode")),
                    "serviceStatus": execution.get("serviceStatus", run.get("serviceStatus")),
                    "interrupted": execution.get("status") == "interrupted",
                }
            )
        run["gallery"] = self.gallery_manager.status(run_id)
        run["deviceCapture"] = self.device_capture_manager.status(run_id)
        run["postprocessExecutions"] = self.postprocess_manager.executions(run_id)
        return run

    def gallery_path(self, run_id: str) -> Path:
        return self.gallery_manager.gallery_path(run_id)

    def validation_failure_items(self, run_id: str) -> list[dict[str, Any]]:
        return self.validation_failure_gallery_manager.items(run_id)

    def device_capture_path(self, run_id: str, sample_id: str, kind: str) -> Path:
        return self.device_capture_manager.image_path(run_id, sample_id, kind)

    def device_gallery_path(self, run_id: str) -> Path:
        return self.device_capture_manager.gallery_path(run_id)

    def sample_device_capture(self, run_id: str, sample_id: str) -> dict[str, Any]:
        return self.device_capture_manager.sample(run_id, sample_id)

    async def _scheduler_loop(self) -> None:
        while not self._closing:
            if self.paused or self.active_run_id is not None or not self.queue:
                self._wake.clear()
                await self._wake.wait()
                continue
            run_id = self.queue.pop(0)
            self.active_run_id = run_id
            self._persist_scheduler()
            await self._execute_queued(run_id)
            self.active_run_id = None
            self._persist_scheduler()
            if not self.queue:
                await self.service_controller.stop()
        await self.service_controller.stop()

    async def _execute_queued(self, run_id: str) -> None:
        execution = self._read_execution(run_id)
        task_id = str(execution.get("taskId") or "")
        try:
            task = self._read_task(task_id)
            execution.update(
                {
                    "status": "preparing",
                    "startedAt": utc_now(),
                    "queuePosition": None,
                    "serviceStatus": "starting",
                }
            )
            self._write_execution(execution)
            backend_mode = str(task.get("backendMode") or "deployed")
            if backend_mode == "managed":
                raw_config = task.get("serviceConfig")
                service_config = raw_config if isinstance(raw_config, dict) else {}
                endpoint = await self.service_controller.ensure(service_config)
                service_status = "managed_running"
            else:
                await self.service_controller.stop()
                endpoint = str(task.get("toolWsBaseUrl") or "")
                service_status = "external"
            execution["serviceStatus"] = service_status
            service_log_path = getattr(self.service_controller, "last_log_path", None)
            if service_log_path is not None:
                execution["serviceLogPath"] = str(service_log_path)
            execution["status"] = "running"
            self._write_execution(execution)
            dataset_root = self._dataset_path(str(task.get("datasetId") or ""))
            if execution.get("continueRun"):
                self.run_manager.continue_run(
                    run_id,
                    endpoint,
                    dataset_root=dataset_root,
                    service_status=service_status,
                    request_overrides=dict(task.get("requestOverrides") or {}),
                )
            else:
                self.run_manager.start_run(
                    list(task.get("sampleIds") or []),
                    endpoint,
                    int(task.get("concurrency", 4)),
                    int(task.get("maxRetries", 1)),
                    task_id=task_id,
                    dataset_id=str(task.get("datasetId") or ""),
                    dataset_root=dataset_root,
                    request_overrides=dict(task.get("requestOverrides") or {}),
                    timeout_seconds=float(task.get("timeoutSeconds", 300.0)),
                    backend_mode=backend_mode,
                    service_status=service_status,
                    run_id=run_id,
                )
            runner_task = self.run_manager.tasks.get(run_id)
            if runner_task is None:
                raise RuntimeError("批量测试执行器未创建后台任务")
            await runner_task
            summary = self.run_manager.get_run(run_id)
            execution["status"] = str(summary.get("status") or "completed")
            execution["finishedAt"] = summary.get("finishedAt") or utc_now()
            for field_name in (
                "total",
                "completed",
                "success",
                "degraded",
                "failed",
                "cancelled",
                "averageElapsedMs",
                "traceWarnings",
            ):
                execution[field_name] = summary.get(field_name, execution.get(field_name))
            execution["summary"] = summary
            execution["continueRun"] = False
            if execution["status"] == "completed":
                self.postprocess_manager.activate_waiting(run_id)
        except asyncio.CancelledError:
            execution["status"] = "interrupted"
            execution["finishedAt"] = utc_now()
            execution["error"] = "调试后端关闭导致执行中断"
        except Exception as exc:
            execution["status"] = "failed"
            execution["finishedAt"] = utc_now()
            execution["serviceStatus"] = "failed"
            execution["error"] = f"{type(exc).__name__}: {exc}"
            service_log_path = getattr(self.service_controller, "last_log_path", None)
            if service_log_path is not None:
                execution["serviceLogPath"] = str(service_log_path)
        self._write_execution(execution)

    def _load_scheduler_state(self) -> None:
        if not self.scheduler_path.is_file():
            return
        try:
            value = json.loads(self.scheduler_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        raw_queue = value.get("queue") if isinstance(value, dict) else None
        if isinstance(raw_queue, list):
            self.queue = [str(item) for item in raw_queue if isinstance(item, str)]
        active_run_id = value.get("activeRunId") if isinstance(value, dict) else None
        if isinstance(active_run_id, str) and active_run_id:
            execution = self._read_execution_optional(active_run_id)
            if execution:
                execution["status"] = "interrupted"
                execution["finishedAt"] = utc_now()
                execution["error"] = "调试后端重启导致执行中断"
                self._write_execution(execution)
                self._mark_persisted_run_interrupted(active_run_id)
        self.active_run_id = None
        self.paused = bool(self.queue)
        self._persist_scheduler()

    def _persist_scheduler(self) -> None:
        for position, run_id in enumerate(self.queue, start=1):
            execution = self._read_execution_optional(run_id)
            if execution:
                execution["queuePosition"] = position
                self._write_execution(execution)
        atomic_write_json(
            self.scheduler_path,
            {
                "paused": self.paused,
                "activeRunId": self.active_run_id,
                "queue": self.queue,
                "updatedAt": utc_now(),
            },
        )

    def _task_public(self, task: dict[str, Any]) -> dict[str, Any]:
        result = dict(task)
        result.pop("enableDeviceCapture", None)
        runs = self._task_runs(str(task.get("taskId") or ""))
        latest = runs[0] if runs else None
        result["latestRun"] = latest
        result["runCount"] = len(runs)
        return result

    def _task_runs(self, task_id: str) -> list[dict[str, Any]]:
        runs = [
            self._execution_public(str(execution.get("runId") or ""))
            for execution in self._task_execution_records(task_id)
        ]
        return sorted(runs, key=lambda item: str(item.get("createdAt", "")), reverse=True)

    def _task_execution_records(self, task_id: str) -> list[dict[str, Any]]:
        executions: list[dict[str, Any]] = []
        if self.executions_root.is_dir():
            for path in self.executions_root.glob("*.json"):
                try:
                    execution = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(execution, dict) and execution.get("taskId") == task_id:
                    executions.append(execution)
        return executions

    def _has_active_postprocess(self, run_id: str) -> bool:
        if not run_id:
            return False
        return any(
            str(item.get("status") or "") in {"queued", "running"}
            for item in self.postprocess_manager.executions(run_id)
        )

    def _execution_public(self, run_id: str) -> dict[str, Any]:
        execution = self._read_execution(run_id)
        try:
            summary = self.run_manager.get_run(run_id)
        except KeyError:
            summary = execution.get("summary")
        if isinstance(summary, dict):
            merged = {**execution, **summary}
            for field_name in (
                "status",
                "createdAt",
                "queuePosition",
                "backendMode",
                "serviceStatus",
                "serviceLogPath",
                "error",
            ):
                if field_name in execution:
                    merged[field_name] = execution.get(field_name)
            merged["gallery"] = self.gallery_manager.status(run_id)
            merged["deviceCapture"] = self.device_capture_manager.status(run_id)
            merged["postprocessExecutions"] = self.postprocess_manager.executions(run_id)
            return merged
        execution["gallery"] = self.gallery_manager.status(run_id)
        execution["deviceCapture"] = self.device_capture_manager.status(run_id)
        execution["postprocessExecutions"] = self.postprocess_manager.executions(run_id)
        return execution

    def _mark_persisted_run_interrupted(self, run_id: str) -> None:
        run_dir = self.output_root / run_id
        for name in ("manifest.json", "summary.json"):
            path = run_dir / name
            if not path.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            value["status"] = "interrupted"
            value["finishedAt"] = utc_now()
            value["interrupted"] = True
            atomic_write_json(path, value)

    def _all_tasks(self) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        if not self.tasks_root.is_dir():
            return tasks
        for path in self.tasks_root.glob("task_*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                tasks.append(value)
        return tasks

    def _read_task(self, task_id: str) -> dict[str, Any]:
        if not _IDENTIFIER_PATTERN.fullmatch(task_id):
            raise KeyError(task_id)
        path = self.tasks_root / f"{task_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError(task_id) from exc
        if not isinstance(value, dict):
            raise KeyError(task_id)
        return value

    def _touch_task(self, task: dict[str, Any]) -> None:
        task["updatedAt"] = utc_now()
        atomic_write_json(self.tasks_root / f"{task['taskId']}.json", task)

    def _write_execution(self, execution: dict[str, Any]) -> None:
        self.executions_root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.executions_root / f"{execution['runId']}.json", execution)

    def _read_execution(self, run_id: str) -> dict[str, Any]:
        value = self._read_execution_optional(run_id)
        if value is None:
            raise KeyError(run_id)
        return value

    def _read_execution_optional(self, run_id: str) -> dict[str, Any] | None:
        if not _IDENTIFIER_PATTERN.fullmatch(run_id):
            return None
        path = self.executions_root / f"{run_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _dataset_path(self, dataset_id: str) -> Path:
        if not _IDENTIFIER_PATTERN.fullmatch(dataset_id):
            raise KeyError(dataset_id)
        path = (self.datasets_root / dataset_id).resolve()
        try:
            path.relative_to(self.datasets_root)
        except ValueError as exc:
            raise KeyError(dataset_id) from exc
        if not path.is_dir():
            raise KeyError(dataset_id)
        return path

    @staticmethod
    def _validate_sample_ids(
        raw_sample_ids: object,
        available: dict[str, Any],
    ) -> list[str]:
        if not isinstance(raw_sample_ids, list):
            raise ValueError("sampleIds 必须是数组")
        result: list[str] = []
        seen: set[str] = set()
        for raw_sample_id in raw_sample_ids:
            sample_id = str(raw_sample_id)
            if sample_id in seen:
                continue
            seen.add(sample_id)
            item = available.get(sample_id)
            if item is None or not _IDENTIFIER_PATTERN.fullmatch(sample_id):
                raise ValueError(f"未知数据样本: {sample_id}")
            if not item.valid:
                raise ValueError(f"数据样本无效: {sample_id}: {item.error}")
            result.append(sample_id)
        if not result:
            raise ValueError("至少选择一个有效数据样本")
        return result

    @staticmethod
    def _validate_request_overrides(raw_value: object) -> dict[str, Any]:
        if raw_value is None:
            return {}
        if not isinstance(raw_value, dict):
            raise ValueError("requestOverrides 必须是对象")
        allowed = {
            "protocolVersion",
            "bundleName",
            "deviceId",
            "phoneType",
            "appVersion",
            "romVersion",
            "locale",
            "countryCode",
            "deviceFormation",
            "deviceType",
            "sysVer",
            "paginationLimit",
            "paginationStart",
        }
        unknown = sorted(set(raw_value).difference(allowed))
        if unknown:
            raise ValueError(f"包含不支持的公共请求字段: {', '.join(unknown)}")
        result: dict[str, Any] = {}
        for key, value in raw_value.items():
            if value is None or value == "":
                continue
            if key in {"deviceType", "paginationLimit"}:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"{key} 必须是整数")
                if key == "paginationLimit" and value < 1:
                    raise ValueError("paginationLimit 必须大于 0")
            elif not isinstance(value, str):
                raise ValueError(f"{key} 必须是字符串")
            result[key] = value
        return result
