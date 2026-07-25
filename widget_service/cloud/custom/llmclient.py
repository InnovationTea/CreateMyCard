# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""
OpenAI 兼容的流式 LLM 客户端。

通过 HTTP SSE (Server-Sent Events) 协议流式调用 LLM API，
以 async generator 形式逐 token 返回生成文本。
"""

import asyncio
import json
from collections.abc import AsyncGenerator, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import websockets

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"


def _parse_stream_chunk(data: str) -> tuple[str, str, dict | None]:
    """解析 OpenAI 兼容 SSE data 行 → (content, reasoning, usage)。"""
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return ("", "", None)

    usage = obj.get("usage")
    choices = obj.get("choices", [])
    if not choices:
        return ("", "", usage)

    ch0 = choices[0]
    delta = ch0.get("delta") or {}
    content = delta.get("content")
    reasoning = delta.get("reasoning_content")

    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            p if isinstance(p, str) else str((p or {}).get("text", "")) for p in content
        )
    else:
        msg = ch0.get("message") or {}
        msg_content = msg.get("content")
        if isinstance(msg_content, str):
            text = msg_content
        if not reasoning:
            reasoning = msg.get("reasoning_content")

    reasoning_text = reasoning if isinstance(reasoning, str) else ""
    return (text, reasoning_text, usage)


def _process_sse_data_line(
    data: str,
    on_sse_event: Callable[[str, str, dict | None], None] | None = None,
) -> str | None:
    if data == "[DONE]":
        return None
    raw, reasoning, usage = _parse_stream_chunk(data)
    if on_sse_event:
        on_sse_event(raw, reasoning, usage)
    return raw if raw else None


def _process_sse_buffer(
    sse_buffer: str,
    on_sse_event: Callable[[str, str, dict | None], None] | None = None,
) -> tuple[list[str], str]:
    lines = sse_buffer.split("\n")
    tail = lines.pop() if lines else ""
    tokens: list[str] = []
    for line in lines:
        trimmed = line.strip()
        if not trimmed.startswith("data:"):
            continue
        token = _process_sse_data_line(trimmed[5:].strip(), on_sse_event)
        if token:
            tokens.append(token)
    return tokens, tail


@dataclass
class LLMClientOptions:
    """流式 LLM 调用的配置选项。"""

    api_key: str
    model: str = DEEPSEEK_DEFAULT_MODEL
    api_url: str = DEEPSEEK_URL
    reasoning_effort: str = "high"
    tools: list | None = None


async def stream_genui(
    options: LLMClientOptions,
    messages: list[dict],
    *,
    _on_sse_event: Callable[[str, str, dict | None], None] | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用 LLM，逐 token yield content。"""
    api_key = "AccessService"
    if not api_key:
        raise ValueError("Missing API key")

    model = "deepseek-ai/DeepSeek-V4-Flash"
    ws_url = "ws://10.32.101.24:18087/llm/websocket/openai/chat/completions"

    body = {
        "api_key": api_key,
        "user": "genui_user",
        "model": model,
        "stream": True,
        "extra_body": {
            "enable_thinking": False
        },
        "stream_options": {
            "include_usage": True,
            "debug_usage": True
        },
        "requestId": "genui_ui",
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 1,
        "max_tokens": 128000,
        "stop": ["DeepSeek"],
        "messages": messages,
    }

    print(f"[DEBUG] 请求体: {json.dumps(body, ensure_ascii=False)[:500]}...")

    headers = {
        "sender": "GenUI",
    }

    token_queue: asyncio.Queue = asyncio.Queue()
    executor = ThreadPoolExecutor(max_workers=1)

    def sync_request():
        """在独立线程中执行 WebSocket 请求，边接收边发送。"""
        print(f"[DEBUG] 开始 WebSocket 连接: {ws_url}")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def websocket_task():
                try:
                    async with websockets.connect(ws_url, additional_headers=headers) as websocket:

                        data = json.dumps(body, ensure_ascii=False)
                        await websocket.send(data)

                        chunk_count = 0

                        while True:
                            try:
                                content = await websocket.recv()
                            except websockets.exceptions.ConnectionClosedOK:
                                print("[DEBUG] WebSocket 连接正常关闭")
                                break
                            except websockets.exceptions.ConnectionClosedError as e:
                                print(f"[DEBUG] WebSocket 连接异常关闭: {e}")
                                break

                            if not content:
                                continue

                            chunk_count += 1

                            try:
                                response = json.loads(content)
                                choices = response.get('choices', [])

                                if choices:
                                    choice = choices[0]
                                    delta = choice.get('delta', {})

                                    # 提取 reasoning 或 content
                                    reasoning = delta.get('reasoning', '')
                                    if reasoning:
                                        token_queue.put_nowait(reasoning)
                                        print(reasoning, end='', flush=True)
                                        continue

                                    content_text = delta.get('content', '')
                                    if content_text:
                                        token_queue.put_nowait(content_text)
                                        print(content_text, end='', flush=True)
                                        continue

                                    finish_reason = choice.get('finish_reason')
                                    if finish_reason:
                                        print(f"\n[DEBUG] 完成原因: {finish_reason}")
                                        token_queue.put_nowait(None)
                                        return

                            except json.JSONDecodeError:
                                continue

                            if chunk_count % 50 == 0:
                                print(f"\n[DEBUG] 已接收 {chunk_count} 条消息", flush=True)

                        token_queue.put_nowait(None)

                except Exception as e:
                    print(f"\n[WEBSOCKET EXCEPTION] {e}")
                    import traceback
                    traceback.print_exc()
                    token_queue.put_nowait(f"ERROR: {e}")
                    token_queue.put_nowait(None)

            loop.run_until_complete(websocket_task())
            loop.close()

        except Exception as e:
            print(f"\n[THREAD EXCEPTION] {e}")
            import traceback
            traceback.print_exc()
            token_queue.put_nowait(f"ERROR: {e}")
            token_queue.put_nowait(None)

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(executor, sync_request)

    try:
        while True:
            if future.done():
                exc = future.exception()
                if exc:
                    raise exc

            try:
                token = await asyncio.wait_for(token_queue.get(), timeout=0.1)
            except TimeoutError:
                if future.done() and token_queue.empty():
                    break
                continue

            if token is None:
                break
            if token.startswith("ERROR:"):
                raise RuntimeError(token[6:])
            yield token
    finally:
        executor.shutdown(wait=False)
