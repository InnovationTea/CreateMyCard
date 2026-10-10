# -*- coding: utf-8 -*-
"""纯文本胶囊动作展开为标准 Button 的样式与事件回归。

Layer C 迁移：PillAction@1 / IconAction@1 在 HeroActionLayout@1 内、2x2 与
2x4 共四种组合的展开+降级产物（组件树、样式与 onClick 载荷）已固化为场景
金样（pill_action__pill|icon__2x2|2x4），内联样式/结构断言由快照整体冻结。
icon 属性拒绝路径（PillAction 携带 icon/空串/null × 2x2/2x4 六种组合）同样
固化为按 case 键分组的错误场景金样（pill_action__reject_icon，冻结
errorType 与完整报错文案）。行为性断言保留：PillAction 的动作规则文案
（"只展示文本，禁止设置 icon"）仍为内联显式断言。
"""

import json
from typing import Any, Literal

import pytest

from models.generation import EventAction, TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _expand_call,
    _ExpansionState,
    _lower_action_template_tree,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.parser import parse_ux_layout_card
from services.template_generation.engine.cardplan.prompt import (
    _ux_layout_action_rule,
    action_bindings,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_ICON = "resources/base/media/battery_leaf_fill.svg"
_ACTION = "event.setPowerSavingMode"
_LABEL = "省电模式"


def _expand_action(
    size: Literal["2x2", "2x4"],
    template_id: str,
    props: dict[str, object],
) -> Nested2Node:
    task = TaskSpec(
        userQuery="切换省电模式",
        size=size,
        dataModelSchema={},
        eventCandidates=[
            EventAction(
                id=_ACTION,
                displayLabel=_LABEL,
                call="clickToIntent",
                args={"intentName": "SetPowerSavingMode"},
            )
        ],
    )
    contract = HybridBodyContract.model_construct(
        theme_profile_id="family-weather-care-blue",
        allowed_template_ids=(template_id,),
        allowed_asset_sources=(_ICON,),
        trusted_literals=(_LABEL,),
        trusted_numbers=(),
        action_bindings=action_bindings(task),
        content_action_ids=(_ACTION,),
    )
    if template_id == "PillAction@1":
        assert "只展示文本，禁止设置 icon" in _ux_layout_action_rule(contract)
    source = (
        'Template("HeroActionLayout@1",{},'
        f'Template("{template_id}",{json.dumps(props, ensure_ascii=False)}));'
    )
    state = _ExpansionState(template_ids=[], action_ids=[], action_occurrences=[])
    result = _expand_call(
        parse_ux_layout_card(source).children[0],
        parent="Column",
        contract=contract,
        registry=get_cardplan_registry(),
        state=state,
        task_spec=task,
        provider_binding_roots={},
    )
    assert state.action_occurrences == [_ACTION]
    return result


def _serialize_value(value: object) -> object:
    if isinstance(value, Nested2Node):
        return _serialize_node(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_node(node: Nested2Node) -> dict[str, object]:
    return {
        "component": node.component_type,
        "values": [_serialize_value(value) for value in node.values],
        "children": [_serialize_node(child) for child in node.children],
    }


def _build_action_expansion(size: Literal["2x2", "2x4"], template_id: str) -> dict:
    props: dict[str, object] = {"actionId": _ACTION}
    if template_id == "PillAction@1":
        props["label"] = _LABEL
    else:
        props["icon"] = _ICON
    result = _expand_action(size, template_id, props)
    result = _lower_action_template_tree(
        result, background="#331F4799", foreground="#FF1F4799",
    )
    return _serialize_node(result)


@scenario("pill_action__pill__2x2")
def _build_pill_2x2() -> dict:
    return _build_action_expansion("2x2", "PillAction@1")


@scenario("pill_action__pill__2x4")
def _build_pill_2x4() -> dict:
    return _build_action_expansion("2x4", "PillAction@1")


@scenario("pill_action__icon__2x2")
def _build_icon_2x2() -> dict:
    return _build_action_expansion("2x2", "IconAction@1")


@scenario("pill_action__icon__2x4")
def _build_icon_2x4() -> dict:
    return _build_action_expansion("2x4", "IconAction@1")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("template_id", ["PillAction@1", "IconAction@1"])
def test_action_expansion_preserves_text_or_icon_and_one_event(
    size: Literal["2x2", "2x4"],
    template_id: str,
) -> None:
    slug = "pill" if template_id == "PillAction@1" else "icon"
    assert_golden_scenario(f"pill_action__{slug}__{size}")


_ICON_REJECT_CASES: tuple[tuple[str, object], ...] = (
    ("icon", _ICON), ("empty", ""), ("none", None),
)


@scenario("pill_action__reject_icon")
def _build_reject_icon() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for size in ("2x2", "2x4"):
        for slug, icon in _ICON_REJECT_CASES:
            try:
                _expand_action(
                    size,
                    "PillAction@1",
                    {"actionId": _ACTION, "label": _LABEL, "icon": icon},
                )
            except TerselConversionError as exc:
                payload[f"{size}__{slug}"] = {
                    "errorType": type(exc).__name__, "message": str(exc),
                }
            else:  # pragma: no cover - PillAction 必须拒绝 icon 属性
                payload[f"{size}__{slug}"] = {"error": "NO_ERROR"}
    return payload


def test_pill_action_reject_icon_matches_golden_scenario() -> None:
    assert_golden_scenario("pill_action__reject_icon")
