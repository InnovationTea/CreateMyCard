"""编辑产物校验：差异保护、完整产物、履约及已确定的可读性约束。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from config.config import get_settings
from models.artifact import WidgetArtifact
from services.card_validation import ValidationOptions, validate_card
from services.card_validation.diagnostics import Diagnostic
from services.card_validation.theme_phase_validator import theme_phase_errors
from services.single_step_edit import _components, _messages, _same
from services.widget_edit_contract import (
    EditExpectation,
    EditIntent,
    EditPropertyValue,
    read_edit_property,
    same_edit_value,
    validate_edit_diff,
)


@dataclass
class EditValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _quality_signature(item: Diagnostic) -> tuple[str, str, str]:
    return item.code, item.json_pointer, json.dumps(item.actual, sort_keys=True)


def validate_edit_artifact(
    original: WidgetArtifact, candidate: WidgetArtifact, intent: EditIntent,
) -> EditValidationResult:
    result = EditValidationResult()
    result.errors.extend(theme_phase_errors(candidate.genui, layout=False))
    try:
        validate_edit_diff(original.genui, candidate.genui, intent)
        _visibility_errors(original.genui, candidate.genui, result)
        result.errors.extend(edit_expectation_errors(original.genui, candidate.genui, intent))
    except (ValueError, TypeError, RecursionError) as exc:
        result.errors.append(f"EDIT_SCOPE_INVALID: {exc}")
        return result
    if candidate.cardSpec.get("suggestSize") != intent.targetSize:
        result.errors.append("EDIT_SIZE_MISMATCH: 交付规格与接受的编辑目标不一致")
    settings = get_settings()
    options = ValidationOptions(
        edit_mode=True,
        asset_src_url_mapping=dict(settings.asset_src_url_mapping),
        capabilities_dir=(
            settings.data_root / "capabilities" / candidate.meta.capabilityRegistryVersion
        ),
    )
    baseline = validate_card(
        artifact=original.model_dump(mode="json", exclude_none=True), options=options,
    )
    historical = set()
    for item in baseline.diagnostics:
        if item.stage == "quality":
            historical.add(_quality_signature(item))
    reporter = validate_card(
        artifact=candidate.model_dump(mode="json", exclude_none=True), options=options,
    )
    for item in reporter.diagnostics:
        message = f"{item.code}: {item.message} [{item.json_pointer}]"
        if item.stage == "quality" and _quality_signature(item) in historical:
            result.warnings.append(f"历史视觉诊断：{message}")
        elif item.severity == "error":
            result.errors.append(message)
        else:
            result.warnings.append(message)
    return result


def edit_expectation_errors(original: str, candidate: str, intent: EditIntent) -> list[str]:
    """检查已接受的属性目标；不以自然语言词法代替意图理解。"""
    before_nodes = _components(_messages(original))
    after_nodes = _components(_messages(candidate))
    errors = []
    for expected in intent.expectations:
        before = read_edit_property(before_nodes.get(expected.componentId, {}), expected.property)
        after = read_edit_property(after_nodes.get(expected.componentId, {}), expected.property)
        if not _expectation_matches(expected, before, after):
            errors.append(
                f"EDIT_EXPECTATION_UNMET: {expected.componentId}.{expected.property} "
                f"要求 {expected.operator} {expected.value!r}，"
                f"实际存在={after.exists} 值={after.value!r}",
            )
    return errors


def _expectation_matches(
    expected: EditExpectation, before: EditPropertyValue, after: EditPropertyValue,
) -> bool:
    matched = False
    if expected.operator == "remove":
        matched = not after.exists
    elif expected.operator == "preserve":
        matched = before.exists == after.exists
        matched = matched and same_edit_value(expected.property, before.value, after.value)
    elif expected.operator == "equal":
        matched = after.exists and same_edit_value(expected.property, expected.value, after.value)
    else:
        old_number, new_number = _number(before.value), _number(after.value)
        if old_number is not None and new_number is not None:
            if expected.operator == "increase":
                matched = new_number > old_number
            elif expected.operator == "decrease":
                matched = new_number < old_number
    return matched


def _number(value: Any) -> float | None:
    result: float | None = None
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        result = float(value)
    return result


def _visibility_errors(original: str, candidate: str, result: EditValidationResult) -> None:
    before_nodes, after_nodes = _components(_messages(original)), _components(_messages(candidate))
    for identity, node in after_nodes.items():
        before = before_nodes.get(identity, {})
        styles = node.get("styles", {})
        old_styles = before.get("styles", {})
        if not isinstance(styles, dict) or not isinstance(old_styles, dict):
            continue
        if _same(styles, old_styles):
            continue
        visibility = styles.get("visibility")
        if visibility in {"hidden", "none"}:
            result.errors.append(f"EDIT_CONTENT_HIDDEN: 不能隐藏原卡内容或承载区 {identity}")
        if node.get("component") != "Text":
            continue
        font = _number(styles.get("fontSize"))
        height = _number(styles.get("height"))
        if font is not None and height is not None:
            if height < font * 0.5:
                result.errors.append(f"EDIT_TEXT_CLIPPED: {identity} 固定高度明显无法容纳文字")
        minimum = _number(styles.get("minFontSize", font))
        if minimum is not None and minimum < 8:
            result.errors.append(f"EDIT_TEXT_UNREADABLE: {identity} 最小字号低于可读基线")
    _fixed_container_errors(before_nodes, after_nodes, result)
    # 不把未知 matchParent 尺寸换算为机型像素；未提供真实视口只能给渲染复核提示。
    result.warnings.append("编辑布局与文字仍需按端侧实际承载尺寸复核，不以未知宿主保证无裁切")


def _fixed_container_errors(before: dict, after: dict, result: EditValidationResult) -> None:
    """只检查已知固定容器中的确定性矛盾，不估算未知宿主或经验文字宽度。"""
    for identity, node in after.items():
        styles = node.get("styles", {})
        if not isinstance(styles, dict):
            continue
        children = node.get("children")
        if not isinstance(children, list):
            continue
        for child_id in children:
            child = after.get(child_id, {})
            child_styles = child.get("styles", {})
            if not isinstance(child_styles, dict):
                continue
            if child.get("component") == "Text":
                old_parent = before.get(identity, {})
                old_child = before.get(child_id, {})
                deficit = _text_height_deficit(styles, child_styles)
                old_deficit = _text_height_deficit(
                    old_parent.get("styles", {}), old_child.get("styles", {}),
                )
                if deficit > old_deficit:
                    result.errors.append(
                        f"EDIT_TEXT_CLIPPED: {identity} 固定高度不足以容纳文字 {child_id}；"
                        "请在获准范围内调整承载高度或字号",
                    )
            if _same(node, before.get(identity)) and _same(child, before.get(child_id)):
                continue
            if child_styles.get("flexShrink", 1) != 0:
                continue
            for axis in ("width", "height"):
                parent_extent = _number(styles.get(axis))
                child_extent = _number(child_styles.get(axis))
                if parent_extent is not None and child_extent is not None:
                    if child_extent > parent_extent:
                        result.errors.append(f"EDIT_FIXED_OVERFLOW: {identity}/{child_id} {axis}")


def _text_height_deficit(parent_styles: dict, text_styles: dict) -> float:
    height = _number(parent_styles.get("height"))
    minimum = _number(text_styles.get("minFontSize", text_styles.get("fontSize")))
    deficit = 0.0
    if height is not None and minimum is not None:
        deficit = max(0.0, minimum - height)
    return deficit
