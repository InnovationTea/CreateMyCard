# -*- coding: utf-8 -*-
"""DeepSeek 官方 Chat Completions HTTP Transport。"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)
from openai.types.chat import ChatCompletion

from app.logger import logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from models.generation import ModelRequestContext
from services.generation_trace_recorder import trace_record
from utils.ops_metrics import report_ops_metrics

_MODULE = "[DeepSeek Official HTTP]"


class DeepSeekOfficialHttpTransport:
    """通过官方 OpenAI-compatible HTTP 接口生成完整模型文本。"""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._sdk_client: AsyncOpenAI | None = None
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
        started_at = time.perf_counter()
        try:
            if self.settings.deepseek_official_http_use_sdk:
                response_body = await self._request_with_sdk(payload)
            else:
                response_body = await self._request_with_httpx(payload)
        except (APITimeoutError, httpx.TimeoutException) as exc:
            self._log_failure("timeout", started_at, exc)
            raise ModelTransportError(
                "DeepSeek official HTTP request timed out",
                code="MODEL_HTTP_TIMEOUT",
            ) from exc
        except (APIConnectionError, httpx.RequestError) as exc:
            self._log_failure("request_error", started_at, exc)
            raise ModelTransportError(
                "DeepSeek official HTTP request failed",
                code="MODEL_HTTP_REQUEST_ERROR",
            ) from exc
        except (APIStatusError, httpx.HTTPStatusError) as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            status_code = exc.response.status_code
            report_ops_metrics(body={"taskFailModelCrash": 1})
            logger.warning(
                f"{_MODULE} response_failed status={status_code} "
                f"duration_ms={duration_ms} model={self.settings.deepseek_official_http_model}"
            )
            raise ModelTransportError(
                f"DeepSeek official HTTP returned status {status_code}",
                code="MODEL_HTTP_STATUS",
            ) from None
        except (APIResponseValidationError, ValueError) as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            report_ops_metrics(body={"taskFailModelCrash": 1})
            logger.warning(
                f"{_MODULE} response_invalid_json duration_ms={duration_ms} "
                f"model={self.settings.deepseek_official_http_model}"
            )
            raise ModelTransportError(
                "DeepSeek official HTTP response is not valid JSON",
                code="MODEL_RESPONSE_INVALID",
            ) from exc

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
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
            f"{_MODULE} response_success duration_ms={duration_ms} "
            f"model={self.settings.deepseek_official_http_model} "
            f"output_chars={len(result)} usage={self._usage_summary(usage)}"
        )
        return result

    async def _request_with_sdk(self, payload: dict[str, Any]) -> dict[str, Any]:
        """使用标准 Chat Completions 方法，正文与 usage 继续由公共逻辑解析。"""
        endpoint = httpx.URL(self.settings.deepseek_official_http_url.strip())
        if self._sdk_client is None:
            base_url = endpoint.copy_with(
                path=endpoint.path.removesuffix("/chat/completions") + "/",
                query=None,
                fragment=None,
            )
            self._sdk_client = AsyncOpenAI(
                api_key=self.settings.deepseek_official_http_api_key.strip(),
                base_url=base_url,
                http_client=self.http_client,
                timeout=self.settings.model_request_timeout_seconds,
                max_retries=0,
            )
        thinking = payload.get("thinking")
        if not isinstance(thinking, dict):
            raise ValueError("DeepSeek thinking parameters must be an object")
        parameters = dict(payload)
        parameters.pop("thinking")
        response = await self._sdk_client.chat.completions.create(
            **parameters,
            extra_body={"thinking": thinking},
            extra_query=endpoint.params,
        )
        if not isinstance(response, ChatCompletion):
            raise ValueError("DeepSeek response is not a Chat Completion object")
        return response.model_dump(warnings=False)

    async def _request_with_httpx(self, payload: dict[str, Any]) -> Any:
        """保留原有请求入口，仅用于显式关闭 SDK 后的对照。"""
        response = await self.http_client.post(
            self.settings.deepseek_official_http_url.strip(),
            json=payload,
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_official_http_api_key.strip()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if response.is_error:
            response.raise_for_status()
        return response.json()

    def _validate_configuration(self) -> None:
        url = self.settings.deepseek_official_http_url.strip()
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ModelTransportError(
                "DeepSeek official HTTP URL is invalid",
                code="MODEL_CONFIG_INVALID",
            )
        if parsed_url.username or parsed_url.password:
            raise ModelTransportError(
                "DeepSeek official HTTP URL must not contain credentials",
                code="MODEL_CONFIG_INVALID",
            )
        if self.settings.deepseek_official_http_use_sdk:
            if not parsed_url.path.endswith("/chat/completions"):
                raise ModelTransportError(
                    "DeepSeek SDK endpoint path must end with /chat/completions; "
                    "disable deepseek_official_http_use_sdk for custom paths",
                    code="MODEL_CONFIG_INVALID",
                )
        if not self.settings.deepseek_official_http_api_key.strip():
            raise ModelTransportError(
                "DeepSeek official HTTP API key is not configured",
                code="MODEL_CONFIG_INVALID",
            )
        if not self.settings.deepseek_official_http_model.strip():
            raise ModelTransportError(
                "DeepSeek official HTTP model is not configured",
                code="MODEL_CONFIG_INVALID",
            )
        if not 0 <= self.settings.deepseek_official_http_temperature <= 2:
            raise ModelTransportError(
                "DeepSeek official HTTP temperature is invalid",
                code="MODEL_CONFIG_INVALID",
            )
        if not 0 < self.settings.deepseek_official_http_top_p <= 1:
            raise ModelTransportError(
                "DeepSeek official HTTP top_p is invalid",
                code="MODEL_CONFIG_INVALID",
            )
        if self.settings.deepseek_official_http_max_tokens < 1:
            raise ModelTransportError(
                "DeepSeek official HTTP max_tokens is invalid",
                code="MODEL_CONFIG_INVALID",
            )

    def _build_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "model": self.settings.deepseek_official_http_model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "temperature": self.settings.deepseek_official_http_temperature,
            "top_p": self.settings.deepseek_official_http_top_p,
            "max_tokens": self.settings.deepseek_official_http_max_tokens,
            "thinking": {
                "type": (
                    "enabled"
                    if self.settings.deepseek_official_http_enable_thinking
                    else "disabled"
                )
            },
        }

    @staticmethod
    def _extract_content(response_body: object) -> str:
        if not isinstance(response_body, Mapping):
            raise ModelTransportError(
                "DeepSeek official HTTP response shape is invalid",
                code="MODEL_RESPONSE_INVALID",
            )
        choices = response_body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ModelTransportError(
                "DeepSeek official HTTP response contains no choices",
                code="MODEL_EMPTY_OUTPUT",
            )
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise ModelTransportError(
                "DeepSeek official HTTP choice is invalid",
                code="MODEL_RESPONSE_INVALID",
            )
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise ModelTransportError(
                "DeepSeek official HTTP message is invalid",
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
                "DeepSeek official HTTP returned empty output",
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
            f"{_MODULE} request_failed type={failure_type} duration_ms={duration_ms} "
            f"model={self.settings.deepseek_official_http_model} "
            f"exception_type={type(exc).__name__}"
        )

    @staticmethod
    def _report_success_metrics(duration_ms: float, usage: object) -> None:
        summary = DeepSeekOfficialHttpTransport._usage_summary(usage)
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
