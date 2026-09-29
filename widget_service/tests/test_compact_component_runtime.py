"""Tests for the versioned Compact high-level component visual contract."""

import pytest

from services.compact_component_runtime import (
    VISUAL_RECIPE_VERSION,
    CompactComponentRuntimeError,
    component_visual_recipe,
    load_visual_recipe_contract,
    visual_recipe_part,
)


def test_visual_recipe_contract_registers_all_high_level_components() -> None:
    contract = load_visual_recipe_contract()

    assert contract["version"] == VISUAL_RECIPE_VERSION
    assert set(contract["components"]) == {
        "PillButton",
        "CircleButton",
        "EmphasizedData",
        "InfoBlock",
        "ProgressLine2",
        "TableText",
        "TextBlock",
        "CardButton",
        "ProgressCircleSingle",
        "EventCard",
        "DataDisplay",
        "TopTextBottomValue",
        "SummaryList",
    }
    assert contract["components"]["InfoBlock"]["alignment"] == "aligned"
    assert contract["components"]["ProgressLine2"]["alignment"] == "adapted"
    assert contract["components"]["SummaryList"]["alignment"] == "native"


def test_visual_recipe_resolves_size_overrides_without_mutating_cache() -> None:
    first = component_visual_recipe("InfoBlock", size="2x4")
    second = component_visual_recipe("InfoBlock", size="2x4")

    assert first["parts"]["root"]["styles"]["width"] == 132
    assert first["parts"]["root"]["styles"]["height"] == 57
    assert first["parts"]["root"]["styles"]["borderRadius"] == 16
    first["parts"]["root"]["styles"]["width"] = 999
    assert second["parts"]["root"]["styles"]["width"] == 132


def test_visual_recipe_part_marks_only_internal_expansion_rows() -> None:
    component_type, styles = visual_recipe_part(
        "TableText",
        "value",
        size="2x2",
    )

    assert component_type == "Text"
    assert styles["fontSize"] == 10
    assert styles["_visualRecipe"] == (f"{VISUAL_RECIPE_VERSION}:TableText.value")


def test_unknown_visual_recipe_variant_is_rejected() -> None:
    with pytest.raises(CompactComponentRuntimeError, match="is not registered"):
        component_visual_recipe("EventCard", variant="unknown")
