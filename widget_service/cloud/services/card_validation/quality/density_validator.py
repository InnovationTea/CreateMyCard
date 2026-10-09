from __future__ import annotations

import re
from typing import Any

from ..base import BaseValidator, numeric
from .common import add, display_text, iter_reachable_components, parents_by_id

_NUMBER_PREFIX = re.compile(r"^[+\-]?\d")


class DensityValidator(BaseValidator):
    stage = "quality"
    name = "density"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        suggest_size = context.cardspec.get("suggestSize")
        if suggest_size not in {"2x2", "2x4"}:
            return
        reachable = list(iter_reachable_components(context))
        actions = [
            component
            for component in reachable
            if isinstance(component.get("onClick"), list) and component.get("onClick")
        ]
        default_action_limit = 2 if suggest_size == "2x4" else 1
        limit = self._size_limit(
            rules,
            "maxExplicitActions",
            suggest_size,
            default_action_limit,
        )
        if len(actions) > limit:
            add(
                reporter,
                "DENSITY.EXPLICIT_ACTIONS",
                "/updateComponents/components",
                "显式操作数量超过卡片尺寸上限。",
                len(actions),
                f"<= {limit}",
            )
        if len(actions) > 1:
            add(
                reporter,
                "DENSITY.SINGLE_PRIMARY_ACTION",
                "/updateComponents/components",
                "卡片默认只保留一个主要操作。",
                len(actions),
                1,
            )
        numbers = [
            component
            for component in reachable
            if self._is_large_number(component, context.data_model)
        ]
        default_number_limit = 2 if suggest_size == "2x4" else 1
        number_limit = self._size_limit(
            rules,
            "maxLargeNumbers",
            suggest_size,
            default_number_limit,
        )
        number_count = self._count_focus_items(context, numbers)
        if number_count > number_limit:
            add(
                reporter,
                "DENSITY.NUMBERS",
                "/updateComponents/components",
                "卡片不应同时出现多个大字号数字。",
                number_count,
                f"<= {number_limit}",
            )

    @classmethod
    def _count_focus_items(cls, context: Any, numbers: list[dict[str, Any]]) -> int:
        """将获准的同级对照数字作为一个焦点组计数。"""
        if len(numbers) < 2:
            return len(numbers)
        number_ids = {
            component.get("id")
            for component in numbers
            if isinstance(component.get("id"), str)
        }
        parents = parents_by_id(context)
        grouped_ids: set[str] = set()
        group_count = 0
        for component in numbers:
            component_id = component.get("id")
            if not isinstance(component_id, str) or component_id in grouped_ids:
                continue
            group = cls._sibling_focus_group(
                component,
                number_ids,
                parents,
                context.components_by_id,
            )
            if len(group) >= 2:
                grouped_ids.update(group)
                group_count += 1
            else:
                grouped_ids.add(component_id)
                group_count += 1
        return group_count

    @classmethod
    def _sibling_focus_group(
        cls,
        component: dict[str, Any],
        number_ids: set[str],
        parents: dict[str, set[str]],
        components_by_id: dict[str, dict[str, Any]],
    ) -> set[str]:
        component_id = component.get("id")
        if not isinstance(component_id, str):
            return set()
        for parent_id in parents.get(component_id, set()):
            parent = components_by_id.get(parent_id)
            if not isinstance(parent, dict) or parent.get("component") != "Row":
                continue
            children = parent.get("children")
            if not isinstance(children, list):
                continue
            sibling_ids = {
                child_id
                for child_id in children
                if isinstance(child_id, str) and child_id in number_ids
            }
            if len(sibling_ids) < 2:
                continue
            siblings = [components_by_id[sibling_id] for sibling_id in sibling_ids]
            if cls._same_focus_style(siblings) and cls._fits_row(parent, siblings):
                return sibling_ids
        return set()

    @staticmethod
    def _same_focus_style(siblings: list[dict[str, Any]]) -> bool:
        first_styles = siblings[0].get("styles")
        if not isinstance(first_styles, dict):
            return False
        signature = (
            numeric(first_styles.get("fontSize")),
            numeric(first_styles.get("fontWeight")) or 400,
            first_styles.get("textAlign", "start"),
        )
        for sibling in siblings[1:]:
            styles = sibling.get("styles")
            if not isinstance(styles, dict):
                return False
            sibling_signature = (
                numeric(styles.get("fontSize")),
                numeric(styles.get("fontWeight")) or 400,
                styles.get("textAlign", "start"),
            )
            if sibling_signature != signature:
                return False
        return True

    @staticmethod
    def _fits_row(parent: dict[str, Any], siblings: list[dict[str, Any]]) -> bool:
        parent_styles = parent.get("styles")
        if not isinstance(parent_styles, dict):
            return True
        row_width = numeric(parent_styles.get("width"))
        item_margin = numeric(parent.get("itemMargin"))
        widths: list[float] = []
        for sibling in siblings:
            styles = sibling.get("styles")
            width = numeric(styles.get("width")) if isinstance(styles, dict) else None
            if width is None:
                return True
            widths.append(width)
        if row_width is None or item_margin is None:
            return True
        return sum(widths) + item_margin * (len(widths) - 1) <= row_width

    @staticmethod
    def _is_large_number(component: dict[str, Any], data_model: Any) -> bool:
        if component.get("component") != "Text":
            return False
        styles = component.get("styles")
        size = numeric(styles.get("fontSize")) if isinstance(styles, dict) else None
        if size is None or size < 24:
            return False
        text = display_text(component.get("content"), data_model)
        return isinstance(text, str) and _NUMBER_PREFIX.match(text.strip()) is not None

    @staticmethod
    def _size_limit(
        rules: Any,
        rule_name: str,
        suggest_size: str,
        fallback: int,
    ) -> int:
        if rules is None:
            return fallback
        configured = rules.layout.get(rule_name)
        if not isinstance(configured, dict):
            return fallback
        value = configured.get(suggest_size)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return fallback
