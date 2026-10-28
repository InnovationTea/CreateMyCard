"""静态计划仅试排，不识别语义或替模型删改展示内容。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StaticPlanSelection:
    facts: list[dict[str, Any]]
    groups: list[dict[str, Any]]
    notes: list[str]
    omitted_contents: tuple[str, ...] = ()
    presentation: str | None = None
    trial_errors: tuple[str, ...] = ()


def select_static_plan_content(
    facts: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    query: str,
    size: str,
    *,
    presentation_style: str = "auto",
) -> StaticPlanSelection:
    """有界候选只作为排版参考，未找到不证明所有合法排版不可行。"""
    from services.static_content_presentation import trial_static_presentation

    trial = trial_static_presentation(
        {
            "info_required": facts,
            "contentGroups": groups,
            "presentationStyle": presentation_style,
        },
        query,
        size,
    )
    feedback = tuple(error[:900] for error in trial.errors[:3])
    return StaticPlanSelection(
        facts, groups, [], presentation=trial.source, trial_errors=feedback,
    )


def normalize_static_record_table(source: str) -> str:
    """新合同不再将模型超额记录静默转换为通用属性表。"""
    return source
