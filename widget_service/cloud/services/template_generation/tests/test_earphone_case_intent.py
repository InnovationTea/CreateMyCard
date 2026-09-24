"""仓电量场景的提示词作用域、动作需求和完整模板链路回归。"""

import json
from itertools import permutations
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessorKind,
)
from services.template_generation.engine.cardplan.earphone_action_policy import (
    resolve_earphone_candidate_actions,
    restrict_earphone_action_role,
)
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    _earphone_template_reference,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.engine.pipeline import (
    TemplateRouteNotApplicable,
    generate_template_a2ui,
)
from services.template_generation.source_adapter import prepare_template_source_dsl

_ACTION = "event.open.settings.bluetooth"
_CASE_FIELDS = ["/batteryLevel", "/chargingStatusDesc"]
_SELF_CHECK = "【输出前最后自检：耳机仓电量与充电状态】"


def _task(extra_earbuds: bool) -> TaskSpec:
    fields: dict[str, Any] = {
        "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
        "batteryLevel": {"type": "integer", "sampleValue": 0},
        "chargingStatusDesc": {"type": "string", "sampleValue": "充电中"},
    }
    if extra_earbuds:
        for name in ("leftBatteryLevel", "rightBatteryLevel"):
            fields[name] = {"type": "integer", "sampleValue": 78}
        for name in ("leftChargingStatusDesc", "rightChargingStatusDesc"):
            fields[name] = {"type": "string", "sampleValue": "未充电"}
    return TaskSpec(
        userQuery="查看耳机盒电量及充电状态",
        size="2x2",
        dataModelSchema={"data": {"earphone": fields}},
        eventCandidates=[
            EventAction(
                id=_ACTION,
                call="clickToDeeplink",
                args={"intentName": "Settings", "uri": "bluetooth_entry"},
            )
        ],
    )


def _binding(task: TaskSpec) -> CandidateDataBinding:
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    fields = data.get("earphone")
    assert isinstance(fields, dict)
    return CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=["/" + name for name in fields],
    )


def _card() -> dict[str, Any]:
    return {
        "title": "耳机仓",
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "GetEarphoneInfo", "writeResultTo": "/data/earphone"}],
    }


class _CaseModel:
    def __init__(self) -> None:
        self.body_calls = 0

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "requiredOutputFieldsByCapability": {"GetEarphoneInfo": _CASE_FIELDS},
            "action": [_ACTION],
        }

    async def generate(self, *_args: Any, **_kwargs: Any) -> str:
        self.body_calls += 1
        return (
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarphoneCaseHero@1",{}),'
            'Template("PillAction@1",'
            '{"actionId":"event.open.settings.bluetooth","label":"蓝牙设置"}));'
        )


@pytest.mark.parametrize("extra_earbuds", [False, True])
@pytest.mark.asyncio
async def test_case_requires_action_and_compiles_without_losing_core_fields(
    extra_earbuds: bool,
) -> None:
    task = _task(extra_earbuds)
    bindings = (_binding(task),)
    registry = get_cardplan_registry()
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS}, action=[]
    )
    search = search_template_variants(intent, task, registry, bindings, _card())
    if extra_earbuds:
        full_plans = plan_template_candidates(intent, search, task, registry)
        assert full_plans
        selected_template = full_plans[0].business_slots[0].template_id
        assert selected_template == "BluetoothDeviceOverviewEarbudPairFull@1"
        assert not full_plans[0].action_assignments
    else:
        with pytest.raises(TemplateRetrievalMiss, match="supported atomic plan"):
            plan_template_candidates(intent, search, task, registry)

    selected = intent.model_copy(update={"action_ids": (_ACTION,)})
    plans = plan_template_candidates(selected, search, task, registry)
    assert plans
    assert plans[0].business_slots[0].template_id == "BluetoothDeviceOverviewEarphoneCaseHero@1"
    model = _CaseModel()
    output = await generate_template_a2ui(task, _card(), bindings, model)
    assert model.body_calls == 1
    assert "BluetoothDeviceOverviewEarphoneCaseHero@1" in output.template_ids
    for path in _CASE_FIELDS:
        assert "/data/earphone" + path in output.a2ui
    assert "/data/earphone/leftBatteryLevel" not in output.a2ui
    assert "/data/earphone/rightBatteryLevel" not in output.a2ui


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("mixed", [False, True])
def test_case_prompt_self_check_is_only_for_small_single_earphone_business(
    size: str, mixed: bool,
) -> None:
    task = _task(True).model_copy(update={"size": size})
    bindings = (_binding(task),)
    if mixed:
        bindings += (
            CandidateDataBinding(
                capabilityId="ViewWeather", writeResultTo="/data/weather",
                candidateOutputFields=["/current/condition"],
            ),
        )
    if size == "2x4":
        with pytest.raises(TemplateRetrievalMiss, match="does not support 2x4"):
            build_template_retrieval_prompt(task, get_cardplan_registry(), bindings)
        return
    messages = build_template_retrieval_prompt(task, get_cardplan_registry(), bindings)
    system = messages[0].get("content")
    assert isinstance(system, str)
    assert (_SELF_CHECK in system) == (size == "2x2" and not mixed)
    assert ("输入动作全部保留为候选，不在第一层筛除" in system) == (not mixed)


@pytest.mark.parametrize("has_action", [False, True])
def test_prompt_keeps_actual_action_candidates_and_negative_examples(has_action: bool) -> None:
    task = _task(False)
    if not has_action:
        task = task.model_copy(update={"eventCandidates": []})
    messages = build_template_retrieval_prompt(task, get_cardplan_registry(), (_binding(task),))
    system = messages[0].get("content")
    content = messages[1].get("content")
    assert isinstance(system, str)
    assert isinstance(content, str)
    assert "输入动作全部保留为候选，不在第一层筛除" in system
    assert "一个候选动作按Hero→Full；两个及以上候选动作按Compact→Hero→Full" in system
    assert "action只填写query明确要求的合法动作" in system
    assert "allowEarphoneCandidateActions=true" in system
    payload = json.loads(content)
    actions = payload.get("actionCandidates")
    assert isinstance(actions, list)
    assert bool(actions) == has_action


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


CHARGES = ("leftChargingStatusDesc", "rightChargingStatusDesc", "chargingStatusDesc")
TEMPLATES = ("BluetoothDeviceOverviewEarbudPairFull@1", "BluetoothDeviceOverviewEarbudTripleHero@1")


def fields_of(task):
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    fields = data.get("earphone")
    assert isinstance(fields, dict)
    return fields


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("mask", range(8))
def test_grouped_charging_fields_count_only_when_visible(template, mask):
    task = _task(True)
    fields = fields_of(task)
    for index, name in enumerate(CHARGES):
        if not mask & (1 << index):
            fields.pop(name)
    required = ["/batteryLevel", "/leftBatteryLevel", "/rightBatteryLevel"]
    registry = get_cardplan_registry()
    binding = _binding(task)
    references = _earphone_template_reference(registry, (binding,))
    reference = next(item for item in references if item.get("templateId") == template)
    for name in CHARGES:
        assert ("/" + name in reference.get("displayFields", [])) == (mask == 7)
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"GetEarphoneInfo": required})
    search_template_variants(intent, task, registry, (binding,), _card(),
                             preferred_template_ids=(template,))
    if "chargingStatusDesc" not in fields:
        return
    required.append("/chargingStatusDesc")
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"GetEarphoneInfo": required})
    if mask != 7:
        with pytest.raises(TemplateRetrievalMiss):
            search_template_variants(intent, task, registry, (binding,), _card(),
                                     preferred_template_ids=(template,))
    else:
        result = search_template_variants(intent, task, registry, (binding,), _card(),
                                          preferred_template_ids=(template,))
        candidate = result.business_candidates[0].candidates[0]
        assert "/chargingStatusDesc" in candidate.covered_explicit_fields


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["identity", "charging"])
async def test_impossible_input_does_not_call_body_model(missing):
    task = _task(True)
    fields = fields_of(task)
    if missing == "identity":
        fields.pop("earphoneName")
        task = task.model_copy(update={"eventCandidates": []})
        template = TEMPLATES[0]
    else:
        fields.pop("leftChargingStatusDesc")
        fields.pop("rightChargingStatusDesc")
        template = TEMPLATES[1]
    required = ["/batteryLevel", "/leftBatteryLevel", "/rightBatteryLevel"]
    if missing == "charging":
        required.append("/chargingStatusDesc")

    class Model(_CaseModel):
        async def generate_json(self, *_args, **_kwargs):
            return {"requiredOutputFieldsByCapability": {"GetEarphoneInfo": required},
                    "action": [_ACTION] if missing == "charging" else []}

    model = Model()
    with pytest.raises(TemplateRouteNotApplicable):
        await generate_template_a2ui(task, _card(), (_binding(task),), model,
                                     trusted_template_candidate_ids=(template,))
    assert model.body_calls == 0


@pytest.mark.parametrize("ids", list(permutations((_ACTION, "music.favorite", "music.daily"))))
def test_partial_exclusions_are_applied_before_candidate_count(ids):
    task = _task(False)
    event = task.eventCandidates[0]
    events = []
    for event_id in ids:
        args = event.args if event_id == _ACTION else {"uri": event_id}
        events.append(event.model_copy(update={"id": event_id, "args": args}))
    task = task.model_copy(update={"eventCandidates": events})
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS},
        excludedActionIds=["music.favorite", "music.daily"],
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    resolved = resolve_earphone_candidate_actions(intent, search, task, registry)
    assert resolved.action_ids == (_ACTION,)
    assert [event.id for event in task.eventCandidates] == list(ids)


@pytest.mark.parametrize("excluded,selected", [(["unknown"], []), ([_ACTION], [_ACTION])])
def test_invalid_or_conflicting_exclusions_are_rejected(excluded, selected):
    task = _task(False)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS},
        excludedActionIds=excluded, action=selected,
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    with pytest.raises(TemplateRetrievalMiss):
        resolve_earphone_candidate_actions(intent, search, task, registry)


@pytest.mark.asyncio
async def test_partial_exclusions_reach_generated_actions():
    task = _task(False)
    event = task.eventCandidates[0]
    ids = ("music.favorite", _ACTION, "music.daily")
    events = []
    for event_id in ids:
        args = event.args if event_id == _ACTION else {"uri": event_id}
        events.append(event.model_copy(update={"id": event_id, "args": args}))
    task = task.model_copy(update={"eventCandidates": events})

    class Model(_CaseModel):
        async def generate_json(self, *_args, **_kwargs):
            return {"requiredOutputFieldsByCapability": {"GetEarphoneInfo": _CASE_FIELDS},
                    "action": [], "excludedActionIds": ["music.favorite", "music.daily"]}

    result = await generate_template_a2ui(task, _card(), (_binding(task),), Model())
    assert [event.id for event in result.projected_task_spec.eventCandidates] == [_ACTION]
    components = []
    for line in result.a2ui.splitlines():
        components.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    assert any(component.get("onClick") for component in components)
    assert "music.favorite" not in result.a2ui
    assert "music.daily" not in result.a2ui

    profile = {"version": "v0.9", "catalogId": "ohos.a2ui.extended.catalog.form"}
    compact = prepare_template_source_dsl(
        result.a2ui, processor_kind=DslProcessorKind.DESIGN_COMPACT,
        size="2x2", protocol_profile=profile,
    )
    processed = DesignCompactProcessor().process(compact, DslProcessingContext(
        size="2x2", card_spec=_card(),
        task_spec=result.projected_task_spec.model_dump(mode="json"),
        protocol_profile=profile, skip_compact_dsl_validation=True,
    ))
    assert not processed.errors
    assert "bluetooth_entry" in processed.standard_dsl
    assert "music.favorite" not in processed.standard_dsl
    assert "music.daily" not in processed.standard_dsl


@pytest.mark.parametrize("allowed", [False, True])
def test_all_candidates_excluded_never_auto_adds_actions(allowed):
    task = _task(True)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS},
        excludedActionIds=[_ACTION], allowEarphoneCandidateActions=allowed,
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, (_binding(task),), _card())
    assert resolve_earphone_candidate_actions(intent, search, task, registry).action_ids == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("template", TEMPLATES)
async def test_complete_status_group_survives_public_processor(template):
    task = _task(True)
    fields = fields_of(task)
    required = ["/" + name for name in fields]
    hero = template.endswith("Hero@1")
    if not hero:
        task = task.model_copy(update={"eventCandidates": []})

    class Model(_CaseModel):
        async def generate_json(self, *_args, **_kwargs):
            return {"requiredOutputFieldsByCapability": {"GetEarphoneInfo": required},
                    "action": [_ACTION] if hero else []}

        async def generate(self, *_args, **_kwargs):
            self.body_calls += 1
            if hero:
                return ('Template("HeroActionLayout@1",{},'
                        f'Template("{template}",{{}}),'
                        'Template("PillAction@1",'
                        '{"actionId":"event.open.settings.bluetooth","label":"蓝牙设置"}));')
            return f'Template("SingleFocusLayout@1",{{}},Template("{template}",{{}}));'

    result = await generate_template_a2ui(task, _card(), (_binding(task),), Model(),
                                         trusted_template_candidate_ids=(template,))
    profile = {"version": "v0.9", "catalogId": "ohos.a2ui.extended.catalog.form"}
    compact = prepare_template_source_dsl(
        result.a2ui, processor_kind=DslProcessorKind.DESIGN_COMPACT,
        size="2x2", protocol_profile=profile,
    )
    processed = DesignCompactProcessor().process(compact, DslProcessingContext(
        size="2x2", card_spec=_card(),
        task_spec=result.projected_task_spec.model_dump(mode="json"),
        protocol_profile=profile, skip_compact_dsl_validation=True,
    ))
    assert not processed.errors
    for output in (result.a2ui, processed.standard_dsl):
        components = []
        for line in output.splitlines():
            components.extend(json.loads(line).get("updateComponents", {}).get("components", []))
        rendered = json.dumps(components)
        for field in CHARGES:
            assert "/data/earphone/" + field in rendered


@pytest.mark.parametrize("key", ["requiredAnyOf", "displayTogether"])
@pytest.mark.parametrize("groups", [[[]], [["/unknown"]], [["/batteryLevel", "/batteryLevel"]]])
def test_condition_contract_rejects_invalid_groups(key, groups):
    from pydantic import ValidationError

    from services.template_generation.engine.cardplan.provider_bundle import ProviderTemplateEntry

    entry = {
        "templateId": "BluetoothDeviceOverviewEarbudPairFull@1",
        "businessId": "BluetoothDeviceOverview", "capabilityId": "GetEarphoneInfo",
        "description": "测试约束", "entry": "templates/test.cardtpl",
        "primaryData": ["/batteryLevel"], key: groups,
    }
    with pytest.raises(ValidationError):
        ProviderTemplateEntry.model_validate(entry)


@pytest.mark.parametrize("value,valid", [(False, True), (True, True), ("false", False)])
def test_identity_admission_uses_type_and_presence_not_truthiness(value, valid):
    task = _task(True)
    fields = fields_of(task)
    fields.pop("earphoneName")
    fields["isConnected"] = {"type": "boolean" if isinstance(value, bool) else "string",
                             "sampleValue": value}
    registry = get_cardplan_registry()
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={
        "GetEarphoneInfo": ["/batteryLevel", "/leftBatteryLevel", "/rightBatteryLevel"],
    })
    if valid:
        search_template_variants(intent, task, registry, (_binding(task),), _card(),
                                 preferred_template_ids=(TEMPLATES[0],))
    else:
        with pytest.raises(TemplateRetrievalMiss):
            search_template_variants(intent, task, registry, (_binding(task),), _card(),
                                     preferred_template_ids=(TEMPLATES[0],))
