# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .validation_policy import (
    STANDARD_VALIDATION_POLICY,
    CardValidationPolicy,
    resolve_validation_policy,
)


@dataclass
class ValidationContext:
    dsl_text: str = ""
    cardspec_text: str = ""
    use_effective_capabilities: bool = False
    effective_capabilities: dict[str, list[Any]] = field(default_factory=dict)
    effective_data_capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    effective_asset_sources: set[str] = field(default_factory=set)
    unresolved_effective_asset_ids: set[str] = field(default_factory=set)
    dsl_messages: list[dict[str, Any]] = field(default_factory=list)
    dsl_line_count: int = 0
    cardspec: dict[str, Any] = field(default_factory=dict)
    create_surface: dict[str, Any] = field(default_factory=dict)
    update_components: dict[str, Any] = field(default_factory=dict)
    update_data_model: dict[str, Any] = field(default_factory=dict)
    components: list[dict[str, Any]] = field(default_factory=list)
    components_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    duplicate_component_ids: set[str] = field(default_factory=set)
    root_id: str | None = None
    root_component: dict[str, Any] | None = None
    data_model: Any = field(default_factory=dict)
    expression_locations: list[tuple[str, str, Any, str | None]] = field(default_factory=list)
    template_context_by_component: dict[str, dict[str, Any]] = field(default_factory=dict)
    quality_score: int | None = None
    validation_policy: CardValidationPolicy = STANDARD_VALIDATION_POLICY

    def resolve_validation_policy(self) -> CardValidationPolicy:
        """为标准 A2UI 入口适配共享策略的结构输入。"""
        root = self.root_component
        children = root.get("children") if root is not None else None
        return resolve_validation_policy(
            root_id=self.root_id,
            root_children=children if isinstance(children, list) else None,
            component_ids=self.components_by_id,
            duplicate_component_ids=self.duplicate_component_ids,
        )

    def has_fusion_template_root(self) -> bool:
        """兼容既有查询；实际校验只消费入口选定的策略。"""
        return self.resolve_validation_policy().name == "template"

    def line_for_genui_pointer(self, pointer: str) -> int | None:
        if pointer.startswith("/createSurface"):
            return 1
        if pointer.startswith("/updateComponents"):
            return 2
        if pointer.startswith("/updateDataModel"):
            return 3
        return None
