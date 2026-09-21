"""设备电量 6/8：候选入口与仅缺口可用的文本等级变体。"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from models.generation import EventAction
from services.card_validation.compact_dsl_validator import validate_compact_dsl
from services.template_generation.controls import TemplateControls
from services.template_generation.engine import pipeline
from services.template_generation.engine.advanced.scope_planner import TemplateRouteNotApplicable
from services.template_generation.engine.cardplan.battery_action_policy import (
    resolve_battery_settings_fallback,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    search_template_variants,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)
from services.template_generation.tests.test_battery_action_policy import (
    _ARGS,
    _CAPABILITY,
    _HEALTH,
    _SETTINGS,
    _case,
    _search,
)

_HEALTH_FIELDS = ("/healthStatusDesc", "/batteryCapacityLevelDesc")
_LEVEL_FIELDS = ("/batterySOCText", "/batteryCapacityLevelDesc")
_FALLBACK_TEMPLATE = "BatteryOverviewPercentLevelHero@1"


def _health_event() -> EventAction:
    return EventAction(
        id=_HEALTH, call="clickToDeeplink", args={**_ARGS, "uri": "smart_charge_battery_health"},
    )


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


@pytest.mark.parametrize("reason", [
    "health-only", "settings-first", "settings-invalid", "settings-duplicate",
    "health-duplicate", "health-invalid", "health-missing", "not-requested", "forbidden",
])
def test_health_entry_is_a_narrow_fallback(reason: str, registry: CardPlanRegistry) -> None:
    fields = _HEALTH_FIELDS if reason != "not-requested" else ("/batterySOCText",)
    case = _case(fields)
    events = [_health_event()]
    expected = (_HEALTH,)
    if reason == "settings-first":
        events += case.task.eventCandidates
        expected = (_SETTINGS,)
    elif reason == "settings-invalid":
        events += [case.task.eventCandidates[0].model_copy(update={"args": {}})]
        expected = ()
    elif reason == "settings-duplicate":
        events += case.task.eventCandidates * 2
        expected = ()
    elif reason == "health-duplicate":
        events *= 2
        expected = ()
    elif reason == "health-invalid":
        events = [_health_event().model_copy(update={"args": _ARGS})]
        expected = ()
    elif reason == "health-missing":
        events = []
        expected = ()
    elif reason in {"not-requested", "forbidden"}:
        expected = ()
    intent = case.intent
    if reason == "forbidden":
        intent = intent.model_copy(update={"allow_battery_settings_fallback": False})
    task = case.task.model_copy(update={"eventCandidates": events})
    resolved = resolve_battery_settings_fallback(intent, _search(case, registry), task)
    assert resolved.action_ids == expected
    assert resolved.required_output_fields_by_capability == (
        intent.required_output_fields_by_capability
    )


@pytest.mark.parametrize("fields", [
    ("/batterySOCText",), ("/batteryCapacityLevelDesc",),
    (*_LEVEL_FIELDS, "/chargingStatusDesc"),
])
def test_percent_level_variant_does_not_broaden_other_queries(
    fields: tuple[str, ...], registry: CardPlanRegistry,
) -> None:
    case = _case(fields, with_full=True)
    result = _search(case, registry)
    candidates = {c.template_id for c in result.business_candidates[0].candidates}
    assert _FALLBACK_TEMPLATE not in candidates


def test_existing_full_keeps_the_same_candidates_when_text_level_variant_is_added(
    registry: CardPlanRegistry,
) -> None:
    case = _case(_LEVEL_FIELDS, with_full=True)
    previous = CardPlanRegistry(disabled_template_ids=(_FALLBACK_TEMPLATE,))
    assert _search(case, registry) == _search(case, previous)


@pytest.mark.parametrize("reason", ["disabled", "missing-level", "missing-text", "wrong-type"])
def test_new_variant_does_not_relax_required_data_or_controls(
    reason: str, registry: CardPlanRegistry,
) -> None:
    case = _case(_LEVEL_FIELDS)
    if reason == "disabled":
        registry = CardPlanRegistry(disabled_template_ids=(_FALLBACK_TEMPLATE,))
    else:
        task = case.task.model_copy(deep=True)
        data = task.dataModelSchema.get("data")
        assert isinstance(data, dict)
        battery = data.get("phoneBattery")
        assert isinstance(battery, dict)
        if reason == "missing-level":
            battery.pop("batteryCapacityLevelDesc")
        elif reason == "missing-text":
            battery.pop("batterySOCText")
        else:
            battery["batterySOCText"] = {"type": "integer", "sampleValue": 68}
        case = replace(case, task=task)
    with pytest.raises(TemplateRetrievalMiss):
        _search(case, registry)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["health", "level", "charging"])
@pytest.mark.parametrize("fusion", [False, True])
async def test_cases_compile_and_pass_the_production_font_validator(
    kind: str, fusion: bool,
) -> None:
    fields = _HEALTH_FIELDS if kind == "health" else _LEVEL_FIELDS
    template = "BatteryOverviewHealthLevelHero@1" if kind == "health" else _FALLBACK_TEMPLATE
    event_id, label = _SETTINGS, "电池设置"
    if kind == "charging":
        fields = ("/batterySOCText", "/chargingStatusDesc")
        template = "BatteryOverviewChargingProgressHero@1"
    case = _case(fields)
    task = case.task
    if kind == "health":
        task = task.model_copy(update={"eventCandidates": [_health_event()]})
        event_id, label = _HEALTH, "电池健康"
    body = 'Template("HeroActionLayout@1",{},Template(' + json.dumps(template) + ',{}),'
    body += 'Template("PillAction@1",' + json.dumps({"actionId": event_id, "label": label}) + '));'

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return body

    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), Model(), enable_fusion_ball=fusion,
    )
    validate_compact_dsl(
        convert_a2ui_to_compact_dsl(output.a2ui, size="2x2"),
        # Production validates against the original TaskSpec, without internal selectors.
        task_spec=task.model_dump(mode="json"),
        card_spec=case.card,
    )
    assert [event.id for event in output.projected_task_spec.eventCandidates] == [event_id]
    assert output.a2ui.count('"call":"clickToDeeplink"') == 1
    assert label in output.a2ui
    if kind == "level":
        assert "batteryCapacityLevelDesc" in output.a2ui
        assert '"Progress"' not in output.a2ui
        assert "chargingStatusDesc" not in output.a2ui
    assert case.intent.required_output_fields_by_capability == {_CAPABILITY: fields}


def test_mixed_business_does_not_gain_the_single_battery_fallback(
    registry: CardPlanRegistry,
) -> None:
    case = _case(_LEVEL_FIELDS)
    intent = case.intent.model_copy(update={"required_output_fields_by_capability": {
        _CAPABILITY: _LEVEL_FIELDS, "GetCalendarEvents": (),
    }})
    calendar_binding = case.binding.model_copy(update={
        "capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar",
    })
    with pytest.raises(
        TemplateRetrievalMiss, match="no provider template covers.*GetPhoneBatteryInfo",
    ):
        search_template_variants(
            intent, case.task, registry, (case.binding, calendar_binding), case.card,
        )


def test_new_variant_cannot_bypass_a_trusted_template_restriction(
    registry: CardPlanRegistry,
) -> None:
    case = _case(_LEVEL_FIELDS)
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(
            case.intent, case.task, registry, (case.binding,), case.card,
            preferred_template_ids=("BatteryOverviewChargingProgressHero@1",),
        )


@pytest.mark.asyncio
async def test_legacy_llm_route_does_not_receive_new_variant(
    monkeypatch: pytest.MonkeyPatch, registry: CardPlanRegistry,
) -> None:
    case = _case(_LEVEL_FIELDS)
    monkeypatch.setattr(pipeline, "get_cardplan_registry", lambda _fusion: registry)
    monkeypatch.setattr(pipeline, "load_template_controls", lambda: TemplateControls(
        schemaVersion="template-controls/1", firstLayerComponentSelector="llm",
    ))

    async def check_legacy_registry(*args: Any, **_kwargs: Any) -> None:
        scoped_registry = args[3]
        assert scoped_registry.enabled_template_ids((_FALLBACK_TEMPLATE,)) == ()
        raise TemplateRouteNotApplicable("test: checked legacy candidates")

    monkeypatch.setattr(pipeline, "plan_template_route_with_llm", check_legacy_registry)
    with pytest.raises(TemplateRouteNotApplicable, match="checked legacy candidates"):
        await pipeline.generate_template_a2ui(case.task, case.card, (case.binding,), object())
    assert registry.enabled_template_ids((_FALLBACK_TEMPLATE,)) == (_FALLBACK_TEMPLATE,)
