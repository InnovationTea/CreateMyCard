"""电量默认设置入口的正向链路、输入保真及跨业务隔离。

确定性选择矩阵与渲染产物已固化为场景金样（Layer C）：hero 兜底字段矩阵、
Full 优先、设置目标校验、事件候选隔离、作用域隔离、Compact/Support 候选、
文本等级兜底、开关严格性各固化一份 ``{输入键: 结果}`` 分组矩阵；二层渲染
（Full/Hero × 融合球）、无按钮未授权 miss、显式/图库动作保留按组合各固化
完整 A2UI + 投影事件。引擎或模板改动后按 golden 工作流 ``check --diff`` /
``bless --declared`` 复核。

检索 prompt 的字节级内容契约（其他业务与混合业务的提示词不出现电池兜底
话术；电池提示词只贴标签不扩权、schema 默认 false）保持内联断言——它们
约束 Layer B 录制语料的提示词字节，不得移入快照。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from models.generation import CandidateDataBinding, EventAction, TaskSpec
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
from services.template_generation.test_support.golden_scenarios import (
    a2ui_messages,
    assert_golden_scenario,
    scenario,
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


def _fields_key(fields: tuple[str, ...]) -> str:
    return "+".join(field.removeprefix("/") for field in fields)


def _plan_summary(plans: Any) -> list[dict[str, Any]]:
    return [
        {
            "layoutTemplateId": plan.layout_template_id,
            "businessTemplateIds": [slot.template_id for slot in plan.business_slots],
            "actionIds": [assignment.action_id for assignment in plan.action_assignments],
        }
        for plan in plans
    ]


def _projected_events(output: Any) -> list[dict[str, Any]]:
    return [
        {"id": event.id, "call": event.call, "args": event.args}
        for event in output.projected_task_spec.eventCandidates
    ]


class _ScriptedModel:
    """检索阶段返回固定意图、二层阶段返回固定模板组合的桩模型。"""

    def __init__(self, intent: TemplateSearchIntent, body: str) -> None:
        self._intent = intent.model_dump(mode="json", by_alias=True)
        self._body = body

    async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
        assert phase == "template-retrieval-query"
        return self._intent

    async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
        return self._body


_HERO_BODY = (
    'Template("HeroActionLayout@1",{},'
    'Template("BatteryOverviewChargingProgressHero@1",{}),'
    'Template("PillAction@1",{"actionId":"event.open.settings.battery",'
    '"label":"电池设置"}));'
)
_FULL_BODY = (
    'Template("SingleFocusLayout@1",{},'
    'Template("BatteryOverviewFull@1",{}));'
)
_HEALTH_BODY = (
    'Template("HeroActionLayout@1",{},'
    'Template("BatteryOverviewChargingProgressHero@1",{}),'
    'Template("PillAction@1",{"actionId":"event.open.settings.batteryHealth",'
    '"label":"电池健康"}));'
)


async def _render_battery(case: BatteryCase, body: str, *, fusion: bool) -> dict[str, Any]:
    output = await pipeline.generate_template_a2ui(
        case.task, case.card, (case.binding,), _ScriptedModel(case.intent, body),
        enable_fusion_ball=fusion,
    )
    return {**a2ui_messages(output), "projectedEvents": _projected_events(output)}


_HERO_FIELD_CASES: tuple[tuple[str, ...], ...] = (
    ("/batterySOCText",),
    _TEXT_FIELDS,
    (*_TEXT_FIELDS, "/healthStatusDesc"),
    ("/healthStatusDesc", "/batteryCapacityLevelDesc"),
    ("/nowCurrentText", "/voltageText", "/batteryCapacityLevelDesc", "/isBatteryPresentText"),
)


@scenario("battery_action__hero_fallback_matrix")
def _build_hero_fallback_matrix() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    registry = CardPlanRegistry()
    for fields in _HERO_FIELD_CASES:
        case = _case(fields)
        original_task = case.task.model_dump()
        original_binding = case.binding.model_dump()
        result = _search(case, registry)
        resolved = resolve_battery_settings_fallback(case.intent, result, case.task)
        payload[_fields_key(fields)] = {
            "originalIntent": case.intent.model_dump(mode="json", by_alias=True),
            "resolvedIntent": resolved.model_dump(mode="json", by_alias=True),
            "taskUnchanged": case.task.model_dump() == original_task,
            "bindingUnchanged": case.binding.model_dump() == original_binding,
            "idempotent": (
                resolve_battery_settings_fallback(resolved, result, case.task) is resolved
            ),
            "plans": _plan_summary(plan_template_candidates(resolved, result, case.task, registry)),
        }
    return payload


@scenario("battery_action__full_wins_no_fallback")
def _build_full_wins_no_fallback() -> dict[str, Any]:
    case = _case(with_full=True)
    registry = CardPlanRegistry()
    result = _search(case, registry)
    return {
        "candidates": sorted(c.template_id for c in result.business_candidates[0].candidates),
        "fallbackApplied": (
            resolve_battery_settings_fallback(case.intent, result, case.task) is not case.intent
        ),
        "plans": _plan_summary(plan_template_candidates(case.intent, result, case.task, registry)),
    }


@scenario("battery_action__settings_target_mismatch")
def _build_settings_target_mismatch() -> dict[str, Any]:
    case = _case()
    result = _search(case, CardPlanRegistry())
    variants: tuple[tuple[str, str | None], ...] = (
        ("uri-health", "smart_charge_battery_health"),
        ("uri-absent", None),
        ("uri-expression", "{{ ${/data/phoneBattery/uri} }}"),
        ("extra-unexpected", "unexpected"),
        ("intentName-other", "Other"),
        ("bundleName-other", "other.app"),
        ("abilityName-other", "OtherAbility"),
    )
    payload: dict[str, Any] = {}
    for name, override in variants:
        args = dict(_ARGS)
        if override is None:
            args.pop("uri")
        else:
            args["uri" if name.startswith("uri-") else name.split("-", 1)[0]] = override
        event = case.task.eventCandidates[0].model_copy(update={"args": args})
        task = case.task.model_copy(update={"eventCandidates": [event]})
        resolved = resolve_battery_settings_fallback(case.intent, result, task)
        payload[name] = {"actionIds": list(resolved.action_ids)}
    return payload


@scenario("battery_action__fallback_event_isolation")
def _build_fallback_event_isolation() -> dict[str, Any]:
    case = _case()
    result = _search(case, CardPlanRegistry())
    base = case.task.eventCandidates[0]
    variants: dict[str, list[EventAction]] = {
        "missing": [],
        "duplicate": [base, base],
        "health-only": [base.model_copy(update={
            "id": _HEALTH, "args": {**_ARGS, "uri": "smart_charge_battery_health"},
        })],
        "wrong-call": [base.model_copy(update={"call": "clickToIntent"})],
    }
    return {
        reason: {"actionIds": list(resolve_battery_settings_fallback(
            case.intent, result, case.task.model_copy(update={"eventCandidates": events}),
        ).action_ids)}
        for reason, events in variants.items()
    }


_ISOLATION_REASONS = (
    "forbidden", "explicit-action", "two-actions", "wide", "size-mismatch",
    "calendar", "earphone", "weather", "mixed", "multiple-groups", "wrong-business",
    "wrong-capability",
)


@scenario("battery_action__fallback_scope_isolation")
def _build_fallback_scope_isolation() -> dict[str, Any]:
    case = _case()
    registry = CardPlanRegistry()
    payload: dict[str, Any] = {}
    for reason in _ISOLATION_REASONS:
        intent, task = case.intent, case.task
        result = _search(case, registry)
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
            fields: dict[str, tuple[str, ...]] = {capability: ()}
            if reason == "mixed":
                fields.update(intent.required_output_fields_by_capability)
            intent = intent.model_copy(update={"required_output_fields_by_capability": fields})
        resolved = resolve_battery_settings_fallback(intent, result, task)
        payload[reason] = {"actionIds": list(resolved.action_ids)}
    return payload


@scenario("battery_action__compact_support_candidates")
def _build_compact_support_candidates() -> dict[str, Any]:
    case = _case(("/batterySOC", "/chargingStatusDesc"))
    registry = CardPlanRegistry(disabled_template_ids=("BatteryOverviewChargingRingHero@1",))
    result = _search(case, registry)
    return {
        "candidates": sorted(c.template_id for c in result.business_candidates[0].candidates),
        "actionIds": list(
            resolve_battery_settings_fallback(case.intent, result, case.task).action_ids
        ),
    }


@scenario("battery_action__text_level_fallback")
def _build_text_level_fallback() -> dict[str, Any]:
    case = _case(("/batterySOCText", "/batteryCapacityLevelDesc"))
    registry = CardPlanRegistry()
    result = _search(case, registry)
    data = case.task.dataModelSchema.get("data")
    assert isinstance(data, dict)
    battery = data.get("phoneBattery")
    assert isinstance(battery, dict)
    resolved = resolve_battery_settings_fallback(case.intent, result, case.task)
    return {
        "candidates": [c.template_id for c in result.business_candidates[0].candidates],
        "schemaBatteryFields": sorted(battery),
        "plans": _plan_summary(plan_template_candidates(resolved, result, case.task, registry)),
    }


@scenario("battery_action__flag_strictness")
def _build_flag_strictness() -> dict[str, Any]:
    old = TemplateSearchIntent(requiredOutputFieldsByCapability={_CAPABILITY: _TEXT_FIELDS})
    payload: dict[str, Any] = {"flagAbsentDefault": old.allow_battery_settings_fallback}
    for invalid in ("true", "false", 1, 0, None):
        try:
            TemplateSearchIntent(
                requiredOutputFieldsByCapability={_CAPABILITY: _TEXT_FIELDS},
                allowBatterySettingsFallback=invalid,
            )
        except ValidationError as exc:
            payload[json.dumps(invalid)] = {"errorType": type(exc).__name__, "message": str(exc)}
        else:  # pragma: no cover - 表中每个非法值都必须被拒绝
            payload[json.dumps(invalid)] = {"errorType": "NO_ERROR"}
    return payload


def _register_battery_renders() -> None:
    for body_slug, body, with_full in (
        ("hero", _HERO_BODY, False), ("full", _FULL_BODY, True),
    ):
        for fusion_slug, fusion in (("plain", False), ("fusion", True)):
            def _build(
                body: str = body, with_full: bool = with_full, fusion: bool = fusion,
            ) -> dict[str, Any]:
                return asyncio.run(_render_battery(_case(with_full=with_full), body, fusion=fusion))

            scenario(f"battery_action__render_{body_slug}__{fusion_slug}")(_build)


_register_battery_renders()


@scenario("battery_action__unauthorized_button_miss")
def _build_unauthorized_button_miss() -> dict[str, Any]:
    case = _case()
    task = case.task.model_copy(update={"userQuery": "显示电量和充电状态，不要按钮"})
    payload: dict[str, Any] = {}
    for name, flag in (("flagFalse", False), ("flagAbsent", None)):
        second_layer_calls: list[bool] = []

        class Model:
            async def generate_json(self, _prompt: Any, *, phase: str) -> dict[str, Any]:
                result: dict[str, Any] = {
                    "requiredOutputFieldsByCapability": {_CAPABILITY: list(_TEXT_FIELDS)},
                }
                if flag is not None:
                    result["allowBatterySettingsFallback"] = flag
                return result

            async def generate(self, _prompt: Any, *_args: Any, **_kwargs: Any) -> str:
                second_layer_calls.append(True)
                raise RuntimeError("二层不得在未授权时运行")

        try:
            asyncio.run(pipeline.generate_template_a2ui(task, case.card, (case.binding,), Model()))
        except TemplateRouteNotApplicable as exc:
            assert not second_layer_calls  # 未授权时不得进入 Hero 二层
            payload[name] = {"errorType": type(exc).__name__, "message": str(exc)}
        else:  # pragma: no cover - 未授权必须 miss
            payload[name] = {"errorType": "NO_ERROR"}
    return payload


def _register_preserve_renders() -> None:
    for source in ("explicit", "gallery"):
        for size in ("full", "hero"):
            def _build(source: str = source, size: str = size) -> dict[str, Any]:
                case = _case(with_full=(size == "full"))
                health = EventAction(
                    id=_HEALTH, call="clickToDeeplink",
                    args={**_ARGS, "uri": "smart_charge_battery_health"},
                )
                task = case.task.model_copy(
                    update={"eventCandidates": [*case.task.eventCandidates, health]},
                )
                intent = case.intent
                if source == "explicit":
                    intent = intent.model_copy(update={"action_ids": (_HEALTH,)})
                trusted_actions = (_HEALTH,) if source == "gallery" else ()
                output = asyncio.run(pipeline.generate_template_a2ui(
                    task, case.card, (case.binding,), _ScriptedModel(intent, _HEALTH_BODY),
                    trusted_template_action_ids=trusted_actions,
                ))
                return {**a2ui_messages(output), "projectedEvents": _projected_events(output)}

            scenario(f"battery_action__preserve_{source}__{size}")(_build)


_register_preserve_renders()


_BATTERY_ACTION_SCENARIO_IDS = (
    "battery_action__hero_fallback_matrix",
    "battery_action__full_wins_no_fallback",
    "battery_action__settings_target_mismatch",
    "battery_action__fallback_event_isolation",
    "battery_action__fallback_scope_isolation",
    "battery_action__compact_support_candidates",
    "battery_action__text_level_fallback",
    "battery_action__flag_strictness",
    "battery_action__render_hero__plain",
    "battery_action__render_hero__fusion",
    "battery_action__render_full__plain",
    "battery_action__render_full__fusion",
    "battery_action__unauthorized_button_miss",
    "battery_action__preserve_explicit__full",
    "battery_action__preserve_explicit__hero",
    "battery_action__preserve_gallery__full",
    "battery_action__preserve_gallery__hero",
)


def test_battery_action_scenarios_match_goldens() -> None:
    for scenario_id in _BATTERY_ACTION_SCENARIO_IDS:
        assert_golden_scenario(scenario_id)


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
