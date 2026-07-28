# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Literal, Protocol

from config.config import Settings, get_settings

ModelBackend = Literal["mep", "llmclient"]


class ModelTransport(Protocol):
    """模型传输层只负责发送消息并返回完整原始文本。"""

    def generate(self, messages: list[dict[str, str]]) -> str:
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


def create_model_transport(
    backend: ModelBackend,
    settings: Settings | None = None,
) -> ModelTransport:
    """根据服务端选择的后端创建统一模型传输对象。"""
    if backend == "mep":
        from custom.mep_model_transport import MepModelTransport

        return MepModelTransport(settings or get_settings())
    if backend == "llmclient":
        from custom.llmclient_model_transport import LlmClientModelTransport

        return LlmClientModelTransport()
    raise ValueError(f"Unsupported model backend: {backend}")
