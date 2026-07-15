# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import time
import traceback
import uuid

import uvicorn
from fastapi import FastAPI, Request, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from api.routes import router
from app.logger import logger
from config.config import get_settings


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    入参：无。
        出参：配置好路由和日志中间件的 FastAPI 应用。
    """
    app = FastAPI(
        title="Widget Service",
        version="0.1.0",
        description="AI widget card generation microservice.",
    )
    app.include_router(router)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next) -> Response:
        """记录 HTTP 请求日志并注入请求追踪 ID。

        入参：
        - request：FastAPI 当前 HTTP 请求对象。
        - call_next：框架提供的下一个处理器。
        出参：带 `x-request-id` 响应头的 HTTP 响应。
        """
        clear_contextvars()
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "",
        )
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.error(
                f"http_request_failed duration_ms={duration_ms} "
                f"exception_type={type(exc).__name__} exception={exc!r} "
                f"traceback={traceback.format_exc()}"
            )
            clear_contextvars()
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            f"http_request_completed status_code={response.status_code} "
            f"duration_ms={duration_ms}"
        )
        clear_contextvars()
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        """健康检查接口。

        入参：无。
        出参：服务存活状态。
        """
        return {"status": "ok"}

    return app


app = create_app()


def run_local_server() -> None:
    """本地直接运行 main.py 时启动服务。

    入参：无。
    出参：无；函数会阻塞当前进程并启动 Uvicorn 服务。
    """
    # 支持 `python cloud/main.py` 直接启动，默认监听 127.0.0.1:8855。
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_config=None,
    )


if __name__ == "__main__":
    run_local_server()
