"""Structural layout rules; never infer a layout pattern from business text."""

from __future__ import annotations

import math
import re
from typing import Any

TOP_LEVEL_2X2_TYPES = frozenset(
    {"0", "1", "2", "3", "6", "10-A", "10-B", "12", "14", "15"}
)
TOP_LEVEL_2X4_TYPES = frozenset({"12", "13", "14", "15"})
FIXED_SLOT_COMPONENTS = frozenset({"CardButton", "InfoBlock"})

# Public names are the exact labels exposed to the generation model. The
# historical numeric codes stay internal so the existing geometry validators
# do not need to duplicate their rules under a second naming system.
LAYOUT_PATTERN_2X2_CODES = {
    "核心居中": "0",
    "标题单内容": "1",
    "双信息块": "3",
    "标题双内容": "2",
    "内容四宫格": "6",
    "标题内容单按钮": "10-A",
    "标题主次内容单按钮": "10-B",
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

_TWO_BY_TWO_TITLE_TYPES = frozenset({"1", "2", "10-A", "10-B", "12", "14"})
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


def _stack_matches(node: Any, expected: dict[str, Any]) -> bool:
    if node.tag != "Stack":
        return False
    for prop, value in expected.items():
        if node.props.get(prop) != value:
            return False
    return True


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
    children = root.child_elements()
    title_slots = []
    for child in children:
        if child.tag != "Stack":
            continue
        for node in _descendants([child]):
            if node.tag in {"SingleLineTitle", "DoubleLineTitle"}:
                title_slots.append(child)
                break
    if pattern == "1":
        content_slots = [child for child in children if child not in title_slots]
        if len(title_slots) != 1 or len(content_slots) != 1:
            errors.append('2x2 layout "标题单内容" requires one title slot and one content region')
        else:
            content = content_slots[0]
            if not _stack_matches(content, {
                "flex": 1, "width": "full", "align": "flex-start", "justify": "flex-end",
            }):
                errors.append(
                    '2x2 layout "标题单内容" content region must use flex={1}, '
                    'width="full", align="flex-start" and justify="flex-end"'
                )
    if pattern == "15":
        non_compact_progress_circles = [
            node
            for node in descendants
            if node.tag == "ProgressCircleSingle" and node.props.get("size") != "compact"
        ]
        if non_compact_progress_circles:
            errors.append(
                '2x2 layout "紧凑内容双按钮" requires every ProgressCircleSingle '
                'to explicitly declare size="compact"'
            )
        button_slots = []
        for child in children:
            if child.tag != "Stack":
                continue
            for node in _descendants([child]):
                if node.tag == "PillButton":
                    button_slots.append(child)
                    break
        content_slots = [child for child in children if child not in button_slots]
        pill_buttons = [node for node in descendants if node.tag == "PillButton"]
        other_buttons = [
            node for node in descendants if node.tag in {"CircleButton", "CardButton"}
        ]
        if len(button_slots) != 2 or len(pill_buttons) != 2 or other_buttons:
            errors.append(
                '2x2 layout "紧凑内容双按钮" requires exactly two PillButton slots'
            )
        elif any(
            slot.props.get("flex") != 0
            or slot.props.get("height") != 36
            or slot.props.get("width") != "full"
            for slot in button_slots
        ):
            errors.append(
                '2x2 layout "紧凑内容双按钮" requires two 136 × 36vp '
                'flex={0} PillButton slots'
            )
        if len(content_slots) != 1 or not children or content_slots[0] is not children[0]:
            errors.append(
                '2x2 layout "紧凑内容双按钮" requires one leading adaptive content region'
            )
        else:
            content = content_slots[0]
            if (
                not _stack_matches(content, {
                    "flex": 1, "width": "full", "align": "flex-start", "justify": "flex-start",
                })
                or root.props.get("gap") != 8
            ):
                errors.append(
                    '2x2 layout "紧凑内容双按钮" content region must use flex={1}, '
                    'width="full", align="flex-start", justify="flex-start" and Card gap={8}'
                )
    if pattern == "12":
        if len(title_slots) == 1:
            title_slot = title_slots[0]
            if title_slot.props.get("flex") != 0 or title_slot.props.get("height") not in {None, "auto"}:
                errors.append(
                    '2x2 layout "双列内容单按钮" requires a flex={0} natural-height title slot'
                )
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
            else:
                column_components = [
                    [
                        node
                        for node in _descendants(column.child_elements())
                        if node.tag not in {"Stack", "Grid"}
                    ]
                    for column in columns
                ]
                if any(
                    len(components) != 1
                    or components[0].tag != "ProgressCircle"
                    or components[0].props.get("size", "sm") != "sm"
                    for components in column_components
                ):
                    errors.append(
                        '2x2 layout "双列内容单按钮" only allows exactly two '
                    'ProgressCircle size="sm" components, one in each column'
                )
    if pattern == "14":
        content_slots = [child for child in children if child not in title_slots]
        if len(title_slots) != 1 or len(content_slots) != 1:
            errors.append('2x2 layout "标题锚点内容" requires one title slot and one content region')
        else:
            content = content_slots[0]
            content_children = content.child_elements() if content.tag == "Stack" else []
            valid_content = (
                content.tag == "Stack"
                and content.props.get("direction", "column") == "column"
                and content.props.get("flex") == 1
                and content.props.get("width") == "full"
                and content.props.get("gap") == 8
                and len(content_children) == 2
            )
            if not valid_content:
                errors.append(
                    '2x2 layout "标题锚点内容" requires a flex={1} content region '
                    'with Hero, bottom row and gap={8}'
                )
            else:
                hero, bottom = content_children
                bottom_children = bottom.child_elements() if bottom.tag == "Stack" else []
                valid_hero = (
                    hero.tag == "Stack"
                    and hero.props.get("flex") == 1
                    and hero.props.get("width") == "full"
                )
                valid_bottom = (
                    bottom.tag == "Stack"
                    and bottom.props.get("direction") == "row"
                    and bottom.props.get("width") == "full"
                    and bottom.props.get("minHeight") == 40
                    and bottom.props.get("gap") == 8
                    and bottom.props.get("align") == "flex-end"
                    and len(bottom_children) == 2
                )
                if not valid_hero or not valid_bottom:
                    errors.append(
                        '2x2 layout "标题锚点内容" requires an adaptive Hero and a '
                        'bottom-aligned 88 + 8 + 40vp row'
                    )
                else:
                    secondary, action = bottom_children
                    circle_buttons = [
                        node for node in _descendants(action.child_elements())
                        if node.tag == "CircleButton"
                    ]
                    if (
                        not _stack_matches(secondary, {
                            "width": 88, "align": "flex-start", "justify": "flex-end",
                        })
                        or not _stack_matches(action, {
                            "width": 40, "height": 40, "align": "center", "justify": "center",
                        })
                        or len(circle_buttons) != 1
                    ):
                        errors.append(
                            '2x2 layout "标题锚点内容" requires an 88vp secondary region, '
                            'an 8vp gap and one centered CircleButton in a 40 × 40vp slot'
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
