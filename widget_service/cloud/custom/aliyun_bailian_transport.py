"""阿里云百炼OpenAI兼容HTTP通道，使用独立配置，不覆盖其它通道。"""

import httpx

from config.config import Settings
from custom.openai_compatible_http_transport import (
    OpenAICompatibleHttpOptions,
    OpenAICompatibleHttpTransport,
)


class AliyunBailianHttpTransport(OpenAICompatibleHttpTransport):
    """公共百炼或专属部署均使用完整非流式Chat Completions响应。"""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        endpoint = settings.aliyun_bailian_base_url.strip().rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        options = OpenAICompatibleHttpOptions(
            url=endpoint,
            api_key=settings.aliyun_bailian_api_key,
            model=settings.aliyun_bailian_model,
            temperature=settings.aliyun_bailian_temperature,
            top_p=settings.aliyun_bailian_top_p,
            max_tokens=settings.aliyun_bailian_max_tokens,
            thinking_enabled=settings.aliyun_bailian_enable_thinking,
            display_name="Aliyun Bailian HTTP",
            log_prefix="[Aliyun Bailian HTTP]",
        )
        super().__init__(settings, options, http_client)
