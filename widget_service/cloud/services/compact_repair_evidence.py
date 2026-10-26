"""从已有失败证据生成修复摘要；不计算几何、不增加校验或省略授权。"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from services.compact_repair_context import (
    _matching_plan_facts,
    _source_component_rows,
    repair_topology_fingerprint,
)

_CORE_MARKER = "SecondaryBody is auxiliary and cannot be the only information component"
_HEIGHT_PATTERN = re.compile(
    r"component (?P<id>[^:]+): vertical layout requires at least "
    r"(?P<required>\d+(?:\.\d+)?)vp within (?P<available>\d+(?:\.\d+)?)vp"
)
_PRESENTATION_KEYS = {
    "fontColor", "backgroundColor", "linearGradient", "fillColor", "borderColor",
}


def missing_core_information(issues: list[dict[str, Any]]) -> bool:
    """只消费校验器已报告的整卡核心缺失，不重新判定组件角色。"""
    return any(_CORE_MARKER in str(issue.get("message") or "") for issue in issues)


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value >= 0


def _height_record(diagnostic: dict[str, Any]) -> dict[str, Any] | None:
    result: dict[str, Any] | None = None
    actual = diagnostic.get("actual")
    expected = diagnostic.get("expected")
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return result
    required = actual.get("minimumRequiredHeight")
    available = expected.get("maximumHeight")
    identifier = diagnostic.get("componentId")
    if not isinstance(identifier, str):
        return result
    if not _finite_number(required) or not _finite_number(available):
        return result
    result = {
        "componentId": identifier,
        "minimumRequiredHeight": float(required),
        "maximumHeight": float(available),
        "overflow": max(0.0, float(required) - float(available)),
        "occupancy": copy.deepcopy(actual.get("occupancy")),
    }
    return result


def _issue_heights(issue: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    diagnostics = issue.get("compactDiagnostics")
    if isinstance(diagnostics, list):
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                continue
            if diagnostic.get("code") != "COMPACT_LAYOUT_HEIGHT_OVERFLOW":
                continue
            record = _height_record(diagnostic)
            if record is not None:
                records.append(record)
    if records:
        return records
    message = str(issue.get("message") or "")
    match = _HEIGHT_PATTERN.search(message)
    if match is not None:
        required = float(match.group("required"))
        available = float(match.group("available"))
        if not _finite_number(required) or not _finite_number(available):
            return records
        occupancy = message.partition("Occupancy: ")[2] or None
        records.append({
            "componentId": match.group("id"),
            "minimumRequiredHeight": required,
            "maximumHeight": available,
            "overflow": max(0.0, required - available),
            "occupancy": occupancy,
        })
    return records


def _only_height_diagnostics(issue: dict[str, Any]) -> bool:
    diagnostics = issue.get("compactDiagnostics")
    if diagnostics is None:
        return True
    if not isinstance(diagnostics, list) or not diagnostics:
        return False
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            return False
        if diagnostic.get("code") != "COMPACT_LAYOUT_HEIGHT_OVERFLOW":
            return False
        if _height_record(diagnostic) is None:
            return False
    return True


def _source_members(
    identifier: str, components: dict[str, dict[str, Any]], plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    pending = [identifier]
    visited: set[str] = set()
    members: list[dict[str, Any]] = []
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        component = components.get(current)
        if component is None:
            continue
        pending.extend(reversed(component.get("children", [])))
        props = component.get("props", {})
        display_props = dict(props)
        display_props.pop("onClick", None)
        members.append({
            "componentId": current,
            "componentType": component.get("type"),
            "planFacts": _matching_plan_facts(display_props, plan),
            "hasAction": bool(props.get("onClick")),
        })
    return members


def repair_failure_evidence(
    source: str, issues: list[dict[str, Any]], plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """交接既有预算及可靠源关联；展开节点不按名称猜测来源。"""
    components = _source_component_rows(source)
    budgets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        for record in _issue_heights(issue):
            identifier = record.get("componentId")
            if identifier in seen:
                continue
            seen.add(identifier)
            known_source = identifier in components
            record["sourceComponentId"] = identifier if known_source else None
            record["sourceComponents"] = _source_members(identifier, components, plan)
            budgets.append(record)
    evidence: dict[str, Any] = {}
    if budgets:
        evidence["heightBudgets"] = budgets
        evidence["instruction"] = (
            "按 sourceComponents 与 Plan 关联重分配信息，预算仅来自本轮参考校验。"
            "sourceComponentId 为 null 时不得猜测源位置或修改内部展开节点。"
            "优先重组完整信息组；候选须再次通过完整校验，不能缩固定字号、裁切或省略未授权事实。"
        )
    if missing_core_information(issues):
        evidence["missingCoreInformation"] = True
        evidence["sourceComponents"] = _source_members("root", components, plan)
    return evidence


def _business_signature(source: str) -> str | None:
    """保守保留文案、绑定、动作和数据；仅忽略 ID、配色与布局容器属性。"""
    components = _source_component_rows(source)
    entries: list[Any] = []
    for component in components.values():
        kind = component.get("type")
        if kind in {"Layout", "Region", "Group", "Row", "Column", "Stack"}:
            props = component.get("props", {})
            if "onClick" in props:
                entries.append({"onClick": props.get("onClick")})
            continue
        retained: dict[str, Any] = {}
        for key, value in component.get("props", {}).items():
            if key not in _PRESENTATION_KEYS:
                retained[key] = value
        entries.append({"type": kind, "props": retained})
    try:
        for line in source.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, list) and len(row) == 2:
                entries.append(row)
    except json.JSONDecodeError:
        return None
    serialized = [json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries]
    return json.dumps(sorted(serialized), ensure_ascii=False)


@dataclass(frozen=True)
class RepairProgress:
    """仅比较同拓扑、同业务证据且错误类型完整可解释的相邻两轮。"""

    topology: str | None
    business: str | None
    overflows: tuple[float, ...]
    core_errors: int
    comparable: bool

    @classmethod
    def capture(cls, source: str, issues: list[dict[str, Any]]) -> RepairProgress:
        overflows: list[float] = []
        core_errors = 0
        comparable = bool(issues)
        seen: set[str] = set()
        for issue in issues:
            heights = _issue_heights(issue)
            if heights:
                comparable = comparable and _only_height_diagnostics(issue)
                for record in heights:
                    identifier = record.get("componentId")
                    if identifier not in seen:
                        seen.add(identifier)
                        overflows.append(record.get("overflow", 0.0))
            elif missing_core_information([issue]):
                core_errors += 1
            else:
                comparable = False
        return cls(
            repair_topology_fingerprint(source), _business_signature(source),
            tuple(sorted(overflows, reverse=True)), core_errors, comparable,
        )

    def compare(self, previous: RepairProgress | None) -> str:
        if previous is None or not self.comparable or not previous.comparable:
            return "unknown"
        if self.topology is None or self.business is None:
            return "unknown"
        if self.topology != previous.topology or self.business != previous.business:
            return "unknown"
        if len(self.overflows) != len(previous.overflows):
            return "unknown"
        improved = self.core_errors < previous.core_errors
        worsened = self.core_errors > previous.core_errors
        for current, earlier in zip(self.overflows, previous.overflows, strict=True):
            improved = improved or current < earlier - 1e-7
            worsened = worsened or current > earlier + 1e-7
        if improved and not worsened:
            return "improved"
        return "stalled"
