"""端到端调试平台后端与浏览器工具桥。

后端只承载主 Agent、Skill 导入和工具调用编排；三个正式微服务接口由浏览器
直接建立 WebSocket 连接，后端不再代理或探活 8855。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from debug_tools.batch_testing import register_batch_routes
from debug_tools.paths import (
    CLOUD_ROOT,
    DEBUG_TOOLS_ROOT,
    REPOSITORY_ROOT,
    WIDGET_SERVICE_ROOT,
    ensure_cloud_import_path,
)
from debug_tools.static_site import (
    FRONTEND_DIST,
    register_renderer_asset_routes,
    static_response,
)


def _discover_roots() -> tuple[Path, Path]:
    """定位 widget_service 项目根和外层仓库根，避免依赖固定 parents 层级。"""

    return WIDGET_SERVICE_ROOT, REPOSITORY_ROOT


_PROJECT_ROOT, _REPO_ROOT = _discover_roots()
_CLOUD_ROOT = str(CLOUD_ROOT)
ensure_cloud_import_path()

if TYPE_CHECKING:
    from .debug_agent.config import DebugSettings

_ALLOWED_OPERATIONS = frozenset(
    {
        "getWidgetCapabilityOverview",
        "getDataCapabilitySchemas",
        "generateWidgetCardCompactDsl",
    }
)


def create_app(
    debug_settings: DebugSettings | None = None,
    *,
    production_settings: Any | None = None,
    model_client_factory: Any | None = None,
    upstream_client: Any | None = None,
    trace_root: Path | None = None,
    gallery_base_url: str = "http://127.0.0.1:8888/debug",
) -> FastAPI:
    """创建工作台 FastAPI 应用。

    ``production_settings`` 和客户端工厂参数用于单元测试及本地调试注入；生产启动时
    会从云侧配置读取模型设置，但不会启动上游工具服务。
    """

    config_path = DEBUG_TOOLS_ROOT / "end_to_end_debug" / "backend" / "debug_agent.yaml"
    if not config_path.is_file():
        raise RuntimeError(f"debug config does not exist: {config_path}")

    from .debug_agent.config import load_debug_config

    debug_config = load_debug_config(config_path, _REPO_ROOT)
    production = production_settings or _load_production_settings(debug_config)
    local = debug_settings or _load_debug_settings(production, debug_config)
    app = FastAPI(title="AI Widget Debug Platform", version="0.1.0")
    static_dir = FRONTEND_DIST
    register_renderer_asset_routes(app)

    @app.get("/debug/health")
    async def health() -> dict[str, Any]:
        provider = str(getattr(production, "openai_master_client", "") or "")
        debug_provider = _resolve_debug_model_provider(production)
        model_key = _model_name_key(provider)
        debug_model_key = _model_name_key(debug_provider)
        return {
            "status": "ok",
            "version": app.version,
            "debugHost": local.host,
            "debugPort": local.port,
            # Do not echo the deprecated URL: legacy deployments may have
            # credentials in it, and browser-direct mode never uses it.
            "upstream": "",
            "upstreamReachable": None,
            "upstreamStatus": "browser_direct",
            "toolTransport": "browser_direct",
            "provider": provider or "未配置",
            "debugModelProvider": debug_provider,
            "debugModel": str(getattr(production, debug_model_key, "") or "未配置"),
            "model": str(getattr(production, model_key, "") or "未配置"),
            "enableArtifactDownloadMock": bool(
                getattr(production, "enable_artifact_download_mock", False)
            ),
            "enableWidgetEdit": bool(getattr(production, "enable_widget_edit", False)),
            "skillProfile": local.skill_profile,
            "skillName": local.skill_name,
            "skillProfiles": list(local.available_profiles),
        }

    @app.get("/debug/skills")
    async def skills() -> dict[str, Any]:
        return {
            "profiles": debug_config.available_profiles(),
            "selected": local.skill_profile,
            "quickPrompts": [
                {"label": item.label, "prompt": item.prompt} for item in local.quick_prompts
            ],
        }

    @app.get("/debug/artifact")
    async def artifact(url: str, digest: str = "") -> Any:
        """为卡片渲染模块读取 artifact URL，统一复用后端下载与 mock 解析。"""

        from .debug_agent.agent import _is_artifact_url
        from .debug_agent.artifact_reader import ArtifactReader

        if not _is_artifact_url(url):
            return JSONResponse({"detail": "artifact URL 不受支持"}, status_code=400)
        preview, error = await ArtifactReader().read("renderer", url, digest)
        if preview is None:
            return JSONResponse({"detail": error or "artifact 下载失败"}, status_code=404)
        return preview.model_dump(mode="json", exclude_none=True)

    @app.websocket("/debug/agent/ws")
    @app.websocket("/debug/e2e/ws")
    async def e2e_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        await _run_e2e_session(
            websocket,
            local,
            production,
            debug_config,
            model_client_factory=model_client_factory,
            upstream_client=upstream_client,
        )

    @app.websocket("/debug/tools/{operation}")
    async def tool_proxy(websocket: WebSocket, operation: str) -> None:
        """保留旧路径以返回明确迁移提示，不再把工具流量转发到 8855。"""

        await websocket.accept()
        reason = (
            "unsupported operation"
            if operation not in _ALLOWED_OPERATIONS
            else "browser must connect to the configured microservice WebSocket directly"
        )
        await websocket.send_json(
            {
                "protocolVersion": "1.0",
                "type": "error",
                "code": "BROWSER_DIRECT_REQUIRED",
                "message": reason,
            }
        )
        await websocket.close(code=1008, reason=reason)

    register_batch_routes(
        app,
        trace_root=trace_root,
        gallery_base_url=gallery_base_url,
    )

    @app.get("/debug/")
    async def debug_index() -> Any:
        return static_response(static_dir, "")

    @app.get("/debug/{asset_path:path}")
    async def debug_asset(asset_path: str) -> Any:
        """提供 SPA fallback，同时只允许读取构建目录内的文件。"""

        return static_response(static_dir, asset_path)

    return app


async def _run_e2e_session(
    websocket: WebSocket,
    settings: DebugSettings,
    production: Any,
    debug_config: Any,
    *,
    model_client_factory: Any | None,
    upstream_client: Any | None,
) -> None:
    from .debug_agent.agent import DebugAgentSession
    from .debug_agent.browser_tool_bridge import BrowserToolBridge, BrowserToolBridgeError
    from .debug_agent.config import DebugSettings
    from .debug_agent.schemas import (
        ConfigureFrame,
        DebugEvent,
        DeviceDebugContext,
        MessageFrame,
        SimpleFrame,
    )
    from .debug_agent.skill_loader import SkillLoadError

    sequence = 0
    session: DebugAgentSession | None = None
    bridge: BrowserToolBridge
    protocol_mode = "legacy"

    async def send_raw_event(payload: dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except (RuntimeError, WebSocketDisconnect) as exc:
            raise BrowserToolBridgeError("浏览器 WebSocket 已断开") from exc

    async def send_browser_event(payload: dict[str, Any]) -> None:
        """按当前 Agent 协议发送浏览器工具调用。

        新协议直接使用 dotted ``tool.call``。旧版独立调试器只认识
        ``tool_call``，因此保留一个窄适配层，避免把浏览器工具事件误当成
        Agent 内部事件或写入共享调用历史。
        """

        nonlocal sequence
        if protocol_mode == "standard":
            await send_raw_event(payload)
            if payload.get("type") == "tool.call":
                await send_raw_event(
                    {
                        "protocolVersion": "1.0",
                        "type": "turn.status",
                        "conversationId": payload.get("conversationId", ""),
                        "sessionId": payload.get("sessionId", ""),
                        "turnId": payload.get("turnId", ""),
                        "runId": payload.get("runId", ""),
                        "status": "waiting_tool",
                    }
                )
            return
        if payload.get("type") != "tool.call":
            await send_raw_event(payload)
            return
        arguments = payload.get("arguments")
        business_arguments = arguments if isinstance(arguments, dict) else {}
        function_name = str(payload.get("functionName") or payload.get("name") or "")
        legacy_arguments = json.dumps(
            {
                "skillName": payload.get("skillName") or settings.skill_name,
                "functionName": function_name,
                "arguments": business_arguments,
                "bundleName": payload.get("bundleName") or settings.bundle_name,
            },
            ensure_ascii=False,
        )
        sequence += 1
        await send_raw_event(
            DebugEvent(
                type="tool_call",
                sequence=sequence,
                sessionId=session.session_id if session is not None else "",
                runId=str(payload.get("runId") or payload.get("turnId") or ""),
                timestamp=_timestamp(),
                data={
                    "name": "invoke",
                    "callId": payload.get("callId", ""),
                    "functionName": function_name,
                    "arguments": legacy_arguments,
                    "step": payload.get("step", 0),
                },
            ).model_dump(mode="json")
        )

    bridge = BrowserToolBridge(
        send_browser_event,
        timeout_seconds=settings.request_timeout_seconds,
    )

    async def invoke_browser_tool(
        function_name: str,
        arguments: dict[str, Any],
        _context: Any,
        _session_id: str,
        _user_query: str,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
        return await bridge.invoke(function_name, arguments, **kwargs)

    # 生产路径不传入 upstream_client，因此只通过浏览器桥接微服务工具。
    # 显式注入 upstream_client 仅用于旧测试/离线调用，保留其原有行为，
    # 避免测试替身被新的浏览器等待协议阻塞。
    browser_tool_invoker = invoke_browser_tool if upstream_client is None else None

    async def send_event(event_type: str, data: dict[str, Any], run_id: str = "") -> None:
        nonlocal protocol_mode, sequence
        sequence += 1
        if session is None:
            return
        if protocol_mode == "standard":
            for event in _standard_agent_events(
                event_type,
                data,
                run_id,
                session.session_id,
            ):
                try:
                    await websocket.send_json(event)
                except (RuntimeError, WebSocketDisconnect):
                    return
            return
        event = DebugEvent(
            type=event_type,
            sequence=sequence,
            sessionId=session.session_id,
            runId=run_id,
            timestamp=_timestamp(),
            data=data,
        )
        try:
            await websocket.send_json(event.model_dump(mode="json"))
        except (RuntimeError, WebSocketDisconnect):
            return

    try:
        session = DebugAgentSession(
            settings,
            production_settings=production,
            event_sink=send_event,
            model_client_factory=model_client_factory,
            upstream_client=upstream_client,
            browser_tool_invoker=browser_tool_invoker,
        )
        bridge.set_session_id(session.session_id)
    except (ValueError, SkillLoadError) as exc:
        await websocket.send_json({"type": "diagnostic", "error": str(exc)})
        await websocket.close(code=1011)
        await bridge.close()
        return

    legacy_session_sent = False

    def session_started_data() -> dict[str, Any]:
        return {
            "skillName": settings.skill_name,
            "skillProfile": settings.skill_profile,
            "skillVersion": settings.skill_version,
            "skillProfiles": list(settings.available_profiles),
            "quickPrompts": [
                {"label": item.label, "prompt": item.prompt} for item in settings.quick_prompts
            ],
            "systemPromptPath": str(settings.system_prompt_path or ""),
            "bundleName": settings.bundle_name,
            "context": DeviceDebugContext(
                uid=settings.default_uid,
                odid=settings.default_device_id,
                deviceId=settings.default_device_id,
                phoneType=settings.default_phone_type,
                appVersion=settings.default_app_version,
                romVersion=settings.default_rom_version,
                locale=settings.default_locale,
                countryCode=settings.default_country_code,
            ).model_dump(mode="json"),
        }

    async def ensure_legacy_session() -> None:
        nonlocal legacy_session_sent
        if legacy_session_sent:
            return
        legacy_session_sent = True
        await send_event("session_started", session_started_data())

    running_task: asyncio.Task[None] | None = None
    active_turn_id = ""
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                if protocol_mode == "standard":
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "帧必须是合法 JSON",
                    )
                    continue
                await ensure_legacy_session()
                await send_event(
                    "diagnostic", {"kind": "invalid_frame", "message": "帧必须是合法 JSON"}
                )
                continue
            if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
                if protocol_mode == "standard":
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "帧类型无效",
                    )
                    continue
                await ensure_legacy_session()
                await send_event("diagnostic", {"kind": "invalid_frame", "message": "帧类型无效"})
                continue
            frame_type = payload["type"]
            if frame_type == "conversation.open":
                protocol_mode = "standard"
                if not _supported_protocol_version(payload):
                    await _send_protocol_error(
                        websocket,
                        "UNSUPPORTED_PROTOCOL_VERSION",
                        "当前仅支持 protocolVersion 1.0",
                    )
                    continue
                requested_id = payload.get("conversationId")
                requested_session_id = payload.get("sessionId")
                if requested_id is not None and not isinstance(requested_id, str):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "conversationId 必须是字符串",
                    )
                    continue
                if requested_session_id is not None and not isinstance(requested_session_id, str):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "sessionId 必须是字符串",
                    )
                    continue
                if (
                    isinstance(requested_id, str)
                    and isinstance(requested_session_id, str)
                    and requested_id.strip() != requested_session_id.strip()
                ):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "conversationId 与 sessionId 不一致",
                    )
                    continue
                if requested_id is None:
                    requested_id = requested_session_id
                requested_bundle = payload.get("bundleName")
                if requested_bundle is not None and (
                    not isinstance(requested_bundle, str)
                    or requested_bundle.strip() != settings.bundle_name
                ):
                    await _send_protocol_error(
                        websocket,
                        "BUNDLE_MISMATCH",
                        "bundleName 必须匹配当前 Agent Skill 配置",
                    )
                    continue
                requested_context = payload.get("context")
                if requested_context is not None:
                    try:
                        context = DeviceDebugContext.model_validate(requested_context)
                        if session.context is None:
                            session.configure(context)
                        elif session.context.model_dump() != context.model_dump():
                            raise ValueError("当前会话已经使用不同的设备上下文")
                    except (TypeError, ValueError) as exc:
                        await _send_protocol_error(
                            websocket,
                            "INVALID_CONTEXT",
                            str(exc),
                        )
                        continue
                resumed = isinstance(requested_id, str) and requested_id == session.session_id
                await _send_conversation_ready(
                    websocket,
                    session,
                    resumed=resumed,
                    settings=settings,
                )
                continue
            standard_frame_types = {
                "turn.start",
                "turn.cancel",
                "conversation.reset",
                "tool.result",
                "tool_result",
            }
            if protocol_mode == "standard":
                if frame_type not in standard_frame_types:
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        f"标准协议不支持帧类型：{frame_type}",
                    )
                    continue
            elif frame_type in {"turn.start", "turn.cancel", "conversation.reset"}:
                protocol_mode = "standard"
            else:
                await ensure_legacy_session()
            if protocol_mode == "standard" and not _supported_protocol_version(payload):
                await _send_protocol_error(
                    websocket,
                    "UNSUPPORTED_PROTOCOL_VERSION",
                    "当前仅支持 protocolVersion 1.0",
                )
                continue
            if frame_type == "turn.start":
                protocol_mode = "standard"
                raw_conversation_id = payload.get("conversationId")
                raw_session_id = payload.get("sessionId")
                if (
                    raw_conversation_id is not None and not isinstance(raw_conversation_id, str)
                ) or (raw_session_id is not None and not isinstance(raw_session_id, str)):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "conversationId/sessionId 必须是字符串",
                    )
                    continue
                if (
                    isinstance(raw_conversation_id, str)
                    and isinstance(raw_session_id, str)
                    and raw_conversation_id.strip() != raw_session_id.strip()
                ):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "conversationId 与 sessionId 不一致",
                    )
                    continue
                supplied_conversation_id = raw_conversation_id or raw_session_id
                conversation_id_matches = (
                    supplied_conversation_id is None
                    or supplied_conversation_id.strip() == session.session_id
                )
                if not conversation_id_matches:
                    await _send_protocol_error(
                        websocket,
                        "STALE_SESSION",
                        "conversationId 不属于当前会话",
                    )
                    continue
                if running_task is not None and not running_task.done():
                    await _send_protocol_error(websocket, "TURN_REJECTED", "已有运行中的任务")
                    continue
                text = payload.get("text")
                if not isinstance(text, str):
                    text = payload.get("content")
                if not isinstance(text, str) or not text.strip():
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "text 必须是非空字符串",
                    )
                    continue
                requested_turn_id = payload.get("turnId")
                if requested_turn_id is None:
                    requested_turn_id = payload.get("runId")
                if requested_turn_id is not None and (
                    not isinstance(requested_turn_id, str) or not requested_turn_id.strip()
                ):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "turnId 必须是非空字符串",
                    )
                    continue
                active_turn_id = (
                    requested_turn_id.strip()
                    if isinstance(requested_turn_id, str)
                    else uuid.uuid4().hex
                )
                await websocket.send_json(
                    {
                        "protocolVersion": "1.0",
                        "type": "turn.status",
                        "conversationId": session.session_id,
                        "sessionId": session.session_id,
                        "turnId": active_turn_id,
                        "runId": active_turn_id,
                        "status": "accepted",
                    }
                )
                running_task = asyncio.create_task(session.run(text, run_id=active_turn_id))
                continue
            if frame_type == "turn.cancel":
                protocol_mode = "standard"
                raw_conversation_id = payload.get("conversationId")
                raw_session_id = payload.get("sessionId")
                if (
                    raw_conversation_id is not None
                    and raw_session_id is not None
                    and raw_conversation_id != raw_session_id
                ):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "conversationId 与 sessionId 不一致",
                    )
                    continue
                supplied_conversation_id = raw_conversation_id or raw_session_id
                stale_session = (
                    supplied_conversation_id is not None
                    and supplied_conversation_id != session.session_id
                )
                if stale_session:
                    await _send_protocol_error(
                        websocket,
                        "STALE_SESSION",
                        "conversationId 不属于当前会话",
                    )
                    continue
                requested_turn_id = payload.get("turnId")
                if requested_turn_id is None:
                    requested_turn_id = payload.get("runId")
                if requested_turn_id is not None and (
                    not isinstance(requested_turn_id, str) or not requested_turn_id.strip()
                ):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "turnId 必须是非空字符串",
                    )
                    continue
                if (
                    isinstance(requested_turn_id, str)
                    and active_turn_id
                    and requested_turn_id.strip() != active_turn_id
                ):
                    await _send_protocol_error(
                        websocket,
                        "STALE_TURN",
                        "turn.cancel 的 turnId 不是当前运行回合",
                    )
                    continue
                if running_task is not None and not running_task.done():
                    await session.cancel()
                    await bridge.cancel_turn(active_turn_id)
                    running_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await running_task
                continue
            if frame_type == "conversation.reset":
                protocol_mode = "standard"
                raw_conversation_id = payload.get("conversationId")
                raw_session_id = payload.get("sessionId")
                if (
                    raw_conversation_id is not None
                    and raw_session_id is not None
                    and raw_conversation_id != raw_session_id
                ):
                    await _send_protocol_error(
                        websocket,
                        "PROTOCOL_INVALID",
                        "conversationId 与 sessionId 不一致",
                    )
                    continue
                supplied_conversation_id = raw_conversation_id or raw_session_id
                stale_session = (
                    supplied_conversation_id is not None
                    and supplied_conversation_id != session.session_id
                )
                if stale_session:
                    await _send_protocol_error(
                        websocket,
                        "STALE_SESSION",
                        "conversationId 不属于当前会话",
                    )
                    continue
                if running_task is not None and not running_task.done():
                    await session.cancel()
                    await bridge.cancel_turn(active_turn_id)
                    running_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await running_task
                await bridge.cancel_all()
                session.reset()
                bridge.set_session_id(session.session_id)
                running_task = None
                active_turn_id = ""
                await _send_conversation_ready(websocket, session, resumed=False, settings=settings)
                continue
            if frame_type in {"tool.result", "tool_result"}:
                result_payload = payload
                if frame_type == "tool_result":
                    data = payload.get("data")
                    if isinstance(data, dict):
                        result_payload = {
                            **payload,
                            **data,
                            "type": "tool.result",
                            "turnId": data.get("turnId")
                            or payload.get("turnId")
                            or payload.get("runId"),
                            "conversationId": data.get("conversationId")
                            or payload.get("conversationId")
                            or payload.get("sessionId"),
                        }
                        if "result" not in result_payload:
                            result_payload["result"] = data
                resolution = await bridge.resolve(result_payload)
                await _send_bridge_resolution(websocket, session.session_id, resolution)
                continue
            if frame_type == "configure":
                if running_task is not None and not running_task.done():
                    await send_event(
                        "diagnostic", {"kind": "busy", "message": "运行中不能修改配置"}
                    )
                    continue
                try:
                    frame = ConfigureFrame.model_validate(payload)
                    session.configure(frame.context)
                except (TypeError, ValueError) as exc:
                    await send_event("diagnostic", {"kind": "invalid_config", "message": str(exc)})
                    continue
                await send_event(
                    "diagnostic",
                    {"kind": "configured", "context": frame.context.model_dump(mode="json")},
                )
                continue
            if frame_type == "message":
                if running_task is not None and not running_task.done():
                    await send_event("diagnostic", {"kind": "busy", "message": "已有运行中的任务"})
                    continue
                try:
                    message = MessageFrame.model_validate(payload)
                except (TypeError, ValueError) as exc:
                    await send_event("diagnostic", {"kind": "invalid_message", "message": str(exc)})
                    continue
                running_task = asyncio.create_task(session.run(message.content))
                continue
            if frame_type == "cancel":
                try:
                    SimpleFrame.model_validate(payload)
                except (TypeError, ValueError) as exc:
                    await send_event("diagnostic", {"kind": "invalid_cancel", "message": str(exc)})
                    continue
                if running_task is not None and not running_task.done():
                    await session.cancel()
                    await bridge.cancel_turn(active_turn_id)
                    running_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await running_task
                continue
            if frame_type == "reset":
                try:
                    reset_frame = SimpleFrame.model_validate(payload)
                    if running_task is not None and not running_task.done():
                        await session.cancel()
                        running_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await running_task
                    await bridge.cancel_all()
                    if reset_frame.profile:
                        selected = DebugSettings.from_config(
                            debug_config,
                            production,
                            profile=reset_frame.profile,
                            log_level=settings.log_level,
                            trace=settings.log_trace,
                            port=settings.port,
                        )
                        settings = selected
                        session = DebugAgentSession(
                            settings,
                            production_settings=production,
                            event_sink=send_event,
                            model_client_factory=model_client_factory,
                            upstream_client=upstream_client,
                            browser_tool_invoker=browser_tool_invoker,
                        )
                        bridge.set_session_id(session.session_id)
                    else:
                        session.reset()
                        bridge.set_session_id(session.session_id)
                    running_task = None
                    active_turn_id = ""
                except (TypeError, ValueError) as exc:
                    await send_event("diagnostic", {"kind": "invalid_reset", "message": str(exc)})
                    continue
                sequence = 0
                await send_event(
                    "session_reset",
                    {
                        "skillName": settings.skill_name,
                        "skillProfile": settings.skill_profile,
                        "skillProfiles": list(settings.available_profiles),
                        "quickPrompts": [
                            {"label": item.label, "prompt": item.prompt}
                            for item in settings.quick_prompts
                        ],
                    },
                )
                continue
            await send_event("diagnostic", {"kind": "unknown_frame", "message": frame_type})
    except WebSocketDisconnect:
        return
    finally:
        if running_task is not None and not running_task.done():
            running_task.cancel()
            with suppress(asyncio.CancelledError):
                await running_task
        await bridge.close()


async def _send_bridge_resolution(
    websocket: WebSocket,
    session_id: str,
    resolution: Any,
) -> None:
    """把浏览器工具结果的接受/拒绝状态回传给协议客户端。"""

    if resolution.accepted:
        event_type = "tool.result.duplicate" if resolution.duplicate else "tool.result.accepted"
        payload = {
            "protocolVersion": "1.0",
            "type": event_type,
            "conversationId": session_id,
            "sessionId": session_id,
            "turnId": resolution.turn_id,
            "runId": resolution.turn_id,
            "callId": resolution.call_id,
            "operation": resolution.operation,
            "duplicate": resolution.duplicate,
        }
    else:
        payload = {
            "protocolVersion": "1.0",
            "type": "tool.result.rejected",
            "conversationId": session_id,
            "sessionId": session_id,
            "turnId": resolution.turn_id,
            "runId": resolution.turn_id,
            "callId": resolution.call_id,
            "operation": resolution.operation,
            "code": resolution.code or "INVALID_RESULT",
            "message": resolution.message or "tool.result 被拒绝",
        }
    with suppress(RuntimeError, WebSocketDisconnect):
        await websocket.send_json(payload)


def _standard_agent_events(
    event_type: str,
    data: dict[str, Any],
    run_id: str,
    session_id: str,
) -> tuple[dict[str, Any], ...]:
    """把当前 AgentSession 的旧事件映射为浏览器 Agent 协议事件。"""

    protocol = "1.0"
    if event_type == "run_started":
        return (
            {
                "protocolVersion": protocol,
                "type": "turn.status",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "status": "thinking",
                "query": data.get("query", ""),
            },
        )
    if event_type == "assistant_message":
        return (
            {
                "protocolVersion": protocol,
                "type": "assistant.message",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "content": data.get("content", ""),
            },
        )
    if event_type == "tool_call":
        # Cloud 工具的 raw tool.call 已由 BrowserToolBridge 发出。Skill
        # 加载及其它后端工具仍通过 trace 暴露给端到端检查器，但不会进入
        # 左侧共享微服务调用历史。
        tool_name = str(data.get("name") or "")
        function_name = str(data.get("functionName") or "")
        if tool_name == "invoke" and function_name in _ALLOWED_OPERATIONS:
            return ()
        return (
            {
                "protocolVersion": protocol,
                "type": "tool.trace",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "callId": data.get("callId", ""),
                "name": tool_name,
                "functionName": function_name,
                "arguments": data.get("arguments", ""),
                "status": "started",
            },
        )
    if event_type == "tool_result":
        result = data.get("result", {})
        tool_name = str(data.get("name") or "")
        function_name = str(data.get("functionName") or "")
        if tool_name == "load_skill" or (
            tool_name == "invoke" and function_name not in _ALLOWED_OPERATIONS
        ):
            result_failed = isinstance(result, dict) and (
                result.get("ok") is False
                or result.get("status") in {"failed", "error", "final_error"}
            )
            return (
                {
                    "protocolVersion": protocol,
                    "type": "tool.trace",
                    "conversationId": session_id,
                    "sessionId": session_id,
                    "turnId": run_id,
                    "runId": run_id,
                    "callId": data.get("callId", ""),
                    "name": tool_name,
                    "functionName": function_name,
                    "result": result,
                    "status": "failed" if result_failed else "completed",
                },
            )
        result_failed = isinstance(result, dict) and (
            result.get("ok") is False or result.get("status") in {"failed", "error", "final_error"}
        )
        return (
            {
                "protocolVersion": protocol,
                "type": "tool.trace",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "callId": data.get("callId", ""),
                "name": data.get("name", ""),
                "functionName": data.get("functionName", ""),
                "result": result,
                "status": "failed" if result_failed else "completed",
            },
        )
    if event_type == "run_completed":
        return (
            {
                "protocolVersion": protocol,
                "type": "turn.completed",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "status": "completed",
                **data,
            },
        )
    if event_type == "run_cancelled":
        return (
            {
                "protocolVersion": protocol,
                "type": "turn.completed",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "status": "cancelled",
            },
        )
    if event_type == "run_failed":
        message = str(data.get("error") or "Agent 运行失败")
        return (
            {
                "protocolVersion": protocol,
                "type": "error",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "code": "AGENT_RUNTIME_ERROR",
                "message": message,
            },
            {
                "protocolVersion": protocol,
                "type": "turn.completed",
                "conversationId": session_id,
                "sessionId": session_id,
                "turnId": run_id,
                "runId": run_id,
                "status": "failed",
            },
        )
    if event_type == "artifact_preview":
        return (
            {
                "protocolVersion": protocol,
                "type": event_type,
                "conversationId": session_id,
                "sessionId": session_id,
                "runId": run_id,
                "turnId": run_id,
                "data": data,
            },
        )
    if event_type == "diagnostic":
        return (
            {
                "protocolVersion": protocol,
                "type": event_type,
                "conversationId": session_id,
                "sessionId": session_id,
                "runId": run_id,
                "turnId": run_id,
                "data": data,
            },
        )
    return (
        {
            "protocolVersion": protocol,
            "type": event_type,
            "conversationId": session_id,
            "sessionId": session_id,
            "runId": run_id,
            "turnId": run_id,
            "data": data,
        },
    )


async def _send_protocol_error(websocket: WebSocket, code: str, message: str) -> None:
    with suppress(RuntimeError, WebSocketDisconnect):
        await websocket.send_json(
            {
                "protocolVersion": "1.0",
                "type": "error",
                "code": code,
                "message": message,
            }
        )


def _supported_protocol_version(payload: dict[str, Any]) -> bool:
    value = payload.get("protocolVersion")
    return value is None or value == "1.0"


async def _send_conversation_ready(
    websocket: WebSocket,
    session: Any,
    *,
    resumed: bool,
    settings: Any,
) -> None:
    with suppress(RuntimeError, WebSocketDisconnect):
        await websocket.send_json(
            {
                "protocolVersion": "1.0",
                "type": "conversation.ready",
                "conversationId": session.session_id,
                "sessionId": session.session_id,
                "resumed": resumed,
                "hasArtifact": bool(session.artifacts),
                "skillName": settings.skill_name,
                "skillProfile": settings.skill_profile,
                "skillVersion": settings.skill_version,
                "skillProfiles": list(settings.available_profiles),
                "quickPrompts": [
                    {"label": item.label, "prompt": item.prompt} for item in settings.quick_prompts
                ],
            }
        )


def _load_production_settings(debug_config: Any) -> Any:
    _ensure_cloud_import_path()
    from config.config import Settings

    from .debug_agent.config import load_main_agent_model_settings

    return load_main_agent_model_settings(debug_config, Settings)


def _load_debug_settings(production: Any, debug_config: Any) -> DebugSettings:
    from .debug_agent.config import DebugSettings

    settings = DebugSettings.from_config(
        debug_config,
        production,
        profile=os.getenv("DEBUG_AGENT_PROFILE"),
        port=int(os.getenv("DEBUG_AGENT_PORT", "8888")),
        log_level=os.getenv("DEBUG_AGENT_LOG_LEVEL"),
        trace=True,
    )
    upstream = os.getenv("DEBUG_AGENT_UPSTREAM_URL")
    if upstream:
        from dataclasses import replace

        settings = replace(settings, upstream_base_url=upstream)
    return settings


def _ensure_cloud_import_path() -> None:
    ensure_cloud_import_path()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolve_debug_model_provider(settings: Any) -> str:
    """返回调试 Agent 实际使用的模型传输。"""

    provider = str(getattr(settings, "openai_master_client", "") or "")
    return provider or "未配置"


def _model_name_key(provider: str) -> str:
    if provider == "deepseek_platform":
        return "deepseek_platform_model_name"
    if provider == "deepseek_official_http":
        return "deepseek_official_http_model"
    return "deepseek_model"


__all__ = ["create_app"]
