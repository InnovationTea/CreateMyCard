# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import base64
import codecs
import hashlib
import hmac
import json
import sys
import time
import traceback
from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlparse

import json_repair
import requests

if __name__ == "__main__" and __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logger import json_for_log, logger
from config.config import get_settings
from custom.llmclient import LLMClientOptions, stream_genui
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ThemeMode,
    convert_compact_dsl_to_a2ui,
)
from services.compact_dsl_protocol import is_compact_dsl
from services.protocol_registry import (
    DESIGN_COMPACT_PROFILE_ID,
    A2UIProtocolRegistry,
)
from utils.base_utils import sts_config

_MODULE = "[A2UI Model]"
START_PREFIX = "$@START_PREFIX@#"
END_SUFFIX = "$@END_SUFFIX@#"
LAST_WORD_TOKEN = "__last_word___"
ModelBackend = Literal["mep", "llmclient"]


class A2UIModelGenerationError(RuntimeError):
    """小模型未能产出可交给校验器的非空 DSL。"""


def require_generated_dsl(value: object) -> str:
    """拒绝空输出和历史错误字符串，保证下游只接收 DSL 候选。"""
    if not isinstance(value, str) or not value.strip():
        raise A2UIModelGenerationError("model returned empty DSL")
    if value.lstrip().startswith("a2ui_model_error:"):
        raise A2UIModelGenerationError("model returned an error instead of DSL")
    return value


class A2UIModelClient:
    """A2UI 模型调用客户端。

    mock 开关打开时按协议 profile 返回对应 mock 文件的原始内容；
    关闭时调用真实小模型接口。
    """

    def __init__(
            self,
            use_mock: bool | None = None,
            mock_data_path: str | Path | None = None,
            backend: ModelBackend = "mep",
    ) -> None:
        """初始化 A2UI 模型客户端。

        入参：
        - use_mock：是否使用 mock 数据；不传时读取全局配置。
        - mock_data_path：可选 mock 文件路径；不传时按协议选择同目录 mock 文件。
        - backend：模型传输后端；第三接口固定传 mep，第四接口固定传 llmclient。
        出参：无。
        """
        if backend not in {"mep", "llmclient"}:
            raise ValueError(f"Unsupported A2UI model backend: {backend}")
        settings = get_settings()
        self.settings = settings
        self.use_mock = (
            settings.enable_a2ui_model_mock if use_mock is None else use_mock
        )
        self.backend = backend
        self.mock_data_path = Path(mock_data_path) if mock_data_path else None
        self._suppress_prompt_log = False

    def generate(
            self,
            prompt: list[dict[str, str]],
            protocol_profile: dict | None = None,
    ) -> str:
        """生成 A2UI genui JSONL。

        入参：
        - prompt：PromptBuilder 生成的模型输入。
        - protocol_profile：用于选择协议对应的 mock；真实模型直接消费 prompt。
        出参：A2UI genui JSONL 字符串。
        """
        if self._suppress_prompt_log:
            logger.info(
                f"{_MODULE} generate_started use_mock={json_for_log(self.use_mock)} "
                f"backend={self.backend} "
                "prompt_redacted=true"
            )
        else:
            logger.info(
                f"{_MODULE} generate_started use_mock={json_for_log(self.use_mock)} "
                f"backend={self.backend} "
                f"system_prompt={json_for_log(prompt)}"
            )

        try:
            if self.use_mock:
                result = self._load_mock_data(protocol_profile, prompt)
            else:
                profile = protocol_profile or {}
                if self.backend == "llmclient":
                    result = self._generate_from_llm_client(prompt, profile)
                else:
                    result = self._generate_from_real_model(prompt, profile)
            return require_generated_dsl(result)
        except A2UIModelGenerationError:
            raise
        except Exception as exc:
            logger.error(
                f"{_MODULE} generation_failed exception_type={type(exc).__name__} "
                f"exception={exc!r} traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError("model generation failed") from exc

    def generate_repair(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict | None = None,
    ) -> str:
        """调用同一模型入口，但不把修复载荷写入日志。"""
        self._suppress_prompt_log = True
        try:
            return self.generate(prompt, protocol_profile)
        finally:
            self._suppress_prompt_log = False

    def _load_mock_data(
        self,
        protocol_profile: dict | None = None,
        prompt: list[dict[str, str]] | None = None,
    ) -> str:
        """直接读取当前协议对应的 mock 原始内容。

        入参：协议 profile 和模型提示词；Design Compact mock 会从 TaskSpec 选择尺寸文件。
        出参：mock 文件的完整 UTF-8 文本，不做替换或结构调整。
        """
        mock_data_path = self.mock_data_path
        if mock_data_path is None:
            filename = self._mock_filename(protocol_profile or {}, prompt or [])
            mock_data_path = Path(__file__).with_name(filename)
        if not mock_data_path.is_file():
            raise FileNotFoundError(f"A2UI mock 数据文件不存在: {mock_data_path}")

        mock_data = mock_data_path.read_text(encoding="utf-8")
        logger.info(
            f"{_MODULE} generate_completed mode=mock path={mock_data_path}"
        )
        return mock_data

    @staticmethod
    def _mock_filename(
        protocol_profile: dict,
        prompt: list[dict[str, str]],
    ) -> str:
        if protocol_profile.get("id") == DESIGN_COMPACT_PROFILE_ID:
            size = A2UIModelClient._task_size_from_prompt(prompt)
            return f"mock.design-compact-dsl-{size}.dat"
        if is_compact_dsl(protocol_profile):
            return "mock.compact-dsl.dat"
        return "mock.dat"

    @staticmethod
    def _task_size_from_prompt(prompt: list[dict[str, str]]) -> str:
        if not prompt:
            return "2x2"
        user_content = prompt[-1].get("content", "")
        try:
            payload = json.loads(user_content)
        except json.JSONDecodeError as exc:
            logger.warning(
                f"{_MODULE} mock_task_spec_parse_failed "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )
            return "2x2"
        size = payload.get("size") if isinstance(payload, dict) else None
        return size if size in {"2x2", "2x4"} else "2x2"

    def _generate_from_llm_client(
        self,
        messages: list[dict[str, str]],
        protocol_profile: dict | None = None,
    ) -> str:
        """通过 llmclient 收集流式输出，并复用 A2UI 的 DSL 后处理。"""

        async def collect_stream() -> str:
            options = LLMClientOptions(api_key="AccessService")
            chunks = [
                chunk
                async for chunk in stream_genui(options, messages)
            ]
            return "".join(chunks)

        full_text = asyncio.run(collect_stream())
        dsl_text = self.extract_genui_payload(full_text)
        if not is_compact_dsl(protocol_profile or {}):
            dsl_text = self.convert_dsl(dsl_text)
        logger.info(
            f"{_MODULE} dsl_processed backend=llmclient "
            f"dsl_content={json_for_log(dsl_text)}"
        )
        return dsl_text

    @staticmethod
    def messages_to_qwen_prompt(messages: list[dict[str, str]]) -> str:
        """将 OpenAI messages 转为 Qwen ChatML Prompt。"""
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
                    f"消息 content 必须为字符串，role={role!r}, "
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
            raise RuntimeError("未获取到模型签名密钥: genui.model.secret.key")
        if isinstance(sign_key, str):
            sign_key = sign_key.encode("utf-8")
        if not path.startswith("/"):
            path = "/" + path
        query_params = query_params or {}
        query_str = "&".join(
            f"{key}={query_params[key]}" for key in sorted(query_params)
        )
        timestamp = str(int(time.time() * 1000))
        sign_str = (
            f"{method}&{path}&{query_str}&{payload}"
            f"&appid={appid}&timestamp={timestamp}"
        )
        signature_bytes = hmac.new(
            sign_key,
            sign_str.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_bytes).decode("utf-8")
        return (
            f"CLOUDSOA-HMAC-SHA256 appid={appid}, "
            f"timestamp={timestamp}, "
            f'signature="{signature}"'
        )

    @staticmethod
    def iter_predict_events(response: requests.Response) -> Iterator[dict]:
        """解析 /predict 的自定义流响应协议。"""
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
                end_index = buffer.find(END_SUFFIX, len(START_PREFIX))
                if end_index < 0:
                    break
                json_text = buffer[len(START_PREFIX):end_index].strip()
                buffer = buffer[end_index + len(END_SUFFIX):]
                if not json_text:
                    continue
                try:
                    yield json.loads(json_text)
                except json.JSONDecodeError:
                    logger.warning(
                        f"{_MODULE} stream_json_parse_failed "
                        f"raw_event={json_for_log(json_text)}"
                    )
        decoder.decode(b"", final=True)

    def extract_genui_payload(self, text):
        """
        如果响应以'''genui 开头，则剔除前后标记，返回中间的JSON字符串
        否则原样返回。
        """
        text = text.strip()
        if text.startswith('```genui'):
            content = text[len('```genui'):].strip()
            if content.endswith('```'):
                content = content[:-3].strip()
            return content
        else:
            return text

    def convert_design_dsl_to_standard_dsl(
        self,
        design_dsl: str,
        *,
        size: str,
        design_profile_id: str = DESIGN_COMPACT_PROFILE_ID,
        theme: ThemeMode = "light",
        surface_id: str = "surface_card",
    ) -> str:
        """使用 Design profile 自带的协议文件把 Design Compact DSL 转为标准 A2UI。"""
        compact_dsl = self.extract_genui_payload(design_dsl)
        try:
            protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
                design_profile_id
            )
            converted_dsl = convert_compact_dsl_to_a2ui(
                compact_dsl,
                size=size,
                protocol_profile=protocol_profile,
                theme=theme,
                surface_id=surface_id,
            )
            logger.info(
                f"{_MODULE} design_dsl_conversion_completed "
                f"converted_dsl={json_for_log(converted_dsl)}"
            )
            return converted_dsl
        except CompactDslConversionError as exc:
            logger.error(
                f"{_MODULE} design_dsl_conversion_failed "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )
            raise A2UIModelGenerationError("design DSL conversion failed") from exc

    def process_line(self, line):
        """
        处理单行 JSON 字符串，返回解析后的数据或 None
        """
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            logger.error(f"{_MODULE} json_parse_failed line={json_for_log(line)}")
            try:
                return json_repair.loads(line)
            except Exception as e:
                logger.error(
                    f"{_MODULE} json_repair_failed exception_type={type(e).__name__} "
                    f"exception={e!r} traceback={traceback.format_exc()}"
                )
                return None

    def convert_dsl(self, dsl_text: str) -> str:
        """
        dsl 文本处理函数
        """
        output_lines = []

        for line in dsl_text.splitlines():
            line = line.strip()
            if not line:
                continue

            data = self.process_line(line)
            if not data:
                logger.error(f"{_MODULE} dsl_line_parse_failed line={json_for_log(line)}")
                return dsl_text

            # 修改 createSurface.catalogId
            create_surface = data.get("createSurface")
            if create_surface:
                create_surface["catalogId"] = "ohos.a2ui.extended.catalog.form"

            # 修改 root 的宽高
            update_components = data.get("updateComponents")
            if update_components:
                for component in update_components.get("components", []):
                    if component.get("id") == "root":
                        styles = component.setdefault("styles", {})
                        styles["width"] = "matchParent"
                        styles["height"] = "matchParent"
                        break

            output_lines.append(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            )

        return "\n".join(output_lines)

    def _generate_from_real_model(
        self,
        messages: list[dict[str, str]],
        protocol_profile: dict | None = None,
        timeout: int = 600,
    ) -> str:
        """通过 /predict 流式模型服务生成当前协议的 DSL。"""
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
        payload_str = json.dumps(
            request_body,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        parsed_url = urlparse(self.settings.model_url)
        authorization = self.calc_sign(
            payload=payload_str,
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
        collected_texts: list[str] = []
        final_event: dict | None = None
        first_token_at: float | None = None
        start = time.perf_counter()
        try:
            with requests.post(
                request_url,
                data=payload_str.encode("utf-8"),
                headers=headers,
                timeout=timeout,
                stream=True,
            ) as response:
                response.raise_for_status()
                for event in self.iter_predict_events(response):
                    event_type = event.get("type")
                    text = event.get("text", "")
                    if event_type == "partialText":
                        if not isinstance(text, str) or not text:
                            continue
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        collected_texts.append(text)
                    elif event_type == "finalText":
                        final_event = event
                        has_final_text = isinstance(text, str) and text
                        if has_final_text and text != LAST_WORD_TOKEN:
                            collected_texts.append(text)

            full_text = "".join(collected_texts)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            first_token_latency_ms = (
                round((first_token_at - start) * 1000, 2)
                if first_token_at is not None
                else None
            )
            input_tokens = final_event.get("inputTokenNum") if final_event else None
            completion_tokens = (
                final_event.get("generateTokenNum") if final_event else None
            )
            model_time_ms = final_event.get("modelTime") if final_event else None
            speed_str = "N/A"
            has_completion_tokens = isinstance(completion_tokens, (int, float))
            if first_token_latency_ms is not None and has_completion_tokens:
                generation_time_sec = (duration_ms - first_token_latency_ms) / 1000
                if generation_time_sec > 0:
                    speed_str = f"{completion_tokens / generation_time_sec:.2f}"
            logger.info(
                f"{_MODULE} response_received "
                f"content_preview={json_for_log(full_text)} "
                f"duration_ms={duration_ms} "
                f"first_token_latency_ms={first_token_latency_ms} "
                f"input_tokens={input_tokens} "
                f"completion_tokens={completion_tokens} "
                f"model_time_ms={model_time_ms} "
                f"tokens_per_sec={speed_str} "
                f"finish_reason={self._event_value(final_event, 'finishReason')} "
                f"error_code={self._event_value(final_event, 'errorCode')} "
                f"error_msg={self._event_value(final_event, 'errorMsg')}"
            )
            if final_event and final_event.get("errorCode"):
                raise RuntimeError(
                    "model returned error: "
                    f"code={final_event.get('errorCode')}, "
                    f"message={final_event.get('errorMsg')}"
                )
            dsl_text = self.extract_genui_payload(full_text)
            if not is_compact_dsl(protocol_profile or {}):
                dsl_text = self.convert_dsl(dsl_text)
            logger.info(
                f"{_MODULE} dsl_processed "
                f"dsl_content={json_for_log(dsl_text)}"
            )
            return dsl_text
        except requests.exceptions.Timeout as e:
            logger.error(
                f"{_MODULE} request_timeout "
                f"exception={e!r} traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError(f"model request timed out after {timeout}s") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"{_MODULE} connection_error "
                f"exception={e!r} traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError("model connection failed") from e
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            logger.error(
                f"{_MODULE} http_error status_code={status} "
                f"exception={e!r} traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError(f"model HTTP request failed: {status}") from e
        except requests.exceptions.RequestException as e:
            logger.error(
                f"{_MODULE} request_exception "
                f"exception={e!r} traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError("model request failed") from e
        except Exception as e:
            logger.error(
                f"{_MODULE} unexpected_error "
                f"exception_type={type(e).__name__} exception={e!r} "
                f"traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError("unexpected model generation error") from e

    @staticmethod
    def _event_value(event: dict | None, key: str) -> object:
        return event.get(key) if event else None


def _build_design_test_task_spec() -> dict:
    """构造覆盖数据、事件和素材能力的 Design Compact DSL 本地测试任务。"""
    return {
        "userQuery": (
            "生成杭州滨江区天气卡片，展示当前温度、天气状况、体感温度、湿度、空气质量、"
            "风向风力、生活指数和未来3天天气预报，并支持打开天气详情"
        ),
        "size": "2x4",
        "eventCandidates": [
            {
                "id": "event.open.weather",
                "call": "clickToDeeplink",
                "args": {
                    "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode=",
                },
            }
        ],
        "dataModelSchema": {
            "data": {
                "weather": {
                    "current": {
                        "temperatureText": {
                            "type": "string",
                            "description": "适合直接显示的温度文本",
                            "sampleValue": "26℃",
                        },
                        "condition": {
                            "type": "string",
                            "description": "当前天气现象",
                            "sampleValue": "多云",
                        },
                        "feelsLikeC": {
                            "type": "number",
                            "description": "当前体感摄氏温度",
                            "sampleValue": 27,
                        },
                        "humidityPercent": {
                            "type": "number",
                            "description": "当前相对湿度百分比",
                            "sampleValue": 68,
                        },
                        "airQuality": {
                            "type": "string",
                            "description": "当前空气质量等级",
                            "sampleValue": "优",
                        },
                        "windDirection": {
                            "type": "string",
                            "description": "当前风向",
                            "sampleValue": "东南风",
                        },
                        "windLevel": {
                            "type": "integer",
                            "description": "当前风力等级",
                            "sampleValue": 2,
                        },
                        "uvIndex": {
                            "type": "string",
                            "description": "当前紫外线等级",
                            "sampleValue": "中等",
                        },
                        "coldLevel": {
                            "type": "string",
                            "description": "当前感冒指数",
                            "sampleValue": "较低",
                        },
                        "alertLevel": {
                            "type": "string",
                            "description": "当前天气预警信息",
                            "sampleValue": "无预警",
                        },
                    },
                    "daily": [
                        {
                            "date": {
                                "type": "string",
                                "description": "预报日期",
                                "sampleValue": "2026-07-15",
                            },
                            "weekday": {
                                "type": "string",
                                "description": "星期文本",
                                "sampleValue": "星期三",
                            },
                            "condition": {
                                "type": "string",
                                "description": "白天天气现象",
                                "sampleValue": "多云",
                            },
                            "temperatureRangeText": {
                                "type": "string",
                                "description": "适合直接显示的温度范围",
                                "sampleValue": "24℃ / 31℃",
                            },
                            "rainProbabilityPercent": {
                                "type": "string",
                                "description": "白天降雨概率百分比",
                                "sampleValue": "20%",
                            },
                        }
                    ],
                }
            }
        },
        "assetCandidates": [
            {
                "id": "asset.sun_max",
                "src": "resources/base/media/sun_max.svg",
                "description": "天气晴朗和亮度信息使用的太阳图标",
            },
            {
                "id": "asset.drop_1",
                "src": "resources/base/media/drop_1.svg",
                "description": "湿度和降雨信息使用的水滴图标",
            },
            {
                "id": "asset.thermometer_sun_fill",
                "src": "resources/base/media/thermometer_sun_fill.svg",
                "description": "温度和体感信息使用的温度计太阳图标",
            },
        ],
    }


def main() -> int:
    """临时验证 Design Compact DSL 生成及标准 A2UI DSL 转换链路。"""
    system_prompt = A2UIProtocolRegistry.read_design_prompt(
        DESIGN_COMPACT_PROFILE_ID
    )
    task_spec = _build_design_test_task_spec()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(task_spec, ensure_ascii=False),
        },
    ]
    client = A2UIModelClient(use_mock=False, backend="llmclient")
    design_profile = {
        "id": DESIGN_COMPACT_PROFILE_ID,
        "format": "compact-dsl",
    }
    design_dsl = client.generate(messages, design_profile)
    final_dsl = client.convert_design_dsl_to_standard_dsl(
        design_dsl,
        size=task_spec["size"],
        design_profile_id=DESIGN_COMPACT_PROFILE_ID,
    )
    print("\n=== Final A2UI DSL ===")
    print(final_dsl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
