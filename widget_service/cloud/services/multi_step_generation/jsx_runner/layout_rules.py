"""Structural layout rules; never infer a layout pattern from business text."""

from __future__ import annotations

import math
import re
from typing import Any

TOP_LEVEL_2X2_TYPES = frozenset(
    {"0", "1", "2", "3", "6", "10-A", "10-B", "12", "14", "15"}
)
TOP_LEVEL_2X4_TYPES = frozenset({"12", "13", "14", "15", "15-R"})
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
    "标题双列内容可选按钮": "12",
    "标题锚点内容": "14",
    "紧凑内容双按钮": "15",
}
LAYOUT_PATTERN_2X4_CODES = {
    "上下双区": "12",
    "左右双区": "13",
    "四槽宫格": "14",
    "左内容右侧双槽": "15",
    "左侧双槽右内容": "15-R",
}
SUB_PATTERN_2X4_GROUPS = {
    "Sub-118-A 核心居中": "118",
    "Sub-118-B 标题单内容": "118",
    "Sub-118-C 标题双内容": "118",
    "Sub-118-D 标题内容单按钮": "118",
    "Sub-118-E 标题双列内容可选按钮": "118",
    "Sub-118-F 内容双按钮": "118",
    "Sub-140-A 核心居中": "140",
    "Sub-140-B 标题单内容": "140",
    "Sub-140-C 标题内容单按钮": "140",
    "Sub-140-D 标题双列内容可选按钮": "140",
    "Sub-140-E 上下双信息块": "140",
    "Sub-140-F 标题主次内容单按钮": "140",
    "Sub-140-G 标题双内容": "140",
    "Sub-140-H 内容四宫格": "140",
    "Sub-140-I 标题双列内容可选按钮": "140",
    "Sub-140-J 内容双按钮": "140",
}

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


def is_fixed_slot_column(node: Any) -> bool:
    children = node.child_elements()
    return (
        node.tag == "Stack"
        and node.props.get("width") == 132
        and node.props.get("height") == 126
        and node.props.get("direction", "column") == "column"
        and node.props.get("gap") == 12
        and len(children) == 2
        and all(fixed_slot_kind(child) is not None for child in children)
    )


def fixed_grid_errors(children: list[Any], columns: int | None) -> list[str]:
    kinds = [fixed_slot_kind(child) for child in children]
    if columns != 2 or len(kinds) != 4 or any(kind is None for kind in kinds):
        return ['2x4 layout "四槽宫格" requires four valid CardButton/InfoBlock slots in a two-column Grid']
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
    allowed_horizontal_business_rows: set[int] = set()
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
    if pattern in {"1", "2", "14"} and root.props.get("gap") != 6:
        errors.append(f'2x2 layout "{pattern_name}" requires a 6vp title-to-content gap')
    if pattern in {"10-A", "10-B"}:
        valid_title = (
            len(title_slots) == 1
            and len(children) == 2
            and title_slots[0] is children[0]
            and title_slots[0].props.get("flex", 0) == 0
            and title_slots[0].props.get("mb", 0) == 0
            and root.props.get("gap") == 6
        )
        if not valid_title:
            errors.append(
                f'2x2 layout "{pattern_name}" requires Card gap={{6}}, one leading '
                'flex={0} title slot, no title mb, and one following action body'
            )
        action_body = children[1] if len(children) == 2 else None
        body_children = (
            action_body.child_elements()
            if action_body is not None and action_body.tag == "Stack"
            else []
        )
        valid_body = (
            action_body is not None
            and action_body.tag == "Stack"
            and action_body.props.get("flex") == 1
            and action_body.props.get("width") == "full"
            and action_body.props.get("gap") == 8
            and action_body.props.get("mb", 0) == 0
            and len(body_children) == 2
        )
        if not valid_body:
            errors.append(
                f'2x2 layout "{pattern_name}" action body must use flex={{1}}, '
                'width="full", gap={8}, no mb, and contain content plus the button slot'
            )
        else:
            content, button_slot = body_children
            valid_content = _stack_matches(content, {
                "flex": 1,
                "width": "full",
                "align": "flex-start",
                "justify": "flex-start",
            }) and content.props.get("mb", 0) == 0
            if pattern == "10-B":
                content_children = content.child_elements() if content.tag == "Stack" else []
                valid_content = (
                    valid_content
                    and content.props.get("gap") == 2
                    and len(content_children) == 2
                    and all(
                        child.tag == "Stack"
                        and child.props.get("flex", 0) == 0
                        and child.props.get("width") == "full"
                        for child in content_children
                    )
                )
            if not valid_content:
                detail = (
                    'a flex={1}, width="full", gap={2} content group with two '
                    'flex={0} full-width content slots'
                    if pattern == "10-B"
                    else 'a flex={1}, width="full" content region'
                )
                errors.append(
                    f'2x2 layout "{pattern_name}" requires {detail}, aligned '
                    'to flex-start with no mb'
                )
            button_descendants = _descendants([button_slot])
            all_buttons = [
                node for node in descendants
                if node.tag in {"PillButton", "CircleButton", "CardButton"}
            ]
            invalid_button_slot = (
                button_slot.tag != "Stack"
                or button_slot.props.get("flex", 0) != 0
                or button_slot.props.get("height") != 36
            )
            if not invalid_button_slot:
                invalid_button_slot = (
                    button_slot.props.get("width") != "full"
                    or sum(node.tag == "PillButton" for node in button_descendants) != 1
                    or len(all_buttons) != 1
                )
            if invalid_button_slot or all_buttons[0].tag != "PillButton":
                errors.append(
                    f'2x2 layout "{pattern_name}" requires exactly one PillButton '
                    'in the final 126 × 36vp flex={0} full-width slot'
                )
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
    if pattern == "3":
        info_blocks = [node for node in descendants if node.tag == "InfoBlock"]
        valid_slots = (
            root.props.get("padding") == 8
            and root.props.get("gap") == 8
            and len(children) == 2
            and all(
                child.tag == "Stack"
                and child.props.get("flex") == 0
                and child.props.get("width") == "full"
                and child.props.get("height") == 63
                and sum(node.tag == "InfoBlock" for node in _descendants([child])) == 1
                for child in children
            )
        )
        if len(info_blocks) != 2 or not valid_slots:
            errors.append(
                '2x2 layout "双信息块" requires padding={8}, gap={8}, and two '
                '134 × 63vp InfoBlock slots'
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
                '2x2 layout "紧凑内容双按钮" requires two 126 × 36vp '
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
        invalid_title_slot = (
            len(title_slots) != 1
            or title_slots[0].props.get("mb") != 6
            or title_slots[0].props.get("flex", 0) != 0
        )
        if not invalid_title_slot:
            invalid_title_slot = (
                title_slots[0].props.get("width") != "full"
                or not children
                or title_slots[0] is not children[0]
            )
        if invalid_title_slot:
            errors.append(
                '2x2 layout "标题双列内容可选按钮" requires one leading flex={0}, '
                'width="full" title slot with mb={6}'
            )
        type12_titles = [
            node for node in descendants if node.tag in {"SingleLineTitle", "DoubleLineTitle"}
        ]
        if len(type12_titles) != 1 or type12_titles[0].tag != "SingleLineTitle":
            errors.append(
                '2x2 layout "标题双列内容可选按钮" requires exactly one SingleLineTitle'
            )
        if root.props.get("gap", 0) != 0:
            errors.append(
                '2x2 layout "标题双列内容可选按钮" uses gap={0}; spacing is owned by slots'
            )
        button_slots = []
        pill_buttons = [node for node in descendants if node.tag == "PillButton"]
        for child in children:
            if child.tag != "Stack":
                continue
            for node in _descendants([child]):
                if node.tag == "PillButton":
                    button_slots.append(child)
                    break
        if len(button_slots) > 1 or len(pill_buttons) > 1:
            errors.append('2x2 layout "标题双列内容可选按钮" allows at most one PillButton slot')
        elif button_slots:
            button_slot = button_slots[0]
            invalid_button_geometry = (
                button_slot.props.get("flex", 0) != 0
                or button_slot.props.get("height") != 36
                or button_slot.props.get("width") != "full"
            )
            if invalid_button_geometry or button_slot is not children[-1]:
                errors.append(
                    '2x2 layout "标题双列内容可选按钮" PillButton slot must be the final '
                    '126 × 36vp flex={0} block'
                )
        other_buttons = [
            node for node in descendants if node.tag in {"CircleButton", "CardButton"}
        ]
        if other_buttons:
            errors.append(
                '2x2 layout "标题双列内容可选按钮" only supports an optional PillButton'
            )

        structural_slots = [
            child for child in children if child not in button_slots and child not in title_slots
        ]
        if len(structural_slots) != 1:
            errors.append('2x2 layout "标题双列内容可选按钮" requires one adaptive two-column content region')
        else:
            content = structural_slots[0]
            allowed_horizontal_business_rows.add(id(content))
            columns = content.child_elements()
            valid_content = (
                content.tag == "Stack"
                and content.props.get("direction") == "row"
                and content.props.get("flex") == 1
                and content.props.get("width") == "full"
                and content.props.get("mb", 0) == (8 if button_slots else 0)
            )
            if valid_content:
                valid_content = (
                    content.props.get("gap") == 8
                    and len(columns) == 2
                )
            if valid_content:
                valid_content = not any(column.tag != "Stack" for column in columns)
            if valid_content:
                valid_content = not any(
                    column.props.get("flex", 0) != 0 or column.props.get("width") != 59
                    for column in columns
                )
            if valid_content:
                valid_content = not any(column.props.get("height") != "full" for column in columns)
            if not valid_content:
                errors.append(
                    '2x2 layout "标题双列内容可选按钮" requires two adaptive-height '
                    '59vp fixed-width columns with gap={8}; content mb={8} only when the button exists'
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
                    or components[0].props.get("size") != "sm"
                    for components in column_components
                ):
                    errors.append(
                        '2x2 layout "标题双列内容可选按钮" requires exactly one '
                        'ProgressCircle size="sm" in each 59vp column'
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
                allowed_horizontal_business_rows.add(id(bottom))
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
                        'bottom-aligned 78 + 8 + 40vp row'
                    )
                else:
                    secondary, action = bottom_children
                    circle_buttons = [
                        node for node in _descendants(action.child_elements())
                        if node.tag == "CircleButton"
                    ]
                    if (
                        not _stack_matches(secondary, {
                            "width": 78, "align": "flex-start", "justify": "flex-end",
                        })
                        or not _stack_matches(action, {
                            "width": 40, "height": 40, "align": "center", "justify": "center",
                        })
                        or len(circle_buttons) != 1
                    ):
                        errors.append(
                            '2x2 layout "标题锚点内容" requires a 78vp secondary region, '
                            'an 8vp gap and one centered CircleButton in a 40 × 40vp slot'
                        )
    for node in descendants:
        if (
            node.tag != "Stack"
            or node.props.get("direction", "column") != "row"
            or id(node) in allowed_horizontal_business_rows
        ):
            continue
        row_business_components = [
            descendant
            for descendant in _descendants(node.child_elements())
            if descendant.tag not in {"Card", "Stack", "Grid"}
        ]
        # A title row is not a content region. Badge is explicitly documented
        # as a title companion, so the generic horizontal-content prohibition
        # must not reject SingleLineTitle/DoubleLineTitle + Badge groups.
        title_components = [
            descendant
            for descendant in row_business_components
            if descendant.tag in {"SingleLineTitle", "DoubleLineTitle"}
        ]
        badges = [
            descendant for descendant in row_business_components if descendant.tag == "Badge"
        ]
        if (
            len(title_components) == 1
            and len(badges) <= 1
            and len(row_business_components) == len(title_components) + len(badges)
        ):
            continue
        business_by_branch = [
            [
                descendant
                for descendant in _descendants([child])
                if descendant.tag not in {"Card", "Stack", "Grid"}
            ]
            for child in node.child_elements()
        ]
        if (
            sum(bool(branch) for branch in business_by_branch) >= 2
            and sum(len(branch) for branch in business_by_branch) >= 2
        ):
            errors.append(
                "a 2x2 content region cannot place two business components side by side "
                'in a direction="row" Stack; use a documented vertical layout. Only '
                'the two ProgressCircle columns in "标题双列内容可选按钮" and the 88 + 8 + '
                '40vp secondary/CircleButton row in "标题锚点内容" are allowed'
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
        if (
            container.tag != "Grid"
            and not is_fixed_slot_column(container)
            and fixed_slot_kind(child) != "CardButton"
        ):
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
        for axis, value, expected in (("width", width, 132), ("height", height, 57)):
            if _finite_number(value) and value != expected:
                errors.append(f"2x4 fixed slot {axis} must be {expected}vp; found {value}vp")
    return list(dict.fromkeys(errors))


def _component_region_errors(root: Any, pattern: str) -> list[str]:
    errors: list[str] = []
    children = root.child_elements()
    descendants = _descendants(children)
    pattern_name = layout_pattern_name("2x4", pattern)
    if pattern in {"12", "13"} and any(node.tag == "InfoBlock" for node in descendants):
        errors.append(f'2x4 layout "{pattern_name}" does not provide an InfoBlock slot')
    if pattern in {"12", "13"} and any(node.tag == "CardButton" for node in descendants):
        errors.append(f'2x4 layout "{pattern_name}" does not provide a CardButton fixed slot')
    return errors


def _type13_parent_errors(
    root: Any,
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
        if child.props.get("surface") != "backplate":
            errors.append(
                f'2x4 layout "左右双区" {region} Sub-118 region requires a backplate'
            )
        for axis, expected in (("width", 132), ("height", 126)):
            value = preferred_axis_size(child, root, axis)
            if _finite_number(value) and value != expected:
                errors.append(
                    f'2x4 layout "左右双区" parent {axis} must be {expected}vp; found {value}vp'
                )
        if any(node.props.get("position") == "absolute" for node in _descendants(child.child_elements())):
            errors.append('2x4 layout "左右双区" subpatterns must use normal flow, not absolute positioning')
        inner = child.child_elements()
        if len(inner) != 1 or inner[0].tag != "Stack":
            errors.append(
                f'2x4 layout "左右双区" {region} backplate requires one 116 × 110vp Sub-118 container'
            )
            continue
        content = inner[0]
        if content.props.get("width") != 116 or content.props.get("height") != 110:
            errors.append(
                f'2x4 layout "左右双区" {region} backplate content must be 116 × 110vp '
                "to preserve the 8vp safe inset"
            )
        local_titles = [
            node for node in _descendants(content.child_elements())
            if node.tag in {"SingleLineTitle", "DoubleLineTitle"}
        ]
        if local_titles:
            title_slot = None
            for slot in content.child_elements():
                if any(
                    node.tag in {"SingleLineTitle", "DoubleLineTitle"}
                    for node in _descendants([slot])
                ):
                    title_slot = slot
                    break
            if title_slot is None or title_slot.props.get("mb") != 4:
                # Direct JSX may express the same spacing as the container gap;
                # semantic lowering uses title-slot mb={4}.
                if content.props.get("gap") != 4:
                    errors.append(
                        f'2x4 layout "左右双区" {region} title-to-first-content gap must be 4vp'
                    )
    gap = root.props.get("gap", 0)
    if _finite_number(gap) and gap != 12:
        errors.append('2x4 layout "左右双区" parent regions require a 12vp horizontal gap')
    return errors


def declared_layout_errors(
    root: Any,
    pattern: str | None,
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
        if public_title_slots > 1:
            errors.append('2x4 layout "上下双区" allows at most one public title slot')
        if public_title_slots == 1 and root.props.get("gap") != 6:
            errors.append('2x4 layout "上下双区" title-to-first-content gap must be 6vp')
    elif public_title_slots:
        errors.append(
            "only 2x4 layout \"上下双区\" allows a public title slot; "
            "use a local sublayout title"
        )
    if pattern == "13":
        errors.extend(_type13_parent_errors(root))
    return list(dict.fromkeys(errors))
