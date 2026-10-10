"""Tests for the versioned Compact high-level component visual contract."""

import json

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
        "SingleLineTitle",
        "DoubleLineTitle",
        "Badge",
        "PillButton",
        "CircleButton",
        "EmphasizedData",
        "EmphasisText",
        "SecondaryBody",
        "InfoBlock",
        "H_BarChart",
        "NumericRatioStack",
        "ProgressCircle",
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
    assert contract["components"]["ProgressCircle"]["alignment"] == "aligned"
    assert contract["components"]["ProgressLine2"]["alignment"] == "aligned"
    assert contract["components"]["ProgressCircleSingle"]["alignment"] == "aligned"
    assert contract["components"]["DataDisplay"]["alignment"] == "aligned"
    assert contract["components"]["SummaryList"]["alignment"] == "native"
    assert contract["components"]["SingleLineTitle"]["alignment"] == "aligned"


def test_visual_recipe_resolves_size_overrides_without_mutating_cache() -> None:
    first = component_visual_recipe("InfoBlock", size="2x4")
    second = component_visual_recipe("InfoBlock", size="2x4")

    assert first["parts"]["root"]["styles"]["width"] == "matchParent"
    assert first["parts"]["root"]["styles"]["height"] == 57
    assert first["parts"]["root"]["styles"]["borderRadius"] == 16
    first["parts"]["root"]["styles"]["width"] = 999
    assert second["parts"]["root"]["styles"]["width"] == "matchParent"


def test_single_line_title_visual_recipe_is_text_only() -> None:
    recipe = component_visual_recipe("SingleLineTitle", size="2x2")

    assert recipe["parts"]["root"]["styles"]["itemMargin"] == 0
    assert set(recipe["parts"]) == {"root", "title"}
    assert "variants" not in recipe


def test_emphasized_data_visual_recipe_aligns_content_to_start_and_baseline() -> None:
    recipe = component_visual_recipe("EmphasizedData", size="2x2")

    root = recipe["parts"]["root"]["styles"]
    assert root["width"] == "matchParent"
    assert root["justifyContent"] == "start"
    assert root["alignItems"] == "top"
    assert recipe["parts"]["unit"]["styles"]["margin"] == {"top": 17}


def test_text_block_visual_recipe_declares_two_to_four_item_capacity() -> None:
    recipe = component_visual_recipe("TextBlock", size="2x4")

    assert recipe["metrics"] == {
        "minimumItems": 2,
        "maximumItems": 4,
    }
    root = recipe["parts"]["root"]["styles"]
    assert "height" not in root
    assert root["itemMargin"] == 8
    assert root["justifyContent"] == "start"
    assert root["layoutWeight"] == 1
    assert root["constraintSize"] == {"minHeight": 48, "maxHeight": 64}
    assert recipe["parts"]["item"]["styles"]["height"] == "matchParent"
    assert recipe["parts"]["item"]["styles"]["layoutWeight"] == 1
    assert recipe["parts"]["item"]["styles"]["constraintSize"]["minWidth"] == 64


def test_secondary_body_visual_recipe_has_controlled_text_roles() -> None:
    base = component_visual_recipe("SecondaryBody", size="2x2")
    body = component_visual_recipe("SecondaryBody", size="2x2", variant="body")
    multiline = component_visual_recipe(
        "SecondaryBody",
        size="2x2",
        variant="bodyMultiline",
    )
    metadata = component_visual_recipe(
        "SecondaryBody",
        size="2x2",
        variant="metadata",
    )

    assert base["metrics"] == {"minimumItems": 1, "maximumItems": 4}
    assert body["parts"]["text"]["styles"]["fontSize"] == 14
    assert body["parts"]["text"]["styles"]["fontWeight"] == 400
    assert multiline["parts"]["text"]["styles"]["height"] == 40
    assert multiline["parts"]["text"]["styles"]["maxLines"] == 2
    assert metadata["parts"]["text"]["styles"]["fontSize"] == 12
    assert metadata["parts"]["text"]["styles"]["height"] == 18


def test_visual_recipe_contract_uses_consistent_icon_and_overflow_rules() -> None:
    contract = load_visual_recipe_contract()
    components = contract["components"]

    assert components["InfoBlock"]["parts"]["icon"]["styles"] == {
        "width": 24,
        "height": 24,
        "objectFit": "contain",
        "flexShrink": 0,
    }
    assert "icon" not in components["SingleLineTitle"]["parts"]
    assert components["CardButton"]["parts"]["icon"]["styles"]["width"] == 24
    assert components["CardButton"]["parts"]["icon"]["styles"]["height"] == 24
    assert components["CardButton"]["parts"]["placeholder"]["styles"]["width"] == 24
    assert components["CardButton"]["parts"]["placeholder"]["styles"]["height"] == 24
    assert components["CircleButton"]["parts"]["root"]["styles"]["width"] == 40
    assert components["CircleButton"]["parts"]["root"]["styles"]["height"] == 40
    assert "ellipsis" not in json.dumps(contract)


def test_visual_recipe_part_marks_only_internal_expansion_rows() -> None:
    component_type, styles = visual_recipe_part(
        "TableText",
        "value",
        size="2x2",
    )

    assert component_type == "Text"
    assert styles["fontSize"] == 12
    assert styles["_visualRecipe"] == (f"{VISUAL_RECIPE_VERSION}:TableText.value")

    wide_recipe = component_visual_recipe("TableText", size="2x4")
    assert wide_recipe["metrics"] == {"twoRowGap": 2, "threeRowGap": 2}

    _, compact_styles = visual_recipe_part(
        "TableText",
        "value",
        size="2x2",
        variant="compact",
    )
    assert compact_styles["fontSize"] == 10


def test_progress_circle_height_follows_latest_runtime_line_count() -> None:
    two_line = component_visual_recipe("ProgressCircleSingle", size="2x4")
    three_line = component_visual_recipe(
        "ProgressCircleSingle",
        size="2x4",
        variant="withSecondary",
    )

    assert two_line["parts"]["root"]["styles"]["height"] == 44
    assert two_line["parts"]["labels"]["styles"]["height"] == 44
    assert three_line["parts"]["root"]["styles"]["height"] == 46
    assert three_line["parts"]["labels"]["styles"]["height"] == 46

    small = component_visual_recipe(
        "ProgressCircleSingle",
        size="2x2",
        variant="twoByTwo",
    )
    small_with_secondary = component_visual_recipe(
        "ProgressCircleSingle",
        size="2x2",
        variant="twoByTwoWithSecondary",
    )
    assert small["parts"]["ring"]["styles"]["width"] == 52
    assert small["parts"]["root"]["styles"]["height"] == 52
    assert small_with_secondary["parts"]["root"]["styles"]["height"] == 52
    assert small_with_secondary["parts"]["secondary"]["styles"]["height"] == 16


def test_progress_circle_recipe_uses_claw_runtime_visual_metrics() -> None:
    recipe = component_visual_recipe("ProgressCircle", size="2x2")

    assert recipe["metrics"] == {
        "externalTextHeight": 14,
        "itemMargin": 2,
        "minimumRingDiameter": 40,
        "strokeWidth": 6,
    }
    assert recipe["parts"]["ring"]["component"] == "Progress"
    assert recipe["parts"]["icon"]["styles"]["width"] == 20
    assert recipe["parts"]["externalText"]["styles"]["fontSize"] == 10


def test_unknown_visual_recipe_variant_is_rejected() -> None:
    with pytest.raises(CompactComponentRuntimeError, match="is not registered"):
        component_visual_recipe("EventCard", variant="unknown")
