"""字段补丁可移植回归：不依赖本地批跑目录，不调用模型或设备。"""

import ast
import copy
import inspect
import json

import pytest

from services import single_step_edit
from services.generation_pipeline import DslProcessingContext
from services.single_step_edit import SingleStepEditProcessor, _validate_value, source_digest


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
    ("styles.fontSize", 12), ("styles.fontColor", "#FF9C27B0"),
    ("onClick", []), ("value", 50),
])
def test_reject_unsupported_field_or_component_type(source, property_name, value):
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


def test_quote_is_optional_audit_and_does_not_gate_preservation_phrase(source):
    query = "仅把title字号改为18fp；其它文字字号保持不变"
    payload = _patch(source, "title", "styles.fontSize", 18, "字号改为18fp")
    _, result = _process(source, payload, query)
    assert not result.errors
    changes = payload.get("changes")
    assert isinstance(changes, list)
    changes[0].pop("requestQuote")
    _, result = _process(source, payload, query)
    assert not result.errors


def test_dynamic_text_cannot_be_replaced_with_literal(source):
    query = "把value文字改为电量"
    payload = _patch(source, "value", "content", "电量", query)
    _, result = _process(source, payload, query)
    assert result.errors


def test_control_conditions_keep_at_most_three_boolean_terms():
    """G.CTL.03：检查整个编辑模块，括号内的组合条件也计数。"""
    tree = ast.parse(inspect.getsource(single_step_edit))
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.While)):
            continue
        term_count = 1
        for expression in ast.walk(node.test):
            if isinstance(expression, ast.BoolOp):
                term_count += len(expression.values) - 1
        if term_count > 3:
            violations.append((node.lineno, term_count))
    assert not violations, violations


def test_static_text_edit_preserves_all_other_fields(source):
    query = "仅把title文字改为今日天气"
    payload = _patch(source, "title", "content", "今日天气", query)
    processor, result = _process(source, payload, query)
    assert not result.errors
    expected = _rows(source)
    _node(expected, "title")["content"] = "今日天气"
    assert _rows(result.standard_dsl) == expected
    assert not processor.preservation_errors(result.standard_dsl)


@pytest.mark.parametrize("old", [
    None, 42, False, [], {}, {"path": "/data/value"}, "{{ value }}", "${/data/value}",
])
def test_static_text_guard_rejects_invalid_original_without_changing_error(old):
    node = {"component": "Text", "content": old}
    with pytest.raises(ValueError, match="^cannot replace dynamic bindings with static text$"):
        _validate_value("content", "天气", node)


@pytest.mark.parametrize("value", ["{{ value }}", "${/data/value}"])
def test_static_text_guard_rejects_binding_in_new_value(value):
    node = {"component": "Text", "content": "天气"}
    with pytest.raises(ValueError, match="^cannot replace dynamic bindings with static text$"):
        _validate_value("content", value, node)


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


@pytest.mark.parametrize("query", [
    "标题调大一点", "让标题醒目一些", "标题再大些并保持其它不变",
    "标题调整得更适合阅读", "Increase the title a little, keep everything else",
])
def test_natural_language_font_edits_do_not_require_numbers_or_keywords(source, query):
    payload = _patch(source, "title", "styles.fontSize", 18, "审计说明无需匹配原话")
    _, result = _process(source, payload, query)
    assert not result.errors
    assert _node(_rows(result.standard_dsl), "title").get("styles", {}).get("fontSize") == 18
    assert _node(_rows(result.standard_dsl), "value") == _node(_rows(source), "value")


@pytest.mark.parametrize("query,color", [
    ("背景换成蒂芙尼蓝", "#FF81D8D0"), ("背景来点橙色", "#FFFFA500"),
    ("底色柔和一些", "#FFE8F0FE"),
])
def test_named_colors_and_relative_palette_have_no_query_whitelist(source, query, color):
    payload = _patch(source, "root", "styles.backgroundColor", color, query)
    _, result = _process(source, payload, query)
    assert not result.errors
    styles = _node(_rows(result.standard_dsl), "root").get("styles", {})
    assert styles.get("backgroundColor") == color


def test_whole_card_palette_allows_multiple_targets_without_fixed_scope_words(source):
    query = "这张卡片整体换成蒂芙尼蓝风格"
    payload = _patch(source, "root", "styles.backgroundColor", "#FF81D8D0", query)
    changes = payload.get("changes")
    extra = _patch(source, "title", "styles.fontColor", "#FF123333", query).get("changes")
    assert isinstance(changes, list) and isinstance(extra, list)
    changes.extend(extra)
    _, result = _process(source, payload, query)
    assert not result.errors
    rows = _rows(result.standard_dsl)
    assert _node(rows, "root").get("styles", {}).get("backgroundColor") == "#FF81D8D0"
    assert _node(rows, "title").get("styles", {}).get("fontColor") == "#FF123333"


def test_static_text_can_be_semantically_shortened_without_verbatim_new_text(source):
    query = "标题改得简洁一点"
    payload = _patch(source, "title", "content", "今日天气", query)
    _, result = _process(source, payload, query)
    assert not result.errors
    assert _node(_rows(result.standard_dsl), "title").get("content") == "今日天气"


@pytest.mark.parametrize("value", [0, -1, True, float("inf"), float("nan"), "18"])
def test_font_output_keeps_type_and_finite_positive_guards(source, value):
    query = "标题大一点"
    payload = _patch(source, "title", "styles.fontSize", value, query)
    _, result = _process(source, payload, query)
    assert result.errors


@pytest.mark.parametrize("value", ["蒂芙尼蓝", "#GG0000", "#FFF", {"path": "/data/color"}])
def test_color_output_keeps_literal_protocol_validation(source, value):
    query = "背景柔和些"
    payload = _patch(source, "root", "styles.backgroundColor", value, query)
    _, result = _process(source, payload, query)
    assert result.errors


def test_regex_calls_are_limited_to_model_output_format_and_color_literals():
    tree = ast.parse(inspect.getsource(single_step_edit))
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == "re":
                assert function.name in {"_normalized_color", "extract_edit_patch"}
