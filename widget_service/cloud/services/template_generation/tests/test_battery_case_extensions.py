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
        registry = CardPlanRegistry(disabled_template_ids=(
            _FALLBACK_TEMPLATE, "BatteryOverviewChargingProgressHero@1",
        ))
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
@pytest.mark.parametrize("kind", [
    "health", "level", "charging", "health-temperature", "charging-level", "charging-only-hero",
    "temperature-only", "temperature-level", "temperature-charging", "temperature-all",
])
@pytest.mark.parametrize("fusion", [False, True])
async def test_cases_compile_and_pass_the_production_font_validator(
    kind: str, fusion: bool,
) -> None:
    fields = _HEALTH_FIELDS if kind == "health" else _LEVEL_FIELDS
    template = "BatteryOverviewHealthLevelHero@1" if kind == "health" else _FALLBACK_TEMPLATE
    if kind == "level":
        template = "BatteryOverviewChargingProgressHero@1"
    event_id, label = _SETTINGS, "电池设置"
    if kind == "charging":
        fields = ("/batterySOCText", "/chargingStatusDesc")
        template = "BatteryOverviewPercentTextFull@1"
    if kind == "health-temperature":
        fields = ("/healthStatusDesc", "/batteryTemperatureText")
        template = "BatteryOverviewHealthTemperatureHero@1"
    if kind == "charging-only-hero":
        fields = ("/batterySOCText", "/chargingStatusDesc")
        template = "BatteryOverviewChargingProgressHero@1"
    if kind == "charging-level":
        fields = (*_LEVEL_FIELDS, "/chargingStatusDesc")
        template = "BatteryOverviewChargingProgressHero@1"
    temperature_fields = {
        "temperature-only": ("/batterySOCText", "/batteryTemperatureText"),
        "temperature-level": (*_LEVEL_FIELDS, "/batteryTemperatureText"),
        "temperature-charging": (
            "/batterySOCText", "/chargingStatusDesc", "/batteryTemperatureText",
        ),
        "temperature-all": (*_LEVEL_FIELDS, "/chargingStatusDesc", "/batteryTemperatureText"),
    }
    selected_fields = temperature_fields.get(kind)
    if selected_fields is not None:
        fields = selected_fields
        template = "BatteryOverviewChargingProgressHero@1"
    case = _case(fields)
    task = case.task
    if kind == "charging":
        task = task.model_copy(update={"eventCandidates": []})
    if kind in {"health", "health-temperature"}:
        task = task.model_copy(update={"eventCandidates": [_health_event()]})
        event_id, label = _HEALTH, "电池健康"
    body = 'Template("HeroActionLayout@1",{},Template(' + json.dumps(template) + ',{}),'
    body += 'Template("PillAction@1",' + json.dumps({"actionId": event_id, "label": label}) + '));'
    if kind == "charging":
        body = 'Template("SingleFocusLayout@1",{},Template(' + json.dumps(template) + ',{}));'

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
    if kind == "charging":
        assert not output.projected_task_spec.eventCandidates
        assert "chargingStatusDesc" in output.a2ui
    else:
        assert [event.id for event in output.projected_task_spec.eventCandidates] == [event_id]
        assert output.a2ui.count('"call":"clickToDeeplink"') == 1
        assert label in output.a2ui
    if kind == "health-temperature":
        assert "healthStatusDesc" in output.a2ui
        assert "batteryTemperatureText" in output.a2ui
        assert "batteryCapacityLevelDesc" not in output.a2ui
    if kind == "level":
        assert "batteryCapacityLevelDesc" in output.a2ui
        assert '"Progress"' not in output.a2ui
        assert "chargingStatusDesc" not in output.a2ui
    singleton_labels = {
        "charging-only-hero": "状态：",
        "level": "电量等级：",
        "temperature-only": "电池温度：",
    }
    expected_label = singleton_labels.get(kind)
    if expected_label is not None:
        assert expected_label in output.a2ui
        assert " · " not in output.a2ui
    if kind in {"charging-level", "temperature-level", "temperature-charging", "temperature-all"}:
        assert " · " in output.a2ui
        for singleton_label in singleton_labels.values():
            assert singleton_label not in output.a2ui
    assert case.intent.required_output_fields_by_capability == {_CAPABILITY: fields}


def test_mixed_business_does_not_gain_the_single_battery_fallback(
    registry: CardPlanRegistry,
) -> None:
    registry = CardPlanRegistry(
        disabled_template_ids=("BatteryOverviewChargingProgressHero@1",),
    )
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
            preferred_template_ids=("BatteryOverviewHealthLevelHero@1",),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
async def test_q231_status_summary_hero_uses_only_four_text_fields(fusion: bool) -> None:
    fields = (
        "/batterySOCText", "/chargingStatusDesc", "/healthStatusDesc", "/batteryTemperatureText",
    )
    case = _case(fields)
    task = case.task.model_copy(update={
        "userQuery": "手机电池状态卡片，显示电量、充电状态、电池健康和温度",
    })

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            assert "优先选择 planCandidates 第一项" in json.dumps(_args, ensure_ascii=False)
            return ('Template("HeroActionLayout@1",{},'
                    'Template("BatteryOverviewStatusSummaryHero@1",{}),'
                    'Template("PillAction@1",{"actionId":"event.open.settings.battery",'
                    '"label":"电池设置"}));')

    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), Model(), enable_fusion_ball=fusion,
    )
    validate_compact_dsl(
        convert_a2ui_to_compact_dsl(output.a2ui, size="2x2"),
        task_spec=task.model_dump(mode="json"), card_spec=case.card,
    )
    for label in ("电池电量", "充电状态", "健康状态", "电池温度"):
        assert label in output.a2ui
    for field in fields:
        assert field in output.a2ui
    for field in (
        "nowCurrentText", "voltageText", "batteryCapacityLevelDesc", "isBatteryPresentText",
    ):
        assert field not in output.a2ui
    assert [event.id for event in output.projected_task_spec.eventCandidates] == [_SETTINGS]


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
async def test_percent_details_full_displays_four_fields(fusion: bool) -> None:
    fields = (
        "/batterySOCText", "/chargingStatusDesc", "/batteryCapacityLevelDesc", "/pluggedTypeDesc",
    )
    case = _case(fields)
    task = case.task.model_copy(update={
        "userQuery": "显示手机电量百分比、充电状态、电量等级、充电类型，不需要按钮",
        "eventCandidates": [],
    })

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return ('Template("SingleFocusLayout@1",{},'
                    'Template("BatteryOverviewPercentDetailsFull@1",{}));')

    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), Model(), enable_fusion_ball=fusion,
    )
    validate_compact_dsl(
        convert_a2ui_to_compact_dsl(output.a2ui, size="2x2"),
        task_spec=task.model_dump(mode="json"), card_spec=case.card,
    )
    assert "BatteryOverviewPercentDetailsFull@1" in output.template_ids
    assert "healthStatusDesc" not in output.a2ui
    assert not output.projected_task_spec.eventCandidates
    components = {}
    for line in output.a2ui.splitlines():
        update = json.loads(line).get("updateComponents", {})
        for component in update.get("components", []):
            components[component.get("id")] = component
    for field in fields:
        value = next(item for item in components.values() if field in str(item.get("content", "")))
        assert value.get("styles", {}).get("fontWeight") == 700
        if field != "/batterySOCText":
            assert value.get("styles", {}).get("textAlign") == "right"
    title = next(item for item in components.values() if item.get("content") == "手机电量")
    body = next(item for item in components.values() if title.get("id") in item.get("children", []))
    children = body.get("children", [])
    assert len(children) == 5
    height = (len(children) - 1) * body.get("itemMargin", 0)
    for child_id in children:
        child = components.get(child_id)
        assert isinstance(child, dict)
        height += child.get("styles", {}).get("height", 0)
    assert height == 112
    assert height <= 150 - 24
    for label in ("充电状态", "电量等级", "充电类型"):
        assert label in output.a2ui


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
async def test_status_level_summary_hero_uses_only_four_text_fields(fusion: bool) -> None:
    fields = (
        "/batterySOCText", "/chargingStatusDesc", "/healthStatusDesc", "/batteryCapacityLevelDesc",
    )
    case = _case(fields)
    task = case.task.model_copy(update={
        "userQuery": "手机电池状态卡片，显示电量、充电状态、电池健康和电量等级",
    })

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            assert "优先选择 planCandidates 第一项" in json.dumps(_args, ensure_ascii=False)
            return ('Template("HeroActionLayout@1",{},'
                    'Template("BatteryOverviewStatusLevelSummaryHero@1",{}),'
                    'Template("PillAction@1",{"actionId":"event.open.settings.battery",'
                    '"label":"电池设置"}));')

    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), Model(), enable_fusion_ball=fusion,
    )
    validate_compact_dsl(
        convert_a2ui_to_compact_dsl(output.a2ui, size="2x2"),
        task_spec=task.model_dump(mode="json"), card_spec=case.card,
    )
    for label in ("电池电量", "充电状态", "健康状态", "电量等级"):
        assert label in output.a2ui
    for field in fields:
        assert field in output.a2ui
    for field in (
        "nowCurrentText", "voltageText", "batteryTemperatureText", "isBatteryPresentText",
    ):
        assert field not in output.a2ui
    assert [event.id for event in output.projected_task_spec.eventCandidates] == [_SETTINGS]


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
async def test_charging_level_summary_hero_uses_only_four_text_fields(fusion: bool) -> None:
    fields = (
        "/batterySOCText", "/chargingStatusDesc", "/pluggedTypeDesc", "/batteryCapacityLevelDesc",
    )
    case = _case(fields)
    task = case.task.model_copy(update={
        "userQuery": "手机电池状态卡片，显示电量、充电状态、充电类型和电量等级",
    })

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
            return case.intent.model_dump(mode="json", by_alias=True)

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            assert "优先选择 planCandidates 第一项" in json.dumps(_args, ensure_ascii=False)
            return ('Template("HeroActionLayout@1",{},'
                    'Template("BatteryOverviewChargingLevelSummaryHero@1",{}),'
                    'Template("PillAction@1",{"actionId":"event.open.settings.battery",'
                    '"label":"电池设置"}));')

    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), Model(), enable_fusion_ball=fusion,
    )
    validate_compact_dsl(
        convert_a2ui_to_compact_dsl(output.a2ui, size="2x2"),
        task_spec=task.model_dump(mode="json"), card_spec=case.card,
    )
    for label in ("电池电量", "充电状态", "充电类型", "电量等级"):
        assert label in output.a2ui
    for field in fields:
        assert field in output.a2ui
    for field in (
        "nowCurrentText", "voltageText", "batteryTemperatureText", "healthStatusDesc",
    ):
        assert field not in output.a2ui
    assert [event.id for event in output.projected_task_spec.eventCandidates] == [_SETTINGS]

    type_row = None
    for line in output.a2ui.splitlines():
        for component in json.loads(line).get("updateComponents", {}).get("components", []):
            if "pluggedTypeDesc" in str(component.get("content", "")):
                type_row = component
    assert isinstance(type_row, dict)
    content = str(type_row.get("content", ""))
    assert "未连接充电器" in content
    assert "未连接" in content
    assert "交流充电器" in content
    assert "无线充电器" in content
    assert type_row.get("styles", {}).get("maxLines") == 1
    assert type_row.get("styles", {}).get("textOverflow") == "ellipsis"
