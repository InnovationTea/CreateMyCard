"""仓电量场景的提示词作用域、动作需求和完整模板链路回归。"""

import json
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
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
from services.template_generation.engine.pipeline import generate_template_a2ui

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
    assert "明确说不要按钮或不要跳转" in system
    assert "缺候选或模板不可用时不能照抄正例" in system
    payload = json.loads(content)
    actions = payload.get("actionCandidates")
    assert isinstance(actions, list)
    assert bool(actions) == has_action
