# -*- coding: utf-8 -*-
"""Detect large unused layout regions in non-template genui cards.

This validator intentionally reports repair guidance instead of mutating genui.
The model or the generation repair loop remains responsible for choosing whether
to redistribute children, change alignment, or add/remove a layout container.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..base import numeric, spacing_tuple
from ..context import ValidationContext

_LAYOUT_COMPONENTS = {"Row", "Column"}
_CONTENT_COMPONENTS = {"Button", "Text", "Image", "Progress", "Slider"}
_DISTRIBUTED_ALIGNMENTS = {"spaceBetween", "spaceAround", "spaceEvenly"}
_DEFAULT_CANVAS = {
    "2x2": (140.0, 140.0),
    "2x4": (300.0, 140.0),
}
_MIN_REMAINING = 24.0
_REMAINING_RATIO = 0.25


@dataclass(frozen=True)
class _LayoutSize:
    width: float | None
    height: float | None


class LayoutDistributionValidator:
    """Check that ordinary Row/Column content uses its parent space evenly."""

    stage = "quality"
    name = "layout_distribution"

    def validate(
        self,
        context: ValidationContext,
        rules: Any,
        reporter: Any,
    ) -> None:
        del rules
        if not context.components or not context.root_id:
            return

        canvas = self._canvas_size(context)
        sizes: dict[str, _LayoutSize] = {}
        self._measure_component(context, context.root_id, canvas, sizes, set())
        for component in context.components:
            component_type = component.get("component")
            children = component.get("children")
            if component_type not in _LAYOUT_COMPONENTS or not isinstance(children, list):
                continue
            child_ids = [child_id for child_id in children if isinstance(child_id, str)]
            if len(child_ids) < 2:
                self._check_redundant_wrapper(component, child_ids, context, reporter)
                continue
            self._check_distribution(component, child_ids, sizes, context, reporter)
            self._check_redundant_wrapper(component, child_ids, context, reporter)


    @staticmethod
    def _canvas_size(context: ValidationContext) -> _LayoutSize:
        size = context.cardspec.get("suggestSize")
        width, height = _DEFAULT_CANVAS.get(size, _DEFAULT_CANVAS["2x2"])
        return _LayoutSize(width, height)

    def _measure_component(
        self,
        context: ValidationContext,
        component_id: str,
        parent_size: _LayoutSize,
        sizes: dict[str, _LayoutSize],
        visiting: set[str],
    ) -> _LayoutSize:
        if component_id in sizes:
            return sizes[component_id]
        if component_id in visiting:
            return _LayoutSize(None, None)
        component = context.components_by_id.get(component_id)
        if not isinstance(component, dict):
            return _LayoutSize(None, None)
        visiting.add(component_id)
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        width = self._dimension(styles.get("width"), parent_size.width)
        height = self._dimension(styles.get("height"), parent_size.height)
        children = component.get("children")
        child_ids = (
            [item for item in children if isinstance(item, str)]
            if isinstance(children, list)
            else []
        )
        child_sizes: list[_LayoutSize] = []
        for child_id in child_ids:
            child_sizes.append(
                self._measure_component(
                    context,
                    child_id,
                    _LayoutSize(width, height),
                    sizes,
                    visiting,
                )
            )
        if component.get("component") == "Column" and height is None:
            height = self._sum_axis(child_sizes, styles, axis="height")
        if component.get("component") == "Row" and width is None:
            width = self._sum_axis(child_sizes, styles, axis="width")
        result = _LayoutSize(width, height)
        sizes[component_id] = result
        visiting.remove(component_id)
        return result

    @staticmethod
    def _dimension(value: Any, parent: float | None) -> float | None:
        if isinstance(value, str) and value.strip() == "matchParent":
            return parent
        return numeric(value)

    def _sum_axis(
        self,
        child_sizes: list[_LayoutSize],
        styles: dict[str, Any],
        *,
        axis: str,
    ) -> float | None:
        values = [getattr(size, axis) for size in child_sizes]
        if any(value is None for value in values):
            return None
        total = sum(value for value in values if value is not None)
        gap = numeric(styles.get("space")) or numeric(styles.get("itemMargin")) or 0.0
        return total + gap * max(0, len(values) - 1) + self._axis_padding(styles, axis)

    @staticmethod
    def _axis_padding(styles: dict[str, Any], axis: str) -> float:
        top, right, bottom, left = spacing_tuple(styles.get("padding"))
        return top + bottom if axis == "height" else left + right

    def _check_distribution(
        self,
        component: dict[str, Any],
        child_ids: list[str],
        sizes: dict[str, _LayoutSize],
        context: ValidationContext,
        reporter: Any,
    ) -> None:
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        component_id = component.get("id")
        if not isinstance(component_id, str):
            return
        parent_size = sizes.get(component_id)
        if parent_size is None:
            return
        is_row = component.get("component") == "Row"
        axis = "width" if is_row else "height"
        available = getattr(parent_size, axis)
        if available is None:
            return
        padding = self._axis_padding(styles, axis)
        available -= padding
        child_sizes = [sizes.get(child_id) for child_id in child_ids]
        if any(size is None or getattr(size, axis) is None for size in child_sizes):
            return
        occupied = sum(getattr(size, axis) for size in child_sizes if size is not None)
        gap = numeric(styles.get("space")) or numeric(styles.get("itemMargin")) or 0.0
        occupied += gap * max(0, len(child_ids) - 1)
        remaining = available - occupied
        if remaining <= max(_MIN_REMAINING, available * _REMAINING_RATIO):
            return
        alignment = styles.get("justifyContent")
        if alignment in _DISTRIBUTED_ALIGNMENTS:
            return
        if self._has_weighted_child(context, child_ids):
            return
        has_fillable_content = any(
            self._contains_fillable_content(context, child_id, set())
            for child_id in child_ids
        )
        if has_fillable_content:
            pointer = self._component_pointer(component_id, "justifyContent")
            reporter.add(
                "warning",
                "QUALITY.LAYOUT_UNBALANCED",
                self.stage,
                "genui",
                line=2,
                json_pointer=pointer,
                actual={
                    "container": component_id,
                    "axis": axis,
                    "available": round(available, 2),
                    "occupied": round(occupied, 2),
                    "remaining": round(remaining, 2),
                    "childCount": len(child_ids),
                },
                expected="内容沿父容器主轴均匀分布，且剩余空间不形成大片空白",
                message=(
                    f"容器 {component_id} 的{('横向' if is_row else '纵向')}内容集中在一侧，"
                    f"约有 {remaining:.0f}vp 未使用。"
                ),
                fix_hint=(
                    "根据内容关系选择 justifyContent=spaceBetween/spaceEvenly，或给可伸缩子项"
                    "增加 layoutWeight；必要时合并冗余容器，或增加一层 Row/Column 将内容分组。"
                ),
                source="quality-layout-distribution",
            )

    def _check_redundant_wrapper(
        self,
        component: dict[str, Any],
        child_ids: list[str],
        context: ValidationContext,
        reporter: Any,
    ) -> None:
        if len(child_ids) != 1:
            return
        child = context.components_by_id.get(child_ids[0])
        if not isinstance(child, dict):
            return
        parent_type = component.get("component")
        child_type = child.get("component")
        if parent_type not in _LAYOUT_COMPONENTS or parent_type != child_type:
            return
        parent_styles = component.get("styles")
        child_styles = child.get("styles")
        if not isinstance(parent_styles, dict) or not isinstance(child_styles, dict):
            return
        if parent_styles.get("justifyContent") or parent_styles.get("alignItems"):
            return
        component_id = component.get("id")
        if not isinstance(component_id, str):
            return
        reporter.add(
            "warning",
            "QUALITY.LAYOUT_REDUNDANT_CONTAINER",
            self.stage,
            "genui",
            line=2,
            json_pointer=f"/updateComponents/componentsById/{component_id}/children",
            actual={"container": component_id, "child": child_ids[0]},
            expected="容器层级与内容分组关系清晰",
            message=f"容器 {component_id} 只有一个同类型布局子容器，可能产生无意义的嵌套。",
            fix_hint="如果没有独立的对齐、背景或点击语义，请移除一层容器；否则保留并明确其布局职责。",
            source="quality-layout-distribution",
        )

    @staticmethod
    def _has_weighted_child(context: ValidationContext, child_ids: list[str]) -> bool:
        for child_id in child_ids:
            child = context.components_by_id.get(child_id)
            if not isinstance(child, dict):
                continue
            styles = child.get("styles")
            if isinstance(styles, dict) and numeric(styles.get("layoutWeight")):
                return True
        return False

    def _contains_fillable_content(
        self,
        context: ValidationContext,
        component_id: str,
        visiting: set[str],
    ) -> bool:
        if component_id in visiting:
            return False
        component = context.components_by_id.get(component_id)
        if not isinstance(component, dict):
            return False
        if component.get("component") in _CONTENT_COMPONENTS:
            return True
        children = component.get("children")
        if not isinstance(children, list):
            return False
        visiting.add(component_id)
        for child_id in children:
            if isinstance(child_id, str) and self._contains_fillable_content(
                context,
                child_id,
                visiting,
            ):
                visiting.remove(component_id)
                return True
        visiting.remove(component_id)
        return False

    @staticmethod
    def _component_pointer(component_id: str, field: str) -> str:
        return f"/updateComponents/componentsById/{component_id}/styles/{field}"
