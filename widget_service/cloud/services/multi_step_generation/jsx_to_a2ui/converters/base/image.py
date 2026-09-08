from __future__ import annotations

from typing import Any

from ...catalog.assets import asset_url
from ...ir.a2ui_nodes import A2UINode, ConversionContext


def image(
    ctx: ConversionContext,
    hint: str,
    src: str,
    *,
    styles: dict[str, Any] | None = None,
    fill_color: str | None = None,
    accessibility: dict[str, Any] | None = None,
) -> A2UINode:
    props: dict[str, Any] = {"src": asset_url(src)}
    values = dict(styles or {})
    if fill_color:
        values["fillColor"] = fill_color
    if accessibility:
        props["accessibility"] = accessibility
    return ctx.make("Image", hint, props=props, styles=values)
