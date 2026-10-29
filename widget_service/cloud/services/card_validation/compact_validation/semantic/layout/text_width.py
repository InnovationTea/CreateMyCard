# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""语义布局校验：完整文案与可用宽度，保持 Fusion 主线判定和错误文本。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.text import (
    _non_negative_number,
    _uses_visual_recipe_part,
)
from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_region_layout import reference_region_boxes


def _collect_text_width_budget_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    card_spec: dict[str, Any],
    errors: list[str],
    protocol_profile: dict[str, Any] | None,
    *,
    include_label_pressure: bool = False,
    warnings: list[str] | None = None,
) -> None:
    """兜底明确单行超宽；自然宽度只用已知祖先内宽作上界，不猜实际尺寸。"""
    from services.compact_composition_context import small_card_display_text

    size = card_spec.get("suggestSize") or task_spec.get("size")
    if size not in {"2x2", "2x4"}:
        return
    nodes = []
    parents = {}
    by_id = {}
    for row in components:
        by_id[row.component_id] = row
        for child in row.children:
            parents[child] = row.component_id
        nodes.append(
            {
                "id": row.component_id,
                "component": row.component_type,
                "styles": row.props,
                "children": list(row.children),
            }
        )
    try:
        boxes = reference_region_boxes(nodes, size=size, profile=protocol_profile)
    except ValueError as exc:
        message = str(exc)
        if message not in errors:
            errors.append(message)
        return
    for row in components:
        if row.component_type not in {"Text", "Button"}:
            continue
        props = row.props
        if props.get("maxLines", 1) != 1:
            continue
        font = _non_negative_number(props.get("fontSize"))
        box = boxes.get(row.component_id)
        if font is None or box is None:
            continue
        width = box.width
        width_description = "allocated text area"
        if width is None:
            ancestor_id = parents.get(row.component_id)
            seen = set()
            while ancestor_id is not None and ancestor_id not in seen:
                seen.add(ancestor_id)
                ancestor_box = boxes.get(ancestor_id)
                ancestor = by_id.get(ancestor_id)
                if ancestor_box is not None and ancestor_box.width is not None:
                    if ancestor is not None:
                        width = ancestor_box.width - _horizontal_padding(ancestor.props)
                        width_description = "known containing area upper bound"
                    break
                ancestor_id = parents.get(ancestor_id)
        if width is None:
            continue
        content = props.get("content") if row.component_type == "Text" else props.get("label")
        # 两种尺寸共用保守的完整文案解析；不运行表达式或猜测未知字段。
        text = small_card_display_text(content, task_spec)
        if text is None and isinstance(content, str) and "{{" not in content:
            text = content
        if not isinstance(text, str) or not text or "\n" in text:
            continue
        duration_error = _compound_duration_label_width_error(
            row,
            text,
            by_id,
            parents,
            boxes,
            include_regular_text=include_label_pressure,
        )
        if duration_error is not None:
            errors.append(duration_error)
        available = width - _horizontal_padding(props)
        maximum = _non_negative_number(props.get("maxWidth"))
        if maximum is not None:
            available = min(available, maximum)
        # 普通文字保持原保守估算；仅固定强调主文字复用规划压力，不冒充端侧测量。
        required = sum(font * (0.5 if character.isascii() else 1) for character in text)
        if _uses_visual_recipe_part(row, "EmphasisText.main"):
            from services.compact_composition_planner import _text_width

            required = _text_width(text, font)
        from services.generation_content_policy import current_content_policy

        marker = props.get("_visualRecipe")
        if current_content_policy().is_static and isinstance(marker, str):
            if marker.startswith("static-content-v1:"):
                from services.static_text_capacity import text_width

                required = text_width(text, font)
        if available > 0 and required > available + 1e-7:
            static_runtime_ellipsis = (
                props.get("textOverflow") == "ellipsis"
                and isinstance(marker, str)
                and marker.startswith(
                    (
                        "static-content-v1:TextList.",
                        "static-content-v1:ComparisonGroup.",
                        "static-content-v1:EmphasisText.secondaryText",
                    )
                )
            )
            if static_runtime_ellipsis:
                if warnings is not None:
                    warnings.append(
                        f"component {row.component_id}: static text exceeds its "
                        f"{available:g}vp single-line text area and will be rendered with "
                        "an ellipsis."
                    )
                continue
            text_block_part = None
            for part in ("TextBlock.label", "TextBlock.value"):
                if _uses_visual_recipe_part(row, part):
                    text_block_part = part
                    break
            if text_block_part is not None:
                if warnings is not None:
                    warnings.append(
                        f"component {row.component_id}: {text_block_part} exceeds its "
                        f"{available:g}vp single-line text area and will be rendered with "
                        "an ellipsis."
                    )
                continue
            if _uses_visual_recipe_part(row, "InfoBlock.secondary"):
                if warnings is not None:
                    warnings.append(
                        f"component {row.component_id}: InfoBlock.secondaryText exceeds its "
                        f"{available:g}vp single-line text area and will be rendered with "
                        "an ellipsis."
                    )
                continue
            if _uses_visual_recipe_part(row, "CardButton.label"):
                if warnings is not None:
                    warnings.append(
                        f"component {row.component_id}: CardButton.label exceeds its "
                        f"{available:g}vp single-line text area and will be rendered with "
                        "an ellipsis."
                    )
                continue
            errors.append(
                f"component {row.component_id}: text width overflow; complete text {text!r} "
                f"at original font {font:g} needs about {required:g}vp in one line, "
                f"but its {width_description} is {available:g}vp. Keep every label, prefix, "
                "value and action; use legal lines at the same font or regroup into a wider "
                "region. A fixed single-line component needs same-font separate lines or a "
                "different legal composition, not clipping, smaller secondary text or weight."
            )


def _compound_duration_label_width_error(
    row: ComponentRow,
    text: str,
    by_id: dict[str, ComponentRow],
    parents: dict[str, str],
    boxes: dict[str, Any],
    *,
    include_regular_text: bool = False,
) -> str | None:
    """带标签的多段时长按完整同行压力核算；未知兄弟宽度不猜测。"""
    from services.compact_composition_planner import _text_width, is_compound_duration_text

    if (not include_regular_text and not is_compound_duration_text(text)) or row.props.get(
        "layoutWeight"
    ) != 1:
        return None
    parent_id = parents.get(row.component_id)
    parent = by_id.get(parent_id)
    box = boxes.get(parent_id)
    if parent is None or box is None:
        return None
    if not _uses_visual_recipe_part(parent, "SecondaryBody.item") or box.width is None:
        return None
    font = _non_negative_number(row.props.get("fontSize"))
    if font is None:
        return None
    required = _text_width(text, font)
    labels: list[str] = []
    for identifier in parent.children:
        if identifier == row.component_id:
            continue
        sibling = by_id.get(identifier)
        if sibling is None or sibling.component_type != "Text":
            return None
        label = sibling.props.get("content")
        sibling_font = _non_negative_number(sibling.props.get("fontSize"))
        if not isinstance(label, str) or "{{" in label or sibling_font is None:
            return None
        if _non_negative_number(sibling.props.get("width")) is not None:
            return None
        labels.append(label)
        required += _text_width(label, sibling_font) + _horizontal_padding(sibling.props)
    if not labels:
        return None
    gap = _non_negative_number(parent.props.get("itemMargin")) or 0
    required += gap * max(0, len(parent.children) - 1)
    available = box.width - _horizontal_padding(parent.props)
    if required <= available + 1e-7:
        return None
    return (
        f"component {parent.component_id}: "
        + ("text width overflow; " if include_regular_text else "")
        + f"complete label {''.join(labels)!r} plus compound "
        f"{'value' if include_regular_text else 'duration'} {text!r} requires about "
        f"{required:g}vp of pressure width within "
        f"{available:g}vp at the original body font. Keep the full label and value; use "
        "legal two-line body text at the same font and budget its height, or regroup. "
        "Weight, clipping and dropping units do not close this text budget."
    )


def _horizontal_padding(props: dict[str, Any]) -> float:
    value = props.get("padding", 0)
    if isinstance(value, dict):
        return sum(_non_negative_number(value.get(side)) or 0 for side in ("left", "right"))
    return (_non_negative_number(value) or 0) * 2
