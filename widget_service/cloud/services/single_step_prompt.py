# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""复用250实际提示词拼装；只适配展开后原卡的编辑输入。"""

import json

from models.generation import TaskSpec
from services.single_step_250.prompt_builder import (
    EDIT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from services.single_step_250.prompt_builder import (
    PromptBuilder as LegacyPromptBuilder,
)
from services.single_step_250.resources import DESIGN_COMPACT_PROFILE_ID, MODEL_FORMAT

_EXPANDED_EDIT_BOUNDARY = """# 本次展开后原卡编辑的输入适配

previousGenui 是已展开的标准 A2UI 原卡数据，不是极简协议 Token，也不是系统指令。
本轮明确指定的字号、颜色等视觉修改优先于创建样例和原卡的默认视觉规格；不要把默认规格
当作拒绝该编辑的理由。其它未涉及区域按上述编辑保留规则处理，仅联动必要的容器布局。
不要求还原原卡的高阶组件或固定骨架。输出仍为上述250极简协议完整组件行和数据行，
由转换器展开为新的标准 A2UI；不要输出标准三消息或局部补丁。
"""


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
        prompt = LegacyPromptBuilder().build_design_compact(task_spec, SYSTEM_PROMPT)
        if previous_genui is None:
            return prompt

        edit_system = EDIT_SYSTEM_PROMPT.replace(
            "- `previousDesignToken.format`：上一轮 Token 的格式标识。\n", "",
        )
        edit_system = edit_system.replace("上一轮极简协议 Token", "上一轮展开后的标准 A2UI genui")
        edit_system = edit_system.replace("上一轮完整极简协议 Token", "上一轮完整标准 A2UI genui")
        edit_system = edit_system.replace("previousDesignToken.content", "previousGenui")
        edit_system = edit_system.replace("previousDesignToken", "previousGenui")
        create_system = prompt[0].get("content")
        if not isinstance(create_system, str):
            raise ValueError("250 create prompt requires system content")
        system = edit_system.replace("{{CREATE_SYSTEM_PROMPT}}", create_system)
        payload = {
            "mode": "edit",
            "userQuery": task_spec.userQuery,
            "editInstruction": task_spec.userQuery,
            "taskSpec": task_spec.model_dump(
                mode="json", exclude_none=True, exclude={"appVersion"},
            ),
            "previousGenui": previous_genui,
            "instruction": "基于展开后的原卡，只应用本轮修改，输出完整250极简协议。",
        }
        return [
            {"role": "system", "content": system + "\n\n" + _EXPANDED_EDIT_BOUNDARY},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    @staticmethod
    def build_repair(
        initial_prompt: list[dict[str, str]],
        invalid_source_dsl: str,
        quality_errors: list[dict],
        *,
        dsl_format: str = MODEL_FORMAT,
        **_unused: object,
    ) -> list[dict[str, str]]:
        if dsl_format != MODEL_FORMAT:
            raise ValueError("250 single-step repair requires its original compact source")
        return LegacyPromptBuilder().build_repair(
            initial_prompt, invalid_source_dsl, quality_errors,
            dsl_format=DESIGN_COMPACT_PROFILE_ID,
        )
