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
        payload = decode_plan_json(raw_output)
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
    return StaticPlanReview(decision, fidelity, findings, corrected_source)
