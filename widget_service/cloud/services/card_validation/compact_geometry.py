"""Compact 展开树的保守二维几何检查；估算结果与确定冲突分开报告。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_reference_canvas import reference_dimension

_CONTAINERS = frozenset({"Row", "Column", "List", "Stack"})
_LEAVES = frozenset({"Text", "Image", "Button", "Checkbox", "Progress", "Divider", "CardHeader"})
_TOLERANCE = 1.5
_MAX_NODES = 512
_MAX_FINDINGS = 32
_MAX_DEPTH = 64


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    def intersection(self, other: Box) -> Box:
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.width, other.x + other.width)
        bottom = min(self.y + self.height, other.y + other.height)
        return Box(left, top, max(0.0, right - left), max(0.0, bottom - top))


@dataclass(frozen=True)
class Size:
    width: float
    height: float
    estimated: bool = False


@dataclass(frozen=True)
class PaintedBox:
    component_id: str
    path: tuple[str, ...]
    box: Box
    estimated: bool
    recipe_owner: str | None


@dataclass
class GeometryResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    boxes: list[PaintedBox] = field(default_factory=list)


def _number(value: Any) -> float | None:
    result: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value):
            result = float(value)
    return result


def _edges(value: Any) -> dict[str, float]:
    result: dict[str, float] = {}
    scalar = _number(value)
    for side in ("left", "right", "top", "bottom"):
        amount = scalar
        if isinstance(value, dict):
            amount = _number(value.get(side))
        result[side] = amount if amount is not None else 0.0
    return result


def _edge_sum(props: dict[str, Any], key: str, axis: str) -> float:
    edges = _edges(props.get(key))
    sides = ("left", "right") if axis == "width" else ("top", "bottom")
    return sum(edges.get(side, 0.0) for side in sides)


def _dimension(value: Any, available: float) -> float | None:
    result = _number(value)
    if value == "matchParent":
        result = available
    elif isinstance(value, str) and value.endswith("%"):
        try:
            fraction = float(value.removesuffix("%")) / 100.0
        except ValueError:
            result = None
        else:
            result = available * fraction if math.isfinite(fraction) else None
    return result


def _limit(props: dict[str, Any], prefix: str, axis: str) -> float | None:
    key = prefix + axis.capitalize()
    value = props.get(key)
    constraints = props.get("constraintSize")
    if isinstance(constraints, dict) and key in constraints:
        value = constraints.get(key)
    return _number(value)


def _clamp(value: float, props: dict[str, Any], axis: str) -> float:
    maximum = _limit(props, "max", axis)
    minimum = _limit(props, "min", axis)
    if maximum is not None:
        value = min(value, maximum)
    if minimum is not None:
        value = max(value, minimum)
    return max(0.0, _edge_sum(props, "padding", axis), value)


def _row(node: ComponentRow) -> bool:
    horizontal_list = (
        node.component_type == "List" and node.props.get("listDirection") == "horizontal"
    )
    return node.component_type == "Row" or horizontal_list


def _gap(node: ComponentRow) -> float:
    return _number(node.props.get("itemMargin", node.props.get("space"))) or 0.0


def _offset(alignment: Any, free: float) -> float:
    if alignment in ("end", "bottom"):
        return free
    if alignment == "center":
        return free / 2.0
    return 0.0


def _text_size(node: ComponentRow, available_width: float) -> Size:
    font_size = _number(node.props.get("fontSize"))
    font = 14.0 if font_size is None else max(0.0, font_size)
    text = node.props.get("content", node.props.get("label"))
    width = available_width
    if isinstance(text, str) and "{{" not in text:
        units = 0.0
        for char in text:
            units += 1.0 if ord(char) > 255 else 0.6
        width = units * font
    lines = max(1, math.ceil(width / max(available_width, 1.0)))
    maximum = _number(node.props.get("maxLines"))
    if maximum is not None and maximum > 0:
        lines = min(lines, int(maximum))
    return Size(min(width, available_width), lines * font * 1.2, True)


class _Geometry:
    def __init__(self, components: list[ComponentRow]) -> None:
        self.nodes = {node.component_id: node for node in components}
        self.result = GeometryResult()
        self.visited: set[str] = set()
        self.unverified: set[str] = set()
        self.size_context: dict[str, list[str]] = {}

    def warn(self, message: str) -> None:
        if message not in self.unverified:
            self.unverified.add(message)
            self.result.warnings.append(f"COMPACT_LAYOUT_UNVERIFIED: {message}")

    def children(self, node: ComponentRow) -> list[ComponentRow]:
        result: list[ComponentRow] = []
        for child_id in node.children:
            child = self.nodes.get(child_id)
            if child is None:
                self.warn(f"component {node.component_id} references missing child {child_id}.")
                continue
            if child.props.get("visibility") == "none":
                continue
            result.append(child)
        return result

    def measure(self, node: ComponentRow, available: Size, trail: set[str]) -> Size:
        if node.component_id in trail or len(trail) >= _MAX_DEPTH:
            self.warn(f"cycle or depth limit at component {node.component_id}.")
            return Size(0.0, 0.0, True)
        width = _dimension(node.props.get("width"), available.width)
        height = _dimension(node.props.get("height"), available.height)
        uncertain = self.unmodeled_styles(node)
        if width is not None and height is not None:
            return Size(
                _clamp(width, node.props, "width"), _clamp(height, node.props, "height"), uncertain
            )
        pad_x = _edge_sum(node.props, "padding", "width")
        pad_y = _edge_sum(node.props, "padding", "height")
        outer_width = available.width if width is None else width
        outer_height = available.height if height is None else height
        inner = Size(max(0.0, outer_width - pad_x), max(0.0, outer_height - pad_y))
        if node.component_type in _CONTAINERS:
            child_sizes: list[Size] = []
            for child in self.children(node):
                size = self.measure(child, inner, trail | {node.component_id})
                child_sizes.append(
                    Size(
                        size.width + _edge_sum(child.props, "margin", "width"),
                        size.height + _edge_sum(child.props, "margin", "height"),
                        size.estimated,
                    )
                )
            natural = self.container_size(node, child_sizes)
        elif node.component_type in {"Text", "Button", "Checkbox"}:
            natural = _text_size(node, inner.width)
        elif node.component_type == "CardHeader":
            natural = Size(inner.width, 20.0)
        else:
            self.warn(f"component {node.component_id} has no definite width/height.")
            natural = Size(inner.width, inner.height, True)
        measured_width = natural.width + pad_x if width is None else width
        measured_height = natural.height + pad_y if height is None else height
        return Size(
            _clamp(measured_width, node.props, "width"),
            _clamp(measured_height, node.props, "height"),
            natural.estimated or uncertain,
        )

    @staticmethod
    def container_size(node: ComponentRow, sizes: list[Size]) -> Size:
        widths = [size.width for size in sizes]
        heights = [size.height for size in sizes]
        gap = _gap(node) * max(0, len(sizes) - 1)
        width = max(widths, default=0.0)
        height = max(heights, default=0.0)
        if _row(node):
            width = sum(widths) + gap
        elif node.component_type != "Stack":
            height = sum(heights) + gap
        return Size(width, height, any(size.estimated for size in sizes))

    def allocate(
        self, children: list[ComponentRow], sizes: list[Size], available: float, axis: str
    ) -> list[float]:
        bases: list[float] = []
        values: list[float] = []
        weights: list[float] = []
        for child, size in zip(children, sizes, strict=True):
            weight = max(0.0, _number(child.props.get("layoutWeight")) or 0.0)
            base = 0.0 if weight > 0 else getattr(size, axis)
            bases.append(base)
            values.append(_clamp(base, child.props, axis))
            weights.append(weight)
        # 冻结达到 min/max 的子项，再重新分配剩余空间，避免一次分配越过上下限。
        active = set(range(len(children)))
        for _ in range(len(children) + 1):
            free = available - sum(values)
            factors: dict[int, float] = {}
            for index in active:
                if free >= 0:
                    factors[index] = weights[index]
                else:
                    shrink = _number(children[index].props.get("flexShrink"))
                    factors[index] = max(0.0, 1.0 if shrink is None else shrink) * bases[index]
            total = sum(factors.values())
            if total <= 0.0 or abs(free) < 1e-6:
                break
            frozen: set[int] = set()
            for index, factor in factors.items():
                desired = values[index] + free * factor / total
                actual = _clamp(desired, children[index].props, axis)
                values[index] = actual
                if abs(actual - desired) > 1e-6:
                    frozen.add(index)
            if not frozen:
                break
            active -= frozen
        return values

    def place(
        self,
        node: ComponentRow,
        box: Box,
        path: tuple[str, ...],
        estimated: bool = False,
        owner: str | None = None,
        clip: Box | None = None,
        hidden: bool = False,
        backdrop: bool = False,
    ) -> None:
        if node.component_id in self.visited or len(path) >= _MAX_DEPTH:
            self.warn(f"cycle, reuse or depth limit at {node.component_id}; geometry incomplete.")
            return
        self.visited.add(node.component_id)
        if self.unmodeled_styles(node):
            estimated = True
        hidden = (
            hidden
            or node.props.get("visibility") in ("hidden", "none")
            or node.props.get("opacity") == 0
        )
        marker = node.props.get("_visualRecipe")
        if isinstance(marker, str) and marker.endswith(".root"):
            owner = node.component_id
        interactive = bool(node.props.get("onClick"))
        is_leaf = node.component_type not in _CONTAINERS
        if node.component_type not in _CONTAINERS | _LEAVES:
            self.warn(f"component {node.component_id} type {node.component_type} is not modeled.")
            estimated = True
        paint = not hidden and not backdrop
        if paint and (is_leaf or interactive):
            visible = box if clip is None else box.intersection(clip)
            if clip is not None:
                lost = max(box.width - visible.width, box.height - visible.height)
                if lost > _TOLERANCE:
                    self.add_issue(
                        f"COMPACT_LAYOUT_CLIPPED: component {node.component_id} loses "
                        f"up to {lost:.2f}vp inside an ancestor clip; rearrange the layout.",
                        True,
                    )
            if visible.width > 0 and visible.height > 0:
                self.result.boxes.append(
                    PaintedBox(node.component_id, path, visible, estimated, owner)
                )
        if is_leaf:
            return
        next_clip = clip
        if node.props.get("clip") is True:
            next_clip = box if clip is None else box.intersection(clip)
        edges = _edges(node.props.get("padding"))
        inner = Box(
            box.x + edges.get("left", 0.0),
            box.y + edges.get("top", 0.0),
            max(0.0, box.width - _edge_sum(node.props, "padding", "width")),
            max(0.0, box.height - _edge_sum(node.props, "padding", "height")),
        )
        children = self.children(node)
        available = Size(inner.width, inner.height)
        sizes = [self.measure(child, available, set(path)) for child in children]
        if node.component_type == "Stack":
            self.place_stack(
                node, children, sizes, inner, path, estimated, owner, next_clip, hidden
            )
        else:
            self.place_flow(node, children, sizes, inner, path, estimated, owner, next_clip, hidden)

    def place_stack(
        self,
        node: ComponentRow,
        children: list[ComponentRow],
        sizes: list[Size],
        inner: Box,
        path: tuple[str, ...],
        estimated: bool,
        owner: str | None,
        clip: Box | None,
        hidden: bool,
    ) -> None:
        alignment = str(node.props.get("alignContent", "center"))
        horizontal = "start" if "Start" in alignment or alignment == "start" else "center"
        if "End" in alignment or alignment == "end":
            horizontal = "end"
        vertical = "start" if alignment.startswith("top") else "center"
        if alignment.startswith("bottom"):
            vertical = "end"
        for index, (child, size) in enumerate(zip(children, sizes, strict=True)):
            margins = _edges(child.props.get("margin"))
            x = inner.x + margins.get("left", 0.0)
            y = inner.y + margins.get("top", 0.0)
            x += _offset(
                horizontal, inner.width - size.width - _edge_sum(child.props, "margin", "width")
            )
            y += _offset(
                vertical, inner.height - size.height - _edge_sum(child.props, "margin", "height")
            )
            box = Box(x, y, size.width, size.height)
            full = box == inner
            background = index == 0 and child.component_type == "Image" and full
            background = background and not child.props.get("onClick")
            self.place(
                child,
                box,
                (*path, child.component_id),
                estimated or size.estimated,
                owner,
                clip,
                hidden,
                bool(background),
            )

    def place_flow(
        self,
        node: ComponentRow,
        children: list[ComponentRow],
        sizes: list[Size],
        inner: Box,
        path: tuple[str, ...],
        estimated: bool,
        owner: str | None,
        clip: Box | None,
        hidden: bool,
    ) -> None:
        row = _row(node)
        axis = "width" if row else "height"
        cross_axis = "height" if row else "width"
        total = inner.width if row else inner.height
        cross = inner.height if row else inner.width
        gap = _gap(node)
        margins = sum(_edge_sum(child.props, "margin", axis) for child in children)
        available = total - margins - gap * max(0, len(children) - 1)
        lengths = self.allocate(children, sizes, available, axis)
        free = available - sum(lengths)
        justify = node.props.get("justifyContent", "start")
        cursor = _offset(justify, free)
        if free > 0 and children:
            if justify == "spaceBetween" and len(children) > 1:
                gap += free / (len(children) - 1)
            elif justify in ("spaceAround", "spaceEvenly"):
                divisor = len(children) + (1 if justify == "spaceEvenly" else 0)
                extra = free / divisor
                cursor = extra if justify == "spaceEvenly" else extra / 2.0
                gap += extra
        # 主轴估算影响后续兄弟的位置，不能把这类相交升级为确定错误。
        uncertain_flow = estimated or any(size.estimated for size in sizes)
        for index, child in enumerate(children):
            size = sizes[index]
            main = lengths[index]
            cross_size = getattr(size, cross_axis)
            align = child.props.get("alignSelf", node.props.get("alignItems"))
            if align is None:
                align = "center" if row else "stretch"
            has_cross_size = _dimension(child.props.get(cross_axis), cross) is not None
            if align == "stretch" and not has_cross_size:
                cross_size = _clamp(
                    cross - _edge_sum(child.props, "margin", cross_axis), child.props, cross_axis
                )
            edges = _edges(child.props.get("margin"))
            cursor += edges.get("left" if row else "top", 0.0)
            cross_position = edges.get("top" if row else "left", 0.0)
            cross_position += _offset(
                align, cross - cross_size - _edge_sum(child.props, "margin", cross_axis)
            )
            child_box = Box(inner.x + cursor, inner.y + cross_position, main, cross_size)
            if not row:
                child_box = Box(inner.x + cross_position, inner.y + cursor, cross_size, main)
            self.record_size_context(node, child, size, child_box, inner)
            self.place(
                child, child_box, (*path, child.component_id), uncertain_flow, owner, clip, hidden
            )
            cursor += main + edges.get("right" if row else "bottom", 0.0) + gap

    def record_size_context(
        self, parent: ComponentRow, child: ComponentRow, natural: Size, box: Box, inner: Box
    ) -> None:
        """只记录尺寸压力，供已有重叠诊断解释原因，不单独产生错误。"""
        axis = "width" if _row(parent) else "height"
        cross_axis = "height" if _row(parent) else "width"
        notes: list[str] = []
        available = max(
            0.0, getattr(inner, cross_axis) - _edge_sum(child.props, "margin", cross_axis)
        )
        actual = getattr(box, cross_axis)
        if actual - available > _TOLERANCE:
            notes.append(
                f"child {child.component_id} has expanded {cross_axis} {actual:.2f}vp "
                f"but parent {parent.component_id} ({parent.component_type}) provides only "
                f"{available:.2f}vp after padding/margins; exceeds by "
                f"{actual - available:.2f}vp. Main-axis weight/shrink does not reduce "
                f"this cross-axis {cross_axis}."
            )
        requested = getattr(natural, axis)
        allocated = getattr(box, axis)
        if requested - allocated > _TOLERANCE:
            notes.append(
                f"parent {parent.component_id} ({parent.component_type}) compresses child "
                f"{child.component_id} {axis} from measured {requested:.2f}vp to allocated "
                f"{allocated:.2f}vp; check its descendants against the reduced slot."
            )
        self.size_context[child.component_id] = notes

    def overlap_context(self, first: PaintedBox, second: PaintedBox) -> str:
        notes: list[str] = []
        for path in (first.path, second.path):
            for component_id in reversed(path):
                for note in self.size_context.get(component_id, []):
                    if note not in notes and len(notes) < 6:
                        notes.append(note)
        context = ""
        if notes:
            context = (
                " Layout size context (model estimates, not pixel measurements): "
                + " ".join(notes)
                + " Rebalance parent space or use a compact component that fits the slot, "
                "preserving content/actions. Do not hide the problem with clipping."
            )
        return context

    def add_issue(self, message: str, estimated: bool) -> None:
        target = self.result.warnings if estimated else self.result.errors
        if len(target) < _MAX_FINDINGS:
            target.append(message)
        else:
            self.warn("finding limit reached; further geometry diagnostics omitted.")

    def unmodeled_styles(self, node: ComponentRow) -> bool:
        props = node.props
        uncertain = False
        if props.get("borderWidth") or props.get("alignItems") == "baseline":
            uncertain = True
        if node.component_type == "List" and (props.get("scrollBar") or props.get("nestedScroll")):
            uncertain = True
        if node.component_type == "Stack" and props.get("padding"):
            uncertain = True
        if node.component_type == "Stack":
            for child in self.children(node):
                if child.props.get("layoutWeight"):
                    uncertain = True
        for key in ("alignItems", "justifyContent", "alignContent", "visibility"):
            value = props.get(key)
            if value is not None and not isinstance(value, str):
                uncertain = True
        if uncertain:
            self.warn(
                f"component {node.component_id} has unmodeled layout styles "
                "(border, baseline, scroll, Stack padding/weight or malformed alignment)."
            )
        return uncertain

    def compare(self) -> None:
        for first, second in combinations(self.result.boxes, 2):
            if first.component_id in second.path or second.component_id in first.path:
                continue
            if first.recipe_owner is not None and first.recipe_owner == second.recipe_owner:
                continue
            overlap = first.box.intersection(second.box)
            if overlap.width <= _TOLERANCE or overlap.height <= _TOLERANCE:
                continue
            estimated = first.estimated or second.estimated
            code = "COMPACT_LAYOUT_ESTIMATED_OVERLAP" if estimated else "COMPACT_LAYOUT_OVERLAP"
            self.add_issue(
                f"{code}: components {first.component_id} and {second.component_id} "
                f"overlap by {overlap.width:.2f}vp horizontally and {overlap.height:.2f}vp "
                "vertically. Preserve content/actions and rearrange their parent layout."
                + self.overlap_context(first, second),
                False,
            )


def validate_compact_geometry(
    components: list[ComponentRow],
    *,
    size: str | None,
    protocol_profile: dict[str, Any] | None = None,
) -> GeometryResult:
    """使用可信展开后的树；不执行绑定表达式，不修改源 DSL。"""
    engine = _Geometry(components)
    if len(components) > _MAX_NODES or len(engine.nodes) != len(components):
        engine.warn("duplicate component IDs or more than 512 nodes; geometry incomplete.")
        return engine.result
    root = engine.nodes.get("root")
    if root is None or not isinstance(size, str):
        engine.warn("root or reference size unavailable; geometry incomplete.")
        return engine.result
    try:
        width = reference_dimension(size, "width", protocol_profile)
        height = reference_dimension(size, "height", protocol_profile)
    except ValueError as exc:
        engine.warn(str(exc))
        return engine.result
    root_width = _dimension(root.props.get("width"), width)
    root_height = _dimension(root.props.get("height"), height)
    width = _clamp(width if root_width is None else root_width, root.props, "width")
    height = _clamp(height if root_height is None else root_height, root.props, "height")
    engine.place(root, Box(0.0, 0.0, width, height), (root.component_id,))
    engine.compare()
    return engine.result
