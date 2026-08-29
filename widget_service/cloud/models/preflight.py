# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from core.errors import ErrorCode
from models.capability import AssetCapability, DataCapability, RemovedCapability
from models.generation import CandidateDataBinding, CardSpec, EventAction, TaskSpec


class AgentAction(StrEnum):
    """主 Agent 收到前置错误后可以执行的受控动作。"""

    FIX_AND_RETRY = "FIX_AND_RETRY"
    REFRESH_CAPABILITIES = "REFRESH_CAPABILITIES"
    REMOVE_OPTIONAL_CANDIDATE = "REMOVE_OPTIONAL_CANDIDATE"
    STOP = "STOP"


class PreflightIssue(BaseModel):
    """不包含实际敏感值的单个生成前置问题。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    path: str
    message: str
    expected: str = ""
    actualType: str = ""
    agentAction: AgentAction
    retryable: bool
    capabilityId: str = ""
    repairInstruction: str = ""
    referenceSource: str = ""


@dataclass(frozen=True)
class GenerationPreflightResult:
    """一次生成前置裁决的具名结果。"""

    effective_bindings: tuple[CandidateDataBinding, ...]
    effective_data_capabilities: tuple[DataCapability, ...]
    effective_events: tuple[EventAction, ...]
    effective_assets: tuple[AssetCapability, ...]
    removed_capabilities: tuple[RemovedCapability, ...]
    blocking_issues: tuple[PreflightIssue, ...]
    warnings: tuple[PreflightIssue, ...]
    card_spec: CardSpec | None
    task_spec: TaskSpec | None


class GenerationPreflightError(ValueError):
    """阻止模型调用并向插件错误帧提供结构化详情。"""

    def __init__(self, result: GenerationPreflightResult) -> None:
        self.result = result
        self.error_code = self._primary_error_code(result.blocking_issues)
        super().__init__(
            f"generation preflight rejected {len(result.blocking_issues)} issue(s)"
        )

    def details(self) -> dict:
        retryable = all(issue.retryable for issue in self.result.blocking_issues)
        action_set = {issue.agentAction for issue in self.result.blocking_issues}
        action_order = (
            AgentAction.STOP,
            AgentAction.REFRESH_CAPABILITIES,
            AgentAction.FIX_AND_RETRY,
            AgentAction.REMOVE_OPTIONAL_CANDIDATE,
        )
        required_actions = [
            action.value for action in action_order if action in action_set
        ]
        return {
            "stage": "generationPreflight",
            "modelCalled": False,
            "retryable": retryable,
            "requiredActions": required_actions,
            "agentInstruction": (
                "按 requiredActions 顺序处理，并结合本轮能力概述和数据 schema 修正全部 issues；"
                "不得原样重试，不得交给模型 repair。候选数据集合变化后必须重新检查权限。"
            ),
            "issues": [
                issue.model_dump(mode="json") for issue in self.result.blocking_issues
            ],
            "warnings": [
                issue.model_dump(mode="json") for issue in self.result.warnings
            ],
        }

    @staticmethod
    def _primary_error_code(issues: tuple[PreflightIssue, ...]) -> ErrorCode:
        codes = {issue.code for issue in issues}
        if ErrorCode.UNKNOWN_CAPABILITY.value in codes:
            return ErrorCode.UNKNOWN_CAPABILITY
        if ErrorCode.WRITE_RESULT_CONFLICT.value in codes:
            return ErrorCode.WRITE_RESULT_CONFLICT
        return ErrorCode.INVALID_ARGUMENTS
