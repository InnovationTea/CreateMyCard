# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import Any

import websockets

from app.logger import logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from models.generation import ModelRequestContext
from utils.base_utils import sts_config

_MODULE = "[DeepSeek Platform]"

SecretLoader = Callable[[str], bytes | str]
TimestampProvider = Callable[[], int]


class DeepSeekPlatformClient:
    """使用 DeepSeek Platform WebSocket 协议生成完整模型文本。"""

    def __init__(
            self,
            settings: Settings,
            *,
            secret_loader: SecretLoader | None = None,
            timestamp_provider: TimestampProvider | None = None,
    ) -> None:
        self.settings = settings
        self._secret_loader = secret_loader or sts_config.get_sts_config
        self._timestamp_provider = timestamp_provider or self._current_timestamp_ms

    async def generate(
            self,
            messages: list[dict[str, str]],
            request_context: ModelRequestContext,
    ) -> str:
        """发送一次非工具调用请求，并返回 finalText 内容。"""
        self._validate_configuration()
        headers = self._build_headers(request_context)
        body = self._build_body(messages, request_context)
        partial_texts: list[str] = []
        model_metrics: dict[str, Any] = {}
        start = time.perf_counter()
        first_token_at: float | None = None
        final_text: str | None = None
        try:
            async with websockets.connect(
                    self.settings.deepseek_platform_ws_url,
                    additional_headers=headers,
                    open_timeout=self.settings.model_request_timeout_seconds,
                    proxy=None,
            ) as websocket:
                await websocket.send(json.dumps(body, ensure_ascii=False))
                async for message in websocket:
                    final_text = self._process_message(message, partial_texts, model_metrics)
                    if final_text is not None:
                        if first_token_at is None and partial_texts:
                            first_token_at = time.perf_counter()
                        return final_text
        except ModelTransportError:
            raise
        except Exception as exc:
            logger.error(
                f"{_MODULE} request_failed exception_type={type(exc).__name__} "
                f"exception={exc!r}"
            )
            raise ModelTransportError(
                "DeepSeek Platform request failed",
                partial_output="".join(partial_texts),
            ) from exc
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            first_token_latency_ms = (
                round((first_token_at - start) * 1000, 2)
                if first_token_at is not None else None
            )
            decode_duration_ms = (
                round(duration_ms - first_token_latency_ms, 2)
                if first_token_latency_ms is not None else None
            )
            input_tokens = model_metrics.get("inputTokenNum")
            completion_tokens = model_metrics.get("generateTokenNum")
            model_time_ms = model_metrics.get("modelTime")
            output_length = len(final_text) if final_text else 0
            speed_str = "N/A"
            if completion_tokens and model_time_ms:
                try:
                    model_time_sec = float(model_time_ms) / 1000
                    if model_time_sec > 0:
                        speed_str = f"{completion_tokens / model_time_sec:.2f}"
                except (ValueError, TypeError):
                    pass
            logger.info(
                f"{_MODULE} stream_metrics "
                f"duration_ms={duration_ms}ms "
                f"first_token_latency_ms={first_token_latency_ms}ms "
                f"decode_duration_ms={decode_duration_ms}ms "
                f"input_tokens={input_tokens} "
                f"completion_tokens={completion_tokens} "
                f"tokens_per_sec={speed_str} "
                f"output_length={output_length} "
                f"output_preview=\n{final_text}"
            )
        raise ModelTransportError(
            "DeepSeek Platform connection closed before finalText",
            code="MODEL_STREAM_INCOMPLETE",
            partial_output="".join(partial_texts),
        )

    def _validate_configuration(self) -> None:
        if not self.settings.deepseek_platform_access_key.strip():
            raise ModelTransportError("DeepSeek Platform access key is not configured")
        if not self.settings.deepseek_platform_ws_url.strip():
            raise ModelTransportError("DeepSeek Platform WebSocket URL is not configured")

    def _build_headers(
            self,
            request_context: ModelRequestContext,
    ) -> dict[str, str]:
        return {
            "messageName": self.settings.deepseek_platform_message_name,
            "sender": self.settings.deepseek_platform_sender,
            "receiver": self.settings.deepseek_platform_receiver,
            "deviceId": request_context.device_id,
            "token": self._build_token(),
            "sessionId": request_context.session_id,
            "interactionId": request_context.interaction_id,
            "locate": request_context.country_code,
            "appVersion": request_context.app_version,
            "appName": request_context.app_name,
        }

    def _build_body(
            self,
            messages: list[dict[str, str]],
            request_context: ModelRequestContext,
    ) -> dict[str, Any]:
        message_name = self.settings.deepseek_platform_message_name
        sender = self.settings.deepseek_platform_sender
        receiver = self.settings.deepseek_platform_receiver
        copied_messages = [dict(message) for message in messages]
        return {
            "session": {
                "messageName": message_name,
                "sender": sender,
                "receiver": receiver,
                "deviceId": request_context.device_id,
                "sessionId": request_context.session_id,
                "interactionId": request_context.interaction_id,
            },
            "body": {
                "apiKey": self.settings.deepseek_platform_api_key,
                "modelName": self.settings.deepseek_platform_model_name,
                "modelParam": {},
                "extra_body": {
                    "enable_thinking": self.settings.deepseek_enable_thinking
                },
                "messages": copied_messages,
                "tools": None,
            },
        }

    def _build_token(self) -> str:
        timestamp = str(self._timestamp_provider())
        secret_key = self._load_secret_key()
        sign_source = f"{self.settings.deepseek_platform_access_key}{timestamp}"
        digest = hmac.new(
            secret_key,
            sign_source.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")
        return (
            f"{self.settings.deepseek_platform_access_key};"
            f"{timestamp};{signature};"
        )

    def _load_secret_key(self) -> bytes:
        config_key = self.settings.deepseek_platform_secret_key_sts_config_key
        try:
            encoded_secret = self._secret_loader(config_key)
            if isinstance(encoded_secret, str):
                encoded_secret = encoded_secret.encode("utf-8")
            secret_key = base64.b64decode(encoded_secret, validate=True)
            if not secret_key:
                raise ValueError("decoded secret key is empty")
            return secret_key
        except (KeyError, ValueError) as exc:
            logger.error(
                f"{_MODULE} secret_key_load_failed config_key={config_key} "
                f"exception_type={type(exc).__name__}"
            )
            raise ModelTransportError(
                f"DeepSeek Platform secret key is unavailable: {config_key}"
            ) from exc

    def _process_message(
            self,
            message: str | bytes,
            partial_texts: list[str],
            model_metrics: dict[str, Any] | None = None,
    ) -> str | None:
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            logger.warning(
                f"{_MODULE} response_json_ignored exception_type={type(exc).__name__}"
            )
            return None
        if not isinstance(data, dict):
            logger.warning(
                f"{_MODULE} response_shape_ignored "
                f"response_type={type(data).__name__}"
            )
            return None
        self._raise_for_platform_error(data, partial_texts)
        result = data.get("result")
        if not isinstance(result, dict):
            return None
        result_type = result.get("type")
        text = result.get("text")
        if result_type == "partialText" and isinstance(text, str) and text:
            partial_texts.append(text)
            return None
        if result_type != "finalText":
            return None

        model_info = data.get("modelRequestInfo")
        if isinstance(model_info, dict):
            self._extract_model_metrics(model_info, model_metrics)

        if not isinstance(text, str) or not text.strip():
            raise ModelTransportError(
                "DeepSeek Platform returned empty finalText",
                code="MODEL_EMPTY_OUTPUT",
                partial_output="".join(partial_texts),
            )
        return text

    @staticmethod
    def _extract_model_metrics(
            model_info: dict[str, Any],
            model_metrics: dict[str, Any] | None,
    ) -> None:
        """从 modelRequestInfo.contentBean 提取模型指标。"""
        content_bean = model_info.get("contentBean")
        if not isinstance(content_bean, dict):
            return
        for key in (
                "inputTokenNum",
                "generateTokenNum",
                "firstCostTime",
                "modelTime",
                "perTokenLantency",
                "contextTokenLantency",
                "prefixLen",
                "prefixHitRate",
                "meanAcceptTokens",
        ):
            if key in content_bean:
                model_metrics[key] = content_bean[key]

    @staticmethod
    def _raise_for_platform_error(
            data: dict[str, Any],
            partial_texts: list[str],
    ) -> None:
        result = data.get("result")
        result_data = result if isinstance(result, dict) else {}
        error_code = data.get("errorCode") or result_data.get("errorCode")
        has_error_code = error_code not in {None, "", 0, "0"}
        result_type = str(result_data.get("type", "")).casefold()
        has_error_type = result_type in {"error", "failed", "failure"}
        if not has_error_code and not has_error_type:
            return
        error_message = (
                data.get("errorMsg")
                or data.get("errorMessage")
                or result_data.get("errorMsg")
                or result_data.get("text")
                or "unknown platform error"
        )
        raise ModelTransportError(
            f"DeepSeek Platform returned error: code={error_code}, message={error_message}",
            code=str(error_code or result_type),
            partial_output="".join(partial_texts),
        )

    @staticmethod
    def _current_timestamp_ms() -> int:
        return int(time.time() * 1000)