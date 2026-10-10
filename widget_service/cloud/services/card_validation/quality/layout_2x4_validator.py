from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric, resolve_dimension, spacing_tuple
from .common import add, children_of, component_pointer


class Layout2x4Validator(BaseValidator):
    stage = "quality"
    name = "layout_2x4"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        suggest_size = context.cardspec.get("suggestSize")
        if suggest_size != "2x4":
            return
        root = context.components_by_id.get(context.root_id) if context.root_id else None
        if not isinstance(root, dict):
            return
        indexes = {
            component.get("id"): index
            for index, component in enumerate(context.components)
            if isinstance(component.get("id"), str)
        }
        equal_split_tokens = self._equal_split_tokens(rules)
        self._walk(
            context,
            reporter,
            root,
            indexes,
            equal_split_tokens,
            320.0,
            160.0,
            set(),
        )

    def _walk(
        self,
        context: Any,
        reporter: Any,
        component: dict[str, Any],
        indexes: dict[str, int],
        equal_split_tokens: tuple[str, ...],
        parent_width: float,
        parent_height: float,
        visited: set[str],
    ) -> None:
        component_id = component.get("id")
        if not isinstance(component_id, str) or component_id in visited:
            return
        visited.add(component_id)
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        width = resolve_dimension(styles.get("width"), parent_width)
        height = resolve_dimension(styles.get("height"), parent_height)
        resolved_width = width if width is not None else parent_width
        resolved_height = height if height is not None else parent_height
        children = children_of(component, context.components_by_id)
        if component.get("component") in {"Row", "Column"} and children:
            self._check_container(
                reporter,
                component,
                children,
                indexes.get(component_id, 0),
                equal_split_tokens,
                resolved_width,
                resolved_height,
            )
        padding = spacing_tuple(styles.get("padding"))
        child_width = max(0.0, resolved_width - padding[1] - padding[3])
        child_height = max(0.0, resolved_height - padding[0] - padding[2])
        for child in children:
            self._walk(
                context,
                reporter,
                child,
                indexes,
                equal_split_tokens,
                child_width,
                child_height,
                visited,
            )

    def _check_container(
        self,
        reporter: Any,
        component: dict[str, Any],
        children: list[dict[str, Any]],
        index: int,
        equal_split_tokens: tuple[str, ...],
        width: float,
        height: float,
    ) -> None:
        is_row = component.get("component") == "Row"
        dimension_key = "width" if is_row else "height"
        parent = width if is_row else height
        cross_key = "height" if is_row else "width"
        cross_parent = height if is_row else width
        styles = component.get("styles")
        styles = styles if isinstance(styles, dict) else {}
        padding = spacing_tuple(styles.get("padding"))
        before = padding[3] if is_row else padding[0]
        after = padding[1] if is_row else padding[2]
        cross_before = padding[0] if is_row else padding[3]
        cross_after = padding[2] if is_row else padding[1]
        inner_parent = max(0.0, parent - before - after)
        inner_cross = max(0.0, cross_parent - cross_before - cross_after)
        gap = numeric(component.get("itemMargin")) or 0.0
        occupied_values: list[float] = []
        equal_split_values: list[float] = []
        all_dimensions_known = True
        for child in children:
            child_styles = child.get("styles")
            child_styles = child_styles if isinstance(child_styles, dict) else {}
            value = resolve_dimension(child_styles.get(dimension_key), inner_parent)
            margins = spacing_tuple(child_styles.get("margin"))
            margin = margins[1] + margins[3] if is_row else margins[0] + margins[2]
            if value is None:
                all_dimensions_known = False
                occupied_values.append(margin)
            else:
                occupied = value + margin
                occupied_values.append(occupied)
                equal_split_values.append(occupied)
            cross_value = resolve_dimension(child_styles.get(cross_key), inner_cross)
            cross_margin = margins[0] + margins[2] if is_row else margins[1] + margins[3]
            cross_occupied = cross_margin
            if cross_value is not None:
                cross_occupied += cross_value
            if cross_occupied > inner_cross + 1:
                add(
                    reporter,
                    "LAYOUT2X4.CLOSURE",
                    component_pointer(index, "children"),
                    "2x4 子项超出容器交叉轴尺寸。",
                    round(cross_occupied, 2),
                    inner_cross,
                )
        total = before + after + sum(occupied_values) + gap * (len(children) - 1)
        if total > parent + 1:
            add(
                reporter,
                "LAYOUT2X4.CLOSURE",
                component_pointer(index, f"styles/{dimension_key}"),
                "2x4 容器内容超出声明尺寸。",
                round(total, 2),
                parent,
            )
        component_id = component.get("id")
        requires_equal_split = isinstance(component_id, str) and any(
            token in component_id.lower() for token in equal_split_tokens
        )
        if not requires_equal_split or not all_dimensions_known:
            return
        available = inner_parent - gap * (len(children) - 1)
        expected = available / len(children)
        if any(abs(value - expected) > 1 for value in equal_split_values):
            add(
                reporter,
                "LAYOUT2X4.EQUAL_SPLIT",
                component_pointer(index, "children"),
                "2x4 等分容器的子项尺寸不一致。",
                equal_split_values,
                round(expected, 2),
            )

    @staticmethod
    def _equal_split_tokens(rules: Any) -> tuple[str, ...]:
        fallback = ("equal", "grid", "metrics", "cells")
        if rules is None:
            return fallback
        configured = rules.layout.get("equalSplitIdTokens")
        if not isinstance(configured, list):
            return fallback
        tokens = tuple(
            token.strip().lower()
            for token in configured
            if isinstance(token, str) and token.strip()
        )
        return tokens or fallback
