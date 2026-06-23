"""Anthropic-compatible Messages API client helpers."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

try:
    import requests
except ImportError:
    sys.exit("错误：缺少依赖库，请运行: pip install requests python-dotenv")

from .config import ANTHROPIC_VERSION, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT


def build_request_body(
    system_prompt: str,
    user_query: str,
    model: str,
    temperature: float | None = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_query}],
    }
    if temperature is not None:
        body["temperature"] = temperature
    return body


def call_api(
    base_url: str,
    auth_token: str,
    request_body: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": auth_token,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            print(f"  [API] request start (attempt {attempt + 1}/{max_retries + 1})", flush=True)
            started = time.time()
            response = requests.post(url, headers=headers, json=request_body, timeout=timeout)
            elapsed = time.time() - started
            print(f"  [API] response HTTP {response.status_code}, elapsed {elapsed:.1f}s", flush=True)
            if response.status_code == 200:
                data = response.json()
                if "content" not in data:
                    raise ValueError(
                        f"API 响应缺少 'content' 字段: {json.dumps(data, ensure_ascii=False)[:300]}"
                    )
                return data
            if response.status_code < 500:
                raise ValueError(
                    f"API 错误 (HTTP {response.status_code}): {response.text[:500]}"
                )
            last_exc = ValueError(
                f"API 错误 (HTTP {response.status_code}): {response.text[:500]}"
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
        if attempt < max_retries:
            wait = 2 ** attempt
            print(
                f"  [RETRY] API 调用失败，{wait}s 后重试 "
                f"(attempt {attempt + 1}/{max_retries + 1}): {last_exc}",
                file=sys.stderr,
            )
            time.sleep(wait)
    if last_exc is None:
        raise RuntimeError("API 调用失败，但未捕获到具体错误")
    raise last_exc


def extract_text_from_response(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in response.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    if not parts:
        raise ValueError(
            "API 响应中未找到 text 类型的内容块: "
            f"{json.dumps(response.get('content', []), ensure_ascii=False)[:300]}"
        )
    return "\n".join(parts)
