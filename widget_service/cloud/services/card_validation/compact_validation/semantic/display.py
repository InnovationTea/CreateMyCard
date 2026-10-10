# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：semantic.display。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.context import component_graph, component_index
from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error
from services.card_validation.compact_validation.schema import (
    _NUMERIC_SCHEMA_TYPES,
    _schema_node_at_path,
    _schema_type,
)
from services.card_validation.compact_validation.syntax.expressions import (
    _EXPRESSION_PATTERN,
    _STRING_LITERAL_PATTERN,
    _collect_binding_context,
)
from services.card_validation.compact_validation.text import (
    _AMBIGUOUS_METRIC_DESCRIPTION_MARKERS,
    _AMBIGUOUS_STATUS_MARKERS,
    _COMMON_DISPLAY_UNITS,
    _binding_roots,
    _component_content_paths,
    _is_allowed_display_unit,
    _nearby_text_context,
    _static_text_fragments,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _collect_two_by_two_weather_date_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    if task_spec.get("size") != "2x2":
        return
    data_model_schema = task_spec.get("dataModelSchema")
    schema_data = data_model_schema.get("data") if isinstance(data_model_schema, dict) else None
    if not isinstance(schema_data, dict) or set(schema_data) != {"weather"}:
        return
    for component in components:
        if component.component_type != "Text":
            continue
        paths: list[str] = []
        _collect_binding_context(
            component.props.get("content"),
            f"component {component.component_id}.props.content",
            paths,
            [],
        )
        has_date = any(path.endswith("/date") for path in paths)
        has_weekday = any(path.endswith("/weekday") for path in paths)
        if not has_date or not has_weekday:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_WEATHER_DATE_WEEKDAY",
                validation_class="semantic",
                category="display",
                message="单日天气把日期和星期拼接到了同一文本中。",
                expected={"dateAndWeekdayInSameText": False},
                actual={"paths": paths},
                component_id=component.component_id,
                property_path="/content",
                legacy_message=(
                    f"component {component.component_id}: 2x2 single-day weather must not "
                    "concatenate date and weekday in one Text. Keep weekday by default, "
                    "or keep date alone when the user explicitly requests the exact date."
                ),
            ),
        )


def _collect_raw_boolean_text_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    data_model_schema = task_spec.get("dataModelSchema")
    if not isinstance(data_model_schema, dict):
        return
    for component in components:
        if component.component_type != "Text":
            continue
        boolean_paths: list[str] = []
        for path in _component_content_paths(component):
            schema_node = _schema_node_at_path(data_model_schema, path)
            if _schema_type(schema_node) == "boolean":
                boolean_paths.append(path)
        if not boolean_paths:
            continue
        content = component.props.get("content")
        if isinstance(content, str) and "?" in content:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_RAW_BOOLEAN",
                validation_class="semantic",
                category="display",
                message="布尔字段被直接作为文本展示。",
                expected={"userFacingConditionalText": True, "rawBooleanDisplayAllowed": False},
                actual={"paths": boolean_paths, "content": content},
                component_id=component.component_id,
                property_path="/content",
                legacy_message=(
                    f"component {component.component_id}: boolean field(s) "
                    f"{', '.join(boolean_paths)} must be mapped to user-facing Text "
                    "with a conditional expression; do not display raw true/false."
                ),
            ),
        )


def _is_ambiguous_metric_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    description = node.get("description")
    sample = node.get("sampleValue")
    if not isinstance(description, str) or not any(
        marker in description
        for marker in _AMBIGUOUS_METRIC_DESCRIPTION_MARKERS
        if marker != "概率"
    ):
        return False
    if isinstance(sample, (int, float)) and not isinstance(sample, bool):
        return True
    return isinstance(sample, str) and 0 < len(sample.strip()) <= 8


def _has_dangling_range_separator(content: Any) -> bool:
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    if "{{" not in stripped:
        return stripped.endswith(("-", "~", "～", "至", "–", "—"))
    match = _EXPRESSION_PATTERN.match(stripped)
    if match is None:
        return False
    body = match.group("body").rstrip()
    return bool(re.search(r"(?:'|\")\s*(?:-|~|～|至|–|—)\s*(?:'|\")\s*$", body))


def _collect_semantic_text_errors(
    components: list[ComponentRow],
    task_spec: dict[str, Any],
    errors: list[str],
) -> None:
    components_by_id = component_index(components)
    parent_by_child = component_graph(components).last_parent_ids

    for component in components:
        if component.component_type != "Text":
            continue
        content = component.props.get("content")
        if _has_dangling_range_separator(content):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_DANGLING_RANGE",
                    validation_class="semantic",
                    category="display",
                    message="时间或日期范围末尾存在悬空分隔符。",
                    expected={"range": "范围分隔符两侧均须有值；仅有一个值时不能保留分隔符"},
                    actual=content,
                    component_id=component.component_id,
                    property_path="/content",
                    legacy_message=(
                        f"component {component.component_id}: time/date range ends with "
                        "a dangling separator. Bind both start and end values, or remove "
                        "the separator and display the available value only."
                    ),
                ),
            )

        paths = _component_content_paths(component)
        normalized_paths = [path.casefold() for path in paths]
        own_text = _static_text_fragments(content)
        nearby_text = _nearby_text_context(
            component,
            parent_by_child,
            components_by_id,
        )
        if any(path.endswith("/eventcount") for path in normalized_paths):
            has_range_context = any(
                marker in own_text for marker in ("未来", "接下来", "近", "今天", "明天", "本周")
            )
            has_schedule_context = any(marker in own_text for marker in ("安排", "日程", "会议"))
            if not has_range_context or not has_schedule_context:
                errors.append(
                    f"component {component.component_id}: calendar eventCount "
                    "must not be shown as a standalone number or unit. Combine it "
                    "with its time scope and schedule meaning, for example "
                    "未来7天 2项安排, inside the calendar region."
                )

        has_reminder_path = any(
            "remindtime" in path or "remindminutes" in path for path in normalized_paths
        )
        if has_reminder_path and not any(marker in nearby_text for marker in ("分钟", "分")):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_REMINDER_UNIT",
                    validation_class="semantic",
                    category="display",
                    message="提醒数值缺少分钟语义。",
                    expected={"minuteSemanticsRequired": True, "bareNumericReminderAllowed": False},
                    actual={"paths": paths, "nearbyText": nearby_text},
                    component_id=component.component_id,
                    property_path="/content",
                    legacy_message=(
                        f"component {component.component_id}: reminder value must keep "
                        "its minute semantics, such as 提前 15 分钟; do not display a "
                        "bare numeric reminder value."
                    ),
                ),
            )

        has_wind_level_path = any(path.endswith("/windlevel") for path in normalized_paths)
        if has_wind_level_path and "风力" not in nearby_text:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_WIND_METRIC_LABEL",
                    validation_class="semantic",
                    category="display",
                    message="风力等级缺少可识别的风力标签。",
                    expected={"requiredMetricLabel": "风力", "bareLevelAllowed": False},
                    actual={"paths": paths, "nearbyText": nearby_text},
                    component_id=component.component_id,
                    property_path="/content",
                    legacy_message=(
                        f"component {component.component_id}: windLevel must include the "
                        "metric label 风力, for example 风力 2级; do not show a bare 2级."
                    ),
                ),
            )


def _collect_unbound_action_hint_errors(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    components_by_id = component_index(components)
    parent_by_child = component_graph(components).last_parent_ids

    action_prefixes = (
        "点击",
        "点一下",
        "点此",
        "一键",
        "打开",
        "查看",
        "设置",
        "导航",
        "拨打",
        "进入",
    )
    for component in components:
        if component.component_type != "Text":
            continue
        text = _static_text_fragments(component.props.get("content"))
        if not text.startswith(action_prefixes):
            continue
        current: ComponentRow | None = component
        has_click_ancestor = False
        while current is not None:
            if current.props.get("onClick"):
                has_click_ancestor = True
                break
            parent_id = parent_by_child.get(current.component_id)
            current = components_by_id.get(parent_id) if parent_id else None
        if has_click_ancestor:
            continue
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_UNBOUND_ACTION_HINT",
                validation_class="semantic",
                category="display",
                message="动作式文案所在组件及其祖先没有点击事件。",
                expected={"actionWordingRequiresClickableAncestor": True},
                actual=text,
                component_id=component.component_id,
                property_path="/content",
                legacy_message=(
                    f"component {component.component_id}: action-like Text {text!r} has "
                    "no clickable ancestor. Bind the matching event to its action slot "
                    "or remove the action wording."
                ),
            ),
        )


def _has_nearby_metric_label(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> bool:
    def has_metric_label(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if "{{" in value:
            candidates = [match[1:-1].strip() for match in _STRING_LITERAL_PATTERN.findall(value)]
        else:
            candidates = [value.strip()]
        return any(
            len(candidate) >= 2
            and candidate not in _AMBIGUOUS_STATUS_MARKERS
            and candidate not in _COMMON_DISPLAY_UNITS
            for candidate in candidates
        )

    if has_metric_label(component.props.get("content")):
        return True

    current = component.component_id
    for _ in range(3):
        parent_id = parent_by_child.get(current)
        parent = components_by_id.get(parent_id) if parent_id else None
        if parent is None:
            return False
        for sibling_id in parent.children:
            if sibling_id == current:
                continue
            sibling = components_by_id.get(sibling_id)
            text = (
                sibling.props.get("content")
                if sibling and sibling.component_type == "Text"
                else None
            )
            if has_metric_label(text):
                return True
        current = parent.component_id
    return False


def _collect_ambiguous_metric_text_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    components_by_id = component_index(components)
    parent_by_child = component_graph(components).last_parent_ids
    for component in components:
        if component.component_type != "Text":
            continue
        paths: list[str] = []
        _collect_binding_context(
            component.props.get("content"),
            f"component {component.component_id}.props.content",
            paths,
            [],
        )
        for path in paths:
            node = _schema_node_at_path(task_spec.get("dataModelSchema"), path)
            if _is_ambiguous_metric_node(node) and not _has_nearby_metric_label(
                component, parent_by_child, components_by_id
            ):
                detail = node.get("description") if isinstance(node, dict) else path
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_DISPLAY_AMBIGUOUS_METRIC",
                        validation_class="semantic",
                        category="display",
                        message="该字段的值无法在缺少指标标签时准确表达含义。",
                        expected={"nearbyMetricLabelRequired": True},
                        actual={"path": path, "description": detail},
                        component_id=component.component_id,
                        property_path="/content",
                        legacy_message=(
                            f"component {component.component_id}: value {path} "
                            "has ambiguous meaning "
                            f"({detail}); add a nearby metric label such as 感冒指数、紫外线指数 "
                            "or 睡眠得分 instead of showing the value alone."
                        ),
                    ),
                )
                break


def _collect_hero_suffix_errors(
    components: list[ComponentRow],
    components_by_id: dict[str, ComponentRow],
    data_model_schema: dict[str, Any],
    numeric_paths: dict[str, str | None],
    formatted_hero_ids: set[str],
    errors: list[str],
) -> None:
    for component in components:
        if component.component_type != "Row":
            continue
        for index, child_id in enumerate(component.children[:-1]):
            suffix = components_by_id.get(component.children[index + 1])
            if child_id in formatted_hero_ids:
                if suffix is not None and suffix.component_type == "Text":
                    emit_error(
                        errors,
                        CompactDiagnostic(
                            code="COMPACT_DISPLAY_FORMATTED_VALUE_SUFFIX",
                            validation_class="semantic",
                            category="display",
                            message="已包含单位的格式化主值后仍附加了文本。",
                            expected={"followingTextAllowed": False, "fieldLabelAllowed": False},
                            actual={"valueId": child_id, "suffixId": suffix.component_id},
                            component_id=component.component_id,
                            legacy_message=(
                                f"component {component.component_id}: formatted value "
                                f"{child_id} already contains its unit; do not append "
                                f"Text {suffix.component_id} or a field label."
                            ),
                        ),
                    )
                continue
            if child_id not in numeric_paths:
                continue
            numeric_path = numeric_paths[child_id]
            if suffix is None or suffix.component_type != "Text":
                continue
            content = suffix.props.get("content")
            if _is_allowed_display_unit(
                content,
                numeric_path or "",
                data_model_schema,
            ):
                continue
            value_source = numeric_path or "the preceding value"
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_HERO_SUFFIX_UNIT",
                    validation_class="semantic",
                    category="display",
                    message="大数值后相邻文本不是该字段的合法单位。",
                    expected={"suffix": "只能包含该字段的真实单位，标签和说明须独立展示"},
                    actual={
                        "valuePath": numeric_path,
                        "suffixId": suffix.component_id,
                        "content": content,
                    },
                    component_id=component.component_id,
                    legacy_message=(
                        f"component {component.component_id}: Text {suffix.component_id} "
                        f"after the large numeric value must contain only a real unit for "
                        f"{value_source}. Move labels or descriptions to a separate line."
                    ),
                ),
            )


def _collect_non_numeric_primary_suffix_error(
    component: ComponentRow,
    value: ComponentRow,
    suffix: ComponentRow,
    value_path: str,
    value_font_size: float | None,
    schema_type: str | None,
    errors: list[str],
) -> bool:
    if (
        value_font_size is not None
        and value_font_size >= 30
        and schema_type not in _NUMERIC_SCHEMA_TYPES
    ):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_NON_NUMERIC_PRIMARY_SUFFIX",
                validation_class="semantic",
                category="display",
                message="非数值的大字号主内容后附加了单位或标签。",
                expected={"nonNumericPrimaryMustOccupyOwnRow": True, "suffixAllowed": False},
                actual={
                    "path": value_path,
                    "schemaType": schema_type,
                    "suffixId": suffix.component_id,
                },
                component_id=component.component_id,
                legacy_message=(
                    f"component {component.component_id}: large primary Text "
                    f"{value.component_id} binds non-numeric field {value_path} "
                    f"and must occupy its own row; do not append "
                    f"{suffix.component_id} as a unit or label."
                ),
            ),
        )
        return True
    return False


def _collect_non_numeric_display_unit_error(
    component: ComponentRow,
    unit: str,
    value_path: str,
    errors: list[str],
) -> None:
    if unit not in _COMMON_DISPLAY_UNITS:
        return
    emit_error(
        errors,
        CompactDiagnostic(
            code="COMPACT_DISPLAY_UNIT_ON_NON_NUMERIC",
            validation_class="semantic",
            category="display",
            message="非数值绑定后附加了数值单位。",
            expected={"numericUnitRequires": ["number", "integer"]},
            actual={"path": value_path, "unit": unit},
            component_id=component.component_id,
            legacy_message=(
                f"component {component.component_id}: display unit {unit!r} cannot "
                f"follow non-numeric binding {value_path}. Remove the unit or bind "
                "a number/integer value."
            ),
        ),
    )


def _collect_w9_business_roots(
    zone: ComponentRow,
    content_roots: set[str],
    errors: list[str],
) -> None:
    if len(content_roots) > 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_BUSINESS_ROOTS",
                validation_class="semantic",
                category="display",
                message="同一背板混合了多个业务对象的数据。",
                expected={"businessObjectsPerBackboard": 1, "fieldOwnershipRequired": True},
                actual={"contentRoots": sorted(content_roots)},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x4 W9 backboard {zone.component_id} mixes data roots "
                    f"{sorted(content_roots)}. Each backboard must display exactly "
                    "one business object; move every field to its owning backboard."
                ),
            ),
        )


def _collect_w9_action_ownership(
    zone: ComponentRow,
    actions: list[ComponentRow],
    content_roots: set[str],
    errors: list[str],
) -> None:
    for action in actions:
        action_roots = _binding_roots(
            action.props.get("onClick"),
            f"component {action.component_id}.props.onClick",
        )
        if action_roots and content_roots and content_roots.isdisjoint(action_roots):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_W9_ACTION_OWNERSHIP",
                    validation_class="semantic",
                    category="display",
                    message="动作的数据归属与所在背板展示的业务对象不一致。",
                    expected={"actionMustBelongToDisplayedBusiness": True},
                    actual={
                        "actionRoots": sorted(action_roots),
                        "contentRoots": sorted(content_roots),
                        "backboardId": zone.component_id,
                    },
                    component_id=action.component_id,
                    property_path="/onClick",
                    legacy_message=(
                        f"2x4 W9 action {action.component_id} binds data root(s) "
                        f"{sorted(action_roots)} but is placed in backboard "
                        f"{zone.component_id}, which displays {sorted(content_roots)}. "
                        "Move the action to its owning business backboard."
                    ),
                ),
            )


def _collect_w9_countdown_unit(
    zone: ComponentRow,
    countdown_texts: list[ComponentRow],
    countdown_units: list[ComponentRow],
    errors: list[str],
) -> None:
    if countdown_texts and len(countdown_units) != 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_COUNTDOWN_UNIT",
                validation_class="semantic",
                category="display",
                message="倒计时缺少唯一的天数单位文本，或重复展示了单位。",
                expected={
                    "unitText": "天",
                    "unitCount": 1,
                    "placement": "数值下方，不与行内单位重复",
                },
                actual={"unitCount": len(countdown_units)},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x4 W9 countdown backboard {zone.component_id} must contain "
                    "exactly one unit Text `天`, placed below the numeric hero. Do "
                    "not generate both an inline unit and another unit below it."
                ),
            ),
        )


def _collect_w9_weather_date_weekday(
    component_id: str,
    day_paths: list[str],
    errors: list[str],
) -> None:
    has_date = any(path.endswith("/date") for path in day_paths)
    has_weekday = any(path.endswith("/weekday") for path in day_paths)
    if has_date and has_weekday:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_WEATHER_DATE_WEEKDAY",
                validation_class="semantic",
                category="display",
                message="紧凑天气行同时展示了日期和星期。",
                expected={
                    "weekdayRequired": True,
                    "redundantFullDateAllowed": False,
                },
                actual={"paths": day_paths},
                component_id=component_id,
                property_path="/content",
                legacy_message=(
                    f"2x4 W9 compact weather day {component_id} must not "
                    "show both full date and weekday in the same 114vp "
                    "row. Keep the weekday and remove the redundant date."
                ),
            ),
        )


def _collect_w9_action_usage(
    task_spec: dict[str, Any],
    has_duplicate_action: bool,
    total_action_count: int,
    errors: list[str],
) -> None:
    candidate_count = len(task_spec.get("eventCandidates") or [])
    if has_duplicate_action:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_DUPLICATE_ACTION",
                validation_class="semantic",
                category="display",
                message="两个背板重复展示了同一动作。",
                expected={"eachRequestedCandidateActionOccursOnce": True},
                legacy_message=(
                    "2x4 W9 must not duplicate the same action across both backboards. "
                    "Keep each requested candidate action exactly once."
                ),
            ),
        )
    if total_action_count > candidate_count:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_ACTION_COUNT",
                validation_class="semantic",
                category="display",
                message="可见动作数量超过本轮候选动作数量。",
                expected={
                    "maximumVisibleActions": candidate_count,
                    "duplicateActionsToFillBackboardAllowed": False,
                },
                actual={"visibleActions": total_action_count},
                legacy_message=(
                    f"2x4 W9 contains {total_action_count} visible actions but TaskSpec "
                    f"provides only {candidate_count} candidates. Do not copy an action "
                    "to fill the other backboard."
                ),
            ),
        )

    query = str(task_spec.get("userQuery") or "").casefold()
    action_markers = (
        "打开",
        "点击",
        "点一下",
        "查看",
        "设置",
        "导航",
        "进入",
        "一键",
        "拨号",
        "入会",
    )
    dual_action_markers = ("也可以", "也能", "分别", "两个", "双入口")
    expected_action_count = 0
    if candidate_count > 0 and any(marker in query for marker in action_markers):
        expected_action_count = 1
        if candidate_count >= 2 and any(marker in query for marker in dual_action_markers):
            expected_action_count = 2
    if total_action_count < expected_action_count:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_REQUIRED_ACTIONS",
                validation_class="semantic",
                category="display",
                message="背板遗漏了当前规则识别出的显式请求动作。",
                expected={
                    "minimumVisibleActions": expected_action_count,
                    "actionMustRemainInOwningBackboard": True,
                },
                actual={"visibleActions": total_action_count},
                legacy_message=(
                    "2x4 W9 must keep explicitly requested actions inside their owning "
                    f"backboards ({total_action_count}/{expected_action_count}). Remove "
                    "lower-priority text before dropping an action."
                ),
            ),
        )


def _has_w9_weather_field_count_error(
    zone: ComponentRow,
    field_name: str,
    matched_components: list[ComponentRow],
    errors: list[str],
) -> bool:
    has_error = len(matched_components) != 1
    if has_error:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_WEATHER_FIELD_COUNT",
                validation_class="semantic",
                category="display",
                message="三行天气摘要中的某项事实重复出现。",
                expected={"field": field_name, "occurrences": 1},
                actual={"occurrences": len(matched_components)},
                component_id=zone.component_id,
                legacy_message=(
                    f"2x4 W9 weather backboard {zone.component_id} must display "
                    f"{field_name} exactly once in its compact three-row summary."
                ),
            ),
        )

    return has_error


def _collect_w9_weather_metric_label(
    component: ComponentRow,
    label: str,
    errors: list[str],
) -> None:
    literal_text = _static_text_fragments(component.props.get("content"))
    if label not in literal_text:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W9_WEATHER_METRIC_LABEL",
                validation_class="semantic",
                category="display",
                message="天气摘要的数值缺少相应的短标签。",
                expected={"requiredLabel": label},
                actual={"literalText": literal_text},
                component_id=component.component_id,
                property_path="/content",
                legacy_message=(
                    f"2x4 W9 weather Text {component.component_id} must include the "
                    f"short label {label!r} so the value remains identifiable and "
                    "is not clipped."
                ),
            ),
        )


def _collect_w1_duplicate_facts(
    focus_text_paths: set[str],
    aux_text_paths: set[str],
    errors: list[str],
) -> None:
    duplicate_text_paths = sorted(focus_text_paths & aux_text_paths)
    if duplicate_text_paths:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W1_DUPLICATE_FACT",
                validation_class="semantic",
                category="display",
                message="左右信息区域重复展示了同一事实。",
                expected={"eachRequestedFieldBelongsToOneRegion": True},
                actual={"duplicatePaths": duplicate_text_paths},
                legacy_message=(
                    "2x4 W1-focus-aux must not repeat the same visible fact in the left "
                    "focus and a right auxiliary cell. Reassign each requested field "
                    f"to one region only; duplicated paths: {duplicate_text_paths}."
                ),
            ),
        )


def _collect_w1_progress_request_error(
    task_spec: dict[str, Any],
    focus_components: list[ComponentRow],
    errors: list[str],
) -> bool:
    query = str(task_spec.get("userQuery") or "").casefold()
    progress_requested = False
    for marker in ("进度", "进度条", "进度环", "环形", "progress"):
        if marker in query:
            progress_requested = True
            break
    has_progress = False
    for component in focus_components:
        if component.component_type == "Progress":
            has_progress = True
            break
    if has_progress and not progress_requested:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W1_PROGRESS_NOT_REQUESTED",
                validation_class="semantic",
                category="display",
                message="当前请求没有明确要求进度可视化，但左侧焦点中出现了进度组件。",
                expected={"progressRequiresExplicitRequest": True},
                actual={"hasProgress": has_progress, "progressRequested": progress_requested},
                legacy_message=(
                    "2x4 W1-focus-aux must not add Progress unless the user explicitly "
                    "requests a progress visualization. Use the left focus for the "
                    "primary value and its necessary status instead."
                ),
            ),
        )
    return has_progress


def _collect_w1_required_action_cells(
    task_spec: dict[str, Any],
    aux_column: ComponentRow,
    components_by_id: dict[str, ComponentRow],
    errors: list[str],
) -> None:
    query = str(task_spec.get("userQuery") or "").casefold()
    action_markers = (
        "打开",
        "点击",
        "点一下",
        "查看",
        "设置",
        "导航",
        "进入",
        "一键",
        "拨号",
        "入会",
    )
    dual_action_markers = ("也可以", "也能", "分别", "两个", "双入口")
    candidate_count = len(task_spec.get("eventCandidates") or [])
    explicit_action = candidate_count > 0 and any(marker in query for marker in action_markers)
    expected_action_cells = 0
    if explicit_action:
        expected_action_cells = 1
        if candidate_count >= 2 and any(marker in query for marker in dual_action_markers):
            expected_action_cells = 2
    actual_action_cells = 0
    for cell_id in aux_column.children:
        cell = components_by_id.get(cell_id)
        if cell is not None and cell.props.get("onClick"):
            actual_action_cells += 1
    if actual_action_cells < expected_action_cells:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W1_REQUIRED_ACTION_CELLS",
                validation_class="semantic",
                category="display",
                message="右侧辅助单元遗漏了当前规则识别出的显式请求动作。",
                expected={"minimumActionCells": expected_action_cells, "placement": "右侧辅助单元"},
                actual={"actionCells": actual_action_cells},
                component_id=aux_column.component_id,
                legacy_message=(
                    "2x4 W1-focus-aux must reserve right auxiliary cells for explicit "
                    f"actions ({actual_action_cells}/{expected_action_cells}). Drop or "
                    "merge lower-priority facts instead of omitting the requested action."
                ),
            ),
        )


def _collect_w1_complete_fact_lines(
    cell: ComponentRow,
    visible_paths: set[str],
    paths_per_text: list[list[str]],
    is_paired_earphone_summary: bool,
    errors: list[str],
) -> None:
    if len(visible_paths) == 2 and not is_paired_earphone_summary:
        has_complete_fact_lines = len(paths_per_text) == 2
        if has_complete_fact_lines:
            for component_paths in paths_per_text:
                if len(component_paths) != 1:
                    has_complete_fact_lines = False
                    break
        if not has_complete_fact_lines:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_W1_COMPLETE_FACT_LINES",
                    validation_class="semantic",
                    category="display",
                    message="辅助单元的两项动态事实没有各自在一个文本节点中完整表达。",
                    expected={
                        "eachFactHasCompleteTextLine": True,
                        "labelsAndValuesSeparatedAcrossLinesAllowed": False,
                    },
                    actual={"pathsPerText": paths_per_text},
                    component_id=cell.component_id,
                    legacy_message=(
                        f"2x4 W1-focus-aux cell {cell.component_id} must place each "
                        "of its two dynamic facts in a separate complete Text line. "
                        "Do not put both labels on one line and both values on the "
                        "other line."
                    ),
                ),
            )


def _collect_w1_cell_business_roots(
    cell: ComponentRow,
    cell_components: list[ComponentRow],
    errors: list[str],
) -> None:
    cell_roots: set[str] = set()
    for component in cell_components:
        if component.component_type == "Text":
            for path in _component_content_paths(component):
                parts = path.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "data":
                    cell_roots.add(parts[1])
        cell_roots.update(
            _binding_roots(
                component.props.get("onClick"),
                f"component {component.component_id}.props.onClick",
            )
        )
    if len(cell_roots) > 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_W1_CELL_BUSINESS_ROOTS",
                validation_class="semantic",
                category="display",
                message="同一辅助单元混合了不同业务对象的文本或动作。",
                expected={"businessObjectsPerCell": 1},
                actual={"roots": sorted(cell_roots)},
                component_id=cell.component_id,
                legacy_message=(
                    f"2x4 W1-focus-aux cell {cell.component_id} mixes data roots "
                    f"{sorted(cell_roots)}. Each auxiliary cell must belong to one "
                    "business object."
                ),
            ),
        )


def _collect_s4_action_hint(
    zone: ComponentRow,
    text_components: list[ComponentRow],
    errors: list[str],
) -> None:
    action_hint_prefixes = ("点击", "点此", "一键")
    if "onClick" in zone.props:
        for text_component in text_components:
            content = text_component.props.get("content")
            if not isinstance(content, str) or "{{" in content:
                continue
            if content.strip().startswith(action_hint_prefixes):
                emit_error(
                    errors,
                    CompactDiagnostic(
                        code="COMPACT_DISPLAY_S4_ACTION_HINT",
                        validation_class="semantic",
                        category="display",
                        message="可点击背板内额外显示了动作提示文案。",
                        expected={"actionHintTextAllowed": False, "clickTarget": "背板"},
                        actual=content,
                        component_id=text_component.component_id,
                        property_path="/content",
                        legacy_message=(
                            f"2x2 S4 clickable backboard {zone.component_id} must not "
                            f"show action hint Text {text_component.component_id}; "
                            "bind the action only to the backboard."
                        ),
                    ),
                )


def _collect_countdown_duplicate_unit(
    components: list[ComponentRow],
    errors: list[str],
) -> None:
    day_units = []
    for component in components:
        if component.component_type != "Text":
            continue
        content = component.props.get("content")
        if not isinstance(content, str):
            continue
        if content.strip() == "天":
            day_units.append(component)
    if len(day_units) > 1:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_DISPLAY_2X2_COUNTDOWN_DUPLICATE_UNIT",
                validation_class="semantic",
                category="display",
                message="倒计时重复展示了天数单位。",
                expected={"dayUnitCount": 1, "inlineAndMetadataDuplicateAllowed": False},
                actual={"dayUnitCount": len(day_units)},
                legacy_message=(
                    "2x2 countdown must display the day unit exactly once; do not place "
                    "'天' beside the value and repeat it again in a second metadata row."
                ),
            ),
        )
