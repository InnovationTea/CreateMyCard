"""关键读数只定位实际失败字段，列表修复建议不得要求隐式删对象。"""

import copy
import json
import socket

import pytest

from services.card_validation.compact_validation.semantic.layout import text_capacity
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_repair_context import static_component_capacity_contexts
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.static_text_capacity import measure_text, text_spec


@pytest.fixture(autouse=True)
def offline_static_scope(monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("容量定位测试不得访问网络")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def make_source(items, *, header=True, size="2x2"):
    children = ["header", "body"] if header else ["body"]
    layout = "S-static-content" if size == "2x2" else "W-static-content"
    rows = [["root", "Layout", {"layout": layout}, children]]
    if header:
        rows.append(["header", "SingleLineTitle", {"title": "价格标准"}])
    rows.append(["body", "SingleLineList", {"items": items}])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def make_plan(count, *, price=False):
    facts = [{"text": "价格标准", "priority": "must"}]
    groups = [{"id": "heading", "kind": "shared", "factIndexes": [0]}]
    for index in range(count):
        identity = f"对象{index}"
        if price and index == 0:
            identity = "第一档"
        label = "第一档 180度以内" if price and index == 0 else identity
        value = "0.51元/度" if price and index == 0 else "短说明"
        fact_indexes = [len(facts), len(facts) + 1]
        facts.extend([
            {"text": label, "priority": "must"},
            {"text": value, "priority": "should"},
        ])
        groups.append({"id": str(index), "kind": "object", "identity": identity,
                       "factIndexes": fact_indexes})
    return {"info_required": facts, "contentGroups": groups}


def issue_for(source):
    with pytest.raises(ValueError) as raised:
        convert_compact_dsl_to_a2ui(source, size="2x2")
    return {"stage": "conversion", "code": "COMPACT_DSL_CONVERSION_FAILED",
            "message": str(raised.value)}


def numeric_case():
    items = [{"text": "第一档 180度以内", "assist": "0.51元/度"},
             {"text": "对象1", "assist": "短说明"}]
    source = make_source(items)
    return source, make_plan(2, price=True), issue_for(source)


def test_success_measurement_is_unchanged():
    spec = text_spec("singleAssist")
    assert text_capacity.require_static_text_capacity("0.51元", 100, spec, "body.item0_assist") == (
        measure_text("0.51元", 100, spec)
    )


def test_numeric_error_keeps_exact_field_and_width():
    _, _, issue = numeric_case()
    assert "body.item0_assist 关键读数 '0.51元' 超过 16.822vp" in issue.get("message", "")


@pytest.mark.parametrize("message", [
    "静态文字参考宽度未知或不足。",
    "COMPACT_STATIC_TEXT_CAPACITY: 静态文字单个字符超过参考文字区。",
    "其它错误",
])
def test_unrelated_measurement_errors_are_not_reclassified(monkeypatch, message):
    original = ValueError(message)

    def fail(*_args):
        raise original

    monkeypatch.setattr(text_capacity, "measure_text", fail)
    with pytest.raises(ValueError) as raised:
        text_capacity.require_static_text_capacity("1", 12, text_spec("singleAssist"), "body.x")
    assert raised.value is original


def test_current_numeric_field_maps_only_its_own_fact():
    source, plan, issue = numeric_case()
    contexts = static_component_capacity_contexts(source, [issue], plan)
    assert len(contexts) == 1
    assert contexts[0].get("doesNotFit") == [
        {"itemIndex": 0, "property": "assist", "planFacts": [{"factIndex": 2}]}]
    tracker = CompactRepairStrategyTracker(static_content=True)
    task = {"size": "2x2", "userQuery": "显示价格标准", "dataModelSchema": {"data": {}},
            "eventCandidates": [], "assetCandidates": []}
    first = tracker.next_directive(source, [issue], compact_plan=plan, task_spec=task)
    assert first.optional_drop is None
    second = tracker.next_directive(source, [issue], compact_plan=plan, task_spec=task)
    assert second.optional_drop is not None
    assert second.optional_drop.fact_indexes == (2,)
    assert tracker.allowed_omitted_fact_indexes == (2,)


@pytest.mark.parametrize("old,new", [
    ("body.item0_assist", "ghost.item0_assist"),
    ("body.item0_assist", "other.body.item0_assist"),
    ("body.item0_assist", "body.item0_unknown"),
    ("body.item0_assist", "body.item9_assist"),
    ("'0.51元'", "'0.99元'"),
    ("16.822vp", "116.822vp"),
    ("16.822vp", "0vp"),
    ("16.822vp", "1..2vp"),
])
def test_unconfirmed_numeric_diagnostic_does_not_map(old, new):
    source, plan, issue = numeric_case()
    issue["message"] = issue.get("message", "").replace(old, new)
    assert static_component_capacity_contexts(source, [issue], plan) == []


def test_stale_numeric_value_and_dynamic_field_do_not_map():
    source, plan, issue = numeric_case()
    for replacement in ("0.99元/度", "{{ ${/data/value} }}"):
        updated = source.replace("0.51元/度", replacement)
        assert static_component_capacity_contexts(updated, [issue], plan) == []


def test_other_value_error_during_readout_remeasurement_does_not_map(monkeypatch):
    from services import static_text_capacity

    source, plan, issue = numeric_case()

    def fail(*_args):
        raise ValueError("COMPACT_STATIC_TEXT_CAPACITY: 未知容量错误")

    monkeypatch.setattr(static_text_capacity, "measure_text", fail)
    assert static_component_capacity_contexts(source, [issue], plan) == []


def repair_instruction(count, header, *, plan=None, approved=()):
    items = [{"text": f"对象{index}", "assist": "短说明"} for index in range(count)]
    source = make_source(items, header=header, size="2x4")
    if plan is None:
        plan = make_plan(count)
    tracker = CompactRepairStrategyTracker(static_content=True)
    tracker._allowed_omitted_fact_indexes = list(approved)
    error = {
        "stage": "layout", "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        "message": "root vertical layout requires at least 138vp within available height 126vp",
    }
    directive = tracker.next_directive(source, [error], compact_plan=plan,
                                      task_spec={"size": "2x4"})
    assert directive.optional_drop is None
    assert directive.capacity_fits == ()
    return directive.instruction


@pytest.mark.parametrize("count,header,permitted", [
    (1, True, False), (2, True, True), (3, True, False), (4, True, False),
    (5, True, False), (6, True, False), (3, False, True), (4, False, False),
])
def test_single_line_feedback_respects_object_count_and_header(count, header, permitted):
    instruction = repair_instruction(count, header)
    assert ("可尝试TextList" in instruction) is permitted
    assert f"Plan仍需完整展示{count}个对象" in instruction
    assert "完整单行文字容量不成立" not in instruction
    assert "整树高度超出不能据此归咎于某一条事实" in instruction
    if not permitted and count > 1:
        assert "不能通过删除或合并不同对象改成TextList" in instruction
    if count == 1:
        assert "对象数不等于展示项数" in instruction
        assert "不满足当前TextList项数合同" not in instruction


def test_feedback_counts_accepted_objects_not_model_deleted_rows():
    instruction = repair_instruction(2, True, plan=make_plan(4))
    assert "Plan仍需完整展示4个对象" in instruction
    assert "可尝试TextList" not in instruction


def test_feedback_counts_only_fully_authorized_removed_objects():
    plan = make_plan(3)
    before = copy.deepcopy(plan)
    partial = repair_instruction(3, True, plan=plan, approved=(5,))
    assert "Plan仍需完整展示3个对象" in partial
    complete = repair_instruction(3, True, plan=plan, approved=(5, 6))
    assert "Plan仍需完整展示2个对象" in complete
    assert "可尝试TextList" in complete
    assert plan == before


@pytest.mark.parametrize("plan", [
    {}, {"info_required": [], "contentGroups": []},
    {"info_required": [], "contentGroups": [{"kind": "object", "factIndexes": [9]}]},
])
def test_incomplete_plan_does_not_recommend_text_list(plan):
    assert "可尝试TextList" not in repair_instruction(4, True, plan=plan)
