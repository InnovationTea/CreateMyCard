from __future__ import annotations

from typing import Any

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement


def _explicit_child_weights(children: list[A2UINode | None]) -> None:
    """Make fixed/flexible intent independent of the catalog's default."""
    for child in children:
        if child is not None:
            child.styles.setdefault("layoutWeight", 0)


def orient_child_flex_basis(
    source_children: list[JSXElement],
    converted_children: list[A2UINode],
    *,
    is_row: bool,
) -> None:
    """Lower a child's flex basis onto the actual main axis of its parent."""
    if not is_row:
        return
    for source, converted in zip(source_children, converted_children, strict=True):
        basis = source.props.get("basis")
        if basis is None:
            continue
        converted.styles["width"] = basis
        if source.props.get("height") is None and converted.styles.get("height") == basis:
            converted.styles.pop("height")


def row(
    ctx: ConversionContext,
    hint: str,
    children: list[A2UINode | None],
    *,
    gap: int | float | None = 0,
    styles: dict[str, Any] | None = None,
    props: dict[str, Any] | None = None,
) -> A2UINode:
    _explicit_child_weights(children)
    values = dict(props or {})
    # The Form catalog defaults Row.itemMargin to 16vp.  Emit zero
    # explicitly so a JSX gap={0} remains gapless after conversion.
    if gap is not None:
        values["itemMargin"] = gap
    return ctx.make("Row", hint, props=values, styles=styles, children=children)


def column(
    ctx: ConversionContext,
    hint: str,
    children: list[A2UINode | None],
    *,
    gap: int | float | None = 0,
    styles: dict[str, Any] | None = None,
    props: dict[str, Any] | None = None,
) -> A2UINode:
    _explicit_child_weights(children)
    values = dict(props or {})
    # Column.itemMargin defaults to 8vp, so omission is not equivalent to 0.
    if gap is not None:
        values["itemMargin"] = gap
    return ctx.make("Column", hint, props=values, styles=styles, children=children)


def stack(
    ctx: ConversionContext,
    hint: str,
    children: list[A2UINode | None],
    *,
    align: str = "center",
    styles: dict[str, Any] | None = None,
    props: dict[str, Any] | None = None,
) -> A2UINode:
    values = dict(styles or {})
    values.setdefault("alignContent", align)
    return ctx.make("Stack", hint, props=props, styles=values, children=children)
