"""批量测试任务中心 REST API。"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from debug_tools.paths import CLOUD_ROOT, DEBUG_TOOLS_ROOT, WIDGET_SERVICE_ROOT

from .capability_labels import options as expect_options_catalog
from .expect_compare import compare as compare_expect
from .expect_compare import compare_live as compare_expect_live
from .expect_compare import detect_payload as detect_expect_payload
from .expect_compare import input_image_path
from .expect_gallery import delete_run as delete_expect_run
from .expect_gallery import delete_sample as delete_expect_sample
from .expect_gallery import gallery as expect_gallery
from .expect_gallery import sample_detail as expect_sample_detail
from .expect_gallery import sample_ids as expect_sample_ids
from .managed_config import ConfigConflict, save_configuration
from .quality import compare as compare_quality
from .quality import evaluation as quality_evaluation
from .quality_import import (
    MAX_REQUEST_BYTES,
    import_batch,
    update_run_category,
    update_sample,
)
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


class LiveCompareRequest(BaseModel):
    """实际侧直接提交浏览器会话里的真实输出；后端不落盘，只做指纹与配对计算。"""

    model_config = ConfigDict(extra="forbid")

    # 期望侧不再要求挑批次：留空即用全部已导入的期望输出。
    importRunId: str = Field(default="", max_length=80)
    actualName: str = Field(default="", max_length=80)
    actuals: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    dimensions: list[str] = Field(
        default_factory=lambda: ["data", "actions", "icons"], max_length=3,
    )


class DetectPayloadRequest(BaseModel):
    """导入页识别一份文件是 CardSpec 还是 genui DSL，并取回自动提取的指纹。"""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2 * 1024 * 1024)


class StartManagedServiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serviceConfig: dict[str, Any] = Field(default_factory=dict)


class SaveServiceConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    changes: dict[str, Any]


def _default_paths(
    explicit_trace_root: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    environment_value = os.getenv("WIDGET_SERVICE_GENERATION_TRACE_ROOT")
    if explicit_trace_root is not None:
        trace_root = explicit_trace_root
        if not trace_root.is_absolute():
            trace_root = WIDGET_SERVICE_ROOT / trace_root
    elif environment_value:
        trace_root = Path(environment_value)
        if not trace_root.is_absolute():
            trace_root = WIDGET_SERVICE_ROOT / trace_root
    else:
        trace_root = Path(str(load_batch_defaults(WIDGET_SERVICE_ROOT).get("traceRoot")))
        if not trace_root.is_absolute():
            trace_root = WIDGET_SERVICE_ROOT / trace_root
    return (
        DEBUG_TOOLS_ROOT / "Datasets",
        DEBUG_TOOLS_ROOT / "batch_output",
        trace_root,
        CLOUD_ROOT,
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
        try:
            return task_manager.service_defaults()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.patch("/debug/batch/service-config/defaults")
    async def save_service_defaults(request: SaveServiceConfigRequest) -> dict[str, Any]:
        try:
            return save_configuration(task_manager.project_root, request.changes, request.version)
        except ConfigConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail="配置文件保存失败，原文件未覆盖") from exc

    async def connection_status(tool_ws_base_url: str) -> dict[str, Any]:
        deployed_available, deployed_detail = await probe_service_health(tool_ws_base_url)
        managed = await task_manager.service_controller.status()
        return {
            "mainAgent": {
                "available": main_agent_available,
                "detail": (
                    "调试 Agent 后端已就绪" if main_agent_available else "当前仅启动静态工作台"
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
            if request.serviceConfig:
                raise ValueError("手动启动只使用服务器已保存配置，请先保存默认值")
            endpoint = await task_manager.service_controller.ensure({})
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
        return {"items": await run_in_threadpool(task_manager.list_tasks)}

    @app.get("/debug/batch/tasks/{task_id}")
    async def batch_task(task_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(task_manager.get_task, task_id)
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
        return await run_in_threadpool(task_manager.scheduler_state)

    @app.post("/debug/batch/scheduler/resume")
    async def resume_batch_scheduler() -> dict[str, Any]:
        return task_manager.resume()

    @app.get("/debug/batch/legacy-runs")
    async def legacy_batch_runs() -> dict[str, Any]:
        return {"items": task_manager.legacy_runs()}

    @app.get("/debug/batch/runs")
    async def batch_runs() -> dict[str, Any]:
        names = {item.get("taskId"): item.get("name") for item in task_manager.list_tasks()}
        runs = run_manager.list_runs()
        for run in runs:
            run["name"] = run.get("name") or names.get(run.get("taskId")) or run.get("datasetId")
            # 导入批次带用途（期望／实际），前端只从这里取列表。
            # 历史导入批次没有 purpose 字段时按期望处理，与后端 import_purpose 同一口径。
            if run.get("sourceType") == "external-quality" and not run.get("purpose"):
                run["purpose"] = "expect"
        return {"items": runs}

    @app.get("/debug/batch/quality/evaluation")
    async def batch_quality_evaluation() -> dict[str, Any]:
        try:
            return quality_evaluation()
        except (OSError, ValueError, IndexError) as exc:
            raise HTTPException(status_code=503, detail="评估方案不可用") from exc

    # 期望对比模块接口。导入产出的是「期望批次」，同时服务质量评分与期望对比，
    # 因此除 /debug/expect/* 正式路径外保留 /debug/batch/quality/* 兼容别名。
    @app.post("/debug/expect/import")
    @app.post("/debug/batch/quality/import")
    async def import_quality(request: Request) -> dict[str, Any]:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="每次导入最多 64 MiB，请分批")
        try:
            payload = json.loads(data)
            return await run_in_threadpool(import_batch, task_manager.output_root, payload)
        except (ValueError, RecursionError) as exc:
            detail = str(exc) if not isinstance(exc, RecursionError) else "输入嵌套过深"
            raise HTTPException(status_code=422, detail=detail) from exc

    @app.get("/debug/batch/quality/compare")
    async def batch_quality_compare(
        leftRunId: str,
        rightRunId: str,
        leftExecutionId: str | None = None,
        rightExecutionId: str | None = None,
        leftSampleId: str | None = None,
        rightSampleId: str | None = None,
    ) -> dict[str, Any]:
        try:
            return compare_quality(
                task_manager.postprocess_manager,
                leftRunId,
                rightRunId,
                leftExecutionId,
                rightExecutionId,
                leftSampleId,
                rightSampleId,
            )
        except (KeyError, OSError) as exc:
            raise HTTPException(status_code=404, detail="批次或评分结果不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/debug/expect/compare")
    @app.get("/debug/batch/quality/expect")
    async def expect_compare(
        runId: str, importRunId: str = "", dimensions: str | None = None,
    ) -> dict[str, Any]:
        # 页面用同一个维度开关覆盖两种实际来源；不传时按默认三个维度全启用。
        options = (
            {"dimensions": [item for item in dimensions.split(",") if item.strip()]}
            if dimensions is not None else None
        )
        try:
            return await run_in_threadpool(
                compare_expect, run_manager, importRunId, runId, options,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批次或样本结果不存在") from exc
        except (OSError, ValueError) as exc:
            detail = str(exc) if not isinstance(exc, OSError) else "批次结果不可读"
            raise HTTPException(status_code=409, detail=detail) from exc

    # 实际侧不要求先跑批：页面把端到端／接口调试拿到的真实输出（query＋genui）提交上来，
    # 后端用与批跑侧同一套指纹、尺寸门槛与配对规则计算。
    @app.post("/debug/expect/compare-live")
    async def expect_compare_live(payload: LiveCompareRequest) -> dict[str, Any]:
        try:
            return await run_in_threadpool(
                compare_expect_live, run_manager, payload.importRunId,
                payload.actuals, payload.actualName,
                {"dimensions": payload.dimensions},
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="期望批次不存在") from exc
        except (OSError, RecursionError) as exc:
            detail = "输入嵌套过深" if isinstance(exc, RecursionError) else "批次结果不可读"
            raise HTTPException(status_code=409, detail=detail) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 导入页选择内容文件后即时识别格式（CardSpec／genui DSL）并预览指纹；导入时后端仍会重新提取。
    @app.post("/debug/expect/detect")
    async def expect_detect(payload: DetectPayloadRequest) -> dict[str, Any]:
        try:
            return await run_in_threadpool(detect_expect_payload, payload.text)
        except RecursionError as exc:
            raise HTTPException(status_code=422, detail="输入嵌套过深") from exc

    # 导入页的数据／动作／图标候选：token 与匹配时比较的值同形，附带中文标签，
    # 页面据此做下拉与模糊提示；候选之外的写法仍可直接输入。
    @app.get("/debug/expect/options")
    async def expect_options() -> dict[str, Any]:
        return await run_in_threadpool(expect_options_catalog)

    # 前端画廊页面自身占用 /debug/expect/gallery，接口改用 /samples 避免被 API 抢先返回 JSON。
    @app.get("/debug/expect/samples")
    async def expect_gallery_list(
        category: str = "", q: str = "",
    ) -> dict[str, Any]:
        try:
            return await run_in_threadpool(
                expect_gallery, run_manager, category, q
            )
        except (OSError, ValueError) as exc:
            detail = str(exc) if not isinstance(exc, OSError) else "期望批次结果不可读"
            raise HTTPException(status_code=409, detail=detail) from exc

    # 导入页提交前只查「该侧已有哪些样本 ID」：轻量接口，避免为了查重拉整份样本。
    @app.get("/debug/expect/sample-ids")
    async def expect_sample_id_index(purpose: str = "") -> dict[str, Any]:
        try:
            return await run_in_threadpool(expect_sample_ids, run_manager, purpose)
        except (OSError, ValueError) as exc:
            detail = str(exc) if not isinstance(exc, OSError) else "期望批次结果不可读"
            raise HTTPException(status_code=409, detail=detail) from exc

    @app.delete("/debug/expect/runs/{run_id}/samples/{sample_id}")
    async def expect_gallery_delete_sample(run_id: str, sample_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(
                delete_expect_sample, run_manager, run_id, sample_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="期望样本不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=409, detail="删除失败，文件可能被占用") from exc

    @app.delete("/debug/expect/runs/{run_id}")
    async def expect_gallery_delete_run(run_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(delete_expect_run, run_manager, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="期望批次不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=409, detail="删除失败，文件可能被占用") from exc

    # 单条样本的读取与就地更新：编辑一条期望不必整批重导，也不会牵动同批其它样本。
    @app.get("/debug/expect/runs/{run_id}/samples/{sample_id}")
    async def expect_gallery_sample(run_id: str, sample_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(
                expect_sample_detail, run_manager, run_id, sample_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="期望样本不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.put("/debug/expect/runs/{run_id}/samples/{sample_id}")
    async def expect_sample_update(
        run_id: str, sample_id: str, request: Request,
    ) -> dict[str, Any]:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="每次最多 64 MiB，请分批")
        try:
            payload = json.loads(data)
            return await run_in_threadpool(
                update_sample, task_manager.output_root, run_id, sample_id, payload
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="期望样本不存在") from exc
        except (ValueError, RecursionError) as exc:
            detail = str(exc) if not isinstance(exc, RecursionError) else "输入嵌套过深"
            raise HTTPException(status_code=422, detail=detail) from exc
        except OSError as exc:
            raise HTTPException(status_code=409, detail="保存失败，文件可能被占用") from exc

    # 整批改数据分类：画廊里一次改掉这批所有图片的分类，不重写 DSL 与截图。
    @app.put("/debug/expect/runs/{run_id}/category")
    async def expect_run_category(run_id: str, request: Request) -> dict[str, Any]:
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="每次最多 64 MiB，请分批")
        try:
            payload = json.loads(data)
            return await run_in_threadpool(
                update_run_category, task_manager.output_root, run_id, payload
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="期望批次不存在") from exc
        except (ValueError, RecursionError) as exc:
            detail = str(exc) if not isinstance(exc, RecursionError) else "输入嵌套过深"
            raise HTTPException(status_code=422, detail=detail) from exc
        except OSError as exc:
            raise HTTPException(status_code=409, detail="保存失败，文件可能被占用") from exc

    @app.get("/debug/expect/runs/{run_id}/samples/{sample_id}/input-image")
    @app.get("/debug/batch/runs/{run_id}/samples/{sample_id}/input-image")
    async def batch_sample_input_image(run_id: str, sample_id: str) -> FileResponse:
        try:
            path, media_type = await run_in_threadpool(
                input_image_path, run_manager.output_root, run_id, sample_id
            )
        except (KeyError, OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="导入截图不存在") from exc
        return FileResponse(path, media_type=media_type)

    @app.get("/debug/batch/runs/{run_id}")
    async def batch_run(run_id: str) -> dict[str, Any]:
        try:
            return await run_in_threadpool(task_manager.get_run, run_id)
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

    @app.get("/debug/batch/runs/{run_id}/postprocess/{execution_id}/plugins/{plugin_id}/dashboard")
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

    @app.get("/debug/batch/runs/{run_id}/postprocess/{execution_id}/plugins/{plugin_id}/samples")
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
        media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
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

    @app.get("/debug/batch/runs/{run_id}/validation-failures")
    async def batch_validation_failures(run_id: str) -> dict[str, Any]:
        try:
            items = task_manager.validation_failure_items(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="批跑执行不存在") from exc
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"items": items}

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
