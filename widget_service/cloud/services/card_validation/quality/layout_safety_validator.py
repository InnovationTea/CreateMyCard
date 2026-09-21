# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""检查 Stack 文字前景的安全分区，不模拟端侧字形测量。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..base import BaseValidator
from .common import children_of, component_pointer

_ALIGNMENTS = {
    "topStart": (0.0, 0.0),
    "top": (0.5, 0.0),
    "topEnd": (1.0, 0.0),
    "start": (0.0, 0.5),
    "center": (0.5, 0.5),
    "end": (1.0, 0.5),
    "bottomStart": (0.0, 1.0),
    "bottom": (0.5, 1.0),
    "bottomEnd": (1.0, 1.0),
}
_HIDDEN = {"hidden", "none"}


@dataclass(frozen=True)
class _Slot:
    component_id: str
    horizontal: tuple[float, float] | None
    vertical: tuple[float, float] | None


def _styles(component: dict[str, Any]) -> dict[str, Any]:
    value = component.get("styles")
    return value if isinstance(value, dict) else {}


def _finite_number(value: Any) -> float | None:
    result: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            candidate = float(value)
        except OverflowError:
            return result
        if math.isfinite(candidate):
            result = candidate
    return result


def _visible(component: dict[str, Any]) -> bool:
    visibility = _styles(component).get("visibility")
    return not isinstance(visibility, str) or visibility not in _HIDDEN


def _has_label(component: dict[str, Any]) -> bool:
    kind = component.get("component")
    if not isinstance(kind, str) or kind not in {"Text", "Button"}:
        return False
    key = "content" if kind == "Text" else "label"
    value = component.get(key)
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, dict) and bool(value)


def _children(component: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    children = children_of(component, by_id)
    template = component.get("children")
    if isinstance(template, dict):
        template_id = template.get("componentId")
        if isinstance(template_id, str):
            child = by_id.get(template_id)
            if isinstance(child, dict):
                children.append(child)
    return children


def _contains_label(component: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    pending = [component]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        current_id = current.get("id")
        if not isinstance(current_id, str) or current_id in visited:
            continue
        visited.add(current_id)
        if not _visible(current):
            continue
        if _has_label(current):
            return True
        pending.extend(_children(current, by_id))
    return False


def _margin(styles: dict[str, Any], edge: str) -> float | None:
    value = styles.get("margin", 0.0)
    if isinstance(value, dict):
        value = value.get(edge, 0.0)
    return _finite_number(value)


def _axis_interval(
    styles: dict[str, Any], dimension: str, edges: tuple[str, str], anchor: float
) -> tuple[float, float] | None:
    interval: tuple[float, float] | None = None
    size = _finite_number(styles.get(dimension))
    before = _margin(styles, edges[0])
    after = _margin(styles, edges[1])
    if size is None or before is None or after is None:
        return interval
    if size <= 0.0 or before < 0.0 or after < 0.0:
        return interval
    # 兄弟共享父级锚点，因此相对锚点计算即可，无需猜测父容器的自适应尺寸。
    start = before - anchor * (size + before + after)
    end = start + size
    if math.isfinite(start) and math.isfinite(end):
        interval = (start, end)
    return interval


def _slot(component: dict[str, Any], alignment: Any) -> _Slot:
    component_id = component.get("id")
    if not isinstance(component_id, str):
        raise ValueError("文字分支必须具有字符串 id")
    horizontal: tuple[float, float] | None = None
    vertical: tuple[float, float] | None = None
    anchors = _ALIGNMENTS.get(alignment) if isinstance(alignment, str) else None
    if anchors is not None:
        styles = _styles(component)
        horizontal = _axis_interval(styles, "width", ("left", "right"), anchors[0])
        vertical = _axis_interval(styles, "height", ("top", "bottom"), anchors[1])
    return _Slot(component_id, horizontal, vertical)


def _separated(left: tuple[float, float] | None, right: tuple[float, float] | None) -> bool:
    if left is None or right is None:
        return False
    return left[1] <= right[0] or right[1] <= left[0]


class LayoutSafetyValidator(BaseValidator):
    stage = "quality"
    name = "layout_safety"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        by_id = context.components_by_id
        root = by_id.get(context.root_id)
        if not isinstance(root, dict):
            return
        indexes: dict[str, int] = {}
        for index, component in enumerate(context.components):
            component_id = component.get("id")
            if isinstance(component_id, str):
                indexes[component_id] = index
        pending = [root]
        visited: set[str] = set()
        while pending:
            component = pending.pop()
            component_id = component.get("id")
            if not isinstance(component_id, str) or component_id in visited:
                continue
            visited.add(component_id)
            if not _visible(component):
                continue
            children = _children(component, by_id)
            pending.extend(reversed(children))
            if component.get("component") != "Stack":
                continue
            index = indexes.get(component_id)
            if index is not None:
                self._check_stack(component, children, by_id, index, reporter)

    @staticmethod
    def _check_stack(
        component: dict[str, Any],
        children: list[dict[str, Any]],
        by_id: dict[str, dict[str, Any]],
        index: int,
        reporter: Any,
    ) -> None:
        alignment = _styles(component).get("alignContent", "center")
        slots: list[_Slot] = []
        seen: set[str] = set()
        for child in children:
            child_id = child.get("id")
            if not isinstance(child_id, str) or child_id in seen:
                continue
            seen.add(child_id)
            if _contains_label(child, by_id):
                slots.append(_slot(child, alignment))
        conflicts: list[list[str]] = []
        for left_index, left in enumerate(slots):
            for right_index in range(left_index + 1, len(slots)):
                right = slots[right_index]
                if _separated(left.horizontal, right.horizontal):
                    continue
                if _separated(left.vertical, right.vertical):
                    continue
                conflicts.append([left.component_id, right.component_id])
        if not conflicts:
            return
        reporter.add(
            "error",
            "LAYOUT.STACK_CONTENT_FLOW",
            "quality",
            "genui",
            line=2,
            json_pointer=component_pointer(index, "children"),
            actual={"stack": component.get("id"), "conflictingBranches": conflicts},
            expected="单一文字前景容器，或可证明互不相交的文字分支槽位",
            message="Stack 内多个文字前景分支缺少可验证的安全分区，存在内容重叠风险。",
            fix_hint=(
                f"Stack {component.get('id')} 的文字分支 {conflicts} 需要重新分区："
                "纵向内容合并到 Column，横向内容合并到 Row；背景可继续放在 Stack。"
                "layoutWeight 和子容器 justifyContent 不会将 Stack 兄弟按顺序排开。"
                "保留文字内容和可读字号，不通过裁剪或隐藏内容消除问题。"
            ),
            source="layout-safety",
        )
