"""模板 A2UI 字符串生成入口。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.logger import json_for_log, logger
from custom.model_runtime import ModelExecutionRuntime
from models.generation import (
    CandidateDataBinding,
    ModelRequestContext,
    TaskSpec,
    WidgetSize,
)
from services.template_generation.engine.pipeline import (
    generate_template_a2ui as generate_template_engine_a2ui,
)
from services.template_generation.model_client import create_template_model_client

_MODULE = "[Template Generation]"
ModelStartCallback = Callable[[WidgetSize], Awaitable[None]]


async def request_template_a2ui(
    task_spec: TaskSpec,
    card_spec: dict,
    effective_bindings: tuple[CandidateDataBinding, ...],
    *,
    model_runtime: ModelExecutionRuntime | None,
    model_request_context: ModelRequestContext,
    before_model_call: ModelStartCallback | None = None,
) -> str:
    """请求模板引擎生成 A2UI，不组装 TaskSpec、artifact 或接口响应。"""
    model_client = create_template_model_client(
        model_runtime,
        model_request_context,
    )
    if before_model_call is not None:
        await before_model_call(task_spec.size)
    output = await generate_template_engine_a2ui(
        task_spec,
        card_spec,
        effective_bindings,
        model_client,
    )
    logger.info(
        f"{_MODULE} a2ui_generated template_ids={json_for_log(output.template_ids)} "
        f"expanded_component_count={output.expanded_component_count}"
    )
    return output.a2ui
