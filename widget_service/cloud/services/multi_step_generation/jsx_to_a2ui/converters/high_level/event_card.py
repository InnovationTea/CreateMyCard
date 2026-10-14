from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row, stack
from ..base.text import text
from ..common import palette


def collect_event_card_conversion_errors(node: JSXElement) -> list[str]:
    items = node.props.get("items")
    if items is None:
        errors: list[str] = []
        if "title" not in node.props:
            errors.append("<EventCard> legacy single-event form requires title")
        if "time" not in node.props:
            errors.append("<EventCard> legacy single-event form requires time")
        return errors
    errors = []
    if any(name in node.props for name in ("title", "time", "location", "dataIds")):
        errors.append(
            "<EventCard> items cannot be combined with top-level title, time, location, or dataIds"
        )
    if not isinstance(items, list) or not 1 <= len(items) <= 2:
        return errors + ["<EventCard> items must contain one or two schedules"]
    allowed = {"title", "time", "location", "dataIds", "dataValueMaps"}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"<EventCard> items[{index}] must be an object")
            continue
        missing = {"title", "time"} - set(item)
        if missing:
            errors.append(
                f"<EventCard> items[{index}] is missing required fields: "
                + ", ".join(sorted(missing))
            )
        unknown = set(item) - allowed
        if unknown:
            errors.append(
                f"<EventCard> items[{index}] has unsupported fields: "
                + ", ".join(sorted(unknown))
            )
    return errors


def _convert_event(
    node: JSXElement,
    ctx: ConversionContext,
    item: dict | None,
    index: int | None,
) -> A2UINode:
    current_palette = palette(ctx)
    owner = node.props if item is None else item
    has_location = owner.get("location") is not None
    compact = node.props.get("density") == "compact"
    event_height = 32 if compact else 50 if has_location else 34
    rail_top = 17 if compact else 18
    # Native layout constrains children of a zero-height Stack even when
    # clip is false. Use a positive rail bounded by the minimum event height.
    # This fallback deliberately does not extend with a two-line title:
    # matchParent would reintroduce the intrinsic-height sizing cycle.
    rail_height = event_height - rail_top
    prefix = "event" if index is None else f"event_{index}"

    def value(name: str):
        if item is None:
            return ctx.prop(node, name)
        return ctx.item_prop(node.tag, item, index or 0, name)

    dot = stack(
        ctx,
        f"{prefix}_dot",
        [],
        styles={
            "width": 8,
            "height": 8,
            "borderRadius": 4,
            "borderWidth": 1.5,
            "borderColor": current_palette.primary,
            "flexShrink": 0,
            "margin": {"top": 4 if compact else 5},
        },
    )
    line = ctx.make(
        "Divider",
        f"{prefix}_line",
        styles={
            "vertical": True,
            "strokeWidth": 1,
            "color": current_palette.secondary,
            "width": 1,
            "height": rail_height,
            "flexShrink": 0,
            "layoutWeight": 0,
        },
    )
    rail = stack(
        ctx,
        f"{prefix}_rail",
        [line],
        align="top",
        styles={
            "width": 8,
            "height": rail_height,
            "margin": {"top": rail_top},
            "clip": True,
            "flexShrink": 0,
        },
    )
    bounded_text = {"width": "matchParent", "constraintSize": {"minWidth": 0}}
    title_styles = {
        **bounded_text,
        "constraintSize": {"minWidth": 0, "minHeight": 16 if compact else 18},
        "fontSize": 12 if compact else 14,
        "fontWeight": 500,
        "fontColor": current_palette.primary,
        "maxLines": 1 if compact else 2,
        "textOverflow": "ellipsis",
        "flexShrink": 0,
    }
    if compact:
        title_styles["height"] = 16
    title = text(
        ctx,
        f"{prefix}_title",
        value("title"),
        styles=title_styles,
    )
    time_styles = {
        "height": 14 if compact else 16,
        "fontSize": 10 if compact else 12,
        "fontWeight": 400,
        "fontColor": current_palette.secondary,
        "maxLines": 1,
        "textOverflow": "ellipsis",
        "flexShrink": 0,
        "constraintSize": {"minWidth": 0},
    }
    if not compact:
        time_styles["width"] = "matchParent"
    time = text(
        ctx,
        f"{prefix}_time",
        value("time"),
        styles=time_styles,
    )
    location = None
    if has_location:
        location_styles = {
            "height": 14 if compact else 16,
            "fontSize": 10 if compact else 12,
            "fontWeight": 400,
            "fontColor": current_palette.secondary,
            "maxLines": 1,
            "textOverflow": "ellipsis",
            "constraintSize": {"minWidth": 0},
        }
        if compact:
            location_styles["layoutWeight"] = 1
        else:
            location_styles["width"] = "matchParent"
        location = text(
            ctx,
            f"{prefix}_location",
            value("location"),
            styles=location_styles,
        )
    if compact:
        detail_children = [time]
        if location is not None:
            detail_children.extend(
                [
                    text(
                        ctx,
                        f"{prefix}_meta_separator",
                        "｜",
                        styles={
                            "height": 14,
                            "fontSize": 10,
                            "fontWeight": 400,
                            "fontColor": current_palette.secondary,
                            "flexShrink": 0,
                        },
                    ),
                    location,
                ]
            )
        details = row(
            ctx,
            f"{prefix}_details",
            detail_children,
            gap=4,
            styles={
                "width": "matchParent",
                "height": 14,
                "flexShrink": 0,
                "constraintSize": {"minWidth": 0},
                "alignItems": "center",
            },
        )
    else:
        details = column(
            ctx,
            f"{prefix}_details",
            [time, location],
            gap=0,
            styles={
                "width": "matchParent",
                "flexShrink": 0,
                "constraintSize": {"minWidth": 0},
                "alignItems": "start",
            },
        )
    body = column(
        ctx,
        f"{prefix}_content",
        [title, details],
        gap=2 if compact else 0,
        styles={
            # Text can grow beyond the bounded decorative rail.
            "width": "100%",
            "padding": {"left": 15},
            "layoutWeight": 0,
            "flexShrink": 0,
            "constraintSize": {"minWidth": 0},
            "alignItems": "start",
        },
    )
    constraint_size = {
        "minWidth": 0,
        "minHeight": event_height,
    }
    if ctx.card_size != "2x4":
        constraint_size["maxWidth"] = 116
    return stack(
        ctx,
        "event_card" if index is None else f"{prefix}_item",
        [body, rail, dot],
        align="topStart",
        styles={
            "width": "matchParent",
            "height": "wrapContent",
            "clip": True,
            "flexShrink": 1,
            "constraintSize": constraint_size,
        },
    )


def convert_event_card(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_event_card_conversion_errors(node)
    if errors:
        from ...exceptions import ValidationError

        raise ValidationError(errors[0])
    items = node.props.get("items")
    if not isinstance(items, list):
        return _convert_event(node, ctx, None, None)
    events = [_convert_event(node, ctx, item, index) for index, item in enumerate(items)]
    if len(events) == 1:
        events[0].id = ctx.allocator.next("event_card")
        return events[0]
    compact = node.props.get("density") == "compact"
    minimum_height = sum(
        32 if compact else 50 if item.get("location") is not None else 34
        for item in items
    ) + 4
    constraint_size = {"minWidth": 0, "minHeight": minimum_height}
    if ctx.card_size != "2x4":
        constraint_size["maxWidth"] = 116
    return column(
        ctx,
        "event_card",
        events,
        # Keep the two schedules as one natural-height component. The parent
        # slot owns vertical alignment; filling that slot here would make a
        # parent's justifyContent="end" ineffective.
        gap=4,
        styles={
            "width": "matchParent",
            "height": "wrapContent",
            "layoutWeight": 0,
            "flexShrink": 1,
            "constraintSize": constraint_size,
        },
    )
