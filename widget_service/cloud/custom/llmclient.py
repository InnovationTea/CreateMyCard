# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""
OpenAI 兼容的流式 LLM 客户端。

通过 WebSocket 协议流式调用 LLM API，
以 async generator 形式逐 token 返回生成文本。
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx
import websockets

from config.config import get_settings
from app.logger import json_for_log, logger

_MODULE = "[LLMClient]"

DEFAULT_STOP = ["DeepSeek"]
DEFAULT_HEADERS = {"sender": "GenUI"}


@dataclass
class LLMClientOptions:
    """流式 LLM 调用的配置选项。"""

    settings = get_settings()

    api_key: str = settings.deepseek_api_key
    api_url: str = settings.deepseek_api_url
    model: str = settings.deepseek_model
    ws_url: str = settings.deepseek_ws_url
    user: str = settings.deepseek_user
    request_id: str = settings.deepseek_request_id
    temperature: float = settings.deepseek_temperature
    top_p: float = settings.deepseek_top_p
    top_k: int = settings.deepseek_top_k
    max_tokens: int = settings.deepseek_max_tokens
    stop: list[str] | None = None
    enable_thinking: bool = settings.deepseek_enable_thinking
    include_usage: bool = settings.deepseek_include_usage
    debug_usage: bool = settings.deepseek_debug_usage
    headers: dict[str, str] | None = None
    recv_timeout: int = settings.deepseek_recv_timeout


async def stream_genui(
        options: LLMClientOptions,
        messages: list[dict],
        *,
        trace: dict[str, object] | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用 LLM，逐 token yield content。"""
    if not options.api_key:
        raise ValueError("Missing API key")
    if options.api_url.startswith(("http://", "https://")):
        async for chunk in _stream_http_genui(options, messages, trace=trace):
            yield chunk
        return

    headers = options.headers or DEFAULT_HEADERS
    stop = options.stop if options.stop is not None else DEFAULT_STOP

    body = {
        "api_key": options.api_key,
        "user": options.user,
        "model": options.model,
        "stream": True,
        "extra_body": {
            "enable_thinking": options.enable_thinking,
        },
        "stream_options": {
            "include_usage": options.include_usage,
            "debug_usage": options.debug_usage,
        },
        "requestId": options.request_id,
        "temperature": options.temperature,
        "top_p": options.top_p,
        "top_k": options.top_k,
        "max_tokens": options.max_tokens,
        "stop": stop,
        "messages": messages,
    }

    logger.info(
        f"{_MODULE} stream_started ws_url={options.ws_url} "
        f"model={options.model} body_preview={json_for_log(json.dumps(body, ensure_ascii=False)[:500])}"
    )

    usage = None
    start = time.perf_counter()
    first_token_at: float | None = None
    try:
        async with websockets.connect(
                options.ws_url,
                additional_headers=headers,
                open_timeout=options.recv_timeout,
        ) as websocket:
            await websocket.send(json.dumps(body, ensure_ascii=False))

            async for message in websocket:
                try:
                    response = json.loads(message)
                except json.JSONDecodeError:
                    continue

                if "usage" in response:
                    usage = response["usage"]
                    if trace is not None and isinstance(usage, dict):
                        trace["usage"] = usage

                choices = response.get("choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})

                content_text = delta.get("content", "")
                if isinstance(content_text, list):
                    content_text = "".join(
                        p if isinstance(p, str) else str((p or {}).get("text", ""))
                        for p in content_text
                    )

                if content_text:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    yield content_text

                if choice.get("finish_reason"):
                    if trace is not None:
                        trace["finishReason"] = choice["finish_reason"]
                    logger.info(f"{_MODULE} stream_finished reason={choice['finish_reason']}")
                    break

    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"{_MODULE} websocket_closed_normally")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"{_MODULE} websocket_closed_abnormally error={e!r}")
        raise
    except Exception as e:
        logger.error(f"{_MODULE} websocket_error error_type={type(e).__name__} error={e!r}")
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        first_token_latency_ms = (
            round((first_token_at - start) * 1000, 2)
            if first_token_at is not None
            else None
        )
        input_tokens = usage.get("prompt_tokens") if usage else None
        completion_tokens = usage.get("completion_tokens") if usage else None
        speed_str = "N/A"
        if first_token_latency_ms is not None and completion_tokens:
            generation_time_sec = (duration_ms - first_token_latency_ms) / 1000
            if generation_time_sec > 0:
                speed_str = f"{completion_tokens / generation_time_sec:.2f}"
        logger.info(
            f"{_MODULE} stream_metrics "
            f"duration_ms={duration_ms}ms "
            f"first_token_latency_ms={first_token_latency_ms}ms "
            f"input_tokens={input_tokens} "
            f"completion_tokens={completion_tokens} "
            f"tokens_per_sec={speed_str} token/s"
        )
        if usage:
            logger.info(f"{_MODULE} usage_stats usage={json_for_log(usage)}")


async def _stream_http_genui(
    options: LLMClientOptions,
    messages: list[dict],
    *,
    trace: dict[str, object] | None = None,
) -> AsyncGenerator[str, None]:
    """调用 DeepSeek/OpenAI 兼容 HTTP SSE 接口。"""
    endpoint = options.api_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    payload = _http_request_payload(options, messages)
    headers = {
        "Authorization": f"Bearer {options.api_key}",
        "Content-Type": "application/json",
    }
    usage = None
    timeout = httpx.Timeout(float(options.recv_timeout))
    logger.info(
        f"{_MODULE} http_stream_started endpoint={endpoint} "
        f"model={options.model} message_count={len(messages)} "
        f"thinking_enabled={options.enable_thinking}"
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                    if trace is not None:
                        trace["usage"] = usage
                choices = event.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if trace is not None and choice.get("finish_reason"):
                    trace["finishReason"] = choice["finish_reason"]
                content = (choice.get("delta") or {}).get("content", "")
                if isinstance(content, str) and content:
                    yield content
    if usage:
        logger.info(f"{_MODULE} usage_stats usage={json_for_log(usage)}")


def _http_request_payload(
    options: LLMClientOptions,
    messages: list[dict],
) -> dict[str, object]:
    """Build the official DeepSeek Chat Completions payload."""
    return {
        "model": options.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": options.include_usage},
        "thinking": {
            "type": "enabled" if options.enable_thinking else "disabled",
        },
        "temperature": options.temperature,
        "top_p": options.top_p,
        "max_tokens": options.max_tokens,
    }