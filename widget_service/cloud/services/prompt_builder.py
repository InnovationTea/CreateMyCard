# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from models.generation import TaskSpec
from models.service import A2UIPromptPayload, A2UIPromptProtocolProfile, A2UIPromptUserMessage


class PromptBuilder:
    def build(
        self, task_spec: TaskSpec, protocol_profile: dict, removed_capability_summary: str = ""
    ) -> A2UIPromptPayload:
        """构造 A2UI 模型输入。

        入参：
        - task_spec：微服务构造的模型任务输入。
        - protocol_profile：当前版本 A2UI 协议 profile。
        - removed_capability_summary：能力降级或移除摘要。
        出参：模型调用所需的 system 和 user 输入结构。
        """
        return A2UIPromptPayload(
            system=(
                "Generate HarmonyOS A2UI Form genui JSONL only. "
                "Use exactly createSurface, updateComponents, updateDataModel in order."
            ),
            user=A2UIPromptUserMessage(
                taskSpec=task_spec.model_dump(mode="json", exclude_none=True),
                protocolProfile=A2UIPromptProtocolProfile(
                    id=protocol_profile["id"],
                    version=protocol_profile["version"],
                    catalogId=protocol_profile["catalogId"],
                    sizes=protocol_profile["sizes"],
                    componentWhitelist=protocol_profile["componentWhitelist"],
                ),
                degradationContext=removed_capability_summary,
            ),
        )
