"""字段补丁可移植回归：不依赖本地批跑目录，不调用模型或设备。"""

import copy
import json

import pytest

from services.generation_pipeline import DslProcessingContext
from services.single_step_edit import SingleStepEditProcessor, source_digest


@pytest.fixture
def source():
    rows = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "card", "root": "root", "components": [
                {"id": "root", "component": "Column", "children": ["title", "ring", "value"],
                 "styles": {"width": "matchParent", "height": "matchParent", "padding": 12,
                            "linearGradient": {"colors": [["#FFFFE0CC", 0], ["#FFFFF7F2", 1]]}}},
                {"id": "title", "component": "Text", "content": "天气",
                 "styles": {"fontSize": 12, "height": 24, "fontColor": "#FF111111"}},
                {"id": "ring", "component": "Progress", "type": "ring", "total": 100,
                 "value": "{{ ${/data/battery} }}",
                 "styles": {"width": 44, "height": 44, "color": "#FF1F4799",
                            "backgroundColor": "#331F4799"},
                 "onClick": [{"call": "existingAction", "args": {"switchFlag": 1}}]},
                {"id": "value", "component": "Text", "content": "{{ ${/data/battery} }}",
                 "styles": {"fontSize": 30}},
            ],
        }},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "card", "path": "/", "value": {"data": {"battery": 68}},
        }},
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _rows(source):
    return [json.loads(line) for line in source.splitlines()]


def _node(rows, identity):
    update = rows[1].get("updateComponents")
    assert isinstance(update, dict)
    return next(node for node in update.get("components", []) if node.get("id") == identity)


def _patch(source, identity, property_name, value, quote):
    node = _node(_rows(source), identity)
    target = node if property_name == "content" else node.get("styles", {})
    key = property_name.removeprefix("styles.")
    before = {"exists": key in target}
    if key in target:
        before["value"] = target.get(key)
    return {"sourceDigest": source_digest(source), "changes": [{
        "componentId": identity, "property": property_name, "value": value,
        "before": before, "requestQuote": quote,
    }]}


def _process(source, payload, query, processor=None):
    processor = processor or SingleStepEditProcessor(source)
    context = DslProcessingContext(
        size="2x4", card_spec={}, protocol_profile={}, task_spec={"userQuery": query},
    )
    result = processor.process(json.dumps(payload, ensure_ascii=False), context)
    return processor, result


def test_progress_changes_only_completion_color(source):
    query = "仅把ring进度完成色改成#FF9C27B0"
    payload = _patch(source, "ring", "styles.color", "#FF9C27B0", query)
    processor, result = _process(source, payload, query)
    assert not result.errors
    expected = _rows(source)
    _node(expected, "ring").get("styles")["color"] = "#FF9C27B0"
    assert _rows(result.standard_dsl) == expected
    assert not processor.preservation_errors(result.standard_dsl)


def test_font_then_background_preserves_previous_edit_and_structure(source):
    query = "仅把title字号改为18fp"
    payload = _patch(source, "title", "styles.fontSize", 18, query)
    _, first = _process(source, payload, query)
    assert not first.errors
    expected = _rows(source)
    _node(expected, "title").get("styles")["fontSize"] = 18
    assert _rows(first.standard_dsl) == expected
    query = "仅把root背景改为#FFE8F0FE"
    payload = _patch(first.standard_dsl, "root", "styles.backgroundColor", "#FFE8F0FE", query)
    _, second = _process(first.standard_dsl, payload, query)
    assert not second.errors
    background = _node(expected, "root").get("styles")
    assert isinstance(background, dict)
    background.pop("linearGradient")
    background["backgroundColor"] = "#FFE8F0FE"
    assert _rows(second.standard_dsl) == expected


@pytest.mark.parametrize("property_name,value", [
    ("children", []), ("styles.height", 20), ("styles.layoutWeight", 1),
    ("styles.fontSize", 12), ("styles.backgroundColor", "#FF9C27B0"),
    ("onClick", []), ("value", 50), ("styles.color", "#FFFF0000"),
])
def test_reject_unrequested_field_or_color(source, property_name, value):
    query = "仅把ring进度完成色改成#FF9C27B0"
    payload = _patch(source, "ring", property_name, value, query)
    _, result = _process(source, payload, query)
    assert result.errors
    assert not result.standard_dsl


@pytest.mark.parametrize("mutation", ["target", "digest", "before", "extra", "empty", "duplicate"])
def test_reject_invalid_or_stale_patch(source, mutation):
    query = "仅把ring进度完成色改成#FF9C27B0"
    payload = _patch(source, "ring", "styles.color", "#FF9C27B0", query)
    changes = payload.get("changes")
    assert isinstance(changes, list)
    if mutation == "target":
        changes[0]["componentId"] = "title"
    elif mutation == "digest":
        payload["sourceDigest"] = "stale"
    elif mutation == "before":
        changes[0]["before"] = {"exists": False}
    elif mutation == "extra":
        changes[0]["children"] = []
    elif mutation == "empty":
        payload["changes"] = []
    else:
        changes.append(copy.deepcopy(changes[0]))
    _, result = _process(source, payload, query)
    assert result.errors


def test_quote_cannot_hide_target_or_authorize_protected_text(source):
    query = "仅把title字号改为18fp；其它文字字号保持不变"
    payload = _patch(source, "title", "styles.fontSize", 18, "字号改为18fp")
    _, result = _process(source, payload, query)
    assert not result.errors
    changes = payload.get("changes")
    assert isinstance(changes, list)
    changes[0]["componentId"] = "value"
    changes[0]["before"] = {"exists": True, "value": 30}
    _, result = _process(source, payload, query)
    assert result.errors


def test_dynamic_text_cannot_be_replaced_with_literal(source):
    query = "把value文字改为电量"
    payload = _patch(source, "value", "content", "电量", query)
    _, result = _process(source, payload, query)
    assert result.errors


def test_repair_reuses_immutable_source_and_detects_downstream_layout_change(source):
    query = "仅把title字号改为18fp"
    payload = _patch(source, "title", "styles.fontSize", 18, query)
    processor, first = _process(source, payload, query)
    assert not first.errors
    stale = copy.deepcopy(payload)
    changes = stale.get("changes")
    assert isinstance(changes, list)
    changes[0]["before"] = {"exists": True, "value": 18}
    _, rejected = _process(source, stale, query, processor)
    assert rejected.errors
    _, repaired = _process(source, payload, query, processor)
    assert not repaired.errors
    assert repaired.standard_dsl == first.standard_dsl
    corrupted = _rows(repaired.standard_dsl)
    _node(corrupted, "root").get("styles")["height"] = 120
    assert processor.preservation_errors("\n".join(json.dumps(row) for row in corrupted))
