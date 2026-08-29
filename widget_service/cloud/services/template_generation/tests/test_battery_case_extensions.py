"""设备电量 6/8：候选入口与仅缺口可用的文本等级变体。

健康入口窄兜底矩阵、文本等级变体的候选范围、Full 候选稳定性与全部检索
拒绝路径（变体禁用、缺字段、字段类型不符、混合业务、受信模板限制）已
固化为 ``{输入键: 结果}`` 分组矩阵场景金样（Layer C）；三类 Hero（健康/
等级/充电）× 融合球开关共 6 份完整 A2UI + 投影事件渲染快照，构建函数内
同时运行生产字号校验器（validate_compact_dsl），该校验覆盖随快照保留。

旧 LLM 路由不接收新变体的断言依赖 monkeypatch 管线内部函数（检查 legacy
候选范围后主动中断流程），保留为普通测试。
"""

from __future__ import annotations

import asyncio
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
from services.template_generation.test_support.golden_scenarios import (
    a2ui_messages,
    assert_golden_scenario,
    scenario,
)
from services.template_generation.tests.test_battery_action_policy import (
    _ARGS,
    _CAPABILITY,
    _HEALTH,
    _SETTINGS,
    _ScriptedModel,
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


def _capture_miss(build: Any) -> dict[str, str]:
    """运行检索并把 TemplateRetrievalMiss 固化为 errorType + message。"""
    try:
        build()
    except TemplateRetrievalMiss as exc:
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"errorType": "NO_ERROR"}


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


_HEALTH_ENTRY_REASONS = (
    "health-only", "settings-first", "settings-invalid", "settings-duplicate",
    "health-duplicate", "health-invalid", "health-missing", "not-requested", "forbidden",
)


@scenario("battery_caseext__health_entry_matrix")
def _build_health_entry_matrix() -> dict[str, Any]:
    registry = CardPlanRegistry()  # 场景构建函数不取 pytest fixture，需本地构建
    payload: dict[str, Any] = {}
    for reason in _HEALTH_ENTRY_REASONS:
        fields = _HEALTH_FIELDS if reason != "not-requested" else ("/batterySOCText",)
        case = _case(fields)
        events = [_health_event()]
        if reason == "settings-first":
            events += case.task.eventCandidates
        elif reason == "settings-invalid":
            events += [case.task.eventCandidates[0].model_copy(update={"args": {}})]
        elif reason == "settings-duplicate":
            events += case.task.eventCandidates * 2
        elif reason == "health-duplicate":
            events *= 2
        elif reason == "health-invalid":
            events = [_health_event().model_copy(update={"args": _ARGS})]
        elif reason == "health-missing":
            events = []
        intent = case.intent
        if reason == "forbidden":
            intent = intent.model_copy(update={"allow_battery_settings_fallback": False})
        task = case.task.model_copy(update={"eventCandidates": events})
        resolved = resolve_battery_settings_fallback(intent, _search(case, registry), task)
        payload[reason] = {
            "actionIds": list(resolved.action_ids),
            "requiredOutputFields": {
                capability: list(values)
                for capability, values in resolved.required_output_fields_by_capability.items()
            },
        }
    return payload


@scenario("battery_caseext__level_variant_scope")
def _build_level_variant_scope() -> dict[str, Any]:
    registry = CardPlanRegistry()
    combos: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("text-only", ("/batterySOCText",)),
        ("level-only", ("/batteryCapacityLevelDesc",)),
        ("text-level-charging", (*_LEVEL_FIELDS, "/chargingStatusDesc")),
    )
    payload: dict[str, Any] = {}
    for key, fields in combos:
        case = _case(fields, with_full=True)
        result = _search(case, registry)
        payload[key] = sorted(c.template_id for c in result.business_candidates[0].candidates)
    return payload


@scenario("battery_caseext__full_candidates_stable")
def _build_full_candidates_stable() -> dict[str, Any]:
    case = _case(_LEVEL_FIELDS, with_full=True)
    previous = CardPlanRegistry(disabled_template_ids=(_FALLBACK_TEMPLATE,))
    with_variant = _search(case, CardPlanRegistry())
    without_variant = _search(case, previous)
    return {
        "withVariant": sorted(
            c.template_id for c in with_variant.business_candidates[0].candidates
        ),
        "withoutVariant": sorted(
            c.template_id for c in without_variant.business_candidates[0].candidates
        ),
        "identical": with_variant == without_variant,
    }


@scenario("battery_caseext__retrieval_miss_errors")
def _build_retrieval_miss_errors() -> dict[str, Any]:
    registry = CardPlanRegistry()
    payload: dict[str, Any] = {}
    for reason in ("variant-disabled", "missing-level", "missing-text", "wrong-type"):
        case = _case(_LEVEL_FIELDS)
        scoped_registry: CardPlanRegistry = registry
        if reason == "variant-disabled":
            scoped_registry = CardPlanRegistry(disabled_template_ids=(_FALLBACK_TEMPLATE,))
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
        payload[reason] = _capture_miss(lambda case=case, scoped=scoped_registry: _search(case, scoped))

    level_case = _case(_LEVEL_FIELDS)
    mixed_intent = level_case.intent.model_copy(update={"required_output_fields_by_capability": {
        _CAPABILITY: _LEVEL_FIELDS, "GetCalendarEvents": (),
    }})
    calendar_binding = level_case.binding.model_copy(update={
        "capabilityId": "GetCalendarEvents", "writeResultTo": "/data/calendar",
    })
    payload["mixed-business"] = _capture_miss(lambda: search_template_variants(
        mixed_intent, level_case.task, registry,
        (level_case.binding, calendar_binding), level_case.card,
    ))
    payload["trusted-restriction"] = _capture_miss(lambda: search_template_variants(
        level_case.intent, level_case.task, registry, (level_case.binding,), level_case.card,
        preferred_template_ids=("BatteryOverviewChargingProgressHero@1",),
    ))
    return payload


_RENDER_KINDS = ("health", "level", "charging")


async def _render_case_extension(kind: str, fusion: bool) -> dict[str, Any]:
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
    output = await pipeline.generate_template_a2ui(
        task, case.card, (case.binding,), _ScriptedModel(case.intent, body),
        enable_fusion_ball=fusion,
    )
    validate_compact_dsl(
        convert_a2ui_to_compact_dsl(output.a2ui, size="2x2"),
        # Production validates against the original TaskSpec, without internal selectors.
        task_spec=task.model_dump(mode="json"),
        card_spec=case.card,
    )
    return {
        **a2ui_messages(output),
        "projectedEvents": [
            {"id": event.id, "call": event.call, "args": event.args}
            for event in output.projected_task_spec.eventCandidates
        ],
        "requiredOutputFields": {
            capability: list(values)
            for capability, values in case.intent.required_output_fields_by_capability.items()
        },
    }


def _register_case_extension_renders() -> None:
    for kind in _RENDER_KINDS:
        for fusion_slug, fusion in (("plain", False), ("fusion", True)):
            def _build(kind: str = kind, fusion: bool = fusion) -> dict[str, Any]:
                return asyncio.run(_render_case_extension(kind, fusion))

            scenario(f"battery_caseext__render_{kind}__{fusion_slug}")(_build)


_register_case_extension_renders()


_BATTERY_CASEEXT_SCENARIO_IDS = (
    "battery_caseext__health_entry_matrix",
    "battery_caseext__level_variant_scope",
    "battery_caseext__full_candidates_stable",
    "battery_caseext__retrieval_miss_errors",
    "battery_caseext__render_health__plain",
    "battery_caseext__render_health__fusion",
    "battery_caseext__render_level__plain",
    "battery_caseext__render_level__fusion",
    "battery_caseext__render_charging__plain",
    "battery_caseext__render_charging__fusion",
)


def test_battery_case_extension_scenarios_match_goldens() -> None:
    for scenario_id in _BATTERY_CASEEXT_SCENARIO_IDS:
        assert_golden_scenario(scenario_id)


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
