"""将闭合的参考分区编译成宿主自适应关系；不读取或猜测设备尺寸。"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from services.compact_reference_canvas import reference_dimension

_AXES = ("width", "height")
_REGIONS = frozenset({"Row", "Column", "InfoBlock", "CardButton"})
_WIDTH_FILL = _REGIONS | {"Text", "Button", "PillButton", "SingleLineTitle"}
_FIXED_ACTIONS = frozenset({"Button", "PillButton", "CircleButton"})
_CONSTRAINTS = frozenset(
    {
        "aspectRatio",
        "constraintSize",
        "minWidth",
        "maxWidth",
        "minHeight",
        "maxHeight",
        "borderWidth",
    }
)


@dataclass(frozen=True)
class RegionBox:
    width: float | None
    height: float | None

    def axis(self, name: str) -> float | None:
        return self.width if name == "width" else self.height


def _number(value: Any) -> float | None:
    result = None
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        if math.isfinite(value) and value >= 0:
            result = float(value)
    return result


def _styles(node: dict[str, Any]) -> dict[str, Any]:
    value = node.get("styles")
    return value if isinstance(value, dict) else {}


def _inset(node: dict[str, Any], name: str, axis: str) -> float | None:
    value = _styles(node).get(name, 0)
    if not isinstance(value, dict):
        scalar = _number(value)
        return None if scalar is None else scalar * 2
    sides = ("left", "right") if axis == "width" else ("top", "bottom")
    first, second = (_number(value.get(side, 0)) for side in sides)
    return None if first is None or second is None else first + second


def _main_axis(node: dict[str, Any]) -> str | None:
    result = None
    if node.get("component") == "Row":
        result = "width"
    elif node.get("component") == "Column":
        result = "height"
    return result


def _gap(node: dict[str, Any]) -> float | None:
    return _number(node.get("itemMargin", _styles(node).get("itemMargin", 0)))


class _ReferenceGeometry:
    """只求可确定的盒尺寸；自然文字尺寸、未知表达式不作为闭合证明。"""

    def __init__(self, nodes: list[dict[str, Any]]) -> None:
        self.nodes = {node.get("id"): node for node in nodes}
        self.boxes: dict[str, RegionBox] = {}

    def children(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for identifier in node.get("children", []):
            child = self.nodes.get(identifier)
            if child is not None:
                result.append(child)
        return result

    def intrinsic(self, node: dict[str, Any], axis: str, seen: set[str]) -> float | None:
        value = _number(_styles(node).get(axis))
        identifier = node.get("id")
        if value is not None or identifier in seen:
            return value
        # 百分比或表达式不是自然尺寸，不能用后代内容代替作者的显式关系。
        if axis in _styles(node):
            return None
        if _styles(node).get("borderWidth", 0) != 0:
            return None
        seen = seen | {identifier}
        main = _main_axis(node)
        children = self.children(node)
        if main is None or not children:
            return None
        lengths: list[float] = []
        for child in children:
            length = self.intrinsic(child, axis, seen)
            margin = _inset(child, "margin", axis)
            if length is None or margin is None:
                return None
            lengths.append(length + margin)
        padding, gap = _inset(node, "padding", axis), _gap(node)
        if padding is None or gap is None:
            return None
        content = sum(lengths) + gap * (len(lengths) - 1) if axis == main else max(lengths)
        return padding + content

    def child_lengths(
        self, node: dict[str, Any], inner: RegionBox, axis: str
    ) -> list[float | None]:
        children = self.children(node)
        available = inner.axis(axis)
        lengths: list[float | None] = []
        weights: list[float] = []
        margins: list[float | None] = []
        for child in children:
            props = _styles(child)
            length = self.intrinsic(child, axis, set())
            if props.get(axis) == "matchParent":
                length = available
            lengths.append(length)
            weights.append(_number(props.get("layoutWeight")) or 0.0)
            margins.append(_inset(child, "margin", axis))
        gap = _gap(node)
        if axis != _main_axis(node) or not any(weights):
            return lengths
        fixed = 0.0
        known = available is not None and gap is not None
        for index, weight in enumerate(weights):
            margin, length = margins[index], lengths[index]
            if margin is None or (weight == 0 and length is None):
                known = False
            else:
                fixed += margin + (length if weight == 0 else 0.0)
        remaining = None
        if known and available is not None and gap is not None:
            remaining = max(0.0, available - fixed - gap * max(0, len(children) - 1))
        for index, weight in enumerate(weights):
            if weight > 0:
                lengths[index] = None if remaining is None else remaining * weight / sum(weights)
        return lengths

    def visit(self, identifier: str, box: RegionBox, seen: set[str]) -> None:
        node = self.nodes.get(identifier)
        if node is None or identifier in seen:
            return
        self.boxes[identifier] = box
        inner = self.inner(node, box)
        widths = self.child_lengths(node, inner, "width")
        heights = self.child_lengths(node, inner, "height")
        for index, child in enumerate(self.children(node)):
            self.visit(
                child.get("id"), RegionBox(widths[index], heights[index]), seen | {identifier}
            )

    def blocked_axes(self) -> dict[str, set[str]]:
        """压缩风险只传播到本区后代和相同轴，不冻结其它可确定区域。"""
        blocked: dict[str, set[str]] = {}

        def mark(identifier: str, axis: str) -> None:
            axes = blocked.setdefault(identifier, set())
            if axis in axes:
                return
            axes.add(axis)
            node = self.nodes.get(identifier)
            if node is not None:
                for child in self.children(node):
                    mark(child.get("id"), axis)

        for identifier, box in self.boxes.items():
            node = self.nodes.get(identifier)
            if node is None:
                continue
            axis, gap = _main_axis(node), _gap(node)
            if axis is None or gap is None:
                continue
            available = self.inner(node, box).axis(axis)
            if available is None:
                continue
            children = self.children(node)
            used = gap * max(0, len(children) - 1)
            for child in children:
                child_box = self.boxes.get(child.get("id"))
                length = child_box.axis(axis) if child_box is not None else None
                margin = _inset(child, "margin", axis)
                used += (length or 0.0) + (margin or 0.0)
            if used > available + 1e-7:
                mark(identifier, axis)
        return blocked

    @staticmethod
    def inner(node: dict[str, Any], box: RegionBox) -> RegionBox:
        # 不假设不同宿主的边框盒模型一致，未知内区不能用于闭合证明。
        if _styles(node).get("borderWidth", 0) != 0:
            return RegionBox(None, None)
        lengths: list[float | None] = []
        for axis in _AXES:
            length, padding = box.axis(axis), _inset(node, "padding", axis)
            available = None
            if length is not None and padding is not None:
                available = max(0.0, length - padding)
            lengths.append(available)
        return RegionBox(*lengths)


def reference_region_boxes(nodes: list[dict[str, Any]], *, size: str) -> dict[str, RegionBox]:
    """只读求解参考盒，用于校验显式权重；未知自然尺寸保留 None。"""
    geometry = _ReferenceGeometry(nodes)
    geometry.visit(
        "root",
        RegionBox(reference_dimension(size, "width"), reference_dimension(size, "height")),
        set(),
    )
    return geometry.boxes


def _fixed_action_branch(
    node: dict[str, Any], geometry: _ReferenceGeometry, author_types: dict[str, str], seen: set[str]
) -> bool:
    identifier = node.get("id")
    if identifier in seen:
        return True
    kind = author_types.get(identifier)
    if kind == "CardButton":
        return False
    if kind in _FIXED_ACTIONS or node.get("onClick"):
        return True
    children = geometry.children(node)
    return len(children) == 1 and _fixed_action_branch(
        children[0], geometry, author_types, seen | {identifier}
    )


def _grow_main_regions(
    parent: dict[str, Any],
    geometry: _ReferenceGeometry,
    inner: RegionBox,
    author_types: dict[str, str],
    output: dict[str, dict[str, Any]],
    slots: frozenset[str],
    slot_actions: frozenset[str],
    author_weights: frozenset[str] | None,
    wrappers: list[tuple[str, str, str, float]],
) -> None:
    axis = _main_axis(parent)
    if axis is None:
        return
    available, gap = inner.axis(axis), _gap(parent)
    if available is None or gap is None:
        return
    children = geometry.children(parent)
    used = gap * max(0, len(children) - 1)
    candidates: list[tuple[str, float]] = []
    for child in children:
        props, identifier = _styles(child), child.get("id")
        # 仅槽位 Recipe 的自动权重可与其它区域合并；作者显式权重原样保留。
        if (_number(props.get("layoutWeight")) or 0) > 0:
            automatic = author_weights is not None and identifier not in author_weights
            if not automatic or identifier not in slots:
                return
        box = geometry.boxes.get(identifier)
        length = box.axis(axis) if box is not None else None
        margin = _inset(child, "margin", axis)
        if length is None or margin is None:
            return
        used += length + margin
        eligible = author_types.get(identifier) in _REGIONS and length > 0
        constrained = _CONSTRAINTS.intersection(props)
        if identifier in slot_actions:
            constrained = constrained - {"constraintSize"}
        if not eligible or constrained:
            continue
        fixed_action = _fixed_action_branch(child, geometry, author_types, set())
        if axis == "height" and fixed_action and identifier not in slots:
            continue
        candidates.append((identifier, length))
    if not math.isclose(used, available, rel_tol=0, abs_tol=1e-7):
        return
    # 内边距占比不同时，用零内边距布局壳分配外框，避免 Web flex 产生比例偏移。
    padding_ratios: list[float] = []
    for identifier, length in candidates:
        node = geometry.nodes.get(identifier)
        padding = _inset(node, "padding", axis) if node is not None else None
        if padding is None:
            return
        padding_ratios.append(padding / length)
    needs_wrapper = bool(padding_ratios) and any(
        not math.isclose(ratio, padding_ratios[0], rel_tol=0, abs_tol=1e-7)
        for ratio in padding_ratios
    )
    if needs_wrapper:
        cross = "height" if axis == "width" else "width"
        for identifier, _ in candidates:
            box = geometry.boxes.get(identifier)
            if box is None or box.axis(cross) is None:
                return
    for identifier, length in candidates:
        props = output.get(identifier)
        if props is None:
            continue
        if needs_wrapper:
            wrappers.append((parent.get("id"), identifier, axis, length))
        else:
            props.pop(axis, None)
            props["layoutWeight"] = length
        if axis == "height" and identifier in slot_actions:
            _release_action_height(props)


def _release_action_height(props: dict[str, Any]) -> None:
    limits = props.get("constraintSize")
    if isinstance(limits, dict):
        limits.pop("maxHeight", None)


def _wrap_regions(
    result: list[dict[str, Any]],
    wrappers: list[tuple[str, str, str, float]],
    geometry: _ReferenceGeometry,
) -> None:
    by_id = {node.get("id"): node for node in result}
    for parent_id, identifier, axis, weight in wrappers:
        parent, child = by_id.get(parent_id), by_id.get(identifier)
        box = geometry.boxes.get(identifier)
        if parent is None or child is None or box is None:
            continue
        cross = "height" if axis == "width" else "width"
        props = child.setdefault("styles", {})
        shell_id = identifier + "_region_shell"
        while shell_id in by_id:
            shell_id += "_"
        shell_styles = {
            "layoutWeight": weight,
            cross: props.get(cross, box.axis(cross)),
            "alignItems": "start",
            "justifyContent": "start",
        }
        if "margin" in props:
            shell_styles["margin"] = props.pop("margin")
        props.pop("layoutWeight", None)
        props.update(width="matchParent", height="matchParent")
        shell = {
            "id": shell_id,
            "component": "Column",
            "children": [identifier],
            "itemMargin": 0,
            "styles": shell_styles,
        }
        parent["children"] = [
            shell_id if item == identifier else item for item in parent.get("children", [])
        ]
        by_id[shell_id] = shell
        result.append(shell)


def adapt_region_layout(
    nodes: list[dict[str, Any]],
    *,
    author_types: dict[str, str],
    size: str,
    profile: dict[str, Any] | None = None,
    slots: frozenset[str] = frozenset(),
    slot_actions: frozenset[str] = frozenset(),
    author_weights: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """只改可证明等价的外部分区尺寸；输出交由宿主测量，无机型分支。"""
    result = copy.deepcopy(nodes)
    # 当前布局契约只有这两种网格形态；其它协议形态沿用原转换，不猜参考预算。
    if size not in {"2x2", "2x4"}:
        return result
    geometry = _ReferenceGeometry(nodes)
    geometry.visit(
        "root",
        RegionBox(
            reference_dimension(size, "width", profile),
            reference_dimension(size, "height", profile),
        ),
        set(),
    )
    blocked = geometry.blocked_axes()
    wrappers: list[tuple[str, str, str, float]] = []
    output: dict[str, dict[str, Any]] = {}
    for node in result:
        identifier = node.get("id")
        if isinstance(identifier, str):
            output[identifier] = node.setdefault("styles", {})
    parent_axes: dict[str, str | None] = {}
    for node in nodes:
        for child in node.get("children", []):
            parent_axes[child] = _main_axis(node)
    for identifier, box in geometry.boxes.items():
        parent = geometry.nodes.get(identifier)
        if parent is None or identifier not in author_types:
            continue
        inner = geometry.inner(parent, box)
        main = _main_axis(parent)
        allocated: set[str] = set()
        parent_styles = output.get(identifier, {})
        for axis in _AXES:
            explicit = _number(parent_styles.get(axis)) is not None
            filled = parent_styles.get(axis) == "matchParent"
            weighted = (_number(parent_styles.get("layoutWeight")) or 0) > 0
            if identifier == "root" or explicit or filled:
                allocated.add(axis)
            elif weighted and parent_axes.get(identifier) == axis:
                allocated.add(axis)
        for child in geometry.children(parent):
            child_id = child.get("id")
            kind = author_types.get(child_id)
            props = _styles(child)
            target = output.get(child_id)
            constraints = _CONSTRAINTS.intersection(props)
            if child_id in slot_actions:
                constraints -= {"constraintSize"}
            if target is None or constraints:
                continue
            for axis in _AXES:
                if axis not in allocated:
                    continue
                allowed = kind in (_WIDTH_FILL if axis == "width" else _REGIONS)
                if not allowed or axis == main or _inset(child, "margin", axis) != 0:
                    continue
                if axis in blocked.get(identifier, set()):
                    continue
                value, available = _number(props.get(axis)), inner.axis(axis)
                if value is not None and available is not None:
                    if value > 0 and math.isclose(value, available, rel_tol=0, abs_tol=1e-7):
                        target[axis] = "matchParent"
                        if axis == "height" and child_id in slot_actions:
                            _release_action_height(target)
        if main in allocated and main not in blocked.get(identifier, set()):
            _grow_main_regions(
                parent, geometry, inner, author_types, output, slots, slot_actions,
                author_weights, wrappers,
            )
    _wrap_regions(result, wrappers, geometry)
    return result
