"""Regression coverage for the reviewed Q058/Q060/Q073 layout geometry."""

from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.template_generation.engine.cardplan.compiler import (
    _constrain_content_height,
    _estimate_height,
    _instantiate_blueprint,
    _ux_layout_body_budget,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    _COMPACT_ROOT_DIMENSIONS,
)
from services.template_generation.engine.tersel_converter import Nested2Node


@pytest.mark.parametrize(
    ("template_id", "gap"),
    [
        ("ScheduleOverviewMeetingEntryHero@1", 10),
        ("BluetoothDeviceOverviewCaseConnectionHero@1", 8),
        ("BluetoothDeviceOverviewCaseSettingsHero@1", 4),
        ("BatteryOverviewChargeStatusHero@1", 8),
    ],
)
def test_reviewed_title_to_content_gap(template_id, gap):
    definition = CardPlanRegistry().require_template(template_id)
    options = definition.variants[0].root.values[-1]
    item_margin = options.properties.get("itemMargin")
    assert item_margin is not None
    assert item_margin.value == gap


@pytest.mark.parametrize("size", ["2x4", "4x2"])
def test_wide_canvas_is_300_by_150(size):
    assert _COMPACT_ROOT_DIMENSIONS.get(size) == {"width": 300, "height": 150}


def test_square_canvas_is_unchanged():
    assert _COMPACT_ROOT_DIMENSIONS.get("2x2") == {"width": 160, "height": 160}


def test_large_action_fits_wide_half_slot():
    definition = CardPlanRegistry().require_template("LargeIconAction@1")
    options = definition.variants[0].root.values[-1]
    width = options.properties.get("width")
    height = options.properties.get("height")
    assert width is not None
    assert height is not None
    assert width.value == height.value == 59


@pytest.mark.parametrize(
    "template_id",
    [
        "WideSingleFocusLayout@1",
        "WideTwoHalfLayout@1",
        "WideFullTwoCompactLayout@1",
        "WideFourCompactLayout@1",
        "WideFullHeroTwoActionLayout@1",
        "WideFullFourActionLayout@1",
        "WideHalfCompactTwoLargeActionLayout@1",
    ],
)
@pytest.mark.parametrize("compact_rows", [False, True])
def test_wide_layout_fixed_slots_fit_content_budget(template_id, compact_rows):
    registry = CardPlanRegistry()
    definition = registry.require_template(template_id)
    child = Nested2Node("Text", ("content", {"height": 14}), ())
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {"compactRows": compact_rows},
        theme_values={"supportContentStyle.backgroundColor": "#FFFFFFFF"},
        spread_children=(child,) * 5,
    )
    budget = _ux_layout_body_budget(registry, "2x4")
    assert budget == 126
    if template_id == "WideSingleFocusLayout@1":
        # C270 真机修复后的既定几何：内容槽 layoutWeight 弹性吸收
        # 126 - 36(动作槽) - 8(根 itemMargin)，估计器按子节点高度计算该槽，
        # 因此断言固定几何不超预算且动作槽高度保持 36。
        assert 0 < _estimate_height(root) <= budget
        action_options = root.children[1].values[-1]
        assert action_options["height"] == 36
    else:
        assert _estimate_height(root) == budget


@pytest.mark.parametrize(
    "template_id",
    [
        "WideFullHeroActionLayout@1",
        "WideHeroActionFullLayout@1",
    ],
)
def test_wide_full_hero_action_flexes_within_content_budget(template_id):
    """Full+Hero+Action 两个半区与 WideTwoFocusTwoActionLayout 同构：弹性槽位吸收底板内边距。"""
    registry = CardPlanRegistry()
    definition = registry.require_template(template_id)
    child = Nested2Node("Text", ("content", {"height": 14}), ())
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        theme_values={
            "supportContentStyle.backgroundColor": "#FFFFFFFF",
            "supportContentStyle.borderRadius": 16,
        },
        spread_children=(child,) * 5,
    )
    budget = _ux_layout_body_budget(registry, "2x4")
    assert 0 < _estimate_height(root) <= budget


def test_production_prompt_uses_current_wide_canvas():
    cloud = Path(__file__).resolve().parents[3]
    prompt = (cloud / "data/protocol_profiles/design-compact-dsl/PROMPT.md").read_text(
        encoding="utf-8"
    )
    assert "300vp × 150vp" in prompt
    assert "276vp × 126vp" in prompt
    assert "59 + 8 + 59 = 126" in prompt
    assert "320vp × 160vp" not in prompt
    assert "296×136" not in prompt
    assert "320×160" not in prompt


@pytest.mark.parametrize(
    ("size", "row_height", "overflows"),
    [("2x4", 59, False), ("2x4", 64, True), ("2x2", 59, False), ("2x2", 64, True)],
)
def test_prompt_row_budget_matches_validator(size, row_height, overflows):
    source = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12,"itemMargin":8},["top","bottom"]]',
            f'["top","Text",{{"content":"Top","height":{row_height}}}]',
            f'["bottom","Text",{{"content":"Bottom","height":{row_height}}}]',
        ]
    )
    task = {"size": size, "dataModelSchema": {"data": {}}, "assetCandidates": []}
    if overflows:
        with pytest.raises(CompactDslValidationError, match="overflows by 10vp"):
            validate_compact_dsl(source, task_spec=task, card_spec={"dataBindings": []})
    else:
        validate_compact_dsl(source, task_spec=task, card_spec={"dataBindings": []})


def _wide_action_wrapper_tree() -> Nested2Node:
    """WideSingleFocusLayout@1 的包装结构:Column[内容槽(LW:1)[业务根], action 槽]。"""
    button = Nested2Node(
        "Button",
        (
            "今日训练",
            {
                "width": "matchParent",
                "height": 36,
                "onClick": [{"call": "clickToIntent", "args": {"intentName": "demo"}}],
            },
        ),
        (),
    )
    action = Nested2Node(
        "Column",
        ({"width": "matchParent", "height": 36},),
        (button,),
    )
    split_row = Nested2Node(
        "Row",
        (
            {
                "width": "100%",
                "height": "100%",
                "justifyContent": "spaceBetween",
                "alignItems": "center",
            },
        ),
        (),
    )
    content = Nested2Node(
        "Column",
        ({"width": "matchParent", "layoutWeight": 1},),
        (split_row,),
    )
    return Nested2Node(
        "Column",
        ({"width": "matchParent", "height": "matchParent"},),
        (content, action),
    )


def test_constrain_hoists_action_slot_into_content_on_2x4():
    """C270 修复:action 槽嵌进内容槽(单子包装),业务根高度钉为 budget-44。

    真机渲染器(genui_form)在包装 Column 同时持有内容槽+action 槽时,
    会让内容槽内 matchParent 后代的宽度塌缩成内容宽;单子包装可规避。
    """
    root = _constrain_content_height(_wide_action_wrapper_tree(), 126, "2x4")
    assert root.component_type == "Column"
    assert len(root.children) == 1
    content = root.children[0]
    assert [child.component_type for child in content.children] == ["Row", "Column"]
    row_options = next(v for v in content.children[0].values if isinstance(v, dict))
    assert row_options["height"] == 82  # 126 - 36(action) - 8(gap)
    action_options = next(v for v in content.children[1].values if isinstance(v, dict))
    assert action_options["height"] == 36
    button = content.children[1].children[0]
    button_options = next(v for v in button.values if isinstance(v, dict))
    assert button_options["onClick"][0]["call"] == "clickToIntent"


def test_constrain_keeps_action_slot_sibling_on_2x2():
    """2x2 不做 action 槽嵌套(塌缩未在 2x2 复现,保持原布局)。"""
    root = _constrain_content_height(_wide_action_wrapper_tree(), 136, "2x2")
    assert len(root.children) == 2
    root_options = next(v for v in root.values if isinstance(v, dict))
    assert root_options["height"] == 136
    assert root_options["clip"] is True
