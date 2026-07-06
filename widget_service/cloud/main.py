import time
import uuid

from fastapi import FastAPI, Request, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from api.routes import router
from core.logger import get_logger
from core.logging import configure_logging


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    入参：无。
        出参：配置好路由和日志中间件的 FastAPI 应用。
    """
    configure_logging()
    app = FastAPI(
        title="Widget Service",
        version="0.1.0",
        description="AI widget card generation microservice.",
    )
    app.include_router(router)
    logger = get_logger(__name__)

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
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.error("http_request_failed", duration_ms=duration_ms)
            clear_contextvars()
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["x-request-id"] = request_id
        logger.info(
            "http_request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
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
