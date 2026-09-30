# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.layout.w9。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.context import (
    _first_text_component,
)
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.semantic.layout.geometry import (
    _non_negative_number,
    _visual_text_line_profile,
)
from services.card_validation.compact_validation.text import (
    _numeric_content_paths,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_two_by_four_w9_density_errors(
    zone: ComponentRow,
    content_regions: list[ComponentRow],
    content_components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    if any(component.component_type == "Progress" for component in content_components):
        return

    line_profile: list[bool] = []
    for region in content_regions:
        line_profile.extend(_visual_text_line_profile(region, components_by_id, set()))
    if not line_profile:
        return

    first_text = None
    for region in content_regions:
        first_text = _first_text_component(region, components_by_id, set())
        if first_text is not None:
            break
    if first_text is not None:
        font_size = _non_negative_number(first_text.props.get("fontSize"))
        font_weight = _non_negative_number(first_text.props.get("fontWeight"))
        identifier = first_text.component_id.casefold()
        looks_like_title = "title" in identifier or "label" in identifier
        has_later_emphasis = any(line_profile[1:])
        title_candidate = looks_like_title or has_later_emphasis
        if font_size == 12 and font_weight == 400 and title_candidate:
            line_profile = line_profile[1:]

    large_number_count = 0
    for component in content_components:
        if component.component_type != "Text":
            continue
        font_size = _non_negative_number(component.props.get("fontSize"))
        if font_size is not None and font_size >= 30:
            large_number_count += 1

    if large_number_count:
        data_model_schema = task_spec.get("dataModelSchema")
        numeric_paths = (
            _numeric_content_paths(content_components, data_model_schema)
            if isinstance(data_model_schema, dict)
            else set()
        )
        if len(numeric_paths) >= 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W9_PEER_METRIC_TYPOGRAPHY",
                    validation_class="semantic",
                    category="layout",
                    message="多个并列数值中存在被放大的主数值。",
                    expected={
                        "peerMetrics": (
                            "所有并列指标须使用相同排版的普通完整文本行，"
                            "不能单独突出为 30fp/38fp 主数值"
                        )
                    },
                    actual={"numericPaths": sorted(numeric_paths)},
                    component_id=zone.component_id,
                    legacy_message=(
                        f"2x4 W9 backboard {zone.component_id} displays multiple peer "
                        "quantitative fields and must keep all of them as ordinary "
                        "complete text lines with the same typography; do not promote "
                        "one field to a 30fp/38fp hero."
                    ),
                ),
            )
        if large_number_count > 1:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W9_HERO_COUNT",
                    validation_class="semantic",
                    category="layout",
                    message="同一背板包含多个大字号数值。",
                    expected={
                        "maximumLargeNumberCount": 1,
                        "peerMetrics": "并列指标使用普通完整文本行",
                    },
                    actual={"largeNumberCount": large_number_count},
                    component_id=zone.component_id,
                    legacy_message=(
                        f"2x4 W9 backboard {zone.component_id} contains multiple "
                        "30fp/38fp values. Keep peer metrics as ordinary complete text "
                        "lines instead of manufacturing multiple hero values."
                    ),
                ),
            )
        if len(line_profile) > 2:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W9_HERO_LINE_BUDGET",
                    validation_class="semantic",
                    category="layout",
                    message="主数值背板在业务标题后的文本行数超出预算。",
                    expected={
                        "maximumLinesAfterTitle": 2,
                        "lines": ["数值及单位", "一行 12fp/400 辅助信息"],
                    },
                    actual={"lineCountAfterTitle": len(line_profile)},
                    component_id=zone.component_id,
                    legacy_message=(
                        f"2x4 W9 backboard {zone.component_id} with a 30fp/38fp numeric "
                        "hero may contain only the value/unit line and one 12fp/400 "
                        "auxiliary line after its business title. Merge auxiliary fields "
                        "with ' | '."
                    ),
                ),
            )


def _collect_two_by_four_w9_sparse_layout_errors(
    zone: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    text_components: list[ComponentRow],
    actions: list[ComponentRow],
    errors: list[str],
) -> None:
    if len(text_components) > 3:
        return
    for child_id in zone.children:
        child = components_by_id.get(child_id)
        if child is None or child.component_type != "Column" or child in actions:
            continue
        if child.props.get("layoutWeight") == 1 and child.props.get("justifyContent") == "center":
            return
    suffix = " with its action area" if actions else ""
    errors.append(
        f"2x4 W9 sparse backboard {zone.component_id}{suffix} must use a direct content "
        "Column with layoutWeight 1 and justifyContent center so the primary content "
        "group remains vertically centered."
    )


def _collect_w9_content_row_limit(
    zone: ComponentRow,
    text_components: list[ComponentRow],
    errors: list[str],
) -> None:
    if len(text_components) > 4:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_CONTENT_ROW_LIMIT",
                validation_class="semantic",
                category="layout",
                message="背板内容文本行数超过上限。",
                expected={"maximumContentTextCount": 4},
                actual={"contentTextCount": len(text_components)},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x4 W9 backboard {zone.component_id} may contain at most four "
                    "content Text rows. Merge same-object fields instead of stacking "
                    "additional rows."
                ),
            ),
        )


def _collect_w9_text_fact_density(
    component: ComponentRow,
    paths: list[str],
    errors: list[str],
) -> None:
    if len(paths) <= 2:
        return
    daily_indexes: set[str] = set()
    only_one_weather_day = True
    for path in paths:
        match = re.match(r"^/data/weather/daily/(\d+)/", path)
        if match is None:
            only_one_weather_day = False
            break
        daily_indexes.add(match.group(1))
    if only_one_weather_day and len(daily_indexes) == 1:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_W9_TEXT_FACT_DENSITY",
            validation_class="semantic",
            category="layout",
            message="窄文本行拼接了过多动态信息。",
            expected={"maximumShortFactsPerText": 2, "exception": "同一天的紧凑多日天气行"},
            actual={"paths": paths},
            component_id=component.component_id,
            property_path="/content",
            legacy_message=(
                f"2x4 W9 text {component.component_id} joins {len(paths)} "
                "dynamic facts in one narrow row. Keep at most two short facts "
                "per Text; split them into separate 12fp rows or remove the "
                "lowest-priority field. A compact multi-day weather row is the "
                "only exception."
            ),
        ),
    )


def _collect_w9_countdown_typography(
    component: ComponentRow,
    errors: list[str],
) -> None:
    font_size = _non_negative_number(component.props.get("fontSize"))
    if font_size not in {30, 38} or component.props.get("fontWeight") != 700:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_COUNTDOWN_TYPOGRAPHY",
                validation_class="semantic",
                category="layout",
                message="倒计时数值的字号或字重不符合独立背板要求。",
                expected={"fontSize": [30, 38], "fontWeight": 700},
                actual={
                    "fontSize": font_size,
                    "fontWeight": component.props.get("fontWeight"),
                },
                component_id=component.component_id,
                legacy_message=(
                    f"2x4 W9 countdown {component.component_id} must use a "
                    "30fp/38fp, 700-weight numeric hero in its own backboard."
                ),
            ),
        )


def _collect_w9_countdown_unit_position(
    countdown_texts: list[ComponentRow],
    countdown_units: list[ComponentRow],
    parent_by_child: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    if countdown_texts and countdown_units:
        countdown_unit_ids = {component.component_id for component in countdown_units}
        for countdown_text in countdown_texts:
            parent = parent_by_child.get(countdown_text.component_id)
            if parent is None or parent.component_type != "Row":
                continue
            has_inline_unit = False
            for child_id in parent.children:
                if child_id in countdown_unit_ids:
                    has_inline_unit = True
                    break
            if not has_inline_unit:
                continue
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_LAYOUT_W9_COUNTDOWN_UNIT_POSITION",
                    validation_class="semantic",
                    category="layout",
                    message="倒计时数值与天数单位放在同一行。",
                    expected={
                        "unitPlacement": "唯一的单位文本须置于主数值下方，不能与数值共享 Row"
                    },
                    actual={"parentId": parent.component_id},
                    component_id=countdown_text.component_id,
                    legacy_message=(
                        f"2x4 W9 countdown value {countdown_text.component_id} must "
                        "not share a Row with unit `天`; keep the single unit below "
                        "the numeric hero."
                    ),
                ),
            )


def _collect_w9_weather_day_typography(
    component: ComponentRow,
    component_id: str,
    errors: list[str],
) -> None:
    font_size = _non_negative_number(component.props.get("fontSize"))
    if font_size == 12 and component.props.get("fontWeight") == 400:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_W9_WEATHER_DAY_TYPOGRAPHY",
            validation_class="semantic",
            category="layout",
            message="紧凑天气日文本字号或字重不符合要求。",
            expected={"fontSize": 12, "fontWeight": 400},
            actual={
                "fontSize": font_size,
                "fontWeight": component.props.get("fontWeight"),
            },
            component_id=component_id,
            legacy_message=(
                f"2x4 W9 compact weather day {component_id} must use 12fp/400 auxiliary text."
            ),
        ),
    )


def _collect_w9_weather_day_rows(
    zone: ComponentRow,
    day_index: str,
    component_ids: set[str],
    errors: list[str],
) -> None:
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_LAYOUT_W9_WEATHER_DAY_ROWS",
            validation_class="semantic",
            category="layout",
            message="同一天的紧凑天气内容分散在多个文本行。",
            expected={"textCountPerDay": 1, "fontSize": 12, "fontWeight": 400},
            actual={"dayIndex": day_index, "textIds": sorted(component_ids)},
            component_id=zone.component_id,
            legacy_message=(
                f"2x4 W9 weather day {day_index} in backboard "
                f"{zone.component_id} is split across multiple Text rows "
                f"{sorted(component_ids)}. Merge each day into one 12fp/400 row."
            ),
        ),
    )


def _collect_w9_weather_divider(
    zone: ComponentRow,
    content_components: list[ComponentRow],
    errors: list[str],
) -> None:
    if any(component.component_type == "Divider" for component in content_components):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_WEATHER_DIVIDER",
                validation_class="semantic",
                category="layout",
                message="多日紧凑天气行之间存在分割线。",
                expected={"dividerAllowed": False},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x4 W9 multi-day weather backboard {zone.component_id} "
                    "must not insert Divider components between compact day rows."
                ),
            ),
        )


def _collect_w9_weather_decoration(
    zone: ComponentRow,
    content_components: list[ComponentRow],
    errors: list[str],
) -> None:
    if any(component.component_type == "Image" for component in content_components):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_WEATHER_DECORATION",
                validation_class="semantic",
                category="layout",
                message="三行天气摘要包含占用内容宽度的装饰图标。",
                expected={"decorativeImagesAllowed": False, "contentWidth": 114},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x4 W9 weather backboard {zone.component_id} with temperature, "
                    "rain and air-quality rows must omit decorative icons so all three "
                    "facts fit in the 114vp content width."
                ),
            ),
        )


def _collect_w9_weather_fact_rows(
    component: ComponentRow,
    component_paths: list[str],
    errors: list[str],
) -> None:
    if len(component_paths) != 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_WEATHER_FACT_ROWS",
                validation_class="semantic",
                category="layout",
                message="三行天气摘要的单行拼接了多项动态事实。",
                expected={"dynamicFactsPerText": 1, "rows": "温度、降雨、空气质量分别独占一行"},
                actual={"paths": component_paths},
                component_id=component.component_id,
                property_path="/content",
                legacy_message=(
                    f"2x4 W9 weather Text {component.component_id} must contain one "
                    "dynamic fact only; keep temperature, rain and air quality on "
                    "three separate rows."
                ),
            ),
        )
    font_size = _non_negative_number(component.props.get("fontSize"))
    if font_size != 12 or component.props.get("fontWeight") != 400:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_LAYOUT_W9_WEATHER_TRIPLET_TYPOGRAPHY",
                validation_class="semantic",
                category="layout",
                message="三行天气摘要的字号或字重不符合要求。",
                expected={"fontSize": 12, "fontWeight": 400},
                actual={"fontSize": font_size, "fontWeight": component.props.get("fontWeight")},
                component_id=component.component_id,
                legacy_message=(
                    f"2x4 W9 weather Text {component.component_id} must use "
                    "12fp/400 in the compact three-row summary."
                ),
            ),
        )
