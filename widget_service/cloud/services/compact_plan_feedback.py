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
    "Action不参与文本分组，准入仍由当前请求合同裁决；引用恢复不授权不支持的Action。"
    "合并或调整事实后重算全部索引。"
    "空factIndexes的遗漏说明只记录未选输入，不能解除仍在info_required中的事实归属义务；"
    "不得仅删contentGroups或写一条遗漏说明就宣称事实已移除。"
    "计划内遗漏引用仅可指向无保护should，must、保护原文及用户要求完整的内容不得借此删除。"
    "这仅说明Plan遗漏声明的权限，不覆盖后续程序明确授权的受控Drop；本账本不产生Drop授权。"
    "recoveries只说明主链路的确定性恢复规则，不是待修阻断，也不表示整份Plan通过；"
    "被撤销的遗漏申请不能删除任何仍保留的事实。"
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


def _is_effective_action(fact: Any) -> bool:
    if not isinstance(fact, dict) or not isinstance(fact.get("actionId"), str):
        return False
    return "text" not in fact or isinstance(fact.get("text"), str)


def _actions_need_no_groups(facts: list[Any]) -> bool:
    if not facts:
        return False
    for fact in facts:
        if not _is_effective_action(fact) or "dataId" in fact:
            return False
    return True


def _collect_group_references(
    rows: Any, facts: list[Any], issues: list[dict[str, Any]],
) -> dict[int, list[str]]:
    references: dict[int, list[str]] = {}
    if rows is None and _actions_need_no_groups(facts):
        return references
    if not isinstance(rows, list):
        issues.append({"code": "array_required", "path": "contentGroups"})
        return references
    group_ids: dict[str, str] = {}
    for row_index, row in enumerate(rows):
        row_path = f"contentGroups[{row_index}]"
        if not isinstance(row, dict):
            issues.append({"code": "object_required", "path": row_path})
            continue
        identifier = row.get("id")
        if isinstance(identifier, str):
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
        if not indexes:
            issues.append({"code": "empty_group", "path": index_path})
        seen: set[int] = set()
        for position, fact_index in enumerate(indexes):
            path = f"{index_path}[{position}]"
            if type(fact_index) is not int or not 0 <= fact_index < len(facts):
                issues.append({
                    "code": "invalid_fact_index", "path": path, "submitted": _preview(fact_index),
                    "factCount": len(facts),
                })
                continue
            references.setdefault(fact_index, []).append(path)
            if _is_effective_action(facts[fact_index]):
                continue
            if fact_index in seen:
                issues.append({"code": "repeated_fact_index", "path": path, "index": fact_index})
            seen.add(fact_index)
    return references


def _omission_resolution(indexes: list[Any], facts: list[Any], path: str) -> dict[str, Any] | None:
    """按主链路顺序区分授权撤销与仍阻断的引用，不推断去重后的删除资格。"""
    seen: set[int] = set()
    for position, index in enumerate(indexes):
        index_path = f"{path}.factIndexes[{position}]"
        if type(index) is not int or not 0 <= index < len(facts):
            return {
                "code": "omission_authorization_revoked", "path": path,
                "reason": "invalid_fact_index", "referencePath": index_path,
                "submitted": _preview(index),
            }
        if index in seen:
            return {"code": "repeated_fact_index", "path": index_path, "index": index}
        seen.add(index)
        fact = facts[index]
        if not isinstance(fact, dict) or not isinstance(fact.get("text"), str):
            return {"code": "non_text_omission_reference", "path": index_path, "index": index}
        if _is_effective_action(fact):
            return {"code": "non_text_omission_reference", "path": index_path, "index": index}
        protected = fact.get("protectedTexts") or fact.get("preserveVerbatim")
        if fact.get("priority") != "should" or protected:
            return {
                "code": "omission_authorization_revoked", "path": path,
                "reason": "must_or_protected_fact", "referencePath": index_path, "index": index,
            }
    return None


def _collect_omission_references(
    rows: Any, facts: list[Any], issues: list[dict[str, Any]], recoveries: list[dict[str, Any]],
) -> dict[int, list[str]]:
    references: dict[int, list[str]] = {}
    if not isinstance(rows, list):
        issues.append({"code": "array_required", "path": "omittedContents"})
        return references
    for row_index, row in enumerate(rows):
        row_path = f"omittedContents[{row_index}]"
        if not isinstance(row, dict):
            issues.append({"code": "object_required", "path": row_path})
            continue
        indexes = row.get("factIndexes")
        if not isinstance(indexes, list):
            issues.append({"code": "array_required", "path": f"{row_path}.factIndexes"})
            continue
        for position, index in enumerate(indexes):
            if type(index) is int and 0 <= index < len(facts):
                references.setdefault(index, []).append(f"{row_path}.factIndexes[{position}]")
        resolution = _omission_resolution(indexes, facts, row_path)
        if resolution is None:
            continue
        if resolution.get("code") == "omission_authorization_revoked":
            recoveries.append(resolution)
        else:
            issues.append(resolution)
    return references


def _fact_entry(
    index: int, fact: Any, groups: dict[int, list[str]], omissions: dict[int, list[str]],
    issues: list[dict[str, Any]], recoveries: list[dict[str, Any]],
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
    if _is_effective_action(fact):
        entry["effectiveKind"] = "action"
        if isinstance(fact.get("text"), str):
            recoveries.append({"code": "action_preferred_over_text", "path": path})
        if group_refs:
            recoveries.append({
                "code": "action_removed_from_groups", "path": path,
                "groupReferences": group_refs,
            })
    elif "text" in fact and len(group_refs) != 1:
        code = "ungrouped_text" if not group_refs else "multiply_grouped_text"
        issues.append({"code": code, "path": path, "groupReferences": group_refs})
    return entry


def _omission_entries(rows: Any, recoveries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    if not isinstance(rows, list):
        return entries
    revoked_paths = set()
    for recovery in recoveries:
        if recovery.get("code") == "omission_authorization_revoked":
            revoked_paths.add(recovery.get("path"))
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        references = row.get("factIndexes")
        path = f"omittedContents[{index}]"
        meaning = "unselected_input" if references == [] else "optional_fact_request"
        if path in revoked_paths:
            meaning = "deletion_authorization_revoked"
        entries.append({
            "path": path, "description": _preview(row.get("description")),
            "factIndexes": _text_array_preview(references),
            "meaning": meaning,
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


def _required_group_repairs(
    facts: list[Any], groups: dict[int, list[str]],
) -> list[dict[str, Any]]:
    """将已有关系诊断聚焦到受影响事实，不替模型选择其所有者。"""
    repairs = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict) or _is_effective_action(fact):
            continue
        text = fact.get("text")
        if not isinstance(text, str):
            continue
        references = groups.get(index, [])
        if len(references) == 1:
            continue
        operation = "assign_one_group" if not references else "resolve_group_conflict"
        repairs.append({
            "index": index, "text": _preview(text), "priority": _preview(fact.get("priority")),
            "currentReferences": references, "operation": operation,
            "instruction": (
                "为本条事实明确且仅保留一个正确归属；保留在info_required的候选should也需归组。"
                "公共标题应引用独立且有来源的标题事实，不能借用对象的数值或时长索引。"
                "不要删除必选事实或仅改omittedContents来消除归组错误；不要猜造新内容。"
            ),
        })
    return repairs


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
    recoveries: list[dict[str, Any]] = []
    groups = _collect_group_references(arguments.get("contentGroups"), facts, issues)
    omissions = arguments.get("omittedContents", [])
    omission_refs = _collect_omission_references(omissions, facts, issues, recoveries)
    ledger = []
    for index, fact in enumerate(facts):
        ledger.append(_fact_entry(index, fact, groups, omission_refs, issues, recoveries))
    if not issues and not recoveries:
        return None
    status = "inconsistent_submitted_references" if issues else "submitted_references_recovered"
    return {
        "status": status, "factCount": len(facts),
        "requiredGroupRepairs": _required_group_repairs(facts, groups),
        "facts": ledger, "groupDeclarations": _group_entries(arguments.get("contentGroups")),
        "omissionDeclarations": _omission_entries(omissions, recoveries),
        "issues": issues, "recoveries": recoveries, "instruction": _REPAIR_INSTRUCTION,
    }
