"""Model-authored display requirements shared by planning and repair.

This verifies explicit references and evidence, not arbitrary natural-language
entailment. Passing it must not be reported as a semantic completeness proof.
"""

from __future__ import annotations

import copy
import math
import re
from typing import Any

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.catalog.bindings import (
        CompileContext, explicit_clock_values, _literal_is_explicit_in_query, _literal_matches_binding_storage_type,
    )
    from ..jsx_to_a2ui.exceptions import ValidationError
else:
    from jsx_to_a2ui.catalog.bindings import (
        CompileContext, explicit_clock_values, _literal_is_explicit_in_query, _literal_matches_binding_storage_type,
    )
    from jsx_to_a2ui.exceptions import ValidationError


def required_facts_schema(context: CompileContext | None = None) -> dict[str, Any]:
    schema = {
        "type": "array",
        "minItems": 1,
        "description": (
            "逐对象、逐属性列出必需事实，每项选择 dataId、actionId、text 中恰好一种。"
            "sourceQuote 必须摘自 userQuery；不得把背景自动当成另一对象的事实。"
            "动态事实使用真实 dataId，不用 text 静态化。用户明确覆盖样例时，"
            "在该 dataId 项填写 initialValue 和包含该值的 valueSourceQuote。"
        ),
        "items": {
            "type": "object",
            "properties": {
                "requirement": {"type": "string"},
                "sourceQuote": {"type": "string"},
                "dataId": {"type": "string", "description": "动态信息选此字段，值为输入 data 的真实 ID。不要同时填写 text/actionId。"},
                "actionId": {"type": "string", "description": "操作选此字段，值为输入 actions 的真实 ID。不要同时填写 text/dataId。"},
                "text": {"type": "string", "description": "仅用户原文明确出现的静态正文；禁止填写样例值、字段说明或设计说明。动态信息必须选 dataId。"},
                "initialValue": {"type": ["string", "number"], "description": "仅用户明确覆盖该 ID 的样例时填写；否则省略，不要填空占位。"},
                "valueSourceQuote": {"type": "string", "description": "只与 initialValue 一起填写，引用用户明确给出该值的原文；不用时省略。"},
            },
            "required": ["requirement"],
            "additionalProperties": False,
        },
    }
    if context is not None:
        props = schema["items"]["properties"]
        for key, values in (("dataId", context.data), ("actionId", context.actions)):
            if values:
                props[key]["enum"] = list(values)
    return schema


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def unavailable_data_ids(context: CompileContext) -> set[str]:
    """Empty input is not a fact that a JSX repair can manufacture."""
    return {key for key, binding in context.data.items()
            if binding.value is None or isinstance(binding.value, str) and not binding.value.strip()}


def input_availability_warnings(context: CompileContext) -> list[dict[str, Any]]:
    unavailable = unavailable_data_ids(context)
    warnings = [{'severity': 'warning', 'code': 'input-value-unavailable', 'dataId': key,
                 'message': 'Input value is empty; retain user-requested display bindings for future updates. Do not invent a value or retry JSX to supply it. Action-only parameters do not require a display binding.'}
                for key in sorted(unavailable)]

    def paths(value):
        if isinstance(value, str):
            yield from re.findall(r'\$\{\s*([^{}]+?)\s*\}', value)
        elif isinstance(value, dict):
            if isinstance(value.get('path'), str):
                yield value['path']
            for item in value.values():
                yield from paths(item)
        elif isinstance(value, list):
            for item in value:
                yield from paths(item)

    for action in context.actions.values():
        dependencies = set(paths(action.handler.get('args', {})))
        for key in sorted(unavailable):
            if context.data[key].path in dependencies:
                warnings.append({'severity': 'warning', 'code': 'action-input-unavailable',
                                 'dataId': key, 'actionId': action.id,
                                 'message': 'Action references an empty input value; button presence does not prove that navigation is usable. Fix the input, not the JSX layout.'})
    return warnings


def validate_data_inventory(
    facts: list[dict[str, Any]], exclusions: Any, context: CompileContext,
    prompt_task: dict[str, Any] | None, warnings: list[dict[str, Any]],
) -> dict[str, str]:
    """Check explicit field accounting, never infer requirements from prose.

    Unaccounted inputs are advisory: they do not prove missing display facts.
    Only explicit invalid references or contradictory declarations are errors.
    """
    if exclusions is None:
        exclusions = {}
    if not isinstance(exclusions, dict):
        raise ValidationError("data_exclusions must map real data IDs to non-empty reasons")
    selected = {item['dataId'] for item in facts if 'dataId' in item}
    errors = []
    for key, reason in exclusions.items():
        if key not in context.data:
            errors.append(f"data_exclusions contains unknown data ID {key!r}")
        elif key in selected:
            errors.append(f"data ID {key!r} cannot be both required and excluded")
        elif not _nonempty(reason):
            errors.append(f"data_exclusions[{key!r}] requires a non-empty reason")
        else:
            warnings.append({'severity': 'warning', 'code': 'plan-data-excluded',
                             'dataId': key, 'message': reason})
    unavailable = unavailable_data_ids(context)
    warnings.extend(input_availability_warnings(context))
    # The task's supplied field table is the inventory, not a larger shared
    # compiler context (which may legitimately contain unrelated fields).
    supplied = {item['id'] for item in (prompt_task or {}).get('data', [])
                if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id'] in context.data}
    missing = sorted(supplied - selected - set(exclusions) - unavailable)
    if missing:
        warnings.append({
            'severity': 'warning', 'phase': 'plan_contract', 'code': 'plan-data-unaccounted',
            'dataIds': missing,
            'message': 'Input data IDs are not mapped in the plan: ' + repr(missing)
                       + '. Coverage is unverified, not proven missing. Use real dataId bindings for requested display facts; do not display internal IDs or background fields merely to clear this warning. No plan retry is required for this warning.',
        })
    if errors:
        raise ValidationError('; '.join(errors))
    return dict(exclusions)


def is_verbatim_requirement(text: str, query: str) -> bool:
    """Only explicitly quoted display copy is an exact-text contract.

    Descriptions, field labels and time paraphrases remain advisory. This is
    deliberately not a natural-language completeness classifier.
    """
    for match in re.finditer(r'[“「"]([^”」"]+)[”」"]', query):
        if match.group(1) != text:
            continue
        clause = re.split(r"[。！？;；\n]", query[:match.start()])[-1]
        if re.search(r"不要|不需|别|不展示|不显示|do not|don't", clause, re.I):
            continue
        suffix = query[match.end():]
        if re.match(r"\s*的(?:状态|数量|完成|进度|标题|长度)", suffix):
            continue  # Quoted object name is not necessarily requested copy.
        if re.search(r"(?:展示|显示|写上|display|show|write)\s*(?:待办事项|待办|正文|文案|文字|文本|内容|text|copy)?\s*[:：]?\s*$", clause, re.I):
            return True
    return False


def validate_required_facts(
    facts: Any, query: str, context: CompileContext,
    *, warnings: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(facts, list) or not facts:
        raise ValidationError("info_required must be a non-empty array of atomic facts")
    errors: list[str] = []
    normalized: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    allowed = set(required_facts_schema()["items"]["properties"])

    def warn(code: str, message: str, **details: str) -> None:
        if warnings is not None:
            warnings.append({"severity": "warning", "phase": "plan_contract",
                             "code": code, "message": message, **details})

    for index, raw in enumerate(facts):
        where = f"info_required[{index}]"
        if not isinstance(raw, dict):
            # Preserve prose as a requirement, not as mandatory literal copy.
            if _nonempty(raw):
                raw = {"requirement": raw}
            else:
                errors.append(f"{where} must be a fact object")
                continue
        fact = copy.deepcopy(raw)
        for key in set(fact) - allowed:
            fact.pop(key)
            warn("plan-metadata-normalized", f"{where}.{key} is unsupported metadata and was ignored")
        for key in ("dataId", "actionId", "text", "valueSourceQuote"):
            if fact.get(key) in (None, ""):
                fact.pop(key, None)
        if not _nonempty(fact.get("requirement")):
            fact["requirement"] = str(fact.get("text") or fact.get("dataId") or fact.get("actionId") or where)
            warn("plan-metadata-normalized", f"{where}.requirement was derived from its target")
        quote = fact.get("sourceQuote")
        if not _nonempty(quote) or quote not in query:
            warn("plan-evidence-unverified", f"{where}.sourceQuote is not a verbatim quote; it is not evidence of coverage")
        targets = [key for key in ("dataId", "actionId", "text") if key in fact]
        invalid_targets = [key for key in targets if not _nonempty(fact[key])]
        if invalid_targets:
            errors.append(f"{where} has non-string targets {invalid_targets!r}")
            continue
        if not targets:
            if "initialValue" in fact:
                warn("plan-initial-value-unverified", f"{where}.initialValue has no dataId; no override applied")
                fact.pop("initialValue")
            fact.pop("valueSourceQuote", None)
            warn("plan-requirement-unverified", f"{where} has no mapped target; retain the requirement for generation and semantic review")
            normalized.append(fact)
            continue
        if len(targets) > 1:
            warn("plan-metadata-normalized", f"{where} was split into independent targets without deleting requirements")
        for target in targets:
            item = {key: value for key, value in fact.items()
                    if key not in {"dataId", "actionId", "text", "initialValue", "valueSourceQuote"}}
            item[target] = fact[target]
            try:
                binding = context.data_binding(item[target]) if target == "dataId" else None
                if target == "actionId":
                    context.action_binding(item[target])
                if target == "text" and not is_verbatim_requirement(item["text"], query):
                    warn("plan-text-advisory", f"{where}.text={item['text']!r} is descriptive or paraphrasable; exact wording will not block JSX")
                if target == "dataId" and "initialValue" in fact:
                    value = fact["initialValue"]
                    evidence = fact.get("valueSourceQuote")
                    if not _literal_matches_binding_storage_type(value, binding):
                        raise ValidationError(f"{where}.initialValue does not match the binding storage type")
                    if binding.data_type == "integer" and type(value) is not int:
                        raise ValidationError(f"{where}.initialValue must be an integer")
                    if isinstance(value, float) and not math.isfinite(value):
                        raise ValidationError(f"{where}.initialValue must be finite")
                    if type(value) is type(binding.value) and value == binding.value and not evidence:
                        pass  # Explicitly repeating the sample is a no-op.
                    elif (_nonempty(evidence) and evidence in query
                          and _literal_is_explicit_in_query(value, evidence)
                          and not (isinstance(value, str) and re.fullmatch(r"\d{2}:\d{2}", value)
                                   and len(explicit_clock_values(evidence)) > 1)):
                        item.update(initialValue=value, valueSourceQuote=evidence)
                    else:
                        warn("plan-initial-value-unverified",
                             f"{where}: proposed initialValue={value!r}, evidence={evidence!r} cannot be verified; no override applied",
                             dataId=item[target])
                elif "initialValue" in fact and "dataId" not in targets:
                    warn("plan-initial-value-unverified", f"{where}.initialValue has no dataId; no override applied")
                elif "valueSourceQuote" in fact and "initialValue" not in fact:
                    warn("plan-unused-value-source-quote", f"{where}.valueSourceQuote ignored because initialValue was not supplied; binding retained")
                identity = (target, item[target])
                previous = seen.get(identity)
                if previous is not None:
                    if ("initialValue" in previous and "initialValue" in item
                            and (type(previous["initialValue"]) is not type(item["initialValue"])
                                 or previous["initialValue"] != item["initialValue"])):
                        raise ValidationError(f"{where} has conflicting initial values for {item[target]!r}")
                    if "initialValue" in item:
                        previous.update(initialValue=item["initialValue"], valueSourceQuote=item["valueSourceQuote"])
                    if item["requirement"] not in previous["requirement"]:
                        previous["requirement"] += "; " + item["requirement"]
                    warn("plan-metadata-normalized", f"{where} duplicates {target} {item[target]!r}; merged")
                else:
                    seen[identity] = item
                    normalized.append(item)
            except ValidationError as exc:
                errors.append(str(exc))
    if errors:
        raise ValidationError("; ".join(dict.fromkeys(errors)))
    return normalized


def checkable_facts(facts: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Targets we can compare with JSX, not proof of user-required coverage."""
    return [fact for fact in facts if "dataId" in fact or "actionId" in fact
            or ("text" in fact and is_verbatim_requirement(fact["text"], query))]


def context_with_initial_values(
    facts: list[dict[str, Any]], payload: Any,
) -> dict[str, Any]:
    context = CompileContext.from_payload(payload)
    for fact in facts:
        if "initialValue" in fact:
            context.override_data_binding_value(fact["dataId"], fact["initialValue"])
    return context.payload()


def missing_required_facts(
    facts: list[dict[str, Any]], used_data: set[str], used_actions: set[str],
    visible_literals: list[Any],
) -> list[dict[str, Any]]:
    texts = [re.sub(r"\s+", "", str(value)) for value in visible_literals
             if isinstance(value, (str, int, float)) and not isinstance(value, bool)]
    missing = []
    for fact in facts:
        if "dataId" in fact:
            present = fact["dataId"] in used_data
        elif "actionId" in fact:
            present = fact["actionId"] in used_actions
        else:
            value = re.sub(r"\s+", "", fact["text"])
            pattern = (r"(?<![\d.])" if value[0].isdigit() else "") + re.escape(value)
            if value[-1].isdigit():
                pattern += r"(?![\d.])"
            present = any(re.search(pattern, text) for text in texts)
        if not present:
            missing.append(fact)
    return missing
