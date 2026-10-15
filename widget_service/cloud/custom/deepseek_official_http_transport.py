# -*- coding: utf-8 -*-
"""DeepSeek官方HTTP适配；保留原配置、请求体、错误码及生命周期。"""

import httpx

from config.config import Settings
from custom.openai_compatible_http_transport import (
    OpenAICompatibleHttpOptions,
    OpenAICompatibleHttpTransport,
)


class DeepSeekOfficialHttpTransport(OpenAICompatibleHttpTransport):
    """将官方通道配置映射到共享非流式传输。"""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        options = OpenAICompatibleHttpOptions(
            url=settings.deepseek_official_http_url,
            api_key=settings.deepseek_official_http_api_key,
            model=settings.deepseek_official_http_model,
            temperature=settings.deepseek_official_http_temperature,
            top_p=settings.deepseek_official_http_top_p,
            max_tokens=settings.deepseek_official_http_max_tokens,
            thinking_enabled=settings.deepseek_official_http_enable_thinking,
            display_name="DeepSeek official HTTP",
            log_prefix="[DeepSeek Official HTTP]",
        )
        super().__init__(settings, options, http_client)
