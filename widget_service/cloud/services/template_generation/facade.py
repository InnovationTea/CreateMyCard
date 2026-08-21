"""模板源 DSL 字符串生成入口。"""

from __future__ import annotations

from typing import Any

from app.logger import json_for_log, logger
from custom.model_runtime import ModelExecutionRuntime
from models.generation import (
    CandidateDataBinding,
    ModelRequestContext,
    TaskSpec,
)
from services.generation_pipeline import DslProcessorKind
from services.template_generation.binding_dependencies import enrich_template_bindings
from services.template_generation.engine.pipeline import (
    generate_template_a2ui as generate_template_engine_a2ui,
)
from services.template_generation.model_client import create_template_model_client
from services.template_generation.source_adapter import prepare_template_source_dsl

_MODULE = "[Template Generation]"


async def request_template_source_dsl(
    task_spec: TaskSpec,
    card_spec: dict,
    effective_bindings: tuple[CandidateDataBinding, ...],
    *,
    processor_kind: DslProcessorKind,
    protocol_profile: dict[str, Any],
    model_runtime: ModelExecutionRuntime | None,
    model_request_context: ModelRequestContext,
) -> str:
    """请求模板引擎并返回当前 Processor 可直接消费的源 DSL。"""
    model_client = create_template_model_client(
        model_runtime,
        model_request_context,
    )
    template_bindings = tuple(enrich_template_bindings(list(effective_bindings)))
    output = await generate_template_engine_a2ui(
        task_spec,
        card_spec,
        template_bindings,
        model_client,
    )
    source_dsl = prepare_template_source_dsl(
        output.a2ui,
        processor_kind=processor_kind,
        size=task_spec.size,
        protocol_profile=protocol_profile,
    )
    logger.info(
        f"{_MODULE} source_dsl_generated processor_kind={processor_kind} "
        f"template_ids={json_for_log(output.template_ids)} "
        f"expanded_component_count={output.expanded_component_count}"
    )
    return source_dsl
