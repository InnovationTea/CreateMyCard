"""Shared OpenAI-compatible HTTP model client.

Both the production generation service and the Debug Agent use this adapter so
the HTTP request envelope and response normalization stay identical.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

_OFFICIAL_MAX_OUTPUT_TOKENS = 8192


@dataclass(frozen=True)
class OfficialHttpToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class OfficialHttpCompletion:
    content: str = ""
    reasoning_content: str = ""
    tool_calls: tuple[OfficialHttpToolCall, ...] = ()
    finish_reason: str = ""
    usage: dict[str, Any] | None = None


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    return "".join(
        item if isinstance(item, str) else str(item.get("text") or "")
        for item in value
        if isinstance(item, (str, dict))
    )


def _parse_tool_calls(value: object) -> tuple[OfficialHttpToolCall, ...]:
    if not isinstance(value, list):
        return ()
    calls: list[OfficialHttpToolCall] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name:
            continue
        arguments = function.get("arguments", "")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        if not isinstance(arguments, str):
            arguments = str(arguments)
        call_id = item.get("id")
        calls.append(
            OfficialHttpToolCall(
                id=call_id if isinstance(call_id, str) and call_id else f"call_{index}",
                name=name,
                arguments=arguments,
            )
        )
    return tuple(calls)


def parse_official_http_completion(payload: object) -> OfficialHttpCompletion:
    if not isinstance(payload, dict):
        raise ValueError("official HTTP response must be an object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("official HTTP response has no choices")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        message = choice.get("delta")
    if not isinstance(message, dict):
        raise ValueError("official HTTP response has no message")
    return OfficialHttpCompletion(
        content=_content_text(message.get("content")),
        reasoning_content=_content_text(message.get("reasoning_content")),
        tool_calls=_parse_tool_calls(message.get("tool_calls")),
        finish_reason=str(choice.get("finish_reason") or ""),
        usage=dict(payload["usage"]) if isinstance(payload.get("usage"), dict) else None,
    )


async def request_official_http(
    *,
    url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, object]],
    user: str = "",
    tools: list[dict[str, object]] | None = None,
    tool_choice: str | dict[str, Any] = "auto",
    temperature: float = 0.7,
    top_p: float = 0.9,
    max_tokens: int = 8192,
    stop: list[str] | None = None,
    thinking_enabled: bool | None = None,
    timeout: float = 120.0,
) -> OfficialHttpCompletion:
    """Call the official OpenAI-compatible chat completions HTTP endpoint.

    WebSocket-only extension fields such as ``top_k``, ``requestId`` and
    ``stream_options`` are intentionally absent from this interface.
    """
    endpoint = url.strip()
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("official HTTP endpoint must use http or https")
    if not api_key.strip():
        raise ValueError("official HTTP API key is not configured")
    # The public DeepSeek endpoint limits a single completion to 8K output
    # tokens.  The legacy WebSocket setting may be 128K, so clamp it here to
    # prevent a request that can run until the runtime's 120-second timeout.
    bounded_max_tokens = min(max_tokens, _OFFICIAL_MAX_OUTPUT_TOKENS)
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": bounded_max_tokens,
    }
    if user:
        payload["user"] = user
    if stop:
        payload["stop"] = stop
    if thinking_enabled is not None:
        payload["thinking"] = {
            "type": "enabled" if thinking_enabled else "disabled",
        }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text.strip()
            if len(detail) > 2000:
                detail = f"{detail[:2000]}..."
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(
                f"official HTTP request returned HTTP {response.status_code}{suffix}"
            ) from exc
        return parse_official_http_completion(response.json())
