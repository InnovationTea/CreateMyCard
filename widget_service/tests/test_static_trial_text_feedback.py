"""Plan 全文压力仅提供软反馈，正式候选和组件省略号合同保持不变。"""

import copy
import json

import pytest

from services import card_validation
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.static_content_components import complete_static_text_trial
from services.static_content_planning import select_static_plan_content
from services.static_content_presentation import (
    static_presentation_candidates,
    trial_static_presentation,
)


def _fact(text, role="body", priority="must"):
    return {
        "requirement": text, "text": text, "sourceTexts": [text],
        "displayRole": role, "priority": priority,
    }


def _plan(text="次日到场"):
    return {
        "info_required": [
            _fact("出行安排", "title"), _fact("甲站", "label"), _fact("09:00到场"),
            _fact("乙站", "label"), _fact(text),
        ],
        "contentGroups": [
            {"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "first", "kind": "object", "identity": "甲站", "factIndexes": [1, 2]},
            {"id": "second", "kind": "object", "identity": "乙站", "factIndexes": [3, 4]},
        ],
        "presentationStyle": "records",
    }


def _query(plan):
    return "；".join(fact.get("text", "") for fact in plan.get("info_required", []))


@pytest.fixture(autouse=True)
def _static_scope():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


@pytest.mark.parametrize("role,field", [("body", "secondaryText"), ("label", "primaryText")])
def test_allowed_ellipsis_adds_exact_pressure_without_replacing_source(role, field):
    plan = _plan("两处来源日期不一致，均未标注改期，请等待进一步确认")
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    if role == "label":
        facts[3] = _fact("乙站：两处来源日期不一致，均未标注改期", "label")
        facts[4] = _fact("次日到场")
    original = copy.deepcopy(plan)
    source = static_presentation_candidates(plan, "2x2")[0]
    standard = convert_compact_dsl_to_a2ui(source, size="2x2")
    trial = trial_static_presentation(plan, _query(plan), "2x2")
    assert trial.source == source
    assert trial.attempted == (2 if role == "label" else 1)
    assert len(trial.errors) == 1
    message = trial.errors[0]
    assert "正式组件UX允许省略号，原候选仍可用" in message
    assert "不是新增发布门禁或事实删减授权" in message
    assert f"body.item1_{field}" in message
    assert "126vp" in message
    assert "仅允许 1 行" in message
    assert convert_compact_dsl_to_a2ui(source, size="2x2") == standard
    assert plan == original


def test_fully_visible_original_candidate_keeps_empty_feedback():
    plan = _plan()
    source = static_presentation_candidates(plan, "2x2")[0]
    trial = trial_static_presentation(plan, _query(plan), "2x2")
    assert trial.source == source
    assert trial.attempted == 1
    assert trial.errors == ()


def test_existing_plan_selection_receives_pressure_without_changing_facts():
    plan = _plan("两处来源日期不一致，均未标注改期，请等待进一步确认")
    facts = plan.get("info_required")
    groups = plan.get("contentGroups")
    assert isinstance(facts, list)
    assert isinstance(groups, list)
    source = static_presentation_candidates(plan, "2x2")[0]
    selection = select_static_plan_content(
        facts, groups, _query(plan), "2x2", presentation_style="records",
    )
    assert selection.presentation == source
    assert selection.facts == facts
    assert selection.groups == groups
    assert "body.item1_secondaryText" in "\n".join(selection.trial_errors)
    assert selection.omitted_contents == ()


def test_long_original_still_precedes_later_complete_optional_candidate():
    plan = _plan()
    facts = plan.get("info_required")
    groups = plan.get("contentGroups")
    assert isinstance(facts, list)
    assert isinstance(groups, list)
    facts.append(_fact("辅助说明请在到场前再查看最新通知内容以确认具体安排", priority="should"))
    groups[2]["factIndexes"].append(5)
    original_sources = static_presentation_candidates(plan, "2x2")
    assert len(original_sources) > 1
    with complete_static_text_trial():
        convert_compact_dsl_to_a2ui(original_sources[-1], size="2x2")
    trial = trial_static_presentation(plan, _query(plan), "2x2")
    assert trial.source == original_sources[0]
    assert trial.attempted == 2
    assert "辅助说明" in trial.source
    assert "完整文字展示压力" in "\n".join(trial.errors)


def test_fallback_is_measured_once_and_keeps_existing_feedback(monkeypatch):
    facts = [
        _fact("猫咪分龄每日喂食量", "title"),
        _fact("每天50至70克干粮，分4餐"), _fact("每天60至90克干粮，分3餐"),
        _fact("每天40至60克干粮，分2餐"), _fact("每天35至50克，选易消化配方"),
        _fact("各阶段均保证自由饮水"),
    ]
    groups = [{"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]}]
    for index, name in enumerate(("2至4月龄幼猫", "4至12月龄", "1至7岁成年猫", "7岁以上老年猫"), 1):
        groups.append({
            "id": f"object{index}", "kind": "object", "identity": name, "factIndexes": [index],
        })
    groups.append({"id": "note", "kind": "shared", "identity": None, "factIndexes": [5]})
    plan = {"info_required": facts, "contentGroups": groups, "presentationStyle": "comparison"}
    calls = []
    validate = card_validation.validate_compact_dsl

    def observed(source, **kwargs):
        calls.append(source)
        return validate(source, **kwargs)

    monkeypatch.setattr(card_validation, "validate_compact_dsl", observed)
    trial = trial_static_presentation(plan, _query(plan), "2x4")
    assert trial.source is not None
    assert "猫咪分龄每日喂食量；各阶段均保证自由饮水" in trial.source
    assert trial.source not in static_presentation_candidates(plan, "2x4")
    assert calls.count(trial.source) == 1
    assert len(calls) == trial.attempted
    assert trial.errors == ()


def test_existing_optional_omission_notice_is_not_replaced():
    plan = _plan()
    facts = plan.get("info_required")
    groups = plan.get("contentGroups")
    assert isinstance(facts, list)
    assert isinstance(groups, list)
    facts.append(_fact("补充说明" * 100, priority="should"))
    groups.append({"id": "note", "kind": "shared", "identity": None, "factIndexes": [5]})
    trial = trial_static_presentation(plan, _query(plan), "2x2")
    assert trial.source is not None
    assert "补充说明" not in trial.source
    assert "省略了事实索引[5]" in trial.errors[0]
    assert all("完整文字展示压力" not in message for message in trial.errors)


def test_action_plan_does_not_enter_trial_validation(monkeypatch):
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"actionId": "event.open", "priority": "must"})

    def unexpected(*_args, **_kwargs):
        raise AssertionError("action plan must keep its existing path")

    monkeypatch.setattr(card_validation, "validate_compact_dsl", unexpected)
    trial = trial_static_presentation(plan, "展示动作", "2x2")
    assert trial.source is None
    assert trial.attempted == 0
    assert trial.errors == ()


def test_trial_does_not_mutate_generated_component_properties():
    plan = _plan("很长的说明文字" * 20)
    source = static_presentation_candidates(plan, "2x2")[0]
    before = [json.loads(line) for line in source.splitlines()]
    trial = trial_static_presentation(plan, _query(plan), "2x2")
    assert trial.source is not None
    assert [json.loads(line) for line in trial.source.splitlines()] == before
