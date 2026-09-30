# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.w1。"""

from __future__ import annotations

from services.card_validation.compact_validation.context import _descendant_components
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _non_negative_number,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_two_by_four_w1_focus_alignment_errors(
    focus: ComponentRow,
    focus_components: list[ComponentRow],
    _normalized_roots: set[str],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    text_count = 0
    has_large_focus = False
    for component in focus_components:
        if component.component_type == "Text":
            text_count += 1
            font_size = _non_negative_number(component.props.get("fontSize")) or 0
            if font_size >= 20:
                has_large_focus = True
        if component.component_type in {"List", "TimelineUnit"}:
            return
    if text_count == 0:
        return
    if text_count > 4:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_FOCUS_TEXT_BUDGET",
                validation_class="semantic",
                category="layout",
                message="左侧焦点的文本数量超过上限。",
                expected={"maximumTextCount": 4, "valueLedMaximumVisualLayers": 3},
                actual={"textCount": text_count},
                component_id=focus.component_id,
                legacy_message=(
                    "2x4 W1-focus-aux left focus may contain at most four Text nodes. "
                    "Use at most three visual layers for value-led content, merge a "
                    "closely related pair, or move one necessary fact to an auxiliary "
                    "cell instead of filling the left zone with a dense list."
                ),
            ),
        )
        return

    if focus.props.get("justifyContent") != "center":
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_FOCUS_VERTICAL_ALIGNMENT",
                validation_class="semantic",
                category="layout",
                message="左侧紧凑内容没有在信息区域内垂直居中。",
                expected={"justifyContent": "center"},
                actual=focus.props.get("justifyContent"),
                component_id=focus.component_id,
                property_path="/justifyContent",
                legacy_message=(
                    "2x4 W1-focus-aux compact left content must use justifyContent "
                    "center so its information group is vertically centered instead "
                    "of being pinned to the top."
                ),
            ),
        )
    requires_horizontal_center = has_large_focus or text_count <= 2
    if requires_horizontal_center and focus.props.get("alignItems") != "center":
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_FOCUS_HORIZONTAL_ALIGNMENT",
                validation_class="semantic",
                category="layout",
                message="左侧稀疏内容或主数值没有水平居中。",
                expected={"alignItems": "center"},
                actual=focus.props.get("alignItems"),
                component_id=focus.component_id,
                property_path="/alignItems",
                legacy_message=(
                    "2x4 W1-focus-aux sparse or value-led left content must use "
                    "alignItems center. Event lists and dense summaries may remain "
                    "left-aligned, but their full group must still be vertically centered."
                ),
            ),
        )

    for child_id in focus.children:
        child = components_by_id.get(child_id)
        if child is None or child.component_type not in {"Column", "Row"}:
            continue
        child_components = [
            child,
            *_descendant_components(child, components_by_id),
        ]
        has_text = False
        for component in child_components:
            if component.component_type == "Text":
                has_text = True
                break
        if not has_text:
            continue
        if child.props.get("justifyContent") != "center":
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W1_FOCUS_GROUP_ALIGNMENT",
                    validation_class="semantic",
                    category="layout",
                    message="左侧内容组没有居中。",
                    expected={"justifyContent": "center"},
                    actual=child.props.get("justifyContent"),
                    component_id=child.component_id,
                    property_path="/justifyContent",
                    legacy_message=(
                        f"2x4 W1-focus-aux left content group {child.component_id} must "
                        "use justifyContent center so its compact text group is not "
                        "pinned to the top or left."
                    ),
                ),
            )
        if child.component_type == "Column" and requires_horizontal_center:
            if child.props.get("alignItems") != "center":
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_LAYOUT_W1_FOCUS_COLUMN_ALIGNMENT",
                        validation_class="semantic",
                        category="layout",
                        message="左侧内容列没有水平居中。",
                        expected={"alignItems": "center"},
                        actual=child.props.get("alignItems"),
                        component_id=child.component_id,
                        property_path="/alignItems",
                        legacy_message=(
                            f"2x4 W1-focus-aux left content Column "
                            f"{child.component_id} must use alignItems center."
                        ),
                    ),
                )


def _collect_w1_focus_structure_errors(
    focus: ComponentRow,
    focus_components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    parent_by_child: dict[str, ComponentRow] = {}
    for component in focus_components:
        for child_id in component.children:
            parent_by_child[child_id] = component
    for component in focus_components:
        if component.component_type != "Image":
            continue
        parent = parent_by_child.get(component.component_id)
        is_progress_center = False
        if parent is not None and parent.component_type == "Stack":
            for sibling_id in parent.children:
                sibling = components_by_id.get(sibling_id)
                if sibling is not None and sibling.component_type == "Progress":
                    is_progress_center = True
                    break
        if is_progress_center:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_FOCUS_DECORATION",
                validation_class="semantic",
                category="layout",
                message="左侧焦点包含进度环中心以外的装饰图片。",
                expected={"allowedImagePlacement": "与有效环形 Progress 位于同一 Stack 中央"},
                component_id=component.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux left focus Image {component.component_id} is "
                    "decorative and must be removed. Only an Image centered inside a "
                    "Stack that also contains a valid ring Progress is allowed there."
                ),
            ),
        )
    large_texts: list[ComponentRow] = []
    for component in focus_components:
        if component.component_type != "Text":
            continue
        font_size = _non_negative_number(component.props.get("fontSize")) or 0
        if font_size >= 20:
            large_texts.append(component)
    if len(large_texts) > 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_PRIMARY_FOCUS_COUNT",
                validation_class="semantic",
                category="layout",
                message="左侧焦点存在多个大字号主内容。",
                expected={
                    "maximumTextCountAtOrAbove20fp": 1,
                    "peerMetricsUseOrdinaryTypography": True,
                },
                actual={"largeTextCount": len(large_texts)},
                component_id=focus.component_id,
                legacy_message=(
                    "2x4 W1-focus-aux may contain only one 20fp-or-larger primary "
                    "focus in the left zone. Keep peer metrics as ordinary auxiliary "
                    "content instead of manufacturing a second hero."
                ),
            ),
        )
    if any(component.props.get("onClick") for component in focus_components):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_ACTION_PLACEMENT",
                validation_class="semantic",
                category="layout",
                message="左侧焦点中包含点击动作。",
                expected={"actionPlacement": "右侧辅助单元", "leftFocusClickAllowed": False},
                component_id=focus.component_id,
                legacy_message=(
                    "2x4 W1-focus-aux actions must occupy a right auxiliary cell; "
                    "do not bind actions inside the left focus zone."
                ),
            ),
        )


def _collect_w1_progress_readout(
    focus: ComponentRow,
    focus_components: list[ComponentRow],
    has_progress: bool,
    errors: list[str],
) -> None:
    if has_progress:
        has_visible_progress_value = False
        for component in focus_components:
            if component.component_type != "Text":
                continue
            font_size = _non_negative_number(component.props.get("fontSize")) or 0
            if font_size >= 18:
                has_visible_progress_value = True
                break
        if not has_visible_progress_value:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W1_PROGRESS_READOUT",
                    validation_class="semantic",
                    category="layout",
                    message="左侧进度组件缺少足够字号的可见主值文本。",
                    expected={"visibleValueTextRequired": True, "minimumFontSize": 18},
                    component_id=focus.component_id,
                    legacy_message=(
                        "2x4 W1-focus-aux Progress must be paired with a visible "
                        "primary value Text of at least 18fp in the left focus zone. "
                        "Do not output a standalone progress line or ring without its "
                        "readout."
                    ),
                ),
            )


def _collect_w1_battery_progress_shape(
    focus_components: list[ComponentRow],
    has_progress: bool,
    normalized_roots: set[str],
    errors: list[str],
) -> None:
    if has_progress and normalized_roots == {"earphone", "phonebattery"}:
        for component in focus_components:
            if component.component_type != "Progress":
                continue
            if component.props.get("type") == "ring":
                continue
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W1_BATTERY_PROGRESS_SHAPE",
                    validation_class="semantic",
                    category="layout",
                    message="手机与耳机组合的焦点进度不是环形。",
                    expected={"progressType": "ring", "binding": "数值型手机电量百分比"},
                    actual=component.props.get("type"),
                    component_id=component.component_id,
                    property_path="/type",
                    legacy_message=(
                        "2x4 phone-and-earphone W1 focus must use a compact ring "
                        "Progress for numeric phone battery percentage; do not use a "
                        "horizontal linear bar. If only formatted battery text exists, "
                        "remove Progress and display that complete text instead."
                    ),
                ),
            )


def _collect_w1_cell_text_layout(
    cell: ComponentRow,
    cell_components: list[ComponentRow],
    cell_texts: list[ComponentRow],
    errors: list[str],
) -> int:
    has_non_start_text = False
    for text in cell_texts:
        if text.props.get("textAlign") not in {None, "start"}:
            has_non_start_text = True
            break
    has_non_start_container = False
    if cell.component_type == "Row":
        has_non_start_container = cell.props.get("justifyContent") not in {
            None,
            "start",
        }
    elif cell.component_type == "Column":
        has_non_start_container = cell.props.get("alignItems") not in {
            None,
            "start",
        }
    if has_non_start_text or has_non_start_container:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_CELL_TEXT_ALIGNMENT",
                validation_class="semantic",
                category="layout",
                message="辅助单元的文本组没有保持左对齐。",
                expected={
                    "rowJustifyContent": "start",
                    "columnAlignItems": "start",
                    "textAlign": "start",
                    "centering": "仅允许垂直居中",
                },
                actual={
                    "nonStartText": has_non_start_text,
                    "nonStartContainer": has_non_start_container,
                },
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux cell {cell.component_id} must keep its text "
                    "group left-aligned. Use Row justifyContent start or Column "
                    "alignItems start, and Text textAlign start; only vertical "
                    "centering is allowed."
                ),
            ),
        )
    text_count = sum(component.component_type == "Text" for component in cell_components)
    if text_count > 2:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_CELL_TEXT_BUDGET",
                validation_class="semantic",
                category="layout",
                message="辅助单元包含过多文本节点。",
                expected={"maximumTextCount": 2},
                actual={"textCount": text_count},
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux cell {cell.component_id} may contain at most "
                    "two Text nodes. Merge its auxiliary information."
                ),
            ),
        )
    return text_count


def _collect_w1_cell_fact_density(
    cell: ComponentRow,
    visible_paths: set[str],
    text_count: int,
    is_paired_earphone_summary: bool,
    errors: list[str],
) -> None:
    if len(visible_paths) > 2 and not is_paired_earphone_summary:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_CELL_FACT_DENSITY",
                validation_class="semantic",
                category="layout",
                message="辅助单元包含过多动态事实。",
                expected={
                    "maximumFacts": 2,
                    "maximumShortLines": 2,
                    "exception": "满足既有双耳机摘要条件的两行内容",
                },
                actual={"visiblePaths": sorted(visible_paths)},
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux cell {cell.component_id} references "
                    f"{len(visible_paths)} dynamic facts. Keep at most two facts "
                    "that fit as two short lines; drop lower-priority fields."
                ),
            ),
        )
    if len(visible_paths) == 2 and text_count < 2:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_CELL_FACT_LINES",
                validation_class="semantic",
                category="layout",
                message="辅助单元把两项动态事实拼接到了一个文本节点。",
                expected={"textCount": 2, "factsPerLine": 1, "singleLineTextRequired": True},
                actual={"textCount": text_count, "visiblePaths": sorted(visible_paths)},
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux cell {cell.component_id} displays two "
                    "dynamic facts in one Text. Use two single-line Text nodes, "
                    "one fact per line, instead of joining them with '|'."
                ),
            ),
        )


def _collect_w1_nested_action(
    cell: ComponentRow,
    cell_components: list[ComponentRow],
    errors: list[str],
) -> None:
    if any(component.component_type in {"Button", "ActionUnit"} for component in cell_components):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_CELL_NESTED_ACTION",
                validation_class="semantic",
                category="layout",
                message="辅助单元内部嵌套了独立按钮或动作组件。",
                expected={
                    "clickTarget": "辅助背板本身",
                    "nestedButtonOrActionUnitAllowed": False,
                },
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux cell {cell.component_id} must bind onClick "
                    "to the auxiliary backboard itself; do not nest a Button or "
                    "ActionUnit inside it."
                ),
            ),
        )
