from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row
from ..base.text import text
from ..common import palette


def convert_checklist_item(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    done = ctx.prop(node, "done", False)
    current_palette = palette(ctx)
    dark_surface = current_palette.primary == "#FFFFFFFF"
    # A2UI has no state-specific unselected border. Keeping the outline in
    # both states remains correct when a data-bound `done` value changes.
    checkbox_styles = {
        "width": 16,
        "height": 16,
        "shape": "circle",
        "selectedColor": "#33FFFFFF" if dark_surface else "#1A000000",
        "backgroundColor": "#33FFFFFF" if dark_surface else "#1A000000",
        "borderWidth": 1,
        "borderColor": "#66FFFFFF" if dark_surface else "#33000000",
        "flexShrink": 0,
    }
    title_value = ctx.prop(node, "title")
    checkbox = ctx.make("Checkbox", "checklist_checkbox", props={"label": "", "value": title_value, "select": done}, styles=checkbox_styles)
    bounded_text = {"width": "matchParent", "constraintSize": {"minWidth": 0}}
    title = text(ctx, "checklist_title", title_value, styles={**bounded_text, "height": 19, "fontSize": 14, "fontWeight": 700, "fontColor": current_palette.primary, "maxLines": 1, "textOverflow": "ellipsis"})
    meta = text(ctx, "checklist_meta", ctx.prop(node, "meta"), styles={**bounded_text, "height": 19, "fontSize": 14, "fontWeight": 400, "fontColor": current_palette.secondary, "maxLines": 1, "textOverflow": "ellipsis"})
    content = column(ctx, "checklist_content", [title, meta], gap=2, styles={"layoutWeight": 1, "flexShrink": 1, "constraintSize": {"minWidth": 0}, "alignItems": "start"})
    body = row(ctx, "checklist_row", [checkbox, content], gap=8, styles={"width": "matchParent", "height": 40, "alignItems": "center"})
    return row(ctx, "checklist_item", [body], styles={"width": "matchParent", "height": 48, "padding": {"left": 8, "right": 8, "top": 4, "bottom": 4}, "borderRadius": 12, "backgroundColor": "#1AFFFFFF" if dark_surface else "#0D000000", "flexShrink": 1, "constraintSize": {"minWidth": 0}, "alignItems": "center"})
