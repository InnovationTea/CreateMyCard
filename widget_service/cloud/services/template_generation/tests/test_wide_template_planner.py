"""宽版 Search → Plan → FillData 的完整覆盖和原子边界回归。"""

from __future__ import annotations

import json

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _expand_health_metric_generic_template,
    _validate_allowed_template_plan,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, HybridLimits
from services.template_generation.engine.cardplan.parser import parse_ux_layout_card
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    build_template_retrieval_prompt,
    search_template_variants,
)
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.tests.test_template_retrieval import (
    _WEATHER_BATTERY_BINDINGS,
    _field,
    _weather_battery_card_spec,
    _weather_battery_task,
)


def _health_case(include_countdown=False):
    fields = {
        "nightSleepDurationText": _field("7小时1分"),
        "dailySteps": _field(6500, "integer"),
        "exerciseHeartRateMin": _field(61, "integer"),
    }
    paths = tuple("/" + key for key in fields)
    task = TaskSpec(
        userQuery="以睡眠时长为主，同时显示今日步数和最低心率",
        size="2x4",
        dataModelSchema={"data": {"healthSport": fields}},
        assetCandidates=[{"src": "resources/base/media/heart_fill.svg", "description": "心率图标"}],
    )
    bindings = [
        CandidateDataBinding(
            capabilityId="GetHealthAndSportSummary",
            writeResultTo="/data/healthSport",
            candidateOutputFields=list(paths),
        )
    ]
    required = {"GetHealthAndSportSummary": paths}
    if include_countdown:
        data = task.dataModelSchema.get("data")
        assert isinstance(data, dict)
        data["countdown"] = {"countdownDays": _field(30, "integer")}
        bindings.append(
            CandidateDataBinding(
                capabilityId="GetCountdownDays",
                writeResultTo="/data/countdown",
                candidateOutputFields=["/countdownDays"],
            )
        )
        required["GetCountdownDays"] = ("/countdownDays",)
    card = {
        "title": "睡眠助手",
        "suggestSize": "2x4",
        "dataBindings": [
            {"capabilityId": binding.capabilityId, "writeResultTo": binding.writeResultTo}
            for binding in bindings
        ],
    }
    return (
        task,
        tuple(bindings),
        card,
        TemplateSearchIntent(
            requiredOutputFieldsByCapability=required,
            primaryOutputFieldByCapability={"GetHealthAndSportSummary": "/nightSleepDurationText"},
        ),
    )


def _plans(task, bindings, card, intent):
    registry = get_cardplan_registry()
    found = search_template_variants(intent, task, registry, bindings, card)
    return plan_template_candidates(intent, found, task, registry)


def _body(plan, actions, *, tamper=None):
    children = []
    embedded = {
        action.business_position: action.action_id
        for action in plan.action_assignments
        if action.consumer == "business-template"
    }
    for slot in plan.business_slots:
        props = dict(slot.field_bindings)
        if props:
            if "valuePath" in props:
                props["title"] = "步数" if props.get("valuePath") == "/dailySteps" else "最低心率"
                props["sourceIcon"] = "resources/base/media/heart_fill.svg"
            else:
                props["firstTitle"] = "步数"
                props["secondTitle"] = "最低心率"
            if tamper is not None:
                for name in slot.field_bindings:
                    props[name] = tamper
        action_id = embedded.get(slot.position)
        if action_id is not None:
            props["actionId"] = action_id
        children.append(f'Template("{slot.template_id}", {json.dumps(props, ensure_ascii=False)})')
    labels = {action.action_id: action.display_label for action in actions}
    for assignment in plan.action_assignments:
        if assignment.consumer != "root-action":
            continue
        label = labels.get(assignment.action_id)
        assert label is not None
        props = {"actionId": assignment.action_id, "label": label}
        if assignment.action_template_id in {"LargeIconAction@1", "IconAction@1"}:
            props.pop("label")
        if assignment.action_template_id != "PillAction@1":
            props["icon"] = "resources/base/media/heart_fill.svg"
        children.append(
            f'Template("{assignment.action_template_id}", {json.dumps(props, ensure_ascii=False)})'
        )
    return f'Template("{plan.layout_template_id}", {{}}, ' + ", ".join(children) + ");"


def _contract(plans, task):
    return HybridBodyContract(
        theme_profile_id=plans[0].theme_id,
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_asset_sources=(),
        trusted_literals=(),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        allowed_template_ids=(),
        allowed_components=(),
        action_bindings=action_bindings(task),
        allowed_template_plans=plans,
        limits=HybridLimits(
            max_raw_components=80,
            max_expanded_components=200,
            max_nesting_depth=20,
            vertical_budget_vp=136,
        ),
    )


def test_wide_first_layer_has_no_ui_decision():
    task, bindings, _, _ = _health_case()
    messages = build_template_retrieval_prompt(task, get_cardplan_registry(), bindings)
    content = messages[0].get("content")
    assert isinstance(content, str)
    schema = json.loads(content.splitlines()[-1])
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    assert set(properties) == {
        "requiredOutputFieldsByCapability",
        "primaryOutputFieldByCapability",
        "action",
    }
    assert "themes" not in json.loads(messages[1].get("content", "{}"))
    action = properties.get("action")
    assert isinstance(action, dict)
    assert action.get("maxItems") == 4


@pytest.mark.parametrize("richer", (False, True))
def test_more_available_variants_do_not_reject_valid_two_business_layout(richer):
    task = _weather_battery_task(False)
    if richer:
        data = task.dataModelSchema.get("data")
        assert isinstance(data, dict)
        weather = data.get("weather")
        phone = data.get("phoneBattery")
        assert isinstance(weather, dict) and isinstance(phone, dict)
        current = weather.get("current")
        assert isinstance(current, dict)
        current["temperatureText"] = _field("29℃")
        phone["batterySOCText"] = _field("68%")
        phone["batteryCapacityLevelDesc"] = _field("正常电量")
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/condition",),
            "GetPhoneBatteryInfo": ("/batterySOC",),
        }
    )
    plans = _plans(task, _WEATHER_BATTERY_BINDINGS, _weather_battery_card_spec(), intent)
    assert plans
    for plan in plans:
        assert {slot.capability_id for slot in plan.business_slots} == {
            "ViewWeather",
            "GetPhoneBatteryInfo",
        }


@pytest.mark.parametrize("reversed_events", (False, True))
def test_paired_actions_follow_business_ownership(reversed_events):
    task = _weather_battery_task(True)
    if reversed_events:
        task.eventCandidates.reverse()
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/condition",),
            "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
        },
        action=tuple(event.id for event in task.eventCandidates),
    )
    plans = _plans(task, _WEATHER_BATTERY_BINDINGS, _weather_battery_card_spec(), intent)
    for plan in plans:
        for assignment in plan.action_assignments:
            assert assignment.business_position is not None
            slot = plan.business_slots[assignment.business_position]
            expected = (
                "ViewWeather"
                if assignment.action_id == "event.open.weather"
                else "GetPhoneBatteryInfo"
            )
            assert slot.capability_id == expected
        body = _body(plan, action_bindings(task))
        contract = _contract(plans, task)
        assert _validate_allowed_template_plan(
            parse_ux_layout_card(body), contract, get_cardplan_registry(), card_size="2x4"
        )
        swapped = (
            body.replace("event.open.weather", "TEMP")
            .replace("event.open.settings.battery", "event.open.weather")
            .replace("TEMP", "event.open.settings.battery")
        )
        with pytest.raises(TerselConversionError, match="atomic Template Plan"):
            _validate_allowed_template_plan(
                parse_ux_layout_card(swapped), contract, get_cardplan_registry(), card_size="2x4"
            )


@pytest.mark.parametrize("include_countdown", (False, True))
def test_health_residual_plans_cover_every_requested_field_and_business(include_countdown):
    task, bindings, card, intent = _health_case(include_countdown)
    plans = _plans(task, bindings, card, intent)
    for plan in plans:
        assert len(plan.business_slots) <= 4
        coverage = {}
        generic_paths = []
        for slot in plan.business_slots:
            coverage.setdefault(slot.capability_id, set()).update(slot.covered_explicit_fields)
            generic_paths.extend(slot.field_bindings.values())
        assert len(generic_paths) == len(set(generic_paths))
        for capability, fields in intent.required_output_fields_by_capability.items():
            assert set(fields).issubset(coverage.get(capability, set()))
        if include_countdown:
            assert any(slot.business_id == "CountdownOverview" for slot in plan.business_slots)


class _PlanModel:
    def __init__(self, intent, tamper=None, actions=()):
        self.intent = intent
        self.actions = actions
        self.tamper = tamper
        self.calls = 0
        self.body = None

    async def generate_json(self, prompt, **kwargs):
        return self.intent.model_dump(by_alias=True)

    async def generate(self, messages, *args, **kwargs):
        from services.template_generation.engine.cardplan.models import TemplatePlan

        self.calls += 1
        for message in messages:
            for line in message.get("content", "").splitlines():
                if line.startswith("planCandidates="):
                    values = json.loads(line.removeprefix("planCandidates="))
                    plan = TemplatePlan.model_validate(values[0])
                    self.body = _body(plan, self.actions, tamper=self.tamper)
                    return self.body
        raise AssertionError("second layer did not receive atomic plans")


@pytest.mark.asyncio
async def test_health_pipeline_compiles_real_relative_paths():
    task, bindings, card, intent = _health_case()
    model = _PlanModel(intent)
    output = await generate_template_a2ui(task, card, bindings, model)
    assert model.calls == 1
    for path in ("nightSleepDurationText", "dailySteps", "exerciseHeartRateMin"):
        assert "/data/healthSport/" + path in output.a2ui


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", ("/dailySteps", "/nightSleepDurationText"))
async def test_fill_data_cannot_duplicate_or_replace_planned_metric(replacement):
    task, bindings, card, intent = _health_case()
    model = _PlanModel(intent, replacement)
    with pytest.raises(TemplateGenerationError):
        await generate_template_a2ui(task, card, bindings, model)
    assert model.calls == 3


@pytest.mark.parametrize("roots", ((), ("/data/healthSport", "/data/other")))
def test_generic_metric_rejects_missing_or_ambiguous_binding_root(roots):
    task, _, _, _ = _health_case()
    with pytest.raises(TerselConversionError, match="exactly one"):
        _expand_health_metric_generic_template(
            "GenericMetricOverviewCompact@1",
            {},
            task_spec=task,
            provider_binding_roots={"GetHealthAndSportSummary": roots},
            theme_values={},
        )


def test_four_actions_are_limited_to_supported_wide_layouts():
    task = _weather_battery_task(False)
    task.assetCandidates = [
        {"src": "resources/base/media/heart_fill.svg", "description": "动作图标"}
    ]
    ids = (
        "event.open.weather",
        "event.open.settings.battery",
        "event.open.settings.batteryHealth",
        "event.setPowerSavingMode",
    )
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    phone = data.get("phoneBattery")
    assert isinstance(phone, dict)
    phone.update(batterySOCText=_field("68%"), batteryCapacityLevelDesc=_field("正常电量"))
    task.eventCandidates = [EventAction(id=event_id, call="open", args={}) for event_id in ids]
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "GetPhoneBatteryInfo": ("/batterySOC",),
        },
        action=ids,
    )
    plans = _plans(task, _WEATHER_BATTERY_BINDINGS, _weather_battery_card_spec(), intent)
    assert plans
    for plan in plans:
        assert plan.layout_template_id in {
            "WideFullFourActionLayout@1",
            "WideHalfFourLargeActionLayout@1",
        }
        assert len(plan.action_assignments) == 4
        assert {item.action_id for item in plan.action_assignments} == set(ids)
    small = task.model_copy(update={"size": "2x2"})
    with pytest.raises(TemplateRetrievalMiss, match="budget"):
        _plans(small, _WEATHER_BATTERY_BINDINGS, _weather_battery_card_spec(), intent)


@pytest.mark.asyncio
async def test_repeated_generic_instances_are_preserved_end_to_end():
    task, bindings, card, intent = _health_case()
    model = _PlanModel(intent)
    output = await generate_template_a2ui(
        task,
        card,
        bindings,
        model,
        trusted_template_candidate_ids=("SleepOverviewFull@1", "GenericMetricOverviewCompact@1"),
    )
    assert model.calls == 1
    assert model.body is not None
    assert model.body.count('Template("GenericMetricOverviewCompact@1"') == 2
    assert "/data/healthSport/dailySteps" in output.a2ui
    assert "/data/healthSport/exerciseHeartRateMin" in output.a2ui


@pytest.mark.asyncio
@pytest.mark.parametrize("count", (2, 4))
async def test_single_business_shortcuts_compile_through_fill_data(count):
    task = _weather_battery_task(False)
    data = task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    phone = data.get("phoneBattery")
    assert isinstance(phone, dict)
    phone.update(batterySOCText=_field("68%"), batteryCapacityLevelDesc=_field("正常电量"))
    ids = (
        "event.open.settings.battery",
        "event.open.settings.batteryHealth",
        "event.setPowerSavingMode",
        "event.open.settings.bluetooth",
    )[:count]
    task.eventCandidates = [
        EventAction(id=event_id, call="clickToDeeplink", args={"uri": event_id}) for event_id in ids
    ]
    task.assetCandidates = [
        {"src": "resources/base/media/heart_fill.svg", "description": "操作图标"}
    ]
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetPhoneBatteryInfo": ("/batterySOC",)},
        action=ids,
    )
    model = _PlanModel(intent, actions=action_bindings(task))
    output = await generate_template_a2ui(
        task,
        _weather_battery_card_spec(),
        _WEATHER_BATTERY_BINDINGS,
        model,
    )
    assert model.calls == 1
    assert output.a2ui.count('"call":"clickToDeeplink"') == count


@pytest.mark.asyncio
async def test_reversed_actions_generate_the_correct_panels():
    task = _weather_battery_task(True)
    task.eventCandidates.reverse()
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/condition",),
            "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
        },
        action=tuple(event.id for event in task.eventCandidates),
    )
    model = _PlanModel(intent, actions=action_bindings(task))
    output = await generate_template_a2ui(
        task,
        _weather_battery_card_spec(),
        _WEATHER_BATTERY_BINDINGS,
        model,
    )
    assert model.calls == 1
    assert output.a2ui.count('"call":"clickToDeeplink"') == 2
    assert model.body is not None
    assert model.body.index('"event.open.weather"') < model.body.index(
        '"event.open.settings.battery"'
    )


@pytest.mark.asyncio
async def test_wide_full_embedded_action_uses_the_common_planner():
    fields = {
        "earphoneName": _field("我的耳机"),
        "isConnected": _field(True, "boolean"),
        "batteryLevel": _field(60, "integer"),
        "chargingStatusDesc": _field("未充电"),
        "leftBatteryLevel": _field(70, "integer"),
        "leftChargingStatusDesc": _field("未充电"),
        "rightBatteryLevel": _field(80, "integer"),
        "rightChargingStatusDesc": _field("未充电"),
    }
    paths = tuple("/" + field for field in fields)
    task = TaskSpec(
        userQuery="查看耳机电量和充电状态，并提供每日歌单入口",
        size="2x4",
        dataModelSchema={"data": {"earphone": fields}},
        eventCandidates=[
            EventAction(
                id="event.open.music.daily",
                call="clickToDeeplink",
                args={"uri": "music:daily"},
            )
        ],
    )
    bindings = (
        CandidateDataBinding(
            capabilityId="GetEarphoneInfo",
            writeResultTo="/data/earphone",
            candidateOutputFields=list(paths),
        ),
    )
    card = {
        "title": "耳机",
        "suggestSize": "2x4",
        "dataBindings": [{"capabilityId": "GetEarphoneInfo", "writeResultTo": "/data/earphone"}],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": paths},
        action=("event.open.music.daily",),
    )
    plans = _plans(task, bindings, card, intent)
    assert plans[0].layout_template_id == "WideFullOnlyLayout@1"
    assert plans[0].action_assignments[0].consumer == "business-template"
    model = _PlanModel(intent, actions=action_bindings(task))
    output = await generate_template_a2ui(task, card, bindings, model)
    assert model.calls == 1
    assert output.a2ui.count('"call":"clickToDeeplink"') == 1
