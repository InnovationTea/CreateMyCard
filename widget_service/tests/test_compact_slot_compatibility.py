"""槽位检查从共享合同读取角色和 Recipe，不放宽容量或辅助语义。"""

import pytest

from services.compact_slot_compatibility import (
    auxiliary_groups_have_core,
    check_component_slot,
    component_slot_matrix,
)


@pytest.mark.parametrize("name", ["TableText", "EmphasisText"])
def test_dual_action_content_rejects_known_overflow(name: str) -> None:
    placements = ["items[0].value", "items[1].value"]
    if name == "EmphasisText":
        placements = ["mainText", "secondaryText"]
    else:
        placements.append("items[2].value")
    result = check_component_slot(
        {"component": name, "placements": placements}, size="2x2",
        layout_id="S-content-dual-action", slot_rule={"types": ["Column", "Row"]},
        width=126.0, height=38.0,
    )
    assert result.status == "incompatible"
    assert result.minimum_height is not None and result.minimum_height > 38.0


def test_auxiliary_fit_still_requires_a_core() -> None:
    result = check_component_slot(
        {"component": "SecondaryBody", "placements": ["items[0].value", "items[1].value"],
         "columns": 1}, size="2x2", layout_id="S-content-dual-action",
        slot_rule={"types": ["Column"]}, width=126.0, height=38.0,
    )
    assert result.status == "conditional"
    assert result.requires_core_information


@pytest.mark.parametrize("name", ["InfoBlock", "CardButton", "TextBlock"])
def test_role_restrictions_survive_available_space(name: str) -> None:
    result = check_component_slot(
        {"component": name}, size="2x4", layout_id="W-split-panels",
        slot_rule={"types": ["Column"]}, width=300.0, height=300.0,
    )
    assert result.status == "incompatible"


def test_unmodeled_capacity_is_unknown() -> None:
    result = check_component_slot(
        {"component": "EventCard"}, size="2x2", layout_id="S-title-content",
        slot_rule={"types": ["Column"]}, width=126.0, height=100.0,
    )
    assert result.status == "unknown"
    assert result.minimum_height is None


def test_actual_group_height_cannot_be_replaced_by_smaller_recipe_lower_bound() -> None:
    result = check_component_slot(
        {"component": "TableText", "placements": ["items[0].value", "items[1].value"],
         "requiredHeight": 52.0}, size="2x2", layout_id="S-content-dual-action",
        slot_rule={"types": ["Column"]}, width=126.0, height=38.0,
    )
    assert result.status == "incompatible"
    assert result.minimum_height == 52.0


def test_auxiliary_dependency_is_checked_across_the_whole_combination() -> None:
    auxiliary = {"component": "Column", "nestedGroups": [{"component": "SecondaryBody"}]}
    assert not auxiliary_groups_have_core([auxiliary, {"component": "PillButton"}])
    assert auxiliary_groups_have_core([auxiliary, {"component": "EmphasisText"}])
    assert auxiliary_groups_have_core([{"component": "PillButton"}, {"component": "PillButton"}])


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_matrix_covers_registered_layouts_without_guessing_unknown_slots(size: str) -> None:
    matrix = component_slot_matrix(size)
    assert matrix
    for entry in matrix:
        width, height = entry.get("width"), entry.get("height")
        assert width is None or (isinstance(width, (int, float)) and width > 0)
        assert height is None or (isinstance(height, (int, float)) and height > 0)
        if width is None or height is None:
            assert entry.get("status") != "conditional"
    if size == "2x2":
        assert any(
            entry.get("layout") == "S-content-dual-action" and entry.get("variant") == 2
            for entry in matrix
        )
