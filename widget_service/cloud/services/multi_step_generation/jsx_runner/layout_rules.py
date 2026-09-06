"""Structural 2x4 rules; never infer a layout Type from business text."""

from __future__ import annotations

import math
import re
from typing import Any

TOP_LEVEL_2X4_TYPES = frozenset({"12", "13", "14", "15", "15-R", "17"})
FIXED_SLOT_COMPONENTS = frozenset({"CardButton", "InfoBlock"})


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _descendants(nodes: list[Any]) -> list[Any]:
    pending = list(nodes)
    result = []
    while pending:
        node = pending.pop()
        result.append(node)
        pending.extend(node.child_elements())
    return result


def fixed_slot_kind(node: Any) -> str | None:
    if node.tag in FIXED_SLOT_COMPONENTS:
        return node.tag
    children = node.child_elements()
    if node.tag == "Stack" and len(children) == 1 and children[0].tag in FIXED_SLOT_COMPONENTS:
        return children[0].tag
    return None


def fixed_grid_errors(children: list[Any], columns: int | None) -> list[str]:
    kinds = [fixed_slot_kind(child) for child in children]
    if columns != 2 or len(kinds) != 4 or any(kind is None for kind in kinds):
        return ["Type 14 requires four valid CardButton/InfoBlock slots in a two-column Grid"]
    if kinds[0] != kinds[2] or kinds[1] != kinds[3]:
        return ["Type 14 mixed CardButton/InfoBlock slots must use the same component type within each column"]
    return []


def preferred_axis_size(node: Any, parent: Any, axis: str) -> Any:
    """Resolve explicit sizing precedence, not content-dependent flex allocation."""
    value = node.props.get(axis)
    main_axis = "width" if parent.props.get("direction", "column") == "row" else "height"
    if parent.tag in {"Card", "Stack"} and axis == main_axis and node.props.get("position") != "absolute":
        if node.props.get("basis") is not None:
            value = node.props["basis"]
        elif node.props.get("flex") == 1:
            return None  # The allocation depends on siblings, not this literal.
    minimum = node.props.get("minWidth" if axis == "width" else "minHeight")
    if _finite_number(value) and _finite_number(minimum):
        value = max(value, minimum)
    return value


def fixed_slot_dimension_errors(container: Any) -> list[str]:
    errors: list[str] = []
    children = container.child_elements()
    for index, child in enumerate(children):
        if fixed_slot_kind(child) is None:
            continue
        # A Stack containing InfoBlock may be a content wrapper, not a fixed
        # slot. Only a Grid or an explicit CardButton slot proves intent here.
        if container.tag != "Grid" and fixed_slot_kind(child) != "CardButton":
            continue
        width = preferred_axis_size(child, container, "width") if child.tag == "Stack" else None
        height = preferred_axis_size(child, container, "height") if child.tag == "Stack" else None
        if container.tag == "Grid" and container.props.get("columns", 2) == 2:
            grid_width = container.props.get("width")
            gap = container.props.get("columnGap", container.props.get("gap", 0))
            if (width is None or width == "full") and _finite_number(grid_width) and _finite_number(gap):
                width = max(0, grid_width - gap) / 2
            rows = container.props.get("rows")
            tokens = rows.split() if isinstance(rows, str) else []
            if (height is None or height == "full") and len(tokens) == (len(children) + 1) // 2:
                token = tokens[index // 2]
                if re.fullmatch(r"\d+(?:\.\d+)?px", token):
                    height = float(token[:-2])
        for axis, value, expected in (("width", width, 144), ("height", height, 64)):
            if _finite_number(value) and value != expected:
                errors.append(f"2x4 fixed slot {axis} must be {expected}vp; found {value}vp")
    return list(dict.fromkeys(errors))


def _component_region_errors(root: Any, pattern: str) -> list[str]:
    errors: list[str] = []
    children = root.child_elements()
    descendants = _descendants(children)
    if pattern in {"12", "13"} and any(node.tag == "InfoBlock" for node in descendants):
        errors.append(f"Type {pattern} does not provide an InfoBlock slot")
    if pattern in {"12", "14"} and any(
        node.tag in {"PillButton", "CircleButton"} for node in descendants
    ):
        errors.append(f"Type {pattern} does not provide a PillButton or CircleButton slot")
    if pattern == "12" and any(node.tag == "CardButton" for node in descendants):
        errors.append("Type 12 does not provide an action slot")
    if pattern in {"15", "15-R", "17"} and root.props.get("direction") == "row" and len(children) == 2:
        content_index = 1 if pattern == "15-R" else 0
        if any(node.tag == "InfoBlock" for node in _descendants([children[content_index]])):
            errors.append(f"Type {pattern} InfoBlock must occupy the fixed side slot, not the content region")
        if pattern == "17" and any(node.tag == "PillButton" for node in _descendants([children[1]])):
            errors.append("Type 17 right-hand action slot requires CardButton, not PillButton")
    return errors


def _type13_parent_errors(root: Any) -> list[str]:
    children = root.child_elements()
    if not (
        root.props.get("direction") == "row"
        and len(children) == 2
        and all(child.tag == "Stack" for child in children)
    ):
        return []
    errors: list[str] = []
    for child in children:
        if child.props.get("surface") != "backplate":
            errors.append("Type 13 requires a backplate on both parent content regions")
        for axis, expected in (("width", 142), ("height", 136)):
            value = preferred_axis_size(child, root, axis)
            if _finite_number(value) and value != expected:
                errors.append(f"Type 13 parent {axis} must be {expected}vp; found {value}vp")
        if any(node.props.get("position") == "absolute" for node in _descendants(child.child_elements())):
            errors.append("Type 13 sublayouts must use normal flow, not absolute positioning")
    gap = root.props.get("gap", 0)
    if _finite_number(gap) and gap != 12:
        errors.append("Type 13 parent regions require a 12vp horizontal gap")
    return errors


def declared_layout_errors(root: Any, pattern: str | None) -> list[str]:
    """Check only explicitly declared Types and unambiguous JSX structures."""
    if pattern not in TOP_LEVEL_2X4_TYPES:
        return []
    errors = _component_region_errors(root, pattern)
    for child in root.child_elements():
        if child.tag == "Stack" and root.props.get("direction", "column") != "column":
            # A title inside a horizontal region is local, not a public header.
            continue
        content = child.child_elements() if child.tag == "Stack" else [child]
        if content and all(node.tag in {"SingleLineTitle", "DoubleLineTitle"} for node in content):
            errors.append("2x4 top-level layouts do not allow a public title slot; use a local sublayout title")
    if pattern == "13":
        errors.extend(_type13_parent_errors(root))
    return list(dict.fromkeys(errors))
