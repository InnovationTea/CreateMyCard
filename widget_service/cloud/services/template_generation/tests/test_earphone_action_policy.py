"""耳机按候选动作数量选布局，并在对应模板不可用时回退 Full。"""

import pytest

from services.template_generation.engine.cardplan.earphone_action_policy import (
    resolve_earphone_candidate_actions,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.test_earphone_case_intent import (
    _ACTION,
    _CASE_FIELDS,
    _binding,
    _card,
    _CaseModel,
    _task,
)


@pytest.mark.parametrize("full", [False, True])
@pytest.mark.parametrize("has_candidates", [False, True])
@pytest.mark.parametrize("allowed", [False, True])
def test_single_candidate_prefers_hero_even_when_full_exists(full, has_candidates, allowed):
    task = _task(full)
    if not has_candidates:
        task = task.model_copy(update={"eventCandidates": []})
    original_events = list(task.eventCandidates)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS},
        action=[], allowEarphoneCandidateActions=allowed,
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    resolved = resolve_earphone_candidate_actions(intent, search, task, registry)
    expected = (_ACTION,) if allowed and has_candidates else ()
    assert resolved.action_ids == expected
    assert task.eventCandidates == original_events
    assert resolved.required_output_fields_by_capability == {"GetEarphoneInfo": tuple(_CASE_FIELDS)}


@pytest.mark.asyncio
async def test_empty_model_actions_still_compile_hero_from_input_candidate():
    class Model(_CaseModel):
        async def generate_json(self, *_args, **_kwargs):
            return {
                "requiredOutputFieldsByCapability": {"GetEarphoneInfo": _CASE_FIELDS},
                "action": [], "allowEarphoneCandidateActions": True,
            }

    task = _task(False)
    output = await generate_template_a2ui(task, _card(), (_binding(task),), Model())
    assert "BluetoothDeviceOverviewEarphoneCaseHero@1" in output.template_ids
    assert "PillAction@1" in output.template_ids
    assert [event.id for event in output.projected_task_spec.eventCandidates] == [_ACTION]


def test_explicit_action_and_other_businesses_are_not_rewritten():
    task = _task(True)
    registry = get_cardplan_registry()
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS}, action=[_ACTION],
    )
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    assert resolve_earphone_candidate_actions(intent, search, task, registry) == intent
    mixed = intent.model_copy(update={
        "action_ids": (),
        "required_output_fields_by_capability": {
            "GetEarphoneInfo": _CASE_FIELDS, "ViewWeather": (),
        },
    })
    assert resolve_earphone_candidate_actions(mixed, search, task, registry) == mixed


def test_all_input_candidates_reach_planning_without_two_action_limit(monkeypatch):
    from services.template_generation.engine.cardplan import earphone_action_policy as policy

    task = _task(False)
    event = task.eventCandidates[0]
    ids = (_ACTION, "event.open.music.favorite", "event.open.music.daily")
    events = [event.model_copy(update={"id": event_id}) for event_id in ids]
    task = task.model_copy(update={"eventCandidates": events})
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS}, action=[],
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    recorded = []
    original = policy.plan_template_candidates

    def record(candidate, *args):
        recorded.append(candidate.action_ids)
        return original(candidate, *args)

    monkeypatch.setattr(policy, "plan_template_candidates", record)
    resolved = resolve_earphone_candidate_actions(intent, search, task, registry)
    assert recorded == [(ids[0], ids[1]), (ids[0], ids[2]), (ids[1], ids[2])]
    assert resolved.action_ids == ids[:2]
    assert task.eventCandidates == events


@pytest.mark.parametrize("candidate_count", [1, 2])
def test_missing_preferred_role_preserves_available_full(candidate_count):
    from services.template_generation.engine.cardplan.template_plan_planner import (
        plan_template_candidates,
    )

    task = _task(True)
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    fields = data.get("earphone")
    assert isinstance(fields, dict)
    fields["isConnected"] = {"type": "boolean", "sampleValue": False}
    event = task.eventCandidates[0]
    ids = (_ACTION, "event.open.music.favorite")
    events = [event.model_copy(update={"id": event_id}) for event_id in ids[:candidate_count]]
    task = task.model_copy(update={"eventCandidates": events})
    required = tuple("/" + name for name in fields)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": required}, action=[],
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    resolved = resolve_earphone_candidate_actions(intent, search, task, registry)
    assert resolved.action_ids == ()
    plans = plan_template_candidates(resolved, search, task, registry)
    assert plans[0].business_slots[0].template_id == "BluetoothDeviceOverviewEarbudPairFull@1"


@pytest.mark.parametrize("candidate_count", [2, 3])
def test_unavailable_compact_tries_single_action_hero_before_full(candidate_count):
    from services.template_generation.engine.cardplan.earphone_action_policy import (
        restrict_earphone_action_role,
    )
    from services.template_generation.engine.cardplan.registry import CardPlanRegistry
    from services.template_generation.engine.cardplan.template_plan_planner import (
        plan_template_candidates,
    )

    task = _task(True)
    event = task.eventCandidates[0]
    ids = (_ACTION, "event.open.music.favorite", "event.open.music.daily")
    events = [event.model_copy(update={"id": event_id}) for event_id in ids[:candidate_count]]
    task = task.model_copy(update={"eventCandidates": events})
    registry = CardPlanRegistry(
        disabled_template_ids=("BluetoothDeviceOverviewEarphoneCaseCompact@1",),
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS}, action=[],
    )
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    full_plans = plan_template_candidates(intent, search, task, registry)
    assert full_plans[0].layout_template_id == "SingleFocusLayout@1"
    resolved = resolve_earphone_candidate_actions(intent, search, task, registry)
    assert resolved.action_ids == (_ACTION,)
    hero_search = restrict_earphone_action_role(search, len(resolved.action_ids))
    hero_plans = plan_template_candidates(resolved, hero_search, task, registry)
    assert hero_plans[0].layout_template_id == "HeroActionLayout@1"
    assert task.eventCandidates == events
