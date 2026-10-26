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
    maximum_actions = 4 if size == "2x4" and not objects else 2
    if len(actions) > maximum_actions:
        return [
            prefix + f"当前静态布局最多承载{maximum_actions}个必要动作，不得删除动作以适配容量。"
        ]
    if not objects and any("text" in item for item in facts):
        return [prefix + "正文至少有一个object组，不能将全部正文移到shared标题或说明。"]
    return []


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
            f"{capacity.maximum_lines} 行；重组、精简补充或显式尾部省略，保留核心读数和保护文字。"
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
