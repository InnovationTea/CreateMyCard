from __future__ import annotations

import ast
import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import websockets

from .schemas import DeviceDebugContext


class UpstreamToolError(RuntimeError):
    """正式 WebSocket 调用或业务包络解析失败。"""


@dataclass(frozen=True)
class UpstreamCallResult:
    data: dict[str, Any]
    status: str
    error_code: str
    request_id: str
    error_message: str
    frames: tuple[dict[str, Any], ...]


_HEADER_PATTERN = re.compile(
    r"^type=(?P<type>'(?:\\.|[^'])*') "
    r"tool=(?P<tool>'(?:\\.|[^'])*') "
    r"operation=(?P<operation>'(?:\\.|[^'])*') "
    r"requestId=(?P<request_id>None|'(?:\\.|[^'])*')$"
)


def parse_legacy_stream_content(stream_content: str) -> dict[str, Any]:
    """安全解析正式路由返回的旧版 Pydantic 消息字符串。"""
    header_start = stream_content.find("type=")
    if header_start < 0:
        raise UpstreamToolError("final streamContent 缺少业务消息")
    legacy_content = stream_content[header_start:]
    try:
        header_text, data_and_tail = legacy_content.split(" data=", 1)
        data_text, status_and_tail = data_and_tail.rsplit(" status=", 1)
        status_text, error_code_and_tail = status_and_tail.split(" errorCode=", 1)
        error_code_text, error_text = error_code_and_tail.split(" error=", 1)
    except ValueError as exc:
        raise UpstreamToolError("final streamContent 格式不完整") from exc
    match = _HEADER_PATTERN.fullmatch(header_text)
    if match is None:
        raise UpstreamToolError("final streamContent 头部不受支持")
    try:
        return {
            "type": ast.literal_eval(match.group("type")),
            "tool": ast.literal_eval(match.group("tool")),
            "operation": ast.literal_eval(match.group("operation")),
            "requestId": ast.literal_eval(match.group("request_id")),
            "data": ast.literal_eval(data_text),
            "status": ast.literal_eval(status_text),
            "errorCode": ast.literal_eval(error_code_text),
            "error": ast.literal_eval(error_text),
        }
    except (SyntaxError, ValueError, TypeError) as exc:
        raise UpstreamToolError("final streamContent 含非法字面量") from exc


class UpstreamWebSocketClient:
    """每次 invoke 新建连接，固定调用正式回环工具路由。"""

    def __init__(self, base_url: str, bundle_name: str, timeout_seconds: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.bundle_name = bundle_name
        self.timeout_seconds = timeout_seconds

    async def invoke(
        self,
        function_name: str,
        arguments: dict[str, Any],
        context: DeviceDebugContext,
        session_id: str,
        user_query: str,
    ) -> UpstreamCallResult:
        interaction_id = uuid.uuid4().hex
        request_id = f"{session_id}&{interaction_id}"
        payload = self._build_envelope(
            function_name,
            arguments,
            context,
            session_id,
            interaction_id,
            user_query,
        )
        uri = f"{self.base_url}/api/v1/ws/tools/{function_name}"
        frames: list[dict[str, Any]] = []
        try:
            async with websockets.connect(uri, open_timeout=10, close_timeout=2) as websocket:
                await websocket.send(json.dumps(payload, ensure_ascii=False))
                while True:
                    raw = await asyncio.wait_for(websocket.recv(), self.timeout_seconds)
                    if not isinstance(raw, str):
                        raise UpstreamToolError("正式工具返回非文本 WebSocket 帧")
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise UpstreamToolError("正式工具返回非法 JSON") from exc
                    if not isinstance(frame, dict):
                        raise UpstreamToolError("正式工具返回帧不是对象")
                    frames.append(self._frame_summary(frame))
                    outer_error = frame.get("errorCode")
                    if outer_error not in (None, "", "0", 0):
                        raise UpstreamToolError(f"正式工具外层错误: {outer_error}")
                    result = self._parse_frame(frame, function_name, request_id)
                    if result is not None:
                        return UpstreamCallResult(
                            data=result["data"],
                            status=result["status"],
                            error_code=result["errorCode"],
                            request_id=request_id,
                            error_message=result["error"],
                            frames=tuple(frames),
                        )
        except TimeoutError as exc:
            raise UpstreamToolError("正式工具 WebSocket 调用超时") from exc
        except UpstreamToolError:
            raise
        except (OSError, websockets.WebSocketException) as exc:
            raise UpstreamToolError(f"正式工具 WebSocket 调用失败: {type(exc).__name__}") from exc
        raise UpstreamToolError("正式工具在 final 前断开连接")

    def _build_envelope(
        self,
        function_name: str,
        arguments: dict[str, Any],
        context: DeviceDebugContext,
        session_id: str,
        interaction_id: str,
        user_query: str,
    ) -> dict[str, Any]:
        del function_name
        business = dict(arguments)
        business.pop("bundleName", None)
        business.pop("uid", None)
        business.pop("odid", None)
        return {
            "content": {"odid": context.odid, **business},
            "deviceInfo": {
                "countryCode": context.countryCode,
                "deviceFormation": "phone",
                "deviceType": 0,
                "locale": context.locale,
                "phoneType": context.phoneType,
                "prdVer": context.appVersion,
                "sysVer": "HarmonyOS",
                "romVersion": context.romVersion,
                "deviceId": context.deviceId,
            },
            "pagination": {"limit": 5, "start": ""},
            "session": {
                "sessionId": session_id,
                "interactionId": interaction_id,
                "isNew": False,
            },
            "userAuth": {"user": {"userId": context.uid}},
            "utterance": {"original": user_query, "type": "text"},
            "version": "1.0",
            "bundleName": self.bundle_name,
        }

    @staticmethod
    def _frame_summary(frame: dict[str, Any]) -> dict[str, Any]:
        reply = frame.get("reply")
        stream_info = reply.get("streamInfo") if isinstance(reply, dict) else None
        if not isinstance(stream_info, dict):
            return {"keys": sorted(frame), "errorCode": frame.get("errorCode", "")}
        content = stream_info.get("streamContent")
        return {
            "streamType": stream_info.get("streamType", "final"),
            "textType": stream_info.get("textType", ""),
            "streamingTextId": stream_info.get("streamingTextId", ""),
            "contentChars": len(content) if isinstance(content, str) else 0,
            "errorCode": frame.get("errorCode", ""),
        }

    @staticmethod
    def _parse_frame(
        frame: dict[str, Any],
        function_name: str,
        request_id: str,
    ) -> dict[str, Any] | None:
        reply = frame.get("reply")
        stream_info = reply.get("streamInfo") if isinstance(reply, dict) else None
        if not isinstance(stream_info, dict):
            raise UpstreamToolError("正式工具帧缺少 streamInfo")
        stream_type = stream_info.get("streamType", "final")
        if stream_type in {"start", "partial", "command"}:
            return None
        if stream_type != "final":
            raise UpstreamToolError("正式工具返回未知流类型")
        content = stream_info.get("streamContent")
        if not isinstance(content, str) or not content:
            raise UpstreamToolError("正式工具 final 缺少 streamContent")
        parsed = parse_legacy_stream_content(content)
        if parsed.get("requestId") != request_id:
            raise UpstreamToolError("正式工具 requestId 与当前 invoke 不匹配")
        if parsed.get("operation") != function_name:
            raise UpstreamToolError("正式工具 operation 与当前 invoke 不匹配")
        data = parsed.get("data")
        if not isinstance(data, dict):
            data = {}
        return {
            "data": data,
            "status": str(parsed.get("status") or "failed"),
            "errorCode": str(parsed.get("errorCode") or ""),
            "error": str(parsed.get("error") or ""),
        }

