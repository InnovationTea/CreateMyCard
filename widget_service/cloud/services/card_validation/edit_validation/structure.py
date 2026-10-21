"""编辑引用结构检查；不接入创建校验流水线。"""

from __future__ import annotations

from typing import Any


def _child_ids(node: dict[str, Any]) -> list[str]:
    children = node.get("children", [])
    if isinstance(children, dict):
        children = [children.get("componentId")]
    if not isinstance(children, list):
        raise ValueError("children 必须为引用数组或合法模板引用")
    for child in children:
        if not isinstance(child, str):
            raise ValueError("children 只能引用组件 ID")
    return children


def validate_edit_structure(nodes: dict[str, dict], root: str) -> set[str]:
    """每个可达节点只能挂载一次，模板引用不按数据条数展开。"""
    visiting: set[str] = set()
    reached: set[str] = set()
    pending = [(root, False)]
    while pending:
        identity, leaving = pending.pop()
        if leaving:
            visiting.remove(identity)
            continue
        if identity in visiting:
            raise ValueError(f"组件树不能形成循环引用：{identity}")
        if identity in reached:
            raise ValueError(f"组件不能重复挂载或具有多个父节点：{identity}")
        node = nodes.get(identity)
        if node is None:
            raise ValueError(f"组件树引用了不存在的目标：{identity}")
        visiting.add(identity)
        reached.add(identity)
        pending.append((identity, True))
        for child in reversed(_child_ids(node)):
            pending.append((child, False))
    return reached


def validate_edit_reachability(
    before: dict[str, dict],
    after: dict[str, dict],
    root: str,
) -> None:
    source_reached = validate_edit_structure(before, root)
    reached = validate_edit_structure(after, root)
    for identity in after:
        if identity not in before and identity not in reached:
            raise ValueError(f"新增容器不能成为孤立节点：{identity}")
        if identity in source_reached and identity not in reached:
            raise ValueError(f"原卡展示内容不能移到不可达区域：{identity}")
