from __future__ import annotations

import re

from ...catalog.appearances import get_appearance
from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, orient_child_flex_basis, row, stack

_BACKPLATE_PADDING = 6


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


def _number(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)px\s*", value)
        if match:
            number = float(match.group(1))
            return int(number) if number.is_integer() else number
    return None


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
    # JSX Stack defaults minWidth to 0. Preserve that default explicitly:
    # A2UI containers otherwise keep their content-driven minimum width and
    # long text can push sibling content outside a fixed card slot.
    minimums = {"minWidth": node.props.get("minWidth", 0)}
    min_height = node.props.get("minHeight")
    if min_height is None and any(
        child.tag == "TextBlock" for child in node.child_elements()
    ):
        # TextBlock is internally flexible between 48vp and 64vp. Its direct
        # Stack parent must be allowed to shrink so a basis-only slot can
        # allocate that range, matching the JSX runtime's local hint.
        min_height = 0
    if min_height is not None:
        minimums["minHeight"] = min_height
    if minimums:
        styles["constraintSize"] = minimums
    margin = {}
    for key, prop_name in (
        ("top", "mt"),
        ("right", "mr"),
        ("bottom", "mb"),
        ("left", "ml"),
    ):
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
                "padding": _BACKPLATE_PADDING,
                "borderRadius": 16,
                "backgroundColor": (
                    "#1AFFFFFF" if appearance.primary == "#FFFFFFFF" else "#66FFFFFF"
                ),
                "clip": True,
            }
        )
    return styles


def _child_content_extent(
    node: JSXElement,
    ctx: ConversionContext,
    axis: str,
) -> int | float | None:
    """Resolve the definite content-box extent visible to child nodes."""
    prop = "width" if axis == "width" else "height"
    raw_extent = node.props.get(prop)
    parent_extent = (
        ctx.parent_content_width if axis == "width" else ctx.parent_content_height
    )
    if raw_extent in {None, "full"}:
        extent = parent_extent
    else:
        extent = _number(raw_extent)
    if extent is not None and node.props.get("surface") == "backplate":
        extent = max(0, extent - 2 * _BACKPLATE_PADDING)
    return extent


def _linear_stack(
    node: JSXElement,
    ctx: ConversionContext,
    *,
    styles: dict[str, object] | None = None,
) -> A2UINode:
    if node.props.get("wrap"):
        raise ValidationError(
            "Stack wrap=true cannot be represented by the supported A2UI Form subset"
        )
    direction = str(node.props.get("direction") or "column")
    is_row = direction == "row"
    source_children = node.child_elements()
    child_ctx = ctx.for_children(
        parent_content_width=_child_content_extent(node, ctx, "width"),
        parent_content_height=_child_content_extent(node, ctx, "height"),
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
        "alignItems": _align(node.props.get("align"), is_row=is_row)
        or ("top" if is_row else "start"),
        "justifyContent": _justify(node.props.get("justify")),
    }
    resolved_layout_styles: dict[str, object] = {}
    for key, value in layout_styles.items():
        if value is not None:
            resolved_layout_styles[key] = value
    layout_styles = resolved_layout_styles
    if is_row:
        return row(
            ctx,
            "stack_row",
            children,
            gap=node.props.get("gap", 0),
            styles=layout_styles,
        )
    return column(
        ctx,
        "stack_column",
        children,
        gap=node.props.get("gap", 0),
        styles=layout_styles,
    )


def _absolute_extent(node: JSXElement, axis: str, parent_extent: int | float) -> object | None:
    explicit = _dimension(node.props.get("width" if axis == "x" else "height"))
    if explicit is not None:
        return explicit
    start = node.props.get("left" if axis == "x" else "top")
    end = node.props.get("right" if axis == "x" else "bottom")
    start_number = _number(start)
    end_number = _number(end)
    if start_number is not None and end_number is not None:
        if start_number == 0 and end_number == 0:
            return "matchParent"
        return max(0, parent_extent - start_number - end_number)
    return None


def _absolute_anchor(node: JSXElement) -> str:
    vertical = (
        "bottom"
        if node.props.get("bottom") is not None and node.props.get("top") is None
        else "top"
    )
    horizontal = (
        "end" if node.props.get("right") is not None and node.props.get("left") is None else "start"
    )
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
            if value in {None, "matchParent"} and extent is None:
                # Preflight does not carry layout context. The converter makes
                # the definite-parent check once the real parent is known.
                continue
            try:
                _relative_extent(value, name, extent)
            except ValidationError as exc:
                errors.append(str(exc))
    return list(dict.fromkeys(errors))


def _absolute_child(
    node: JSXElement,
    ctx: ConversionContext,
    *,
    parent_width: int | float,
    parent_height: int | float,
) -> A2UINode:
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
    child_width = parent_width if width == "matchParent" else _number(width)
    child_height = parent_height if height == "matchParent" else _number(height)
    content = _linear_stack(
        node,
        ctx.for_children(
            parent_content_width=child_width,
            parent_content_height=child_height,
        ),
        styles=child_styles,
    )
    content.styles["layoutWeight"] = 0
    return stack(
        ctx,
        "stack_anchor",
        [content],
        align=_absolute_anchor(node),
        styles={"width": "matchParent", "height": "matchParent", "layoutWeight": 0},
    )


def _relative_stack(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    source_children = node.child_elements()
    if not any(child.props.get("position") == "absolute" for child in source_children):
        return _linear_stack(node, ctx)
    width = _dimension(node.props.get("width"))
    height = _dimension(node.props.get("height"))
    parent_width = _relative_extent(width, "width", ctx.parent_content_width)
    parent_height = _relative_extent(height, "height", ctx.parent_content_height)
    content_width = max(
        0,
        parent_width
        - (2 * _BACKPLATE_PADDING if node.props.get("surface") == "backplate" else 0),
    )
    content_height = max(
        0,
        parent_height
        - (2 * _BACKPLATE_PADDING if node.props.get("surface") == "backplate" else 0),
    )
    child_ctx = ctx.for_children(
        parent_content_width=content_width,
        parent_content_height=content_height,
        enters_backplate=node.props.get("surface") == "backplate",
    )
    children: list[A2UINode] = []
    flow_children = [
        child for child in source_children if child.props.get("position") != "absolute"
    ]
    if flow_children:
        # CSS permits normal-flow and absolutely positioned children in the
        # same relative container. A2UI Stack is overlay-only, so lower the
        # normal-flow children into one full-size Row/Column layer first.
        flow_props: dict[str, object] = {}
        for name in ("direction", "gap", "align", "justify", "wrap"):
            if name in node.props:
                flow_props[name] = node.props.get(name)
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
        if node.props.get("surface") == "backplate":
            # A relative backplate needs two coordinate spaces. Normal-flow
            # content is inset by the runtime's padding, while absolute CSS
            # offsets are measured from the backplate's padding box. Keep the
            # inset on this flow layer so the absolute anchors below can use
            # the full outer extent without adding the padding a second time.
            flow.styles["padding"] = _BACKPLATE_PADDING
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
    if node.props.get("surface") == "backplate":
        # A2UI Stack padding also insets overlay children. Leaving it on this
        # node would turn JSX left={12} into an effective 18vp offset and
        # bottom={6} into 12vp. Normal-flow padding is carried by `flow` above.
        styles.pop("padding", None)
    styles.setdefault("width", "matchParent")
    if node.props.get("flex") != 1:
        styles.setdefault("height", "matchParent")
    return stack(ctx, "stack_overlay", children, align="topStart", styles=styles)


def relative_stack_child_errors(node: JSXElement) -> list[str]:
    """Compatibility hook retained for callers; mixed flow/absolute is valid."""
    return []


def _relative_extent(
    value: object,
    name: str,
    parent_extent: int | float | None,
) -> int | float:
    if value in {None, "matchParent"}:
        if parent_extent is None:
            raise ValidationError(
                f"relative Stack {name}='full' requires a definite parent {name}"
            )
        return parent_extent
    number = _number(value)
    if number is not None and number >= 0:
        return number
    raise ValidationError(f"relative Stack {name} must be a non-negative number or 'full'")


def convert_flex_stack(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_stack_conversion_errors(
        node,
        card_width=ctx.parent_content_width,
        card_height=ctx.parent_content_height,
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
