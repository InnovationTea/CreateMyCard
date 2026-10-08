"""浏览器侧微服务工具桥。

端到端调试的主 Agent 运行在调试后端，但三个正式微服务工具必须由浏览器
直接建立 WebSocket 连接。该模块只负责把后端产生的工具调用挂起，发送一个
标准 ``tool.call`` 事件，并在收到匹配的 ``tool.result`` 后恢复模型循环。

这里不持有任何微服务 WebSocket 客户端，也不负责解析微服务的流式帧。浏览器
应当只把 final 帧整理成 ``result`` 回传；后端只校验关联 ID、结果大小和结果
的基本结构。
"""

from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


class BrowserToolBridgeError(RuntimeError):
    """浏览器工具桥无法完成一次调用。"""


@dataclass(frozen=True)
class BrowserToolResolution:
    """处理 ``tool.result`` 后返回给 WebSocket 路由的状态。"""

    accepted: bool
    duplicate: bool = False
    code: str = ""
    message: str = ""
    turn_id: str = ""
    call_id: str = ""
    operation: str = ""


@dataclass
class _PendingCall:
    turn_id: str
    call_id: str
    function_name: str
    future: asyncio.Future[dict[str, Any]]


SendEvent = Callable[[dict[str, Any]], Awaitable[None]]
_ALLOWED_OPERATIONS = frozenset(
    {
        "getWidgetCapabilityOverview",
        "getDataCapabilitySchemas",
        "generateWidgetCardCompactDsl",
    }
)


class BrowserToolBridge:
    """在后端 Agent 与浏览器工具执行器之间建立一次一一对应的等待关系。"""

    _COMPLETED_LIMIT = 256

    def __init__(
        self,
        send_event: SendEvent,
        *,
        session_id: str = "",
        timeout_seconds: float = 180.0,
        max_result_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("浏览器工具等待超时必须为正数")
        if max_result_bytes <= 0:
            raise ValueError("浏览器工具结果大小上限必须为正数")
        self._send_event = send_event
        self._session_id = session_id
        self._timeout_seconds = timeout_seconds
        self._max_result_bytes = max_result_bytes
        self._pending: dict[tuple[str, str], _PendingCall] = {}
        self._completed: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._expired: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def session_id(self) -> str:
        return self._session_id

    def set_session_id(self, session_id: str) -> None:
        """更新当前会话 ID；只允许在没有挂起调用时切换。"""

        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("浏览器工具会话 ID 必须是非空字符串")
        if self._pending:
            raise RuntimeError("存在挂起的浏览器工具调用，不能切换会话")
        self._session_id = session_id
        self._completed.clear()
        self._expired.clear()

    async def invoke(
        self,
        function_name: str,
        arguments: dict[str, Any],
        *,
        call_id: str,
        turn_id: str,
        step: int = 0,
        skill_name: str = "",
        bundle_name: str = "",
    ) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
        """发送 ``tool.call`` 并等待匹配的 ``tool.result``。

        返回值沿用旧 ``ToolDispatcher`` 的 ``(result, frames)`` 约定；浏览器已
        过滤掉 start/partial/command，因此 frames 始终为空，不会污染时间线。
        """

        if not isinstance(function_name, str) or not function_name.strip():
            raise BrowserToolBridgeError("浏览器工具名称无效")
        if function_name not in _ALLOWED_OPERATIONS:
            raise BrowserToolBridgeError("浏览器工具名称不在白名单中")
        if not isinstance(call_id, str) or not call_id.strip():
            raise BrowserToolBridgeError("浏览器工具 callId 无效")
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise BrowserToolBridgeError("浏览器工具 turnId 无效")
        call_id = call_id.strip()
        turn_id = turn_id.strip()
        if len(call_id) > 256 or len(turn_id) > 256:
            raise BrowserToolBridgeError("浏览器工具关联 ID 过长")
        if any(ord(char) < 32 or ord(char) == 127 for char in f"{call_id}{turn_id}"):
            raise BrowserToolBridgeError("浏览器工具关联 ID 含控制字符")
        if not isinstance(arguments, dict):
            raise BrowserToolBridgeError("浏览器工具 arguments 必须是对象")

        key = (turn_id, call_id)
        loop = asyncio.get_running_loop()
        pending = _PendingCall(
            turn_id=turn_id,
            call_id=call_id,
            function_name=function_name,
            future=loop.create_future(),
        )
        async with self._lock:
            if self._closed:
                raise BrowserToolBridgeError("浏览器工具桥已关闭")
            if key in self._pending:
                raise BrowserToolBridgeError("重复的浏览器工具调用")
            if key in self._completed:
                raise BrowserToolBridgeError("浏览器工具调用已完成")
            if key in self._expired:
                raise BrowserToolBridgeError("浏览器工具调用已过期")
            self._pending[key] = pending

        event = {
            "protocolVersion": "1.0",
            "type": "tool.call",
            "conversationId": self._session_id,
            "sessionId": self._session_id,
            "turnId": turn_id,
            "runId": turn_id,
            "callId": call_id,
            "executor": "client",
            "toolName": "invoke",
            "name": "invoke",
            "operation": function_name,
            "functionName": function_name,
            "arguments": arguments,
            "step": step,
        }
        if skill_name:
            event["skillName"] = skill_name
        if bundle_name:
            event["bundleName"] = bundle_name

        try:
            await self._send_event(event)
        except asyncio.CancelledError:
            await self._remove_pending(key, cancel=True)
            raise
        except Exception as exc:
            await self._remove_pending(key, cancel=True)
            raise BrowserToolBridgeError("浏览器工具调用事件发送失败") from exc

        try:
            result = await asyncio.wait_for(
                asyncio.shield(pending.future), self._timeout_seconds
            )
        except asyncio.exceptions.TimeoutError as exc:
            await self._cancel_pending(key, reason="浏览器工具调用超时")
            raise BrowserToolBridgeError("浏览器工具调用超时") from exc
        except asyncio.CancelledError:
            await self._cancel_pending(key)
            raise
        except Exception:
            await self._remove_pending(key, cancel=False)
            raise
        async with self._lock:
            self._pending.pop(key, None)
            self._remember_completed_locked(key, pending.function_name)
        return result, ()

    async def resolve(self, payload: dict[str, Any]) -> BrowserToolResolution:
        """校验并处理浏览器回传的 ``tool.result``。"""

        if not isinstance(payload, dict):
            return BrowserToolResolution(False, code="INVALID_RESULT", message="结果必须是对象")
        frame_type = payload.get("type")
        if frame_type is not None and (
            not isinstance(frame_type, str)
            or frame_type not in {"tool.result", "tool_result"}
        ):
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="结果帧类型必须是 tool.result",
            )
        turn_value, turn_present = _read_string_field(payload, "turnId")
        run_value, run_present = _read_string_field(payload, "runId")
        call_id, call_present = _read_string_field(payload, "callId")
        if turn_value is None or run_value is None or call_id is None:
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="tool.result 关联 ID 必须是字符串",
            )
        if (turn_present and not turn_value) or (run_present and not run_value) or (
            not (turn_value or run_value) or not call_present or not call_id
        ):
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="tool.result 缺少非空 turnId 或 callId",
            )
        turn_id = turn_value or run_value
        if (
            turn_present
            and run_present
            and turn_value != run_value
        ):
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="turnId 与 runId 不一致",
                turn_id=turn_id,
                call_id=call_id,
            )
        if (
            len(turn_id) > 256
            or len(call_id) > 256
            or any(ord(char) < 32 or ord(char) == 127 for char in f"{turn_id}{call_id}")
        ):
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="tool.result 关联 ID 无效",
                turn_id=turn_id,
                call_id=call_id,
            )
        key = (turn_id, call_id)
        conversation_value, conversation_present = _read_string_field(
            payload, "conversationId"
        )
        session_value, session_present = _read_string_field(payload, "sessionId")
        if conversation_value is None or session_value is None:
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="conversationId/sessionId 必须是字符串",
                turn_id=turn_id,
                call_id=call_id,
            )
        if (conversation_present and not conversation_value) or (
            session_present and not session_value
        ):
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="conversationId/sessionId 不能是空字符串",
                turn_id=turn_id,
                call_id=call_id,
            )
        conversation_id = conversation_value or session_value
        if (
            conversation_present
            and session_present
            and conversation_value != session_value
        ):
            return BrowserToolResolution(
                False,
                code="INVALID_RESULT",
                message="conversationId 与 sessionId 不一致",
                turn_id=turn_id,
                call_id=call_id,
            )
        if conversation_id and conversation_id != self._session_id:
            return BrowserToolResolution(
                False,
                code="STALE_SESSION",
                message="tool.result 不属于当前会话",
                turn_id=turn_id,
                call_id=call_id,
            )
        if "operation" in payload and not isinstance(payload["operation"], str):
            return await self._reject_matching_pending(
                key,
                "INVALID_RESULT",
                "tool.result.operation 必须是字符串",
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            return await self._reject_matching_pending(
                key,
                "INVALID_RESULT",
                "tool.result.result 必须是对象",
            )
        try:
            encoded_payload = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            return await self._reject_matching_pending(
                key,
                "INVALID_RESULT",
                "tool.result 不是可序列化 JSON",
            )
        if len(encoded_payload.encode("utf-8")) > self._max_result_bytes:
            return await self._reject_matching_pending(
                key,
                "RESULT_TOO_LARGE",
                "tool.result 超出大小限制",
            )
        async with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                if key in self._completed:
                    completed_operation = self._completed.get(key, "")
                    returned_operations, operation_error = _collect_operation_values(payload)
                    if operation_error:
                        return BrowserToolResolution(
                            False,
                            code="INVALID_RESULT",
                            message=operation_error,
                            turn_id=turn_id,
                            call_id=call_id,
                            operation=completed_operation,
                        )
                    if completed_operation and any(
                        value != completed_operation for value in returned_operations
                    ):
                        return BrowserToolResolution(
                            False,
                            code="OPERATION_MISMATCH",
                            message="重复 tool.result operation 与已完成调用不匹配",
                            turn_id=turn_id,
                            call_id=call_id,
                            operation=completed_operation,
                        )
                    return BrowserToolResolution(
                        True,
                        duplicate=True,
                        turn_id=turn_id,
                        call_id=call_id,
                        operation=completed_operation
                        or (returned_operations[0] if returned_operations else ""),
                    )
                if key in self._expired:
                    return BrowserToolResolution(
                        False,
                        code="STALE_CALL",
                        message="tool.result 对应的调用已过期或取消",
                        turn_id=turn_id,
                        call_id=call_id,
                        operation=self._expired.get(key, "")
                        or _string_field(payload, "operation"),
                    )
                same_call = next(
                    (
                        item
                        for item in self._pending.values()
                        if item.call_id == call_id
                    ),
                    None,
                )
                completed_call = any(item[1] == call_id for item in self._completed)
                expired_call = any(item[1] == call_id for item in self._expired)
                has_related_call = same_call is not None or completed_call or expired_call
                message = (
                    "tool.result 的 turnId 与挂起调用不匹配"
                    if has_related_call
                    else "tool.result 不匹配任何挂起调用"
                )
                return BrowserToolResolution(
                    False,
                    code="STALE_CALL" if has_related_call else "UNKNOWN_CALL",
                    message=message,
                    turn_id=turn_id,
                    call_id=call_id,
                )
            validation = _validate_result(result, payload, pending, self._session_id)
            if pending.future.done():
                return BrowserToolResolution(
                    True,
                    duplicate=True,
                    turn_id=turn_id,
                    call_id=call_id,
                    operation=pending.function_name,
                )
            if validation is not None:
                code, message = validation
                if code == "NON_FINAL_RESULT":
                    # A defensive client may still send a partial frame before
                    # its final frame.  Reject it, but keep the exact pending
                    # call alive so the later final result can complete it.
                    return BrowserToolResolution(
                        False,
                        code=code,
                        message=message,
                        turn_id=turn_id,
                        call_id=call_id,
                        operation=pending.function_name,
                    )
                rejection = (code, message)
            else:
                normalized_input = dict(result)
                for field in (
                    "ok",
                    "status",
                    "errorCode",
                    "error",
                    "operation",
                    "requestId",
                ):
                    if field not in normalized_input and field in payload:
                        normalized_input[field] = payload[field]
                pending.future.set_result(_normalize_result(normalized_input))
                return BrowserToolResolution(
                    True,
                    turn_id=turn_id,
                    call_id=call_id,
                    operation=pending.function_name,
                )
        return await self._reject_matching_pending(
            key,
            rejection[0],
            rejection[1],
        )

    async def _reject_matching_pending(
        self,
        key: tuple[str, str],
        code: str,
        message: str,
    ) -> BrowserToolResolution:
        """拒绝精确关联的非法终态，并立即释放对应 Agent future。"""

        async with self._lock:
            pending = self._pending.pop(key, None)
            if pending is not None:
                operation = pending.function_name
                self._remember_expired_locked(key, operation)
            else:
                operation = self._completed.get(key, "") or self._expired.get(key, "")
        turn_id, call_id = key
        if pending is not None:
            if not pending.future.done():
                pending.future.set_exception(BrowserToolBridgeError(message))
                # ``invoke`` may be unwinding concurrently; observe the
                # exception here so asyncio never reports an orphaned Future.
                pending.future.exception()
            await self._send_cancel_for_pending(
                turn_id,
                call_id,
                message,
            )
        return BrowserToolResolution(
            False,
            code=code,
            message=message,
            turn_id=turn_id,
            call_id=call_id,
            operation=operation,
        )

    async def cancel_turn(self, turn_id: str) -> None:
        """取消指定运行中的所有浏览器调用。"""

        keys = [key for key in self._pending if key[0] == turn_id]
        for key in keys:
            await self._cancel_pending(key)

    async def cancel_all(self) -> None:
        """取消当前桥上的全部挂起调用。"""

        keys = tuple(self._pending)
        for key in keys:
            await self._cancel_pending(key)

    async def close(self) -> None:
        """关闭桥并唤醒所有等待中的调用。"""

        async with self._lock:
            self._closed = True
            keys = tuple(self._pending)
        for key in keys:
            await self._cancel_pending(key, reason="浏览器工具桥已关闭")

    async def _remove_pending(self, key: tuple[str, str], *, cancel: bool) -> None:
        async with self._lock:
            item = self._pending.pop(key, None)
            if item is not None:
                self._remember_terminal_locked(key, item)
        if item is not None and cancel and not item.future.done():
            item.future.cancel()

    async def _cancel_pending(
        self,
        key: tuple[str, str],
        *,
        reason: str = "浏览器工具调用已取消",
    ) -> None:
        async with self._lock:
            item = self._pending.pop(key, None)
            if item is not None:
                self._remember_terminal_locked(key, item)
        if item is None:
            return
        if not item.future.done():
            item.future.set_exception(BrowserToolBridgeError(reason))
            # ``invoke`` may be cancelled at the same time as this cleanup;
            # mark the exception as observed so asyncio does not emit a noisy
            # "Future exception was never retrieved" warning.
            item.future.exception()
        try:
            await self._send_event(
                {
                    "protocolVersion": "1.0",
                    "type": "tool.cancel",
                    "conversationId": self._session_id,
                    "sessionId": self._session_id,
                    "turnId": item.turn_id,
                    "runId": item.turn_id,
                    "callId": item.call_id,
                    "reason": reason,
                }
            )
        except Exception:
            # WebSocket 断线时浏览器已无法再收到取消通知；Future 已释放，
            # 因此不能让清理流程被发送异常阻塞。
            return

    async def _send_cancel_for_pending(
        self,
        turn_id: str,
        call_id: str,
        reason: str,
    ) -> None:
        """通知浏览器停止一条已被后端判定为无效的结果。"""

        try:
            await self._send_event(
                {
                    "protocolVersion": "1.0",
                    "type": "tool.cancel",
                    "conversationId": self._session_id,
                    "sessionId": self._session_id,
                    "turnId": turn_id,
                    "runId": turn_id,
                    "callId": call_id,
                    "reason": reason,
                }
            )
        except Exception:
            # 结果已经让 Agent future 结束；断线时无需阻塞清理流程。
            return

    def _remember_completed_locked(self, key: tuple[str, str], operation: str = "") -> None:
        self._completed.pop(key, None)
        self._completed[key] = operation
        self._expired.pop(key, None)
        while len(self._completed) > self._COMPLETED_LIMIT:
            self._completed.popitem(last=False)

    def _remember_expired_locked(self, key: tuple[str, str], operation: str = "") -> None:
        self._expired.pop(key, None)
        self._expired[key] = operation
        self._completed.pop(key, None)
        while len(self._expired) > self._COMPLETED_LIMIT:
            self._expired.popitem(last=False)

    def _remember_terminal_locked(self, key: tuple[str, str], item: _PendingCall) -> None:
        if item.future.done() and not item.future.cancelled():
            self._remember_completed_locked(key, item.function_name)
        else:
            self._remember_expired_locked(key, item.function_name)


def _string_field(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _collect_operation_values(payload: dict[str, Any]) -> tuple[list[str], str | None]:
    """收集重复结果中的协议 operation，避免只校验顶层字段。"""

    containers: list[tuple[str, dict[str, Any]]] = []
    pending_containers: list[tuple[str, dict[str, Any]]] = [("payload", payload)]
    seen_containers: set[int] = set()
    while pending_containers:
        label, container = pending_containers.pop(0)
        if id(container) in seen_containers:
            continue
        seen_containers.add(id(container))
        containers.append((label, container))
        for field in ("result", "response", "finalFrame", "reply", "streamInfo"):
            nested = container.get(field)
            if isinstance(nested, dict):
                pending_containers.append((f"{label}.{field}", nested))
    values: list[str] = []
    for label, container in containers:
        for field in ("operation", "functionName"):
            if field not in container:
                continue
            value = container[field]
            if not isinstance(value, str):
                return [], f"{label}.{field} 必须是字符串"
            normalized = value.strip()
            if normalized and not (field == "functionName" and normalized == "invoke"):
                values.append(normalized)
    return values, None


def _read_string_field(payload: dict[str, Any], key: str) -> tuple[str | None, bool]:
    """读取协议字符串，同时区分缺失和非法类型。"""

    if key not in payload:
        return "", False
    value = payload[key]
    if not isinstance(value, str):
        return None, True
    return value.strip(), True


def _has_error_code(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip()
        return bool(normalized and normalized != "0")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return True


def _validate_result(
    result: dict[str, Any],
    payload: dict[str, Any],
    pending: _PendingCall,
    session_id: str,
) -> tuple[str, str] | None:
    """校验 final 标记、关联元数据和工具名称。"""

    # Agent 桥允许关联元数据出现在 tool.result 顶层，也允许浏览器把
    # 微服务响应放在 response/data/finalFrame 中；统一在这些容器中校验，
    # 但后面的状态判断只读取 envelope 容器，避免业务 data.status 误判为流状态。
    containers: list[tuple[str, dict[str, Any]]] = []
    pending_containers: list[tuple[str, dict[str, Any]]] = [
        ("payload", payload),
        ("result", result),
    ]
    seen_containers: set[int] = set()
    while pending_containers:
        label, container = pending_containers.pop(0)
        if id(container) in seen_containers:
            continue
        seen_containers.add(id(container))
        containers.append((label, container))
        for field in ("response", "finalFrame", "reply", "streamInfo"):
            value = container.get(field)
            if value is None:
                continue
            if not isinstance(value, dict):
                if field == "finalFrame":
                    return "INVALID_RESULT", f"{label}.finalFrame 必须是对象"
                continue
            pending_containers.append((f"{label}.{field}", value))

    metadata_containers = [item for item in containers if item[0] != "data"]
    operation_values: list[str] = []
    request_ids: list[str] = []
    stream_ids: list[str] = []
    for label, container in metadata_containers:
        if "errorCode" in container:
            error_code = container["errorCode"]
            if error_code is not None and (
                isinstance(error_code, bool)
                or not isinstance(error_code, (str, int, float))
            ):
                return "INVALID_RESULT", f"{label}.errorCode 必须是字符串或数字"
        for field in ("operation", "functionName"):
            if field not in container:
                continue
            value = container[field]
            if not isinstance(value, str):
                return "INVALID_RESULT", f"{label}.{field} 必须是字符串"
            if value.strip() and not (field == "functionName" and value.strip() == "invoke"):
                operation_values.append(value.strip())
        if "requestId" in container:
            value = container["requestId"]
            if not isinstance(value, str):
                return "INVALID_RESULT", f"{label}.requestId 必须是字符串"
            if value.strip():
                request_ids.append(value.strip())
        if "streamingTextId" in container:
            value = container["streamingTextId"]
            if not isinstance(value, str):
                return "INVALID_RESULT", f"{label}.streamingTextId 必须是字符串"
            if value.strip():
                stream_ids.append(value.strip())
        stream_info = container.get("reply")
        if isinstance(stream_info, dict):
            nested_info = stream_info.get("streamInfo")
            if isinstance(nested_info, dict):
                if "streamingTextId" in nested_info:
                    value = nested_info["streamingTextId"]
                    if not isinstance(value, str):
                        return "INVALID_RESULT", "streamInfo.streamingTextId 必须是字符串"
                    if value.strip():
                        stream_ids.append(value.strip())

    for value in operation_values:
        if value != pending.function_name:
            return "OPERATION_MISMATCH", "tool.result operation 与挂起调用不匹配"

    expected_request_id = f"{session_id}&{pending.call_id}" if session_id else ""
    if expected_request_id:
        if any(value != expected_request_id for value in request_ids):
            return "REQUEST_ID_MISMATCH", "tool.result requestId 与挂起调用不匹配"
        if any(value != expected_request_id for value in stream_ids):
            return "REQUEST_ID_MISMATCH", "tool.result streamingTextId 与挂起调用不匹配"

    status_values: list[tuple[str, str]] = []
    for label, container in metadata_containers:
        status_fields = ("status", "invokeStatus", "streamType")
        if label != "payload":
            status_fields = (*status_fields, "type")
        for field in status_fields:
            if field not in container:
                continue
            value = container[field]
            if not isinstance(value, str):
                return "INVALID_RESULT", f"{label}.{field} 必须是字符串"
            if field == "type" and value.strip().lower() not in {
                "final",
                "final_error",
                "start",
                "partial",
                "command",
                "streaming",
                "pending",
            }:
                continue
            status_values.append((field, value.strip().lower()))

    result_statuses = {value for _, value in status_values}
    has_error_code = any(
        _has_error_code(container.get("errorCode"))
        for _, container in metadata_containers
    )
    frame_types = [
        _frame_stream_type(container)
        for label, container in metadata_containers
        if label in {"payload", "result"} or ".finalFrame" in label
    ]
    frame_type = next((value for value in frame_types if value == "final_error"), "")
    if not frame_type:
        frame_type = next((value for value in frame_types if value), "")
    has_error_value = any(
        bool(container.get("error")) or bool(container.get("errorMessage"))
        for _, container in metadata_containers
    )
    has_failure_flag = any(
        container.get("ok") is False for _, container in metadata_containers
    )
    is_failure = (
        has_failure_flag
        or bool(result_statuses & {"failed", "error", "final_error"})
        or frame_type == "final_error"
        or has_error_code
        or has_error_value
    )
    if frame_type and frame_type not in {"final", "final_error"}:
        return "NON_FINAL_RESULT", "只接受微服务 WebSocket 的 final 结果"
    for field, value in status_values:
        if value in {"start", "partial", "command", "streaming", "pending"}:
            return "NON_FINAL_RESULT", "只接受微服务 WebSocket 的 final 结果"
        if field in {"streamType", "type"} and value and value not in {
            "final",
            "final_error",
        }:
            return "NON_FINAL_RESULT", "只接受微服务 WebSocket 的 final 结果"

    has_final_marker = bool(frame_type in {"final", "final_error"})
    has_final_marker = has_final_marker or any(
        value in {"final", "final_error", "success", "degraded", "failed", "error"}
        for _, value in status_values
    )
    # 网络/取消/白名单失败可以用 ``ok: false`` 直接结束；成功结果必须
    # 携带 final/final_error 或明确的终态 status，不能把任意业务对象当作
    # 微服务最终帧。
    if not has_final_marker and not is_failure:
        return "NON_FINAL_RESULT", "tool.result 缺少 final 结果标记"
    if not operation_values and not is_failure:
        return "OPERATION_MISSING", "tool.result 缺少 operation"
    if expected_request_id and not request_ids and not stream_ids and not is_failure:
        return "REQUEST_ID_MISSING", "tool.result 缺少 requestId 或 streamingTextId"
    return None


def _frame_stream_type(frame: dict[str, Any]) -> str:
    values: list[str] = []
    value = frame.get("streamType")
    if isinstance(value, str):
        values.append(value.strip().lower())
    reply = frame.get("reply")
    if isinstance(reply, dict):
        info = reply.get("streamInfo")
        if isinstance(info, dict) and isinstance(info.get("streamType"), str):
            values.append(info["streamType"].strip().lower())
    outer_type = frame.get("type")
    terminal_types = {"final", "final_error", "error", "tool.error"}
    if isinstance(outer_type, str) and outer_type.lower() in terminal_types:
        values.append(outer_type.lower())
    if "final_error" in values or "error" in values or "tool.error" in values:
        return "final_error"
    if "final" in values:
        return "final"
    return values[0] if values else ""


def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    """兼容浏览器直接回传 final 结果或 ``{response, invokeStatus}`` 包装。"""

    response = result.get("response")
    if isinstance(response, dict):
        normalized = _normalize_flat_result(response)
        invoke_status = str(result.get("invokeStatus") or "").lower()
        outer_status = str(result.get("status") or "").lower()
        outer_error_code = str(result.get("errorCode") or "")
        has_outer_error = outer_error_code not in {"", "0"}
        if (
            result.get("ok") is False
            or invoke_status in {"failed", "error", "final_error"}
            or outer_status in {"failed", "error", "final_error"}
            or has_outer_error
        ):
            normalized["status"] = "failed"
            normalized.setdefault(
                "errorCode",
                str(result.get("errorCode") or "BROWSER_TOOL_FAILED"),
            )
            if "error" not in normalized and result.get("error") is not None:
                normalized["error"] = result["error"]
        return normalized
    return _normalize_flat_result(result)


def _normalize_flat_result(result: dict[str, Any]) -> dict[str, Any]:
    """归一化不再包裹 response 的浏览器结果。"""

    invoke_status = str(result.get("invokeStatus") or "").lower()
    raw_status = str(result.get("status") or "").lower()
    error_code = str(result.get("errorCode") or "")
    frame_status = (
        _frame_stream_type(result.get("finalFrame"))
        if isinstance(result.get("finalFrame"), dict)
        else ""
    )
    if (
        invoke_status in {"failed", "error", "final_error"}
        or raw_status in {
        "failed",
        "error",
        "final_error",
        }
        or frame_status == "final_error"
        or error_code not in {"", "0"}
    ):
        error = result.get("error")
        normalized_error: Any = error
        if error is None or error == "":
            normalized_error = "浏览器工具执行失败"
        return {
            "status": "failed",
            "errorCode": str(result.get("errorCode") or "BROWSER_TOOL_FAILED"),
            "error": normalized_error,
            "data": result.get("data") if isinstance(result.get("data"), dict) else {},
        }
    normalized = dict(result)
    if normalized.get("ok") is False:
        normalized["status"] = "failed"
        normalized.setdefault("errorCode", "BROWSER_TOOL_FAILED")
    elif normalized.get("ok") is True or raw_status == "final" or frame_status == "final":
        # 微服务 final 帧可能带业务成功码字符串 "0"；它仍然是成功结果。
        normalized["status"] = "success"
    return normalized
