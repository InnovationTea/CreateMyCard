"""确定性第二层组合：对已完全确定的选型直接产出 Tersel 调用树。

当第一层选型已经过度确定——恰好一个可行布局、每个业务组件在布局后缀
过滤后恰好剩一个候选 Template、Action children 由布局唯一确定——组合树
不再存在任何模型选择空间。本模块按与组合 LLM 完全相同的语法与契约渲染
这棵树，跳过第二次模型调用。字段级 ``required_template_groups`` 的覆盖
证明由 compiler 契约校验兜底。

安全边界：
- 产物仍必须通过 ``compile_ux_layout_card`` 的同一契约校验；任何校验失败
  在 ``pipeline.py`` 中回退到 LLM 组合路径，fail-closed 语义不变。
- 仅填充可唯一确定的资产 Prop（语义标签匹配候选恰为一个，与
  compiler.py ``_normalize_template_provider_params`` 的规则一致）；其余
  可选 Prop 一律省略，由模板的 ``#if`` 分支兜底。存在无法唯一确定的
  必填 Prop 时返回 ``None`` 交还 LLM。
"""

from __future__ import annotations

import json
from typing import Any

from services.template_generation.engine.cardplan.prompt import _parameter_value_kind
from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

from .ux_mixed_prompt import UxMixedPromptProjection

_ICON_ACTION_LAYOUT_ID = "FullIconActionLayout"
_PILL_ACTION_TEMPLATE_ID = "PillAction@1"
_ICON_ACTION_TEMPLATE_ID = "IconAction@1"


def compose_deterministic_tree(
    projection: UxMixedPromptProjection,
    registry: CardPlanRegistry,
) -> str | None:
    """Return the Tersel source for an over-determined composition, else ``None``."""
    selection = projection.layout_selection
    if len(selection.layout_ids) != 1 or selection.embeds_support_actions:
        return None
    layout_id = selection.layout_ids[0]
    components = projection.component_template_ids
    if not components:
        return None

    # 每个业务槽位（组件）必须恰好剩一个候选 Template；位置型布局按
    # business_layout_kinds_by_position 的后缀逐槽收窄。字段级
    # required_template_groups 的覆盖证明由 compiler 契约校验兜底。
    positional_kinds = selection.business_layout_kinds_by_position
    if positional_kinds and len(components) != len(positional_kinds):
        return None
    business_template_ids: list[str] = []
    for index, (_, template_ids) in enumerate(components):
        kind = positional_kinds[index] if positional_kinds else selection.layout_kinds[0]
        matching = [
            template_id
            for template_id in template_ids
            if provider_template_layout_kind(template_id) == kind
        ]
        if len(matching) != 1:
            return None
        business_template_ids.append(matching[0])

    actions = projection.selected_actions
    action_template_ids = projection.action_template_ids
    if actions:
        if len(action_template_ids) != 1:
            return None
        if len(actions) != len(projection.selected_action_ids):
            return None
        action_template_id = (
            _ICON_ACTION_TEMPLATE_ID
            if layout_id == _ICON_ACTION_LAYOUT_ID
            else _PILL_ACTION_TEMPLATE_ID
        )
        if action_template_id != action_template_ids[0]:
            return None
    elif action_template_ids:
        return None

    children: list[str] = []
    for template_id in business_template_ids:
        params = _deterministic_template_params(template_id, projection.contract, registry)
        if params is None:
            return None
        children.append(_template_call(template_id, params))
    children.extend(
        _template_call(action_template_ids[0], dict(action)) for action in actions
    )
    layout_template_id = f"{layout_id}@1"
    return (
        f"Template({json.dumps(layout_template_id)}, {{}}, "
        + ", ".join(children)
        + ");"
    )


def _deterministic_template_params(
    template_id: str,
    contract: Any,
    registry: CardPlanRegistry,
) -> dict[str, Any] | None:
    """Fill only uniquely-determined asset props; omit everything else."""
    definition = registry.require_template(template_id)
    if definition.source_format != "cardtpl/1" or len(definition.variants) != 1:
        return None
    variant = definition.variants[0]
    properties = variant.parameters_schema.get("properties", {})
    required_names = set(variant.parameters_schema.get("required", ()))
    params: dict[str, Any] = {}
    for name, schema in properties.items():
        value_kind = _parameter_value_kind(name, schema)
        if value_kind != "asset-source":
            # 可选字符串/动作 Prop 省略；必填则无法确定，交还 LLM。
            if name in required_names:
                return None
            continue
        candidates = _unique_asset_candidates(name, definition, contract)
        if len(candidates) == 1:
            params[name] = candidates[0]
        elif name in required_names:
            return None
    return params


def _unique_asset_candidates(
    name: str,
    definition: Any,
    contract: Any,
) -> tuple[str, ...]:
    """资产 Prop 的语义标签匹配候选（规则同 prompt.py 的 allowedSources）。"""
    required_tags = set(definition.asset_parameter_semantic_tags.get(name, ()))
    if not required_tags:
        return tuple(contract.allowed_asset_sources)
    return tuple(
        source
        for source in contract.allowed_asset_sources
        if required_tags.issubset(set(contract.asset_semantic_tags_by_source.get(source, ())))
    )


def _template_call(template_id: str, params: dict[str, Any]) -> str:
    serialized = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    return f"Template({json.dumps(template_id)}, {serialized})"
