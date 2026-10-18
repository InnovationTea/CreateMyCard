from __future__ import annotations

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..common import palette
from .helpers import collect_segmented_text_conversion_errors, segmented_text


def _wrapped_fields(node: JSXElement, ctx: ConversionContext, items: list) -> A2UINode:
    rows = []
    for index in range(0, len(items), 2):
        fields = []
        for item in items[index:index + 2]:
            field_source = JSXElement(
                tag=node.tag, props={**node.props, "items": [item]}, children=[],
            )
            field = segmented_text(
                field_source, ctx, hint="secondary_body_field",
                font_size=12, line_height=16, font_color=palette(ctx).secondary,
            )
            # Let the native Row wrap whole fields before Text wraps a field
            # that is itself wider than the available row. Keep live bindings.
            field.styles.update({"width": "wrapContent", "flexShrink": 0})
            field.styles["constraintSize"] = {
                "minWidth": 0, "maxWidth": "100%", "minHeight": 16,
            }
            fields.append(field)
        rows.append(row(
            ctx, "secondary_body_row", fields, gap=4, props={"wrap": "wrap"},
            styles={
                "width": "matchParent", "height": "wrapContent",
                "flexShrink": 0, "alignItems": "top",
            },
        ))
    return column(
        ctx, "secondary_body", rows, gap=2,
        styles={
            "width": "matchParent", "height": "wrapContent", "flexShrink": 0,
            "constraintSize": {"minWidth": 0, "minHeight": 18 * len(rows) - 2},
            "alignItems": "start",
        },
    )


def convert_secondary_body(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    # Native Row.wrap cannot conditionally hide separators at line breaks or
    # share measured font sizes. The default fallback uses gaps, fixed pairs
    # and 12vp fields; JSX retains its own measured grouping/typography.
    if "body" in node.props:
        raise ValidationError(
            "SecondaryBody.body is no longer supported; "
            "use items={[{value: ...}]} and item-level dataIds.value"
        )
    errors = collect_segmented_text_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    items = node.props.get("items")
    measured = ctx.secondary_body_layouts.get(id(node))
    if measured is not None:
        # One bounded Text per actual JSX row group. Compose from original
        # fields so their data paths/maps/units remain live, never from DOM text.
        rows = []
        offset = 0
        for size in measured["rowSizes"]:
            group = JSXElement(
                tag=node.tag, props={**node.props, "items": items[offset:offset + size]},
            )
            paragraph = segmented_text(
                group, ctx, hint="secondary_body_row",
                font_size=measured["fontSize"], line_height=measured["lineHeight"],
                font_color=palette(ctx).secondary,
            )
            paragraph.styles.update({"height": "wrapContent", "flexShrink": 0})
            rows.append(paragraph)
            offset += size
        return column(ctx, "secondary_body", rows, gap=measured["rowGap"], styles={
            "width": "matchParent", "height": "wrapContent", "flexShrink": 0,
            "alignItems": "start", "constraintSize": {"minWidth": 0},
        })
    separator = node.props.get("separator", " ｜ ")
    if isinstance(items, list) and len(items) > 1 and separator.strip() in {"", "|", "｜"}:
        return _wrapped_fields(node, ctx, items)
    # Preserve explicitly requested non-pipe separators verbatim; there is no
    # native line-break callback to remove them safely in the wrapped layout.
    if isinstance(items, list) and len(items) > 2:
        rows = []
        for index in range(0, len(items), 2):
            row_node = JSXElement(
                tag=node.tag,
                props={**node.props, "items": items[index:index + 2]},
                children=[],
            )
            rows.append(
                segmented_text(
                    row_node,
                    ctx,
                    hint="secondary_body_row",
                    font_size=12,
                    line_height=16,
                    font_color=palette(ctx).secondary,
                )
            )
        return column(
            ctx,
            "secondary_body",
            rows,
            gap=2,
            styles={
                "width": "matchParent",
                "height": "wrapContent",
                "flexShrink": 0,
                "constraintSize": {"minWidth": 0, "minHeight": 16 * len(rows) + 2 * (len(rows) - 1)},
                "alignItems": "start",
            },
        )
    return segmented_text(
        node,
        ctx,
        hint="secondary_body",
        font_size=14,
        line_height=19,
        font_color=palette(ctx).secondary,
    )
