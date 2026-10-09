from __future__ import annotations

import re
from typing import Any

from ..base import BaseValidator, numeric
from .common import add, display_text, iter_reachable_components

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
        if len(numbers) > number_limit:
            add(
                reporter,
                "DENSITY.NUMBERS",
                "/updateComponents/components",
                "卡片不应同时出现多个大字号数字。",
                len(numbers),
                f"<= {number_limit}",
            )

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
