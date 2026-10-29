"""全文裁省压力下复用安全同对象续行；不重排已成功 DSL。"""

import copy
import json

import pytest

from models.artifact import ArtifactMeta, WidgetArtifact
from services import card_validation
from services.card_validation.compact_validation.semantic.static_content import (
    static_fact_coverage,
    static_group_errors,
)
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.protocol_registry import A2UIProtocolRegistry
from services.static_content_components import complete_static_text_trial
from services.static_content_presentation import (
    _trial_continuation,
    static_presentation_candidates,
    trial_static_presentation,
)
from services.validator import ArtifactValidator


def _case():
    texts = [
        "星光展览·滨江展馆", "2028年11月7日–9日 每日19:30开放",
        "11月7日场次已售罄", "11月8日、9日场次余票紧张", "380/680/980/1580/1980元",
    ]
    facts = []
    for index, text in enumerate(texts):
        facts.append({
            "requirement": text, "text": text, "sourceTexts": [text], "priority": "must",
            "displayRole": "title" if index == 0 else "body",
        })
    return {
        "info_required": facts, "presentationStyle": "records",
        "contentGroups": [
            {"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "schedule", "kind": "object", "identity": "开放安排",
             "factIndexes": [1, 2, 3]},
            {"id": "price", "kind": "object", "identity": "票价", "factIndexes": [4]},
        ],
    }


def _facts(plan):
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    return facts


def _groups(plan):
    groups = plan.get("contentGroups")
    assert isinstance(groups, list)
    return groups


def _task(plan):
    return {
        "userQuery": "；".join(fact.get("text", "") for fact in _facts(plan)),
        "size": "2x4", "dataModelSchema": {"data": {}},
        "appVersion": "11.7.5.205", "romVersion": "6.0.0.328",
        "eventCandidates": [], "assetCandidates": [],
    }


@pytest.fixture(autouse=True)
def static_policy():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def test_full_continuation_keeps_original_facts_groups_and_fixed_fonts():
    plan = _case()
    before = copy.deepcopy(plan)
    task = _task(plan)
    candidates = static_presentation_candidates(plan, "2x4")
    trial = trial_static_presentation(plan, task.get("userQuery"), "2x4")
    assert trial.source is not None and trial.source not in candidates
    assert trial.attempted == 2 and trial.errors == ()
    assert plan == before
    assert static_presentation_candidates(plan, "2x4") == candidates
    assert not static_group_errors(trial.source, plan)
    assert all(fact.visible for fact in static_fact_coverage(trial.source, plan))
    profile = A2UIProtocolRegistry().get_profile()
    card = {"suggestSize": "2x4", "title": "展览安排", "description": "完整展览排期和票价"}
    with complete_static_text_trial():
        card_validation.validate_compact_dsl(
            trial.source, task_spec=task, card_spec=card, compact_plan=plan,
            layout_scope="W-static-content-guided",
        )
    result = DesignCompactProcessor().process(trial.source, DslProcessingContext(
        size="2x4", task_spec=task, card_spec=card, protocol_profile=profile,
        compact_plan=plan, content_policy=STATIC_CONTENT_POLICY,
        layout_scope="W-static-content-guided", colorless_layout=True,
    ))
    assert not result.errors
    rows = [json.loads(line) for line in trial.source.splitlines()]
    assert [json.loads(line) for line in result.source_dsl.splitlines()] == rows
    items = rows[2][2].get("items")
    assert isinstance(items, list) and len(items) == 4
    assert [item.get("assist") for item in items] == [
        fact.get("text") for fact in _facts(plan)[1:]
    ]
    for line in result.standard_dsl.splitlines():
        components = json.loads(line).get("updateComponents", {}).get("components", [])
        for component in components:
            if component.get("component") == "Text":
                assert component.get("styles", {}).get("fontSize") == 12
    artifact = WidgetArtifact(
        genui=result.standard_dsl, taskSpec=task, cardSpec=card,
        effectiveCapabilities={"data": [], "event": [], "asset": []},
        meta=ArtifactMeta(protocolProfileId=profile.get("id"), createdAt=0,
                          capabilityRegistryVersion="offline"),
    )
    assert ArtifactValidator({}).validate_layout(artifact, profile) == []


def test_cross_object_borrowing_is_rejected_by_existing_mapping():
    plan = _case()
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source is not None
    rows = [json.loads(line) for line in trial.source.splitlines()]
    items = rows[2][2].get("items")
    assert isinstance(items, list)
    first = items[0].get("assist")
    items[0]["assist"] = items[-1].get("assist")
    items[-1]["assist"] = first
    wrong = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    assert any("GROUP_MISMATCH" in error for error in static_group_errors(wrong, plan))


def test_complete_original_remains_preferred_without_extra_trial(monkeypatch):
    plan = _case()
    texts = ("上午开放", "下午开放", "晚上开放", "免费")
    for fact, text in zip(_facts(plan)[1:], texts, strict=True):
        fact.update(text=text, requirement=text, sourceTexts=[text])
    original = static_presentation_candidates(plan, "2x4")[0]

    def unexpected(*_args, **_kwargs):
        raise AssertionError("complete original must stay preferred")

    monkeypatch.setattr("services.static_content_presentation._trial_continuation", unexpected)
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source == original and trial.attempted == 1 and trial.errors == ()


def test_failed_extra_trial_preserves_original_source_feedback_and_counts_actual_attempt():
    plan = _case()
    text = "仍须核实具体开放条件以及后续安排" * 12
    _facts(plan)[3].update(text=text, requirement=text, sourceTexts=[text])
    original = static_presentation_candidates(plan, "2x4")[0]
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source == original and trial.attempted == 2
    assert len(trial.errors) == 1 and "body.item0_secondaryText" in trial.errors[0]


@pytest.mark.parametrize("change", ["shared_note", "same_identity", "missing_identity"])
def test_unsafe_ownership_or_shared_non_title_has_no_extra_candidate(change):
    plan = _case()
    if change == "shared_note":
        _facts(plan)[0]["displayRole"] = "body"
    elif change == "same_identity":
        _groups(plan)[2]["identity"] = _groups(plan)[1].get("identity")
    else:
        _groups(plan)[1]["identity"] = None
    trial = _trial_continuation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source is None and trial.attempted == 0 and trial.errors == ()


def test_actions_keep_existing_path_without_trial(monkeypatch):
    plan = _case()
    _facts(plan).append({"actionId": "event.open", "priority": "must"})

    def unexpected(*_args, **_kwargs):
        raise AssertionError("actions must not enter static trial")

    monkeypatch.setattr(card_validation, "validate_compact_dsl", unexpected)
    trial = trial_static_presentation(plan, "保留动作", "2x4")
    assert trial.source is None and trial.attempted == 0 and trial.errors == ()
