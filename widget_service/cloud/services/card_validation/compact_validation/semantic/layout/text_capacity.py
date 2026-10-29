"""静态完整文字的参考容量判定，供语义组件展开与校验共同调用。"""

from typing import Any

from services.static_text_capacity import TextCapacity, measure_text

from ...diagnostics import CompactDiagnostic


def static_plan_capacity_errors(plan: dict[str, Any], size: str) -> list[str]:
    """只检查动作和正文角色；文字承载以实际组件展开和整卡预算为准。"""
    facts = plan.get("info_required", [])
    groups = plan.get("contentGroups", [])
    objects = [group for group in groups if group.get("kind") == "object"]
    actions = [item for item in facts if "actionId" in item]
    prefix = "COMPACT_STATIC_TEXT_CAPACITY: "
    if actions:
        return [prefix + "静态合同只展示内容，不支持Action；请使用能力型请求链路。"]
    record_groups = _record_list_object_groups(plan, objects, facts)
    if len(record_groups) > 3 and not static_plan_candidate_preserves_required_content(plan, size):
        return [prefix + (
            "TextList最多三项，含标题最多两项；请在Plan核对已选记录与实际组件容量。"
            "SingleLineList仅适合能完整单行承载的短键值，不是记录数超限的通用替代；"
            "普通Plan沿原合同合理取舍并同步展示账本与遗漏声明，恢复Plan仍须保持固定事实。"
        )]
    if not objects and not actions and any("text" in item for item in facts):
        return [prefix + "正文至少有一个object组，不能将全部正文移到shared标题或说明。"]
    return []


def static_plan_candidate_preserves_required_content(plan: dict[str, Any], size: str) -> bool:
    """已归一化 Plan 的实际候选须独立通过原合同；偏好不等同于最终承载组件。"""
    from services.card_validation import CompactDslValidationError, validate_compact_dsl
    from services.compact_high_level_components import CompactDslConversionError
    from services.generation_content_policy import current_content_policy

    from ..static_content import static_fact_coverage, static_group_errors

    source = plan.get("staticPresentation")
    if not isinstance(source, str) or not source.strip():
        return False
    if not current_content_policy().is_static or size not in {"2x2", "2x4"}:
        return False
    try:
        validate_compact_dsl(
            source,
            task_spec={
                "size": size, "dataModelSchema": {"data": {}},
                "eventCandidates": [], "assetCandidates": [],
            },
            card_spec={"suggestSize": size}, compact_plan=plan,
            layout_scope=f"{'S' if size == '2x2' else 'W'}-static-content-guided",
        )
    except (CompactDslValidationError, CompactDslConversionError):
        return False
    if static_group_errors(source, plan):
        return False
    facts = plan.get("info_required", [])
    coverage = static_fact_coverage(source, plan)
    indexes = {item.fact_index for item in coverage}
    if indexes != set(range(len(facts))):
        return False
    for item in coverage:
        if item.visible:
            continue
        fact = facts[item.fact_index]
        if fact.get("priority") != "should":
            return False
        if fact.get("protectedTexts") or fact.get("preserveVerbatim"):
            return False
    return True


def _record_list_object_groups(
    plan: dict[str, Any],
    objects: list[dict[str, Any]],
    facts: list[Any],
) -> list[dict[str, Any]]:
    """识别已明确选择单个 TextList 的对象组。"""
    if plan.get("presentationStyle") == "records":
        return objects
    if plan.get("presentationStyle") in {"content", "rows", "comparison"}:
        return []
    result = []
    for group in objects:
        preferred_record_list = False
        for fact_index in group.get("factIndexes", []):
            if type(fact_index) is not int or not 0 <= fact_index < len(facts):
                continue
            fact = facts[fact_index]
            if not isinstance(fact, dict):
                continue
            hints = fact.get("componentHints")
            if isinstance(hints, list) and hints and hints[0] == "TextList":
                preferred_record_list = True
                break
        if preferred_record_list:
            result.append(group)
    return result


def require_static_text_capacity(
    text: str,
    width: float,
    spec: dict[str, Any],
    location: str,
) -> TextCapacity:
    try:
        capacity = measure_text(text, width, spec)
    except ValueError as exc:
        prefix = "COMPACT_STATIC_TEXT_CAPACITY: "
        if not str(exc).startswith(prefix + "关键读数 "):
            raise
        message = prefix + location + " " + str(exc).removeprefix(prefix)
        raise ValueError(message) from exc
    if not capacity.fits:
        message = (
            f"{location} 完整文字需要 {capacity.lines} 行，{width:g}vp 区域仅允许 "
            f"{capacity.maximum_lines} 行；请保持已接受文字与字号，换用更合适的组件；"
            "Plan阶段才能忠实精简。"
        )
        diagnostic = static_capacity_diagnostic(message)
        raise ValueError(diagnostic.message)
    return capacity


def static_capacity_diagnostic(message: str) -> CompactDiagnostic:
    return CompactDiagnostic(
        code="COMPACT_STATIC_TEXT_CAPACITY",
        validation_class="semantic",
        category="layout",
        message=message,
        legacy_message=message,
        expected={"completeTextFits": True, "fontSizeUnchanged": True},
    )


def capacity_diagnostic_from_error(error: ValueError) -> CompactDiagnostic | None:
    diagnostic: CompactDiagnostic | None = None
    message = str(error)
    if message.startswith("COMPACT_STATIC_TEXT_CAPACITY:"):
        diagnostic = static_capacity_diagnostic(message)
    return diagnostic
