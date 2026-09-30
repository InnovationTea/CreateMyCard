# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.routing。"""

from __future__ import annotations

from services.card_validation.compact_validation.context import (
    _descendant_on_click_count,
)
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _non_negative_number,
)
from services.card_validation.compact_validation.semantic.layout.regions import (
    _has_stacked_two_by_four_backboards,
    _has_two_by_four_w1_focus_aux,
    _has_two_by_four_w8_backboards,
    _has_two_by_four_w9_backboards,
    _has_two_by_four_w10_backboards,
    _has_two_by_two_s4_zones,
    _is_2x2_small_backboard,
    _two_by_two_s4_object_count,
)
from services.card_validation.compact_validation.syntax.expressions import _collect_binding_context
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_stacked_backboards(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if _has_stacked_two_by_four_backboards(components, components_by_id):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_STACKED_FULL_BACKBOARDS",
                validation_class="semantic",
                category="layout",
                message="宽卡片纵向堆叠了多个全宽内容背板。",
                expected={
                    "stackedFullWidthBackboardsAllowed": False,
                    "backboardWidths": [276, 296],
                    "backboardHeightRange": [48, 64],
                    "twoBusinessBlocksRequire": "W9 左右背板",
                },
                legacy_message=(
                    "2x4 cards must not stack two or more full-width 276x48-59 "
                    "content backboards vertically. Select the matching W skeleton; "
                    "two semantic data blocks must use W9 left/right backboards."
                ),
            ),
        )


def _collect_backboard_action_count(
    component: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if _descendant_on_click_count(component, components_by_id) > 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_2X4_BACKBOARD_ACTION_COUNT",
                validation_class="semantic",
                category="layout",
                message="大背板内存在多个动作控件。",
                expected={"maximumActionControls": 1},
                component_id=component.component_id,
                legacy_message=(
                    f"2x4 large backboard {component.component_id} may contain at "
                    "most one action control. Do not stack two buttons inside a "
                    "138x134 backboard; remove duplicate or lower-priority actions."
                ),
            ),
        )


def _collect_single_business_structure(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if (
        root is not None
        and _has_two_by_two_s4_zones(root, components_by_id)
        and _two_by_two_s4_object_count(root, components_by_id) != 2
    ):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_S4_OBJECT_COUNT",
                validation_class="semantic",
                category="layout",
                message="S4 布局没有对应两个独立展示对象。",
                expected={
                    "independentDisplayObjects": 2,
                    "oneObjectSplitAcrossTwoBackboardsAllowed": False,
                },
                legacy_message=(
                    "2x2 S4 requires exactly two independent display objects. "
                    "Fields from one object must remain in one single-business "
                    "layout instead of being split across two 134x63 backboards."
                ),
            ),
        )
    if root is not None and len(root.children) == 1:
        only_child = components_by_id.get(root.children[0])
        if _is_2x2_small_backboard(only_child):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_2X2_SINGLE_BUSINESS_WIDTH",
                    validation_class="semantic",
                    category="layout",
                    message="单业务卡片使用了孤立的小背板。",
                    expected={
                        "layout": "全宽单业务布局",
                        "isolated134x63BackboardAllowed": False,
                    },
                    legacy_message=(
                        "2x2 card has one data root and must use a full-width "
                        "single-business layout; do not generate an isolated "
                        "134x63 S4 backboard."
                    ),
                ),
            )


def _validate_w1_skeleton(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> bool:
    is_valid = root is not None and _has_two_by_four_w1_focus_aux(root, components_by_id)
    if not is_valid:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W1_FOCUS_AUX_SKELETON",
                validation_class="semantic",
                category="layout",
                message="一个主焦点加辅助单元的布局不符合 W1 骨架。",
                expected={
                    "root": {"type": "Row", "padding": 12, "itemMargin": 10},
                    "leftFocus": {"width": 136, "height": 126, "backboardAllowed": False},
                    "rightColumn": {
                        "width": 130,
                        "height": 126,
                        "itemMargin": 8,
                        "backboardCount": 2,
                        "backboardSize": [130, 59],
                    },
                },
                legacy_message=(
                    "2x4 card has one dominant focus and at most two auxiliary slots and "
                    "must use W1-focus-aux: root Row padding 12/itemMargin 10, a left "
                    "136x126 focus zone without a backboard, and a right 130x126 Column "
                    "containing two 130x59 backboards separated by itemMargin 8."
                ),
            ),
        )
    return is_valid


def _collect_w8_skeleton(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if _has_two_by_four_w8_backboards(root, components_by_id):
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_W8_SKELETON",
            validation_class="semantic",
            category="layout",
            message="至少四个语义指标组没有采用 W8 布局。",
            expected={
                "root": {"type": "Column", "padding": 8, "itemMargin": 8},
                "directRows": {"count": 2, "size": [284, 63], "itemMargin": 8},
                "backboardsPerRow": {"count": 2, "size": [138, 63]},
            },
            legacy_message=(
                "2x4 card displays at least four semantic metric groups and must use W8: "
                "root must be a Column with padding 8 and two direct 284x63 "
                "Rows separated by itemMargin 8; each Row must contain two "
                "138x63 backboards separated by itemMargin 8. Merge naturally "
                "related weather facts before dropping the lowest-priority group."
            ),
        ),
    )
    return


def _collect_w10_skeleton(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if _has_two_by_four_w10_backboards(root, components_by_id):
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_W10_SKELETON",
            validation_class="semantic",
            category="layout",
            message="三个语义数据块没有采用 W10 布局。",
            expected={
                "root": {"type": "Row", "padding": 8, "itemMargin": 8},
                "largeBackboardSize": [138, 134],
                "sideColumn": {
                    "size": [138, 134],
                    "itemMargin": 8,
                    "backboardCount": 2,
                    "backboardSize": [138, 63],
                },
            },
            legacy_message=(
                "2x4 card displays three semantic data blocks and must use W10: "
                "root must be a Row with padding 8 and itemMargin 8, containing "
                "one 138x134 large backboard and one 138x134 Column with two "
                "138x63 backboards separated by itemMargin 8."
            ),
        ),
    )
    return


def _collect_s4_object_count(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> bool:
    invalid = (
        root is not None
        and _has_two_by_two_s4_zones(root, components_by_id)
        and _two_by_two_s4_object_count(root, components_by_id) != 2
    )
    if invalid:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_S4_OBJECT_COUNT",
                validation_class="semantic",
                category="layout",
                message="S4 布局没有对应两个独立展示对象。",
                expected={
                    "independentDisplayObjects": 2,
                    "oneObjectSplitAcrossTwoBackboardsAllowed": False,
                },
                legacy_message=(
                    "2x2 S4 requires exactly two independent display objects. Fields "
                    "from one object must remain in one single-business layout instead "
                    "of being split across two 134x63 backboards."
                ),
            ),
        )
    return invalid


def _collect_s4_countdown_typography(
    components: list[ComponentRow],
    data_roots: set[str],
    errors: list[str],
) -> None:
    if "countdown" not in data_roots:
        return
    countdown_texts = []
    for component in components:
        if component.component_type != "Text":
            continue
        component_paths: list[str] = []
        _collect_binding_context(
            component.props.get("content"),
            f"component {component.component_id}.props.content",
            component_paths,
            [],
        )
        if any(path.startswith("/data/countdown/") for path in component_paths):
            countdown_texts.append(component)
    countdown_style_valid = bool(countdown_texts)
    for component in countdown_texts:
        font_size = _non_negative_number(component.props.get("fontSize"))
        if font_size != 14 or component.props.get("fontWeight") != 700:
            countdown_style_valid = False
    if countdown_style_valid:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_S4_COUNTDOWN_TYPOGRAPHY",
            validation_class="semantic",
            category="layout",
            message="S4 背板中的倒计时采用了独立大数值布局。",
            expected={
                "fontSize": 14,
                "fontWeight": 700,
                "standaloneCountdownGroupAllowed": False,
            },
            legacy_message=(
                "2x2 S4 countdown must be displayed as ordinary 14fp/700 "
                "primary text inside its backboard; do not reuse the V01 "
                "30fp/38fp hero or standalone countdown group."
            ),
        ),
    )
    return


def _validate_s4_skeleton(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    data_roots: set[str],
    errors: list[str],
) -> bool:
    is_valid = root is not None and _has_two_by_two_s4_zones(root, components_by_id)
    if not is_valid:
        roots = ", ".join(sorted(data_roots))
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_S4_SKELETON",
                validation_class="semantic",
                category="layout",
                message="两个业务数据根的方卡没有采用 S4 布局。",
                expected={
                    "root": {"type": "Column", "padding": 8, "itemMargin": 8},
                    "directBackboards": {"count": 2, "type": ["Row", "Column"], "size": [134, 63]},
                    "countdown": {"fontSize": 14, "fontWeight": 700},
                },
                actual={"dataRoots": roots},
                legacy_message=(
                    f"2x2 card displays two data roots ({roots}) and must use S4: root "
                    "must be a Column with padding 8 and exactly two direct 134x63 "
                    "Row/Column backboards with itemMargin 8. Countdown remains ordinary 14fp/700 "
                    "primary text inside its backboard."
                ),
            ),
        )
    return is_valid


def _validate_w9_skeleton(
    root: ComponentRow | None,
    components_by_id: dict[str, ComponentRow],
    data_roots: set[str],
    errors: list[str],
) -> bool:
    is_valid = root is not None and _has_two_by_four_w9_backboards(root, components_by_id)
    if not is_valid:
        roots = ", ".join(sorted(data_roots))
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_SKELETON",
                validation_class="semantic",
                category="layout",
                message="两个语义数据块的宽卡没有采用 W9 布局。",
                expected={
                    "root": {"type": "Row", "padding": 8, "itemMargin": 8},
                    "directBackboards": {"count": 2, "type": "Column", "size": [138, 134]},
                    "sharedTitleOrActionAreaAllowed": False,
                    "stackedFullWidthBusinessRowsAllowed": False,
                },
                actual={"dataRoots": roots},
                legacy_message=(
                    f"2x4 card displays two semantic data blocks ({roots}) and must use W9: "
                    "root must be a Row with padding 8 and exactly two direct 138x134 "
                    "Column backboards with itemMargin 8. Do not use a shared title, "
                    "a shared action area, or "
                    "stacked full-width business rows."
                ),
            ),
        )
    return is_valid
