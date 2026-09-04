# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import hashlib
import json
import time
import traceback
import uuid
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    ToolRequestEnvelope,
    VersionedToolRequest,
)
from app.logger import (
    _sanitize_json_log_value,
    json_for_log,
    logger,
    task_logger,
)
from app.websocket_metrics import websocket_metrics
from config.config import get_settings
from core.errors import ErrorCode
from custom.model_runtime import ModelExecutionRuntime
from models.generation import DEFAULT_WIDGET_SIZE, ModelRequestContext, WidgetSize
from models.preflight import GenerationPreflightError
from models.service import (
    WidgetPluginReply,
    WidgetPluginStreamResponse,
    WidgetStreamInfo,
    WidgetWebSocketErrorMessage,
    WidgetWebSocketResultMessage,
)
from services.capability_registry import CapabilityRegistry
from services.widget_directive import (
    WidgetDirectiveState,
    build_widget_directive_response,
)
from services.widget_generation_service import WidgetGenerationService

_MODULE = "[WS Router]"

router = APIRouter(prefix="/api/v1")

COMPACT_DSL_OPERATION = "generateWidgetCardCompactDsl"
COMPACT_DSL_TRANSPORT_CONTENT_KEYS = frozenset(
    {
        "uid",
        "odid",
        "romVersion",
        "bundleName",
    }
)
GENERATION_OPERATIONS = frozenset(
    {
        "generateWidgetCard",
        COMPACT_DSL_OPERATION,
        "generateWidgetCardTerseDslNested2",
    }
)
ERROR_EXPLANATIONS = {
    ErrorCode.INVALID_ARGUMENTS.value: (
        "工具参数传入有误，请按 details.issues 修正全部必填字段、类型和取值后再调用；"
        "不要只修第一项或原样重试。报错信息如下"
    ),
    ErrorCode.UNKNOWN_CAPABILITY.value: (
        "工具参数中包含未注册的能力 ID，请重新获取能力概述，并仅使用返回的能力 ID；"
        "随后继续修正 details.issues 中的其它问题。报错信息如下"
    ),
    ErrorCode.WRITE_RESULT_CONFLICT.value: (
        "多个数据能力的写入路径存在冲突，请调整 writeResultTo，"
        "避免路径相同、嵌套或相互覆盖，并继续修正 details.issues 中的其它问题。报错信息如下"
    ),
    ErrorCode.NO_EFFECTIVE_CAPABILITY.value: (
        "本次请求没有可用于生成卡片的有效能力，请检查候选能力、参数和设备可用性后重新规划。报错信息如下"
    ),
    ErrorCode.PROTOCOL_CAPABILITY_UNSUPPORTED.value: (
        "当前指定的 DSL 协议不支持本次请求中的动态能力或编辑模式，"
        "请改为静态新建请求，"
        "或选择支持对应能力的生成接口。报错信息如下"
    ),
    ErrorCode.APP_VERSION_UNSUPPORTED.value: (
        "当前设备的 App 或 ROM 版本不在服务支持范围内，请停止继续生成，并向用户说明版本暂不支持。"
        "报错信息如下"
    ),
    ErrorCode.PACKAGE_NOT_INSTALLED.value: (
        "当前设备未安装能力依赖的应用，请移除对应候选能力，或提示用户安装依赖应用后重试。报错信息如下"
    ),
    ErrorCode.A2UI_GENERATION_FAILED.value: (
        "卡片生成模型调用失败，或模型没有返回有效 DSL；"
        "本次没有可继续处理的卡片结果，建议稍后重新调用。"
        "报错信息如下"
    ),
    ErrorCode.VALIDATION_FAILED.value: (
        "模型生成的卡片 DSL 存在 error 级校验问题，且当前结果未通过修复校验，"
        "请结合错误位置重新生成。"
        "报错信息如下"
    ),
    ErrorCode.ARTIFACT_UPLOAD_FAILED.value: (
        "卡片内容已经生成，但产物保存或上传失败，当前没有可用的 artifactUrl，"
        "建议稍后重新调用。报错信息如下"
    ),
    ErrorCode.WIDGET_EDIT_DISABLED.value: (
        "当前服务没有开启卡片编辑功能，无法处理 sourceArtifactUrl；"
        "请改为新建卡片，或开启编辑功能后重试。"
        "报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_NOT_FOUND.value: (
        "没有找到待编辑的来源卡片产物，请检查 sourceArtifactUrl 是否正确，"
        "或重新创建卡片。报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_DOWNLOAD_FAILED.value: (
        "待编辑的来源卡片产物下载失败，请检查 sourceArtifactUrl 的可访问性后重试。报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_SCHEMA_UNSUPPORTED.value: (
        "待编辑的来源卡片产物版本或结构不受当前服务支持，请重新创建卡片，不要继续沿用该产物。报错信息如下"
    ),
    ErrorCode.SOURCE_ARTIFACT_INVALID.value: (
        "待编辑的来源卡片产物内容无效或不完整，请检查来源产物，或重新创建卡片。报错信息如下"
    ),
    ErrorCode.TIMEOUT.value: (
        "工具执行超时，本次调用未在限定时间内完成，建议稍后重试；不要把本次结果当作成功结果。报错信息如下"
    ),
}
DEFAULT_ERROR_EXPLANATION = (
    "工具执行过程中发生未分类的服务异常，本次调用未成功完成，建议稍后重试。报错信息如下"
)


class StringifiedToolArgumentsError(ValueError):
    """表示主 Agent 把工具 arguments 错误序列化成了 JSON 字符串。"""

    error_code = ErrorCode.INVALID_ARGUMENTS

    def __init__(self) -> None:
        super().__init__("tool arguments must be a JSON object instead of a JSON string")

    def details(self) -> dict[str, Any]:
        """构造保持插件包络格式的可执行修复说明。"""
        return {
            "stage": "requestEnvelope",
            "modelCalled": False,
            "retryable": True,
            "requiredActions": ["FIX_AND_RETRY"],
            "agentInstruction": (
                "调用 generateWidgetCardCompactDsl 时，arguments 必须直接传合法的 "
                "JSON 对象，不能把整个对象序列化成 JSON 字符串。请保持 arguments、"
                "functionName、skillName 同层，并把 bundleName、userQuery、title、"
                "description 等工具字段放入 arguments 对象后重新调用。"
            ),
            "issues": [
                {
                    "code": "STRINGIFIED_TOOL_ARGUMENTS",
                    "path": "/arguments",
                    "message": "工具调用的 arguments 被错误地传成了 JSON 字符串。",
                    "expected": "arguments must be a JSON object",
                    "actualType": "string",
                    "agentAction": "FIX_AND_RETRY",
                    "retryable": True,
                    "capabilityId": "",
                    "repairInstruction": (
                        "将 arguments 字符串反序列化为 JSON 对象；保留 functionName 和 skillName 为"
                        " arguments 的同层字段，不要在 arguments 内再次嵌套工具调用外层。"
                    ),
                    "referenceSource": "generateWidgetCardCompactDsl tool schema",
                }
            ],
            "warnings": [],
        }


def get_service(
    model_runtime: ModelExecutionRuntime | None = None,
) -> WidgetGenerationService:
    """创建卡片生成服务对象。

    入参：无。
    出参：WidgetGenerationService 实例。
    """
    return WidgetGenerationService(model_runtime=model_runtime)


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


def _request_id_from_raw_payload(payload: Any) -> str | None:
    """在完整协议校验前，从原始请求中提取稳定的 requestId。"""
    if not isinstance(payload, dict):
        return None
    session = payload.get("session")
    if isinstance(session, dict):
        session_id = str(session.get("sessionId") or "").strip()
        interaction_id = str(session.get("interactionId") or "").strip()
        if session_id and interaction_id:
            return f"{session_id}&{interaction_id}"
        if session_id:
            return session_id
    request_id = payload.get("requestId")
    if request_id is None:
        return None
    return str(request_id).strip() or None


def _normalize_directive_size(
    value: Any,
    fallback: WidgetSize = DEFAULT_WIDGET_SIZE,
) -> WidgetSize:
    """将指令尺寸限制为服务支持的标准值。"""
    if value == "2x4":
        return "2x4"
    if value == "2x2":
        return "2x2"
    return fallback


def _directive_size_from_raw_payload(payload: Any) -> WidgetSize:
    """在请求模型构造前读取显式尺寸，缺失或非法时使用首次生成默认值。"""
    if not isinstance(payload, dict):
        return DEFAULT_WIDGET_SIZE
    content = payload.get("content")
    if not isinstance(content, dict):
        return DEFAULT_WIDGET_SIZE
    return _normalize_directive_size(content.get("size"))


def _raw_device_rom_version(
    device_info: dict[str, Any],
    content_rom_version: Any = None,
) -> str:
    """按 content、deviceInfo、默认配置的顺序选择完整 ROM 版本。"""
    if content_rom_version is not None and str(content_rom_version).strip():
        return str(content_rom_version)
    device_rom_version = device_info.get("romVersion")
    if device_rom_version is not None and str(device_rom_version).strip():
        return str(device_rom_version)
    return get_settings().default_device_rom_version


def _pick_device_rom_version(
    device_info: dict[str, Any],
    content_rom_version: Any = None,
) -> str:
    """优先读取 content.romVersion，并归一化为内部 ROM 版本。

    入参：
    - device_info：外部请求中的 deviceInfo 字典。
    - content_rom_version：content 中可选的完整 ROM 版本。
    出参：内部 DeviceContext 使用的 romVersion。
    """
    raw_rom_version = _raw_device_rom_version(device_info, content_rom_version)
    return CapabilityRegistry.normalize_rom_version(raw_rom_version)


def _device_context_from_envelope(
    envelope: ToolRequestEnvelope,
    odid: Any = None,
    content_rom_version: Any = None,
) -> dict[str, Any]:
    """把外部设备信息转换成内部 DeviceContext 字典。

    入参：
    - envelope：已经解析后的 WebSocket 外部请求包络。
    - odid：content 中可选的设备 odid。
    - content_rom_version：content 中可选且优先使用的完整 ROM 版本。
    出参：可直接传给 DeviceContext 的字典。
    """
    device_info = envelope.deviceInfo.model_dump(mode="json", exclude_none=True)
    phone_type = device_info.get("phoneType")
    raw_rom_version = _raw_device_rom_version(device_info, content_rom_version)
    return {
        "deviceId": device_info.get("deviceId"),
        "deviceType": phone_type or str(device_info.get("deviceType", "")),
        "sysVersion": device_info.get("sysVer"),
        "deviceName": device_info.get("deviceFormation"),
        "odid": odid,
        "udid": device_info.get("udid"),
        "romVersion": _pick_device_rom_version(device_info, content_rom_version),
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
    content_uid = arguments.pop("uid", None)
    content_rom_version = arguments.pop("romVersion", None)
    if operation in GENERATION_OPERATIONS and not arguments.get("userQuery"):
        arguments["userQuery"] = envelope.utterance.original if envelope.utterance else ""
    arguments["uid"] = _first_text(content_uid, envelope.userAuth.user.userId)
    arguments["locale"] = envelope.deviceInfo.locale or "zh-CN"
    arguments["prdVer"] = envelope.deviceInfo.prdVer
    arguments["device"] = _device_context_from_envelope(
        envelope,
        odid,
        content_rom_version,
    )
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
        _validate_compact_dsl_content(payload, operation)
        envelope = ToolRequestEnvelope(**payload)
        return _request_id_from_envelope(envelope), _arguments_from_envelope(
            envelope, operation
        )
    return payload.get("requestId"), payload.get("arguments", payload)


def _validate_compact_dsl_content(
    payload: dict[str, Any],
    operation: str,
) -> None:
    """识别工具层映射后可见的字符串化 arguments 错误。"""
    if operation != COMPACT_DSL_OPERATION:
        return
    content = payload.get("content")
    if not isinstance(content, dict):
        return
    if isinstance(content.get("arguments"), str):
        raise StringifiedToolArgumentsError()
    if set(content) == COMPACT_DSL_TRANSPORT_CONTENT_KEYS:
        # arguments 为字符串时，部分工具层不会展开业务字段，只保留自动透传字段。
        raise StringifiedToolArgumentsError()


def _mapping(value: Any) -> dict[str, Any]:
    """把请求中的可选对象安全归一化为字典。"""
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any, default: str = "") -> str:
    """按顺序选择第一个非空值并转换为字符串。"""
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return default


def _request_trace_hashes(payload: dict[str, Any]) -> dict[str, str]:
    """从新旧工具包络提取用户、设备标识并生成不可逆排障摘要。"""
    content = _mapping(payload.get("content"))
    arguments = _mapping(payload.get("arguments"))
    user_auth = _mapping(payload.get("userAuth"))
    user = _mapping(user_auth.get("user"))
    legacy_device = _mapping(arguments.get("device"))
    user_value = _first_text(
        content.get("uid"),
        user.get("userId"),
        arguments.get("uid"),
        payload.get("uid"),
    )
    device_value = _first_text(
        content.get("odid"),
        legacy_device.get("odid"),
        arguments.get("odid"),
        payload.get("odid"),
    )
    return {
        "user_trace_hash": _sha256_trace_value(user_value),
        "device_trace_hash": _sha256_trace_value(device_value),
    }


def _combined_request_trace_hash(trace_hashes: dict[str, str]) -> str:
    """使用 & 拼接用户和设备的脱敏排障摘要。"""
    user_trace_hash = trace_hashes.get("user_trace_hash", "")
    device_trace_hash = trace_hashes.get("device_trace_hash", "")
    if not user_trace_hash or not device_trace_hash:
        return "None"
    return f"{user_trace_hash}&{device_trace_hash}"


def _sha256_trace_value(value: Any) -> str:
    """为非空排障标识生成稳定的 SHA-256 摘要。"""
    if value is None or not str(value).strip():
        return ""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _raw_request_for_log(payload: dict[str, Any]) -> str:
    """始终移除入口请求中的敏感标识后再序列化。"""
    return json_for_log(_sanitize_json_log_value(payload))


def _model_request_context_from_payload(
    payload: dict[str, Any],
    request: VersionedToolRequest,
) -> ModelRequestContext:
    """从原始工具请求构造模型服务使用的稳定动态上下文。"""
    settings = get_settings()
    session = _mapping(payload.get("session"))
    device_info = _mapping(payload.get("deviceInfo"))
    content = _mapping(payload.get("content"))
    arguments = _mapping(payload.get("arguments"))
    session_id = _first_text(session.get("sessionId"), default=uuid.uuid4().hex)
    interaction_id = _first_text(
        session.get("interactionId"),
        default=uuid.uuid4().hex,
    )
    device_id = _first_text(
        session.get("deviceId"),
        device_info.get("deviceId"),
        request.device.deviceId,
        default=f"aiwidget-{uuid.uuid4().hex}",
    )
    app_version = _first_text(
        session.get("clientVersion"),
        session.get("prdVer"),
        device_info.get("prdVer"),
        request.prdVer,
        default=settings.default_prd_version,
    )
    app_name = _first_text(
        session.get("packageName"),
        payload.get("bundleName"),
        content.get("bundleName"),
        arguments.get("bundleName"),
        default=settings.deepseek_platform_default_app_name,
    )
    country_code = _first_text(
        device_info.get("countryCode"),
        default=settings.deepseek_platform_default_country_code,
    )
    return ModelRequestContext(
        session_id=session_id,
        interaction_id=interaction_id,
        device_id=device_id,
        country_code=country_code,
        app_version=app_version,
        app_name=app_name,
    )


def _error_details(
    exc: ValidationError | ValueError,
) -> dict[str, Any] | list[dict[str, Any]] | str:
    """将参数异常转换成可序列化详情。

    入参：
    - exc：Pydantic 校验异常或业务参数异常。
    出参：可写入 WebSocket 错误消息的详情对象。
    """
    if isinstance(exc, StringifiedToolArgumentsError):
        return exc.details()
    if isinstance(exc, GenerationPreflightError):
        return exc.details()
    if isinstance(exc, ValidationError):
        # Pydantic 的 ctx 可能携带原生 ValueError，input 可能包含完整请求或注册表；
        # 二者既不适合对外返回，也可能导致错误响应再次序列化失败。
        return exc.errors(include_context=False, include_input=False)
    return str(exc)


def _value_error_code(exc: ValueError) -> str:
    """读取业务参数异常的错误码，普通参数错误保持原有错误码。"""
    error_code = getattr(exc, "error_code", ErrorCode.INVALID_ARGUMENTS)
    if isinstance(error_code, ErrorCode):
        return error_code.value
    return str(error_code)


def _build_plugin_stream_response(
    legacy_message: WidgetWebSocketResultMessage | WidgetWebSocketErrorMessage,
    streaming_text_id: str | None = None,
) -> WidgetPluginStreamResponse:
    """把旧版完整消息转换成华为流处理插件输出包络。

    入参：
    - legacy_message：旧版 WebSocket 完整出参。
    出参：插件顶层始终成功；业务异常说明和完整旧消息放入 streamContent。
    """
    resolved_streaming_text_id = streaming_text_id or legacy_message.requestId or uuid.uuid4().hex
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
                streamingTextId=resolved_streaming_text_id,
            ),
            items=[],
        ),
    )


def _error_explanation(error_code: str) -> str:
    """把内部错误码转换成主 Agent 可理解、可采取下一步动作的异常说明。"""
    if not error_code:
        return ""
    return ERROR_EXPLANATIONS.get(error_code, DEFAULT_ERROR_EXPLANATION)


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


async def _send_widget_directive_command(
    websocket: WebSocket,
    raw_payload: dict[str, Any],
    operation: str,
    request_id: str | None,
    streaming_text_id: str,
    state: WidgetDirectiveState,
    card_id: str,
    size: WidgetSize,
    artifact_url: str = "",
) -> bool:
    """按开关发送生成进度指令，不改变原有业务帧和异常处理。"""
    if not _widget_directive_commands_enabled():
        return True
    response = build_widget_directive_response(
        raw_payload,
        state,
        streaming_text_id,
        card_id,
        request_id or "",
        size,
        artifact_url,
    )
    return await _send_websocket_json(
        websocket,
        response.model_dump(mode="json", exclude_none=True),
        operation,
        request_id,
        f"command_{state.value}",
    )


def _widget_directive_commands_enabled() -> bool:
    """判断当前生成接口是否需要下发端侧卡片指令。"""
    return get_settings().enable_widget_directive_commands


def _generation_result_directive(
    result_data: dict[str, Any],
) -> tuple[WidgetDirectiveState, str]:
    """根据生成结果是否具有有效 artifact 地址选择结束指令。"""
    status = result_data.get("status")
    artifact_url = result_data.get("artifactUrl")
    valid_artifact_url = isinstance(artifact_url, str) and bool(artifact_url.strip())
    if status in {"success", "degraded"} and valid_artifact_url:
        return WidgetDirectiveState.SUCCESS, artifact_url
    return WidgetDirectiveState.FAILURE, ""


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
        return
    except Exception:
        logger.error(f"{_MODULE} widget_operation_ws_heartbeat_failed", exc_info=True)


async def _serve_operation_websocket(
    websocket: WebSocket,
    operation: str,
    request_model: type[BaseModel],
    handler,
    heartbeat: bool = False,
    heartbeat_interval: float = 6.0,
    handler_in_threadpool: bool = True,
) -> None:
    """承载单个工具能力的 WebSocket 循环。

    每条消息依次经过：原始日志、协议归一化、start/heartbeat、业务调用和 final 封装。
    同步查询在线程池执行，长耗时生成链路直接等待异步 service。

    入参：
    - websocket：客户端 WebSocket 连接。
    - operation：当前 WS path 对应的能力名。
    - request_model：当前能力的入参实体类。
    - handler：当前能力对应的 service 方法。
    - handler_in_threadpool：同步查询为 true，异步生成链路为 false。
    出参：无；服务端通过 WebSocket 返回华为流处理插件格式消息。
    """
    # 每个 WS path 只承载一个业务能力，客户端不需要再传 operation 字段。
    metrics = websocket_metrics
    await websocket.accept()
    metrics.connection_opened()
    logger.info(f"{_MODULE} widget_operation_ws_connected operation={operation}")
    try:
        model_runtime = getattr(websocket.app.state, "model_runtime", None)
        service = get_service(model_runtime)
        while True:
            card_id = str(uuid.uuid4())
            directive_size = DEFAULT_WIDGET_SIZE
            widget_directive_started = False
            try:
                raw_request_body = await websocket.receive_text()
                payload = json.loads(raw_request_body)
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
                streaming_text_id = uuid.uuid4().hex
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    streaming_text_id,
                )
                if not await _send_websocket_json(
                    websocket,
                    plugin_response.model_dump(mode="json", exclude_none=True),
                    operation,
                    None,
                    "final_error",
                ):
                    return
                continue
            # 完整协议校验前只提取关联 ID，保证原始请求日志也能归属当前轮次。
            raw_request_id = _request_id_from_raw_payload(payload)
            directive_size = _directive_size_from_raw_payload(payload)
            trace_hashes = _request_trace_hashes(payload)
            combined_trace_hash = _combined_request_trace_hash(trace_hashes)
            task_logger.set_user_device_trace(combined_trace_hash)
            task_logger.set_session_id(raw_request_id or "None")
            logger.info(
                f"widget_operation_ws_raw_request_received operation={operation} "
                f"user_trace_hash={trace_hashes['user_trace_hash']} "
                f"device_trace_hash={trace_hashes['device_trace_hash']} "
                f"request_body={_raw_request_for_log(payload)}"
            )
            started_at = time.perf_counter()
            request_id = raw_request_id
            arguments: dict[str, Any] = {}
            heartbeat_task: asyncio.Task | None = None
            streaming_text_id = request_id or uuid.uuid4().hex
            metrics.task_started()
            try:
                if not isinstance(payload, dict):
                    raise ValueError("WebSocket request body must be a JSON object")
                request_id, arguments = _normalize_payload(payload, operation)
                # 解析出 requestId 后立即写入日志上下文，后续链路共用同一日志标识。
                task_logger.set_user_device_trace(combined_trace_hash)
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
                request._raw_request_body = raw_request_body
                if operation in GENERATION_OPERATIONS:
                    request._model_request_context = _model_request_context_from_payload(
                        payload,
                        request,
                    )
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
                if handler_in_threadpool:
                    result = await run_in_threadpool(handler, service, request)
                else:
                    # 心跳通道断开不取消内部生成、repair 或 artifact 保存。
                    async def send_model_start_command(
                        resolved_size: WidgetSize,
                        raw_payload=payload,
                        current_request_id=request_id,
                        current_streaming_text_id=streaming_text_id,
                        current_card_id=card_id,
                    ) -> None:
                        nonlocal directive_size, widget_directive_started
                        directive_size = resolved_size
                        command_enabled = _widget_directive_commands_enabled()
                        command_sent = await _send_widget_directive_command(
                            websocket,
                            raw_payload,
                            operation,
                            current_request_id,
                            current_streaming_text_id,
                            WidgetDirectiveState.START,
                            current_card_id,
                            resolved_size,
                        )
                        if command_enabled and command_sent:
                            widget_directive_started = True

                    result = await handler(service, request, send_model_start_command)
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
                if operation in GENERATION_OPERATIONS and widget_directive_started:
                    directive_state, artifact_url = _generation_result_directive(result_data)
                    directive_size = _normalize_directive_size(
                        result_data.get("suggestSize"),
                        directive_size,
                    )
                    if not await _send_widget_directive_command(
                        websocket,
                        payload,
                        operation,
                        request_id,
                        streaming_text_id,
                        directive_state,
                        card_id,
                        directive_size,
                        artifact_url,
                    ):
                        return
                plugin_response = _build_plugin_stream_response(
                    result_message,
                    streaming_text_id,
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
                error_code = _value_error_code(exc)
                logger.error(
                    f"{_MODULE} widget_operation_ws_invalid_arguments request_id={request_id} "
                    f"operation={operation} duration_ms={duration_ms} "
                    f"error_code={error_code} "
                    f"details={json_for_log(_error_details(exc))} "
                    f"exception_type={type(exc).__name__} exception={exc!r} "
                    f"traceback={traceback.format_exc()}"
                )
                error_message = WidgetWebSocketErrorMessage(
                    tool=operation,
                    operation=operation,
                    requestId=request_id,
                    errorCode=error_code,
                    error={
                        "message": f"Invalid {operation} arguments.",
                        "details": _error_details(exc),
                    },
                )
                if operation in GENERATION_OPERATIONS and widget_directive_started:
                    raw_payload = payload if isinstance(payload, dict) else {}
                    if not await _send_widget_directive_command(
                        websocket,
                        raw_payload,
                        operation,
                        request_id,
                        streaming_text_id,
                        WidgetDirectiveState.FAILURE,
                        card_id,
                        directive_size,
                    ):
                        return
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    streaming_text_id,
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
                if operation in GENERATION_OPERATIONS and widget_directive_started:
                    raw_payload = payload if isinstance(payload, dict) else {}
                    if not await _send_widget_directive_command(
                        websocket,
                        raw_payload,
                        operation,
                        request_id,
                        streaming_text_id,
                        WidgetDirectiveState.FAILURE,
                        card_id,
                        directive_size,
                    ):
                        return
                plugin_response = _build_plugin_stream_response(
                    error_message,
                    streaming_text_id,
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
                    with suppress(asyncio.CancelledError):
                        await heartbeat_task
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
        lambda service, request, before_model_call: service.generate_widget_card_a2ui_form(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
    )


@router.websocket("/ws/tools/generateWidgetCardCompactDsl")
async def generate_widget_card_compact_dsl_ws(websocket: WebSocket):
    """Compact DSL 卡片生成 WebSocket 入口。"""
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCardCompactDsl",
        GenerateWidgetCardRequest,
        lambda service, request, before_model_call: service.generate_widget_card_compact_dsl(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
    )


@router.websocket("/ws/tools/generateWidgetCardTerseDslNested2")
async def generate_widget_card_terse_dsl_nested2_ws(websocket: WebSocket):
    """TerseDSL-Nested-2 卡片生成 WebSocket 入口。"""
    await _serve_operation_websocket(
        websocket,
        "generateWidgetCardTerseDslNested2",
        GenerateWidgetCardRequest,
        lambda service, request, before_model_call: service.generate_widget_card_terse_dsl_nested2(
            request,
            before_model_call=before_model_call,
        ),
        heartbeat=True,
        heartbeat_interval=6.0,
        handler_in_threadpool=False,
    )
