"""集中定义普通卡片和模板卡片的规则清单，两个校验入口共享选择逻辑。"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from enum import StrEnum


class CompactRule(StrEnum):
    """Compact 转换前可调度的规则组。解析和绑定提取始终执行。"""

    ASSET_SOURCE = "asset_source"
    COMPONENT_CONTRACT = "component_contract"
    FUSION_COMPOSITION = "fusion_composition"
    METRIC_LABEL = "metric_label"
    WEATHER_DATE = "weather_date"
    HERO_VALUE = "hero_value"
    HEIGHT_BUDGET = "height_budget"
    DUAL_ACTION = "dual_action"
    LAYOUT_ROUTE = "layout_route"
    DATA_CONTEXT = "data_context"


@dataclass(frozen=True)
class CardValidationPolicy:
    """场景配置只选择规则，不改变规则内部的阈值或错误语义。"""

    name: str
    compact_rules: frozenset[CompactRule]
    a2ui_validators: frozenset[str]
    display_unit_rules: frozenset[str]


_COMMON_COMPACT_RULES = frozenset({
    CompactRule.ASSET_SOURCE,
    CompactRule.COMPONENT_CONTRACT,
    CompactRule.HEIGHT_BUDGET,
    CompactRule.DUAL_ACTION,
    CompactRule.DATA_CONTEXT,
})
_COMMON_A2UI_VALIDATORS = frozenset({
    "protocol", "component", "aesthetic_baseline", "cardspec", "expression", "asset",
    "binding", "display_unit", "cross", "effective-capability",
})

STANDARD_VALIDATION_POLICY = CardValidationPolicy(
    name="standard",
    compact_rules=frozenset(CompactRule),
    a2ui_validators=_COMMON_A2UI_VALIDATORS | {"contrast"},
    display_unit_rules=frozenset({"DISPLAY_UNIT_MISSING", "DISPLAY_UNIT_DUPLICATED"}),
)
TEMPLATE_VALIDATION_POLICY = CardValidationPolicy(
    name="template",
    compact_rules=_COMMON_COMPACT_RULES,
    a2ui_validators=_COMMON_A2UI_VALIDATORS,
    display_unit_rules=frozenset({"DISPLAY_UNIT_DUPLICATED"}),
)


def resolve_validation_policy(
    *,
    root_id: str | None,
    root_children: object,
    component_ids: Iterable[str],
    duplicate_component_ids: Collection[str] = (),
) -> CardValidationPolicy:
    """仅接受存在、直接挂在 root 下且无重复 ID 的精确模板标记。"""
    ids = tuple(component_ids)
    unique_ids = set(ids)
    valid_ids = len(ids) == len(unique_ids) and not duplicate_component_ids
    has_roots = root_id == "root" and {"root", "template_root"}.issubset(unique_ids)
    direct_template = (
        isinstance(root_children, (list, tuple)) and "template_root" in root_children
    )
    policy = STANDARD_VALIDATION_POLICY
    if valid_ids and has_roots and direct_template:
        policy = TEMPLATE_VALIDATION_POLICY
    return policy
