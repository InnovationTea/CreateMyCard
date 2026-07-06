from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from api.schemas import WidgetCardServiceRequest
from core.logger import get_logger
from models.service import (
    WidgetWebSocketErrorMessage,
    WidgetWebSocketReadyMessage,
    WidgetWebSocketResultMessage,
)
from services.widget_generation_service import WidgetGenerationService

router = APIRouter(prefix="/api/v1")
logger = get_logger(__name__)
SUPPORTED_OPERATIONS = [
    "getWidgetCapabilityOverview",
    "getDataCapabilitySchemas",
    "generateWidgetCard",
]


def get_service() -> WidgetGenerationService:
    """创建卡片生成服务对象。

    入参：无。
    出参：WidgetGenerationService 实例。
    """
    return WidgetGenerationService()


def _widget_card_service_request_from_payload(payload: dict[str, Any]) -> WidgetCardServiceRequest:
    """从 WebSocket 原始报文中解析统一工具请求。

    入参：
    - payload：客户端发送的 JSON 对象，可直接是工具入参，也可包含 arguments 包装层。
    出参：WidgetCardServiceRequest 请求对象。
    """
    arguments = payload.get("arguments", payload)
    return WidgetCardServiceRequest(**arguments)


def _error_details(exc: ValidationError | ValueError) -> list[dict[str, Any]] | str:
    """将参数异常转换成可序列化详情。

    入参：
    - exc：Pydantic 校验异常或业务参数异常。
    出参：可写入 WebSocket 错误消息的详情对象。
    """
    if isinstance(exc, ValidationError):
        return exc.errors()
    return str(exc)


@router.websocket("/ws/tools/widgetCardService")
async def widget_card_service(websocket: WebSocket):
    """WebSocket 统一工具入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 widgetCardService inputSchema。
    出参：无；服务端通过 WebSocket 返回 ready、result 或 error 消息。
    """
    # 单一入口承载三个 operation，客户端可在同一连接内连续发送能力概述、schema 加载和卡片生成请求。
    await websocket.accept()
    logger.info("widget_card_service_ws_connected")
    ready_message = WidgetWebSocketReadyMessage(operations=SUPPORTED_OPERATIONS)
    await websocket.send_json(
        ready_message.model_dump(mode="json", exclude_none=True)
    )
    service = get_service()
    try:
        while True:
            payload = await websocket.receive_json()
            request_id = payload.get("requestId")
            try:
                request = _widget_card_service_request_from_payload(payload)
                logger.info(
                    "widget_card_service_ws_message_received",
                    request_id=request_id,
                    operation=request.operation,
                    uid=request.uid,
                )
                result = service.widget_card_service(request)
                result_message = WidgetWebSocketResultMessage(
                    operation=request.operation,
                    requestId=request_id,
                    data=result.model_dump(mode="json", exclude_none=True),
                )
                await websocket.send_json(
                    result_message.model_dump(mode="json", exclude_none=True)
                )
            except (ValidationError, ValueError) as exc:
                logger.error(
                    "widget_card_service_ws_invalid_arguments",
                    request_id=request_id,
                    details=_error_details(exc),
                )
                error_message = WidgetWebSocketErrorMessage(
                    requestId=request_id,
                    errorCode="INVALID_ARGUMENTS",
                    message="Invalid widgetCardService arguments.",
                    details=_error_details(exc),
                )
                await websocket.send_json(
                    error_message.model_dump(mode="json", exclude_none=True)
                )
            except Exception as exc:
                logger.error(
                    "widget_card_service_ws_failed",
                    request_id=request_id,
                    error=str(exc),
                )
                error_message = WidgetWebSocketErrorMessage(
                    requestId=request_id,
                    errorCode="FAILED",
                    message=str(exc),
                )
                await websocket.send_json(
                    error_message.model_dump(mode="json", exclude_none=True)
                )
    except WebSocketDisconnect:
        logger.info("widget_card_service_ws_disconnected")
        return
