from __future__ import annotations

from typing import Any

from ..base import BaseValidator, numeric, spacing_tuple
from .common import (
    FUSION_BACKGROUND_ID,
    FUSION_CONTENT_ID_PREFIX,
    add,
    component_pointer,
    iter_components,
)


class SpacingValidator(BaseValidator):
    stage = "quality"
    name = "spacing"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        default_padding = 12
        if rules is not None:
            configured_padding = numeric(rules.layout.get("defaultPadding"))
            if configured_padding is not None:
                default_padding = configured_padding
        safe_root_id = self._safe_root_id(context)
        safe_label = "根容器" if safe_root_id == context.root_id else "内容容器"
        size = context.cardspec.get("suggestSize")
        card_width = {"2x2": 160.0, "2x4": 320.0}.get(size)
        for index, component in iter_components(context):
            styles = component.get("styles")
            if not isinstance(styles, dict):
                if component.get("id") == safe_root_id:
                    add(
                        reporter,
                        "SPACING.SAFE_MARGIN",
                        component_pointer(index, "styles/padding"),
                        f"{safe_label}安全边距应为 {default_padding:g}vp。",
                        None,
                        default_padding,
                    )
                continue
            padding = styles.get("padding")
            if component.get("id") == safe_root_id and not self._matches_padding(
                padding,
                default_padding,
            ):
                add(
                    reporter,
                    "SPACING.SAFE_MARGIN",
                    component_pointer(index, "styles/padding"),
                    f"{safe_label}安全边距应为 {default_padding:g}vp。",
                    padding,
                    default_padding,
                )
            self._check_explicit_width(
                reporter,
                index,
                component,
                safe_root_id,
                card_width,
            )
            self._check_button_padding(reporter, index, component)

    @staticmethod
    def _check_explicit_width(
        reporter: Any,
        index: int,
        component: dict[str, Any],
        safe_root_id: str | None,
        card_width: float | None,
    ) -> None:
        if card_width is None or component.get("id") == safe_root_id:
            return
        styles = component.get("styles")
        width = numeric(styles.get("width")) if isinstance(styles, dict) else None
        if width is None:
            return
        margin = spacing_tuple(styles.get("margin")) if isinstance(styles, dict) else None
        horizontal_margin = margin[1] + margin[3] if margin else 0.0
        if width + horizontal_margin > card_width - 24:
            add(
                reporter,
                "SPACING.SAFE_AREA_OVERFLOW",
                component_pointer(index, "styles/width"),
                "元素宽度超出左右 12vp 安全区域。",
                width + horizontal_margin,
                f"<= {card_width - 24:g}",
            )

    @staticmethod
    def _check_button_padding(reporter: Any, index: int, component: dict[str, Any]) -> None:
        if component.get("component") != "Button":
            return
        styles = component.get("styles")
        padding = spacing_tuple(styles.get("padding")) if isinstance(styles, dict) else None
        if padding is not None and (padding[1] < 8 or padding[3] < 8):
            add(
                reporter,
                "SPACING.BUTTON_CONTENT_PADDING",
                component_pointer(index, "styles/padding"),
                "按钮内容到左右边缘的最小内边距为 8vp。",
                padding,
                ">= 8vp",
            )

    @staticmethod
    def _safe_root_id(context: Any) -> str | None:
        safe_root_id: str | None = context.root_id
        root = context.components_by_id.get(safe_root_id)
        if not isinstance(root, dict) or root.get("component") != "Stack":
            return safe_root_id
        children = root.get("children")
        if not isinstance(children, list) or "root_0" in children:
            return safe_root_id
        foreground_ids = [child for child in children if child != FUSION_BACKGROUND_ID]
        if len(foreground_ids) != 1:
            return safe_root_id
        foreground_id = foreground_ids[0]
        if not isinstance(foreground_id, str):
            return safe_root_id
        foreground = context.components_by_id.get(foreground_id)
        if not isinstance(foreground, dict):
            return safe_root_id
        if foreground.get("component") not in {"Row", "Column", "Stack"}:
            return safe_root_id
        is_fusion = FUSION_BACKGROUND_ID in children
        is_template = SpacingValidator._is_template_foreground(foreground, context)
        is_layered = SpacingValidator._is_plain_foreground(root, foreground)
        if is_fusion or is_template or is_layered:
            safe_root_id = foreground_id
        return safe_root_id

    @staticmethod
    def _is_plain_foreground(root: dict[str, Any], foreground: dict[str, Any]) -> bool:
        children = root.get("children")
        if not isinstance(children, list) or len(children) != 1:
            return False
        styles = root.get("styles")
        padding = styles.get("padding") if isinstance(styles, dict) else None
        if padding is not None and not SpacingValidator._matches_padding(padding, 0):
            return False
        foreground_styles = foreground.get("styles")
        if not isinstance(foreground_styles, dict):
            return False
        return (
            foreground_styles.get("width") == "matchParent"
            and foreground_styles.get("height") == "matchParent"
        )

    @staticmethod
    def _is_template_foreground(foreground: dict[str, Any], context: Any) -> bool:
        if foreground.get("id") != "template_root" or foreground.get("component") != "Stack":
            return False
        children = foreground.get("children")
        if not isinstance(children, list) or len(children) != 1:
            return False
        content_id = children[0]
        if not isinstance(content_id, str) or not content_id.startswith(FUSION_CONTENT_ID_PREFIX):
            return False
        content = context.components_by_id.get(content_id)
        return isinstance(content, dict) and content.get("component") in {"Row", "Column", "Stack"}

    @staticmethod
    def _matches_padding(value: Any, expected: float) -> bool:
        if value is None:
            return False
        return spacing_tuple(value) == (expected, expected, expected, expected)

