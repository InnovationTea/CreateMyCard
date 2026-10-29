"""静态 Plan 第二次提交的复核封装；只核合同与证据来源，不推断语义。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from services.compact_plan_output import decode_plan_json


class StaticPlanReviewError(ValueError):
    """复核没有提供可执行的明确结论，不得当作确认沿用。"""


@dataclass(frozen=True)
class StaticPlanReview:
    decision: str
    source_fidelity: str
    findings: tuple[dict[str, Any], ...]
    corrected_source: str | None = None
    warnings: tuple[str, ...] = ()


def static_plan_unreferenced_source(plan: dict[str, Any], source: str) -> list[str]:
    """机械列出未被来源引用覆盖的原文，不把引用缺口推断为展示遗漏。"""
    normalized_source = source.replace("\r\n", "\n").replace("\r", "\n")
    ranges: list[tuple[int, int]] = []
    for fact in plan.get("info_required", []):
        for quote in fact.get("sourceTexts", []):
            if not isinstance(quote, str) or not quote:
                continue
            normalized_quote = quote.replace("\r\n", "\n").replace("\r", "\n")
            start = normalized_source.find(normalized_quote)
            while start >= 0:
                ranges.append((start, start + len(normalized_quote)))
                start = normalized_source.find(normalized_quote, start + 1)
    fragments = []
    cursor = 0
    for start, end in sorted(ranges):
        if start > cursor:
            fragments.append(normalized_source[cursor:start])
        cursor = max(cursor, end)
    if cursor < len(normalized_source):
        fragments.append(normalized_source[cursor:])
    return [fragment for fragment in fragments if fragment.strip(" \t\n，。；;、,.：:")]


def _display_text_slots(groups: list[Any]) -> list[dict[str, Any]]:
    result = []
    for group in groups:
        fields = {}
        for name, values in group.property_parts:
            if values:
                fields[name] = list(values)
        result.append({"texts": list(group.parts), "fields": fields})
    return result


def static_plan_display_evidence(plan: dict[str, Any]) -> dict[str, Any]:
    """复用展示读取器，只提供候选文字及其分区，不向模型注入重排 DSL。"""
    from services.card_validation.compact_validation.semantic.static_content import (
        static_display_groups,
    )
    from services.compact_dsl_a2ui_converter import CompactDslConversionError

    source = plan.get("staticPresentation")
    if not isinstance(source, str) or not source.strip():
        return {"status": "unknown", "reason": "no_candidate"}
    try:
        objects, shared = static_display_groups(source)
    except CompactDslConversionError:
        return {"status": "unknown", "reason": "unreadable_candidate"}
    if not objects and not shared:
        return {"status": "unknown", "reason": "no_display_text"}
    return {
        "status": "available",
        "objects": _display_text_slots(objects),
        "shared": _display_text_slots(shared),
    }


def _group_visible_parts(group: dict[str, Any], facts: list[dict[str, Any]]) -> list[str]:
    parts = []
    identity = group.get("identity")
    if isinstance(identity, str):
        parts.append(identity)
    for index in group.get("factIndexes", []):
        text = facts[index].get("text")
        if isinstance(text, str):
            parts.append(text)
    return parts


def _group_sources(group: dict[str, Any], facts: list[dict[str, Any]]) -> set[str]:
    sources = set()
    for index in group.get("factIndexes", []):
        sources.update(facts[index].get("sourceTexts", []))
    return sources


def static_review_lost_must_indexes(
    original: dict[str, Any], corrected: dict[str, Any],
) -> tuple[int, ...]:
    """仅核已解析的preserved改排；不从引用、说明或其它对象补展示文字。"""
    from services.card_validation.compact_validation.semantic.static_content import (
        _fact_covered,
        _identity_covered,
    )

    old_facts = original.get("info_required", [])
    new_facts = corrected.get("info_required", [])
    new_groups = corrected.get("contentGroups", [])
    shared_parts = []
    for group in new_groups:
        if group.get("kind") == "shared":
            shared_parts.extend(_group_visible_parts(group, new_facts))
    missing = []
    for group in original.get("contentGroups", []):
        matches = []
        for candidate in new_groups:
            if candidate.get("kind") != group.get("kind"):
                continue
            if group.get("kind") == "shared":
                matches.append(candidate)
                continue
            identity = group.get("identity")
            if isinstance(identity, str):
                same_object = _identity_covered(
                    identity, _group_visible_parts(candidate, new_facts),
                )
            else:
                same_object = bool(
                    _group_sources(group, old_facts) & _group_sources(candidate, new_facts)
                )
            if same_object:
                matches.append(candidate)
        parts = []
        if group.get("kind") == "shared" or len(matches) == 1:
            for candidate in matches:
                parts.extend(_group_visible_parts(candidate, new_facts))
            if group.get("kind") == "object":
                parts.extend(shared_parts)
        for index in group.get("factIndexes", []):
            fact = old_facts[index]
            protected = fact.get("protectedTexts") or fact.get("preserveVerbatim")
            required = fact.get("priority") == "must" or protected
            if required and not _fact_covered(fact, parts):
                missing.append(index)
    return tuple(missing)


def _decode_review(raw_output: str) -> tuple[Any, tuple[str, ...]]:
    """仅恢复缺失的最外层闭合符，不补值、内部结构或重复键。"""
    text = raw_output.strip()
    try:
        return decode_plan_json(text), ()
    except json.JSONDecodeError as exc:
        if exc.pos != len(text) or not text.startswith("{"):
            raise
        if not text.endswith(("}", "]")):
            raise
        payload = decode_plan_json(text + "}")
        return payload, ("Static review outer JSON closing brace restored; values unchanged.",)


def _findings(value: Any, source: str, fact_count: int) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise StaticPlanReviewError("findings 必须是数组。")
    normalized_source = source.replace("\r\n", "\n").replace("\r", "\n")
    result = []
    for finding in value:
        if not isinstance(finding, dict):
            raise StaticPlanReviewError("每条 findings 必须是对象。")
        if set(finding) != {"sourceText", "factIndexes", "issue"}:
            raise StaticPlanReviewError("findings 只接受 sourceText、factIndexes 和 issue。")
        quote = finding.get("sourceText")
        issue = finding.get("issue")
        if not isinstance(quote, str) or not quote.strip():
            raise StaticPlanReviewError("复核问题必须引用非空原始事实证据。")
        normalized_quote = quote.replace("\r\n", "\n").replace("\r", "\n")
        if normalized_quote not in normalized_source:
            raise StaticPlanReviewError("复核 sourceText 不在本轮有效事实源中。")
        if not isinstance(issue, str) or not issue.strip():
            raise StaticPlanReviewError("复核问题必须给出非空 issue。")
        indexes = finding.get("factIndexes")
        if not isinstance(indexes, list):
            raise StaticPlanReviewError("factIndexes 必须是首份计划的索引数组。")
        seen = set()
        for index in indexes:
            if type(index) is not int or not 0 <= index < fact_count:
                raise StaticPlanReviewError("复核事实索引超出首份计划范围。")
            if index in seen:
                raise StaticPlanReviewError("复核事实索引不得重复。")
            seen.add(index)
        result.append(dict(finding))
    return tuple(result)


def parse_static_plan_review(
    raw_output: str, *, source: str, fact_count: int,
) -> StaticPlanReview:
    """严格解析 keep/correct，修正 Plan 的事实与结构仍交原解析器。"""
    try:
        payload, warnings = _decode_review(raw_output)
    except ValueError as exc:
        raise StaticPlanReviewError("静态复核必须返回唯一、无重复键的纯 JSON 对象。") from exc
    if not isinstance(payload, dict):
        raise StaticPlanReviewError("静态复核必须返回 JSON 对象。")
    required = {"decision", "sourceFidelity", "findings"}
    if not required.issubset(payload) or set(payload) - required - {"correctedPlan"}:
        raise StaticPlanReviewError("静态复核字段不完整或包含未知字段。")
    decision = payload.get("decision")
    fidelity = payload.get("sourceFidelity")
    if decision not in ("keep", "correct"):
        raise StaticPlanReviewError("decision 必须为 keep 或 correct。")
    if fidelity not in ("preserved", "needs_correction"):
        raise StaticPlanReviewError("sourceFidelity 必须为 preserved 或 needs_correction。")
    findings = _findings(payload.get("findings"), source, fact_count)
    if fidelity == "preserved" and findings:
        raise StaticPlanReviewError("preserved 不得同时报告语义问题。")
    if fidelity == "needs_correction" and not findings:
        raise StaticPlanReviewError("needs_correction 必须给出可追溯的问题证据。")
    corrected_source = None
    if decision == "keep":
        if fidelity != "preserved" or "correctedPlan" in payload:
            raise StaticPlanReviewError("keep 只能确认原计划语义完整，且不得夹带新计划。")
    else:
        corrected = payload.get("correctedPlan")
        if not isinstance(corrected, dict):
            raise StaticPlanReviewError("correct 必须提交完整 correctedPlan 对象。")
        if set(corrected) != {"name", "arguments"}:
            raise StaticPlanReviewError("correctedPlan 必须使用原 submit_card_plan 包装。")
        if corrected.get("name") != "submit_card_plan":
            raise StaticPlanReviewError("correctedPlan 只能提交 submit_card_plan。")
        if not isinstance(corrected.get("arguments"), dict):
            raise StaticPlanReviewError("correctedPlan.arguments 必须为对象。")
        corrected_source = json.dumps(corrected, ensure_ascii=False, separators=(",", ":"))
    return StaticPlanReview(decision, fidelity, findings, corrected_source, warnings)
