"""Compact 历史 CodeCheck 整改保持可选返回、正文穿透和事实筛选语义。"""

import copy
from dataclasses import replace

import pytest

from services.compact_dsl_a2ui_converter import VISUAL_RECIPE_VERSION, _single_body_slot
from services.compact_high_level_components import ComponentRow
from services.compact_outer_recomposition import _single_attribute
from services.compact_plan import _anchor_plan_errors


@pytest.fixture
def body_rows():
    prefix = f"{VISUAL_RECIPE_VERSION}:SecondaryBody."
    return {
        "body": ComponentRow("body", "Column", {"_visualRecipe": prefix + "root"}, ("row",)),
        "row": ComponentRow("row", "Row", {"_visualRecipe": prefix + "row"}, ("item",)),
        "item": ComponentRow("item", "Column", {"_visualRecipe": prefix + "item"}, ("text",)),
        "text": ComponentRow("text", "Text", {
            "_visualRecipe": prefix + "text", "height": 19, "content": {"path": "/data/value"},
        }),
    }


def test_single_body_slot_keeps_wrapper_order_and_original_nodes(body_rows):
    root = body_rows.get("body")
    assert root is not None
    before = copy.deepcopy(body_rows)
    result = _single_body_slot(root, body_rows)
    assert result is not None
    wrappers, text = result
    assert [node.component_id for node in wrappers] == ["body", "row", "item"]
    assert text is body_rows.get("text")
    assert all(node is body_rows.get(node.component_id) for node in wrappers)
    assert body_rows == before


@pytest.mark.parametrize("node_id,changes", [
    ("body", {"props": {}}),
    ("row", {"children": ()}),
    ("row", {"children": ("item", "text")}),
    ("row", {"children": ("missing",)}),
    ("row", {"children": ("body",)}),
    ("item", {"props": {"_visualRecipe": "foreign"}}),
    ("text", {"component_type": "Image"}),
])
def test_invalid_body_chain_still_returns_none(body_rows, node_id, changes):
    node = body_rows.get(node_id)
    assert node is not None
    body_rows[node_id] = replace(node, **changes)
    root = body_rows.get("body")
    assert root is not None
    assert _single_body_slot(root, body_rows) is None


@pytest.mark.parametrize("props,accepted", [
    ({"_visualRecipe": "foreign"}, False),
    ({"height": None}, False),
    ({"height": True}, False),
    ({"height": 0}, False),
    ({"height": -1}, False),
    ({"height": "19"}, False),
    ({"height": float("inf")}, False),
    ({"height": 32}, True),
    ({"constraintSize": {"minHeight": 1}}, False),
    ({"constraintSize": {"minHeight": 0}}, True),
    ({"constraintSize": {}}, True),
    ({"constraintSize": None}, True),
])
def test_body_text_height_and_minimum_constraints_unchanged(body_rows, props, accepted):
    text = body_rows.get("text")
    root = body_rows.get("body")
    assert text is not None and root is not None
    body_rows["text"] = replace(text, props={**text.props, **props})
    assert (_single_body_slot(root, body_rows) is not None) == accepted


@pytest.fixture
def attribute_task():
    return {"dataModelSchema": {"data": {
        "weather": {
            "state": {"type": "string", "sampleValue": "sunny"},
            "temperature": {"type": "number", "sampleValue": 29},
            "empty": {"type": "string", "sampleValue": ""},
            "multiline": {"type": "string", "sampleValue": "sunny\nrain"},
            "unknown": {"type": "string"},
        },
        "device": {"name": {"type": "string", "sampleValue": "phone"}},
    }}}


def attribute_row(value):
    return ComponentRow("body", "SecondaryBody", {
        "role": "supporting", "width": "matchParent",
        "items": [{"label": "Status", "value": value}],
    })


@pytest.mark.parametrize("value,expected", [
    ({"path": "/data/weather/state"}, "sunny"),
    ({"path": "/data/weather/empty"}, ""),
    ("{{ ${/data/weather/state} + ' ' + ${/data/weather/temperature} }}", "sunny 29"),
    ("fixed", None),
    (42, None),
    ({"path": "/data/weather/missing"}, None),
    ({"path": "/data/weather/unknown"}, None),
    ({"path": "/data/weather/multiline"}, None),
    ("{{ ${/data/weather/state} + ${/data/device/name} }}", None),
    ("{{ ${/data/weather/state} + ${/data/weather/missing} }}", None),
])
def test_single_attribute_keeps_none_or_complete_tuple(attribute_task, value, expected):
    row = attribute_row(value)
    before = copy.deepcopy((row, attribute_task))
    result = _single_attribute(row, attribute_task)
    if expected is None:
        assert result is None
    else:
        assert result is not None
        item, owner, text = result
        items = row.props.get("items")
        assert items is not None
        assert item is items[0]
        assert owner == "/data/weather"
        assert text == expected
    assert (row, attribute_task) == before


@pytest.mark.parametrize("overrides", [
    {"role": "body"},
    {"columns": 2},
    {"items": []},
    {"items": [{"label": "A", "value": {"path": "/data/weather/state"}},
               {"label": "B", "value": {"path": "/data/weather/temperature"}}]},
])
def test_single_attribute_rejects_non_single_supporting_body(attribute_task, overrides):
    row = attribute_row({"path": "/data/weather/state"})
    row = replace(row, props={**row.props, **overrides})
    assert _single_attribute(row, attribute_task) is None


@pytest.mark.parametrize("facts,accepted", [
    ([], False),
    ([{"componentHints": ["EmphasisText"]}], False),
    ([{"componentHints": ["SingleLineTitle"]}, {"componentHints": ["EmphasisText"]}], False),
    ([{"actionId": None}, {"componentHints": ["EmphasisText"]}], False),
    ([{"componentHints": ["EmphasisText"]}, {"componentHints": ["SecondaryBody"]}], True),
    ([{"componentHints": ["SingleLineTitle", "EmphasisText"]}, {}], True),
    ([{}, {}], True),
])
def test_anchor_filter_preserves_title_action_and_duplicate_fact_handling(facts, accepted):
    before = copy.deepcopy(facts)
    errors = _anchor_plan_errors(facts, ["S-title-anchor"], None)
    assert (not errors) == accepted
    if not accepted:
        assert len(errors) == 1
        assert errors[0].startswith("S-title-anchor requires one primary body fact")
    assert facts == before
