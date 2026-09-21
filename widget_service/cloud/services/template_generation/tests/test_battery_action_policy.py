"""电量默认设置入口的正向链路、输入保真及跨业务隔离。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced.scope_planner import TemplateRouteNotApplicable
from services.template_generation.engine.cardplan.battery_action_policy import (
    resolve_battery_settings_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    TemplateSearchResult,
    build_template_retrieval_prompt,
    search_template_variants,
)

_CAPABILITY = "GetPhoneBatteryInfo"
_SETTINGS = "event.open.settings.battery"
_HEALTH = "event.open.settings.batteryHealth"
_TEXT_FIELDS = ("/batterySOCText", "/chargingStatusDesc")
_FULL_FIELDS = (*_TEXT_FIELDS, "/batterySOC", "/batteryCapacityLevelDesc")
_ARGS = {
    "intentName": "Settings", "bundleName": "com.huawei.hmos.settings",
    "abilityName": "com.huawei.hmos.settings.MainAbility", "uri": "battery",
}
_SAMPLES = {
    "/batterySOC": 68, "/batterySOCText": "68%", "/chargingStatusDesc": "未充电",
    "/batteryCapacityLevelDesc": "正常电量", "/healthStatusDesc": "正常",
    "/nowCurrentText": "-151 mA", "/voltageText": "4 V", "/isBatteryPresentText": "在位",
    "/updatedAt": "09:00", "/pluggedTypeDesc": "未连接充电器",
}


@dataclass(frozen=True)
class BatteryCase:
    task: TaskSpec
    binding: CandidateDataBinding
    card: dict[str, Any]
    intent: TemplateSearchIntent


def _case(fields: tuple[str, ...] = _TEXT_FIELDS, *, with_full: bool = False) -> BatteryCase:
    available_fields = (*fields, "/updatedAt")
    if with_full:
        available_fields += _FULL_FIELDS
    schema = {}
    for path in available_fields:
        value = _SAMPLES.get(path)
        assert value is not None
        schema[path.removeprefix("/")] = {
            "type": "integer" if isinstance(value, int) else "string",
            "sampleValue": value, "description": "电量回归字段",
        }
    task = TaskSpec(
        userQuery="创建电量卡片，显示电量和充电状态", size="2x2",
        dataModelSchema={"data": {"phoneBattery": schema}},
        eventCandidates=[EventAction(id=_SETTINGS, call="clickToDeeplink", args=dict(_ARGS))],
    )
    binding = CandidateDataBinding(
        capabilityId=_CAPABILITY, writeResultTo="/data/phoneBattery",
        candidateOutputFields=list(dict.fromkeys(available_fields)),
    )
    return BatteryCase(
        task=task, binding=binding,
        card={"title": "电量卡片", "description": "展示手机电量", "suggestSize": "2x2",
              "dataBindings": [{"capabilityId": _CAPABILITY,
                                "writeResultTo": "/data/phoneBattery"}]},
        intent=TemplateSearchIntent(
            requiredOutputFieldsByCapability={_CAPABILITY: fields},
            allowBatterySettingsFallback=True,
        ),
    )


def _search(case: BatteryCase, registry: CardPlanRegistry) -> TemplateSearchResult:
    return search_template_variants(case.intent, case.task, registry, (case.binding,), case.card)


@pytest.mark.parametrize(("fields", "template"), [
    (("/batterySOCText",), "BatteryOverviewChargingProgressHero@1"),
    (_TEXT_FIELDS, "BatteryOverviewChargingProgressHero@1"),
    ((*_TEXT_FIELDS, "/healthStatusDesc"), "BatteryOverviewChargingProgressHero@1"),
    (("/healthStatusDesc", "/batteryCapacityLevelDesc"), "BatteryOverviewHealthLevelHero@1"),
    (("/nowCurrentText", "/voltageText", "/batteryCapacityLevelDesc", "/isBatteryPresentText"),
     "BatteryOverviewChargingDiagnosticsHero@1"),
])
def test_hero_adds_one_settings_action_without_changing_fields_or_inputs(
    fields: tuple[str, ...], template: str,
) -> None:
    case = _case(fields)
    registry = CardPlanRegistry()
    original_task = case.task.model_dump()
    original_binding = case.binding.model_dump()
    result = _search(case, registry)
    resolved = resolve_battery_settings_fallback(case.intent, result, case.task)
    assert resolved.action_ids == (_SETTINGS,)
    assert resolved.required_output_fields_by_capability == {_CAPABILITY: fields}
    assert resolved.model_dump(exclude={"action_ids"}) == case.intent.model_dump(
        exclude={"action_ids"},
    )
    assert case.intent.action_ids == ()
    assert case.task.model_dump() == original_task
    assert case.binding.model_dump() == original_binding
    assert "/updatedAt" not in fields  # 候选中的额外字段不会变成用户要求。
    plans = plan_template_candidates(resolved, result, case.task, registry)
    assert plans
    for plan in plans:
        assert plan.layout_template_id == "HeroActionLayout@1"
        assert plan.business_slots[0].template_id == template
        assert len(plan.action_assignments) == 1
        assert plan.action_assignments[0].action_id == _SETTINGS
    assert resolve_battery_settings_fallback(resolved, result, case.task) is resolved


def test_full_wins_without_adding_button_even_when_hero_is_available() -> None:
    case = _case(with_full=True)
    registry = CardPlanRegistry()
    result = _search(case, registry)
    candidates = {c.template_id for c in result.business_candidates[0].candidates}
    assert "BatteryOverviewFull@1" in candidates
    assert "BatteryOverviewChargingProgressHero@1" in candidates
    resolved = resolve_battery_settings_fallback(case.intent, result, case.task)
    assert resolved is case.intent
    plans = plan_template_candidates(resolved, result, case.task, registry)
    assert all(p.layout_template_id == "SingleFocusLayout@1" for p in plans)


@pytest.mark.parametrize(("key", "value"), [
    ("uri", "smart_charge_battery_health"), ("uri", None),
    ("uri", "{{ ${/data/phoneBattery/uri} }}"), ("extra", "unexpected"),
    ("intentName", "Other"), ("bundleName", "other.app"), ("abilityName", "OtherAbility"),
])
def test_settings_target_must_match_the_approved_static_destination(key: str, value: Any) -> None:
    case = _case()
    args = dict(_ARGS)
    if value is None:
        args.pop(key)
    else:
        args[key] = value
    event = case.task.eventCandidates[0].model_copy(update={"args": args})
    task = case.task.model_copy(update={"eventCandidates": [event]})
    result = _search(case, CardPlanRegistry())
    assert resolve_battery_settings_fallback(case.intent, result, task) is case.intent


@pytest.mark.parametrize("reason", ["missing", "duplicate", "health-only", "wrong-call"])
def test_fallback_never_creates_replaces_or_disambiguates_events(reason: str) -> None:
    case = _case()
    event = case.task.eventCandidates[0]
    if reason == "missing":
        events = []
    elif reason == "duplicate":
        events = [event, event]
    elif reason == "health-only":
        events = [event.model_copy(update={
            "id": _HEALTH, "args": {**_ARGS, "uri": "smart_charge_battery_health"},
        })]
    else:
        events = [event.model_copy(update={"call": "clickToIntent"})]
    task = case.task.model_copy(update={"eventCandidates": events})
    result = _search(case, CardPlanRegistry())
    assert resolve_battery_settings_fallback(case.intent, result, task) is case.intent


@pytest.mark.parametrize("reason", [
    "forbidden", "explicit-action", "two-actions", "wide", "size-mismatch",
    "calendar", "earphone", "weather", "mixed", "multiple-groups", "wrong-business",
    "wrong-capability",
])
def test_fallback_is_isolated_to_unselected_single_battery_2x2(reason: str) -> None:
    case = _case()
    intent, task = case.intent, case.task
    result = _search(case, CardPlanRegistry())
    if reason == "forbidden":
        intent = intent.model_copy(update={"allow_battery_settings_fallback": False})
    elif reason in {"explicit-action", "two-actions"}:
        actions = (_HEALTH,) if reason == "explicit-action" else (_HEALTH, _SETTINGS)
        intent = intent.model_copy(update={"action_ids": actions})
    elif reason == "wide":
        task = task.model_copy(update={"size": "2x4"})
        result = result.model_copy(update={"card_size": "2x4"})
    elif reason == "size-mismatch":
        result = result.model_copy(update={"card_size": "2x4"})
    elif reason == "multiple-groups":
        result = result.model_copy(update={"business_candidates": result.business_candidates * 2})
    elif reason in {"wrong-business", "wrong-capability"}:
        key = "business_id" if reason == "wrong-business" else "capability_id"
        group = result.business_candidates[0].model_copy(update={key: "Other"})
        result = result.model_copy(update={"business_candidates": (group,)})
    else:
        capabilities = {"calendar": "GetCalendarEvents", "earphone": "GetEarphoneInfo"}
        capability = capabilities.get(reason, "ViewWeather")
        fields = {capability: ()}
        if reason == "mixed":
            fields.update(intent.required_output_fields_by_capability)
        intent = intent.model_copy(update={"required_output_fields_by_capability": fields})
    assert resolve_battery_settings_fallback(intent, result, task) is intent


def test_compact_and_support_without_hero_do_not_trigger_fallback() -> None:
    case = _case(("/batterySOC", "/chargingStatusDesc"))
    registry = CardPlanRegistry(disabled_template_ids=("BatteryOverviewChargingRingHero@1",))
    result = _search(case, registry)
    assert {c.template_id for c in result.business_candidates[0].candidates} == {
        "BatteryOverviewCompact@1", "BatteryOverviewSupport@1",
    }
    assert resolve_battery_settings_fallback(case.intent, result, case.task) is case.intent


def test_text_level_fallback_covers_both_fields_without_fabricating_numeric_data() -> None:
    case = _case(("/batterySOCText", "/batteryCapacityLevelDesc"))
    registry = CardPlanRegistry()
    result = _search(case, registry)
    assert [c.template_id for c in result.business_candidates[0].candidates] == [
        "BatteryOverviewPercentLevelHero@1",
    ]
    assert "batterySOC\"" not in json.dumps(case.task.dataModelSchema)
    resolved = resolve_battery_settings_fallback(case.intent, result, case.task)
    plan = plan_template_candidates(resolved, result, case.task, registry)[0]
    assert plan.layout_template_id == "HeroActionLayout@1"
    assert plan.action_assignments[0].action_id == _SETTINGS


@pytest.mark.parametrize("invalid", ["true", "false", 1, 0, None])
def test_battery_flag_is_optional_and_strict(invalid: Any) -> None:
    old = TemplateSearchIntent(requiredOutputFieldsByCapability={_CAPABILITY: _TEXT_FIELDS})
    assert old.allow_battery_settings_fallback is False
    with pytest.raises(ValidationError):
        TemplateSearchIntent(
            requiredOutputFieldsByCapability={_CAPABILITY: _TEXT_FIELDS},
            allowBatterySettingsFallback=invalid,
        )


@pytest.mark.parametrize("capabilities", [
    ("GetCalendarEvents",), ("GetEarphoneInfo",), ("ViewWeather",), ("GetSystemMemInfo",),
    (_CAPABILITY, "GetCalendarEvents"), (_CAPABILITY, "GetEarphoneInfo"),
])
def test_other_and_mixed_business_prompts_do_not_receive_battery_fallback(
    capabilities: tuple[str, ...],
) -> None:
    case = _case()
    bindings = tuple(case.binding.model_copy(update={"capabilityId": c}) for c in capabilities)
    prompt = build_template_retrieval_prompt(case.task, CardPlanRegistry(), bindings)
    system = prompt[0].get("content")
    assert isinstance(system, str)
    assert "allowBatterySettingsFallback" not in system
    assert "默认电池设置入口" not in system


def test_battery_prompt_only_labels_permission_and_keeps_explicit_fields() -> None:
    case = _case()
    prompt = build_template_retrieval_prompt(case.task, CardPlanRegistry(), (case.binding,))
    system = prompt[0].get("content")
    assert isinstance(system, str)
    assert "没有提到按钮不等于禁止按钮" in system
    assert "只展示不交互等时为 false" in system
    assert "action 仍只含显式需求，不直接选择默认入口" in system
    assert "也不得为兜底补字段、删用户要求的字段或编造事件" in system
    schema = json.loads(system.splitlines()[-1])
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    flag = properties.get("allowBatterySettingsFallback")
    assert isinstance(flag, dict)
    assert flag.get("default") is False


@pytest.mark.asyncio
@pytest.mark.parametrize("with_full", [False, True])
@pytest.mark.parametrize("fusion", [False, True])
async def test_default_settings_reaches_second_layer_and_compiles_once(
    monkeypatch: pytest.MonkeyPatch, with_full: bool, fusion: bool,
) -> None:
    case = _case(with_full=with_full)
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    ))

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            assert phase == "template-retrieval-query"
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
            if with_full:
                return ('Template("SingleFocusLayout@1",{},'
                        'Template("BatteryOverviewFull@1",{}));')
            return ('Template("HeroActionLayout@1",{},'
                    'Template("BatteryOverviewChargingProgressHero@1",{}),'
                    'Template("PillAction@1",{"actionId":"event.open.settings.battery",'
                    '"label":"电池设置"}));')

    output = await pipeline.generate_template_a2ui(
        case.task, case.card, (case.binding,), Model(), enable_fusion_ball=fusion,
    )
    selected = output.projected_task_spec.eventCandidates
    assert len(selected) == (0 if with_full else 1)
    assert output.a2ui.count('"call":"clickToDeeplink"') == (0 if with_full else 1)
    if not with_full:
        assert "电池设置" in output.a2ui
        assert selected[0].args == _ARGS


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", [False, None])
async def test_no_button_and_legacy_intents_keep_the_existing_hero_miss(
    monkeypatch: pytest.MonkeyPatch, flag: bool | None,
) -> None:
    case = _case()
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    ))
    task = case.task.model_copy(update={"userQuery": "显示电量和充电状态，不要按钮"})

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            result = {"requiredOutputFieldsByCapability": {_CAPABILITY: _TEXT_FIELDS}}
            if flag is not None:
                result["allowBatterySettingsFallback"] = flag
            return result

        async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
            pytest.fail("禁止按钮或旧输出未授权时不得进入 Hero 二层")

    with pytest.raises(TemplateRouteNotApplicable, match="cannot form"):
        await pipeline.generate_template_a2ui(task, case.card, (case.binding,), Model())


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["explicit", "gallery"])
@pytest.mark.parametrize("with_full", [False, True])
async def test_existing_explicit_and_gallery_actions_are_never_replaced_or_deleted(
    monkeypatch: pytest.MonkeyPatch, source: str, with_full: bool,
) -> None:
    case = _case(with_full=with_full)
    health = EventAction(
        id=_HEALTH, call="clickToDeeplink", args={**_ARGS, "uri": "smart_charge_battery_health"},
    )
    task = case.task.model_copy(update={"eventCandidates": [*case.task.eventCandidates, health]})
    intent = case.intent
    if source == "explicit":
        intent = intent.model_copy(update={"action_ids": (_HEALTH,)})
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="search",
    ))

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            return intent.model_dump(mode="json", by_alias=True)

        async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
            return ('Template("HeroActionLayout@1",{},'
                    'Template("BatteryOverviewChargingProgressHero@1",{}),'
                    'Template("PillAction@1",{"actionId":"event.open.settings.batteryHealth",'
                    '"label":"电池健康"}));')

    trusted_actions = (_HEALTH,) if source == "gallery" else ()
    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), Model(), trusted_template_action_ids=trusted_actions,
    )
    assert [event.id for event in output.projected_task_spec.eventCandidates] == [_HEALTH]
    assert output.a2ui.count('"call":"clickToDeeplink"') == 1
    assert "电池健康" in output.a2ui
