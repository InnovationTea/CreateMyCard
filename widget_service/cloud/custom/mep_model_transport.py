# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import base64
import codecs
import hashlib
import hmac
import json
import time
import traceback
from collections.abc import Iterator
from urllib.parse import urlencode, urlparse

import requests

from app.logger import json_for_log, logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from utils.base_utils import sts_config

_MODULE = "[MEP Model Transport]"
START_PREFIX = "$@START_PREFIX@#"
END_SUFFIX = "$@END_SUFFIX@#"
LAST_WORD_TOKEN = "__last_word___"


class MepModelTransport:
    """封装 MEP 鉴权、请求和自定义流协议解析。"""

    def __init__(self, settings: Settings, timeout: int = 600) -> None:
        self.settings = settings
        self.timeout = timeout

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
                    f"消息 content 必须为字符串，role={role!r}, 实际类型={type(content).__name__}"
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
        sign_str = f"{method}&{path}&{query_str}&{payload}&appid={appid}&timestamp={timestamp}"
        signature_bytes = hmac.new(
            sign_key,
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_bytes).decode("utf-8")
        return f'CLOUDSOA-HMAC-SHA256 appid={appid}, timestamp={timestamp}, signature="{signature}"'

    @staticmethod
    def iter_predict_events(response: requests.Response) -> Iterator[dict]:
        """解析 MEP /predict 的自定义流响应协议。"""
        buffer = ""
        decoder = codecs.getincrementaldecoder("utf-8")()
        for chunk in response.iter_content(chunk_size=4096):
            if not chunk:
                continue
            buffer += decoder.decode(chunk)
            while True:
                start_index = buffer.find(START_PREFIX)
                if start_index < 0:
                    keep_size = len(START_PREFIX) - 1
                    if len(buffer) > keep_size:
                        buffer = buffer[-keep_size:]
                    break
                if start_index > 0:
                    buffer = buffer[start_index:]
                payload_buffer = buffer.removeprefix(START_PREFIX)
                if END_SUFFIX not in payload_buffer:
                    break
                json_text, _, buffer = payload_buffer.partition(END_SUFFIX)
                json_text = json_text.strip()
                if not json_text:
                    continue
                try:
                    yield json.loads(json_text)
                except json.JSONDecodeError:
                    logger.warning(
                        f"{_MODULE} stream_json_parse_failed raw_event={json_for_log(json_text)}"
                    )
        decoder.decode(b"", final=True)

    def generate(self, messages: list[dict[str, str]]) -> str:
        """调用 MEP /predict 并返回未经 DSL 处理的完整模型文本。"""
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
        payload = json.dumps(
            request_body,
            ensure_ascii=False,
            separators=(",", ":"),
        )
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
        return self._request_stream(request_url, payload, headers)

    def _request_stream(
        self,
        request_url: str,
        payload: str,
        headers: dict[str, str],
    ) -> str:
        collected_texts: list[str] = []
        final_event: dict | None = None
        first_token_at: float | None = None
        start = time.perf_counter()
        try:
            with requests.post(
                request_url,
                data=payload.encode("utf-8"),
                headers=headers,
                timeout=self.timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                for event in self.iter_predict_events(response):
                    event_type = event.get("type")
                    text = event.get("text", "")
                    if event_type == "partialText":
                        first_token_at = self._append_partial_text(
                            collected_texts,
                            text,
                            first_token_at,
                        )
                    elif event_type == "finalText":
                        final_event = event
                        self._append_final_text(collected_texts, text)
            full_text = "".join(collected_texts)
            self._log_response(start, first_token_at, final_event, full_text)
            self._raise_for_model_error(final_event, full_text)
            return full_text
        except ModelTransportError:
            raise
        except requests.exceptions.Timeout as exc:
            self._raise_request_error("request_timeout", exc)
            raise ModelTransportError(f"model request timed out after {self.timeout}s") from exc
        except requests.exceptions.ConnectionError as exc:
            self._raise_request_error("connection_error", exc)
            raise ModelTransportError("model connection failed") from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            self._raise_request_error("http_error", exc, status)
            raise ModelTransportError(f"model HTTP request failed: {status}") from exc
        except requests.exceptions.RequestException as exc:
            self._raise_request_error("request_exception", exc)
            raise ModelTransportError("model request failed") from exc
        except Exception as exc:
            self._raise_request_error("unexpected_error", exc)
            raise ModelTransportError("unexpected model generation error") from exc

    @staticmethod
    def _append_partial_text(
        collected_texts: list[str],
        text: object,
        first_token_at: float | None,
    ) -> float | None:
        if not isinstance(text, str) or not text:
            return first_token_at
        collected_texts.append(text)
        return first_token_at or time.perf_counter()

    @staticmethod
    def _append_final_text(collected_texts: list[str], text: object) -> None:
        has_final_text = isinstance(text, str) and bool(text)
        if has_final_text and text != LAST_WORD_TOKEN:
            collected_texts.append(text)

    def _log_response(
        self,
        start: float,
        first_token_at: float | None,
        final_event: dict | None,
        full_text: str,
    ) -> None:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        first_token_latency_ms = (
            round((first_token_at - start) * 1000, 2) if first_token_at is not None else None
        )
        input_tokens = final_event.get("inputTokenNum") if final_event else None
        completion_tokens = final_event.get("generateTokenNum") if final_event else None
        model_time_ms = final_event.get("modelTime") if final_event else None
        speed = self._token_speed(duration_ms, first_token_latency_ms, completion_tokens)
        logger.info(
            f"{_MODULE} response_received content_preview={json_for_log(full_text)} "
            f"duration_ms={duration_ms} first_token_latency_ms={first_token_latency_ms} "
            f"input_tokens={input_tokens} completion_tokens={completion_tokens} "
            f"model_time_ms={model_time_ms} tokens_per_sec={speed} "
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
