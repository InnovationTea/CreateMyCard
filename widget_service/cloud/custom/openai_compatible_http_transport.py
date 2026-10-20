# -*- coding: utf-8 -*-
"""共享OpenAI兼容HTTP传输；各通道独立提供配置与诊断名称。"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from app.logger import logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from models.generation import ModelRequestContext
from services.generation_trace_recorder import trace_record
from utils.ops_metrics import report_ops_metrics


@dataclass(frozen=True)
class OpenAICompatibleHttpOptions:
    """仅保存当前通道配置，密钥不得进入repr或诊断。"""

    url: str
    api_key: str = field(repr=False)
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    thinking_enabled: bool
    display_name: str
    log_prefix: str


class OpenAICompatibleHttpTransport:
    """通过已选择的兼容HTTP通道返回完整模型文本，不自行重试。"""

    def __init__(
        self,
        settings: Settings,
        options: OpenAICompatibleHttpOptions,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.options = options
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
        """关闭 Transport 自行创建的 HTTP 连接池。"""
        if self._owns_http_client:
            await self.http_client.aclose()

    async def generate(
        self,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None = None,
    ) -> str:
        """发送一次非流式 Chat Completions 请求并返回 assistant content。"""
        del request_context
        self._validate_configuration()
        payload = self._build_payload(messages)
        request_url = self.options.url.strip()
        headers = {
            "Authorization": f"Bearer {self.options.api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        started_at = time.perf_counter()
        try:
            response = await self.http_client.post(
                request_url,
                json=payload,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            self._log_failure("timeout", started_at, exc)
            raise ModelTransportError(
                f"{self.options.display_name} request timed out",
                code="MODEL_HTTP_TIMEOUT",
            ) from exc
        except httpx.RequestError as exc:
            self._log_failure("request_error", started_at, exc)
            raise ModelTransportError(
                f"{self.options.display_name} request failed",
                code="MODEL_HTTP_REQUEST_ERROR",
            ) from exc

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if response.is_error:
            report_ops_metrics(body={"taskFailModelCrash": 1})
            logger.warning(
                f"{self.options.log_prefix} response_failed status={response.status_code} "
                f"duration_ms={duration_ms} model={self.options.model}"
            )
            raise ModelTransportError(
                f"{self.options.display_name} returned status {response.status_code}",
                code="MODEL_HTTP_STATUS",
            )

        try:
            response_body = response.json()
        except ValueError as exc:
            report_ops_metrics(body={"taskFailModelCrash": 1})
            logger.warning(
                f"{self.options.log_prefix} response_invalid_json duration_ms={duration_ms} "
                f"model={self.options.model}"
            )
            raise ModelTransportError(
                f"{self.options.display_name} response is not valid JSON",
                code="MODEL_RESPONSE_INVALID",
            ) from exc

        try:
            result = self._extract_content(response_body)
        except ModelTransportError:
            report_ops_metrics(body={"taskFailModelCrash": 1})
            raise
        usage = response_body.get("usage") if isinstance(response_body, Mapping) else None
        self._report_success_metrics(duration_ms, usage)
        usage_summary = self._usage_summary(usage)
        trace_record(
            "model.transport_metrics",
            stage="model.transport",
            status="completed",
            duration_ms=duration_ms,
            metrics={
                "inputTokens": usage_summary.get("prompt_tokens"),
                "completionTokens": usage_summary.get("completion_tokens"),
                "totalTokens": usage_summary.get("total_tokens"),
                "outputChars": len(result),
            },
        )
        logger.info(
            f"{self.options.log_prefix} response_success duration_ms={duration_ms} "
            f"model={self.options.model} "
            f"output_chars={len(result)} usage={self._usage_summary(usage)}"
        )
        return result

    def _validate_configuration(self) -> None:
        url = self.options.url.strip()
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ModelTransportError(
                f"{self.options.display_name} URL is invalid",
                code="MODEL_CONFIG_INVALID",
            )
        if parsed_url.username or parsed_url.password:
            raise ModelTransportError(
                f"{self.options.display_name} URL must not contain credentials",
                code="MODEL_CONFIG_INVALID",
            )
        if not self.options.api_key.strip():
            raise ModelTransportError(
                f"{self.options.display_name} API key is not configured",
                code="MODEL_CONFIG_INVALID",
            )
        if not self.options.model.strip():
            raise ModelTransportError(
                f"{self.options.display_name} model is not configured",
                code="MODEL_CONFIG_INVALID",
            )
        if not 0 <= self.options.temperature <= 2:
            raise ModelTransportError(
                f"{self.options.display_name} temperature is invalid",
                code="MODEL_CONFIG_INVALID",
            )
        if not 0 < self.options.top_p <= 1:
            raise ModelTransportError(
                f"{self.options.display_name} top_p is invalid",
                code="MODEL_CONFIG_INVALID",
            )
        if self.options.max_tokens < 1:
            raise ModelTransportError(
                f"{self.options.display_name} max_tokens is invalid",
                code="MODEL_CONFIG_INVALID",
            )

    def _build_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self.options.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "temperature": self.options.temperature,
            "top_p": self.options.top_p,
            "max_tokens": self.options.max_tokens,
            "thinking": {"type": ("enabled" if self.options.thinking_enabled else "disabled")},
        }

    def _extract_content(self, response_body: object) -> str:
        if not isinstance(response_body, Mapping):
            raise ModelTransportError(
                f"{self.options.display_name} response shape is invalid",
                code="MODEL_RESPONSE_INVALID",
            )
        choices = response_body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelTransportError(
                f"{self.options.display_name} response contains no choices",
                code="MODEL_EMPTY_OUTPUT",
            )
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise ModelTransportError(
                f"{self.options.display_name} choice is invalid",
                code="MODEL_RESPONSE_INVALID",
            )
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise ModelTransportError(
                f"{self.options.display_name} message is invalid",
                code="MODEL_RESPONSE_INVALID",
            )
        content = message.get("content")
        if isinstance(content, str):
            result = content
        elif isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if not isinstance(part, Mapping) or part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
            result = "".join(text_parts)
        else:
            result = ""
        if not result.strip():
            raise ModelTransportError(
                f"{self.options.display_name} returned empty output",
                code="MODEL_EMPTY_OUTPUT",
            )
        return result

    @staticmethod
    def _usage_summary(usage: object) -> dict[str, int]:
        if not isinstance(usage, Mapping):
            return {}
        summary: dict[str, int] = {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                summary[key] = value
        return summary

    def _log_failure(self, failure_type: str, started_at: float, exc: Exception) -> None:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        report_ops_metrics(body={"taskFailModelCrash": 1})
        logger.warning(
            f"{self.options.log_prefix} request_failed type={failure_type} "
            f"duration_ms={duration_ms} "
            f"model={self.options.model} "
            f"exception_type={type(exc).__name__}"
        )

    @staticmethod
    def _report_success_metrics(duration_ms: float, usage: object) -> None:
        summary = OpenAICompatibleHttpTransport._usage_summary(usage)
        report_ops_metrics(
            body={
                "modelInputTokens": summary.get("prompt_tokens", 0),
                "modelOutputTokens": summary.get("completion_tokens", 0),
                "modelTotalTime": duration_ms,
                "modelFirstTokenTime": 0.0,
                "modelInferenceTime": duration_ms,
                "modelInferenceSpeedTps": 0.0,
                "taskFailModelCrash": 0,
            }
        )
