"""Support 事件白名单、动作实例归属、Prompt 及编译防绕过回归。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from models.generation import EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.business_actions import supports_business_action
from services.template_generation.engine.cardplan.compiler import (
    _validate_allowed_template_plan,
    _validate_business_template_action,
    compile_ux_layout_card,
)
from services.template_generation.engine.cardplan.models import (
    ActionBinding,
    HybridBodyContract,
    HybridLimits,
    TemplatePlan,
)
from services.template_generation.engine.cardplan.parser import parse_ux_layout_card
from services.template_generation.engine.cardplan.preview_dataset import _build_data_schema
from services.template_generation.engine.cardplan.prompt import (
    action_bindings,
    build_template_prompt_contracts,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    ProviderTemplateEntry,
    load_provider_bundle,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    _selected_action_ids,
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateBusinessCandidates,
    TemplateRetrievalMiss,
    TemplateSearchCandidate,
    TemplateSearchIntent,
    TemplateSearchResult,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.test_support import provider_gallery

_ROOT = Path(__file__).resolve().parents[1]
_EVENT_PATH = _ROOT.parents[1] / "data/capabilities/app-11.7.5.205_rom-6.0/event_capabilities.json"
_EVENTS = json.loads(_EVENT_PATH.read_text(encoding="utf-8"))
_EVENT_IDS = tuple(event.get("id") for event in _EVENTS)
_APPROVED = {
    "WeatherOverviewTemperatureSupport@1": [
        "event.open.weather"
    ],
    "WeatherOverviewTemperatureUvSupport@1": [
        "event.open.weather"
    ],
    "WeatherOverviewTemperaturecoldLevelSupport@1": [
        "event.open.weather"
    ],
    "BatteryOverviewSupport@1": [
        "event.open.settings.battery",
        "event.open.settings.batteryHealth",
        "event.setPowerSavingMode"
    ],
    "ScheduleOverviewTimeSupport@1": [
        "event.viewCalendarEvent",
        "event.enter.meeting"
    ],
    "ScheduleOverviewLocationSupport@1": [
        "event.viewCalendarEvent",
        "event.enter.meeting"
    ],
    "ScheduleOverviewStartTimeSupport@1": [
        "event.viewCalendarEvent",
        "event.enter.meeting"
    ],
    "ScheduleOverviewDateSupport@1": [
        "event.viewCalendarEvent",
        "event.enter.meeting"
    ],
    "CountdownOverviewSupport@1": [],
    "BluetoothDeviceOverviewEarbudsSupport@1": [
        "event.open.settings.bluetooth"
    ],
    "BluetoothDeviceOverviewChargeSupport@1": [
        "event.open.settings.bluetooth"
    ],
    "ActivityOverviewSupport@1": [
        "event.open.health.sport"
    ],
    "WorkoutOverviewSupport@1": [
        "event.open.health.sport"
    ],
    "HeartRateOverviewSupport@1": [
        "event.open.health.sport"
    ],
    "SleepOverviewSupport@1": [
        "event.open.health.sleep"
    ],
    "AppUsageOverviewSupport@1": [
        "event.open.settings.parentControl"
    ],
    "ResourceUsageOverviewSupport@1": [
        "event.clean.memory"
    ]
}


def _event(event_id: str) -> EventAction:
    payload = next(item for item in _EVENTS if item.get("id") == event_id)
    action = payload.get("actionTemplate")
    assert isinstance(action, dict)
    call = action.get("call")
    args = action.get("args")
    assert isinstance(call, str)
    assert isinstance(args, dict)
    args = json.loads(json.dumps(args).replace("/events/i/", "/events/0/"))
    return EventAction(id=event_id, call=call, args=args)


def _task(events: tuple[str, ...]) -> TaskSpec:
    return TaskSpec(
        userQuery="展示对应业务，并执行明确要求的关联操作",
        size="2x2",
        dataModelSchema={},
        eventCandidates=[_event(event_id) for event_id in events],
    )


def _binding(event_id: str) -> ActionBinding:
    bindings = action_bindings(_task((event_id,)))
    assert len(bindings) == 1
    return bindings[0]


def _plans(template_ids: tuple[str, str], events: tuple[str, ...]) -> tuple[TemplatePlan, ...]:
    registry = get_cardplan_registry()
    groups: list[TemplateBusinessCandidates] = []
    required: dict[str, tuple[str, ...]] = {}
    for template_id in template_ids:
        definition = registry.require_template(template_id)
        capability_id = definition.capability_id
        business_id = definition.business_id
        assert capability_id is not None
        assert business_id is not None
        fields = definition.required_data
        required[capability_id] = fields
        groups.append(TemplateBusinessCandidates(
            capabilityId=capability_id,
            businessId=business_id,
            explicitFields=fields,
            candidates=(TemplateSearchCandidate(
                templateId=template_id,
                coveredExplicitFields=fields,
            ),),
        ))
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability=required, action=events)
    result = TemplateSearchResult(cardSize="2x2", businessCandidates=tuple(groups))
    return plan_template_candidates(intent, result, _task(events), registry)


def _contract(events: tuple[str, ...], **updates: object) -> HybridBodyContract:
    bindings = action_bindings(_task(events))
    contract = HybridBodyContract(
        theme_profile_id="2x2-two-support",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=(),
        allowed_asset_sources=(),
        trusted_literals=(),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        action_bindings=bindings,
        content_action_ids=tuple(binding.action_id for binding in bindings),
        limits=HybridLimits(
            max_raw_components=16, max_expanded_components=64,
            max_nesting_depth=8, vertical_budget_vp=128,
        ),
    )
    return contract.model_copy(update=updates)


@pytest.mark.parametrize("template_id", tuple(_APPROVED))
def test_support_allowlist_exactly_matches_approved_policy(template_id: str) -> None:
    definition = get_cardplan_registry().require_template(template_id)
    expected = _APPROVED.get(template_id)
    assert expected is not None
    assert definition.supported_event_ids == tuple(expected)
    assert set(expected).issubset(_EVENT_IDS)


def test_policy_inventory_covers_every_business_support() -> None:
    registry = get_cardplan_registry()
    support_ids = set()
    for template_id in registry.provider_template_ids:
        definition = registry.require_template(template_id)
        if definition.business_id is not None and template_id.endswith("Support@1"):
            support_ids.add(template_id)
    assert support_ids == set(_APPROVED)


@pytest.mark.parametrize("template_id", tuple(_APPROVED))
@pytest.mark.parametrize("event_id", _EVENT_IDS)
def test_support_event_business_matrix(template_id: str, event_id: str) -> None:
    definition = get_cardplan_registry().require_template(template_id)
    expected = _APPROVED.get(template_id)
    assert expected is not None
    assert supports_business_action(definition, _binding(event_id), "2x2") is (
        event_id in expected
    )


@pytest.mark.parametrize("value", (["event.open.weather#1"], [" event.open.weather"],
                                  ["event.open.weather", "event.open.weather"], [12], None))
def test_manifest_rejects_invalid_event_type_ids(value: object) -> None:
    with pytest.raises(ValueError):
        ProviderTemplateEntry(
            templateId="WeatherOverviewTemperatureSupport@1",
            businessId="WeatherOverview",
            capabilityId="ViewWeather",
            description="天气",
            entry="templates/weather-overview.cardtpl",
            supportedEventIds=value,
        )


def test_missing_or_empty_allowlist_denies_embedded_action() -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewTemperatureSupport@1")
    definition = definition.model_copy(update={"supported_event_ids": ()})
    assert not supports_business_action(definition, _binding("event.open.weather"), "2x2")


def test_bundle_rejects_allowlist_without_optional_action_prop(tmp_path: Path) -> None:
    target = tmp_path / "weather"
    shutil.copytree(_ROOT / "resources/source/providers/weather", target)
    manifest_path = target / "provider.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    templates = manifest.get("templates")
    assert isinstance(templates, list)
    entry = next(item for item in templates if item.get("templateId") == "WeatherOverviewFull@1")
    entry["supportedEventIds"] = ["event.open.weather"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="requires optional actionId"):
        load_provider_bundle(target)


@pytest.mark.parametrize("uri", (
    "{{ ${/data/otherWeather/location/cityCode} }}",
    "{{ ${/data/weather/location/prefectureName} }}",
    "60814",
    "{{ ${/data/weather/location/cityCode} + ${/data/other/location/cityCode} }}",
    {"path": "/data/other/location/cityCode"},
))
def test_weather_action_requires_same_city_binding(uri: object) -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewTemperatureSupport@1")
    action = _binding("event.open.weather")
    action = action.model_copy(update={"args": {**action.args, "uri": uri}})
    assert not supports_business_action(definition, action, "2x2")


@pytest.mark.parametrize("value", (
    "{{ ${data.weather.location.cityCode} }}",
    {"path": "/data/weather/location/cityCode"},
))
def test_weather_binding_accepts_registered_expression_forms(value: object) -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewTemperatureSupport@1")
    action = _binding("event.open.weather")
    action = action.model_copy(update={"args": {**action.args, "uri": value}})
    assert supports_business_action(definition, action, "2x2")


@pytest.mark.parametrize("event_id", ("event.viewCalendarEvent", "event.enter.meeting"))
def test_calendar_action_rejects_different_displayed_item(event_id: str) -> None:
    definition = get_cardplan_registry().require_template("ScheduleOverviewTimeSupport@1")
    action = _binding(event_id)
    args = json.loads(json.dumps(action.args).replace("/events/0/", "/events/1/"))
    assert not supports_business_action(definition, action.model_copy(update={"args": args}), "2x2")


def test_event_instances_keep_type_identity_and_request_numbering() -> None:
    event_id = "event.viewCalendarEvent"
    task = _task(("event.open.weather", event_id, event_id))
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetCalendarEvents": ()}, action=(event_id,),
    )
    assert _selected_action_ids(intent, task) == (event_id + "#1", event_id + "#2")
    definition = get_cardplan_registry().require_template("ScheduleOverviewTimeSupport@1")
    instances = action_bindings(task)
    for action in instances:
        if action.event_id == event_id:
            assert supports_business_action(definition, action, "2x2")


def test_planner_never_places_weather_action_on_other_business() -> None:
    plans = _plans(
        ("WeatherOverviewTemperatureSupport@1", "AppUsageOverviewSupport@1"),
        ("event.open.weather",),
    )
    assert 1 <= len(plans) <= 3
    for plan in plans:
        slots = {slot.position: slot for slot in plan.business_slots}
        for assignment in plan.action_assignments:
            slot = slots.get(assignment.business_position)
            assert slot is not None
            assert slot.business_id == "WeatherOverview"


def test_two_events_for_one_business_cannot_spill_into_partner() -> None:
    with pytest.raises(TemplateRetrievalMiss, match="cannot form"):
        _plans(
            ("BatteryOverviewSupport@1", "WeatherOverviewTemperatureSupport@1"),
            ("event.open.settings.battery", "event.setPowerSavingMode"),
        )


@pytest.mark.parametrize("events", ((), ("event.open.weather",)))
def test_countdown_can_pair_without_own_action(events: tuple[str, ...]) -> None:
    assert _plans(
        ("CountdownOverviewSupport@1", "WeatherOverviewTemperatureSupport@1"), events,
    )


def test_countdown_cannot_use_alarm_as_a_related_event() -> None:
    with pytest.raises(TemplateRetrievalMiss, match="cannot form"):
        _plans(
            ("CountdownOverviewSupport@1", "WeatherOverviewTemperatureSupport@1"),
            ("event.open.clock.alarm",),
        )


def test_compiler_rechecks_policy_even_if_the_plan_is_forged() -> None:
    plans = _plans(
        ("WeatherOverviewTemperatureSupport@1", "AppUsageOverviewSupport@1"),
        ("event.open.weather",),
    )
    plan = plans[0]
    target = next(slot for slot in plan.business_slots if slot.business_id == "AppUsageOverview")
    assignment = plan.action_assignments[0].model_copy(
        update={"business_position": target.position},
    )
    forged = plan.model_copy(update={"action_assignments": (assignment,)})
    children: list[str] = []
    for slot in plan.business_slots:
        params = {"actionId": assignment.action_id} if slot.position == target.position else {}
        children.append(f'Template("{slot.template_id}",{json.dumps(params)})')
    source = 'Template("TwoSupportLayout@1",{},' + ",".join(children) + ");"
    contract = _contract(("event.open.weather",), allowed_template_plans=(forged,))
    with pytest.raises(TerselConversionError, match="supported events or data context"):
        _validate_allowed_template_plan(
            parse_ux_layout_card(source), contract, get_cardplan_registry(),
        )


def test_legacy_business_expansion_also_rejects_wrong_action() -> None:
    definition = get_cardplan_registry().require_template("SleepOverviewSupport@1")
    contract = _contract(("event.open.health.sport",))
    assert not contract.allowed_template_plans
    with pytest.raises(TerselConversionError, match="supported events or data context"):
        _validate_business_template_action(
            definition, {"actionId": "event.open.health.sport"}, contract, "2x2",
        )


def test_prompt_projects_only_matching_action_instances() -> None:
    from services.template_generation.tests.test_template_plan_planner import _weather_task

    task = _weather_task().model_copy(update={
        "eventCandidates": [_event("event.open.weather"), _event("event.open.settings.bluetooth")],
    })
    contract = _contract(("event.open.weather", "event.open.settings.bluetooth"))
    card_spec = {
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
    }
    contracts = build_template_prompt_contracts(
        ("WeatherOverviewTemperatureSupport@1",), contract, get_cardplan_registry(),
        task_spec=task, card_spec=card_spec, ux_layout_root=True,
    )
    assert len(contracts) == 1
    sources = contracts[0].get("parameterSources")
    assert isinstance(sources, dict)
    action_source = sources.get("actionId")
    assert isinstance(action_source, dict)
    assert action_source.get("allowedActionIds") == ["event.open.weather"]
    assert action_source.get("supportedEventIds") == ("event.open.weather",)


def test_gallery_support_events_come_from_each_template_allowlist(tmp_path: Path) -> None:
    manifest = provider_gallery.write_gallery_input_dataset(tmp_path)
    provider = next(item for item in manifest.providers if item.providerSlug == "two-support")
    assert len(provider.cases) == 50
    countdown_cases = []
    for case in provider.cases:
        payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
        content = payload.get("content")
        assert isinstance(content, dict)
        events = content.get("candidateEventCandidates")
        assert isinstance(events, list)
        allowed = []
        for template_id in (case.targetTemplateId, case.partnerTemplateId):
            definition = get_cardplan_registry().require_template(template_id)
            if definition.supported_event_ids:
                allowed.append(definition.supported_event_ids[0])
        assert [event.get("capabilityId") for event in events] == allowed[:len(events)]
        if case.targetTemplateId == "CountdownOverviewSupport@1":
            countdown_cases.append(case.scenarioId)
            assert all(event.get("capabilityId") == "event.open.weather" for event in events)
    assert set(countdown_cases) == {"dual-support-content", "dual-support-one-action"}


@pytest.mark.parametrize(
    ("use_planner", "wrong_target"),
    ((True, False), (False, False), (False, True)),
)
def test_real_compiler_enforces_support_event_ownership(
    use_planner: bool, wrong_target: bool,
) -> None:
    template_ids = ("BatteryOverviewSupport@1", "CountdownOverviewSupport@1")
    events = ("event.open.settings.battery",)
    registry = get_cardplan_registry()
    plans = _plans(template_ids, events)
    data: dict[str, object] = {}
    data_bindings: list[dict[str, str]] = []
    for template_id in template_ids:
        definition = registry.require_template(template_id)
        generated_data = _build_data_schema(definition).get("data")
        assert isinstance(generated_data, dict)
        data.update(generated_data)
        capability_id = definition.capability_id
        root = definition.data_domain
        assert capability_id is not None
        assert root is not None
        data_bindings.append({"capabilityId": capability_id, "writeResultTo": root})
    task = _task(events).model_copy(update={"dataModelSchema": {"data": data}})
    card_spec = {
        "title": "电量倒计时", "description": "查看电池设置",
        "suggestSize": "2x2", "dataBindings": data_bindings,
    }
    projection = build_ux_mixed_prompt(
        task_spec=task, card_spec=card_spec, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=registry,
    )
    contract = projection.contract
    if not use_planner:
        contract = contract.model_copy(update={"allowed_template_plans": ()})
    event_owner = "CountdownOverview" if wrong_target else "BatteryOverview"
    children: list[str] = []
    for slot in plans[0].business_slots:
        params = {"actionId": events[0]} if slot.business_id == event_owner else {}
        children.append(f'Template("{slot.template_id}",{json.dumps(params)})')
    source = 'Template("TwoSupportLayout@1",{},' + ",".join(children) + ");"
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    if wrong_target:
        with pytest.raises(TerselConversionError, match="supported events or data context"):
            compile_ux_layout_card(
                source, task_spec=task, contract=contract, protocol_profile=profile,
                registry=registry, card_spec=card_spec, enable_data_bindings=True,
            )
    else:
        result = compile_ux_layout_card(
            source, task_spec=task, contract=contract, protocol_profile=profile,
            registry=registry, card_spec=card_spec, enable_data_bindings=True,
        )
        messages = [json.loads(line) for line in result.a2ui.splitlines() if line.strip()]
        assert provider_gallery._count_a2ui_actions(messages) == 1
        assert result.stats.action_used_ids == events
