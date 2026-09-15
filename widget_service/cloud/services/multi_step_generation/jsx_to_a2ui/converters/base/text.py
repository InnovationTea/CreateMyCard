from __future__ import annotations

from typing import Any

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from .layout import stack


def text(
    ctx: ConversionContext,
    hint: str,
    content: Any,
    *,
    styles: dict[str, Any] | None = None,
    accessibility: dict[str, Any] | None = None,
) -> A2UINode:
    # Preserve a standard A2UI path binding instead of stringifying it.
    props: dict[str, Any] = {"content": content if isinstance(content, dict) else str(content)}
    if accessibility:
        props["accessibility"] = accessibility
    return ctx.make("Text", hint, props=props, styles=styles)


def fixed_text_line_box(
    ctx: ConversionContext,
    hint: str,
    content: A2UINode,
    height: int,
) -> A2UINode:
    """Reserve an atomic line box without sizing the text paragraph to it."""
    # wrapContent is bounded by the parent's box. Intrinsic sizing must also
    # preserve wide atomic numbers and paragraphs taller than their line box.
    content.styles.update(
        {"width": "fixAtIdealSize", "height": "fixAtIdealSize", "flexShrink": 0}
    )
    return stack(
        ctx,
        hint,
        [content],
        align="center",
        styles={"width": "fixAtIdealSize", "height": height, "flexShrink": 0},
    )
