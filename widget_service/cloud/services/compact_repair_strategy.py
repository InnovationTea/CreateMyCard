# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""为 Design Compact 质量修复选择逐级升级的执行范围。"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

_CAPACITY_MARKERS = (
    "vertical layout requires at least",
    "overflows by",
    "occupancy:",
    "within available height",
)
_STRUCTURE_MARKERS = (
    "compact layout does not match scope",
    "layout does not match",
    "slot root",
    "must have",
    "must use row",
    "must use column",
)


@dataclass(frozen=True)
class CompactRepairDirective:
    """一次 Design Compact 修复应采用的范围与策略。"""

    category: str
    scope: str
    repair_strategy: str
    retry_target: str
    fingerprint: str
    consecutive_failures: int
    category_attempt: int
    no_progress: bool
    retryable: bool
    instruction: str

    def to_prompt_payload(self) -> dict[str, Any]:
        """转换成可进入修复提示词和 Trace 的稳定字段。"""
        return {
            "category": self.category,
            "scope": self.scope,
            "repairStrategy": self.repair_strategy,
            "retryTarget": self.retry_target,
            "fingerprint": self.fingerprint,
            "consecutiveFailures": self.consecutive_failures,
            "categoryAttempt": self.category_attempt,
            "noProgress": self.no_progress,
            "retryable": self.retryable,
            "instruction": self.instruction,
        }


def _normalized_issue_message(message: str) -> str:
    """忽略每轮可变的 vp 数值，保留被违反的容器与约束。"""
    normalized = message.strip().lower()
    return re.sub(r"\b\d+(?:\.\d+)?vp\b", "<vp>", normalized)


def _issue_fingerprint(quality_errors: list[dict[str, Any]]) -> str:
    entries: list[tuple[str, str, str]] = []
    for issue in quality_errors:
        entries.append(
            (
                str(issue.get("stage") or ""),
                str(issue.get("code") or ""),
                _normalized_issue_message(str(issue.get("message") or "")),
            )
        )
    encoded = json.dumps(sorted(entries), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _contains_marker(messages: str, markers: tuple[str, ...]) -> bool:
    return any(marker in messages for marker in markers)


def _issue_category(quality_errors: list[dict[str, Any]]) -> str:
    codes = {str(issue.get("code") or "") for issue in quality_errors}
    messages = "\n".join(
        str(issue.get("message") or "").lower() for issue in quality_errors
    )
    if _contains_marker(messages, _CAPACITY_MARKERS):
        return "layout_capacity"
    if _contains_marker(messages, _STRUCTURE_MARKERS):
        return "layout_structure"
    if "COMPACT_PLAN_COVERAGE_FAILED" in codes:
        return "plan_coverage"
    if "ARTIFACT_VALIDATION_FAILED" in codes:
        return "artifact_validation"
    return "component_contract"


def _layout_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
) -> CompactRepairDirective:
    repeated_root_cause = consecutive_failures >= 2 or no_progress
    if repeated_root_cause:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        instruction = (
            "同一布局根因已经重复或上一轮 DSL 没有变化；放弃 invalidSourceDsl 的旧拓扑，"
            "从已接受 Plan 的全部硬事实和动作重新构造完整 DSL。"
        )
    elif category_attempt == 1:
        scope = "parent_layout" if category == "layout_structure" else "sublayout"
        strategy = "structural" if scope == "parent_layout" else "rebudget"
        instruction = (
            "修复违反合同的父布局结构，重新分配完整信息组和动作槽。"
            if scope == "parent_layout"
            else "重算受影响信息组的完整高度与间距，改用能闭合的合法子布局组合。"
        )
    elif category_attempt == 2:
        scope = "parent_layout"
        strategy = "structural"
        instruction = (
            "前一轮布局修复没有闭合；停止修改局部几何，重新选择父布局变体并分配全部事实。"
        )
    else:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        instruction = (
            "局部与父布局修复均未解决根因；放弃 invalidSourceDsl 的旧拓扑，"
            "从已接受 Plan 的全部硬事实和动作重新构造完整 DSL。"
        )
    return CompactRepairDirective(
        category=category,
        scope=scope,
        repair_strategy=strategy,
        retry_target="dsl_recompose",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
    )


def _non_layout_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
) -> CompactRepairDirective:
    repeated_root_cause = consecutive_failures >= 2 or no_progress
    if repeated_root_cause:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        retry_target = "dsl_recompose"
        instruction = (
            "同一局部错误已经重复或上一轮 DSL 没有变化；从已接受 Plan "
            "的全部硬事实和动作重建完整 DSL，不再修补原组件结构。"
        )
    elif category_attempt > 1:
        scope = "parent_layout"
        strategy = "structural"
        retry_target = "dsl_recompose"
        instruction = (
            "局部修复没有消除错误；保留全部事实与动作，重新组织受影响组件及其父布局，"
            "不要再次提交相同组件结构。"
        )
    else:
        scope = "information_group" if category == "plan_coverage" else "component"
        strategy = "coverage_restore" if category == "plan_coverage" else "targeted"
        retry_target = "dsl_local_repair"
        instruction = (
            "恢复缺失的 Plan 必须事实并复查其所属信息组，不删除其它已正确事实。"
            if category == "plan_coverage"
            else "只修复错误组件的 Props、绑定或格式，并复查直接父容器。"
        )
    return CompactRepairDirective(
        category=category,
        scope=scope,
        repair_strategy=strategy,
        retry_target=retry_target,
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
    )


def _exhausted_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
) -> CompactRepairDirective:
    return CompactRepairDirective(
        category=category,
        scope="full_dsl",
        repair_strategy="exhausted",
        retry_target="stop",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=False,
        instruction=(
            "完整 DSL 重组后仍出现同一根因或原样返回；"
            "停止重复调用模型，保留当前诊断并按校验失败处理。"
        ),
    )


class CompactRepairStrategyTracker:
    """在单次生成请求内跟踪失败指纹并选择下一轮修复范围。"""

    def __init__(self) -> None:
        self._previous_fingerprint: str | None = None
        self._previous_source: str | None = None
        self._consecutive_failures = 0
        self._category_attempts: dict[str, int] = {}
        self._previous_strategy: str | None = None

    def next_directive(
        self,
        invalid_source_dsl: str,
        quality_errors: list[dict[str, Any]],
    ) -> CompactRepairDirective:
        """根据当前失败和请求内历史选择局部修复或结构重组。"""
        category = _issue_category(quality_errors)
        fingerprint = _issue_fingerprint(quality_errors)
        if fingerprint == self._previous_fingerprint:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 1
        normalized_source = invalid_source_dsl.strip()
        no_progress = (
            self._previous_source is not None
            and normalized_source == self._previous_source
        )
        category_attempt = self._category_attempts.get(category, 0) + 1
        self._category_attempts[category] = category_attempt
        self._previous_fingerprint = fingerprint
        self._previous_source = normalized_source

        repeated_root_cause = self._consecutive_failures >= 2 or no_progress
        if repeated_root_cause and self._previous_strategy == "plan_guided_recompose":
            directive = _exhausted_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
            )
        elif category in {"layout_capacity", "layout_structure"}:
            directive = _layout_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
            )
        else:
            directive = _non_layout_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
            )
        self._previous_strategy = directive.repair_strategy
        return directive
