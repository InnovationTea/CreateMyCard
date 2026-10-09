"""调试工作台编译产物的独立静态站点。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response

from debug_tools.batch_testing import register_batch_routes
from debug_tools.paths import DEBUG_TOOLS_ROOT, REPOSITORY_ROOT

FRONTEND_DIST = DEBUG_TOOLS_ROOT / "dist"
RESOURCE_ROOT = REPOSITORY_ROOT / "render" / "platform" / "public" / "resources"
RENDER_BACKGROUND_ROOT = REPOSITORY_ROOT / "render" / "platform" / "public" / "background_assets"
RENDER_FONT_ROOT = REPOSITORY_ROOT / "render" / "platform" / "public" / "fonts" / "harmonyos"


def register_renderer_asset_routes(app: FastAPI) -> None:
    """注册渲染器只读资源路由，并阻止资源根之外的路径访问。"""

    @app.get("/resources/{asset_path:path}")
    async def renderer_resource(asset_path: str) -> Response:
        return asset_response(RESOURCE_ROOT, asset_path)

    @app.get("/background_assets/{asset_path:path}")
    async def renderer_background(asset_path: str) -> Response:
        return asset_response(RENDER_BACKGROUND_ROOT, asset_path)

    @app.get("/fonts/harmonyos/{asset_path:path}")
    async def renderer_harmonyos_font(asset_path: str) -> Response:
        return asset_response(RENDER_FONT_ROOT, asset_path, media_type="font/ttf")


def create_frontend_app(
    static_dir: Path | None = None,
    *,
    trace_root: Path | None = None,
    gallery_base_url: str = "http://127.0.0.1:8888/debug",
) -> FastAPI:
    """创建不包含 Main Agent API 的纯前端静态服务。"""

    resolved_static_dir = (static_dir or FRONTEND_DIST).resolve()
    app = FastAPI(
        title="AI Widget Debug Frontend",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    register_renderer_asset_routes(app)

    @app.get("/debug/health")
    @app.get("/debug/skills")
    async def backend_unavailable() -> Response:
        return JSONResponse(
            {"status": "unavailable", "message": "Main Agent backend is disabled"},
            status_code=404,
        )

    @app.post("/debug/artifact")
    async def artifact_backend_unavailable() -> Response:
        return JSONResponse(
            {"status": "unavailable", "message": "Main Agent backend is disabled"},
            status_code=404,
        )

    register_batch_routes(
        app,
        trace_root=trace_root,
        gallery_base_url=gallery_base_url,
        main_agent_available=False,
    )

    @app.get("/debug")
    @app.get("/debug/")
    async def frontend_index() -> Response:
        return static_response(resolved_static_dir, "")

    @app.get("/debug/{asset_path:path}")
    async def frontend_asset(asset_path: str) -> Response:
        return static_response(resolved_static_dir, asset_path)

    return app


def static_response(static_dir: Path, asset_path: str) -> Response:
    """返回静态资源；非资源路径回退到 SPA 入口。"""

    if not static_dir.is_dir():
        return JSONResponse(
            {
                "status": "failed",
                "message": "debug frontend is not built; run npm run build in debug_tools",
            },
            status_code=503,
        )
    normalized = Path(asset_path)
    if asset_path and (normalized.is_absolute() or ".." in normalized.parts):
        return JSONResponse({"detail": "invalid asset path"}, status_code=400)
    candidate = (static_dir / normalized).resolve() if asset_path else static_dir / "index.html"
    try:
        candidate.relative_to(static_dir)
    except ValueError:
        return JSONResponse({"detail": "invalid asset path"}, status_code=400)
    if candidate.is_file():
        return FileResponse(candidate)
    index_path = static_dir / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return JSONResponse(
        {"status": "failed", "message": "debug frontend index is missing"},
        status_code=503,
    )


def asset_response(
    asset_root: Path,
    asset_path: str,
    *,
    media_type: str | None = None,
) -> Response:
    """从固定资源根返回文件，不对目录或越界路径提供 SPA fallback。"""

    normalized = Path(asset_path)
    if not asset_path or normalized.is_absolute() or ".." in normalized.parts:
        return JSONResponse({"detail": "invalid asset path"}, status_code=400)
    resolved_root = asset_root.resolve()
    candidate = (resolved_root / normalized).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return JSONResponse({"detail": "invalid asset path"}, status_code=400)
    if not candidate.is_file():
        return JSONResponse({"detail": "asset not found"}, status_code=404)
    return FileResponse(candidate, media_type=media_type)
