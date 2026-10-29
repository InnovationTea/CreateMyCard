"""静态接口恢复不得把失败源误删的必要事实变成正式省略。"""

import copy
import json
import socket

import pytest

from services.card_validation.compact_validation.semantic.static_content import (
    static_fact_coverage,
    static_group_errors,
)
from services.compact_plan import (
    compact_plan_recovery_facts,
    compact_recovery_plan_errors,
    parse_compact_plan_call,
)
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)


@pytest.fixture(autouse=True)
def offline_static_policy(monkeypatch):
    def reject_network(*_args, **_kwargs):
        raise AssertionError("恢复事实回归不得访问网络")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def fact(text, *, priority="must", **extra):
    return {
        "requirement": text, "text": text, "sourceTexts": [text], "priority": priority, **extra,
    }


def inputs():
    texts = ["对象甲", "周一开门", "对象乙", "周二开门", "对象丙", "周三开门"]
    facts = [fact(text) for text in texts]
    groups = []
    for index, name in enumerate(("对象甲", "对象乙", "对象丙")):
        groups.append({
            "id": str(index), "kind": "object", "identity": name,
            "factIndexes": [index * 2, index * 2 + 1],
        })
    plan = {"info_required": facts, "contentGroups": groups}
    task = {
        "size": "2x4", "userQuery": "；".join(texts), "dataModelSchema": {"data": {}},
        "eventCandidates": [], "assetCandidates": [],
    }
    return plan, task


def source(items, *, kind="SingleLineList"):
    rows = [
        ["root", "Layout", {"layout": "W-static-content"}, ["body"]],
        ["body", kind, {"items": items}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def visible_first_only():
    return source([{"text": "对象甲", "assist": "周一开门"}])


def values(facts):
    return [(item.target, item.value) for item in facts]


def test_only_authorized_missing_must_is_omitted_when_other_must_facts_are_lost():
    plan, task = inputs()
    before = copy.deepcopy(plan)
    retained, omitted = compact_plan_recovery_facts(
        visible_first_only(), plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert values(omitted) == [("text", "周二开门")]
    assert values(retained) == [
        ("text", "对象甲"), ("text", "周一开门"), ("text", "对象乙"),
        ("text", "对象丙"), ("text", "周三开门"),
    ]
    assert plan == before


def test_missing_must_without_explicit_permission_stays_required():
    plan, task = inputs()
    retained, omitted = compact_plan_recovery_facts(visible_first_only(), plan, task)
    assert len(retained) == 6
    assert not omitted


def test_previously_authorized_but_restored_facts_are_not_omitted():
    plan, task = inputs()
    dsl = source([
        {"text": "对象甲", "assist": "周一开门"},
        {"text": "对象乙", "assist": "周二开门"},
        {"text": "对象丙", "assist": "周三开门"},
    ])
    retained, omitted = compact_plan_recovery_facts(
        dsl, plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert len(retained) == 6
    assert not omitted


def test_incomplete_value_is_not_complete_restoration():
    plan, task = inputs()
    dsl = source([
        {"text": "对象甲", "assist": "周一开门"},
        {"text": "对象乙", "assist": "周二"},
        {"text": "对象丙", "assist": "周三开门"},
    ])
    retained, omitted = compact_plan_recovery_facts(
        dsl, plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert values(omitted) == [("text", "周二开门")]
    assert len(retained) == 5
    retained_without_permission, omitted_without_permission = compact_plan_recovery_facts(
        dsl, plan, task,
    )
    assert len(retained_without_permission) == 6
    assert not omitted_without_permission


def test_complete_value_under_wrong_owner_stays_required_but_not_valid():
    plan, task = inputs()
    dsl = source([
        {"text": "对象甲", "assist": "周一开门；周二开门"},
        {"text": "对象乙", "assist": "周二"},
        {"text": "对象丙", "assist": "周三开门"},
    ])
    before_errors = static_group_errors(dsl, plan)
    coverage = static_fact_coverage(dsl, plan, (3,))
    assert not coverage[3].visible
    assert coverage[3].text_present
    retained, omitted = compact_plan_recovery_facts(
        dsl, plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert len(retained) == 6
    assert not omitted
    assert before_errors
    assert static_group_errors(dsl, plan) == before_errors


def test_split_schedule_does_not_turn_visible_status_into_recovery_omission():
    texts = [
        "演出安排", "11月7日–9日 上海体育场 每日19:30开演", "票价", "380/680元",
        "11月7日场次", "已售罄", "11月8日、9日场次", "余票紧张",
    ]
    plan = {
        "info_required": [fact(text) for text in texts],
        "contentGroups": [
            {"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "schedule", "kind": "object", "identity": "演出安排", "factIndexes": [1]},
            {"id": "price", "kind": "object", "identity": "票价", "factIndexes": [2, 3]},
            {"id": "sold", "kind": "object", "identity": "11月7日场次", "factIndexes": [4, 5]},
            {
                "id": "tight", "kind": "object", "identity": "11月8日、9日场次",
                "factIndexes": [6, 7],
            },
        ],
    }
    dsl = source([
        {"text": "时间地点", "assist": "11月7日–9日"},
        {"text": "开演", "assist": "每日19:30 上海体育场"},
        {"text": "票价", "assist": "380/680元"},
        {"text": "11月7日场次", "assist": "已售罄"},
        {"text": "11月8日、9日场次", "assist": "余票紧张"},
    ])
    coverage = static_fact_coverage(dsl, plan, (7,))
    assert not coverage[7].visible
    assert coverage[7].text_present
    retained, omitted = compact_plan_recovery_facts(
        dsl, plan, {}, allowed_omitted_fact_indexes=(7,),
    )
    assert len(retained) == 8
    assert not omitted
    assert static_group_errors(dsl, plan)


@pytest.mark.parametrize("text,first_fragment,last_fragment", [
    ("周二开门", "周二", "开门"), ("380", "1380", "其它"),
])
def test_cross_item_fragments_and_longer_number_do_not_prove_presence(
    text, first_fragment, last_fragment,
):
    plan, task = inputs()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[3] = fact(text)
    dsl = source([
        {"text": "对象甲", "assist": first_fragment},
        {"text": "对象乙", "assist": "未知"},
        {"text": "对象丙", "assist": last_fragment},
    ])
    coverage = static_fact_coverage(dsl, plan, (3,))
    assert not coverage[3].text_present
    _, omitted = compact_plan_recovery_facts(
        dsl, plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert values(omitted) == [("text", text)]


def test_unreachable_text_preserves_parser_failure_instead_of_guessing_omission():
    plan, task = inputs()
    dsl = visible_first_only() + '\n["orphan","EmphasisText",{"mainText":"周二开门"}]'
    with pytest.raises(ValueError, match="Unreachable component"):
        compact_plan_recovery_facts(dsl, plan, task, allowed_omitted_fact_indexes=(3,))


def test_equal_text_in_another_object_conservatively_keeps_authorized_fact():
    plan, task = inputs()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[1] = fact("营业时间待定")
    facts[3] = fact("营业时间待定")
    dsl = source([{"text": "对象甲", "assist": "营业时间待定"}])
    retained, omitted = compact_plan_recovery_facts(
        dsl, plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert len(retained) == 6
    assert not omitted
    assert static_group_errors(dsl, plan)


def test_missing_action_is_always_retained():
    plan, task = inputs()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"requirement": "打开详情", "actionId": "action.details", "priority": "must"})
    retained, omitted = compact_plan_recovery_facts(
        visible_first_only(), plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert ("actionId", "action.details") in values(retained)
    assert values(omitted) == [("text", "周二开门")]


def test_missing_unprotected_should_keeps_existing_optional_omission_rule():
    plan, task = inputs()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[3]["priority"] = "should"
    retained, omitted = compact_plan_recovery_facts(visible_first_only(), plan, task)
    assert values(omitted) == [("text", "周二开门")]
    assert len(retained) == 5


@pytest.mark.parametrize("protection", [
    {"protectedTexts": ["周二开门"]}, {"preserveVerbatim": True},
])
def test_protected_should_is_not_implicitly_authorized(protection):
    plan, task = inputs()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[3].update({"priority": "should", **protection})
    retained, omitted = compact_plan_recovery_facts(visible_first_only(), plan, task)
    assert len(retained) == 6
    assert not omitted


def test_equal_values_in_different_objects_do_not_share_drop_permission():
    plan, task = inputs()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[3] = fact("营业时间待定")
    facts[5] = fact("营业时间待定")
    retained, omitted = compact_plan_recovery_facts(
        visible_first_only(), plan, task, allowed_omitted_fact_indexes=(3,),
    )
    assert values(omitted) == [("text", "营业时间待定")]
    assert values(retained).count(("text", "营业时间待定")) == 1
    assert len(retained) == 5


def test_recovery_plan_accepts_restored_unauthorized_must_and_rejects_omitted_fact_reentry():
    plan, task = inputs()
    retained, _ = compact_plan_recovery_facts(
        visible_first_only(), plan, task, allowed_omitted_fact_indexes=(3,),
    )
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    recovery = {
        "info_required": [facts[0], facts[1], facts[2], facts[4], facts[5]],
        "contentGroups": [
            {"id": "0", "kind": "object", "identity": "对象甲", "factIndexes": [0, 1]},
            {"id": "1", "kind": "object", "identity": "对象乙", "factIndexes": [2]},
            {"id": "2", "kind": "object", "identity": "对象丙", "factIndexes": [3, 4]},
        ],
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": recovery}, ensure_ascii=False)
    accepted = parse_compact_plan_call(raw, task).plan
    assert not compact_recovery_plan_errors(accepted, retained)
    assert compact_recovery_plan_errors(plan, retained)


@pytest.mark.parametrize("allowed", [(), (0,)])
def test_dynamic_recovery_keeps_existing_visible_fact_semantics(allowed):
    plan = {"info_required": [
        {"requirement": "当前值", "dataId": "/data/current", "priority": "must"},
        {"requirement": "其它值", "dataId": "/data/other", "priority": "must"},
        {"requirement": "打开详情", "actionId": "action.details", "priority": "must"},
    ]}
    dsl = '\n'.join([
        '["root","Column",{},["main"]]',
        '["main","EmphasisText",{"mainText":{"path":"/data/current"},"fontSize":18}]',
    ])
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        retained, omitted = compact_plan_recovery_facts(
            dsl, plan, {"size": "2x2"}, allowed_omitted_fact_indexes=allowed,
        )
    assert values(retained) == [("dataId", "/data/current"), ("actionId", "action.details")]
    assert values(omitted) == [("dataId", "/data/other")]
