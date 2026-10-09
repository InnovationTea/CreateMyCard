from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric
from .common import add, children_of, contains_action, quality_scene

_CONTAINERS = {"Row", "Column", "Stack", "List"}
_TITLE_TOKENS = ("title", "header", "kicker")


class SlotValidator(BaseValidator):
    stage = "quality"
    name = "slot"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        scene = quality_scene(context)
        if scene is None:
            return
        content_root = self._region_root(scene.content_root, context.components_by_id)
        children = children_of(content_root, context.components_by_id)
        if not children:
            add(
                reporter,
                "SLOT.MODEL_REQUIRED",
                self._children_pointer(content_root),
                "卡片至少需要标题或内容区域。",
                len(children),
                ">= 1",
            )
            return
        action_indexes = [
            index
            for index, child in enumerate(children)
            if contains_action(child, context.components_by_id)
        ]
        if action_indexes and action_indexes[-1] != len(children) - 1:
            add(
                reporter,
                "SLOT.ORDER",
                self._children_pointer(content_root),
                "操作区域应位于最后。",
                action_indexes,
                "title, content, action",
            )
        title = self._find_title(children[0], context.components_by_id)
        if title is None:
            return
        styles = title.get("styles")
        size = numeric(styles.get("fontSize")) if isinstance(styles, dict) else None
        suggest_size = context.cardspec.get("suggestSize")
        allowed_sizes = self._title_sizes(rules, suggest_size)
        if size is not None and size not in allowed_sizes:
            add(
                reporter,
                "AREA.TITLE_TEXT_TIER",
                f"/updateComponents/componentsById/{title.get('id')}/styles/fontSize",
                "标题区域字号不符合卡片尺寸档位。",
                size,
                sorted(allowed_sizes),
            )

    @staticmethod
    def _title_sizes(rules: Any, suggest_size: Any) -> set[float]:
        fallback = {12.0, 18.0} if suggest_size == "2x4" else {12.0}
        if rules is None or not isinstance(suggest_size, str):
            return fallback
        configured = rules.layout.get("titleFontSizes")
        if not isinstance(configured, dict):
            return fallback
        raw_sizes = configured.get(suggest_size)
        if not isinstance(raw_sizes, list):
            return fallback
        sizes = {
            float(size)
            for size in raw_sizes
            if isinstance(size, (int, float)) and not isinstance(size, bool)
        }
        return sizes or fallback

    @classmethod
    def _region_root(
        cls,
        component: dict[str, Any],
        by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        current = component
        visited: set[str] = set()
        while current.get("component") in _CONTAINERS:
            current_id = current.get("id")
            if not isinstance(current_id, str) or current_id in visited:
                break
            visited.add(current_id)
            children = children_of(current, by_id)
            handlers = current.get("onClick")
            has_direct_action = isinstance(handlers, list) and bool(handlers)
            if len(children) != 1 or has_direct_action:
                break
            child = children[0]
            if child.get("component") not in _CONTAINERS:
                break
            current = child
        return current

    @classmethod
    def _find_title(
        cls,
        component: dict[str, Any],
        by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        stack = [component]
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            component_id = current.get("id")
            if not isinstance(component_id, str) or component_id in visited:
                continue
            visited.add(component_id)
            is_title = any(token in component_id.lower() for token in _TITLE_TOKENS)
            if current.get("component") == "Text" and is_title:
                return current
            children = children_of(current, by_id)
            stack.extend(reversed(children))
        return None

    @staticmethod
    def _children_pointer(component: dict[str, Any]) -> str:
        return f"/updateComponents/componentsById/{component.get('id')}/children"
