"""Regression coverage for the reviewed Q058/Q060/Q073 layout geometry."""

from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.template_generation.engine.cardplan.compiler import (
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
