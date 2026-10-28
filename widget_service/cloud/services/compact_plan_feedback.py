"""失败静态 Plan 的引用关系账本；只解释提交，不修补事实或替代正式校验。"""

from __future__ import annotations

from typing import Any

from services.compact_plan_output import (
    decode_plan_json,
    normalize_plan_output,
    normalize_plan_root_arguments,
)

_MAX_ROWS = 24
_MAX_RAW_CHARS = 131072
_TEXT_PREVIEW_CHARS = 120
_REPAIR_INSTRUCTION = (
    "以下账本只描述这次失败提交，索引均来自本次info_required；不是新Plan或删除授权。"
    "下一次原子同步info_required、contentGroups及omittedContents：保留的每条text恰好归属一组，"
    "Action不分组、不省略；合并或调整事实后重算全部索引。"
    "空factIndexes的遗漏说明只记录未选输入，不能解除仍在info_required中的事实归属义务；"
    "不得仅删contentGroups或写一条遗漏说明就宣称事实已移除。"
    "计划内遗漏引用仅可指向无保护should，must、保护原文及用户要求完整的内容不得借此删除。"
    "requirement、text和sourceTexts均为原提交摘录，来源真实性仍须对照原始需求，不由此账本确认。"
)


def _submitted_arguments(raw_output: str) -> dict[str, Any] | None:
    try:
        text = normalize_plan_output(raw_output).text.strip()
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            if lines[0].strip().lower() in {"```", "```json"}:
                text = "\n".join(lines[1:-1])
        payload = decode_plan_json(text)
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict) or payload.get("name") != "submit_card_plan":
        return None
    payload = normalize_plan_root_arguments(payload).payload
    arguments = payload.get("arguments")
    return arguments if isinstance(arguments, dict) else None


def _preview(value: Any) -> Any:
    result = value
    if isinstance(value, str) and len(value) > _TEXT_PREVIEW_CHARS:
        result = {
            "preview": value[:_TEXT_PREVIEW_CHARS],
            "originalChars": len(value),
            "truncated": True,
        }
    elif not isinstance(value, (str, int, float, bool, type(None))):
        result = {"invalidType": type(value).__name__}
    return result


def _text_array_preview(value: Any) -> Any:
    result = _preview(value)
    if isinstance(value, list):
        result = [_preview(item) for item in value[:_MAX_ROWS]]
        if len(value) > _MAX_ROWS:
            result = {
                "preview": result, "totalItems": len(value), "truncated": True,
            }
    return result


def _size_issues(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for field_name in ("info_required", "contentGroups", "omittedContents"):
        rows = arguments.get(field_name)
        if not isinstance(rows, list):
            continue
        if len(rows) > _MAX_ROWS:
            issues.append({"path": field_name, "actualItems": len(rows), "maxItems": _MAX_ROWS})
            continue
        if field_name == "info_required":
            continue
        for index, row in enumerate(rows):
            references = row.get("factIndexes") if isinstance(row, dict) else None
            if isinstance(references, list) and len(references) > _MAX_ROWS:
                issues.append({
                    "path": f"{field_name}[{index}].factIndexes",
                    "actualItems": len(references), "maxItems": _MAX_ROWS,
                })
    return issues


def _collect_references(
    rows: Any, field_name: str, fact_count: int, issues: list[dict[str, Any]],
) -> dict[int, list[str]]:
    references: dict[int, list[str]] = {}
    if not isinstance(rows, list):
        issues.append({"code": "array_required", "path": field_name})
        return references
    group_ids: dict[str, str] = {}
    for row_index, row in enumerate(rows):
        row_path = f"{field_name}[{row_index}]"
        if not isinstance(row, dict):
            issues.append({"code": "object_required", "path": row_path})
            continue
        identifier = row.get("id")
        if field_name == "contentGroups" and isinstance(identifier, str):
            earlier = group_ids.get(identifier)
            if earlier is not None:
                issues.append({
                    "code": "duplicate_group_id", "path": f"{row_path}.id",
                    "earlierPath": earlier, "submitted": _preview(identifier),
                })
            group_ids[identifier] = f"{row_path}.id"
        indexes = row.get("factIndexes")
        index_path = f"{row_path}.factIndexes"
        if not isinstance(indexes, list):
            issues.append({"code": "array_required", "path": index_path})
            continue
        if not indexes and field_name == "contentGroups":
            issues.append({"code": "empty_group", "path": index_path})
        seen: set[int] = set()
        for position, fact_index in enumerate(indexes):
            path = f"{index_path}[{position}]"
            if type(fact_index) is not int or not 0 <= fact_index < fact_count:
                issues.append({
                    "code": "invalid_fact_index", "path": path, "submitted": _preview(fact_index),
                    "factCount": fact_count,
                })
                continue
            references.setdefault(fact_index, []).append(path)
            if fact_index in seen:
                issues.append({"code": "repeated_fact_index", "path": path, "index": fact_index})
            seen.add(fact_index)
    return references


def _fact_entry(
    index: int, fact: Any, groups: dict[int, list[str]], omissions: dict[int, list[str]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    path = f"info_required[{index}]"
    group_refs = groups.get(index, [])
    omission_refs = omissions.get(index, [])
    entry: dict[str, Any] = {
        "index": index, "groupReferences": group_refs, "omissionRequests": omission_refs,
    }
    if not isinstance(fact, dict):
        issues.append({"code": "object_required", "path": path})
        entry["submitted"] = _preview(fact)
        return entry
    entry.update(
        requirement=_preview(fact.get("requirement")), priority=_preview(fact.get("priority")),
        text=_preview(fact.get("text")), actionId=_preview(fact.get("actionId")),
        submittedSourceTexts=_text_array_preview(fact.get("sourceTexts")),
        protectedTexts=_text_array_preview(fact.get("protectedTexts")),
        preserveVerbatim=_preview(fact.get("preserveVerbatim")),
    )
    if "text" in fact and len(group_refs) != 1:
        code = "ungrouped_text" if not group_refs else "multiply_grouped_text"
        issues.append({"code": code, "path": path, "groupReferences": group_refs})
    if "actionId" in fact and group_refs:
        issues.append({"code": "action_in_content_group", "path": path})
    protected = fact.get("protectedTexts") or fact.get("preserveVerbatim")
    eligible_omission = fact.get("priority") == "should" and not protected
    if omission_refs and (not eligible_omission or not isinstance(fact.get("text"), str)):
        issues.append({
            "code": "ineligible_omission_reference", "path": path,
            "omissionRequests": omission_refs,
        })
    return entry


def _omission_entries(rows: Any) -> list[dict[str, Any]]:
    entries = []
    if not isinstance(rows, list):
        return entries
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        references = row.get("factIndexes")
        entries.append({
            "path": f"omittedContents[{index}]", "description": _preview(row.get("description")),
            "factIndexes": _text_array_preview(references),
            "meaning": "unselected_input" if references == [] else "optional_fact_request",
        })
    return entries


def _group_entries(rows: Any) -> list[dict[str, Any]]:
    entries = []
    if not isinstance(rows, list):
        return entries
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        entries.append({
            "path": f"contentGroups[{index}]", "id": _preview(row.get("id")),
            "kind": _preview(row.get("kind")), "identity": _preview(row.get("identity")),
            "factIndexes": _text_array_preview(row.get("factIndexes")),
        })
    return entries


def static_plan_repair_feedback(raw_output: str) -> dict[str, Any] | None:
    """仅为关系不闭合的失败提交构造有界账本，不改输入或判定计划通过。"""
    if len(raw_output) > _MAX_RAW_CHARS:
        return {
            "status": "ledger_not_built_over_diagnostic_limit",
            "actualChars": len(raw_output), "maxChars": _MAX_RAW_CHARS,
            "instruction": "失败提交超过诊断读取上限，未截取部分事实或推断关系；以原错误为准。",
        }
    arguments = _submitted_arguments(raw_output)
    if arguments is None:
        return None
    size_issues = _size_issues(arguments)
    if size_issues:
        return {
            "status": "ledger_not_built_outside_contract_bounds", "limits": size_issues,
            "instruction": "提交数组超出当前合同，未截取部分事实建立账本。请先修正所列结构。",
        }
    facts = arguments.get("info_required")
    if not isinstance(facts, list):
        return None
    issues: list[dict[str, Any]] = []
    groups = _collect_references(
        arguments.get("contentGroups"), "contentGroups", len(facts), issues,
    )
    omissions = arguments.get("omittedContents", [])
    omission_refs = _collect_references(omissions, "omittedContents", len(facts), issues)
    ledger = []
    for index, fact in enumerate(facts):
        ledger.append(_fact_entry(index, fact, groups, omission_refs, issues))
    if not issues:
        return None
    return {
        "status": "inconsistent_submitted_references", "factCount": len(facts),
        "facts": ledger, "groupDeclarations": _group_entries(arguments.get("contentGroups")),
        "omissionDeclarations": _omission_entries(omissions),
        "issues": issues, "instruction": _REPAIR_INSTRUCTION,
    }
