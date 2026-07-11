# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

from models.generation import TaskSpec
from config.config import get_settings

SYSTEM_PROMPT = get_settings().system_prompt


class PromptBuilder:
    def build(
            self, task_spec: TaskSpec
    ) -> list:
        """构造 A2UI 模型输入。

        入参：
        - task_spec：微服务构造的模型任务输入。
        - protocol_profile：当前版本 A2UI 协议 profile。
        - removed_capability_summary：能力降级或移除摘要。
        出参：模型调用所需的 system 和 user 输入结构。
        """

        system_prompt = SYSTEM_PROMPT.replace("{{TASK_SPEC_JSON}}", task_spec.model_dump_json())

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": task_spec.userQuery,
            }
        ]