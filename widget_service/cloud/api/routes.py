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
from core.errors import ErrorCode
from models.service import (
    WidgetPluginReply,
    WidgetPluginStreamResponse,
    WidgetStreamInfo,
    WidgetWebSocketErrorMessage,
    WidgetWebSocketResultMessage,
)
from services.capability_registry import CapabilityRegistry
from services.widget_generation_service import WidgetGenerationService

_MODULE = "[WS Router]"

router = APIRouter(prefix="/api/v1")

GENERATION_OPERATIONS = frozenset(
    {
        "generateWidgetCard",
        "generateWidgetCardCompactDsl",
    }
)

PARAMETER_ERROR_CODES = frozenset(
    {
        ErrorCode.INVALID_ARGUMENTS.value,
        ErrorCode.UNKNOWN_CAPABILITY.value,
        ErrorCode.WRITE_RESULT_CONFLICT.value,
        ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
    }
)
SOURCE_ARTIFACT_ERROR_CODES = frozenset(
    {
        ErrorCode.SOURCE_ARTIFACT_NOT_FOUND.value,
        ErrorCode.SOURCE_ARTIFACT_DOWNLOAD_FAILED.value,
        ErrorCode.SOURCE_ARTIFACT_SCHEMA_UNSUPPORTED.value,
        ErrorCode.SOURCE_ARTIFACT_INVALID.value,
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
    raw_rom_version = device_info.get("romVersion")
    if raw_rom_version is None or not str(raw_rom_version).strip():
        raw_rom_version = get_settings().default_device_rom_version
    return {
        "deviceId": device_info.get("deviceId"),
        "deviceType": phone_type or str(device_info.get("deviceType", "")),
        "sysVersion": device_info.get("sysVer"),
        "deviceName": device_info.get("deviceFormation"),
        "odid": odid,
        "udid": device_info.get("udid"),
        "romVersion": _pick_device_rom_version(device_info),
        "_sourceRomVersion": str(raw_rom_version),
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


def _build_plugin_stream_response(
    legacy_message: WidgetWebSocketResultMessage | WidgetWebSocketErrorMessage,
) -> WidgetPluginStreamResponse:
    """把旧版完整消息转换成华为流处理插件输出包络。

    入参：
    - legacy_message：旧版 WebSocket 完整出参。
    出参：插件顶层始终成功；业务异常说明和完整旧消息放入 streamContent。
    """
    streaming_text_id = legacy_message.requestId or uuid.uuid4().hex
    stream_content = str(legacy_message)
    error_explanation = _error_explanation(legacy_message.errorCode)
    if error_explanation:
        stream_content = f"{error_explanation}：{stream_content}"
    return WidgetPluginStreamResponse(
        errorCode="0",
        errorMessage="",
        reply=WidgetPluginReply(
            streamInfo=WidgetStreamInfo(
                # 插件只消费字符串字段；保留旧消息的完整字符串表现，避免拆散旧协议字段。
                streamContent=stream_content,
                streamingTextId=streaming_text_id,
            ),
            items=[],
        ),
    )


def _error_explanation(error_code: str) -> str:
    """根据业务错误码生成放在 streamContent 最前面的中文异常类型说明。"""
    if not error_code:
        return ""
    if error_code in PARAMETER_ERROR_CODES:
        return "当前调用工具参数异常"
    if error_code == ErrorCode.APP_VERSION_UNSUPPORTED.value:
        return "当前设备版本不支持调用此工具"
    if error_code == ErrorCode.PACKAGE_NOT_INSTALLED.value:
        return "当前设备缺少工具依赖应用"
    if error_code == ErrorCode.A2UI_GENERATION_FAILED.value:
        return "当前调用工具卡片生成异常"
    if error_code == ErrorCode.VALIDATION_FAILED.value:
        return "当前调用工具卡片校验异常"
    if error_code == ErrorCode.ARTIFACT_UPLOAD_FAILED.value:
        return "当前调用工具产物保存异常"
    if error_code == ErrorCode.WIDGET_EDIT_DISABLED.value:
        return "当前调用工具编辑功能未开启"
    if error_code in SOURCE_ARTIFACT_ERROR_CODES:
        return "当前调用工具来源产物处理异常"
    if error_code == ErrorCode.TIMEOUT.value:
        return "当前调用工具执行超时"
    return "当前调用工具服务异常"


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
            f"{_MODULE} widget_operation_ws_send_failed request_id={request_id} "
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
        logger.error(f"{_MODULE} widget_operation_ws_heartbeat_cancelled")
        pass
    except Exception:
        logger.error(f"{_MODULE} widget_operation_ws_heartbeat_failed", exc_info=True)
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

    每条消息依次经过：原始日志、协议归一化、start/heartbeat、线程池业务调用、
    final 旧消息字符串封装。业务调用期间不占用事件循环线程。

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
    logger.info(f"{_MODULE} widget_operation_ws_connected operation={operation}")
    try:
        service = get_service()
        while True:
            try:
                payload = await websocket.receive_json()
            except ValueError as exc:
                logger.error(
                    f"{_MODULE} widget_operation_ws_invalid_json operation={operation} "
                    f"exception_type={type(exc).__name__} exception={exc!r}"
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    operation=operation,
                    errorCode=ErrorCode.INVALID_ARGUMENTS.value,
                    error={
                        "message": "WebSocket request body must be valid JSON.",
                        "details": str(exc),
                    },
                )
                plugin_response = _build_plugin_stream_response(error_message)
                if not await _send_websocket_json(
                    websocket,
                    plugin_response.model_dump(mode="json", exclude_none=True),
                    operation,
                    None,
                    "final_error",
                ):
                    return
                continue
            # 同一连接可连续发送多条消息，先清理上一条消息的 requestId，
            # 避免协议归一化前的原始请求日志错误关联到旧请求。
            task_logger.set_session_id("None")
            logger.info(
                f"widget_operation_ws_raw_request_received operation={operation} "
                f"request_body={json_for_log(payload)}"
            )
            started_at = time.perf_counter()
            request_id = None
            arguments: dict[str, Any] = {}
            heartbeat_task: asyncio.Task | None = None
            metrics.task_started()
            try:
                if not isinstance(payload, dict):
                    raise ValueError("WebSocket request body must be a JSON object")
                request_id, arguments = _normalize_payload(payload, operation)
                # 解析出 requestId 后立即写入日志上下文，后续链路共用同一日志标识。
                task_logger.set_session_id(request_id or "None")
                logger.info(
                    f"{_MODULE} widget_operation_ws_payload_received request_id={request_id} "
                    f"operation={operation} payload_keys={json_for_log(sorted(payload))} "
                    f"argument_keys={json_for_log(sorted(arguments))}"
                )
                # 有 requestId 时沿用它，否则为当前消息生成稳定的流式文本 ID。
                streaming_text_id = request_id or uuid.uuid4().hex
                device_arguments = arguments.get("device")
                source_rom_version = None
                if isinstance(device_arguments, dict):
                    source_rom_version = device_arguments.pop("_sourceRomVersion", None)
                request = request_model(**arguments)
                request.device._source_rom_version = source_rom_version
                request_log = json_for_log(
                    request.model_dump(
                        mode="json",
                        exclude={"uid", "sourceArtifactUrl"},
                        exclude_none=True,
                    )
                )
                logger.info(
                    f"{_MODULE} widget_operation_ws_message_received request_id={request_id} "
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
                    f"{_MODULE} widget_operation_ws_handler_completed request_id={request_id} "
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
                plugin_response = _build_plugin_stream_response(result_message)
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
                    f"{_MODULE} widget_operation_ws_invalid_arguments request_id={request_id} "
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
                plugin_response = _build_plugin_stream_response(error_message)
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
                    f"{_MODULE} widget_operation_ws_failed request_id={request_id} "
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
                plugin_response = _build_plugin_stream_response(error_message)
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
                        logger.error(f"{_MODULE} widget_operation_ws_heartbeat_cancelled")
    except WebSocketDisconnect:
        logger.info(f"{_MODULE} widget_operation_ws_disconnected operation={operation}")
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
