"""Structural layout rules; never infer a layout pattern from business text."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

TOP_LEVEL_2X2_TYPES = frozenset(
    {"0", "1", "2", "3", "6", "10-A", "10-B", "10-C", "11-A", "12", "14", "15"}
)
TOP_LEVEL_2X4_TYPES = frozenset({"12", "13", "14", "15"})
FIXED_SLOT_COMPONENTS = frozenset({"CardButton", "InfoBlock"})
_MISSING = object()

# Shared with the gallery audit; regression tests compare this table with §2.5.
SUB_PATTERN_CONTRACT = json.loads(
    (Path(__file__).resolve().parents[1] / "references/layouts/subpattern_contracts.json")
    .read_text(encoding="utf-8")
)


def _sub140_skeleton_valid(skeleton: Any, blocks: list[Any], expected_blocks: int) -> bool:
    if not skeleton or skeleton.props.get("gap") != 8 or len(blocks) != expected_blocks:
        return False
    if not blocks:
        return False
    for node in _descendants([blocks[0]]):
        if node.tag in SUB_PATTERN_CONTRACT["titleComponents"]:
            return True
    return False


def _sub140_columns_valid(row: Any, columns: list[Any]) -> bool:
    if not row or row.tag != "Stack" or row.props.get("direction") != "row":
        return False
    if row.props.get("flex") != 1 or row.props.get("gap") != 8 or len(columns) != 2:
        return False
    for node in columns:
        if node.tag != "Stack" or node.props.get("flex") != 1:
            return False
    return True


def sub_pattern_composition_errors(
    root: Any, pattern: str, sub_patterns: dict[str, str],
) -> list[str]:
    """Count authored component instances, not wrappers, fields or rendered DOM."""
    if pattern not in {"13", "15"} or not sub_patterns:
        return []
    children = root.child_elements()
    if (root.props.get("direction") != "row" or len(children) != 2
            or any(child.tag != "Stack" for child in children)):
        return ["2x4 declared subpatterns require two direct Stack regions in a row Card"]
    regions = {"left": children[0], "right": children[1]} if pattern == "13" else {"content": children[0]}
    errors = []
    for region, name in sub_patterns.items():
        code = name.split()[0]
        expected = SUB_PATTERN_CONTRACT["patterns"][code]
        counts = {"content": 0, "titles": 0, "buttons": 0}
        buttons = []
        content_nodes = []
        pending = [regions[region]]
        while pending:
            node = pending.pop()
            if node.tag in SUB_PATTERN_CONTRACT["structuralComponents"]:
                pending.extend(node.child_elements())
            elif node.tag in SUB_PATTERN_CONTRACT["titleComponents"]:
                counts["titles"] += 1
            elif node.tag in SUB_PATTERN_CONTRACT["buttonComponents"]:
                counts["buttons"] += 1
                buttons.append(node.tag)
            elif node.tag not in SUB_PATTERN_CONTRACT["decorationComponents"]:
                # Business components are atomic even when they contain JSX.
                counts["content"] += 1
                content_nodes.append(node)
        count_labels = (
            ("content", "content components"),
            ("titles", "title components"),
            ("buttons", "buttons"),
        )
        for key, label in count_labels:
            required = expected.get(key, _MISSING)
            if required is _MISSING:
                raise KeyError(key)
            actual = counts.get(key)
            if actual is None:
                raise KeyError(key)
            allowed = required if isinstance(required, list) else [required]
            if actual not in allowed:
                errors.append(
                    f"decision.subPattern.{region} {code} requires exactly "
                    f"{required} {label}; found {actual}"
                )
        if expected["buttons"] and any(button != "PillButton" for button in buttons):
            errors.append(f"decision.subPattern.{region} {code} only allows PillButton in its action slot")
        component = expected.get("contentComponent")
        if component:
            for node in content_nodes:
                if (
                    node.tag == component["name"]
                    and node.props.get("size", "sm") == component["size"]
                ):
                    continue
                errors.append(
                    f'decision.subPattern.{region} {code} requires {component["name"]} '
                    f'size="{component["size"]}" content components'
                )
                break
        if code == "Sub-140-D":
            candidates = _descendants([regions[region]])
            skeleton = None
            for node in candidates:
                if node.tag != "Stack" or node.props.get("width") != 140:
                    continue
                if node.props.get("height") == 136:
                    skeleton = node
                    break
            blocks = skeleton.child_elements() if skeleton else []
            expected_blocks = 3 if buttons else 2
            if not _sub140_skeleton_valid(skeleton, blocks, expected_blocks):
                errors.append(
                    f"{code} requires a leading title and two-column content; "
                    "omit the entire button slot when absent"
                )
            row = blocks[1] if len(blocks) > 1 else None
            columns = row.child_elements() if row else []
            if not _sub140_columns_valid(row, columns):
                errors.append(
                    f"{code} requires an adaptive flex=1 row "
                    "with two equal flex=1 columns and gap=8"
                )
            if buttons:
                if not blocks or blocks[-1].props.get("width") != 136:
                    errors.append(f"{code} requires a final 136x36vp button slot")
                elif blocks[-1].props.get("height") != 36:
                    errors.append(f"{code} requires a final 136x36vp button slot")
    return errors

# Public names are the exact labels exposed to the generation model. The
# historical numeric codes stay internal so the existing geometry validators
# do not need to duplicate their rules under a second naming system.
LAYOUT_PATTERN_2X2_CODES = {
    "核心居中": "0",
    "标题单内容": "1",
    "标题双内容": "2",
    "双信息块": "3",
    "内容四宫格": "6",
    "标题内容单按钮": "10-A",
    "标题主次内容单按钮": "10-B",
    "标题内容双按钮": "10-C",
    "标题正文角标按钮": "11-A",
    "双列内容单按钮": "12",
    "标题锚点内容": "14",
    "紧凑内容双按钮": "15",
}
LAYOUT_PATTERN_2X4_CODES = {
    "上下双区": "12",
    "左右双区": "13",
    "四槽宫格": "14",
    "左内容右侧双槽": "15",
}
SUB_PATTERN_2X4_GROUPS = {
    "Sub-118-A 核心居中": "118",
    "Sub-118-B 标题单内容": "118",
    "Sub-118-C 标题双内容": "118",
    "Sub-118-D 标题内容单按钮": "118",
    "Sub-140-A 核心居中": "140",
    "Sub-140-B 标题单内容": "140",
    "Sub-140-C 标题内容单按钮": "140",
    "Sub-140-D 标题双列内容可选按钮": "140",
    "Sub-140-E 上下双信息块": "140",
    "Sub-140-F 标题主次内容单按钮": "140",
    "Sub-140-G 标题双内容": "140",
    "Sub-140-H 内容四宫格": "140",
}

TYPE13_WIDE_SUB_PATTERNS = frozenset({
    "Sub-140-D 标题双列内容可选按钮",
    "Sub-140-E 上下双信息块",
    "Sub-140-H 内容四宫格",
})

LAYOUT_PATTERN_2X2_NAMES = tuple(LAYOUT_PATTERN_2X2_CODES)
LAYOUT_PATTERN_2X4_NAMES = tuple(LAYOUT_PATTERN_2X4_CODES)
SUB_PATTERN_2X4_NAMES = tuple(SUB_PATTERN_2X4_GROUPS)

_LAYOUT_PATTERN_2X2_NAMES_BY_CODE = {
    code: name for name, code in LAYOUT_PATTERN_2X2_CODES.items()
}
_LAYOUT_PATTERN_2X4_NAMES_BY_CODE = {
    code: name for name, code in LAYOUT_PATTERN_2X4_CODES.items()
}


def layout_pattern_name(size: str, code: str) -> str:
    names = (
        _LAYOUT_PATTERN_2X2_NAMES_BY_CODE
        if size == "2x2"
        else _LAYOUT_PATTERN_2X4_NAMES_BY_CODE
    )
    return names.get(code, code)

_TWO_BY_TWO_TITLE_TYPES = frozenset({"1", "2", "10-A", "10-B", "10-C", "11-A", "12", "14"})
_TWO_BY_TWO_NO_TITLE_TYPES = frozenset({"0", "3", "6", "15"})


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
        return ['2x4 layout "四槽宫格" requires four valid CardButton/InfoBlock slots in a two-column Grid']
    if kinds[0] != kinds[2] or kinds[1] != kinds[3]:
        return [
            '2x4 layout "四槽宫格" mixed CardButton/InfoBlock slots must use '
            "the same component type within each column"
        ]
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


def declared_2x2_layout_errors(root: Any, pattern: str | None) -> list[str]:
    """Validate only the topology made definite by an explicit 2x2 pattern."""
    if pattern not in TOP_LEVEL_2X2_TYPES:
        return []
    descendants = _descendants(root.child_elements())
    errors: list[str] = []
    title_count = sum(
        node.tag in {"SingleLineTitle", "DoubleLineTitle"}
        for node in descendants
    )
    pattern_name = layout_pattern_name("2x2", pattern)
    if pattern in _TWO_BY_TWO_TITLE_TYPES and title_count != 1:
        errors.append(f'2x2 layout "{pattern_name}" requires exactly one title component')
    if pattern in _TWO_BY_TWO_NO_TITLE_TYPES and title_count:
        errors.append(f'2x2 layout "{pattern_name}" does not provide a title slot')
    if pattern == "12":
        children = root.child_elements()
        title_slots = []
        for child in children:
            if child.tag != "Stack":
                continue
            for node in _descendants([child]):
                if node.tag in {"SingleLineTitle", "DoubleLineTitle"}:
                    title_slots.append(child)
                    break
        if len(title_slots) == 1:
            title_slot = title_slots[0]
            if title_slot.props.get("height") != 18:
                errors.append('2x2 layout "双列内容单按钮" requires a fixed 18vp title slot')
            title_nodes = [
                node
                for node in _descendants([title_slot])
                if node.tag in {"SingleLineTitle", "DoubleLineTitle"}
            ]
            if any(node.tag != "SingleLineTitle" for node in title_nodes):
                errors.append('2x2 layout "双列内容单按钮" requires SingleLineTitle')

        button_slots = []
        for child in children:
            if child.tag != "Stack":
                continue
            for node in _descendants([child]):
                if node.tag == "PillButton":
                    button_slots.append(child)
                    break
        if len(button_slots) > 1:
            errors.append('2x2 layout "双列内容单按钮" allows at most one PillButton slot')
        elif button_slots:
            button_slot = button_slots[0]
            if button_slot.props.get("height") != 36 or button_slot.props.get("width") != "full":
                errors.append(
                    '2x2 layout "双列内容单按钮" PillButton slot must be 136 × 36vp'
                )

        structural_slots = [
            child for child in children if child not in title_slots and child not in button_slots
        ]
        if len(structural_slots) != 1:
            errors.append('2x2 layout "双列内容单按钮" requires one adaptive two-column content region')
        else:
            content = structural_slots[0]
            columns = content.child_elements()
            valid_content = (
                content.tag == "Stack"
                and content.props.get("direction") == "row"
                and content.props.get("flex") == 1
            )
            if valid_content:
                valid_content = content.props.get("gap") == 8 and len(columns) == 2
            if valid_content:
                valid_content = not any(column.tag != "Stack" for column in columns)
            if valid_content:
                valid_content = not any(column.props.get("width") != 64 for column in columns)
            if valid_content:
                valid_content = not any(column.props.get("height") != "full" for column in columns)
            if not valid_content:
                errors.append(
                    '2x2 layout "双列内容单按钮" requires two 64vp fixed-width columns '
                    'with gap={8} inside a flex={1} content region'
                )
    return list(dict.fromkeys(errors))


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
            if width is None or width == "full":
                if _finite_number(grid_width) and _finite_number(gap):
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
    pattern_name = layout_pattern_name("2x4", pattern)
    if pattern == "12" and any(node.tag == "InfoBlock" for node in descendants):
        errors.append(f'2x4 layout "{pattern_name}" does not provide an InfoBlock slot')
    return errors


def _type13_parent_errors(
    root: Any,
    wide_regions: frozenset[str] = frozenset(),
) -> list[str]:
    children = root.child_elements()
    if not (
        root.props.get("direction") == "row"
        and len(children) == 2
        and all(child.tag == "Stack" for child in children)
    ):
        return []
    errors: list[str] = []
    for index, child in enumerate(children):
        region = "left" if index == 0 else "right"
        if region in wide_regions:
            if child.props.get("surface") == "backplate":
                errors.append(
                    f'2x4 layout "左右双区" {region} Sub-140 region must not use a backplate'
                )
        elif child.props.get("surface") != "backplate":
            errors.append(
                f'2x4 layout "左右双区" {region} Sub-118 region requires a backplate'
            )
        for axis, expected in (("width", 142), ("height", 136)):
            value = preferred_axis_size(child, root, axis)
            if _finite_number(value) and value != expected:
                errors.append(
                    f'2x4 layout "左右双区" parent {axis} must be {expected}vp; found {value}vp'
                )
        if any(node.props.get("position") == "absolute" for node in _descendants(child.child_elements())):
            errors.append('2x4 layout "左右双区" subpatterns must use normal flow, not absolute positioning')
    gap = root.props.get("gap", 0)
    if _finite_number(gap) and gap != 12:
        errors.append('2x4 layout "左右双区" parent regions require a 12vp horizontal gap')
    return errors


def declared_layout_errors(
    root: Any,
    pattern: str | None,
    *,
    type13_wide_regions: frozenset[str] = frozenset(),
) -> list[str]:
    """Check only explicitly declared patterns and unambiguous JSX structures."""
    if pattern not in TOP_LEVEL_2X4_TYPES:
        return []
    errors = _component_region_errors(root, pattern)
    public_title_slots = 0
    for child in root.child_elements():
        if child.tag == "Stack" and root.props.get("direction", "column") != "column":
            # A title inside a horizontal region is local, not a public header.
            continue
        content = child.child_elements() if child.tag == "Stack" else [child]
        title_tags = {"SingleLineTitle", "DoubleLineTitle"}
        if (
            any(node.tag in title_tags for node in content)
            and all(node.tag in title_tags | {"Badge"} for node in content)
        ):
            public_title_slots += 1
    if pattern == "12":
        if public_title_slots != 1:
            errors.append('2x4 layout "上下双区" requires exactly one public title slot')
    elif public_title_slots:
        errors.append(
            "only 2x4 layout \"上下双区\" allows a public title slot; "
            "use a local sublayout title"
        )
    if pattern == "13":
        errors.extend(_type13_parent_errors(root, type13_wide_regions))
    return list(dict.fromkeys(errors))
