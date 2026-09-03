"""A2UI If 虚拟节点的共享结构约束，不在云侧求值条件。"""

from __future__ import annotations

from typing import Any

IF_BRANCH_FIELDS = ("childrenIf", "childrenElse")
IF_PROPERTIES = frozenset({"condition", *IF_BRANCH_FIELDS})


def validate_runtime_if(props: dict[str, Any]) -> None:
    """校验虚拟节点字段及分支 ID；表达式语法沿用各链路的表达式校验器。"""
    extra = set(props) - IF_PROPERTIES
    if extra:
        raise ValueError(f"If does not support properties: {sorted(extra)}")
    condition = props.get("condition")
    if not isinstance(condition, str):
        raise ValueError("If.condition must be a complete {{ ... }} expression")
    stripped = condition.strip()
    has_bounds = stripped.startswith("{{") and stripped.endswith("}}")
    has_single_wrapper = stripped.count("{{") == 1 and stripped.count("}}") == 1
    if not has_bounds or not has_single_wrapper:
        raise ValueError("If.condition must be a complete {{ ... }} expression")
    if not stripped.removeprefix("{{").removesuffix("}}").strip():
        raise ValueError("If.condition must not be empty")
    for field in IF_BRANCH_FIELDS:
        values = props.get(field, [])
        if not isinstance(values, list):
            raise ValueError(f"If.{field} must be an array of component IDs")
        for child in values:
            if not isinstance(child, str) or not child.strip():
                raise ValueError(f"If.{field} requires non-empty component IDs")
            if any(marker in child for marker in ("{{", "}}", "${")):
                raise ValueError(f"If.{field} must not contain expressions")
        if len(values) != len(set(values)):
            raise ValueError(f"If.{field} contains duplicate component IDs")


def component_child_ids(component: dict[str, Any]) -> tuple[str, ...]:
    """返回两条可能分支的结构引用，不将它们视为同时显示的兄弟节点。"""
    fields = IF_BRANCH_FIELDS if component.get("component") == "If" else ("children",)
    result: list[str] = []
    for field in fields:
        children = component.get(field, [])
        if isinstance(children, dict):
            children = [children.get("componentId")]
        if not isinstance(children, list):
            continue
        for child in children:
            if isinstance(child, str) and child not in result:
                result.append(child)
    return tuple(result)


def validate_runtime_if_graph(components: list[dict[str, Any]]) -> None:
    """检查包含 If 的路径是否悬空或成环；允许两条互斥分支共享组件。"""
    by_id: dict[str, dict[str, Any]] = {}
    roots: list[str] = []
    for component in components:
        component_id = component.get("id")
        if not isinstance(component_id, str):
            continue
        by_id[component_id] = component
        if component.get("component") != "If":
            continue
        if component_id == "root":
            raise ValueError("If cannot replace the card root shell")
        roots.append(component_id)
    visited: set[str] = set()
    visiting: set[str] = set()
    for root_id in roots:
        stack = [(root_id, False)]
        while stack:
            current_id, closing = stack.pop()
            if closing:
                visiting.remove(current_id)
                visited.add(current_id)
                continue
            if current_id in visited:
                continue
            if current_id in visiting:
                raise ValueError(f"If branch contains a component cycle: {current_id}")
            current = by_id.get(current_id)
            if current is None:
                raise ValueError(f"If branch references missing component: {current_id}")
            visiting.add(current_id)
            stack.append((current_id, True))
            for child_id in component_child_ids(current):
                stack.append((child_id, False))
