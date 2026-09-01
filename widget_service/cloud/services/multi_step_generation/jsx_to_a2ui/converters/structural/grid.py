from __future__ import annotations

import re

from ...exceptions import ValidationError
from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from ..base.layout import column, row

_ROW_SIZE = re.compile(r"(?P<value>\d+(?:\.\d+)?)px")
_TWO_COLUMN_TEMPLATE = re.compile(
    r"\s*(?P<fixed>\d+(?:\.\d+)?)px\s+"
    r"minmax\(0,\s*(?P<fr>\d+(?:\.\d+)?)fr\)\s*"
)


def _column_tracks(value: object) -> tuple[int, list[tuple[str, int | float]] | None]:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value, None
    if isinstance(value, str):
        match = _TWO_COLUMN_TEMPLATE.fullmatch(value)
        if match:
            fixed = float(match.group("fixed"))
            weight = float(match.group("fr"))
            return 2, [
                ("width", int(fixed) if fixed.is_integer() else fixed),
                ("weight", int(weight) if weight.is_integer() else weight),
            ]
    raise ValidationError("Grid columns must be a positive integer or '<px> minmax(0, <fr>fr)'")


def _row_heights(value: object, row_count: int) -> list[int | float | None]:
    if value is None:
        return [None] * row_count
    if not isinstance(value, str):
        raise ValidationError(
            "Grid rows must be a complete px template string, "
            "for example '54px 54px'"
        )
    tokens = value.split()
    if len(tokens) != row_count or any(_ROW_SIZE.fullmatch(token) is None for token in tokens):
        raise ValidationError(f"Grid rows must contain exactly {row_count} px sizes")
    result: list[int | float | None] = []
    for token in tokens:
        number = float(_ROW_SIZE.fullmatch(token).group("value"))  # type: ignore[union-attr]
        result.append(int(number) if number.is_integer() else number)
    return result


def _row_align(value: object) -> str:
    return {
        "flex-start": "top",
        "start": "top",
        "center": "center",
        "flex-end": "bottom",
        "end": "bottom",
        "stretch": "top",
        None: "top",
    }.get(value, str(value))


def _cell_align(value: object) -> str:
    return {
        "flex-start": "start",
        "start": "start",
        "center": "center",
        "flex-end": "end",
        "end": "end",
        "stretch": "start",
        None: "start",
    }.get(value, str(value))


def collect_grid_conversion_errors(node: JSXElement) -> list[str]:
    """Collect the Grid input errors that would make A2UI lowering fail."""
    errors: list[str] = []
    try:
        columns, _ = _column_tracks(node.props.get("columns", 2))
    except ValidationError as exc:
        errors.append(str(exc))
        return errors

    child_count = len(node.child_elements())
    row_count = (child_count + columns - 1) // columns
    try:
        _row_heights(node.props.get("rows"), row_count)
    except ValidationError as exc:
        errors.append(str(exc))
    return errors


def convert_grid(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    errors = collect_grid_conversion_errors(node)
    if errors:
        raise ValidationError("; ".join(errors))
    columns, column_tracks = _column_tracks(node.props.get("columns", 2))
    gap = node.props.get("gap", 0)
    row_gap = node.props.get("rowGap", gap)
    column_gap = node.props.get("columnGap", gap)
    source_children = node.child_elements()
    converted = [ctx.convert(child) for child in source_children]
    row_count = (len(converted) + columns - 1) // columns
    heights = _row_heights(node.props.get("rows"), row_count)
    rows: list[A2UINode] = []
    for row_index, index in enumerate(range(0, len(converted), columns)):
        cells = converted[index:index + columns]
        # A CSS Grid keeps every declared column track in an incomplete last
        # row. A2UI rows only distribute space among their actual children, so
        # without invisible structural cells a three-item, two-column Grid
        # would stretch its last item across the full row.
        cells.extend(
            column(ctx, "grid_empty_cell", [], styles={})
            for _ in range(columns - len(cells))
        )
        row_height = heights[row_index]
        justify = node.props.get("justify")
        if justify is not None:
            wrapped: list[A2UINode] = []
            for cell_index, cell in enumerate(cells):
                if justify == "stretch":
                    cell.styles.setdefault("width", "matchParent")
                track = column_tracks[cell_index] if column_tracks else None
                wrapper_styles: dict[str, object] = {"alignItems": _cell_align(justify)}
                if track and track[0] == "width":
                    wrapper_styles.update(
                        {
                            "width": track[1],
                            "layoutWeight": 0,
                            "flexShrink": 0,
                        }
                    )
                else:
                    wrapper_styles.update(
                        {
                            "layoutWeight": track[1] if track else 1,
                            "flexShrink": 1,
                        }
                    )
                if row_height is not None:
                    wrapper_styles["height"] = row_height
                wrapped.append(column(ctx, "grid_cell", [cell], styles=wrapper_styles))
            cells = wrapped
        else:
            for cell_index, cell in enumerate(cells):
                track = column_tracks[cell_index] if column_tracks else None
                if track and track[0] == "width":
                    cell.styles.setdefault("width", track[1])
                    cell.styles.setdefault("layoutWeight", 0)
                    cell.styles.setdefault("flexShrink", 0)
                else:
                    cell.styles.setdefault("layoutWeight", track[1] if track else 1)
                    cell.styles.setdefault("flexShrink", 1)
        row_styles: dict[str, object] = {
            "width": "matchParent",
            "alignItems": _row_align(node.props.get("align")),
        }
        if row_height is not None:
            row_styles["height"] = row_height
            if node.props.get("align") in {None, "stretch"}:
                for cell in cells:
                    cell.styles.setdefault("height", "matchParent")
        else:
            row_styles["layoutWeight"] = 1
            row_styles["flexShrink"] = 1
            if node.props.get("align") in {None, "stretch"}:
                for cell in cells:
                    cell.styles.setdefault("height", "matchParent")
        rows.append(row(ctx, "grid_row", cells, gap=column_gap, styles=row_styles))
    height = "matchParent" if node.props.get("height") == "full" else node.props.get("height")
    if height is None and node.props.get("basis") is not None:
        height = node.props["basis"]
    has_basis = node.props.get("basis") is not None
    width = node.props.get("width")
    styles = {
        "width": "matchParent" if width in {None, "full"} else width,
        "height": height,
        "layoutWeight": 1 if node.props.get("flex") == 1 and not has_basis else 0,
        "flexShrink": 1 if node.props.get("flex") == 1 and not has_basis else 0,
        "alignItems": "start",
    }
    # JSX Grid also defaults minWidth to 0. Emit it even when omitted so an
    # A2UI grid remains shrinkable inside a fixed card region.
    minimums: dict[str, object] = {"minWidth": node.props.get("minWidth", 0)}
    min_height = node.props.get("minHeight")
    if min_height is not None:
        minimums["minHeight"] = min_height
    if minimums:
        styles["constraintSize"] = minimums
    margin = {
        key: value
        for key, value in {"top": node.props.get("mt"), "bottom": node.props.get("mb")}.items()
        if value is not None
    }
    if margin:
        styles["margin"] = margin
    styles = {key: value for key, value in styles.items() if value is not None}
    return column(ctx, "grid", rows, gap=row_gap, styles=styles)
