# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import time
import traceback
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    ToolRequestEnvelope,
)
from app.logger import logger
from config.config import get_settings
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


def _request_id_from_envelope(envelope: ToolRequestEnvelope) -> str | None:
    """从外部请求包络中生成 requestId。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    出参：`sessionId&interactionId` 格式的 requestId；会话字段缺失时返回 None。
    """
    session_id = envelope.session.sessionId
    interaction_id = envelope.session.interactionId
    if session_id and interaction_id:
        return f"{session_id}&{interaction_id}"
    if session_id:
        return session_id
    return None


def _pick_device_rom_version(device_info: dict[str, Any]) -> str:
    """从 deviceInfo 中读取 ROM 版本，缺失时使用配置默认值。

    入参：
    - device_info：外部请求中的 deviceInfo 字典。
    出参：内部 DeviceContext 使用的 romVersion。
    """
    settings = get_settings()
    for key in ("romVersion", "romVer", "rom", "rom_version"):
        value = device_info.get(key)
        if value:
            return str(value)
    return settings.default_device_rom_version


def _pick_ohos_api_version(device_info: dict[str, Any]) -> int:
    """从 deviceInfo 中读取 ohosApiVersion，缺失时使用配置默认值。

    入参：
    - device_info：外部请求中的 deviceInfo 字典。
    出参：内部 DeviceContext 使用的 ohosApiVersion。
    """
    settings = get_settings()
    for key in ("ohosApiVersion", "ohos_api_version"):
        value = device_info.get(key)
        if value is not None:
            return int(value)
    return settings.default_ohos_api_version


def _device_context_from_envelope(envelope: ToolRequestEnvelope) -> dict[str, Any]:
    """把外部 deviceInfo 转换成内部 DeviceContext 字典。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    出参：可直接传给 DeviceContext 的字典。
    """
    device_info = envelope.deviceInfo.model_dump(mode="json", exclude_none=True)
    phone_type = device_info.get("phoneType")
    return {
        "deviceId": device_info.get("deviceId"),
        "deviceType": phone_type or str(device_info.get("deviceType", "")),
        "sysVersion": device_info.get("sysVer"),
        "deviceName": device_info.get("deviceFormation"),
        "odid": device_info.get("odid"),
        "udid": device_info.get("udid"),
        "romVersion": _pick_device_rom_version(device_info),
        "marketingName": device_info.get("marketingName") or phone_type,
        "ohosApiVersion": _pick_ohos_api_version(device_info),
    }


def _arguments_from_envelope(envelope: ToolRequestEnvelope, operation: str) -> dict[str, Any]:
    """从外部请求包络中组装内部业务入参。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    - operation：当前 WebSocket path 对应的业务能力名。
    出参：可直接传给具体请求模型的业务入参字典。
    """
    arguments = dict(envelope.content)
    if operation == "generateWidgetCard" and not arguments.get("userQuery"):
        arguments["userQuery"] = envelope.utterance.original if envelope.utterance else ""
    arguments["uid"] = envelope.userAuth.user.userId or ""
    arguments["locale"] = envelope.deviceInfo.locale or "zh-CN"
    arguments["apiVersion"] = envelope.deviceInfo.apiVersion
    arguments["device"] = _device_context_from_envelope(envelope)
    return arguments


def _normalize_payload(
    payload: dict[str, Any],
    operation: str,
) -> tuple[str | None, dict[str, Any]]:
    """归一化 WebSocket 原始报文。

    入参：
    - payload：客户端发送的 JSON 对象。
    - operation：当前 WebSocket path 对应的业务能力名。
    出参：requestId 与内部业务入参；优先支持 content/deviceInfo/session 新协议。
    """
    if "content" in payload or "deviceInfo" in payload or "session" in payload:
        envelope = ToolRequestEnvelope(**payload)
        return _request_id_from_envelope(envelope), _arguments_from_envelope(
            envelope, operation
        )
    return payload.get("requestId"), payload.get("arguments", payload)


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
    logger.info(f"widget_operation_ws_connected operation={operation}")
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
            started_at = time.perf_counter()
            request_id, arguments = _normalize_payload(payload, operation)
            logger.info(
                f"widget_operation_ws_payload_received request_id={request_id} "
                f"operation={operation} payload_keys={list(payload.keys())} "
                f"arguments={arguments}"
            )
            try:
                request = request_model(**arguments)
                logger.info(
                    f"widget_operation_ws_message_received request_id={request_id} "
                    f"operation={operation} uid={getattr(request, 'uid', '')} "
                    f"request={request.model_dump(mode='json', exclude_none=True)}"
                )
                result = handler(service, request)
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    f"widget_operation_ws_handler_completed request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"response={result.model_dump(mode='json', exclude_none=True)}"
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
                    f"widget_operation_ws_invalid_arguments request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"details={_error_details(exc)} "
                    f"exception_type={type(exc).__name__} exception={exc!r} "
                    f"traceback={traceback.format_exc()}"
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
                    f"widget_operation_ws_failed request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} error={exc} "
                    f"exception_type={type(exc).__name__} exception={exc!r} "
                    f"traceback={traceback.format_exc()}"
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
        logger.info(f"widget_operation_ws_disconnected operation={operation}")
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
