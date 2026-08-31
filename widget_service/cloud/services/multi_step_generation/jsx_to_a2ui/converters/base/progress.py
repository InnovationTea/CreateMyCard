from __future__ import annotations

from typing import Any

from ...ir.a2ui_nodes import A2UINode, ConversionContext


def progress(ctx: ConversionContext, hint: str, value: Any, total: Any = 100, *, kind: str = "linear", color: str | None = None, stroke_width: int | float | None = None, styles: dict[str, Any] | None = None) -> A2UINode:
    values = dict(styles or {})
    values["type"] = kind
    if kind == "linear" and "borderRadius" not in values:
        thickness = values.get("height", stroke_width)
        if isinstance(thickness, (int, float)) and not isinstance(thickness, bool) and thickness > 0:
            radius = thickness / 2
            values["borderRadius"] = int(radius) if radius.is_integer() else radius
    if color:
        values["color"] = color
    if stroke_width is not None:
        values["strokeWidth"] = stroke_width
    return ctx.make("Progress", hint, props={"value": value, "total": total}, styles=values)
