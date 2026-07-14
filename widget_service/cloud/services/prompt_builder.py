# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

from config.config import get_settings
from models.generation import TaskSpec
from services.compact_dsl_protocol import build_compact_dsl_system_prompt, is_compact_dsl

SYSTEM_PROMPT = get_settings().system_prompt


class PromptBuilder:
    def build(
            self,
            task_spec: TaskSpec,
            protocol_profile: dict | None = None,
            removed_capability_summary: str = "",
    ) -> list[dict[str, str]]:
        """构造 A2UI 模型输入。

        入参：
        - task_spec：微服务构造的模型任务输入。
        - protocol_profile：当前版本 A2UI 协议 profile。
        - removed_capability_summary：能力降级或移除摘要。
        出参：模型调用所需的 system 和 user 输入结构。
        """
        if protocol_profile and is_compact_dsl(protocol_profile):
            generation_context = {
                "taskSpec": task_spec.model_dump(mode="json", exclude_none=True),
                "protocolProfile": {
                    "id": protocol_profile["id"],
                    "version": protocol_profile["version"],
                    "catalogId": protocol_profile["catalogId"],
                    "sizes": protocol_profile["sizes"],
                    "componentWhitelist": protocol_profile["componentWhitelist"],
                },
                "degradationContext": removed_capability_summary,
            }
            system_prompt = "\n".join(
                [
                    build_compact_dsl_system_prompt(protocol_profile),
                    "Generation context JSON:",
                    json.dumps(generation_context, ensure_ascii=False, separators=(",", ":")),
                ]
            )
        else:
            system_prompt = SYSTEM_PROMPT.replace(
                "{{TASK_SPEC_JSON}}", task_spec.model_dump_json()
            )

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
