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
    if len(record_groups) > 3:
        return [prefix + "TextList最多三项，含标题最多两项；请改用单行列表或在Plan重新组织。"]
    if not objects and not actions and any("text" in item for item in facts):
        return [prefix + "正文至少有一个object组，不能将全部正文移到shared标题或说明。"]
    return []


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
    capacity = measure_text(text, width, spec)
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
