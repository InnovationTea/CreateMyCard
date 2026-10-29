# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any

from core.errors import ErrorCode, GenerationStatus
from models.capability import RemovedCapability
from models.generation import CompactDslRecoveryFact, CompactDslRetryContext
from models.service import ResponsePlan


def _recovered_static_omission(
    source: str, fact: CompactDslRecoveryFact, plan: dict[str, Any] | None,
) -> bool:
    """只有原对象归属与完整事实都可验证时，才撤销前轮实际省略记录。"""
    if not plan or fact.target != "text":
        return False
    facts = plan.get("info_required")
    groups = plan.get("contentGroups")
    if not isinstance(facts, list) or not isinstance(groups, list):
        return False
    matching_indexes = []
    for index, original in enumerate(facts):
        if not isinstance(original, dict):
            continue
        same_value = original.get(fact.target) == fact.value
        if same_value and original.get("requirement") == fact.requirement:
            matching_indexes.append(index)
    if len(matching_indexes) != 1:
        return False
    target_index = matching_indexes[0]
    from services.card_validation.compact_validation.semantic.static_content import (
        static_fact_coverage,
        static_group_errors,
    )

    # 其它旧事实可能在后续轮次合法省略；只复核本条和原对象身份，不借其它对象同值。
    allowed = tuple(index for index in range(len(facts)) if index != target_index)
    if static_group_errors(source, plan, allowed):
        return False
    for coverage in static_fact_coverage(source, plan, allowed):
        if coverage.fact_index == target_index:
            return coverage.visible
    return False


def merge_static_recovery_omissions(
    current: list[str], source: str, retry_context: CompactDslRetryContext | None,
) -> list[str]:
    """最终反馈承接前轮实际取舍，不改 Plan、DSL、发布校验或修复预算。"""
    from services.generation_content_policy import current_content_policy

    if not current_content_policy().is_static or retry_context is None:
        return current
    if not retry_context.capacity_recovery or not retry_context.omitted_facts:
        return current
    omitted = []
    for fact in retry_context.omitted_facts:
        if fact.target == "actionId":
            continue
        if not _recovered_static_omission(source, fact, retry_context.omission_plan):
            omitted.append(fact.requirement)
    result = []
    for requirement in omitted + current:
        if requirement and requirement not in result:
            result.append(requirement)
    return result


class ResponsePlanner:
    """把内部生成结果转换成工具状态和用户可读话术。"""

    def plan(
        self,
        requested_count: int,
        effective_count: int,
        removed: list[RemovedCapability],
        has_artifact: bool,
        generation_mode: str = "create",
        omitted_requirements: list[str] | None = None,
    ) -> ResponsePlan:
        """规划生成接口响应状态。

        入参：
        - requested_count：用户候选数据能力数量。
        - effective_count：过滤后有效数据能力数量。
        - removed：被移除能力列表。
        - has_artifact：是否已生成 artifact。
        - generation_mode：create 或 edit，用于选择用户话术。
        - omitted_requirements：最终有界兜底中实际省略的信息。
        出参：结构化响应规划结果。
        """
        if not has_artifact:
            return ResponsePlan(
                status=GenerationStatus.UNSUPPORTED,
                message="当前设备上没有可用的数据能力或入口能力，暂时不能生成这类实时卡片。你可以试试天气、日历或系统状态类卡片。",
                errorCode=ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
            )
        success_message = (
            "已按你的要求修改卡片。"
            if generation_mode == "edit"
            else "已为你生成可用的桌面卡片。"
        )
        if removed:
            reasons = "、".join(sorted({item.userReadableReason for item in removed}))
            optional_reason = (
                "；部分信息因卡片空间限制未展示"
                if omitted_requirements else ""
            )
            return ResponsePlan(
                status=GenerationStatus.DEGRADED,
                message=(
                    f"{reasons}{optional_reason}，已按可用能力完成本次修改。"
                    if generation_mode == "edit"
                    else f"{reasons}{optional_reason}，已先为你生成可用版本。"
                ),
            )
        if omitted_requirements:
            return ResponsePlan(
                status=GenerationStatus.DEGRADED,
                message=(
                    "部分信息因卡片空间限制未展示，已按其余内容完成本次修改。"
                    if generation_mode == "edit"
                    else "部分信息因卡片空间限制未展示，已先为你生成可用版本。"
                ),
            )
        if requested_count > 0 and effective_count == requested_count:
            return ResponsePlan(
                status=GenerationStatus.SUCCESS,
                message=success_message,
            )
        return ResponsePlan(
            status=GenerationStatus.SUCCESS,
            message=success_message,
        )
