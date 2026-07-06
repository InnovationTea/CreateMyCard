import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
)
from app.logger import logger
from models.service import (
    WidgetWebSocketErrorMessage,
    WidgetWebSocketReadyMessage,
    WidgetWebSocketResultMessage,
)
from services.widget_generation_service import WidgetGenerationService

router = APIRouter(prefix="/api/v1")


def get_service() -> WidgetGenerationService:
    """创建卡片生成服务对象。

    入参：无。
    出参：WidgetGenerationService 实例。
    """
    return WidgetGenerationService()


def _arguments_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """从 WebSocket 原始报文中提取业务入参。

    入参：
    - payload：客户端发送的 JSON 对象，可直接是业务入参，也可包含 arguments 包装层。
    出参：业务入参字典。
    """
    return payload.get("arguments", payload)


def _error_details(exc: ValidationError | ValueError) -> list[dict[str, Any]] | str:
    """将参数异常转换成可序列化详情。

    入参：
    - exc：Pydantic 校验异常或业务参数异常。
    出参：可写入 WebSocket 错误消息的详情对象。
    """
    if isinstance(exc, ValidationError):
        return exc.errors()
    return str(exc)


async def _serve_operation_websocket(
    websocket: WebSocket,
    operation: str,
    request_model: type[BaseModel],
    handler,
) -> None:
    """承载单个工具能力的 WebSocket 循环。

    入参：
    - websocket：客户端 WebSocket 连接。
    - operation：当前 WS path 对应的能力名。
    - request_model：当前能力的入参实体类。
    - handler：当前能力对应的 service 方法。
    出参：无；服务端通过 WebSocket 返回 ready、result 或 error 消息。
    """
    # 每个 WS path 只承载一个业务能力，客户端不需要再传 operation 字段。
    await websocket.accept()
    logger.info("widget_operation_ws_connected", operation=operation)
    ready_message = WidgetWebSocketReadyMessage(
        tool=operation,
        operations=[operation],
    )
    await websocket.send_json(
        ready_message.model_dump(mode="json", exclude_none=True)
    )
    service = get_service()
    try:
        while True:
            payload = await websocket.receive_json()
            request_id = payload.get("requestId")
            started_at = time.perf_counter()
            logger.info(
                "widget_operation_ws_payload_received",
                request_id=request_id,
                operation=operation,
                payload_keys=list(payload.keys()),
                arguments=_arguments_from_payload(payload),
            )
            try:
                request = request_model(**_arguments_from_payload(payload))
                logger.info(
                    "widget_operation_ws_message_received",
                    request_id=request_id,
                    operation=operation,
                    uid=getattr(request, "uid", ""),
                    request=request.model_dump(mode="json", exclude_none=True),
                )
                result = handler(service, request)
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    "widget_operation_ws_handler_completed",
                    request_id=request_id,
                    operation=operation,
                    duration_ms=duration_ms,
                    response=result.model_dump(mode="json", exclude_none=True),
                )
                result_message = WidgetWebSocketResultMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    data=result.model_dump(mode="json", exclude_none=True),
                )
                await websocket.send_json(
                    result_message.model_dump(mode="json", exclude_none=True)
                )
            except (ValidationError, ValueError) as exc:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.error(
                    "widget_operation_ws_invalid_arguments",
                    request_id=request_id,
                    operation=operation,
                    duration_ms=duration_ms,
                    details=_error_details(exc),
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    requestId=request_id,
                    errorCode="INVALID_ARGUMENTS",
                    message=f"Invalid {operation} arguments.",
                    details=_error_details(exc),
                )
                await websocket.send_json(
                    error_message.model_dump(mode="json", exclude_none=True)
                )
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.error(
                    "widget_operation_ws_failed",
                    request_id=request_id,
                    operation=operation,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    requestId=request_id,
                    errorCode="FAILED",
                    message=str(exc),
                )
                await websocket.send_json(
                    error_message.model_dump(mode="json", exclude_none=True)
                )
    except WebSocketDisconnect:
        logger.info("widget_operation_ws_disconnected", operation=operation)
        return


@router.websocket("/ws/tools/getWidgetCapabilityOverview")
async def get_widget_capability_overview_ws(websocket: WebSocket):
    """能力概述 WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 CapabilityOverviewRequest。
    出参：无；服务端通过 WebSocket 返回 ready、result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "getWidgetCapabilityOverview",
        CapabilityOverviewRequest,
        lambda service, request: service.get_widget_capability_overview(request),
    )


@router.websocket("/ws/tools/getDataCapabilitySchemas")
async def get_data_capability_schemas_ws(websocket: WebSocket):
    """数据能力 schema WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 DataCapabilitySchemasRequest。
    出参：无；服务端通过 WebSocket 返回 ready、result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "getDataCapabilitySchemas",
        DataCapabilitySchemasRequest,
        lambda service, request: service.get_data_capability_schemas(request),
    )


@router.websocket("/ws/tools/generateWidgetCard")
async def generate_widget_card_ws(websocket: WebSocket):
    """卡片生成 WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 GenerateWidgetCardRequest。
    出参：无；服务端通过 WebSocket 返回 ready、result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCard",
        GenerateWidgetCardRequest,
        lambda service, request: service.generate_widget_card(request),
    )
