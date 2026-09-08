"""卡片名称不再隐式投影为 UX 布局中的可见标题。"""

from __future__ import annotations

import json
from typing import Literal

import pytest

from models.generation import TaskSpec
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.models import HybridBodyContract, HybridLimits
from services.template_generation.engine.cardplan.registry import CardPlanRegistry


@pytest.mark.parametrize(
    ("size", "layout"),
    [("2x2", "SingleFocusLayout"), ("2x4", "WideSingleFocusLayout")],
)
@pytest.mark.parametrize("explicit_title", [False, True])
def test_ux_layout_only_renders_explicit_titles(
    size: Literal["2x2", "2x4"], layout: str, explicit_title: bool
) -> None:
    title = "天气卡片名称"
    card_spec = {"title": title, "description": "显示天气", "suggestSize": size}
    contract = HybridBodyContract(
        theme_profile_id="family-weather-care-blue",
        allowed_components=("Text", "Column", "Stack", layout),
        allowed_design_tokens=("body",),
        allowed_layout_tokens=(),
        allowed_template_ids=(f"{layout}@1",),
        allowed_asset_sources=(),
        trusted_literals=(title, "晴"),
        trusted_numbers=(),
        required_literals=("晴",),
        protected_literals=("晴",),
        allowed_layout_component_ids=(layout,),
        limits=HybridLimits(
            max_raw_components=8,
            max_expanded_components=32,
            max_nesting_depth=9,
            vertical_budget_vp=126,
        ),
    )
    texts = ["晴"]
    if explicit_title:
        texts.insert(0, title)
    children = ",".join(f'Text({json.dumps(text, ensure_ascii=False)},"body")' for text in texts)
    source = f'Template("{layout}@1",{{}},Column({children}));'
    compilation = compile_ux_layout_card(
        source,
        task_spec=TaskSpec(userQuery="显示天气", size=size, dataModelSchema={"data": {}}),
        contract=contract,
        protocol_profile=A2UIProtocolRegistry().get_profile(),
        registry=CardPlanRegistry(),
        business_title=title,
        card_spec=card_spec,
    )
    message = json.loads(compilation.a2ui.splitlines()[1])
    update = message.get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    actual_texts = []
    for component in components:
        if component.get("component") == "Text":
            actual_texts.append(component.get("content"))
    assert actual_texts == texts
    assert card_spec == {"title": title, "description": "显示天气", "suggestSize": size}
