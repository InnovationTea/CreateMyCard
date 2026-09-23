"""耳机条件覆盖、二选一准入及局部禁止动作的回归。"""

import json
from itertools import permutations

import pytest

from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessorKind,
)
from services.template_generation.engine.cardplan.earphone_action_policy import (
    resolve_earphone_candidate_actions,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    _earphone_template_reference,
    search_template_variants,
)
from services.template_generation.engine.pipeline import (
    TemplateRouteNotApplicable,
    generate_template_a2ui,
)
from services.template_generation.source_adapter import prepare_template_source_dsl
from services.template_generation.tests.test_earphone_case_intent import (
    _ACTION,
    _CASE_FIELDS,
    _binding,
    _card,
    _CaseModel,
    _task,
)

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
