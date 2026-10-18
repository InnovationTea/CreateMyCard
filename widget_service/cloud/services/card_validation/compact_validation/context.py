# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：context。"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow, DataRow


class ComponentRows(list[ComponentRow]):
    """兼容现有列表入参；规则只读，本轮首次查询时建立索引。"""

    @cached_property
    def by_id(self) -> dict[str, ComponentRow]:
        return {component.component_id: component for component in self}


def component_index(components: list[ComponentRow]) -> dict[str, ComponentRow]:
    if isinstance(components, ComponentRows):
        return components.by_id
    return {component.component_id: component for component in components}


@dataclass
class ValidationContext:
    """组织本轮现有输入；数据模型和绑定按原执行位置补齐。"""

    original_source: str
    validation_source: str
    components: ComponentRows
    data_rows: list[DataRow]
    task_spec: dict[str, Any]
    card_spec: dict[str, Any]
    original_components: ComponentRows | None = None
    binding_paths: list[str] = field(default_factory=list)
    visible_binding_paths: list[str] = field(default_factory=list)
    data_model: dict[str, Any] | None = None
    layout_origins: dict[str, str] = field(default_factory=dict)
