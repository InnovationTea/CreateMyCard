from __future__ import annotations

from ...catalog.bindings import data_model_expression_reference
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column
from ..base.text import text
from ..common import palette


def _secondary_visibility(content: object) -> str | None:
    if isinstance(content, dict) and "path" in content:
        reference = data_model_expression_reference(content["path"])
        # String coercion keeps numeric zero visible while empty text occupies
        # no line. Keep the binding so later data updates can restore the line.
        return f"{{{{ '' + {reference} ? 'visible' : 'none' }}}}"
    if content == "":
        return "none"
    # Multi-ID expressions contain a separator; Boolean maps have nonempty
    # labels. Neither can resolve to an empty line under the component contract.
    return None


def convert_emphasis_text(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    main = text(
        ctx,
        "emphasis_main",
        ctx.prop(node, "mainText"),
        styles={
            "width": None if ctx.intrinsic_width else "matchParent",
            "constraintSize": {"minWidth": 0, "minHeight": 20},
            "fontSize": 20,
            "fontWeight": 700,
            "fontColor": palette(ctx).primary,
            "flexShrink": 1,
        },
    )
    secondary = None
    if node.props.get("secondaryText") is not None:
        secondary_content = ctx.prop(node, "secondaryText")
        secondary = text(
            ctx,
            "emphasis_secondary",
            secondary_content,
            styles={
                "width": None if ctx.intrinsic_width else "matchParent",
                "constraintSize": {"minWidth": 0, "minHeight": 16},
                "fontSize": 12,
                "fontWeight": 400,
                "fontColor": palette(ctx).secondary,
                "flexShrink": 1,
                "visibility": _secondary_visibility(secondary_content),
            },
        )
        # JSX retains the 2vp gap next to an empty (zero-height) paragraph.
        # A hidden A2UI child does not participate in itemMargin, so put that
        # spacing on the main line and preserve it across binding updates.
        main.styles["margin"] = {"bottom": 2}
    return column(
        ctx,
        "emphasis_text",
        [main, secondary],
        gap=0,
        styles={
            "constraintSize": {"minWidth": 0},
            "flexShrink": 1,
            "alignItems": "start",
        },
    )
