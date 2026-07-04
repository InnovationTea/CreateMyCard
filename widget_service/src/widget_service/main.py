from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from widget_service.api.routes import router
from widget_service.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Widget Service",
        version="0.1.0",
        description="AI widget card generation microservice.",
    )
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "ready", "service": "widget-service"})
        try:
            while True:
                message = await websocket.receive_json()
                await websocket.send_json({"type": "echo", "payload": message})
        except WebSocketDisconnect:
            return

    return app


app = create_app()
