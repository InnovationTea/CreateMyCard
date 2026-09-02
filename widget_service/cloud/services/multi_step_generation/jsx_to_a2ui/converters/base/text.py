from __future__ import annotations

from typing import Any

from ...ir.a2ui_nodes import A2UINode, ConversionContext


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
