# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import base64
import codecs
import hashlib
import hmac
import json
import time
import traceback
from urllib.parse import urlencode, urlparse

import httpx

from app.logger import json_for_log, logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from utils.base_utils import sts_config

_MODULE = "[MEP Model Transport]"
START_PREFIX = "$@START_PREFIX@#"
END_SUFFIX = "$@END_SUFFIX@#"
LAST_WORD_TOKEN = "__last_word___"


class PredictEventDecoder:
    """跨任意网络 chunk 边界解析 MEP 自定义事件帧。"""

    def __init__(self) -> None:
        self._buffer = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")()

    def feed(self, chunk: bytes, *, final: bool = False) -> list[dict]:
        """输入一个字节块并返回其中已经完整解析出的事件。"""
        self._buffer += self._decoder.decode(chunk, final=final)
        events: list[dict] = []
        while True:
            start_index = self._buffer.find(START_PREFIX)
            if start_index < 0:
                self._retain_possible_prefix()
                break
            if start_index > 0:
                self._buffer = self._buffer[start_index:]
            payload = self._buffer.removeprefix(START_PREFIX)
            if END_SUFFIX not in payload:
                break
            json_text, _, self._buffer = payload.partition(END_SUFFIX)
            json_text = json_text.strip()
            if not json_text:
                continue
            try:
                events.append(json.loads(json_text))
            except json.JSONDecodeError:
                logger.warning(
                    f"{_MODULE} stream_json_parse_failed raw_event={json_for_log(json_text)}"
                )
        return events

    def _retain_possible_prefix(self) -> None:
        keep_size = len(START_PREFIX) - 1
        if len(self._buffer) > keep_size:
            self._buffer = self._buffer[-keep_size:]


class MepModelTransport:
    """封装 MEP 鉴权、异步请求和流式协议解析。"""

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
        """关闭当前 Transport 自行创建的连接池。"""
        if self._owns_http_client:
            await self.http_client.aclose()

    @staticmethod
    def messages_to_qwen_prompt(messages: list[dict[str, str]]) -> str:
        """将 OpenAI messages 转为 MEP 使用的 Qwen ChatML Prompt。"""
        supported_roles = {
            "system",
            "user",
            "assistant",
            "tool",
            "classifier",
            "web_result",
        }
        parts: list[str] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role not in supported_roles:
                raise ValueError(f"不支持的消息角色: {role!r}")
            if not isinstance(content, str):
                raise TypeError(
                    f"消息 content 必须为字符串，role={role!r}，"
                    f"实际类型={type(content).__name__}"
                )
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
        parts.append("<|im_start|>assistant\n")
        return "".join(parts)

    def calc_sign(
        self,
        payload: str,
        method: str = "POST",
        path: str | None = None,
        query_params: dict[str, str] | None = None,
    ) -> str:
        """生成模型服务所需的 CLOUDSOA-HMAC-SHA256 签名。"""
        path = path or self.settings.model_path
        appid = self.settings.model_appid
        sign_key = sts_config.get_sts_config("genui.model.secret.key")
        if not sign_key:
            raise ModelTransportError("未获取到模型签名密钥: genui.model.secret.key")
        if isinstance(sign_key, str):
            sign_key = sign_key.encode("utf-8")
        if not path.startswith("/"):
            path = "/" + path
        query_params = query_params or {}
        query_str = "&".join(f"{key}={query_params[key]}" for key in sorted(query_params))
        timestamp = str(int(time.time() * 1000))
        sign_text = f"{method}&{path}&{query_str}&{payload}&appid={appid}&timestamp={timestamp}"
        signature_bytes = hmac.new(
            sign_key,
            sign_text.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_bytes).decode("utf-8")
        return f'CLOUDSOA-HMAC-SHA256 appid={appid}, timestamp={timestamp}, signature="{signature}"'

    async def generate(self, messages: list[dict[str, str]]) -> str:
        """异步调用 MEP /predict 并返回聚合后的原始模型文本。"""
        prompt = self.messages_to_qwen_prompt(messages)
        query_params = {
            "bId": self.settings.model_bid,
            "flowId": self.settings.model_flow_id,
        }
        request_body = {
            "data": {"prompt": prompt, "stream": True},
            "param": {
                "temperature": self.settings.model_temperature,
                "topkNum": self.settings.model_top_k,
            },
        }
        payload = json.dumps(request_body, ensure_ascii=False, separators=(",", ":"))
        parsed_url = urlparse(self.settings.model_url)
        authorization = self.calc_sign(
            payload=payload,
            method="POST",
            path=parsed_url.path or "/predict",
            query_params=query_params,
        )
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        request_url = f"{self.settings.model_url.rstrip('/')}?{urlencode(query_params)}"
        return await self._request_stream(request_url, payload, headers)

    async def _request_stream(
        self,
        request_url: str,
        payload: str,
        headers: dict[str, str],
    ) -> str:
        collected_texts: list[str] = []
        final_event: dict | None = None
        first_token_at: float | None = None
        started_at = time.perf_counter()
        try:
            decoder = PredictEventDecoder()
            async with self.http_client.stream(
                "POST",
                request_url,
                content=payload.encode("utf-8"),
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    first_token_at, final_event = self._collect_events(
                        decoder.feed(chunk),
                        collected_texts,
                        first_token_at,
                        final_event,
                    )
                first_token_at, final_event = self._collect_events(
                    decoder.feed(b"", final=True),
                    collected_texts,
                    first_token_at,
                    final_event,
                )
            full_text = "".join(collected_texts)
            self._log_response(started_at, first_token_at, final_event, full_text)
            self._raise_for_model_error(final_event, full_text)
            return full_text
        except ModelTransportError:
            raise
        except httpx.TimeoutException as exc:
            self._raise_request_error("request_timeout", exc)
            timeout = self.settings.model_request_timeout_seconds
            raise ModelTransportError(f"model request timed out after {timeout}s") from exc
        except httpx.ConnectError as exc:
            self._raise_request_error("connection_error", exc)
            raise ModelTransportError("model connection failed") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            self._raise_request_error("http_error", exc, status)
            raise ModelTransportError(f"model HTTP request failed: {status}") from exc
        except httpx.RequestError as exc:
            self._raise_request_error("request_exception", exc)
            raise ModelTransportError("model request failed") from exc
        except Exception as exc:
            self._raise_request_error("unexpected_error", exc)
            raise ModelTransportError("unexpected model generation error") from exc

    @staticmethod
    def _collect_events(
        events: list[dict],
        collected_texts: list[str],
        first_token_at: float | None,
        final_event: dict | None,
    ) -> tuple[float | None, dict | None]:
        for event in events:
            event_type = event.get("type")
            text = event.get("text", "")
            if event_type == "partialText":
                if not isinstance(text, str) or not text:
                    continue
                first_token_at = first_token_at or time.perf_counter()
                collected_texts.append(text)
                continue
            if event_type == "finalText":
                final_event = event
                has_final_text = isinstance(text, str) and bool(text)
                if has_final_text and text != LAST_WORD_TOKEN:
                    collected_texts.append(text)
        return first_token_at, final_event

    def _log_response(
        self,
        started_at: float,
        first_token_at: float | None,
        final_event: dict | None,
        full_text: str,
    ) -> None:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        first_token_latency_ms = (
            round((first_token_at - started_at) * 1000, 2)
            if first_token_at is not None
            else None
        )
        completion_tokens = final_event.get("generateTokenNum") if final_event else None
        speed = self._token_speed(duration_ms, first_token_latency_ms, completion_tokens)
        logger.info(
            f"{_MODULE} response_received content_preview={json_for_log(full_text)} "
            f"duration_ms={duration_ms} first_token_latency_ms={first_token_latency_ms} "
            f"input_tokens={self._event_value(final_event, 'inputTokenNum')} "
            f"completion_tokens={completion_tokens} "
            f"model_time_ms={self._event_value(final_event, 'modelTime')} "
            f"tokens_per_sec={speed} "
            f"finish_reason={self._event_value(final_event, 'finishReason')} "
            f"error_code={self._event_value(final_event, 'errorCode')} "
            f"error_msg={self._event_value(final_event, 'errorMsg')}"
        )

    @staticmethod
    def _token_speed(
        duration_ms: float,
        first_token_latency_ms: float | None,
        completion_tokens: object,
    ) -> str:
        has_token_count = isinstance(completion_tokens, (int, float))
        if first_token_latency_ms is None or not has_token_count:
            return "N/A"
        generation_time_sec = (duration_ms - first_token_latency_ms) / 1000
        if generation_time_sec <= 0:
            return "N/A"
        return f"{completion_tokens / generation_time_sec:.2f}"

    @staticmethod
    def _raise_for_model_error(
        final_event: dict | None,
        partial_output: str,
    ) -> None:
        if not final_event or not final_event.get("errorCode"):
            return
        error_code = str(final_event.get("errorCode"))
        raise ModelTransportError(
            "model returned error: "
            f"code={error_code}, message={final_event.get('errorMsg')}",
            code=error_code,
            partial_output=partial_output,
        )

    @staticmethod
    def _raise_request_error(
        event: str,
        exc: Exception,
        status: object | None = None,
    ) -> None:
        status_text = f" status_code={status}" if status is not None else ""
        logger.error(
            f"{_MODULE} {event}{status_text} exception_type={type(exc).__name__} "
            f"exception={exc!r} traceback={traceback.format_exc()}"
        )

    @staticmethod
    def _event_value(event: dict | None, key: str) -> object:
        return event.get(key) if event else None
