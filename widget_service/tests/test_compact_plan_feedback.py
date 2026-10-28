"""静态失败 Plan 的关系账本；日志结构缩减复现，不改变事实或删除权限。"""

import copy
import json

import pytest

from services.compact_plan_feedback import static_plan_repair_feedback
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.prompt_builder import PromptBuilder


def _fact(index: int, **overrides) -> dict:
    return {
        "requirement": f"需求{index}", "text": f"完整事实{index}", "priority": "must",
        "sourceTexts": [f"原始完整事实{index}"], **overrides,
    }


def _group(index: int, indexes: list[int]) -> dict:
    return {
        "id": f"group{index}", "kind": "object", "identity": f"对象{index}",
        "factIndexes": indexes,
    }


def _arguments(count: int = 3) -> dict:
    return {
        "info_required": [_fact(index) for index in range(count)],
        "contentGroups": [_group(index, [index]) for index in range(count)],
        "omittedContents": [], "layoutHints": ["S-stack"],
    }


def _raw(arguments: dict) -> str:
    return json.dumps({"name": "submit_card_plan", "arguments": arguments}, ensure_ascii=False)


def _issues(feedback: dict, code: str) -> list[dict]:
    items = feedback.get("issues")
    assert isinstance(items, list)
    return [item for item in items if item.get("code") == code]


def _feedback(arguments: dict) -> dict:
    feedback = static_plan_repair_feedback(_raw(arguments))
    assert isinstance(feedback, dict)
    return feedback


@pytest.mark.parametrize("count", [1, 3, 5, 24])
def test_consistent_plan_does_not_add_ledger_or_restore_three_object_gate(count):
    arguments = _arguments(count)
    before = copy.deepcopy(arguments)
    assert static_plan_repair_feedback(_raw(arguments)) is None
    assert arguments == before


def test_action_only_plan_has_no_group_obligation():
    arguments = {
        "info_required": [{"requirement": "打开", "actionId": "event.open", "priority": "must"}],
        "contentGroups": [], "omittedContents": [],
    }
    assert static_plan_repair_feedback(_raw(arguments)) is None


@pytest.mark.parametrize("omission_indexes", [[[], []], [[3], [4]]])
def test_q011_q052_omission_claim_does_not_remove_still_submitted_facts(omission_indexes):
    arguments = _arguments(5)
    arguments["contentGroups"] = [_group(index, [index]) for index in range(3)]
    arguments["omittedContents"] = [
        {"description": "对象3不展示", "factIndexes": omission_indexes[0]},
        {"description": "对象4不展示", "factIndexes": omission_indexes[1]},
    ]
    before = copy.deepcopy(arguments)
    feedback = _feedback(arguments)
    missing = _issues(feedback, "ungrouped_text")
    assert [item.get("path") for item in missing] == ["info_required[3]", "info_required[4]"]
    facts = feedback.get("facts")
    assert isinstance(facts, list) and len(facts) == 5
    assert [fact.get("index") for fact in facts] == [0, 1, 2, 3, 4]
    protected = _issues(feedback, "ineligible_omission_reference")
    assert len(protected) == (0 if omission_indexes == [[], []] else 2)
    assert arguments == before
    instruction = feedback.get("instruction")
    assert isinstance(instruction, str) and "不是新Plan或删除授权" in instruction


def test_q052_ten_facts_reports_all_missing_groups_and_must_omission_conflicts():
    arguments = _arguments(10)
    arguments["contentGroups"] = [_group(0, [0, 5]), _group(1, [1, 6]), _group(2, [2, 7])]
    arguments["omittedContents"] = [
        {"description": "对象3", "factIndexes": [3, 8]},
        {"description": "对象4", "factIndexes": [4, 9]},
    ]
    feedback = _feedback(arguments)
    expected = ["info_required[3]", "info_required[4]", "info_required[8]", "info_required[9]"]
    assert [item.get("path") for item in _issues(feedback, "ungrouped_text")] == expected
    protected = _issues(feedback, "ineligible_omission_reference")
    assert [item.get("path") for item in protected] == expected
    assert feedback.get("groupDeclarations") == [
        {"path": "contentGroups[0]", **_group(0, [0, 5])},
        {"path": "contentGroups[1]", **_group(1, [1, 6])},
        {"path": "contentGroups[2]", **_group(2, [2, 7])},
    ]


@pytest.mark.parametrize("count, first_indexes", [(6, [0, 1, 2]), (7, [0, 1, 2, 3])])
def test_z136_repair_still_reports_last_unassigned_fact(count, first_indexes):
    arguments = _arguments(count)
    arguments["contentGroups"] = [
        _group(0, first_indexes), _group(1, [count - 3]), _group(2, [count - 2]),
    ]
    arguments["omittedContents"] = [{"description": "没有数据使用描述", "factIndexes": []}]
    feedback = _feedback(arguments)
    assert [item.get("path") for item in _issues(feedback, "ungrouped_text")] == [
        f"info_required[{count - 1}]",
    ]


def test_all_ambiguous_or_invalid_references_include_exact_original_paths():
    arguments = _arguments(3)
    arguments["contentGroups"] = [_group(0, [0, 0, True, -1, 3]), _group(1, [0]), _group(2, [])]
    arguments["omittedContents"] = [{"description": "不明确省略", "factIndexes": [1, 1, "2", 8]}]
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "empty_group")) == 1
    assert len(_issues(feedback, "repeated_fact_index")) == 2
    assert [item.get("path") for item in _issues(feedback, "invalid_fact_index")] == [
        "contentGroups[0].factIndexes[2]", "contentGroups[0].factIndexes[3]",
        "contentGroups[0].factIndexes[4]", "omittedContents[0].factIndexes[2]",
        "omittedContents[0].factIndexes[3]",
    ]
    multiple = _issues(feedback, "multiply_grouped_text")
    assert len(multiple) == 1
    assert multiple[0].get("groupReferences") == [
        "contentGroups[0].factIndexes[0]", "contentGroups[0].factIndexes[1]",
        "contentGroups[1].factIndexes[0]",
    ]


def test_duplicate_group_ids_keep_both_declared_objects_in_ledger():
    arguments = _arguments(2)
    arguments["contentGroups"] = [_group(0, [0]), _group(0, [1])]
    feedback = _feedback(arguments)
    assert _issues(feedback, "duplicate_group_id") == [{
        "code": "duplicate_group_id", "path": "contentGroups[1].id",
        "earlierPath": "contentGroups[0].id", "submitted": "group0",
    }]
    assert len(feedback.get("groupDeclarations", [])) == 2


@pytest.mark.parametrize(
    "protection", [{"protectedTexts": ["必须原文"]}, {"preserveVerbatim": True}],
)
def test_protected_should_cannot_be_omitted_and_protection_is_visible(protection):
    arguments = _arguments(1)
    arguments["info_required"] = [_fact(0, priority="should", **protection)]
    arguments["omittedContents"] = [{"description": "省略", "factIndexes": [0]}]
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "ineligible_omission_reference")) == 1
    facts = feedback.get("facts")
    assert isinstance(facts, list)
    for key, value in protection.items():
        assert facts[0].get(key) == value


def test_legal_should_omission_is_a_candidate_and_still_requires_group():
    arguments = _arguments(1)
    arguments["info_required"] = [_fact(0, priority="should")]
    arguments["omittedContents"] = [{"description": "可选省略", "factIndexes": [0]}]
    assert static_plan_repair_feedback(_raw(arguments)) is None
    arguments["contentGroups"] = []
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "ungrouped_text")) == 1
    assert not _issues(feedback, "ineligible_omission_reference")


def test_actions_cannot_be_grouped_or_omitted():
    arguments = _arguments(1)
    arguments["info_required"] = [
        {"requirement": "打开", "actionId": "event.open", "priority": "should"},
    ]
    arguments["omittedContents"] = [{"description": "移除动作", "factIndexes": [0]}]
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "action_in_content_group")) == 1
    assert len(_issues(feedback, "ineligible_omission_reference")) == 1


@pytest.mark.parametrize("rows", [None, ["invalid"], [{"id": "g"}]])
def test_malformed_groups_do_not_hide_other_ungrouped_facts(rows):
    arguments = _arguments(3)
    arguments["contentGroups"] = rows
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "ungrouped_text")) == 3
    assert len(feedback.get("issues", [])) >= 4


@pytest.mark.parametrize("facts", [None, "invalid", {}, []])
def test_missing_or_empty_fact_array_does_not_invent_any_fact(facts):
    arguments = {"info_required": facts, "contentGroups": [], "omittedContents": []}
    assert static_plan_repair_feedback(_raw(arguments)) is None


def test_invalid_fact_rows_and_empty_fact_references_are_reported_without_crashing():
    arguments = {"info_required": [None, "invalid", 1], "contentGroups": [], "omittedContents": []}
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "object_required")) == 3
    arguments["info_required"] = []
    arguments["contentGroups"] = [_group(0, [0])]
    feedback = _feedback(arguments)
    assert len(_issues(feedback, "invalid_fact_index")) == 1
    assert feedback.get("facts") == []


def test_deep_malformed_json_does_not_crash_feedback():
    raw = '{"name":"submit_card_plan","arguments":' + '[' * 2000 + '0' + ']' * 2000 + '}'
    assert static_plan_repair_feedback(raw) is None


@pytest.mark.parametrize("raw", [
    "not JSON", '{"name":"submit_card_plan","arguments":',
    '{"name":"submit_card_plan","arguments":{},"arguments":{"info_required":[]}}',
    '{"name":"other","arguments":{}}', '{"name":"submit_card_plan","arguments":"{}"}',
    '{"name":"submit_card_plan","arguments":{}}{}',
])
def test_invalid_or_ambiguous_json_does_not_guess_a_ledger(raw):
    assert static_plan_repair_feedback(raw) is None


@pytest.mark.parametrize("wrapper", ["plain", "fence", "call"])
def test_known_transport_envelopes_share_output_normalizer(wrapper):
    arguments = _arguments(1)
    arguments["contentGroups"] = []
    raw = _raw(arguments)
    if wrapper == "fence":
        raw = "```json\n" + raw + "\n```"
    elif wrapper == "call":
        raw = "call\n" + raw
    feedback = static_plan_repair_feedback(raw)
    assert isinstance(feedback, dict)
    assert len(_issues(feedback, "ungrouped_text")) == 1


def test_complete_fence_with_unambiguous_root_groups_matches_existing_normalization():
    arguments = _arguments(3)
    groups = arguments.pop("contentGroups")
    payload = {"name": "submit_card_plan", "arguments": arguments, "contentGroups": groups}
    raw = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    assert static_plan_repair_feedback(raw) is None


def test_long_text_is_explicit_preview_but_every_fact_keeps_original_index():
    arguments = _arguments(24)
    arguments["info_required"] = [_fact(index, text="文" * 121) for index in range(24)]
    arguments["contentGroups"] = []
    feedback = _feedback(arguments)
    facts = feedback.get("facts")
    assert isinstance(facts, list) and len(facts) == 24
    assert len(_issues(feedback, "ungrouped_text")) == 24
    for index, fact in enumerate(facts):
        assert fact.get("index") == index
        assert fact.get("text") == {"preview": "文" * 120, "originalChars": 121, "truncated": True}


@pytest.mark.parametrize("oversized", ["facts", "groups", "omissions", "references", "raw"])
def test_excessive_payload_is_explicitly_unavailable_not_a_partial_ledger(oversized):
    arguments = _arguments(1)
    if oversized == "facts":
        arguments["info_required"] = [_fact(index) for index in range(25)]
    elif oversized == "groups":
        arguments["contentGroups"] = [_group(index, [0]) for index in range(25)]
    elif oversized == "omissions":
        arguments["omittedContents"] = [{"description": "未选输入", "factIndexes": []}] * 25
    elif oversized == "references":
        arguments["contentGroups"] = [_group(0, list(range(25)))]
    raw = _raw(arguments)
    if oversized == "raw":
        raw += " " * 131073
    feedback = static_plan_repair_feedback(raw)
    assert isinstance(feedback, dict)
    assert str(feedback.get("status")).startswith("ledger_not_built_")
    assert "facts" not in feedback


def test_only_static_failed_repair_gets_ledger_and_original_conversation_is_unchanged():
    arguments = _arguments(5)
    arguments["contentGroups"] = [_group(index, [index]) for index in range(3)]
    raw = _raw(arguments)
    messages = [
        {"role": "system", "content": "原合同"},
        {"role": "user", "content": "原始全部需求"},
        {"role": "assistant", "content": raw},
    ]
    before = copy.deepcopy(messages)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        repaired = PromptBuilder.build_compact_plan_repair(messages, raw, ("缺组",))
    payload = json.loads(repaired[-1].get("content", ""))
    assert isinstance(payload.get("staticPlanReferences"), dict)
    assert payload.get("toolResult") == {
        "name": "submit_card_plan", "ok": False, "errors": ["缺组"],
    }
    assert isinstance(payload.get("outputFormat"), dict)
    assert len(repaired) == len(messages) + 1
    assert repaired[:-1] == before
    assert messages == before
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        dynamic = PromptBuilder.build_compact_plan_repair(messages, raw, ("缺组",))
    dynamic_payload = json.loads(dynamic[-1].get("content", ""))
    assert "staticPlanReferences" not in dynamic_payload


def test_consistent_static_plan_with_an_unrelated_error_gets_no_ledger():
    raw = _raw(_arguments(5))
    messages = [
        {"role": "system", "content": "原合同"},
        {"role": "user", "content": "原始需求"},
        {"role": "assistant", "content": raw},
    ]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        repaired = PromptBuilder.build_compact_plan_repair(messages, raw, ("来源引用不匹配",))
    payload = json.loads(repaired[-1].get("content", ""))
    assert "staticPlanReferences" not in payload
