# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责：semantic.display。判断与顺序基于 Fusion 主线。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.constants import (
    _AMBIGUOUS_METRIC_DESCRIPTION_MARKERS,
    _AMBIGUOUS_STATUS_MARKERS,
    _COMMON_DISPLAY_UNITS,
    _EXPRESSION_PATTERN,
    _MEASUREMENT_SAMPLE_PATTERN,
    _NUMERIC_SCHEMA_TYPES,
    _STRING_LITERAL_PATTERN,
)
from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    emit_error,
)
from services.card_validation.compact_validation.schema import _schema_node_at_path, _schema_type
from services.card_validation.compact_validation.syntax.expressions import _collect_binding_context
from services.card_validation.compact_validation.text import (
    _component_content_paths,
    _pure_binding_path,
    _static_text_fragments,
    _uses_visual_recipe_part,
)
from services.compact_dsl_a2ui_converter import (
    ComponentRow,
)


def _collect_raw_boolean_text_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
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
                    f"{', '.join(boolean_paths)} must be mapped to user-facing Text with a "
                    f"conditional expression; do not display raw true/false."
                ),
            ),
        )


def _data_business_root(path: str | None) -> str | None:
    root = None
    if path:
        parts = path.split("/")
        if len(parts) >= 4 and parts[1] == "data":
            root = f"/data/{parts[2]}"
    return root


def _progress_readout_root(component: ComponentRow, schema: dict[str, Any]) -> str | None:
    """只识别单字段动态读数，不把动态名称、标签或多字段摘要当配对证据。"""
    root = None
    if component.component_type == "Text":
        paths = _component_content_paths(component)
        if len(paths) == 1:
            path = paths[0]
            node = _schema_node_at_path(schema, path)
            sample = node.get("sampleValue") if isinstance(node, dict) else None
            numeric = _schema_type(node) in _NUMERIC_SCHEMA_TYPES
            formatted = isinstance(sample, str) and bool(
                _MEASUREMENT_SAMPLE_PATTERN.fullmatch(sample.strip())
            )
            if numeric or formatted:
                root = _data_business_root(path)
    return root


def _collect_progress_readout_object_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    """阻止进度与直接同组读数明确来自不同业务根；不猜测远端分区或同根指标。"""
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return
    components_by_id = {component.component_id: component for component in components}
    for parent in components:
        if parent.component_type not in {"Row", "Column", "Stack"}:
            continue
        readout_roots: set[str] = set()
        progresses: list[ComponentRow] = []
        for child_id in parent.children:
            child = components_by_id.get(child_id)
            if child is None:
                continue
            root = _progress_readout_root(child, schema)
            if root is not None:
                readout_roots.add(root)
            if child.component_type == "Progress":
                progresses.append(child)
        if not readout_roots:
            continue
        for progress in progresses:
            value_path = _pure_binding_path(progress.props.get("value"))
            value_root = _data_business_root(value_path)
            if value_root is None or value_root in readout_roots:
                continue
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_DISPLAY_PROGRESS_OBJECT_MISMATCH",
                    validation_class="semantic",
                    category="display",
                    message=(
                        f"component {progress.component_id}: Progress.value {value_path} "
                        f"belongs to {value_root}, but the direct sibling readout(s) in "
                        f"{parent.component_id} belong to "
                        f"{', '.join(sorted(readout_roots))}."
                    ),
                    legacy_message=(
                        f"component {progress.component_id}: Progress.value {value_path} "
                        f"belongs to {value_root}, but the direct sibling readout(s) in "
                        f"{parent.component_id} belong to "
                        f"{', '.join(sorted(readout_roots))}. Keep progress and its "
                        f"readout on the same object; if that object has no numeric field, "
                        f"omit its progress and retain its complete text. Do not borrow "
                        f"another object's value."
                    ),
                    expected={
                        "readoutRoots": sorted(readout_roots),
                        "sameObject": True,
                        "borrowOtherObjectValueAllowed": False,
                        "preserveCompleteReadout": True,
                    },
                    actual={
                        "progressPath": value_path,
                        "progressRoot": value_root,
                        "parentId": parent.component_id,
                    },
                    component_id=progress.component_id,
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
    if isinstance(sample, (int, float)) and (not isinstance(sample, bool)):
        return True
    return isinstance(sample, str) and 0 < len(sample.strip()) <= 8


def _nearby_text_context(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> str:
    fragments = [
        _static_text_fragments(component.props.get("content")),
        _paired_recipe_label_context(component, parent_by_child, components_by_id),
    ]
    parent_id = parent_by_child.get(component.component_id)
    parent = components_by_id.get(parent_id) if parent_id else None
    if parent is None:
        return " ".join(fragment for fragment in fragments if fragment)
    for sibling_id in parent.children:
        if sibling_id == component.component_id:
            continue
        sibling = components_by_id.get(sibling_id)
        if sibling is None or sibling.component_type != "Text":
            continue
        fragments.append(_static_text_fragments(sibling.props.get("content")))
    return " ".join(fragment for fragment in fragments if fragment)


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
    return bool(re.search("(?:'|\\\")\\s*(?:-|~|～|至|–|—)\\s*(?:'|\\\")\\s*$", body))


def _collect_semantic_text_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str]
) -> None:
    components_by_id = {component.component_id: component for component in components}
    parent_by_child: dict[str, str] = {}
    for parent in components:
        for child_id in parent.children:
            parent_by_child[child_id] = parent.component_id
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
                        f"component {component.component_id}: time/date range ends with a "
                        f"dangling separator. Bind both start and end values, or remove "
                        f"the separator and display the available value only."
                    ),
                ),
            )
        paths = _component_content_paths(component)
        normalized_paths = [path.casefold() for path in paths]
        nearby_text = _nearby_text_context(component, parent_by_child, components_by_id)
        has_reminder_path = any(
            "remindtime" in path or "remindminutes" in path for path in normalized_paths
        )
        if has_reminder_path and (not any(marker in nearby_text for marker in ("分钟", "分"))):
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
                        f"component {component.component_id}: reminder value must keep its "
                        f"minute semantics, such as 提前 15 分钟; do not display a bare "
                        f"numeric reminder value."
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
                        f"metric label 风力, for example 风力 2级; do not show a bare 2级."
                    ),
                ),
            )


def _collect_unbound_action_hint_errors(components: list[ComponentRow], errors: list[str]) -> None:
    components_by_id = {component.component_id: component for component in components}
    parent_by_child: dict[str, str] = {}
    for parent in components:
        for child_id in parent.children:
            parent_by_child[child_id] = parent.component_id
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
                    f"component {component.component_id}: action-like Text {text!r} has no "
                    f"clickable ancestor. Bind the matching event to its action slot or "
                    f"remove the action wording."
                ),
            ),
        )


def _has_nearby_metric_label(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
    layout_origins: dict[str, str] | None = None,
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
    if has_metric_label(_paired_recipe_label_context(component, parent_by_child, components_by_id)):
        return True

    current = component.component_id
    levels = 0
    visited: set[str] = set()
    origins = layout_origins or {}
    while levels < 3 and current not in visited:
        visited.add(current)
        parent_id = parent_by_child.get(current)
        parent = components_by_id.get(parent_id) if parent_id else None
        if parent is None:
            return False
        # 模板新增的承载容器不改变“相邻”的语义距离；业务 Region 仍计一层。
        origin = origins.get(parent.component_id)
        if origin is None or origin == parent.component_id:
            levels += 1
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
            if sibling and sibling.component_type == "SingleLineTitle":
                if has_metric_label(sibling.props.get("title")):
                    return True
            is_semantic_label = sibling is not None and (
                _uses_visual_recipe_part(sibling, "SingleLineTitle.root")
                or _uses_visual_recipe_part(sibling, "SecondaryBody.root")
            )
            if not is_semantic_label:
                continue
            pending = list(sibling.children)
            for _ in range(3):
                next_level = []
                for child_id in pending:
                    child = components_by_id.get(child_id)
                    if child is None:
                        continue
                    if child.component_type == "Text":
                        if has_metric_label(child.props.get("content")):
                            return True
                    else:
                        next_level.extend(child.children)
                pending = next_level
        current = parent.component_id
    return False


def _collect_ambiguous_metric_text_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str],
    *, layout_origins: dict[str, str] | None = None,
) -> None:
    components_by_id = {component.component_id: component for component in components}
    parent_by_child: dict[str, str] = {}
    for parent in components:
        for child_id in parent.children:
            parent_by_child[child_id] = parent.component_id
    for component in components:
        if component.component_type != "Text":
            continue
        if _uses_visual_recipe_part(component, "ProgressLine2.value"):
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
            if _is_ambiguous_metric_node(node) and (
                not _has_nearby_metric_label(component, parent_by_child, components_by_id,
                                            layout_origins)
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
                            f"component {component.component_id}: value {path} has "
                            f"ambiguous meaning ({detail}); add a nearby metric label such "
                            "as 感冒指数、紫外线指数 or 睡眠得分 "
                            "instead of showing the value alone."
                        ),
                    ),
                )
                break


def _paired_recipe_label_context(
    component: ComponentRow,
    parent_by_child: dict[str, str],
    components_by_id: dict[str, ComponentRow],
) -> str:
    """识别当前 TextBlock 项内的真实标签，不跨项或跨分区寻找文字。"""
    if not _uses_visual_recipe_part(component, "TextBlock.value"):
        return ""
    slot = components_by_id.get(parent_by_child.get(component.component_id))
    if slot is None or not _uses_visual_recipe_part(slot, "TextBlock.valueSlot"):
        return ""
    item = components_by_id.get(parent_by_child.get(slot.component_id))
    if item is None or not _uses_visual_recipe_part(item, "TextBlock.item"):
        return ""
    fragments: list[str] = []
    for sibling_id in item.children:
        sibling = components_by_id.get(sibling_id)
        if sibling is None or not _uses_visual_recipe_part(sibling, "TextBlock.labelSlot"):
            continue
        for child_id in sibling.children:
            child = components_by_id.get(child_id)
            if child is not None and _uses_visual_recipe_part(child, "TextBlock.label"):
                fragments.append(_static_text_fragments(child.props.get("content")))
    return " ".join(fragment for fragment in fragments if fragment)


def _collect_compound_duration_component_errors(
    components: list[ComponentRow], task_spec: dict[str, Any], errors: list[str],
) -> None:
    """只兜底有明确样值的文本/数值选型错误，不改变组件内部字号。"""
    from services.compact_composition_context import _literal_display_sample
    from services.compact_composition_planner import is_compound_duration_text

    for component in components:
        if component.component_type != "EmphasizedData":
            continue
        value = component.props.get("value")
        displayed = _literal_display_sample(value, task_spec)
        sample = displayed[1] if displayed is not None else value
        if not is_compound_duration_text(sample):
            continue
        errors.append(
            f"component {component.component_id}: compound duration {sample!r} is a complete "
            "text readout, not a single numeric value. Use EmphasisText.mainText with the "
            "same complete binding at its registered 18fp text style; keep every duration "
            "part and unit. Do not split sample digits, invent fields or change numeric "
            "hero font sizes. Supporting durations keep their existing body role."
        )
