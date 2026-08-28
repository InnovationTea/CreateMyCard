# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""基于最终 CardSpec 与微服务能力定义检查并修复 Text 展示单位。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .base import expression_body, expression_references

_STRING_LITERAL_RE = re.compile(r"^'(?P<value>(?:[^'\\]|\\.)*)'$")
_ARRAY_INDEX_RE = re.compile(r"/(?P<index>\d+)(?=/|$)")
_UNIT_ALIASES = {
    "℃": {"℃", "°C", "°"},
}


@dataclass(frozen=True)
class DisplayUnitRule:
    units: tuple[str, ...]
    unit_included: bool


def collect_bound_display_unit_rules(
    card_spec: Any,
    data_capabilities: Any,
) -> dict[str, DisplayUnitRule]:
    """按最终数据绑定将能力 outputSchema 的单位规则映射为绝对路径。"""
    result: dict[str, DisplayUnitRule] = {}

    capabilities_by_id = {}
    values = (
        data_capabilities.values()
        if isinstance(data_capabilities, dict)
        else data_capabilities
    )
    if values is None:
        values = []
    for capability in values:
        capability_id = _capability_value(capability, "id")
        if isinstance(capability_id, str):
            capabilities_by_id[capability_id] = capability

    def visit(schema: Any, parts: tuple[str, ...]) -> None:
        if not isinstance(schema, dict):
            return
        units = schema.get("displayUnits")
        included = schema.get("unitIncluded")
        if (
            isinstance(units, list)
            and units
            and all(isinstance(item, str) and item.strip() for item in units)
            and isinstance(included, bool)
        ):
            result["/" + "/".join(parts)] = DisplayUnitRule(
                units=tuple(item.strip() for item in units),
                unit_included=included,
            )
            return
        schema_type = schema.get("type")
        if schema_type == "object":
            for key, child in schema.get("properties", {}).items():
                visit(child, (*parts, str(key)))
        elif schema_type == "array":
            visit(schema.get("items"), (*parts, "0"))

    bindings = card_spec.get("dataBindings") if isinstance(card_spec, dict) else None
    if not isinstance(bindings, list):
        return result
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        capability = capabilities_by_id.get(binding.get("capabilityId"))
        write_result_to = binding.get("writeResultTo")
        output_schema = _capability_value(capability, "outputSchema")
        if (
            not isinstance(write_result_to, str)
            or not write_result_to.startswith("/data/")
            or not isinstance(output_schema, dict)
        ):
            continue
        root_parts = tuple(part for part in write_result_to.strip("/").split("/") if part)
        visit(output_schema, root_parts)
    return result


def _capability_value(capability: Any, field: str) -> Any:
    if isinstance(capability, dict):
        return capability.get(field)
    return getattr(capability, field, None)


def unit_rule_for_path(
    path: str,
    rules: dict[str, DisplayUnitRule],
) -> DisplayUnitRule | None:
    rule = rules.get(path)
    if rule is not None:
        return rule
    canonical_path = _ARRAY_INDEX_RE.sub("/0", path)
    return rules.get(canonical_path)


def matching_unit_literal_count(expression: Any, rule: DisplayUnitRule) -> int:
    if not isinstance(expression, str):
        return 0
    return sum(
        1
        for term in _split_concat_terms(expression_body(expression))
        if _literal_matches_rule(term, rule)
    )


def static_text_matches_rule(value: Any, rule: DisplayUnitRule) -> bool:
    return isinstance(value, str) and any(
        _normalized_unit(value) in _normalized_aliases(unit) for unit in rule.units
    )


def repair_repeated_display_units(
    dsl_text: str,
    card_spec: dict[str, Any],
    data_capabilities: Any,
) -> str:
    """确定性移除 Text 表达式或相邻单位节点中的重复单位。"""
    rules = collect_bound_display_unit_rules(card_spec, data_capabilities)
    if not rules:
        return dsl_text
    lines = [line.strip() for line in dsl_text.splitlines() if line.strip()]
    if len(lines) != 3:
        return dsl_text
    try:
        messages = [json.loads(line) for line in lines]
    except json.JSONDecodeError:
        return dsl_text
    components = messages[1].get("updateComponents", {}).get("components")
    if not isinstance(components, list):
        return dsl_text

    by_id = {
        component.get("id"): component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    text_rules: dict[str, DisplayUnitRule] = {}
    for component_id, component in by_id.items():
        if component.get("component") != "Text":
            continue
        content = component.get("content")
        refs = expression_references(content) if isinstance(content, str) else []
        matched = [unit_rule_for_path(ref, rules) for ref in refs]
        matched = [rule for rule in matched if rule is not None]
        if len(matched) != 1:
            continue
        rule = matched[0]
        text_rules[component_id] = rule
        component["content"] = _repair_expression_units(content, rule)

    removed_child_ids: set[str] = set()
    for parent in by_id.values():
        children = parent.get("children")
        if not isinstance(children, list):
            continue
        repaired_children = list(children)
        for component_id in children:
            rule = text_rules.get(component_id)
            if rule is None:
                continue
            value_index = repaired_children.index(component_id)
            matching_siblings = []
            for sibling_id in repaired_children[value_index + 1 :]:
                if not static_text_matches_rule(
                    by_id.get(sibling_id, {}).get("content"),
                    rule,
                ):
                    break
                matching_siblings.append(sibling_id)
            keep_count = 0 if rule.unit_included else 1
            for sibling_id in matching_siblings[keep_count:]:
                repaired_children.remove(sibling_id)
                removed_child_ids.add(sibling_id)
        parent["children"] = repaired_children

    if removed_child_ids:
        still_referenced = {
            child_id
            for component in by_id.values()
            for child_id in (
                component.get("children")
                if isinstance(component.get("children"), list)
                else []
            )
            if isinstance(child_id, str)
        }
        messages[1]["updateComponents"]["components"] = [
            component
            for component in components
            if not (
                isinstance(component, dict)
                and component.get("id") in removed_child_ids - still_referenced
            )
        ]
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for message in messages
    )


def _repair_expression_units(expression: str, rule: DisplayUnitRule) -> str:
    terms = _split_concat_terms(expression_body(expression))
    matching_indexes = [
        index for index, term in enumerate(terms) if _literal_matches_rule(term, rule)
    ]
    keep_count = 0 if rule.unit_included else 1
    if len(matching_indexes) <= keep_count:
        return expression
    remove_indexes = set(matching_indexes[keep_count:])
    repaired_terms = [term for index, term in enumerate(terms) if index not in remove_indexes]
    if not repaired_terms:
        return expression
    return "{{ " + " + ".join(repaired_terms) + " }}"


def _split_concat_terms(body: str) -> list[str]:
    terms: list[str] = []
    start = 0
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(body):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                in_string = False
            continue
        if char == "'":
            in_string = True
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == "+" and depth == 0:
            terms.append(body[start:index].strip())
            start = index + 1
    terms.append(body[start:].strip())
    return terms


def _literal_matches_rule(term: str, rule: DisplayUnitRule) -> bool:
    match = _STRING_LITERAL_RE.fullmatch(term.strip())
    if match is None:
        return False
    literal = match.group("value")
    return any(_normalized_unit(literal) in _normalized_aliases(unit) for unit in rule.units)


def _normalized_aliases(unit: str) -> set[str]:
    aliases = _UNIT_ALIASES.get(unit, {unit})
    return {_normalized_unit(item) for item in aliases}


def _normalized_unit(value: str) -> str:
    return "".join(value.split()).casefold()
