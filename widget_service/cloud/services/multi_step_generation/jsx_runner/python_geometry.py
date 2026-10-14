"""Conservative browser-free geometry checks for Card/Stack/Grid JSX."""
from __future__ import annotations

from dataclasses import dataclass
import re

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.parser.jsx_ast import JSXElement
else:
    from jsx_to_a2ui.parser.jsx_ast import JSXElement

from .card_sizes import card_dimensions
from .workflow import (
    _BUDGET_CARD_SIZE,
    _emphasized_data_width,
    _estimated_auto_height,
    _estimated_text_width,
    _estimated_wrapped_lines,
    _flex_weight,
    _gap,
    _minimum_height,
    _minimum_width,
    _number,
    _progress_circle_single_width_estimate,
)

_MODELED_COMPONENTS = frozenset({
    "Card", "Stack", "Grid", "Icon", "AppIcon", "WeatherIcon",
    "SingleLineTitle", "DoubleLineTitle", "Badge", "EmphasizedData",
    "EmphasisText", "SecondaryBody", "DataDisplay", "InfoBlock",
    "TopTextBottomValue", "TableText", "TextBlock", "WeatherSummaryCard",
    "SecondaryBodyCard", "ProgressLine1", "ProgressLine2",
    "ProgressLine2WithData", "H_BarChart", "Gauge", "ProgressRing",
    "ProgressCircleSingle", "ProgressCircle", "NumericRatio",
    "NumericRatioStack", "ChecklistItem", "EventCard", "PillButton",
    "CircleButton", "CardButton",
})

# State axes that change a component's painted geometry in the checked-in
# runtime.  Keeping this list beside the geometry model makes the coverage
# explicit and gives tests one place to assert every runtime branch.  An empty
# tuple means that the component currently has one geometry state.
COMPONENT_STATE_COVERAGE: dict[str, tuple[str, ...]] = {
    "Card": ("size", "direction", "padding"),
    "Stack": ("direction", "wrap", "surface"),
    "Grid": ("columns", "rows"),
    "Icon": ("size",),
    "AppIcon": (), "WeatherIcon": (), "SingleLineTitle": (),
    "DoubleLineTitle": (), "Badge": ("value",),
    "EmphasizedData": ("items", "value", "unit"),
    "EmphasisText": ("secondaryText",),
    "SecondaryBody": ("items", "separator"),
    "DataDisplay": ("contentWidth",),
    "InfoBlock": ("cardSize", "visual", "unit"),
    "TopTextBottomValue": ("parentWidth", "items"),
    "TableText": ("items", "containerWidth"),
    "TextBlock": ("items", "containerWidth"),
    "WeatherSummaryCard": (), "SecondaryBodyCard": ("lines", "value"),
    "ProgressLine1": (), "ProgressLine2": ("items", "value", "unit"),
    "ProgressLine2WithData": ("items", "value", "unit"),
    "H_BarChart": ("items",), "Gauge": (), "ProgressRing": ("size",),
    "ProgressCircleSingle": ("size", "secondaryLabel"),
    "ProgressCircle": ("size",), "NumericRatio": (),
    "NumericRatioStack": ("direction", "items"), "ChecklistItem": (),
    "EventCard": ("density", "items", "location", "parentHeight"),
    "PillButton": ("appearance", "cardSize", "backplate"),
    "CircleButton": ("appearance",), "CardButton": (),
}


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class ComponentBox:
    tag: str
    path: str
    box: Box
    slot: Box
    node: JSXElement
    clipping_box: Box | None = None


def _vp(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else f"{number:.1f}"


def _padding(node: JSXElement) -> tuple[float, float, float, float]:
    if node.tag == "Card":
        default = 12
    elif node.tag == "Stack" and node.props.get("surface") == "backplate":
        default = 8 if _BUDGET_CARD_SIZE.get() == "2x4" else 6
    else:
        default = 0
    value = node.props.get("padding", default)
    if isinstance(value, dict):
        return tuple(float(_number(value.get(side)) or 0) for side in ("top", "right", "bottom", "left"))
    amount = float(_number(value) or 0)
    return amount, amount, amount, amount


def _painted_width(node: JSXElement, allocated: float, inside_backplate: bool) -> float:
    if node.tag == "Gauge":
        return 94
    if node.tag == "ProgressLine1":
        return 116
    if node.tag in {"AppIcon", "WeatherIcon"}:
        return 20
    if node.tag in {"WeatherSummaryCard", "SecondaryBodyCard"}:
        return 150
    if node.tag == "ProgressRing":
        return _number(node.props.get("size")) or 44
    if node.tag == "CircleButton":
        return 36 if node.props.get("appearance") == "card" else 40
    if node.tag == "PillButton":
        if node.props.get("appearance") != "card":
            return 136
        return (116 if inside_backplate else 132) if _BUDGET_CARD_SIZE.get() == "2x4" else 126
    if node.tag == "InfoBlock":
        return 132 if _BUDGET_CARD_SIZE.get() == "2x4" else 134
    if node.tag == "ProgressCircleSingle":
        return max(allocated, _progress_circle_single_width_estimate(node))
    if node.tag == "EmphasizedData":
        return min(allocated, _emphasized_data_width(node))
    return allocated


def _natural_height(node: JSXElement, width: float, parent_height: float | None = None) -> float:
    height = max(_minimum_height(node), _estimated_auto_height(node, max(1, width)))
    if node.tag == "EventCard":
        items = node.props.get("items")
        # The runtime measures its immediate parent before selecting the
        # preferred 8px gap.  The static minimum uses the 4px compact gap.
        if isinstance(items, list) and len(items) > 1:
            if parent_height is not None and parent_height >= height + 4:
                height += 4
    return height


def _internal_vertical_clips(node: JSXElement, width: float) -> list[tuple[str, float]]:
    """Estimate text hidden by runtime line clamps inside a component."""
    clips: list[tuple[str, float]] = []
    if node.tag == "DoubleLineTitle":
        lines = _estimated_wrapped_lines(node.props.get("secondaryInfo"), 12, width, 500)
        if lines > 2:
            clips.append(("secondaryInfo", (lines - 2) * 18))
    elif node.tag == "TableText":
        items = node.props.get("items")
        if isinstance(items, list) and len(items) >= 3 and width <= 120:
            for index, value in enumerate(items):
                if not isinstance(value, dict):
                    continue
                label_width = _estimated_text_width(value.get("label"), 10, 500)
                parameter_width = max(1, width - label_width - 8)
                lines = _estimated_wrapped_lines(
                    value.get("parameter"), 10, parameter_width, 500,
                )
                if lines > 2:
                    clips.append((f"items[{index}].parameter", (lines - 2) * 12))
    elif node.tag == "EventCard" and node.props.get("density") != "compact":
        items = node.props.get("items")
        schedules = items if isinstance(items, list) else [node.props]
        content_width = max(1, width - 15)
        for index, value in enumerate(schedules[:2]):
            if not isinstance(value, dict):
                continue
            lines = _estimated_wrapped_lines(
                value.get("title"), 14, content_width, 700,
                overflow_wrap="break-word",
            )
            if lines > 2:
                clips.append((f"items[{index}].title", (lines - 2) * 20))
    return clips


def _child_width(node: JSXElement, available: float, inside_backplate: bool = False) -> float:
    declared = node.props.get("width")
    if declared == "full":
        return available
    numeric = _number(declared)
    if numeric is not None:
        return float(numeric)
    # Intrinsic inline widths matter in a row: assigning its full parent
    # width to a fit-content title or badge invents a collision next door.
    if node.tag == "SingleLineTitle":
        return min(available, _estimated_text_width(node.props.get("title"), 12))
    if node.tag == "Badge":
        return _estimated_text_width(node.props.get("value"), 10) + 12
    if node.tag == "CircleButton":
        return 36 if node.props.get("appearance") == "card" else 40
    if node.tag == "Gauge":
        return 94
    if node.tag == "ProgressLine1":
        return 116
    if node.tag in {"AppIcon", "WeatherIcon"}:
        return 20
    if node.tag in {"WeatherSummaryCard", "SecondaryBodyCard"}:
        return 150
    if node.tag == "ProgressRing":
        return _number(node.props.get("size")) or 44
    if node.tag == "PillButton":
        if node.props.get("appearance") != "card":
            return 136
        return (116 if inside_backplate else 132) if _BUDGET_CARD_SIZE.get() == "2x4" else 126
    if node.tag == "InfoBlock":
        return 132 if _BUDGET_CARD_SIZE.get() == "2x4" else 134
    return max(_minimum_width(node, inside_backplate=inside_backplate), available)


def _dimension(value: object, available: float) -> float | None:
    if value == "full":
        return available
    numeric = _number(value)
    return float(numeric) if numeric is not None else None


def _main_margins(node: JSXElement, is_row: bool) -> tuple[float, float]:
    names = ("ml", "mr") if is_row else ("mt", "mb")
    return tuple(float(_number(node.props.get(name)) or 0) for name in names)


def _cross_margins(node: JSXElement, is_row: bool) -> tuple[float, float]:
    names = ("mt", "mb") if is_row else ("ml", "mr")
    return tuple(float(_number(node.props.get(name)) or 0) for name in names)


def _main_base(
    node: JSXElement,
    available_main: float,
    available_cross: float,
    is_row: bool,
    inside_backplate: bool,
) -> float:
    basis = _number(node.props.get("basis"))
    if basis is not None:
        base = float(basis)
    elif is_row:
        base = _child_width(node, available_main, inside_backplate)
    else:
        explicit = _dimension(node.props.get("height"), available_main)
        base = explicit if explicit is not None else _natural_height(
            node, max(1, available_cross), available_main,
        )
    minimum = (
        _minimum_width(node, inside_backplate=inside_backplate)
        if is_row else (_number(node.props.get("minHeight")) or 0)
    )
    return max(float(minimum), base)


def _cross_size(
    node: JSXElement,
    available: float,
    main_size: float,
    is_row: bool,
    alignment: str,
    inside_backplate: bool,
) -> float:
    if is_row:
        explicit = _dimension(node.props.get("height"), available)
        minimum = _number(node.props.get("minHeight")) or 0
        natural = _natural_height(node, max(1, main_size), available)
    else:
        explicit = _dimension(node.props.get("width"), available)
        minimum = _minimum_width(node, inside_backplate=inside_backplate)
        natural = _child_width(node, available, inside_backplate)
    before, after = _cross_margins(node, is_row)
    if explicit is not None:
        return max(float(minimum), explicit)
    if alignment == "stretch":
        return max(float(minimum), available - before - after)
    return max(float(minimum), min(available - before - after, natural))


def _align_offset(alignment: object, free: float) -> float:
    if alignment in {"flex-end", "end"}:
        return free
    if alignment == "center":
        return free / 2
    return 0


def _justify_values(justify: object, free: float, count: int) -> tuple[float, float]:
    """Return leading free space and extra space added after each item."""
    if justify in {"flex-end", "end"}:
        return free, 0
    if justify == "center":
        return free / 2, 0
    if free <= 0 and justify in {"space-between", "between", "space-around", "space-evenly"}:
        return 0, 0
    if justify in {"space-between", "between"} and count > 1:
        return 0, free / (count - 1)
    if justify == "space-around" and count:
        between = free / count
        return between / 2, between
    if justify == "space-evenly" and count:
        between = free / (count + 1)
        return between, between
    return 0, 0


def _grid_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(value.strip()):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char.isspace() and depth == 0:
            if value.strip()[start:index].strip():
                tokens.append(value.strip()[start:index].strip())
            start = index + 1
    tail = value.strip()[start:].strip()
    if tail:
        tokens.append(tail)
    return tokens


_REPEAT_TRACK = re.compile(r"repeat\(\s*(\d+)\s*,\s*(.+)\s*\)")
_FR_TRACK = re.compile(r"(\d+(?:\.\d+)?)fr")
_MINMAX_FR_TRACK = re.compile(r"minmax\(\s*0(?:px)?\s*,\s*(\d+(?:\.\d+)?)fr\s*\)")


def _track_specs(value: object, numeric_default: int | None = None) -> list[str] | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return ["1fr"] * value
    if value is None and numeric_default:
        return ["1fr"] * numeric_default
    if not isinstance(value, str):
        return None
    text = value.strip()
    repeated = _REPEAT_TRACK.fullmatch(text)
    if repeated:
        inner = repeated.group(2).strip()
        if _track_specs(inner) is None:
            return None
        return [inner] * int(repeated.group(1))
    tokens = _grid_tokens(text)
    if tokens and all(
        re.fullmatch(r"\d+(?:\.\d+)?px", token)
        or _FR_TRACK.fullmatch(token)
        or _MINMAX_FR_TRACK.fullmatch(token)
        for token in tokens
    ):
        return tokens
    return None


def _track_sizes(specs: list[str], available: float, gap: float) -> list[float]:
    space = available - gap * max(0, len(specs) - 1)
    fixed = sum(float(spec[:-2]) for spec in specs if spec.endswith("px"))
    weights: list[float] = []
    for spec in specs:
        match = _FR_TRACK.fullmatch(spec) or _MINMAX_FR_TRACK.fullmatch(spec)
        weights.append(float(match.group(1)) if match else 0)
    remaining = max(0, space - fixed)
    total = sum(weights)
    return [
        float(spec[:-2]) if spec.endswith("px") else remaining * weight / total
        for spec, weight in zip(specs, weights)
    ]


def _absolute_box(
    node: JSXElement,
    containing: Box,
    unverified: set[str],
    path: str,
    inside_backplate: bool,
) -> Box:
    left = _number(node.props.get("left"))
    right = _number(node.props.get("right"))
    top = _number(node.props.get("top"))
    bottom = _number(node.props.get("bottom"))
    mt = float(_number(node.props.get("mt")) or 0)
    mb = float(_number(node.props.get("mb")) or 0)
    ml = float(_number(node.props.get("ml")) or 0)
    mr = float(_number(node.props.get("mr")) or 0)
    width = _dimension(node.props.get("width"), containing.width)
    if width is None and left is not None and right is not None:
        width = max(0, containing.width - left - right - ml - mr)
    if width is None:
        width = _minimum_width(node, inside_backplate=inside_backplate)
        if width <= 0:
            unverified.add(f"{path}: 绝对定位组件缺少可静态确定的 width")
    width = max(width, _number(node.props.get("minWidth")) or 0)
    height = _dimension(node.props.get("height"), containing.height)
    if height is None and top is not None and bottom is not None:
        height = max(0, containing.height - top - bottom - mt - mb)
    if height is None:
        height = _natural_height(node, max(1, width), containing.height)
    height = max(height, _number(node.props.get("minHeight")) or 0)
    if left is not None:
        x = containing.x + left + ml
    elif right is not None:
        x = containing.right - right - mr - width
    else:
        x = containing.x
        unverified.add(f"{path}: 绝对定位组件缺少 left/right，静态位置无法证明")
    if top is not None:
        y = containing.y + top + mt
    elif bottom is not None:
        y = containing.bottom - bottom - mb - height
    else:
        y = containing.y
        unverified.add(f"{path}: 绝对定位组件缺少 top/bottom，静态位置无法证明")
    return Box(x, y, width, height)


def _place(
    node: JSXElement,
    box: Box,
    path: str,
    components: list[ComponentBox],
    slots: dict[str, Box],
    unverified: set[str],
    inside_backplate: bool = False,
    positioning_box: Box | None = None,
    clipping_box: Box | None = None,
) -> None:
    if node.props.get("position") == "relative":
        left_offset = _number(node.props.get("left"))
        right_offset = _number(node.props.get("right"))
        top_offset = _number(node.props.get("top"))
        bottom_offset = _number(node.props.get("bottom"))
        dx = left_offset if left_offset is not None else -(right_offset or 0)
        dy = top_offset if top_offset is not None else -(bottom_offset or 0)
        box = Box(box.x + dx, box.y + dy, box.width, box.height)
    slots[path] = box
    if node.tag not in _MODELED_COMPONENTS:
        unverified.add(f"{path}: 组件 {node.tag} 没有 Python 尺寸规则")
        return
    if node.tag == "Icon" and _number(node.props.get("size")) is None:
        unverified.add(f"{path}: Icon 未指定尺寸，依赖图片资源的固有尺寸")
    if node.props.get("style"):
        unverified.add(f"{path}: 自定义 style 可能覆盖布局属性")
    if node.tag == "Grid":
        children = node.child_elements()
        grid_alignments = {None, "start", "flex-start", "center", "end", "flex-end", "stretch"}
        if node.props.get("align") not in grid_alignments:
            unverified.add(f"{path}: 未支持的 Grid.align={node.props.get('align')!r}")
        if node.props.get("justify") not in grid_alignments:
            unverified.add(f"{path}: 未支持的 Grid.justify={node.props.get('justify')!r}")
        column_specs = _track_specs(node.props.get("columns", 2), 2)
        if column_specs is None:
            unverified.add(f"{path}: 无法解析 Grid.columns")
            return
        columns = len(column_specs)
        rows = (len(children) + columns - 1) // columns
        column_gap = _number(node.props.get("columnGap", node.props.get("gap", 0))) or 0
        row_gap = _number(node.props.get("rowGap", node.props.get("gap", 0))) or 0
        widths = _track_sizes(column_specs, box.width, column_gap)
        row_spec = node.props.get("rows")
        row_specs = _track_specs(row_spec) if row_spec is not None else None
        if row_spec is not None and row_specs is None:
            unverified.add(f"{path}: 无法解析 Grid.rows")
            return
        if row_specs is not None and len(row_specs) != rows:
            unverified.add(f"{path}: Grid.rows 数量与内容行数不一致")
            return
        if row_specs is not None:
            heights = _track_sizes(row_specs, box.height, row_gap)
        else:
            heights = [max((_natural_height(child, widths[index % columns])
                            for index, child in enumerate(children[i:i + columns], start=i)),
                           default=0) for i in range(0, len(children), columns)]
            spare = max(0, box.height - sum(heights) - row_gap * max(0, rows - 1))
            heights = [height + spare / rows for height in heights] if rows else heights
        y = box.y
        for row in range(rows):
            for column in range(columns):
                index = row * columns + column
                if index >= len(children):
                    break
                child = children[index]
                cell = Box(box.x + sum(widths[:column]) + column * column_gap, y,
                           widths[column], heights[row])
                justify = node.props.get("justify", "stretch")
                align = child.props.get("alignSelf", node.props.get("align", "stretch"))
                if align not in grid_alignments:
                    unverified.add(
                        f"{path}/<{child.tag}>[{index + 1}]: "
                        f"未支持的 Grid 子项 alignSelf={align!r}"
                    )
                mt = float(_number(child.props.get("mt")) or 0)
                mb = float(_number(child.props.get("mb")) or 0)
                ml = float(_number(child.props.get("ml")) or 0)
                mr = float(_number(child.props.get("mr")) or 0)
                available_width = max(0, cell.width - ml - mr)
                available_height = max(0, cell.height - mt - mb)
                child_width = _cross_size(child, available_width, available_height, False,
                                          str(justify), inside_backplate)
                child_height = _cross_size(child, available_height, available_width, True,
                                           str(align), inside_backplate)
                child_box = Box(
                    cell.x + ml + _align_offset(justify, available_width - child_width),
                    cell.y + mt + _align_offset(align, available_height - child_height),
                    child_width,
                    child_height,
                )
                _place(child, child_box, f"{path}/<{child.tag}>[{index + 1}]",
                       components, slots, unverified, inside_backplate, positioning_box,
                       clipping_box)
            y += heights[row] + row_gap
        return
    if node.tag not in {"Card", "Stack"}:
        parent = slots.get(path.rsplit("/", 1)[0])
        painted_height = _natural_height(node, box.width, parent.height if parent else None)
        components.append(ComponentBox(
            node.tag, path,
            Box(box.x, box.y, _painted_width(node, box.width, inside_backplate), painted_height),
            box,
            node,
            clipping_box,
        ))
        return
    children = node.child_elements()
    inside_backplate = inside_backplate or node.props.get("surface") == "backplate"
    if node.tag == "Card" or node.props.get("surface") == "backplate":
        clipping_box = box
    if not children:
        return
    top, right, bottom, left = _padding(node)
    inner = Box(box.x + left, box.y + top,
                max(0, box.width - left - right), max(0, box.height - top - bottom))
    position = node.props.get("position")
    if position not in {None, "relative", "absolute"}:
        unverified.add(f"{path}: 未支持的 position={position!r}")
    if node.tag == "Card" or position in {"relative", "absolute"}:
        positioning_box = box
    elif positioning_box is None:
        positioning_box = box
    direction = node.props.get("direction", "column")
    if direction not in {"column", "row"}:
        unverified.add(f"{path}: 未支持的布局方向 {direction!r}")
        return
    is_row = direction == "row"
    supported_alignments = {None, "start", "flex-start", "center", "end", "flex-end", "stretch"}
    if node.props.get("align") not in supported_alignments:
        unverified.add(f"{path}: 未支持的 align={node.props.get('align')!r}")
    supported_justify = {
        None, "start", "flex-start", "center", "end", "flex-end", "space-between",
        "between", "space-around", "space-evenly",
    }
    if node.props.get("justify") not in supported_justify:
        unverified.add(f"{path}: 未支持的 justify={node.props.get('justify')!r}")
    indexed_children = list(enumerate(children, start=1))
    flow_children = [(index, child) for index, child in indexed_children
                     if child.props.get("position") != "absolute"]
    absolute_children = [(index, child) for index, child in indexed_children
                         if child.props.get("position") == "absolute"]
    length = inner.width if is_row else inner.height
    gap = _gap(node)
    wrap = bool(node.props.get("wrap"))
    cross_available = inner.height if is_row else inner.width
    entries: list[tuple[int, JSXElement, float, float]] = []
    for index, child in flow_children:
        if child.props.get("alignSelf") not in supported_alignments:
            unverified.add(
                f"{path}/<{child.tag}>[{index}]: 未支持的 alignSelf={child.props.get('alignSelf')!r}"
            )
        if child.props.get("flex") is not None and _number(child.props.get("flex")) is None:
            unverified.add(f"{path}/<{child.tag}>[{index}]: 非数值 flex 尚未建模")
        if child.props.get("basis") is not None and _number(child.props.get("basis")) is None:
            unverified.add(f"{path}/<{child.tag}>[{index}]: 非数值 basis 尚未建模")
        base = _main_base(child, length, cross_available, is_row, inside_backplate)
        before, after = _main_margins(child, is_row)
        entries.append((index, child, base, before + after))

    lines: list[list[tuple[int, JSXElement, float, float]]] = []
    for entry in entries:
        current = lines[-1] if lines else []
        needed = entry[2] + entry[3] + (gap if current else 0)
        used = sum(item[2] + item[3] for item in current) + gap * max(0, len(current) - 1)
        if wrap and current and used + needed > length + 1e-9:
            lines.append([entry])
        else:
            if not lines:
                lines.append([])
            lines[-1].append(entry)

    natural_line_crosses: list[float] = []
    for line in lines:
        natural_line_crosses.append(max((
            _cross_size(child, cross_available, base, is_row,
                        ("start" if child.props.get(
                            "alignSelf", node.props.get("align", "stretch")
                        ) == "stretch" else str(child.props.get(
                            "alignSelf", node.props.get("align", "stretch")
                        ))),
                        inside_backplate)
            + sum(_cross_margins(child, is_row))
            for _, child, base, _ in line
        ), default=0))
    if not wrap or len(lines) <= 1:
        line_crosses = [cross_available] if lines else []
    else:
        cross_gap = gap
        spare_cross = max(0, cross_available - sum(natural_line_crosses)
                          - cross_gap * max(0, len(lines) - 1))
        line_crosses = [value + spare_cross / len(lines) for value in natural_line_crosses]

    cross_cursor = inner.y if is_row else inner.x
    for line, line_cross in zip(lines, line_crosses):
        weights = [(_flex_weight(child) if child.props.get("basis") is None else 0)
                   for _, child, _, _ in line]
        base_sizes = [base if not weight else 0 for (_, _, base, _), weight in zip(line, weights)]
        fixed = sum(base_sizes) + sum(margins for _, _, _, margins in line) + gap * max(0, len(line) - 1)
        remaining = max(0, length - fixed)
        total_weight = sum(weights)
        sizes = list(base_sizes)
        if total_weight:
            for item_index, ((_, child, _, _), weight) in enumerate(zip(line, weights)):
                if not weight:
                    continue
                share = remaining * weight / total_weight
                minimum = (_minimum_width(child, inside_backplate=inside_backplate)
                           if is_row else (_number(child.props.get("minHeight")) or 0))
                sizes[item_index] = max(float(minimum), share)
        occupied = sum(sizes) + sum(margins for _, _, _, margins in line) + gap * max(0, len(line) - 1)
        free = length - occupied
        leading, extra_gap = _justify_values(node.props.get("justify", "start"), free, len(line))
        # TableText's runtime root uses height:100%. When its painted rows are
        # taller than the flex slot, the item remains at the slot start rather
        # than moving upward under flex-end.
        if not is_row and free < 0 and any(child.tag == "TableText" for _, child, _, _ in line):
            leading = 0
        cursor = (inner.x if is_row else inner.y) + leading
        for item_number, ((index, child, _, _), size) in enumerate(zip(line, sizes)):
            main_before, main_after = _main_margins(child, is_row)
            cross_before, cross_after = _cross_margins(child, is_row)
            cursor += main_before
            alignment = child.props.get("alignSelf", node.props.get("align", "stretch"))
            child_cross = _cross_size(child, line_cross, size, is_row,
                                      str(alignment), inside_backplate)
            cross_free = line_cross - child_cross - cross_before - cross_after
            cross_pos = cross_cursor + cross_before + _align_offset(alignment, cross_free)
            child_box = (Box(cursor, cross_pos, size, child_cross) if is_row
                         else Box(cross_pos, cursor, child_cross, size))
            _place(child, child_box, f"{path}/<{child.tag}>[{index}]",
                   components, slots, unverified, inside_backplate, positioning_box,
                   clipping_box)
            cursor += size + main_after + gap
            if item_number < len(line) - 1:
                cursor += extra_gap
        cross_cursor += line_cross + (gap if wrap else 0)

    for index, child in absolute_children:
        absolute_path = f"{path}/<{child.tag}>[{index}]"
        containing = positioning_box or box
        child_box = _absolute_box(child, containing, unverified, absolute_path, inside_backplate)
        _place(child, child_box, absolute_path, components, slots, unverified,
               inside_backplate, containing, clipping_box)


def validate_geometry(root: JSXElement) -> list[dict[str, str]]:
    """Check estimated painted boxes; mark unsupported geometry explicitly."""
    dimensions = card_dimensions(root.props.get("size"))
    if dimensions is None or root.props.get("size") not in {"2x2", "2x4"}:
        return [{"severity": "error", "code": "python-layout-unverified",
                 "message": "当前几何检查只覆盖 2x2/2x4 Card/Stack；其他尺寸仍执行预算校验"}]
    card = Box(0, 0, float(dimensions[0]), float(dimensions[1]))
    components: list[ComponentBox] = []
    slots: dict[str, Box] = {}
    unverified: set[str] = set()
    token = _BUDGET_CARD_SIZE.set(root.props.get("size"))
    try:
        _place(root, card, "<Card>", components, slots, unverified)
    finally:
        _BUDGET_CARD_SIZE.reset(token)
    findings: list[dict[str, str]] = []
    top, right, bottom, left = _padding(root)
    safe = Box(left, top, card.width - left - right, card.height - top - bottom)

    def add(code: str, message: str, *, uncertain: bool = False) -> None:
        findings.append({"severity": "warning" if uncertain else "error", "code": code,
                         "message": message})

    for item in components:
        box = item.box
        horizontal_outside = max(-box.x, box.right - card.right)
        vertical_outside = max(-box.y, box.bottom - card.bottom)
        outside = max(horizontal_outside, vertical_outside)
        if outside > 1:
            add("python-layout-overflow-box",
                f"{item.path} 的预计内容超出 Card 约 {_vp(outside)}vp",
                # Retain the existing tolerance only for a small, purely
                # vertical font/rounding estimate. A proven horizontal extent
                # beyond the Card must remain blocking.
                uncertain=horizontal_outside <= 1 and vertical_outside <= 4)
            continue
        shortfall = max(safe.x - box.x, safe.y - box.y,
                        box.right - safe.right, box.bottom - safe.bottom)
        if shortfall > 2:
            add("python-layout-edge-spacing",
                f"{item.path} 的预计内容侵入 Card 安全边距约 {_vp(shortfall)}vp")
        horizontal_slot_excess = max(
            item.slot.x - box.x, box.right - item.slot.right,
        )
        vertical_slot_excess = max(
            item.slot.y - box.y, box.bottom - item.slot.bottom,
        )
        slot_excess = max(horizontal_slot_excess, vertical_slot_excess)
        if slot_excess > 1.5:
            blocking = (
                horizontal_slot_excess > 1.5 and item.tag == "TopTextBottomValue"
            ) or (
                vertical_slot_excess > 6
                and not (item.tag == "TableText" and vertical_slot_excess <= 8)
            )
            add(
                "python-layout-semantic-content-overflow",
                f"{item.path} 的预计内部内容超出组件槽约 {_vp(slot_excess)}vp",
                uncertain=not blocking,
            )
        for field, clipped in _internal_vertical_clips(item.node, item.slot.width):
            add(
                "python-layout-vertical-clipping",
                f"{item.path}.{field} 预计超过运行时最多两行的内部区域，"
                f"纵向将裁剪约 {_vp(clipped)}vp",
            )
        if item.tag in {"PillButton", "CircleButton", "CardButton"} and item.clipping_box:
            clipped = max(
                item.clipping_box.x - box.x,
                item.clipping_box.y - box.y,
                box.right - item.clipping_box.right,
                box.bottom - item.clipping_box.bottom,
            )
            if clipped > 1.5 and item.clipping_box != card:
                add(
                    "python-layout-button-clipping",
                    f"{item.path} 的按钮本体预计被裁切祖先约 {_vp(clipped)}vp",
                )

    for index, first in enumerate(components):
        for second in components[index + 1:]:
            horizontal = min(first.box.right, second.box.right) - max(first.box.x, second.box.x)
            vertical = min(first.box.bottom, second.box.bottom) - max(first.box.y, second.box.y)
            if horizontal > 1.5 and vertical > 1.5:
                add("python-layout-semantic-overlap",
                    f"{first.path} 与 {second.path} 预计发生重叠："
                    f"横向重叠 {_vp(horizontal)}vp，纵向重叠 {_vp(vertical)}vp",
                    uncertain=vertical < 4)

    for button in (item for item in components if item.tag == "PillButton"):
        preceding = [item for item in components if item is not button
                     and item.box.y < button.box.y
                     and min(item.box.right, button.box.right) - max(item.box.x, button.box.x) > 1.5]
        if preceding:
            nearest = max(preceding, key=lambda item: item.box.bottom)
            gap = button.box.y - nearest.box.bottom
            required_gap = 6 if card.width > 200 and button.box.width <= 118.75 else 8
            if gap < required_gap - 0.75:
                add("python-layout-pillbutton-gap",
                    f"{button.path} 与上方 {nearest.path} 的预计间距为 {_vp(gap)}vp，要求至少 {_vp(required_gap)}vp")

    children = root.child_elements()
    if len(children) >= 2 and any(n.tag in {"SingleLineTitle", "DoubleLineTitle"}
                                  for n in children[0].child_elements()):
        first = slots.get(f"<Card>/<{children[0].tag}>[1]")
        second = slots.get(f"<Card>/<{children[1].tag}>[2]")
        if first and second and abs(second.y - first.bottom - 6) > 0.75:
            add("python-layout-title-gap",
                f"标题槽与内容槽的预计间距为 {_vp(second.y - first.bottom)}vp，要求 6vp")

    for detail in sorted(unverified):
        # Python-only validation must never report a successful card when a
        # branch of its geometry was skipped. Unsupported geometry is a
        # blocking result; callers can fix or explicitly add a model for it.
        add("python-layout-unverified", detail)
    return findings
