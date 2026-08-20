# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from collections.abc import Awaitable
from typing import Literal, Protocol

from models.generation import ModelRequestContext

ModelBackend = Literal["mep", "openai"]
ModelProvider = Literal["mep", "deepseek_platform", "llmclient"]


class ModelTransport(Protocol):
    """物理模型传输层只负责发送消息并返回完整原始文本。"""

    def generate(
        self,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None = None,
    ) -> str | Awaitable[str]:
        """发送模型消息并返回聚合后的原始输出。"""
        ...


class ModelTransportError(RuntimeError):
    """模型传输、协议解析或远端显式错误。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "",
        partial_output: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.partial_output = partial_output
