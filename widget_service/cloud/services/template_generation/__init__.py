"""模板源 DSL 生成接口及蓝区兼容实现。"""

from typing import Any

from custom.model_runtime import ModelExecutionRuntime
from models.generation import CandidateDataBinding, ModelRequestContext, TaskSpec
from services.generation_pipeline import DslProcessorKind

from .facade import request_template_source_dsl
from .legacy_python import route_legacy_python_terse_generation


class FusionBallA2UIConversionError(ValueError):
    """保留绿区融合球转换异常接口。"""


def convert_a2ui_with_fusion_ball(a2ui_jsonl: str) -> str:
    """蓝区未启用融合球组件，直接返回原始 A2UI。"""
    return a2ui_jsonl


class TemplateSourceGenerator:
    """将绿区生成器接口适配到蓝区已有的模板生成函数。"""

    def __init__(
        self,
        *,
        enable_fusion_ball: bool = False,
        trusted_template_candidate_ids: tuple[str, ...] = (),
        trusted_template_action_ids: tuple[str, ...] = (),
        trusted_template_sample_overrides: dict[str, object] | None = None,
    ) -> None:
        del trusted_template_candidate_ids
        del trusted_template_action_ids
        del trusted_template_sample_overrides
        self.enable_fusion_ball = enable_fusion_ball
        self.processor_kind: DslProcessorKind | None = None
        self.protocol_profile: dict[str, Any] | None = None
        self.model_runtime: ModelExecutionRuntime | None = None
        self.model_request_context: ModelRequestContext | None = None

    async def __call__(
        self,
        task_spec: TaskSpec,
        card_spec: dict[str, Any],
        effective_bindings: tuple[CandidateDataBinding, ...],
    ) -> str:
        """复用蓝区模板入口生成源 DSL。"""
        if self.processor_kind is None or self.protocol_profile is None:
            raise RuntimeError("template source generator is not configured")
        if self.model_request_context is None:
            raise RuntimeError("template model request context is not configured")
        return await request_template_source_dsl(
            task_spec,
            card_spec,
            effective_bindings,
            processor_kind=self.processor_kind,
            protocol_profile=self.protocol_profile,
            model_runtime=self.model_runtime,
            model_request_context=self.model_request_context,
        )


__all__ = [
    "FusionBallA2UIConversionError",
    "TemplateSourceGenerator",
    "convert_a2ui_with_fusion_ball",
    "request_template_source_dsl",
    "route_legacy_python_terse_generation",
]
