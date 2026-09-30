# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.two_by_four。"""

from __future__ import annotations

from typing import Any

from services.card_validation.compact_validation.context import (
    _descendant_components,
    _descendant_on_click_count,
    _descendant_type_count,
    component_graph,
)
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.schema import (
    _NUMERIC_SCHEMA_TYPES,
    _schema_node_at_path,
    _schema_type,
    _task_spec_data_roots,
)
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _TWO_BY_FOUR_MULTI_INNER_WIDTH,
    _horizontal_padding_at_least,
)
from services.card_validation.compact_validation.semantic.layout.regions import (
    _has_expected_two_by_four_aux_icon_layout,
    _is_two_by_four_direct_action,
    _is_two_by_four_focus_aux_cell,
)
from services.card_validation.compact_validation.text import (
    _COMMON_DISPLAY_UNITS,
    _component_content_paths,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_two_by_four_small_backboard_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    for backboard in components:
        dimensions = (
            backboard.props.get("width"),
            backboard.props.get("height"),
        )
        if dimensions != (138, 63):
            continue
        descendants = _descendant_components(backboard, components_by_id)
        text_count = sum(component.component_type == "Text" for component in descendants)
        if text_count > 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X4_SMALL_TEXT_COUNT",
                    validation_class="semantic",
                    category="layout",
                    message="小背板包含过多文本节点。",
                    expected={
                        "maximumTextCount": 2,
                        "roles": ["主要信息", "辅助信息"],
                        "clipThirdLineAllowed": False,
                    },
                    actual={"textCount": text_count},
                    component_id=backboard.component_id,
                    legacy_message=(
                        f"2x4 small backboard {backboard.component_id} may contain at "
                        "most two Text nodes. Keep one primary line and one supporting "
                        "line instead of clipping a third line."
                    ),
                ),
            )
        has_visual = any(
            component.component_type in {"Image", "Progress", "Stack"} for component in descendants
        )
        if has_visual:
            if backboard.component_type != "Row":
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_2X4_SMALL_VISUAL_ROW",
                        validation_class="semantic",
                        category="layout",
                        message="带视觉元素的小背板未使用横向排列。",
                        expected={
                            "componentType": "Row",
                            "textSide": "left",
                            "visualSide": "right",
                        },
                        actual=backboard.component_type,
                        component_id=backboard.component_id,
                        legacy_message=(
                            f"2x4 small backboard {backboard.component_id} with a visual "
                            "must use Row so its text stays on the left and the visual "
                            "stays on the right."
                        ),
                    ),
                )
            continue
        if backboard.component_type != "Column":
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X4_SMALL_TEXT_COLUMN",
                    validation_class="semantic",
                    category="layout",
                    message="无视觉元素的小背板未使用纵向排列。",
                    expected={"componentType": "Column", "sideBySideTextAllowed": False},
                    actual=backboard.component_type,
                    component_id=backboard.component_id,
                    legacy_message=(
                        f"2x4 small backboard {backboard.component_id} without a visual "
                        "must use Column; do not place two Text nodes side by side where "
                        "the second line can be clipped."
                    ),
                ),
            )
        elif backboard.props.get("justifyContent") != "center":
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X4_SMALL_TEXT_ALIGNMENT",
                    validation_class="semantic",
                    category="layout",
                    message="无视觉元素的小背板未将文字垂直居中。",
                    expected={"justifyContent": "center"},
                    actual=backboard.props.get("justifyContent"),
                    component_id=backboard.component_id,
                    property_path="/justifyContent",
                    legacy_message=(
                        f"2x4 small backboard {backboard.component_id} without a visual "
                        "must vertically center its one or two Text lines."
                    ),
                ),
            )


def _collect_two_by_four_action_backboard_errors(
    backboard: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    actions: list[ComponentRow] = []
    for child_id in backboard.children:
        child = components_by_id.get(child_id)
        if _is_two_by_four_direct_action(child):
            actions.append(child)
    if len(actions) != 1:
        return

    action = actions[0]
    if not backboard.children or backboard.children[-1] != action.component_id:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_ACTION_ORDER",
                validation_class="semantic",
                category="layout",
                message="大背板的动作不是最后一个直接子节点。",
                expected={"lastDirectChild": action.component_id},
                actual=backboard.children,
                component_id=backboard.component_id,
                property_path="/children",
                legacy_message=(
                    f"2x4 large backboard {backboard.component_id} must place its action "
                    "as the final direct child."
                ),
            ),
        )
    if (
        action.props.get("width") != _TWO_BY_FOUR_MULTI_INNER_WIDTH
        or action.props.get("height") != 36
    ):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_ACTION_SIZE",
                validation_class="semantic",
                category="layout",
                message="大背板的动作尺寸不符合要求。",
                expected={"width": _TWO_BY_FOUR_MULTI_INNER_WIDTH, "height": 36},
                actual={"width": action.props.get("width"), "height": action.props.get("height")},
                component_id=action.component_id,
                legacy_message=(
                    f"2x4 large backboard {backboard.component_id} action must be "
                    f"{_TWO_BY_FOUR_MULTI_INNER_WIDTH}x36."
                ),
            ),
        )
    if action.component_type == "Row":
        _collect_two_by_four_action_row_errors(action, errors)

    content_ids = backboard.children[:-1]
    if len(content_ids) != 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_ACTION_STRUCTURE",
                validation_class="semantic",
                category="layout",
                message="大背板的直接子节点没有采用内容加动作的结构。",
                expected={"directChildren": ["content", action.component_type], "count": 2},
                actual=backboard.children,
                component_id=backboard.component_id,
                property_path="/children",
                legacy_message=(
                    f"2x4 large backboard {backboard.component_id} with a Button must "
                    "have exactly [content, Button] as direct children."
                ),
            ),
        )
        return
    content = components_by_id.get(content_ids[0])
    if content is None or content.component_type != "Column":
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_CONTENT_TYPE",
                validation_class="semantic",
                category="layout",
                message="大背板的内容不是有效的 Column。",
                expected={"contentComponentType": "Column"},
                component_id=backboard.component_id,
                legacy_message=(
                    f"2x4 large backboard {backboard.component_id} content must be a Column."
                ),
            ),
        )
        return
    if content.props.get("layoutWeight") != 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_CONTENT_WEIGHT",
                validation_class="semantic",
                category="layout",
                message="大背板内容未按剩余空间伸缩。",
                expected={"layoutWeight": 1, "buttonRemainsAtBottom": True},
                actual=content.props.get("layoutWeight"),
                component_id=content.component_id,
                property_path="/layoutWeight",
                legacy_message=(
                    f"2x4 large backboard {backboard.component_id} content must use "
                    "layoutWeight 1 so the Button stays at the bottom."
                ),
            ),
        )
    if _descendant_type_count(content, components_by_id, "Text") > 4:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_TEXT_BUDGET",
                validation_class="semantic",
                category="layout",
                message="带按钮的大背板内容超过文本预算。",
                expected={"maximumTextCount": 4, "maximumVisualRows": 3},
                component_id=content.component_id,
                legacy_message=(
                    f"2x4 large backboard {backboard.component_id} with a Button may "
                    "contain at most four Text nodes across no more than three visual "
                    "rows. Merge or remove lower-priority fields."
                ),
            ),
        )


def _collect_two_by_four_action_row_errors(
    action: ComponentRow,
    errors: list[str],
) -> None:
    props = action.props
    valid_layout = (
        props.get("itemMargin") == 8
        and props.get("justifyContent") == "center"
        and props.get("alignItems") == "center"
        and _horizontal_padding_at_least(props, 8)
    )
    if valid_layout:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_2X4_ACTION_ROW_LAYOUT",
            validation_class="semantic",
            category="layout",
            message="图文动作的间距、内边距或居中方式不符合要求。",
            expected={
                "itemMargin": 8,
                "minimumHorizontalPadding": 8,
                "justifyContent": "center",
                "alignItems": "center",
            },
            actual=props,
            component_id=action.component_id,
            legacy_message=(
                f"2x4 graphical action Row {action.component_id} must use itemMargin 8, "
                "at least 8vp left/right padding, justifyContent center, and alignItems "
                "center so its icon and label stay centered."
            ),
        ),
    )


def _collect_two_by_four_full_width_action_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child = component_graph(components).last_parent

    for action in components:
        if not _is_two_by_four_direct_action(action):
            continue
        if action.props.get("width") != 276 or action.props.get("height") != 36:
            continue

        parent = parent_by_child.get(action.component_id)
        is_full_height_foreground = (
            parent is not None
            and parent.component_type == "Column"
            and parent.props.get("width") == "matchParent"
            and parent.props.get("height") == "matchParent"
        )
        if not is_full_height_foreground:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X4_FULL_ACTION_PARENT",
                    validation_class="semantic",
                    category="layout",
                    message="全宽动作未直接放在铺满前景的纵向容器中。",
                    expected={
                        "parentType": "Column",
                        "parentWidth": "matchParent",
                        "parentHeight": "matchParent",
                        "nestedFixedHeightBodyAllowed": False,
                    },
                    component_id=action.component_id,
                    legacy_message=(
                        f"2x4 full-width action {action.component_id} must be a direct "
                        "child of the matchParent foreground Column; do not nest it "
                        "inside a fixed-height main/body container where content can overlap."
                    ),
                ),
            )
            continue

        if parent is None:
            continue
        if not parent.children or parent.children[-1] != action.component_id:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X4_FULL_ACTION_ORDER",
                    validation_class="semantic",
                    category="layout",
                    message="全宽动作不是前景容器的最后一个直接子节点。",
                    expected={"lastDirectChild": action.component_id},
                    actual=parent.children,
                    component_id=parent.component_id,
                    property_path="/children",
                    legacy_message=(
                        f"2x4 full-width action {action.component_id} must be the final "
                        "direct child of foreground Column {parent.component_id}."
                    ),
                ),
            )
            continue
        if len(parent.children) < 2:
            continue
        content = components_by_id.get(parent.children[-2])
        if content is None or content.props.get("layoutWeight") != 1:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X4_FULL_ACTION_CONTENT_WEIGHT",
                    validation_class="semantic",
                    category="layout",
                    message="全宽动作之前的内容没有按剩余空间伸缩。",
                    expected={
                        "precedingContentLayoutWeight": 1,
                        "actionSize": [276, 36],
                        "overlapAllowed": False,
                    },
                    component_id=action.component_id,
                    legacy_message=(
                        f"2x4 content immediately above full-width action "
                        f"{action.component_id} must use layoutWeight 1 so the 276x36 "
                        "action remains fixed at the bottom without overlapping content."
                    ),
                ),
            )


def _collect_two_by_four_aux_icon_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    for cell in components:
        if not _is_two_by_four_focus_aux_cell(cell):
            continue
        cell_components = [cell, *_descendant_components(cell, components_by_id)]
        has_image = any(component.component_type == "Image" for component in cell_components)
        if not has_image:
            continue
        if _has_expected_two_by_four_aux_icon_layout(cell, components_by_id):
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_AUX_ICON_STRUCTURE",
                validation_class="semantic",
                category="layout",
                message="带图标的辅助背板结构不符合要求。",
                expected={
                    "text": "一个单行 Text 或一个含一至两行文本的 Column",
                    "imageCount": 1,
                    "textAlignment": "left",
                    "imageSide": "right",
                    "imageSize": [20, 20],
                },
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 130x59 auxiliary backboard {cell.component_id} with an icon "
                    "must contain exactly one one-line Text or one 1-2 line text Column "
                    "plus one Image. The converter normalizes the cell to left-aligned "
                    "text and a 20x20vp Image on the right."
                ),
            ),
        )


def _collect_two_by_four_detached_unit_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return

    parent_by_child = component_graph(components).last_parent

    for component in components:
        if component.component_type != "Text":
            continue
        numeric_paths: list[str] = []
        for path in _component_content_paths(component):
            schema_node = _schema_node_at_path(data_model_schema, path)
            if _schema_type(schema_node) in _NUMERIC_SCHEMA_TYPES:
                numeric_paths.append(path)
        if len(numeric_paths) != 1:
            continue
        numeric_path = numeric_paths[0]
        if numeric_path.casefold().endswith("/countdowndays"):
            continue
        parent = parent_by_child.get(component.component_id)
        if parent is None or parent.component_type == "Row":
            continue
        detached_unit = None
        for sibling_id in parent.children:
            if sibling_id == component.component_id:
                continue
            sibling = components_by_id.get(sibling_id)
            if sibling is None or sibling.component_type != "Text":
                continue
            sibling_content = sibling.props.get("content")
            if _component_content_paths(sibling):
                continue
            if (
                isinstance(sibling_content, str)
                and sibling_content.strip() in _COMMON_DISPLAY_UNITS
            ):
                detached_unit = sibling
                break
        if detached_unit is None:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_DETACHED_UNIT",
                validation_class="semantic",
                category="layout",
                message="数值与单位没有放在同一行的相邻文本节点中。",
                expected={
                    "sameRowRequired": True,
                    "adjacentTextRequired": True,
                    "alignItems": "bottom",
                    "mixedFontBottomPadding": (
                        "须保留现有混合字号规则要求的底部补偿，不能按旧建议无条件清零"
                    ),
                    "nonCountdownUnitOnNextLineAllowed": False,
                },
                actual={"valueId": component.component_id, "unitId": detached_unit.component_id},
                component_id=component.component_id,
                legacy_message=(
                    f"2x4 numeric value {component.component_id} and unit "
                    f"{detached_unit.component_id} must be adjacent Text children of "
                    "the same Row. Use Row alignItems bottom without bottom padding on "
                    "the smaller Text; do not place a "
                    "non-countdown unit on the next line."
                ),
            ),
        )


def _collect_two_by_four_weather_calendar_alignment_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    if _task_spec_data_roots(task_spec) != {"calendar", "weather"}:
        return

    temperature_texts: list[ComponentRow] = []
    condition_texts: list[ComponentRow] = []
    for component in components:
        if component.component_type != "Text":
            continue
        normalized_paths = [path.casefold() for path in _component_content_paths(component)]
        has_temperature = False
        has_condition = False
        for path in normalized_paths:
            if path.startswith("/data/weather/current/temperature"):
                has_temperature = True
            if path == "/data/weather/current/condition":
                has_condition = True
        if has_temperature and has_condition:
            return
        if has_temperature:
            temperature_texts.append(component)
        if has_condition:
            condition_texts.append(component)

    if not temperature_texts or not condition_texts:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_2X4_WEATHER_CALENDAR_ALIGNMENT",
            validation_class="semantic",
            category="layout",
            message="天气与日程组合中的当前温度与天气状况被拆成了不同文本节点。",
            expected={
                "temperatureAndConditionShareSingleLineText": True,
                "separateFontMetricsAllowed": False,
            },
            legacy_message=(
                "2x4 weather-and-calendar cards must combine current temperature and "
                "condition in one single-line Text, such as 29° · 多云. Do not split "
                "them into separate Text nodes with different font metrics because their "
                "visible baselines will not align."
            ),
        ),
    )


def _collect_two_by_four_countdown_backboard_errors(
    backboard: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    descendants = _descendant_components(backboard, components_by_id)
    countdown_values = []
    for component in descendants:
        if component.component_type != "Text":
            continue
        paths = _component_content_paths(component)
        if any(path.casefold().endswith("/countdowndays") for path in paths):
            countdown_values.append(component)
    if not countdown_values:
        return
    if _descendant_on_click_count(backboard, components_by_id) > 0:
        return

    direct_children = []
    for child_id in backboard.children:
        child = components_by_id.get(child_id)
        if child is not None:
            direct_children.append(child)
    has_three_children = len(direct_children) == 3
    has_three_texts = has_three_children and all(
        child.component_type == "Text" for child in direct_children
    )
    if not has_three_texts:
        errors.append(
            f"2x4 countdown backboard {backboard.component_id} without an action "
            "must directly contain exactly three Text children: target title, "
            "numeric countdown, and unit `天`. Do not nest a content/readout "
            "Column or add a fourth auxiliary line."
        )
        return

    title, value, unit = direct_children
    value_paths = _component_content_paths(value)
    is_countdown_value = any(path.casefold().endswith("/countdowndays") for path in value_paths)
    if not is_countdown_value or unit.props.get("content") != "天":
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_COUNTDOWN_ORDER",
                validation_class="semantic",
                category="layout",
                message="倒计时背板的三个文本子节点顺序不符合要求。",
                expected={"directChildOrder": ["目标标题", "countdownDays 数值", "天"]},
                actual=backboard.children,
                component_id=backboard.component_id,
                property_path="/children",
                legacy_message=(
                    f"2x4 countdown backboard {backboard.component_id} must order its "
                    "three Text children as target title, countdownDays value, and unit `天`."
                ),
            ),
        )

    has_balanced_distribution = (
        backboard.props.get("justifyContent") == "spaceBetween"
        and backboard.props.get("alignItems") == "center"
    )
    if not has_balanced_distribution:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_COUNTDOWN_DISTRIBUTION",
                validation_class="semantic",
                category="layout",
                message="倒计时背板的垂直分布或水平对齐不符合要求。",
                expected={"justifyContent": "spaceBetween", "alignItems": "center"},
                actual=backboard.props,
                component_id=backboard.component_id,
                legacy_message=(
                    f"2x4 countdown backboard {backboard.component_id} must use "
                    'justifyContent "spaceBetween" and alignItems "center" so the '
                    "title, number, and unit have balanced vertical spacing."
                ),
            ),
        )

    for child in (title, value, unit):
        if child.props.get("width") == 114 and child.props.get("textAlign") == "center":
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_COUNTDOWN_TEXT_WIDTH",
                validation_class="semantic",
                category="layout",
                message="倒计时文本的宽度或文字对齐不符合要求。",
                expected={"width": 114, "textAlign": "center"},
                actual=child.props,
                component_id=child.component_id,
                legacy_message=(
                    f"2x4 countdown Text {child.component_id} must use width 114 and "
                    "textAlign center inside the balanced countdown backboard."
                ),
            ),
        )
