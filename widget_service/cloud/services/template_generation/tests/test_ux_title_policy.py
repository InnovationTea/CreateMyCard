"""卡片名称不再隐式投影为 UX 布局中的可见标题。

2x2 / 2x4 × 显式/隐式标题共四种组合的编译产物已固化为场景金样（Layer C，
``ux_title__explicit_titles``，载荷按 case 键分组）：实际渲染的 Text 内容、
card_spec 编译前后的逐字段快照整体冻结——卡片名称只有显式写进模板体才会
渲染，编译既不回填标题也不修改 card_spec。引擎改动后按 golden 工作流
``check --diff`` / ``bless --declared`` 复核。
"""

from __future__ import annotations

import json

from models.generation import TaskSpec
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.models import HybridBodyContract, HybridLimits
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_SIZE_LAYOUTS: tuple[tuple[str, str], ...] = (
    ("2x2", "SingleFocusLayout"),
    ("2x4", "WideSingleFocusLayout"),
)


def _compile_explicit_titles(size: str, layout: str, explicit_title: bool) -> dict:
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
    card_spec_before = dict(card_spec)
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
    rendered_texts = [
        component.get("content")
        for component in components
        if component.get("component") == "Text"
    ]
    return {
        "texts": rendered_texts,
        "cardSpecBefore": card_spec_before,
        "cardSpecAfter": dict(card_spec),
    }


@scenario("ux_title__explicit_titles")
def _build_explicit_titles() -> dict:
    cases: dict[str, dict] = {}
    for size, layout in _SIZE_LAYOUTS:
        for explicit in (False, True):
            key = f"{size}_{'explicit' if explicit else 'implicit'}"
            cases[key] = _compile_explicit_titles(size, layout, explicit)
    return cases


def test_ux_layout_titles_match_golden_scenario() -> None:
    assert_golden_scenario("ux_title__explicit_titles")
