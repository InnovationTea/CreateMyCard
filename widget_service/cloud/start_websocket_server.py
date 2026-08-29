# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
from contextlib import asynccontextmanager, suppress

import uvicorn
from anyio import to_thread
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from api.routes import router
from app.logger import logger
from app.websocket_metrics import report_websocket_metrics, websocket_metrics
from config.config import get_settings
from custom.model_runtime import ModelExecutionRuntime

_MODULE = "[Main]"


def configure_anyio_thread_pool() -> int:
    """配置 Starlette 同步业务处理使用的 AnyIO 默认线程池容量。"""
    limiter = to_thread.current_default_thread_limiter()
    previous_tokens = limiter.total_tokens
    configured_tokens = get_settings().anyio_thread_pool_tokens
    limiter.total_tokens = configured_tokens
    logger.info(
        f"{_MODULE} anyio_thread_pool_configured previous_tokens={previous_tokens} "
        f"total_tokens={configured_tokens}"
    )
    return configured_tokens


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    入参：无。
    出参：配置好路由和日志中间件的 FastAPI 应用。
    """
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        configure_anyio_thread_pool()
        model_runtime = ModelExecutionRuntime()
        _app.state.model_runtime = model_runtime
        """启动并回收 WebSocket 全局统计打印任务。"""
        reporter = asyncio.create_task(report_websocket_metrics(websocket_metrics))
        try:
            yield
        finally:
            reporter.cancel()
            with suppress(asyncio.CancelledError):
                await reporter
            await model_runtime.aclose()
    fastapi_app = FastAPI(
        title="Widget Service",
        version="0.1.0",
        description="AI widget card generation microservice.",
        lifespan=lifespan,
    )
    fastapi_app.include_router(router)

    # Mount static file serving for mock_obs directory (artifact storage)
    mock_obs_dir = get_settings().WORKSPACE_ROOT / "mock_obs"
    mock_obs_dir.mkdir(parents=True, exist_ok=True)
    fastapi_app.mount(
        "/api/v1/artifacts",
        StaticFiles(directory=str(mock_obs_dir)),
        name="artifacts",
    )
    logger.info(
        f"{_MODULE} static_files_mounted path=/api/v1/artifacts directory={mock_obs_dir}"
    )

    @fastapi_app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:
        """记录 HTTP 请求日志并注入请求追踪 ID。

        入参：
        - request：FastAPI 当前 HTTP 请求对象。
        - call_next：框架提供的下一个处理器。
        出参：带 `x-request-id` 响应头的 HTTP 响应。
        """
        return await call_next(request)

    @fastapi_app.get("/health")
    async def health() -> dict[str, str]:
        """健康检查接口。

        入参：无。
        出参：服务存活状态。
        """
        return {"status": "ok"}

    return fastapi_app


app = create_app()


def run_local_server() -> None:
    """本地直接运行时启动服务。

    入参：无。
    出参：无；函数会阻塞当前进程并启动 Uvicorn 服务。
    """
    # 支持 `python cloud` 直接启动，默认监听 127.0.0.1:8855。
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_config=None,
    )


if __name__ == "__main__":
    run_local_server()
