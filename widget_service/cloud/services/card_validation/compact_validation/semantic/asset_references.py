# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""只提取原始 Compact 已登记素材属性，不遍历运行时生成节点。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow

_ICON_COMPONENTS = frozenset(
    {
        "ProgressCircle",
        "ProgressCircleSingle",
        "PillButton",
        "CircleButton",
        "CardButton",
        "DataDisplay",
        "InfoBlock",
        "SingleLineTitle",
    }
)


@dataclass(frozen=True)
class AssetReference:
    """已确认是静态字符串的模型素材引用及原始属性位置。"""

    component: ComponentRow
    source: str
    property_label: str
    property_path: str


def task_asset_candidates(task_spec: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    """区分未提供候选约束与明确提供空候选集合。"""
    result: dict[str, dict[str, Any]] | None = None
    candidates = task_spec.get("assetCandidates")
    if isinstance(candidates, list):
        result = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            source = candidate.get("src")
            if isinstance(source, str):
                result[source] = candidate
    return result


def _append_static_reference(
    references: list[AssetReference],
    component: ComponentRow,
    source: Any,
    property_label: str,
    property_path: str,
) -> None:
    if not isinstance(source, str) or not source.strip():
        return
    if source.strip().startswith("{{"):
        return
    references.append(AssetReference(component, source, property_label, property_path))


def model_asset_references(components: list[ComponentRow]) -> list[AssetReference]:
    """类型、结构和表达式是否合法仍由组件合同及绑定规则判断。"""
    references: list[AssetReference] = []
    for component in components:
        kind = component.component_type
        if kind in _ICON_COMPONENTS:
            _append_static_reference(
                references, component, component.props.get("icon"), "icon", "/icon"
            )
        if kind == "Image":
            _append_static_reference(
                references, component, component.props.get("src"), "src", "/src"
            )
        if kind == "InfoBlock":
            visual = component.props.get("visual")
            if isinstance(visual, dict):
                _append_static_reference(
                    references, component, visual.get("icon"), "visual.icon", "/visual/icon"
                )
        if kind != "NumericRatioStack":
            continue
        items = component.props.get("items")
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            _append_static_reference(
                references,
                component,
                item.get("icon"),
                f"items[{index}].icon",
                f"/items/{index}/icon",
            )
    return references
