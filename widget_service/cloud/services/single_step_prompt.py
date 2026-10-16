# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""新建完整复用250；编辑使用独立的展开原卡字段补丁。"""

from models.generation import TaskSpec
from services.single_step_250.prompt_builder import SYSTEM_PROMPT
from services.single_step_250.prompt_builder import (
    PromptBuilder as LegacyPromptBuilder,
)
from services.single_step_250.resources import DESIGN_COMPACT_PROFILE_ID, MODEL_FORMAT
from services.single_step_edit import EDIT_FORMAT, SingleStepEditPromptBuilder


class SingleStepPromptBuilder:
    @staticmethod
    def build(
        task_spec: TaskSpec,
        protocol_profile: dict,
        *,
        previous_genui: str | None = None,
        fallback_context: dict | None = None,
    ) -> list[dict[str, str]]:
        # 不把失败源、融合Plan或Recipe字号重新施加到250生成策略。
        del protocol_profile, fallback_context
        if previous_genui is not None:
            return SingleStepEditPromptBuilder.build(task_spec, previous_genui)
        return LegacyPromptBuilder().build_design_compact(task_spec, SYSTEM_PROMPT)

    @staticmethod
    def build_repair(
        initial_prompt: list[dict[str, str]],
        invalid_source_dsl: str,
        quality_errors: list[dict],
        *,
        dsl_format: str = MODEL_FORMAT,
        **_unused: object,
    ) -> list[dict[str, str]]:
        if dsl_format == EDIT_FORMAT:
            return SingleStepEditPromptBuilder.build_repair(
                initial_prompt, invalid_source_dsl, quality_errors,
            )
        if dsl_format != MODEL_FORMAT:
            raise ValueError("250 single-step repair requires its original compact source")
        return LegacyPromptBuilder().build_repair(
            initial_prompt, invalid_source_dsl, quality_errors,
            dsl_format=DESIGN_COMPACT_PROFILE_ID,
        )
