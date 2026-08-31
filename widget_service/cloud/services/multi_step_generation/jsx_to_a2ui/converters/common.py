from __future__ import annotations

from typing import Any

from ..catalog.appearances import get_appearance
from ..exceptions import ValidationError
from ..ir.a2ui_nodes import A2UINode, ConversionContext
from ..parser.jsx_ast import JSXElement


def jsx_prop_element(node: JSXElement, name: str, *, required: bool = False) -> JSXElement | None:
    value = node.props.get(name)
    if value is None:
        if required:
            raise ValidationError(f"<{node.tag}> requires JSX slot prop {name!r}")
        return None
    if not isinstance(value, JSXElement):
        raise ValidationError(f"<{node.tag}> prop {name!r} must contain a JSX element")
    return value


def convert_slot(node: JSXElement, name: str, ctx: ConversionContext, *, required: bool = False) -> A2UINode | None:
    value = jsx_prop_element(node, name, required=required)
    return ctx.convert(value) if value is not None else None


def palette(ctx: ConversionContext):
    return get_appearance(ctx.appearance)


def accessibility(label: Any) -> None:
    # The supplied Form A2UI protocol marks accessibility as optional but does
    # not define its wire shape.  Do not invent a non-standard object that a
    # strict renderer may reject.  The source label remains available in JSX
    # and can be enabled once the target catalog publishes the exact schema.
    return None
