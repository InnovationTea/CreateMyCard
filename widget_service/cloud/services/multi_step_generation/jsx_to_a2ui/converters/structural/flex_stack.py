from __future__ import annotations

from ...catalog.appearances import get_appearance
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, orient_child_flex_basis, row, stack


def _align(value: str | None, *, is_row: bool) -> str | None:
    if value is None:
        return None
    if value in {"baseline", "top", "bottom"}:
        raise ValidationError(
            f"Stack.align={value!r} is not in the exact browser/A2UI "
            "intersection; use stretch, flex-start, center, or flex-end"
        )
    mapping = {
        "flex-start": "top" if is_row else "start",
        "flex-end": "bottom" if is_row else "end",
        "start": "top" if is_row else "start",
        "end": "bottom" if is_row else "end",
        "center": "center",
        "stretch": None,
    }
    return mapping.get(value, value)


def _justify(value: str | None) -> str | None:
    return {
        "flex-start": "start",
        "flex-end": "end",
        "space-between": "spaceBetween",
        "space-around": "spaceAround",
        "space-evenly": "spaceEvenly",
        "between": "spaceBetween",
    }.get(value, value)


def _dimension(value: object) -> object:
    return "matchParent" if value == "full" else value


def _box_styles(node: JSXElement, ctx: ConversionContext) -> dict[str, object]:
    styles: dict[str, object] = {}
    width = _dimension(node.props.get("width"))
    height = _dimension(node.props.get("height"))
    if width is not None:
        styles["width"] = width
    if height is not None:
        styles["height"] = height
    if node.props.get("flex") == 1:
        styles.update({"layoutWeight": 1, "flexShrink": 1})
    elif node.props.get("flex") == 0 or node.props.get("basis") is not None:
        styles.update({"layoutWeight": 0, "flexShrink": 0})
    if node.props.get("basis") is not None and height is None:
        # Generated cards use a column Card. A bare basis therefore reserves
        # vertical space; explicit width/height always wins.
        styles["height"] = node.props["basis"]
    minimums = {}
    for key, prop_name in (("minWidth", "minWidth"), ("minHeight", "minHeight")):
        value = node.props.get(prop_name)
        if value is not None:
            minimums[key] = value
    if minimums:
        styles["constraintSize"] = minimums
    margin = {}
    for key, prop_name in (("top", "mt"), ("right", "mr"), ("bottom", "mb"), ("left", "ml")):
        value = node.props.get(prop_name)
        if value is not None:
            margin[key] = value
    if margin:
        styles["margin"] = margin
    if node.props.get("alignSelf") is not None:
        raise ValidationError(
            "Stack.alignSelf is a browser-runtime-only prop and cannot be "
            "represented by the A2UI Form protocol; align the parent Stack "
            "or use an explicit layout slot"
        )
    if node.props.get("surface") == "backplate":
        appearance = get_appearance(ctx.appearance)
        styles.update(
            {
                "padding": 6,
                "borderRadius": 16,
                "backgroundColor": (
                    "#1AFFFFFF"
                    if appearance.primary == "#FFFFFFFF"
                    else "#66FFFFFF"
                ),
                "clip": True,
            }
        )
    return styles


def _child_content_height(
    node: JSXElement,
    ctx: ConversionContext,
) -> int | float | None:
    """Resolve the definite containing-block height visible to child nodes."""
    raw_height = node.props.get("height")
    if raw_height == "full":
        height = ctx.parent_content_height
    elif isinstance(raw_height, int | float) and not isinstance(raw_height, bool):
        height = raw_height
    else:
        height = None
    if height is not None and node.props.get("surface") == "backplate":
        height = max(0, height - 12)
    return height


def _linear_stack(
    node: JSXElement,
    ctx: ConversionContext,
    *,
    styles: dict[str, object] | None = None,
) -> A2UINode:
    if node.props.get("wrap"):
        raise ValidationError("Stack wrap=true cannot be represented by the supported A2UI Form subset")
    direction = str(node.props.get("direction") or "column")
    is_row = direction == "row"
    source_children = node.child_elements()
    child_ctx = ctx.for_children(
        parent_content_height=_child_content_height(node, ctx),
        enters_backplate=node.props.get("surface") == "backplate",
    )
    children = [child_ctx.convert(child) for child in source_children]
    orient_child_flex_basis(source_children, children, is_row=is_row)
    if node.props.get("align") in {None, "stretch"}:
        for child in children:
            child.styles.setdefault("height" if is_row else "width", "matchParent")
    layout_styles: dict[str, object] = {
        **_box_styles(node, ctx),
        **(styles or {}),
        "alignItems": _align(node.props.get("align"), is_row=is_row) or ("top" if is_row else "start"),
        "justifyContent": _justify(node.props.get("justify")),
    }
    layout_styles = {key: value for key, value in layout_styles.items() if value is not None}
    if is_row:
        return row(ctx, "stack_row", children, gap=node.props.get("gap", 0), styles=layout_styles)
    return column(ctx, "stack_column", children, gap=node.props.get("gap", 0), styles=layout_styles)


def _absolute_extent(node: JSXElement, axis: str, parent_extent: int) -> object | None:
    explicit = _dimension(node.props.get("width" if axis == "x" else "height"))
    if explicit is not None:
        return explicit
    start = node.props.get("left" if axis == "x" else "top")
    end = node.props.get("right" if axis == "x" else "bottom")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        if start == 0 and end == 0:
            return "matchParent"
        return max(0, parent_extent - start - end)
    return None


def _absolute_anchor(node: JSXElement) -> str:
    vertical = "bottom" if node.props.get("bottom") is not None and node.props.get("top") is None else "top"
    horizontal = "end" if node.props.get("right") is not None and node.props.get("left") is None else "start"
    return {
        ("top", "start"): "topStart",
        ("top", "end"): "topEnd",
        ("bottom", "start"): "bottomStart",
        ("bottom", "end"): "bottomEnd",
    }[(vertical, horizontal)]


def collect_stack_conversion_errors(
    node: JSXElement,
    *,
    allow_absolute: bool = False,
    card_width: int | float | None = None,
    card_height: int | float | None = None,
) -> list[str]:
    """Collect Stack inputs that the supported A2UI lowering cannot express."""
    errors: list[str] = []
    direction = str(node.props.get("direction") or "column")
    try:
        _align(node.props.get("align"), is_row=direction == "row")
    except ValidationError as exc:
        errors.append(str(exc))
    if node.props.get("alignSelf") is not None:
        errors.append(
            "Stack.alignSelf is a browser-runtime-only prop and cannot be "
            "represented by the A2UI Form protocol; align the parent Stack "
            "or use an explicit layout slot"
        )
    if node.props.get("wrap"):
        errors.append("Stack wrap=true cannot be represented by the supported A2UI Form subset")

    position = node.props.get("position")
    if position == "absolute" and not allow_absolute:
        errors.append("absolute Stack must be a direct child of a relative Stack")
    elif position not in {None, "static", "relative", "absolute"}:
        errors.append(f"unsupported Stack position {position!r}")

    if position == "relative":
        for value, name, extent in (
            (_dimension(node.props.get("width")), "width", card_width),
            (_dimension(node.props.get("height")), "height", card_height),
        ):
            try:
                _relative_extent(value, name, extent)
            except ValidationError as exc:
                errors.append(str(exc))
    return list(dict.fromkeys(errors))


def _absolute_child(node: JSXElement, ctx: ConversionContext, *, parent_width: int, parent_height: int) -> A2UINode:
    errors = collect_stack_conversion_errors(node, allow_absolute=True)
    if errors:
        raise ValidationError("; ".join(errors))
    child_styles: dict[str, object] = {}
    width = _absolute_extent(node, "x", parent_width)
    height = _absolute_extent(node, "y", parent_height)
    if width is not None:
        child_styles["width"] = width
    if height is not None:
        child_styles["height"] = height
    margin = {}
    for key in ("top", "right", "bottom", "left"):
        value = node.props.get(key)
        if value not in {None, 0}:
            margin[key] = value
    if margin:
        child_styles["margin"] = margin
    content = _linear_stack(node, ctx, styles=child_styles)
    content.styles["layoutWeight"] = 0
    return stack(
        ctx,
        "stack_anchor",
        [content],
        align=_absolute_anchor(node),
        styles={"width": "matchParent", "height": "matchParent", "layoutWeight": 0},
    )


def _relative_stack(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    width = _dimension(node.props.get("width"))
    height = _dimension(node.props.get("height"))
    # A generated card's relative layout surface is the 136x136 content area
    # of a 160vp Card with 12vp padding.
    parent_width = _relative_extent(width, "width", ctx.card_content_width)
    parent_height = _relative_extent(height, "height", ctx.card_content_height)
    child_ctx = ctx.for_children(
        parent_content_height=max(
            0,
            parent_height - (12 if node.props.get("surface") == "backplate" else 0),
        ),
        enters_backplate=node.props.get("surface") == "backplate",
    )
    children: list[A2UINode] = []
    source_children = node.child_elements()
    flow_children = [child for child in source_children if child.props.get("position") != "absolute"]
    if flow_children:
        # CSS permits normal-flow and absolutely positioned children in the
        # same relative container. A2UI Stack is overlay-only, so lower the
        # normal-flow children into one full-size Row/Column layer first.
        flow_props = {
            name: node.props[name] for name in ("direction", "gap", "align", "justify", "wrap") if name in node.props
        }
        flow_props.update({"width": "full", "height": "full"})
        flow = _linear_stack(
            JSXElement(
                tag="Stack",
                props=flow_props,
                children=list(flow_children),
                offset=node.offset,
            ),
            child_ctx,
        )
        flow.styles.update(
            {
                "width": "matchParent",
                "height": "matchParent",
                "layoutWeight": 0,
                "flexShrink": 0,
            }
        )
        children.append(flow)
    for child in source_children:
        if child.props.get("position") != "absolute":
            continue
        children.append(
            _absolute_child(
                child,
                child_ctx,
                parent_width=parent_width,
                parent_height=parent_height,
            )
        )
    styles = _box_styles(node, ctx)
    styles.setdefault("width", "matchParent")
    if node.props.get("flex") != 1:
        styles.setdefault("height", "matchParent")
    return stack(ctx, "stack_overlay", children, align="topStart", styles=styles)


def relative_stack_child_errors(node: JSXElement) -> list[str]:
    """Compatibility hook retained for callers; mixed flow/absolute is valid."""
    return []


def _relative_extent(value: object, name: str, card_extent: int | float | None) -> int:
    if value in {None, "matchParent"}:
        return int(card_extent if card_extent is not None else 136)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return int(value)
    raise ValidationError(f"relative Stack {name} must be a non-negative number or 'full'")


def convert_flex_stack(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_stack_conversion_errors(
        node,
        card_width=ctx.card_content_width,
        card_height=ctx.card_content_height,
    )
    if errors:
        raise ValidationError("; ".join(errors))
    position = node.props.get("position")
    if position == "relative":
        return _relative_stack(node, ctx)
    if position == "absolute":
        raise ValidationError("absolute Stack must be a direct child of a relative Stack")
    if position not in {None, "static"}:
        raise ValidationError(f"unsupported Stack position {position!r}")
    return _linear_stack(node, ctx)
