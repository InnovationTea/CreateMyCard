# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""独立重复动作诊断、严格事件身份及上下文排除边界。"""

import copy
import json
import socket

import pytest

from services.card_validation.compact_validation.semantic.action_display import (
    _strict_action_identity,
    find_duplicate_actions,
)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("duplicate action tests must not access network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


def _handler(target="weather"):
    return {"call": "clickToDeeplink", "args": {"intentName": target, "uri": ""}}


def _switch(flag):
    return {"call": "clickToIntent", "args": {
        "intentName": "SetSettingSwitch", "params": {
            "appBundleName": "com.huawei.hmos.settings",
            "itemName": "battery_saving_mode", "switchFlag": flag,
        },
    }}


def _source(rows):
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _button(identifier, handler=None, kind="PillButton"):
    return [identifier, kind, {
        "label": "查看天气", "onClick": [copy.deepcopy(handler or _handler())],
    }]


def _buttons(handlers=None, kind="PillButton"):
    handlers = handlers or [_handler(), _handler()]
    identifiers = [f"button{index}" for index in range(len(handlers))]
    rows = [["root", "Row", {}, identifiers]]
    for index, handler in enumerate(handlers):
        rows.append(_button(identifiers[index], handler, kind))
    return rows


def _plan(handler=None):
    plan = {"info_required": [{"actionId": "action.weather", "priority": "must"}]}
    handlers = {"action.weather": handler or _handler()}
    return plan, handlers


def _duplicates(rows, handler=None):
    plan, handlers = _plan(handler)
    return find_duplicate_actions(_source(rows), plan, handlers)


def test_unique_plan_action_reports_raw_reachable_button_positions():
    duplicates = _duplicates(_buttons())
    assert len(duplicates) == 1
    duplicate = duplicates[0]
    assert duplicate.get("actionId") == "action.weather"
    assert duplicate.get("factIndex") == 0
    assert duplicate.get("expectedVisibleCount") == 1
    assert duplicate.get("actualVisibleCount") == 2
    occurrences = duplicate.get("occurrences")
    assert isinstance(occurrences, list)
    assert occurrences[0] == {
        "componentId": "button0", "componentType": "PillButton", "property": "onClick",
        "parentId": "root", "parentRole": "Row.children[0]", "fixedRequiredSlot": False,
        "onClick": [_handler()],
    }


@pytest.mark.parametrize("kind", ["CardButton", "CircleButton", "PillButton"])
def test_all_independent_button_types_are_diagnosed(kind):
    assert len(_duplicates(_buttons(kind=kind))) == 1


@pytest.mark.parametrize("other", ["other", "weather?city=another", "{{ ${/data/other} }}"])
def test_different_targets_are_not_duplicates(other):
    assert not _duplicates(_buttons([_handler(), _handler(other)]))


def test_optional_switch_matching_does_not_merge_different_flag_values():
    assert not _duplicates(_buttons([_switch(0), _switch(1)]), _switch(0))


def test_a_a_b_still_reports_a_pair_without_including_different_switch_value():
    duplicates = _duplicates(_buttons([_switch(0), _switch(0), _switch(1)]), _switch(0))
    assert len(duplicates) == 1
    occurrences = duplicates[0].get("occurrences")
    assert isinstance(occurrences, list)
    assert [item.get("componentId") for item in occurrences] == ["button0", "button1"]


def test_strict_identity_distinguishes_types_and_array_order():
    assert _strict_action_identity([{"value": False}]) != _strict_action_identity([{"value": 0}])
    assert _strict_action_identity([1, 2]) != _strict_action_identity([2, 1])
    assert _strict_action_identity({"b": 2, "a": 1}) == _strict_action_identity({"a": 1, "b": 2})


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), {1, 2}])
def test_unstable_json_identity_is_skipped_without_raising(invalid):
    assert _strict_action_identity([{"parameter": invalid}]) is None


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_raw_event_parameter_does_not_crash_coverage_diagnostic(invalid):
    handler = _handler()
    args = handler.get("args")
    assert isinstance(args, dict)
    args["value"] = invalid
    assert not _duplicates(_buttons([handler, handler]), handler)


def test_multihandler_order_is_part_of_complete_identity():
    rows = _buttons()
    for row in rows[1:]:
        row[2]["onClick"] = [_handler(), _handler("extra")]
    duplicates = _duplicates(rows)
    assert len(duplicates) == 1
    rows[2][2]["onClick"].reverse()
    assert not _duplicates(rows)


def test_two_accepted_actions_on_same_button_is_ambiguous():
    rows = _buttons()
    for row in rows[1:]:
        row[2]["onClick"] = [_handler(), _handler("extra")]
    plan, handlers = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"actionId": "action.extra"})
    handlers["action.extra"] = _handler("extra")
    assert not find_duplicate_actions(_source(rows), plan, handlers)


def test_accepted_aliases_are_ambiguous():
    plan, handlers = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"actionId": "alias"})
    handlers["alias"] = _handler()
    assert not find_duplicate_actions(_source(_buttons()), plan, handlers)


def test_repeated_plan_action_fact_has_no_inferred_unique_ownership():
    plan, handlers = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append(copy.deepcopy(facts[0]))
    assert not find_duplicate_actions(_source(_buttons()), plan, handlers)


@pytest.mark.parametrize("plan", [None, {}, {"info_required": []}, {"info_required": [None]}])
def test_absent_action_plan_does_not_enable_diagnostic(plan):
    assert not find_duplicate_actions(_source(_buttons()), plan, {"action.weather": _handler()})


def test_unknown_action_is_left_to_existing_coverage():
    plan, _ = _plan()
    assert not find_duplicate_actions(_source(_buttons()), plan, {})


@pytest.mark.parametrize("kind", ["List", "Grid", "ForEach", "Repeat", "RecordList", "SummaryList"])
def test_list_context_is_not_cross_item_deduplicated(kind):
    rows = _buttons()
    rows[0][1] = kind
    assert not _duplicates(rows)


@pytest.mark.parametrize("key", ["template", "itemTemplate", "dataSource", "forEach", "repeat"])
def test_template_properties_exclude_descendant_actions(key):
    rows = _buttons()
    rows[0][2][key] = "items"
    assert not _duplicates(rows)


def test_whole_card_and_descendant_clicks_are_not_independent_buttons():
    rows = _buttons()
    rows[0][2]["onClick"] = [_handler()]
    assert not _duplicates(rows)


def test_parent_child_clicks_are_excluded():
    rows = _buttons()
    rows[0][3] = ["parent"]
    rows.append(["parent", "Row", {"onClick": [_handler()]}, ["button0", "button1"]])
    assert not _duplicates(rows)


def test_unreachable_action_is_not_visible():
    rows = _buttons()
    rows[0][3] = ["button0"]
    assert not _duplicates(rows)


def test_shared_reference_or_cycle_has_no_safe_occurrence_identity():
    rows = _buttons()
    rows[0][3].append("other_parent")
    rows.append(["other_parent", "Column", {}, ["button0"]])
    assert not _duplicates(rows)
    rows[0][3] = ["root"]
    assert not _duplicates(rows)


@pytest.mark.parametrize("source", ["bad", "[]", '["x","PillButton",{}]'])
def test_malformed_or_rootless_sources_do_not_mask_original_errors(source):
    plan, handlers = _plan()
    assert not find_duplicate_actions(source, plan, handlers)


@pytest.mark.parametrize("layout", [
    "W-content-side-slots", "W-four-slots", "S-content-dual-action",
])
def test_fixed_slots_keep_accurate_parent_roles_in_diagnostic(layout):
    rows = _buttons(kind="CardButton")
    rows[0][1] = "Layout"
    rows[0][2] = {"layout": layout}
    if layout == "W-content-side-slots":
        rows[0][3].insert(0, "content")
        rows.append(["content", "Region", {"variant": "center"}, ["body"]])
        rows.append(["body", "EmphasisText", {"mainText": "正文", "fontSize": 18}])
    duplicates = _duplicates(rows)
    assert len(duplicates) == 1
    positions = duplicates[0].get("occurrences")
    assert isinstance(positions, list) and len(positions) == 2
    for position in positions:
        assert position.get("parentId") == "root"
        assert position.get("fixedRequiredSlot") is True
        assert position.get("parentRole", "").startswith(f"{layout}.")


@pytest.mark.parametrize("property_name,value", [
    ("label", "查看别处"), ("icon", "resources/base/media/other.svg"),
    ("accessibility", {"label": "另一个对象"}),
])
def test_button_presentation_does_not_change_execution_identity(property_name, value):
    rows = _buttons()
    rows[2][2][property_name] = value
    duplicates = _duplicates(rows)
    assert len(duplicates) == 1


def test_diagnostic_does_not_mutate_source_or_share_handler_objects():
    rows = _buttons()
    original = copy.deepcopy(rows)
    duplicates = _duplicates(rows)
    occurrences = duplicates[0].get("occurrences")
    assert isinstance(occurrences, list)
    handlers = occurrences[0].get("onClick")
    assert isinstance(handlers, list)
    handlers[0]["call"] = "changed"
    assert rows == original
    assert _duplicates(rows) != duplicates
