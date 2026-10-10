from __future__ import annotations

from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, display_text, iter_components


class CopyValidator(BaseValidator):
    stage = "quality"
    name = "copy"
    title_tokens = ("title", "header", "kicker")

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        suggest_size = context.cardspec.get("suggestSize")
        default_action_limit = 6
        action_limit = self._size_limit(
            rules,
            "maxActionLabelChars",
            suggest_size,
            default_action_limit,
        )
        title_limit = self._size_limit(rules, "titleMaxChars", suggest_size, 9)
        for index, component in iter_components(context):
            if component.get("component") == "Button":
                self._check_value(
                    reporter,
                    index,
                    "label",
                    component.get("label"),
                    context.data_model,
                    action_limit,
                    "COPY.ACTION_LABEL_MAX_CHARS",
                )
                continue
            if component.get("component") != "Text":
                continue
            component_id = component.get("id")
            is_title = isinstance(component_id, str) and any(
                token in component_id.lower() for token in self.title_tokens
            )
            is_action = isinstance(component.get("onClick"), list) and component.get("onClick")
            if not is_title and not is_action:
                continue
            limit = action_limit if is_action else title_limit
            code = "COPY.ACTION_LABEL_MAX_CHARS" if is_action else "COPY.TITLE_MAX_CHARS"
            self._check_value(
                reporter,
                index,
                "content",
                component.get("content"),
                context.data_model,
                limit,
                code,
            )

    @staticmethod
    def _check_value(
        reporter: Any,
        component_index: int,
        field: str,
        value: Any,
        data_model: Any,
        limit: int,
        code: str,
    ) -> None:
        text = display_text(value, data_model)
        if text is None or len(text) <= limit:
            return
        add(
            reporter,
            code,
            component_pointer(component_index, field),
            "文案超过卡片设计长度限制。",
            len(text),
            f"<= {limit} 字",
        )

    @staticmethod
    def _size_limit(
        rules: Any,
        rule_name: str,
        suggest_size: Any,
        fallback: int,
    ) -> int:
        if rules is None or not isinstance(suggest_size, str):
            return fallback
        configured = rules.layout.get(rule_name)
        if not isinstance(configured, dict):
            return fallback
        value = configured.get(suggest_size)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return fallback
