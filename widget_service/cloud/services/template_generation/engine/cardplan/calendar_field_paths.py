"""Align approved calendar reminder shorthand with the existing TaskSpec projection."""

from __future__ import annotations

import re
from typing import Any

from core.json_pointer import parse_json_pointer
from models.generation import CandidateDataBinding, TaskSpec

CALENDAR_CAPABILITY_ID = "GetCalendarEvents"
_REMINDER_PARENT = re.compile(r"/events/(?:0|[1-9][0-9]?)/remindTime")
_SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean"})


def calendar_reminder_aliases(
    task_spec: TaskSpec,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> dict[str, str]:
    """Only alias candidate parents whose first scalar exists at every approved root."""
    if task_spec.size != "2x2":
        return {}
    bindings = tuple(
        binding for binding in coverage_bindings
        if binding.capabilityId == CALENDAR_CAPABILITY_ID
    )
    aliases: dict[str, str] = {}
    for binding in bindings:
        for path in binding.candidateOutputFields:
            if path in aliases or _REMINDER_PARENT.fullmatch(path) is None:
                continue
            if all(_has_scalar_array(task_spec, item.writeResultTo, path) for item in bindings):
                aliases[path] = f"{path}/0"
    return aliases


def _has_scalar_array(task_spec: TaskSpec, data_root: str, path: str) -> bool:
    current: Any = task_spec.dataModelSchema
    for part in parse_json_pointer(f"{data_root.rstrip('/')}{path}"):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return False
            current = current[index]
        else:
            return False
    if not isinstance(current, list) or not current:
        return False
    for item in current:
        if not isinstance(item, dict):
            return False
        kind = item.get("type")
        if not isinstance(kind, str) or kind not in _SCALAR_TYPES:
            return False
    return True


def normalize_calendar_reminder_bindings(
    task_spec: TaskSpec,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> tuple[CandidateDataBinding, ...]:
    """Return local candidate copies; never mutate upstream requests or TaskSpec."""
    aliases = calendar_reminder_aliases(task_spec, coverage_bindings)
    if not aliases:
        return coverage_bindings
    normalized: list[CandidateDataBinding] = []
    for binding in coverage_bindings:
        if binding.capabilityId != CALENDAR_CAPABILITY_ID:
            normalized.append(binding)
            continue
        fields: list[str] = []
        for path in binding.candidateOutputFields:
            canonical = aliases.get(path, path)
            if canonical not in fields:
                fields.append(canonical)
        if fields == binding.candidateOutputFields:
            normalized.append(binding)
        else:
            normalized.append(binding.model_copy(update={"candidateOutputFields": fields}))
    return tuple(normalized)
