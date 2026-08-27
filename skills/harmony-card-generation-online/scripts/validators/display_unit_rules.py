from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .base import expression_body

_STRING_LITERAL_RE = re.compile(r"^'(?P<value>(?:[^'\\]|\\.)*)'$")
_ARRAY_INDEX_RE = re.compile(r"/(?P<index>\d+)(?=/|$)")
_UNIT_ALIASES = {"℃": {"℃", "°C", "°"}}


@dataclass(frozen=True)
class DisplayUnitRule:
    units: tuple[str, ...]
    unit_included: bool


def collect_bound_display_unit_rules(card_spec: Any, data_capabilities: Any):
    result: dict[str, DisplayUnitRule] = {}

    values = (
        data_capabilities.values()
        if isinstance(data_capabilities, dict)
        else data_capabilities
    ) or []
    capabilities_by_id = {}
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
                tuple(item.strip() for item in units), included
            )
            return
        if schema.get("type") == "object":
            for key, child in schema.get("properties", {}).items():
                visit(child, (*parts, str(key)))
        elif schema.get("type") == "array":
            visit(schema.get("items"), (*parts, "0"))

    bindings = card_spec.get("dataBindings") if isinstance(card_spec, dict) else None
    for binding in bindings if isinstance(bindings, list) else []:
        if not isinstance(binding, dict):
            continue
        capability = capabilities_by_id.get(binding.get("capabilityId"))
        root = binding.get("writeResultTo")
        schema = _capability_value(capability, "outputSchema")
        if (
            isinstance(root, str)
            and root.startswith("/data/")
            and isinstance(schema, dict)
        ):
            visit(schema, tuple(part for part in root.strip("/").split("/") if part))
    return result


def _capability_value(capability: Any, field: str) -> Any:
    if isinstance(capability, dict):
        return capability.get(field)
    return getattr(capability, field, None)


def unit_rule_for_path(path: str, rules: dict[str, DisplayUnitRule]):
    return rules.get(path) or rules.get(_ARRAY_INDEX_RE.sub("/0", path))


def matching_unit_literal_count(expression: Any, rule: DisplayUnitRule) -> int:
    if not isinstance(expression, str):
        return 0
    return sum(
        _literal_matches_rule(term, rule)
        for term in _split_concat_terms(expression_body(expression))
    )


def static_text_matches_rule(value: Any, rule: DisplayUnitRule) -> bool:
    return isinstance(value, str) and any(
        _normalized_unit(value) in _normalized_aliases(unit) for unit in rule.units
    )


def _split_concat_terms(body: str) -> list[str]:
    terms: list[str] = []
    start = depth = 0
    in_string = escaped = False
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
    return bool(match) and any(
        _normalized_unit(match.group("value")) in _normalized_aliases(unit)
        for unit in rule.units
    )


def _normalized_aliases(unit: str) -> set[str]:
    return {_normalized_unit(item) for item in _UNIT_ALIASES.get(unit, {unit})}


def _normalized_unit(value: str) -> str:
    return "".join(value.split()).casefold()
