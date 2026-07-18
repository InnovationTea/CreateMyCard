# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import json
import time
import traceback
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    ToolRequestEnvelope,
)
from app.logger import json_for_log, logger, task_logger
from app.websocket_metrics import websocket_metrics
from config.config import get_settings
from models.service import (
    WidgetPluginReply,
    WidgetPluginStreamResponse,
    WidgetStreamInfo,
    WidgetWebSocketErrorMessage,
    WidgetWebSocketResultMessage,
)
from services.capability_registry import CapabilityRegistry
from services.widget_generation_service import WidgetGenerationService

router = APIRouter(prefix="/api/v1")

GENERATION_OPERATIONS = frozenset(
    {
        "generateWidgetCard",
        "generateWidgetCardCompactDsl",
    }
)


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
    """从 deviceInfo 中读取 ROM 版本。

    入参：
    - device_info：外部请求中的 deviceInfo 字典。
    出参：内部 DeviceContext 使用的 romVersion。
    """
    settings = get_settings()
    value = device_info.get("romVersion")
    if value is not None and str(value).strip():
        return CapabilityRegistry.normalize_rom_version(str(value))
    return CapabilityRegistry.normalize_rom_version(settings.default_device_rom_version)


def _device_context_from_envelope(
    envelope: ToolRequestEnvelope,
    odid: Any = None,
) -> dict[str, Any]:
    """把外部 deviceInfo 和 content.odid 转换成内部 DeviceContext 字典。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    - odid：content 中可选的设备 odid。
    出参：可直接传给 DeviceContext 的字典。
    """
    device_info = envelope.deviceInfo.model_dump(mode="json", exclude_none=True)
    phone_type = device_info.get("phoneType")
    return {
        "deviceId": device_info.get("deviceId"),
        "deviceType": phone_type or str(device_info.get("deviceType", "")),
        "sysVersion": device_info.get("sysVer"),
        "deviceName": device_info.get("deviceFormation"),
        "odid": odid,
        "udid": device_info.get("udid"),
        "romVersion": _pick_device_rom_version(device_info),
        "marketingName": device_info.get("marketingName") or phone_type,
    }


def _arguments_from_envelope(envelope: ToolRequestEnvelope, operation: str) -> dict[str, Any]:
    """从外部请求包络中组装内部业务入参。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    - operation：当前 WebSocket path 对应的业务能力名。
    出参：可直接传给具体请求模型的业务入参字典。
    """
    arguments = dict(envelope.content)
    odid = arguments.pop("odid", None)
    if operation in GENERATION_OPERATIONS and not arguments.get("userQuery"):
        arguments["userQuery"] = envelope.utterance.original if envelope.utterance else ""
    arguments["uid"] = envelope.userAuth.user.userId or ""
    arguments["locale"] = envelope.deviceInfo.locale or "zh-CN"
    arguments["prdVer"] = envelope.deviceInfo.prdVer
    arguments["device"] = _device_context_from_envelope(envelope, odid)
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
        # Pydantic 的 ctx 可能携带原生 ValueError，input 可能包含完整请求或注册表；
        # 二者既不适合对外返回，也可能导致错误响应再次序列化失败。
        return exc.errors(include_context=False, include_input=False)
    return str(exc)


def _stream_content_for_result(operation: str, result_data: dict[str, Any]) -> str:
    """根据业务结果生成流式答复文本。

    入参：
    - operation：当前 WS path 对应的能力名。
    - result_data：业务响应对象的 JSON 字典。
    出参：写入 reply.streamInfo.streamContent 的 markdown 文本。
    """
    if operation == "getWidgetCapabilityOverview":
        data_count = len(result_data.get("dataCapabilities", []))
        event_count = len(result_data.get("eventCapabilities", []))
        asset_count = len(result_data.get("assetCandidates", []))
        unavailable_count = len(result_data.get("unavailableCapabilities", []))
        return (
            f"已获取卡片能力概述：{data_count} 个数据能力、"
            f"{event_count} 个事件能力、{asset_count} 个素材候选，"
            f"{unavailable_count} 项不可用。"
        )

    if operation == "getDataCapabilitySchemas":
        found_count = len(result_data.get("dataCapabilities", []))
        missing_count = len(result_data.get("missingCapabilityIds", []))
        if missing_count:
            return f"已获取 {found_count} 个数据能力 Schema，{missing_count} 个能力未找到。"
        return f"已获取 {found_count} 个数据能力 Schema。"

    if operation in GENERATION_OPERATIONS:
        return result_data.get("message") or "卡片生成流程已完成。"

    return "工具调用已完成。"


def _stream_content_for_error(operation: str, error_code: str) -> str:
    """根据异常类型生成流式错误文本。

    入参：
    - operation：当前 WS path 对应的能力名。
    - error_code：错误码。
    出参：写入 reply.streamInfo.streamContent 的 markdown 文本。
    """
    if error_code == "INVALID_ARGUMENTS":
        return f"{operation} 入参校验失败，请检查参数后重试。"
    return f"{operation} 调用失败，请稍后再试。"


def _build_plugin_stream_response(
    legacy_message: WidgetWebSocketResultMessage | WidgetWebSocketErrorMessage,
    stream_content: str,
    top_error_code: str = "0",
    top_error_message: str = "",
) -> WidgetPluginStreamResponse:
    """把当前完整旧出参整体放入华为流处理插件输出包络。

    入参：
    - legacy_message：旧版 WebSocket 完整出参。
    - stream_content：流式文本内容。
    - top_error_code：插件顶层错误码，成功为 "0"。
    - top_error_message：插件顶层错误描述。
    出参：符合华为流处理插件输出参数配置的新包络。
    """
    streaming_text_id = legacy_message.requestId or uuid.uuid4().hex
    return WidgetPluginStreamResponse(
        errorCode=top_error_code,
        errorMessage=top_error_message,
        reply=WidgetPluginReply(
            streamInfo=WidgetStreamInfo(
                streamContent=str(legacy_message),
                streamingTextId=streaming_text_id,
            ),
            items=[
                legacy_message.model_dump(mode="json", exclude_none=True),
            ],
        ),
    )


async def _send_websocket_json(
    websocket: WebSocket,
    payload: dict[str, Any],
    operation: str,
    request_id: str | None,
    frame_type: str,
) -> bool:
    """发送 WebSocket JSON 帧，并处理客户端已断开的情况。"""
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError) as exc:
        logger.error(
            f"widget_operation_ws_send_failed request_id={request_id} "
            f"operation={operation} frame_type={frame_type} "
            f"exception_type={type(exc).__name__} exception={exc!r} "
            f"traceback={traceback.format_exc()}"
        )
        return False


async def _heartbeat_sender(
    websocket: WebSocket,
    streaming_text_id: str,
    interval: float = 6.0,
) -> None:
    """周期性向客户端发送 partial 心跳帧。

    入参：
    - websocket：客户端 WebSocket 连接。
    - streaming_text_id：一次请求内稳定的流式文本 ID。
    - interval：心跳发送间隔秒数，默认 6 秒。
    出参：无；协程会持续运行直到被取消或连接关闭。
    """
    partial_frame = WidgetPluginStreamResponse(
        errorCode="0",
        errorMessage="",
        reply=WidgetPluginReply(
            streamInfo=WidgetStreamInfo(
                streamContent="",
                streamingTextId=streaming_text_id,
                streamType="partial",
                textType="markdown",
            ),
            items=[],
        ),
    )
    partial_json = json.dumps(
        partial_frame.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
    )
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text(partial_json)
    except asyncio.CancelledError:
        logger.error("widget_operation_ws_heartbeat_cancelled")
        pass
    except Exception:
        logger.error("widget_operation_ws_heartbeat_failed", exc_info=True)
        pass


async def _serve_operation_websocket(
    websocket: WebSocket,
    operation: str,
    request_model: type[BaseModel],
    handler,
    heartbeat: bool = False,
    heartbeat_interval: float = 6.0,    
) -> None:
    """承载单个工具能力的 WebSocket 循环。

    入参：
    - websocket：客户端 WebSocket 连接。
    - operation：当前 WS path 对应的能力名。
    - request_model：当前能力的入参实体类。
    - handler：当前能力对应的 service 方法。
    出参：无；服务端通过 WebSocket 返回华为流处理插件格式消息。
    """
    # 每个 WS path 只承载一个业务能力，客户端不需要再传 operation 字段。
    metrics = websocket_metrics
    await websocket.accept()
    metrics.connection_opened()
    logger.info(f"widget_operation_ws_connected operation={operation}")
    try:
        service = get_service()
        while True:
            payload = await websocket.receive_json()
            started_at = time.perf_counter()
            request_id, arguments = _normalize_payload(payload, operation)
            # 三个接口共用该入口；解析出 requestId 后立即写入日志上下文，
            # 后续 service、IDS、A2UI 和异常日志都会自动携带同一个 requestId。
            task_logger.set_session_id(request_id or "None")
            logger.info(
                f"widget_operation_ws_payload_received request_id={request_id} "
                f"operation={operation} payload_keys={json_for_log(sorted(payload))} "
                f"argument_keys={json_for_log(sorted(arguments))}"
            )
            # streaming_text_id 沿用现有逻辑：有 requestId 时取 requestId，否则生成随机 ID。
            streaming_text_id = request_id or uuid.uuid4().hex
            heartbeat_task: asyncio.Task | None = None
            metrics.task_started()
            try:
                request = request_model(**arguments)
                request_log = json_for_log(
                    request.model_dump(
                        mode="json",
                        exclude={"uid", "sourceArtifactUrl"},
                        exclude_none=True,
                    )
                )
                logger.info(
                    f"widget_operation_ws_message_received request_id={request_id} "
                    f"operation={operation} "
                    f"request={request_log}"
                )
                # 收到合法请求后先发送 start 帧，再启动心跳协程。
                start_frame = WidgetPluginStreamResponse(
                    errorCode="0",
                    errorMessage="",
                    reply=WidgetPluginReply(
                        streamInfo=WidgetStreamInfo(
                            streamContent="",
                            streamingTextId=streaming_text_id,
                            streamType="start",
                            textType="markdown",
                        ),
                        items=[],
                    ),
                )
                if not await _send_websocket_json(
                    websocket,
                    start_frame.model_dump(mode="json", exclude_none=True),
                    operation,
                    request_id,
                    "start",
                ):
                    return
                if heartbeat:
                    heartbeat_task = asyncio.create_task(
                        _heartbeat_sender(websocket, streaming_text_id, heartbeat_interval)
                    )                
                # service 目前是同步编排器，内部包含 requests、同步文件读取和重试校验。
                # WebSocket 入口必须把它放到线程池里执行，避免阻塞当前 async 事件循环。
                result = await run_in_threadpool(handler, service, request)
                result_data = result.model_dump(mode="json", exclude_none=True)
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.info(
                    f"widget_operation_ws_handler_completed request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"response={json_for_log(result_data)}"
                )
                result_message = WidgetWebSocketResultMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    data=result_data,
                    status=result_data.get("status", "success"),
                    errorCode=result_data.get("errorCode", ""),
                    error={},
                )
                plugin_response = _build_plugin_stream_response(
                    result_message,
                    _stream_content_for_result(operation, result_data),
                    top_error_code=result_data.get("errorCode", "FAILED")
                    if result_data.get("status") == "failed"
                    else "0",
                    top_error_message=result_data.get("message", "")
                    if result_data.get("status") == "failed"
                    else "",
                )
                if not await _send_websocket_json(
                    websocket,
                    plugin_response.model_dump(mode="json", exclude_none=True),
                    operation,
                    request_id,
                    "final",
                ):
                    return
            except ValueError as exc:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                logger.error(
                    f"widget_operation_ws_invalid_arguments request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"details={json_for_log(_error_details(exc))} "
                    f"exception_type={type(exc).__name__} exception={exc!r} "
                    f"traceback={traceback.format_exc()}"
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    errorCode="INVALID_ARGUMENTS",
                    error={
                        "message": f"Invalid {operation} arguments.",
                        "details": _error_details(exc),
                    },
                )
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    _stream_content_for_error(operation, "INVALID_ARGUMENTS"),
                    top_error_code="INVALID_ARGUMENTS",
                    top_error_message=f"Invalid {operation} arguments.",
                )
                if not await _send_websocket_json(
                    websocket,
                    plugin_response.model_dump(mode="json", exclude_none=True),
                    operation,
                    request_id,
                    "final_error",
                ):
                    return
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
                    operation=operation,
                    requestId=request_id,
                    errorCode="FAILED",
                    error={"message": str(exc)},
                )
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    _stream_content_for_error(operation, "FAILED"),
                    top_error_code="FAILED",
                    top_error_message=str(exc),
                )
                if not await _send_websocket_json(
                    websocket,
                    plugin_response.model_dump(mode="json", exclude_none=True),
                    operation,
                    request_id,
                    "final_error",
                ):
                    return
            finally:
                metrics.task_finished()
                if heartbeat_task:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        logger.error("widget_operation_ws_heartbeat_cancelled")
    except WebSocketDisconnect:
        logger.info(f"widget_operation_ws_disconnected operation={operation}")
        return
    finally:
        metrics.connection_closed()


@router.websocket("/ws/tools/getWidgetCapabilityOverview")
async def get_widget_capability_overview_ws(websocket: WebSocket):
    """能力概述 WebSocket 入口。

    入参：
    - websocket：客户端 WebSocket 连接，消息体需符合 CapabilityOverviewRequest。
    出参：无；服务端通过 WebSocket 返回 result 或 error 消息。
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
    出参：无；服务端通过 WebSocket 返回 result 或 error 消息。
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
    出参：无；服务端通过 WebSocket 返回 result 或 error 消息。
    """
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCard",
        GenerateWidgetCardRequest,
        lambda service, request: service.generate_widget_card_a2ui_form(request),
        heartbeat=True,
        heartbeat_interval=6.0,        
    )


@router.websocket("/ws/tools/generateWidgetCardCompactDsl")
async def generate_widget_card_compact_dsl_ws(websocket: WebSocket):
    """Compact DSL 卡片生成 WebSocket 入口。"""
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCardCompactDsl",
        GenerateWidgetCardRequest,
        lambda service, request: service.generate_widget_card_compact_dsl(request),
        heartbeat=True,
        heartbeat_interval=6.0,        
    )
