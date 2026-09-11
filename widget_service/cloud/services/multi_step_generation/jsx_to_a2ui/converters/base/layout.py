from __future__ import annotations

from typing import Any

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement


def _explicit_child_weights(children: list[A2UINode | None]) -> None:
    """Make fixed/flexible intent independent of the catalog's default."""
    for child in children:
        if child is not None:
            child.styles.setdefault("layoutWeight", 0)


def _adapt_paragraph_slot_basis(source: JSXElement, converted: A2UINode) -> None:
    """Keep a basis-only paragraph slot's automatic content minimum."""
    basis = source.props.get("basis")
    if (
        source.tag != "Stack"
        or isinstance(basis, bool)
        or not isinstance(basis, (int, float))
        or basis < 0
        or source.props.get("height") is not None
        or source.props.get("minHeight") is not None
        or source.props.get("direction") not in {None, "column"}
        or source.props.get("position") not in {None, "static"}
    ):
        return
    children = source.child_elements()
    if not children or any(child.tag != "SecondaryBody" for child in children):
        return
    # CSS flex-basis does not cap min-height:auto. A wrapped paragraph can
    # enlarge this slot, whereas an A2UI height would pin it to one line.
    # Leave explicit sizes, horizontal bases and other component trees alone.
    converted.styles.pop("height", None)
    converted.styles.setdefault("constraintSize", {})["minHeight"] = basis
    converted.styles.update({"layoutWeight": 0, "flexShrink": 0})


def adapt_flex_children(
    source_children: list[JSXElement],
    converted_children: list[A2UINode],
    *,
    is_row: bool,
    fill_table_height: bool = False,
) -> None:
    """Preserve child sizing semantics along the parent's actual main axis."""
    for source, converted in zip(source_children, converted_children, strict=True):
        if source.tag == "TableText" and fill_table_height:
            converted.styles["height"] = "100%"
        if not is_row:
            # JSX wrapping paragraphs retain their content-based minimum height.
            # An explicit one-line A2UI minimum must not let their layout box
            # shrink while all lines continue painting outside it. Row children
            # still need horizontal shrinking so their text can wrap normally.
            if source.tag == "SecondaryBody":
                converted.styles["flexShrink"] = 0
            _adapt_paragraph_slot_basis(source, converted)
            continue
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
