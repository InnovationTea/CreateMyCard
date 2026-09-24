"""仓电量场景的提示词作用域、动作需求和完整模板链路回归。

仓电量 Hero 的动作依赖与渲染产物已固化为场景金样（Layer C）：
``earphone__case_intent`` 冻结「无动作时检索必失败」（TemplateRetrievalMiss
的报错类型 + 消息）、补上动作后的 EarphoneCaseHero 选择，以及完整渲染里
出现/不出现的 ``/data/earphone`` 数据路径集（含单仓场景不渲染左右耳字段）。
模型只被调用一次的交互契约保留为普通测试。

检索提示词的内容契约（自检句只出现在 2x2 单业务、负面示例与动作候选透传）
属于提示词字节契约，门禁 Layer B 重放有效性，保留为普通测试。引擎或模板
改动后按 golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
"""

import asyncio
import json
import re
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
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

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


def _earphone_paths(a2ui: str) -> list[str]:
    return sorted(set(re.findall(r"/data/earphone/[A-Za-z]+", a2ui)))


async def _run_case_intent(extra_earbuds: bool) -> dict[str, Any]:
    task = _task(extra_earbuds)
    bindings = (_binding(task),)
    registry = get_cardplan_registry()
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _CASE_FIELDS}, action=[]
    )
    search = search_template_variants(intent, task, registry, bindings, _card())
    try:
        plan_template_candidates(intent, search, task, registry)
        miss: dict[str, Any] = {"error": "NO_ERROR"}
    except Exception as exc:  # noqa: BLE001 - 报错类型 + 消息整体冻结
        miss = {"errorType": type(exc).__name__, "message": str(exc)}
    selected = intent.model_copy(update={"action_ids": (_ACTION,)})
    plans = plan_template_candidates(selected, search, task, registry)
    assert plans
    model = _CaseModel()
    output = await generate_template_a2ui(task, _card(), bindings, model)
    return {
        "retrievalMissWithoutAction": miss,
        "templateId": plans[0].business_slots[0].template_id,
        "templateIds": sorted(output.template_ids),
        "dataPaths": _earphone_paths(output.a2ui),
    }


@scenario("earphone__case_intent")
def _build_case_intent() -> dict:
    return {
        "single_earphone": asyncio.run(_run_case_intent(False)),
        "with_earbud_pair_fields": asyncio.run(_run_case_intent(True)),
    }


def test_earphone_case_intent_scenario() -> None:
    assert_golden_scenario("earphone__case_intent")


@pytest.mark.asyncio
async def test_case_model_body_called_once() -> None:
    model = _CaseModel()
    await generate_template_a2ui(_task(False), _card(), (_binding(_task(False)),), model)
    assert model.body_calls == 1


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
