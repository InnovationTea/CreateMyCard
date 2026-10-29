"""静态计划仅试排，不识别语义或替模型删改展示内容。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.card_validation.compact_validation.semantic.static_content import (
    _comparison_text,
    _identity_covered,
)


def _shortened_name(alias: str, identity: str) -> bool:
    """仅定位逐字删短的命名提醒；不据此认可别名或改变覆盖校验。"""
    brackets = str.maketrans("", "", "()（）")
    alias = alias.translate(brackets)
    identity = identity.translate(brackets)
    if not alias or alias == identity:
        return False
    position = 0
    for character in identity:
        if position < len(alias) and character == alias[position]:
            position += 1
    return position == len(alias)


def _source_name_differs(identity: str, text: str, source: str) -> bool:
    """来源完整名称与展示简称之外须保留同一完整前缀或后缀。"""
    if source.startswith(identity):
        remainder = source.removeprefix(identity)
        if remainder and text.endswith(remainder):
            if _shortened_name(text.removesuffix(remainder), identity):
                return True
    if source.endswith(identity):
        remainder = source.removesuffix(identity)
        if remainder and text.startswith(remainder):
            if _shortened_name(text.removeprefix(remainder), identity):
                return True
    return False


def _group_name_feedback(
    identity: str, indexed_facts: list[tuple[int, dict[str, Any]]], group_index: int,
) -> str | None:
    texts = []
    for _index, fact in indexed_facts:
        text = fact.get("text")
        if isinstance(text, str):
            texts.append(text)
    if _identity_covered(identity, texts):
        return None
    normalized_identity = _comparison_text(identity)
    result: str | None = None
    for fact_index, fact in indexed_facts:
        text = fact.get("text")
        sources = fact.get("sourceTexts")
        if not isinstance(text, str) or not isinstance(sources, list):
            continue
        normalized_text = _comparison_text(text)
        for source in sources:
            if not isinstance(source, str):
                continue
            if not _source_name_differs(
                normalized_identity, normalized_text, _comparison_text(source),
            ):
                continue
            excerpt = text[:180]
            if len(text) > 180:
                excerpt += "……（截取；完整文字见本次Plan）"
            result = (
                f"contentGroups[{group_index}].identity={identity!r}，"
                f"info_required[{fact_index}].text={excerpt!r}："
                "该来源片段的其余文字未变，名称处出现另一删短版本，请核对是否需要统一。"
            )
            break
        if result is not None:
            break
    return result


def _name_consistency_feedback(
    facts: list[dict[str, Any]], groups: list[dict[str, Any]],
) -> tuple[str, ...]:
    reminders = []
    for group_index, group in enumerate(groups):
        identity = group.get("identity")
        indexes = group.get("factIndexes")
        if group.get("kind") != "object" or not isinstance(identity, str):
            continue
        if not identity.strip() or not isinstance(indexes, list):
            continue
        indexed_facts = []
        for index in indexes:
            if type(index) is not int or not 0 <= index < len(facts):
                continue
            indexed_facts.append((index, facts[index]))
        reminder = _group_name_feedback(identity, indexed_facts, group_index)
        if reminder is not None:
            reminders.append(reminder)
    if reminders:
        reminders.insert(
            0,
            "名称一致性提醒（非校验错误）：identity是最终可见名称；若text已有同对象简称，"
            "在本次Plan内原子统一名称版本，保留来源、数字、限定语及保护文字。"
            "独立名称标签加正文仍然合法，不必把identity塞入每条text；"
            "以下仅为需核对的字面证据，不证明语义冲突，也不自动改写或授权省略。",
        )
    return tuple(reminders)


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
    if feedback:
        feedback += _name_consistency_feedback(facts, groups)
    return StaticPlanSelection(
        facts, groups, [], presentation=trial.source, trial_errors=feedback,
    )


def normalize_static_record_table(source: str) -> str:
    """新合同不再将模型超额记录静默转换为通用属性表。"""
    return source
