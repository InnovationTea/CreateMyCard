# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelTokenUsage:
    """一次模型请求的最终累计 token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0

    @classmethod
    def from_stream_chunk(cls, chunk: dict[str, Any]) -> ModelTokenUsage | None:
        """从 OpenAI 兼容流式响应中读取当前累计 usage。"""
        usage = chunk.get("usage")
        if not isinstance(usage, dict):
            return None

        prompt_tokens = _first_token_count(
            usage,
            ("prompt_tokens", "input_tokens", "inputToken"),
        )
        completion_tokens = _first_token_count(
            usage,
            ("completion_tokens", "output_tokens", "outputToken"),
        )
        total_tokens = _first_token_count(
            usage,
            ("total_tokens", "totalToken"),
        )
        completion_details = usage.get("completion_tokens_details")
        if not isinstance(completion_details, dict):
            completion_details = {}
        reasoning_tokens = _first_token_count(
            completion_details,
            ("reasoning_tokens",),
        )
        if reasoning_tokens is None:
            reasoning_tokens = _first_token_count(usage, ("reasoning_tokens",))

        prompt_tokens = prompt_tokens or 0
        completion_tokens = completion_tokens or 0
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            reasoning_tokens=reasoning_tokens or 0,
        )


def sum_model_token_usage(records: Iterable[ModelTokenUsage]) -> ModelTokenUsage:
    """汇总同一次工具调用中全部模型请求的 token 用量。"""
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    reasoning_tokens = 0
    for record in records:
        prompt_tokens += record.prompt_tokens
        completion_tokens += record.completion_tokens
        total_tokens += record.total_tokens
        reasoning_tokens += record.reasoning_tokens
    return ModelTokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        reasoning_tokens=reasoning_tokens,
    )


def _first_token_count(data: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if not isinstance(value, int):
            continue
        if value < 0:
            continue
        return value
    return None
