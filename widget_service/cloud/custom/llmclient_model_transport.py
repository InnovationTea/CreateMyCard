# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio

from app.logger import json_for_log, logger
from custom.llmclient import LLMClientOptions, stream_genui
from custom.model_transport import ModelTransportError

_MODULE = "[LLMClient Model Transport]"


class LlmClientModelTransport:
    """适配现有 llmclient 流，保持其实现不变。"""

    def generate(self, messages: list[dict[str, str]]) -> str:
        """聚合 llmclient 的流式 Token，返回未经 DSL 处理的完整文本。"""

        async def collect_stream() -> str:
            options = LLMClientOptions()
            chunks = [chunk async for chunk in stream_genui(options, messages)]
            return "".join(chunks)

        try:
            result = asyncio.run(collect_stream())
            logger.info(f"{_MODULE} response_collected content={json_for_log(result)}")
            return result
        except ModelTransportError:
            raise
        except Exception as exc:
            logger.error(
                f"{_MODULE} generation_failed "
                f"error_type={type(exc).__name__} error={exc!r}"
            )
            raise ModelTransportError("llmclient model generation failed") from exc