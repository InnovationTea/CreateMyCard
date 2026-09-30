# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：context。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow, DataRow


@dataclass(frozen=True)
class ComponentGraph:
    """本轮有序记录及只读使用的兼容视图，不丢弃重复引用。"""

    records: tuple[ComponentRow, ...]
    by_id: dict[str, ComponentRow]
    first_parent: dict[str, ComponentRow]
    last_parent: dict[str, ComponentRow]
    all_parents: dict[str, list[ComponentRow]]
    last_parent_ids: dict[str, str]

    @classmethod
    def build(cls, components: list[ComponentRow]) -> ComponentGraph:
        by_id: dict[str, ComponentRow] = {}
        first: dict[str, ComponentRow] = {}
        last: dict[str, ComponentRow] = {}
        all_parents: dict[str, list[ComponentRow]] = {}
        last_ids: dict[str, str] = {}
        for component in components:
            by_id[component.component_id] = component
            for child_id in component.children:
                first.setdefault(child_id, component)
                last[child_id] = component
                all_parents.setdefault(child_id, []).append(component)
                last_ids[child_id] = component.component_id
        return cls(tuple(components), by_id, first, last, all_parents, last_ids)


class ComponentRows(list[ComponentRow]):
    """兼容现有列表入参；规则只读，本轮首次查询时建立索引。"""

    @cached_property
    def graph(self) -> ComponentGraph:
        return ComponentGraph.build(self)


def component_graph(components: list[ComponentRow]) -> ComponentGraph:
    if isinstance(components, ComponentRows):
        return components.graph
    return ComponentGraph.build(components)


def component_index(components: list[ComponentRow]) -> dict[str, ComponentRow]:
    return component_graph(components).by_id


@dataclass
class ValidationContext:
    """组织本轮现有输入；数据模型和绑定按原执行位置补齐。"""

    original_source: str
    validation_source: str
    components: ComponentRows
    data_rows: list[DataRow]
    task_spec: dict[str, Any]
    card_spec: dict[str, Any]
    binding_paths: list[str] = field(default_factory=list)
    visible_binding_paths: list[str] = field(default_factory=list)
    data_model: dict[str, Any] | None = None


@dataclass(frozen=True)
class HeroTextAnalysis:
    numeric_paths: dict[str, str | None]
    formatted_ids: set[str]


def _has_parent_column(
    component: ComponentRow,
    components: list[ComponentRow],
    width: float,
) -> bool:
    child_to_parents = component_graph(components).all_parents
    pending = [component.component_id]
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        for parent in child_to_parents.get(child_id, []):
            if (
                parent.component_type == "Column"
                and parent.props.get("width") == width
                and parent.props.get("padding", 0) == 0
            ):
                return True
            pending.append(parent.component_id)
    return False


def _descendant_on_click_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> int:
    count = 0
    pending = list(component.children)
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        child = components_by_id.get(child_id)
        if child is None:
            continue
        if "onClick" in child.props:
            count += 1
        pending.extend(child.children)
    return count


def _descendant_type_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    component_type: str,
) -> int:
    count = 0
    pending = list(component.children)
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        child = components_by_id.get(child_id)
        if child is None:
            continue
        if child.component_type == component_type:
            count += 1
        pending.extend(child.children)
    return count


def _descendant_components(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
) -> list[ComponentRow]:
    descendants: list[ComponentRow] = []
    pending = list(component.children)
    visited: set[str] = set()
    while pending:
        child_id = pending.pop()
        if child_id in visited:
            continue
        visited.add(child_id)
        child = components_by_id.get(child_id)
        if child is None:
            continue
        descendants.append(child)
        pending.extend(child.children)
    return descendants


def _first_text_component(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    visiting: set[str],
) -> ComponentRow | None:
    if component.component_type == "Text":
        return component
    if component.component_id in visiting:
        return None
    visiting.add(component.component_id)
    for child_id in component.children:
        child = components_by_id.get(child_id)
        if child is None:
            continue
        result = _first_text_component(child, components_by_id, visiting)
        if result is not None:
            visiting.remove(component.component_id)
            return result
    visiting.remove(component.component_id)
    return None


def _has_ancestor_component_type(
    component_id: str,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
    component_type: str,
) -> bool:
    current = parent_by_child.get(component_id)
    visited: set[str] = set()
    while current is not None and current not in visited:
        visited.add(current)
        parent = components_by_id.get(current)
        if parent is None:
            return False
        if parent.component_type == component_type:
            return True
        current = parent_by_child.get(current)
    return False
