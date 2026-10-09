"""批量测试任务中心 REST API。"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .runner import BatchRunManager
from .service_manager import load_batch_defaults, probe_service_health
from .task_manager import BatchTaskManager


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=120)
    datasetId: str = Field(min_length=1, max_length=80)
    sampleIds: list[str] = Field(min_length=1)
    requestOverrides: dict[str, Any] = Field(default_factory=dict)
    backendMode: str = Field(default="deployed")
    toolWsBaseUrl: str = Field(default="")
    serviceConfig: dict[str, Any] = Field(default_factory=dict)


class StartPostprocessRequest(BaseModel):
    rerun: bool = False
    model_config = ConfigDict(extra="forbid")

    pluginIds: list[str] = Field(min_length=1)
    configs: dict[str, Any] = Field(default_factory=dict)


class ConnectionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    toolWsBaseUrl: str = Field(default="")


class StartManagedServiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceConfig: dict[str, Any] = Field(default_factory=dict)


def _default_paths(
    explicit_trace_root: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    debug_root = Path(__file__).resolve().parents[1]
    project_root = debug_root.parent
    cloud_root = project_root / "cloud"
    environment_value = os.getenv("WIDGET_SERVICE_GENERATION_TRACE_ROOT")
    if explicit_trace_root is not None:
        trace_root = explicit_trace_root
        if not trace_root.is_absolute():
            trace_root = project_root / trace_root
    elif environment_value:
        trace_root = Path(environment_value)
        if not trace_root.is_absolute():
            trace_root = project_root / trace_root
    else:
        trace_root = Path(str(load_batch_defaults(project_root).get("traceRoot")))
        if not trace_root.is_absolute():
            trace_root = project_root / trace_root
    return (
        debug_root / "Datasets",
        debug_root / "batch_output",
        trace_root,
        cloud_root,
    )


def register_batch_routes(
    app: FastAPI,
    manager: BatchRunManager | None = None,
    *,
    task_manager: BatchTaskManager | None = None,
    trace_root: Path | None = None,
    gallery_base_url: str = "http://127.0.0.1:8888/debug",
    main_agent_available: bool = True,
) -> BatchTaskManager:
    """把任务中心 API 与调度器生命周期注册到指定 FastAPI 应用。"""

    if task_manager is None:
        datasets_root, output_root, resolved_trace_root, cloud_root = _default_paths(trace_root)
        task_manager = BatchTaskManager(
            datasets_root,
            output_root,
            resolved_trace_root,
            cloud_root,
            run_manager=manager,
            gallery_base_url=gallery_base_url,
        )
    run_manager = task_manager.run_manager
    app.state.batch_task_manager = task_manager
    app.state.batch_run_manager = run_manager
    app.router.add_event_handler("startup", task_manager.start)
    app.router.add_event_handler("shutdown", task_manager.close)

    @app.get("/debug/batch/datasets")
    async def batch_datasets() -> dict[str, Any]:
        return {"items": task_manager.list_datasets()}

    @app.get("/debug/batch/datasets/{dataset_id}/samples")
    async def batch_dataset_samples(dataset_id: str) -> dict[str, Any]:
        try:
            return {"items": task_manager.dataset_samples(dataset_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="数据集不存在") from exc

    @app.get("/debug/batch/service-config/defaults")
    async def batch_service_defaults() -> dict[str, Any]:
        return task_manager.service_defaults()

    async def connection_status(tool_ws_base_url: str) -> dict[str, Any]:
        deployed_available, deployed_detail = await probe_service_health(tool_ws_base_url)
        managed = await task_manager.service_controller.status()
        return {
            "mainAgent": {
                "available": main_agent_available,
                "detail": (
                    "调试 Agent 后端已就绪"
                    if main_agent_available
                    else "当前仅启动静态工作台"
                ),
            },
            "deployedService": {
                "available": deployed_available,
                "detail": deployed_detail,
            },
            "managedService": managed,
        }

    @app.post("/debug/batch/connections/status")
    async def batch_connection_status(request: ConnectionStatusRequest) -> dict[str, Any]:
        return await connection_status(request.toolWsBaseUrl)

    @app.post("/debug/batch/connections/managed/start")
    async def start_managed_service(request: StartManagedServiceRequest) -> dict[str, Any]:
        try:
            endpoint = await task_manager.service_controller.ensure(request.serviceConfig)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return await connection_status(endpoint)

    @app.get("/debug/batch/device-capture/config")
    async def batch_device_capture_config() -> dict[str, Any]:
        return await task_manager.device_capture_manager.availability()

    @app.post("/debug/batch/tasks", status_code=201)
    async def create_batch_task(request: CreateTaskRequest) -> dict[str, Any]:
        try:
            return task_manager.create_and_enqueue(request.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="数据集不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/debug/batch/tasks")
    async def batch_tasks() -> dict[str, Any]:
        return {"items": task_manager.list_tasks()}

    @app.get("/debug/batch/tasks/{task_id}")
    async def batch_task(task_id: str) -> dict[str, Any]:
        try:
            return task_manager.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批量测试任务不存在") from exc

    @app.delete("/debug/batch/tasks/{task_id}", status_code=204)
    async def delete_batch_task(task_id: str) -> None:
        try:
            task_manager.delete_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批量测试任务不存在") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/debug/batch/tasks/{task_id}/copy", status_code=201)
    async def copy_batch_task(task_id: str) -> dict[str, Any]:
        try:
            return task_manager.copy_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批量测试任务不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/debug/batch/tasks/{task_id}/runs", status_code=202)
    async def enqueue_batch_task(task_id: str) -> dict[str, Any]:
        try:
            return task_manager.enqueue(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批量测试任务不存在") from exc

    @app.post("/debug/batch/runs/{run_id}/continue", status_code=202)
    async def continue_batch_run(run_id: str) -> dict[str, Any]:
        try:
            return task_manager.continue_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑记录不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/debug/batch/scheduler")
    async def batch_scheduler() -> dict[str, Any]:
        return task_manager.scheduler_state()

    @app.post("/debug/batch/scheduler/resume")
    async def resume_batch_scheduler() -> dict[str, Any]:
        return task_manager.resume()

    @app.get("/debug/batch/legacy-runs")
    async def legacy_batch_runs() -> dict[str, Any]:
        return {"items": task_manager.legacy_runs()}

    @app.get("/debug/batch/runs")
    async def batch_runs() -> dict[str, Any]:
        return {"items": run_manager.list_runs()}

    @app.get("/debug/batch/runs/{run_id}")
    async def batch_run(run_id: str) -> dict[str, Any]:
        try:
            return task_manager.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑记录不存在") from exc

    @app.get("/debug/batch/postprocess/plugins")
    async def batch_postprocess_plugins() -> dict[str, Any]:
        return {"items": task_manager.postprocess_manager.plugins()}

    @app.post("/debug/batch/runs/{run_id}/postprocess", status_code=202)
    async def start_batch_postprocess(
        run_id: str,
        request: StartPostprocessRequest,
    ) -> dict[str, Any]:
        try:
            return task_manager.postprocess_manager.enqueue(
                run_id,
                request.pluginIds,
                request.configs,
                rerun=request.rerun,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑记录不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/debug/batch/runs/{run_id}/postprocess")
    async def batch_postprocess_executions(run_id: str) -> dict[str, Any]:
        try:
            return {"items": task_manager.postprocess_manager.executions(run_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑记录不存在") from exc

    @app.get("/debug/batch/runs/{run_id}/postprocess/{execution_id}")
    async def batch_postprocess_execution(run_id: str, execution_id: str) -> dict[str, Any]:
        try:
            return task_manager.postprocess_manager.get_execution(run_id, execution_id)
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail="后处理执行不存在") from exc

    @app.get(
        "/debug/batch/runs/{run_id}/postprocess/{execution_id}/plugins/"
        "{plugin_id}/dashboard"
    )
    async def batch_postprocess_dashboard(
        run_id: str,
        execution_id: str,
        plugin_id: str,
    ) -> dict[str, Any]:
        try:
            return task_manager.postprocess_manager.dashboard(
                run_id,
                execution_id,
                plugin_id,
            )
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail="后处理看板不存在") from exc

    @app.get(
        "/debug/batch/runs/{run_id}/postprocess/{execution_id}/plugins/"
        "{plugin_id}/samples"
    )
    async def batch_postprocess_samples(
        run_id: str,
        execution_id: str,
        plugin_id: str,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=200),
        q: str = Query(default="", max_length=200),
        status: str = Query(default="", max_length=40),
        sort: str = Query(default="sequence", max_length=100),
        order: str = Query(default="asc", pattern="^(asc|desc)$"),
        factKey: str = Query(default="", max_length=80),
        factValue: str = Query(default="", max_length=200),
    ) -> dict[str, Any]:
        try:
            return task_manager.postprocess_manager.samples(
                run_id,
                execution_id,
                plugin_id,
                offset=offset,
                limit=limit,
                query=q,
                status=status,
                sort=sort,
                order=order,
                fact_key=factKey,
                fact_value=factValue,
            )
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail="后处理样本索引不存在") from exc

    @app.get(
        "/debug/batch/runs/{run_id}/postprocess/{execution_id}/plugins/"
        "{plugin_id}/samples/{sample_id}"
    )
    async def batch_postprocess_sample(
        run_id: str,
        execution_id: str,
        plugin_id: str,
        sample_id: str,
    ) -> dict[str, Any]:
        try:
            return task_manager.postprocess_manager.sample_result(
                run_id,
                execution_id,
                plugin_id,
                sample_id,
            )
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=404, detail="后处理样本结果不存在") from exc

    @app.get(
        "/debug/batch/runs/{run_id}/postprocess/{execution_id}/assets/"
        "{plugin_id}/{relative_path:path}"
    )
    async def batch_postprocess_asset(
        run_id: str,
        execution_id: str,
        plugin_id: str,
        relative_path: str,
    ) -> FileResponse:
        try:
            path = task_manager.postprocess_manager.asset_path(
                run_id,
                execution_id,
                plugin_id,
                relative_path,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="插件产物不存在") from exc
        return FileResponse(path)

    @app.get("/debug/batch/runs/{run_id}/samples/{sample_id}")
    async def batch_sample(run_id: str, sample_id: str) -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(run_manager.get_sample, run_id, sample_id)
            result["deviceCapture"] = task_manager.sample_device_capture(run_id, sample_id)
            return result
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑样本结果不存在") from exc

    @app.post("/debug/batch/runs/{run_id}/stop")
    async def stop_batch(run_id: str) -> dict[str, Any]:
        try:
            return await task_manager.stop_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑执行不存在") from exc

    @app.post("/debug/batch/runs/{run_id}/cancel")
    async def cancel_batch_compatibility(run_id: str) -> dict[str, Any]:
        try:
            return await task_manager.stop_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑执行不存在") from exc

    @app.get("/debug/batch/runs/{run_id}/device-captures/{sample_id}/{kind}")
    async def batch_device_capture_image(
        run_id: str,
        sample_id: str,
        kind: str,
    ) -> FileResponse:
        try:
            path = task_manager.device_capture_path(run_id, sample_id, kind)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="真机截图不存在") from exc
        media_type = "image/png" if kind == "card" else "image/jpeg"
        return FileResponse(path, media_type=media_type)

    @app.get("/debug/batch/runs/{run_id}/gallery.html")
    async def batch_gallery(run_id: str) -> FileResponse:
        try:
            path = task_manager.gallery_path(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑画廊尚未生成") from exc
        return FileResponse(path, media_type="text/html; charset=utf-8")

    @app.get("/debug/batch/runs/{run_id}/device-gallery.html")
    async def batch_device_gallery(run_id: str) -> FileResponse:
        try:
            path = task_manager.device_gallery_path(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="真机截图画廊尚未生成") from exc
        return FileResponse(path, media_type="text/html; charset=utf-8")

    @app.get("/debug/batch/runs/{run_id}/gallery-captures/{sample_id}")
    async def batch_gallery_capture(run_id: str, sample_id: str) -> FileResponse:
        try:
            path = task_manager.gallery_manager.capture_path(run_id, sample_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Web 渲染截图不存在") from exc
        return FileResponse(path, media_type="image/png")

    @app.get("/debug/batch/runs/{run_id}/trace-artifacts/{digest}")
    async def batch_trace_artifact(run_id: str, digest: str) -> FileResponse:
        try:
            path, media_type = run_manager.get_trace_artifact(run_id, digest)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return FileResponse(path, media_type=media_type)

    return task_manager
