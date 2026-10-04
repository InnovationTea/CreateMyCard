"""本地画廊的显式模型配置适配；不修改生产配置或记录凭据。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import dotenv_values

from config.config import Settings, get_settings


@dataclass(frozen=True)
class GalleryHttpConfig:
    """显式配置的本地 OpenAI 兼容模型连接。"""

    base_url: str
    model: str
    api_key: str = field(repr=False)


def configure_gallery_environment(path: Path) -> GalleryHttpConfig | None:
    """将旧版 WIDGET_SERVICE_ 本地配置映射到当前 Settings 字段。"""
    if not path.is_file():
        raise FileNotFoundError(path)
    values = dotenv_values(path)
    current = get_settings()
    payload = current.model_dump()
    for name in Settings.model_fields:
        value = values.get(f"WIDGET_SERVICE_{name.upper()}")
        if value is not None:
            current_value = getattr(current, name)
            if isinstance(current_value, (list, tuple, dict)):
                payload[name] = json.loads(value)
            else:
                payload[name] = value
    payload["LOCAL_FLAG"] = True
    payload["enable_a2ui_model_mock"] = False
    payload["enable_artifact_validation"] = True
    selected_backend = payload.get("openai_master_client")
    http_config: GalleryHttpConfig | None = None
    if selected_backend == "deepseek_http":
        base_url = values.get("WIDGET_SERVICE_DEEPSEEK_API_URL")
        model = values.get("WIDGET_SERVICE_DEEPSEEK_MODEL")
        api_key = values.get("WIDGET_SERVICE_DEEPSEEK_API_KEY")
        if not base_url or not model or not api_key:
            raise ValueError("画廊本地 HTTP 模型配置不完整")
        http_config = GalleryHttpConfig(base_url, model, api_key)
        payload["openai_master_client"] = "llmclient"
        payload["openai_fallback_client"] = "llmclient"
    configured = Settings.model_validate(payload)
    for name in Settings.model_fields:
        setattr(current, name, getattr(configured, name))
    return http_config


class GalleryHttpTransport:
    """通过既有 runtime 注入真实 HTTP 调用，所有模板流程仍走正式入口。"""

    def __init__(self, config: GalleryHttpConfig) -> None:
        self.config = config

    def generate(self, messages: list[dict[str, str]], request_context: object = None) -> str:
        settings = get_settings()
        with httpx.Client(timeout=settings.model_request_timeout_seconds) as client:
            response = client.post(
                self.config.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json={
                    "model": self.config.model, "messages": messages,
                    "temperature": settings.deepseek_temperature,
                    "max_tokens": settings.deepseek_max_tokens,
                    "thinking": {"type": "disabled"}, "stream": False,
                },
            )
            if response.is_error:
                raise RuntimeError(f"画廊模型 HTTP 请求失败：{response.status_code}")
            payload = response.json()
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("画廊模型响应缺少 choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise ValueError("画廊模型 choices[0] 不是对象")
        message = first.get("message")
        if not isinstance(message, dict):
            raise ValueError("画廊模型响应缺少 message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("画廊模型响应缺少文本内容")
        return content
