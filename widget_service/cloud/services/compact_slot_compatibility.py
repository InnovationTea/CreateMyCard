"""复用现有布局与 Recipe 检查组件槽位下界；未知容量不等于可以容纳。"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Literal

from services.compact_component_runtime import load_visual_recipe_contract
from services.compact_component_semantics import (
    CORE_INFORMATION_COMPONENT_TYPES,
    MODEL_COMPONENT_TYPES_BY_SIZE,
)
from services.compact_layout_runtime import load_layout_contract

_CONTAINERS = frozenset({"Row", "Column", "Stack"})
_ACTIONS = frozenset({"PillButton", "CircleButton", "CardButton"})


@dataclass(frozen=True)
class SlotCompatibility:
    status: Literal["incompatible", "conditional", "unknown"]
    reasons: tuple[str, ...]
    minimum_height: float | None
    minimum_width: float | None
    requires_core_information: bool


def _extent(value: Any) -> float | None:
    result: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and value >= 0:
            result = float(value)
    return result


def check_component_slot(
    group: dict[str, Any], *, size: str, layout_id: str | None,
    slot_rule: dict[str, Any], width: float | None, height: float | None,
) -> SlotCompatibility:
    """只拒绝现有合同可证明不成立的角色或下界，不引入新发布门禁。"""
    from services.compact_composition_context import composition_group_minimum_height

    name = group.get("component")
    reasons: list[str] = []
    allowed = MODEL_COMPONENT_TYPES_BY_SIZE.get(size, ())
    if name not in allowed and name not in _CONTAINERS:
        reasons.append("组件未在当前尺寸登记。")
    types = slot_rule.get("types", [])
    container_slot = any(kind in _CONTAINERS for kind in types)
    if types and not container_slot and name not in types:
        reasons.append("组件类型不符合槽位角色。")
    policy = slot_rule.get("eventPolicy")
    action = name in _ACTIONS or bool(group.get("actionId"))
    if policy == "require" and not action:
        reasons.append("该槽位必须承载动作。")
    if policy == "forbid-subtree" and action:
        reasons.append("该槽位禁止动作。")
    if name in {"InfoBlock", "CardButton"} and name not in types:
        reasons.append("固定槽组件不能进入普通内容槽。")
    placement = load_layout_contract().get("componentPlacementRules", {}).get(name)
    if isinstance(placement, dict) and placement.get("size") == size:
        allowed_layouts = placement.get("allowedLayouts", [])
        if layout_id is not None and layout_id not in allowed_layouts:
            reasons.append("组件不支持当前父布局。")
    minimum_height = composition_group_minimum_height(size, group)
    planned_height = _extent(group.get("requiredHeight"))
    if minimum_height is None:
        minimum_height = planned_height
    elif planned_height is not None:
        minimum_height = max(minimum_height, planned_height)
    minimum_width = _extent(group.get("minimumWidth"))
    if minimum_height is not None and height is not None and minimum_height > height:
        reasons.append(f"组件至少需要 {minimum_height:g}vp 高，槽位仅有 {height:g}vp。")
    if minimum_width is not None and width is not None and minimum_width > width:
        reasons.append(f"组件至少需要 {minimum_width:g}vp 宽，槽位仅有 {width:g}vp。")
    requires_core = name == "SecondaryBody"
    for nested in group.get("nestedGroups", []):
        nested_result = check_component_slot(
            nested, size=size, layout_id=layout_id, slot_rule=slot_rule,
            width=width, height=height,
        )
        reasons.extend(nested_result.reasons)
        requires_core = requires_core or nested_result.requires_core_information
    status: Literal["incompatible", "conditional", "unknown"] = "unknown"
    if reasons:
        status = "incompatible"
    elif minimum_height is not None and height is not None and width is not None:
        status = "conditional"
    return SlotCompatibility(
        status, tuple(dict.fromkeys(reasons)), minimum_height, minimum_width,
        requires_core,
    )


def auxiliary_groups_have_core(groups: list[dict[str, Any]]) -> bool:
    """按整卡检查辅助组依赖，纯动作组合不要求新增核心正文。"""
    names: set[str] = set()
    pending = list(groups)
    while pending:
        group = pending.pop()
        name = group.get("component")
        if isinstance(name, str):
            names.add(name)
        pending.extend(group.get("nestedGroups", []))
    return "SecondaryBody" not in names or bool(names & CORE_INFORMATION_COMPONENT_TYPES)


def _probe_groups() -> list[dict[str, Any]]:
    """枚举组件固有下界；条数相关组件显式说明探针形态，不代表任意 Props。"""
    groups: list[dict[str, Any]] = []
    components = load_visual_recipe_contract().get("components", {})
    for name in components:
        group: dict[str, Any] = {"component": name, "placements": []}
        if name in {"TableText", "SecondaryBody"}:
            group.update(placements=["items[0].value", "items[1].value"], columns=1)
        groups.append(group)
        if name == "EmphasisText":
            groups.append({"component": name, "placements": ["mainText", "secondaryText"]})
    return groups


def component_slot_matrix(size: str) -> list[dict[str, Any]]:
    """导出各正式布局变体叶槽，参考盒与生成组合搜索共用。"""
    from services.compact_composition_planner import _leaves, _region_tree

    if size not in {"2x2", "2x4"}:
        raise ValueError("槽位矩阵只支持 2x2 或 2x4。")
    result: list[dict[str, Any]] = []
    layouts = load_layout_contract().get("layouts", {})
    probes = _probe_groups()
    for name, layout in layouts.items():
        if layout.get("size") != size:
            continue
        for variant, pattern in enumerate(layout.get("patterns", []), start=1):
            rules = pattern.get("rules", [])
            tree = _region_tree(size, rules)
            slots: list[dict[str, Any]] = []
            if tree is not None:
                for slot in _leaves(tree):
                    slots.append({"path": list(slot.path), "rule": slot.rule,
                                  "width": slot.width, "height": slot.height})
            else:
                # 有限参考求解不覆盖全部变体；仅保留显式尺寸，其余标记未知。
                for rule in rules:
                    path = rule.get("path", [])
                    has_descendant = False
                    for candidate in rules:
                        other = candidate.get("path", [])
                        if len(other) > len(path) and other[:len(path)] == path:
                            has_descendant = True
                            break
                    if has_descendant:
                        continue
                    props = {**rule.get("props", {}), **rule.get("slotSize", {})}
                    slots.append({"path": path, "rule": rule,
                                  "width": _extent(props.get("width")),
                                  "height": _extent(props.get("height"))})
            for slot in slots:
                rule = slot.get("rule")
                if not isinstance(rule, dict):
                    raise ValueError("槽位缺少布局规则。")
                for group in probes:
                    assessment = check_component_slot(
                        group, size=size, layout_id=name, slot_rule=rule,
                        width=slot.get("width"), height=slot.get("height"),
                    )
                    result.append({
                        "size": size, "layout": name, "variant": variant,
                        "path": slot.get("path"), "roleTypes": rule.get("types", []),
                        "width": slot.get("width"), "height": slot.get("height"), "probe": group,
                        **asdict(assessment),
                    })
    return result


if __name__ == "__main__":
    print(json.dumps({
        "说明": "conditional 只表示已知下界成立；未知文字和完整组合仍须原校验。",
        "2x2": component_slot_matrix("2x2"), "2x4": component_slot_matrix("2x4"),
    }, ensure_ascii=False, indent=2))
