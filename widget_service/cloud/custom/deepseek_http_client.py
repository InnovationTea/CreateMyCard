# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""DeepSeek OpenAI-compatible HTTPS transport."""

from __future__ import annotations

from typing import Any

import httpx

from app.logger import logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from models.generation import ModelRequestContext

_MODULE = "[DeepSeek HTTP Client]"


class DeepSeekHttpClient:
    """Call the configured public DeepSeek chat-completions endpoint."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=settings.model_max_concurrency,
                max_keepalive_connections=settings.model_max_concurrency,
            ),
            timeout=settings.model_request_timeout_seconds,
            trust_env=False,
        )

    async def aclose(self) -> None:
        """Close the owned HTTP connection pool."""
        if self._owns_http_client:
            await self.http_client.aclose()

    async def generate(
        self,
        messages: list[dict[str, str]],
        _request_context: ModelRequestContext | None = None,
    ) -> str:
        """Return one complete assistant message without logging credentials."""
        api_key = self.settings.deepseek_api_key.strip()
        api_url = self.settings.deepseek_api_url.strip().rstrip("/")
        if not api_key:
            raise ModelTransportError(
                "DeepSeek HTTP API key is missing",
                code="MODEL_CONFIGURATION_INVALID",
            )
        if not api_url:
            raise ModelTransportError(
                "DeepSeek HTTP API URL is missing",
                code="MODEL_CONFIGURATION_INVALID",
            )
        payload = {
            "model": self.settings.deepseek_http_model,
            "messages": messages,
            "stream": False,
            "thinking": {
                "type": (
                    "enabled"
                    if self.settings.deepseek_enable_thinking
                    else "disabled"
                )
            },
            "temperature": self.settings.deepseek_temperature,
            "top_p": self.settings.deepseek_top_p,
            "max_tokens": self.settings.deepseek_http_max_tokens,
        }
        logger.info(
            f"{_MODULE} request_started model={self.settings.deepseek_http_model} "
            f"message_count={len(messages)}"
        )
        try:
            response = await self.http_client.post(
                f"{api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise ModelTransportError(
                "DeepSeek HTTP request failed",
                code="MODEL_TRANSPORT_ERROR",
            ) from exc
        if response.status_code >= 400:
            logger.error(
                f"{_MODULE} request_rejected status_code={response.status_code}"
            )
            raise ModelTransportError(
                f"DeepSeek HTTP request rejected with status {response.status_code}",
                code="MODEL_REMOTE_ERROR",
            )
        try:
            body: dict[str, Any] = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ModelTransportError(
                "DeepSeek HTTP response is malformed",
                code="MODEL_RESPONSE_INVALID",
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ModelTransportError(
                "DeepSeek HTTP response is empty",
                code="MODEL_EMPTY_OUTPUT",
            )
        logger.info(f"{_MODULE} request_completed content_chars={len(content)}")
        return content
