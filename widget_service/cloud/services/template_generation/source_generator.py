"""可由不同服务入口配置的模板源生成器对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from custom.model_runtime import ModelExecutionRuntime
from models.generation import CandidateDataBinding, ModelRequestContext, TaskSpec
from services.generation_pipeline import DslProcessorKind
from services.template_generation.facade import request_template_source_dsl


@dataclass
class TemplateSourceGenerator:
    """保存入口差异，并由策略层补齐模板源生成所需的运行时上下文。"""

    enable_fusion_ball: bool = True
    trusted_template_candidate_ids: tuple[str, ...] = ()
    trusted_template_action_ids: tuple[str, ...] = ()
    trusted_template_sample_overrides: dict[str, Any] = field(default_factory=dict)
    processor_kind: DslProcessorKind | None = field(default=None, init=False)
    protocol_profile: dict[str, Any] | None = field(default=None, init=False)
    model_runtime: ModelExecutionRuntime | None = field(default=None, init=False)
    model_request_context: ModelRequestContext | None = field(default=None, init=False)

    async def __call__(
        self,
        task_spec: TaskSpec,
        card_spec: dict[str, Any],
        effective_bindings: tuple[CandidateDataBinding, ...],
    ) -> str:
        """在策略层完成配置后调用模板生成门面。"""
        if self.processor_kind is None:
            raise RuntimeError("TemplateSourceGenerator processor kind is not configured")
        if self.protocol_profile is None:
            raise RuntimeError("TemplateSourceGenerator protocol profile is not configured")
        if self.model_request_context is None:
            raise RuntimeError("TemplateSourceGenerator model context is not configured")
        return await request_template_source_dsl(
            task_spec,
            card_spec,
            effective_bindings,
            processor_kind=self.processor_kind,
            protocol_profile=self.protocol_profile,
            model_runtime=self.model_runtime,
            model_request_context=self.model_request_context,
            enable_fusion_ball=self.enable_fusion_ball,
            trusted_template_candidate_ids=self.trusted_template_candidate_ids,
            trusted_template_action_ids=self.trusted_template_action_ids,
            trusted_template_sample_overrides=self.trusted_template_sample_overrides,
        )
