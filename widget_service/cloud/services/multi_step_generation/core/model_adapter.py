from __future__ import annotations

# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import base64
import hashlib
import hmac
import json
import random
import sys
import time
import weakref
from dataclasses import dataclass
from typing import Any, Literal

import websockets

from config.config import Settings
from models.generation import ModelRequestContext
from utils.base_utils import sts_config

_MODULE = "[JSX Platform Model]"
_DEFAULT_HEADERS = {"sender": "GenUI"}
_DEFAULT_STOP = ["DeepSeek"]

ToolChoice = str | dict[str, Any]
Provider = Literal["deepseek_platform", "llmclient"]

_LOOP_SEMAPHORES: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop,
    tuple[int, asyncio.Semaphore],
] = weakref.WeakKeyDictionary()


class PlatformModelError(RuntimeError):
    """本模块模型传输错误；保留 named tool_choice 兼容状态。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class _ModelToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class _ModelCompletion:
    content: str = ""
    reasoning_content: str = ""
    tool_calls: tuple[_ModelToolCall, ...] = ()
    finish_reason: str = ""
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class _Function:
    name: str
    arguments: str


@dataclass(frozen=True)
class _ToolCall:
    id: str
    function: _Function
    type: str = "function"

    def model_dump(self, *, exclude_none: bool = True) -> dict[str, Any]:
        del exclude_none
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments,
            },
        }


@dataclass(frozen=True)
class _Message:
    content: str
    reasoning_content: str
    tool_calls: tuple[_ToolCall, ...]


@dataclass(frozen=True)
class _Choice:
    message: _Message
    finish_reason: str


@dataclass(frozen=True)
class _Response:
    choices: tuple[_Choice, ...]
    usage: dict[str, Any]


def _status_code(value: object) -> int | None:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    return number if number in {400, 422} else None


def _is_tool_choice_compatibility_error(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) not in {400, 422}:
        return False
    message = str(exc).casefold()
    compatibility_markers = (
        "tool_choice",
        "named tool",
        "named function",
        "function calling",
    )
    for marker in compatibility_markers:
        if marker in message:
            return True
    return False


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    parts = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            parts.append(str(item.get("text") or ""))
    return "".join(parts)


def _merge_tool_calls(
    accumulators: dict[int, dict[str, str]],
    value: object,
) -> None:
    if not isinstance(value, list):
        return
    for fallback_index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        index = item.get("index", fallback_index)
        if not isinstance(index, int):
            continue
        current = accumulators.setdefault(
            index,
            {"id": "", "name": "", "arguments": ""},
        )
        call_id = item.get("id")
        if isinstance(call_id, str) and call_id:
            current["id"] = call_id
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if isinstance(name, str) and name:
            current["name"] = name
        arguments = function.get("arguments")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        if isinstance(arguments, str):
            current["arguments"] += arguments


def _tool_calls_from_value(value: object) -> tuple[_ModelToolCall, ...]:
    calls: dict[int, dict[str, str]] = {}
    _merge_tool_calls(calls, value)
    return _final_tool_calls(calls)


def _final_tool_calls(
    accumulators: dict[int, dict[str, str]],
) -> tuple[_ModelToolCall, ...]:
    result: list[_ModelToolCall] = []
    for index in sorted(accumulators):
        item = accumulators[index]
        if not item["name"]:
            continue
        result.append(
            _ModelToolCall(
                id=item["id"] or f"call_{index}",
                name=item["name"],
                arguments=item["arguments"],
            )
        )
    return tuple(result)


def _completion_from_payload(payload: object) -> _ModelCompletion | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        message = choice.get("message")
        if isinstance(message, dict):
            return _ModelCompletion(
                content=_content_text(message.get("content")),
                reasoning_content=_content_text(message.get("reasoning_content")),
                tool_calls=_tool_calls_from_value(message.get("tool_calls")),
                finish_reason=str(choice.get("finish_reason") or ""),
                usage=(dict(payload["usage"]) if isinstance(payload.get("usage"), dict) else {}),
            )
    tool_calls = _tool_calls_from_value(payload.get("tool_calls") or payload.get("toolCalls"))
    if tool_calls:
        return _ModelCompletion(
            content=_content_text(payload.get("content") or payload.get("text")),
            reasoning_content=_content_text(payload.get("reasoning_content")),
            tool_calls=tool_calls,
            finish_reason=str(payload.get("finish_reason") or "tool_calls"),
            usage=(dict(payload["usage"]) if isinstance(payload.get("usage"), dict) else {}),
        )
    return None


def _stream_completion(state: dict[str, Any], finish_reason: str) -> _ModelCompletion:
    return _ModelCompletion(
        content="".join(state["content"]),
        reasoning_content="".join(state["reasoning"]),
        tool_calls=_final_tool_calls(state["tool_calls"]),
        finish_reason=finish_reason,
        usage=dict(state["usage"]),
    )


def _semaphore(limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    current = _LOOP_SEMAPHORES.get(loop)
    if current is None or current[0] != limit:
        current = (limit, asyncio.Semaphore(limit))
        _LOOP_SEMAPHORES[loop] = current
    return current[1]


class _Completions:
    def __init__(self, owner: PlatformChatClient) -> None:
        self.owner = owner

    async def create(self, **request: Any) -> _Response:
        messages = request.get("messages")
        tools = request.get("tools")
        if not isinstance(messages, list) or not isinstance(tools, list):
            raise ValueError("messages and tools must be arrays")
        max_tokens = request.get("max_tokens", 8192)
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        completion = await self.owner.complete(
            messages,
            tools=tools,
            tool_choice=request.get("tool_choice", "auto"),
            max_tokens=max_tokens,
        )
        tool_calls = tuple(
            _ToolCall(
                id=item.id,
                function=_Function(name=item.name, arguments=item.arguments),
            )
            for item in completion.tool_calls
        )
        return _Response(
            choices=(
                _Choice(
                    message=_Message(
                        content=completion.content,
                        reasoning_content=completion.reasoning_content,
                        tool_calls=tool_calls,
                    ),
                    finish_reason=completion.finish_reason,
                ),
            ),
            usage=dict(completion.usage or {}),
        )


class _Chat:
    def __init__(self, owner: PlatformChatClient) -> None:
        self.completions = _Completions(owner)


class PlatformChatClient:
    """仅在 multi_step_generation 内使用的平台 WS/tool_choice 适配器。"""

    def __init__(
        self,
        settings: Settings,
        request_context: ModelRequestContext,
        *,
        thinking_mode: str,
        request_timeout: float,
    ) -> None:
        self.settings = settings
        self.request_context = request_context
        self.thinking_mode = thinking_mode
        self.request_timeout = request_timeout
        self.retry_count = 0
        self.chat = _Chat(self)

    async def complete(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
        tool_choice: ToolChoice,
        max_tokens: int,
    ) -> _ModelCompletion:
        plans: list[tuple[Provider, str, int]] = [
            (
                self.settings.openai_master_client,
                "master",
                self._retry_count("master"),
            )
        ]
        if self.settings.enable_model_failure_retry and self.settings.enable_openai_fallback:
            plans.append(
                (
                    self.settings.openai_fallback_client,
                    "fallback",
                    self._retry_count("fallback"),
                )
            )
        last_error: Exception | None = None
        for plan_index, (provider, role, retry_count) in enumerate(plans):
            if plan_index:
                self.retry_count += 1
                print(
                    f"{_MODULE} fallback_started provider={provider} role={role}",
                    file=sys.stderr,
                    flush=True,
                )
            try:
                return await self._complete_with_provider(
                    provider,
                    role,
                    retry_count,
                    messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                if _is_tool_choice_compatibility_error(exc):
                    raise
                last_error = exc
        if last_error is not None:
            raise last_error
        raise PlatformModelError("platform model provider plan is empty")

    async def _complete_with_provider(
        self,
        provider: Provider,
        role: str,
        retry_count: int,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
        tool_choice: ToolChoice,
        max_tokens: int,
    ) -> _ModelCompletion:
        max_attempts = retry_count + 1
        for attempt in range(1, max_attempts + 1):
            try:
                semaphore = _semaphore(self.settings.model_max_concurrency)
                async with asyncio.timeout(self.settings.model_queue_timeout_seconds):
                    await semaphore.acquire()
                try:
                    async with asyncio.timeout(self.request_timeout):
                        return await self._call_provider(
                            provider,
                            messages,
                            tools=tools,
                            tool_choice=tool_choice,
                            max_tokens=max_tokens,
                        )
                finally:
                    semaphore.release()
            except Exception as exc:
                if _is_tool_choice_compatibility_error(exc):
                    raise
                should_retry = attempt < max_attempts
                print(
                    f"{_MODULE} call_failed provider={provider} role={role} "
                    f"attempt={attempt} max_attempts={max_attempts} "
                    f"will_retry={str(should_retry).lower()} "
                    f"error_type={type(exc).__name__}",
                    file=sys.stderr,
                    flush=True,
                )
                if not should_retry:
                    raise
                self.retry_count += 1
                await asyncio.sleep(self._retry_delay(attempt))
        raise AssertionError("model retry loop exited unexpectedly")

    async def _call_provider(
        self,
        provider: Provider,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
        tool_choice: ToolChoice,
        max_tokens: int,
    ) -> _ModelCompletion:
        if provider == "deepseek_platform":
            return await self._complete_deepseek_platform(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens,
            )
        if provider == "llmclient":
            return await self._complete_llmclient(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens,
            )
        raise PlatformModelError(
            f"unsupported platform model provider: {provider}",
            code="MODEL_PROVIDER_UNSUPPORTED",
        )

    async def _complete_deepseek_platform(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
        tool_choice: ToolChoice,
        max_tokens: int,
    ) -> _ModelCompletion:
        settings = self.settings
        if not settings.deepseek_platform_access_key.strip():
            raise PlatformModelError("DeepSeek Platform access key is not configured")
        if not settings.deepseek_platform_ws_url.strip():
            raise PlatformModelError("DeepSeek Platform WebSocket URL is not configured")
        headers = self._deepseek_headers()
        body = {
            "session": {
                "messageName": settings.deepseek_platform_message_name,
                "sender": settings.deepseek_platform_sender,
                "receiver": settings.deepseek_platform_receiver,
                "deviceId": self.request_context.device_id,
                "sessionId": self.request_context.session_id,
                "interactionId": self.request_context.interaction_id,
            },
            "body": {
                "apiKey": settings.deepseek_platform_api_key,
                "modelName": settings.deepseek_platform_model_name,
                "modelParam": {},
                "extra_body": {
                    "enable_thinking": self.thinking_mode != "disable",
                },
                "messages": [dict(item) for item in messages],
                "tools": tools,
                "tool_choice": tool_choice,
                "max_tokens": max_tokens,
            },
        }
        state: dict[str, Any] = {
            "content": [],
            "reasoning": [],
            "tool_calls": {},
            "usage": {},
        }
        partial_texts: list[str] = []
        try:
            async with websockets.connect(
                settings.deepseek_platform_ws_url,
                additional_headers=headers,
                open_timeout=self.request_timeout,
                proxy=None,
            ) as websocket:
                await websocket.send(json.dumps(body, ensure_ascii=False))
                async for raw_message in websocket:
                    completion = self._process_deepseek_message(
                        raw_message,
                        partial_texts,
                        state,
                    )
                    if completion is not None:
                        return completion
        except PlatformModelError:
            raise
        except Exception as exc:
            raise PlatformModelError("DeepSeek Platform tool completion failed") from exc
        raise PlatformModelError(
            "DeepSeek Platform connection closed before tool completion",
            code="MODEL_STREAM_INCOMPLETE",
        )

    async def _complete_llmclient(
        self,
        messages: list[dict[str, object]],
        *,
        tools: list[dict[str, object]],
        tool_choice: ToolChoice,
        max_tokens: int,
    ) -> _ModelCompletion:
        settings = self.settings
        if not settings.deepseek_api_key:
            raise PlatformModelError("llmclient API key is not configured")
        body = {
            "api_key": settings.deepseek_api_key,
            "user": settings.deepseek_user,
            "model": settings.deepseek_model,
            "stream": True,
            "extra_body": {"enable_thinking": self.thinking_mode != "disable"},
            "stream_options": {
                "include_usage": settings.deepseek_include_usage,
                "debug_usage": settings.deepseek_debug_usage,
            },
            "requestId": settings.deepseek_request_id,
            "temperature": settings.deepseek_temperature,
            "top_p": settings.deepseek_top_p,
            "top_k": settings.deepseek_top_k,
            "max_tokens": max_tokens,
            "stop": _DEFAULT_STOP,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        state: dict[str, Any] = {
            "content": [],
            "reasoning": [],
            "tool_calls": {},
            "usage": {},
        }
        finish_reason = ""
        try:
            async with websockets.connect(
                settings.deepseek_ws_url,
                additional_headers=_DEFAULT_HEADERS,
                open_timeout=self.request_timeout,
            ) as websocket:
                await websocket.send(json.dumps(body, ensure_ascii=False))
                async for raw_message in websocket:
                    try:
                        response = json.loads(raw_message)
                    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                        continue
                    self._raise_llmclient_error(response)
                    if isinstance(response.get("usage"), dict):
                        state["usage"] = response["usage"]
                    choices = response.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0]
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta")
                    if isinstance(delta, dict):
                        state["content"].append(_content_text(delta.get("content")))
                        state["reasoning"].append(_content_text(delta.get("reasoning_content")))
                        _merge_tool_calls(state["tool_calls"], delta.get("tool_calls"))
                    message = choice.get("message")
                    if isinstance(message, dict):
                        state["content"].append(_content_text(message.get("content")))
                        state["reasoning"].append(_content_text(message.get("reasoning_content")))
                        _merge_tool_calls(
                            state["tool_calls"],
                            message.get("tool_calls"),
                        )
                    reason = choice.get("finish_reason")
                    if isinstance(reason, str) and reason:
                        finish_reason = reason
                        break
        except PlatformModelError:
            raise
        except Exception as exc:
            raise PlatformModelError("llmclient tool completion failed") from exc
        completion = _stream_completion(state, finish_reason)
        if not completion.content.strip() and not completion.tool_calls:
            raise PlatformModelError(
                "llmclient returned neither content nor tool calls",
                code="MODEL_EMPTY_OUTPUT",
            )
        return completion

    def _deepseek_headers(self) -> dict[str, str]:
        settings = self.settings
        return {
            "messageName": settings.deepseek_platform_message_name,
            "sender": settings.deepseek_platform_sender,
            "receiver": settings.deepseek_platform_receiver,
            "deviceId": self.request_context.device_id,
            "token": self._deepseek_token(),
            "sessionId": self.request_context.session_id,
            "interactionId": self.request_context.interaction_id,
            "locate": self.request_context.country_code,
            "appVersion": self.request_context.app_version,
            "appName": self.request_context.app_name,
        }

    def _deepseek_token(self) -> str:
        settings = self.settings
        timestamp = str(int(time.time() * 1000))
        config_key = settings.deepseek_platform_secret_key_sts_config_key
        try:
            encoded = sts_config.get_sts_config(config_key)
            if isinstance(encoded, str):
                encoded = encoded.encode("utf-8")
            secret = base64.b64decode(encoded, validate=True)
            if not secret:
                raise ValueError("decoded secret key is empty")
        except (KeyError, ValueError) as exc:
            raise PlatformModelError(f"DeepSeek Platform secret key is unavailable: {config_key}") from exc
        signature = base64.b64encode(
            hmac.new(
                secret,
                f"{settings.deepseek_platform_access_key}{timestamp}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return f"{settings.deepseek_platform_access_key};{timestamp};{signature};"

    @classmethod
    def _process_deepseek_message(
        cls,
        raw_message: str | bytes,
        partial_texts: list[str],
        state: dict[str, Any],
    ) -> _ModelCompletion | None:
        try:
            data = json.loads(raw_message)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        cls._raise_deepseek_error(data, partial_texts)
        if isinstance(data.get("usage"), dict):
            state["usage"] = data["usage"]
        complete = _completion_from_payload(data)
        if complete is not None:
            return complete
        choices = data.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            delta = choice.get("delta")
            if isinstance(delta, dict):
                state["content"].append(_content_text(delta.get("content")))
                state["reasoning"].append(_content_text(delta.get("reasoning_content")))
                _merge_tool_calls(state["tool_calls"], delta.get("tool_calls"))
            reason = choice.get("finish_reason")
            if isinstance(reason, str) and reason:
                return _stream_completion(state, reason)
        result = data.get("result")
        if not isinstance(result, dict):
            return None
        complete = _completion_from_payload(result)
        if complete is not None:
            return complete
        result_type = result.get("type")
        text = result.get("text")
        if result_type == "partialText" and isinstance(text, str):
            partial_texts.append(text)
            return None
        if result_type != "finalText" or not isinstance(text, str):
            return None
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return _ModelCompletion(content=text, finish_reason="stop")
        return _completion_from_payload(decoded) or _ModelCompletion(
            content=text,
            finish_reason="stop",
        )

    @staticmethod
    def _raise_deepseek_error(
        data: dict[str, Any],
        partial_texts: list[str],
    ) -> None:
        result = data.get("result")
        result_data = result if isinstance(result, dict) else {}
        code = data.get("errorCode") or result_data.get("errorCode")
        result_type = str(result_data.get("type") or "").casefold()
        if code in {None, "", 0, "0"} and result_type not in {
            "error",
            "failed",
            "failure",
        }:
            return
        message = (
            data.get("errorMsg")
            or data.get("errorMessage")
            or result_data.get("errorMsg")
            or result_data.get("text")
            or "unknown platform error"
        )
        raise PlatformModelError(
            f"DeepSeek Platform returned error: code={code}, message={message}; "
            f"partial_length={len(''.join(partial_texts))}",
            code=str(code or result_type),
            status_code=_status_code(code),
        )

    @staticmethod
    def _raise_llmclient_error(response: object) -> None:
        if not isinstance(response, dict):
            return
        error = response.get("error")
        error_payload = error if isinstance(error, dict) else {}
        code = (
            error_payload.get("status_code")
            or error_payload.get("status")
            or error_payload.get("code")
            or response.get("status_code")
            or response.get("statusCode")
            or response.get("errorCode")
        )
        message = error_payload.get("message") or response.get("errorMsg") or response.get("errorMessage")
        if code in {None, "", 0, "0"} and not isinstance(message, str):
            return
        raise PlatformModelError(
            f"llmclient returned error: code={code}, message={message or 'unknown error'}",
            code=str(code or "MODEL_PROVIDER_ERROR"),
            status_code=_status_code(code),
        )

    def _retry_count(self, role: str) -> int:
        if not self.settings.enable_model_failure_retry:
            return 0
        if role == "fallback":
            return self.settings.fallback_model_failure_max_retry_attempts
        return self.settings.model_failure_max_retry_attempts

    def _retry_delay(self, retry_index: int) -> float:
        settings = self.settings
        nominal = min(
            settings.model_failure_retry_max_delay_seconds,
            settings.model_failure_retry_initial_delay_seconds
            * settings.model_failure_retry_backoff_multiplier ** (retry_index - 1),
        )
        span = nominal * settings.model_failure_retry_jitter_ratio
        return round(
            random.uniform(
                max(0.0, nominal - span),
                min(settings.model_failure_retry_max_delay_seconds, nominal + span),
            ),
            3,
        )
