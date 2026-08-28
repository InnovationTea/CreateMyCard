# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Directly generate Design Compact DSL and standard A2UI from a TaskSpec."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from app.logger import logger
from config.config import get_settings
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from models.generation import TaskSpec
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry

_OUTPUT_SEPARATOR = "==========================="
_MODEL_FORMAT = "compact-dsl"


@dataclass(frozen=True)
class GeneratedDsl:
    """保留模型生成的极简协议和转换后的标准 A2UI DSL。"""

    compact_dsl: str
    dsl: str


async def generate_dsl_from_task_spec(task_spec: dict[str, Any]) -> GeneratedDsl:
    """复用第四接口的 Prompt、模型客户端和转换器，从 TaskSpec 生成 DSL。"""
    validated_task_spec = TaskSpec.model_validate(task_spec)
    task_spec_value = validated_task_spec.model_dump(mode="json", exclude_none=True)
    settings = get_settings()
    design_profile_id = settings.design_compact_profile_id
    system_prompt = A2UIProtocolRegistry.read_design_prompt(design_profile_id)
    prompt = PromptBuilder().build_design_compact(validated_task_spec, system_prompt)
    model_profile = {
        "id": design_profile_id,
        "format": _MODEL_FORMAT,
    }
    model_client = A2UIModelClient(
        backend=settings.design_compact_model_backend,
        operation_name="generateWidgetCardCompactDsl",
    )
    try:
        compact_dsl = await model_client.generate(prompt, model_profile)
        processing_context = DslProcessingContext(
            size=validated_task_spec.size,
            card_spec={},
            task_spec=task_spec_value,
            protocol_profile=A2UIProtocolRegistry.read_design_protocol_profile(
                design_profile_id
            ),
            design_profile_id=design_profile_id,
        )
        result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(
            compact_dsl,
            processing_context,
        )
        if result.errors:
            error_message = "; ".join(item.repair_message() for item in result.errors)
            raise A2UIModelGenerationError(error_message)
        return GeneratedDsl(compact_dsl=result.source_dsl, dsl=result.standard_dsl)
    finally:
        await model_client.aclose()


def main() -> None:
    """粘贴 TaskSpec JSON，生成并打印极简协议与转换后的标准 DSL。"""
    logger.remove()
    task_spec = json.loads(
        r"""
{
  "userQuery": "生成一张简洁的欢迎卡片",
  "size": "2x2",
  "eventCandidates": [],
  "dataModelSchema": {},
  "assetCandidates": []
}
"""
    )
    generated = asyncio.run(generate_dsl_from_task_spec(task_spec))
    print(generated.compact_dsl.rstrip())
    print(_OUTPUT_SEPARATOR)
    print(generated.dsl.rstrip())


if __name__ == "__main__":
    main()
