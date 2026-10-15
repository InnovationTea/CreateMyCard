# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""独立的标准A2UI单步提示词，不依赖融合提示词和模板开关。"""

import copy
import json

from config.config import get_settings
from models.generation import TaskSpec
from services.single_step_contract import clean_fallback_plan, clean_font_requirements


class SingleStepPromptBuilder:
    @staticmethod
    def build(
        task_spec: TaskSpec,
        protocol_profile: dict,
        *,
        previous_genui: str | None = None,
        fallback_context: dict | None = None,
    ) -> list[dict[str, str]]:
        path = (
            get_settings().data_root
            / "protocol_profiles"
            / "single-step-a2ui"
            / "system.md"
        )
        system = path.read_text(encoding="utf-8")
        payload: dict = {
            "mode": "edit" if previous_genui is not None else "create",
            "taskSpec": task_spec.model_dump(mode="json", exclude={"appVersion"}),
            "catalogId": protocol_profile.get("catalogId"),
            "protocolDocuments": protocol_profile.get("documents", {}),
        }
        if previous_genui is not None:
            payload["previousGenui"] = previous_genui
            payload["editInstruction"] = task_spec.userQuery
        if fallback_context is not None:
            plan = clean_fallback_plan(fallback_context.get("acceptedPlan"))
            payload["fallbackFacts"] = plan.get("info_required", [])
            payload["fontRequirements"] = clean_font_requirements(
                fallback_context.get("fontRequirements")
            )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    @staticmethod
    def build_repair(
        initial_prompt: list[dict[str, str]],
        invalid_source_dsl: str,
        quality_errors: list[dict],
        *,
        previous_failures: list[list[dict]] | None = None,
        dsl_format: str = "a2ui-form",
        task_spec: TaskSpec | None = None,
        compact_plan: dict | None = None,
        repair_history: list[dict] | None = None,
        repair_strategy: dict | None = None,
        original_display_roles: dict | None = None,
    ) -> list[dict[str, str]]:
        del task_spec, compact_plan, repair_history, repair_strategy, original_display_roles
        if dsl_format != "a2ui-form":
            raise ValueError("Single-step repair only accepts standard A2UI")
        messages = copy.deepcopy(initial_prompt)
        messages.append({"role": "assistant", "content": invalid_source_dsl})
        payload = {
            "invalidSourceDsl": invalid_source_dsl,
            "qualityErrors": quality_errors,
            "previousFailures": previous_failures,
            "instruction": (
                "仅修复上述错误，保留未涉及内容和原合法字号；"
                "输出完整标准A2UI三行JSONL。"
            ),
        }
        messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
        return messages
