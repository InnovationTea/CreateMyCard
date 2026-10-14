"""纯文本胶囊动作展开为标准 Button 的样式与事件回归。"""

import json
from typing import Literal

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


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("template_id", ["PillAction@1", "IconAction@1"])
def test_action_expansion_preserves_text_or_icon_and_one_event(
    size: Literal["2x2", "2x4"],
    template_id: str,
) -> None:
    props: dict[str, object] = {"actionId": _ACTION}
    if template_id == "PillAction@1":
        props["label"] = _LABEL
    else:
        props["icon"] = _ICON
    result = _expand_action(size, template_id, props)
    result = _lower_action_template_tree(
        result, background="#331F4799", foreground="#FF1F4799",
    )
    nodes: list[Nested2Node] = []
    pending = [result]
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(node.children)
    buttons = [node for node in nodes if node.component_type == "Button"]
    images = [node.values[0] for node in nodes if node.component_type == "Image"]
    if template_id == "PillAction@1":
        assert nodes == buttons == [result]
        assert result.values[0] == _LABEL
        assert result.children == ()
        styles = result.values[-1]
        assert isinstance(styles, dict)
        assert styles.get("width") == "matchParent"
        assert styles.get("height") == 36
        assert styles.get("borderRadius") == 18
        assert styles.get("fontSize") == 14
        assert styles.get("fontWeight") == 500
        assert styles.get("backgroundColor") == "#331F4799"
        assert styles.get("fontColor") == "#FF1F4799"
    else:
        assert result.component_type == "Stack"
        assert buttons == []
    assert images == ([_ICON] if template_id == "IconAction@1" else [])
    events = []
    for node in nodes:
        for value in node.values:
            if isinstance(value, dict) and "onClick" in value:
                events.append(value.get("onClick"))
    assert events == [
        [
            {
                "call": "clickToIntent",
                "args": {"intentName": "SetPowerSavingMode"},
            }
        ]
    ]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("icon", [_ICON, "", None])
def test_pill_action_rejects_icon_even_when_asset_is_trusted(
    size: Literal["2x2", "2x4"],
    icon: str | None,
) -> None:
    with pytest.raises(TerselConversionError, match="Additional properties.*icon"):
        _expand_action(
            size,
            "PillAction@1",
            {
                "actionId": _ACTION,
                "label": _LABEL,
                "icon": icon,
            },
        )
