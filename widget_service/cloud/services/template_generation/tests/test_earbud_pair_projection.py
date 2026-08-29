"""耳机名称和左右耳电量从模板检索到数据投影的回归。

检索选择、事实投影与完整渲染产物已固化为场景金样（Layer C）：
- ``earbud__pair_hero_projection``：三组电量取值下的 EarbudPairHero 选择、
  投影字段（类型 + 样本值）、task 数据模型不被改写与 A2UI 中的数据路径集；
- ``earbud__pair_hero_validation``：缺必需字段与旧 Hero 缺连接状态的
  TerselConversionError 报错类型 + 消息；
- ``earbud__facts_extraction_rejections``：非法/缺失/跨实体电量在
  ``extract_bluetooth_device_overview_facts`` 下的拒绝矩阵（含合法对照）。

模型只被调用一次的交互契约保留为普通测试（不进快照）。引擎或模板改动后
按 golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
"""

import asyncio
import re
from dataclasses import asdict
from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.content_selectors import (
    extract_bluetooth_device_overview_facts,
    project_content_component_facts,
)
from services.template_generation.engine.cardplan.compiler import _validate_provider_template_state
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)


class _EarbudPairModel:
    def __init__(self) -> None:
        self.body_calls = 0

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "requiredOutputFieldsByCapability": {
                "GetEarphoneInfo": ["/earphoneName", "/leftBatteryLevel", "/rightBatteryLevel"]
            },
            "action": ["event.open.settings.bluetooth"],
        }

    async def generate(self, *_args: Any, **_kwargs: Any) -> str:
        self.body_calls += 1
        return (
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbudPairHero@1",{}),'
            'Template("PillAction@1",'
            '{"actionId":"event.open.settings.bluetooth","label":"蓝牙设置"}));'
        )


def _fields(left: Any = 76, right: Any = 78) -> dict[str, Any]:
    return {
        "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
        "leftBatteryLevel": {"type": "integer", "sampleValue": left},
        "rightBatteryLevel": {"type": "integer", "sampleValue": right},
    }


def _pair_task(fields: dict[str, Any]) -> TaskSpec:
    return TaskSpec(
        userQuery="显示耳机名称和左右耳机的剩余电量",
        size="2x2",
        dataModelSchema={"data": {"earphone": fields}},
        eventCandidates=[
            EventAction(
                id="event.open.settings.bluetooth",
                call="clickToDeeplink",
                args={"intentName": "Settings", "uri": "bluetooth_entry"},
            )
        ],
    )


_PATHS = ["/earphoneName", "/leftBatteryLevel", "/rightBatteryLevel"]


def _bindings(fields: dict[str, Any]) -> tuple[CandidateDataBinding, ...]:
    return (
        CandidateDataBinding(
            capabilityId="GetEarphoneInfo",
            writeResultTo="/data/earphone",
            candidateOutputFields=["/" + name for name in fields],
        ),
    )


_CARD = {
    "suggestSize": "2x2",
    "dataBindings": [{"capabilityId": "GetEarphoneInfo", "writeResultTo": "/data/earphone"}],
}


def _earphone_paths(a2ui: str) -> list[str]:
    return sorted(set(re.findall(r"/data/earphone/[A-Za-z]+", a2ui)))


async def _run_pair_hero(
    left: int, right: int,
) -> tuple[TaskSpec, dict[str, Any], Any, _EarbudPairModel]:
    fields = _fields(left, right)
    task = _pair_task(fields)
    bindings = _bindings(fields)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": _PATHS},
        action=["event.open.settings.bluetooth"],
    )
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, bindings, _CARD)
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    projected = project_content_component_facts(
        task, {"GetEarphoneInfo"}, ("BluetoothDeviceOverview",)
    )
    data = projected.dataModelSchema.get("data")
    assert isinstance(data, dict)
    selected = data.get("BluetoothDeviceOverview")
    assert isinstance(selected, dict)
    model = _EarbudPairModel()
    output = await generate_template_a2ui(task, _CARD, bindings, model)
    payload = {
        "templateId": plans[0].business_slots[0].template_id,
        "projectedFields": selected,
        "taskSchemaUnchanged": task.dataModelSchema == {"data": {"earphone": fields}},
        "dataPaths": _earphone_paths(output.a2ui),
        "templateIds": sorted(output.template_ids),
    }
    return task, fields, payload, model


@scenario("earbud__pair_hero_projection")
def _build_pair_hero_projection() -> dict:
    cases: dict[str, dict[str, Any]] = {}
    for left, right in ((76, 78), (0, 100), (100, 0)):
        _, _, payload, _ = asyncio.run(_run_pair_hero(left, right))
        cases[f"{left}x{right}"] = payload
    return {"batteries": cases}


def _validation_error(template_id: str, task: TaskSpec) -> dict[str, Any]:
    try:
        _validate_provider_template_state(
            template_id, "default", task, business_names={"BluetoothDeviceOverview"},
        )
    except Exception as exc:  # noqa: BLE001 - 报错类型 + 消息整体冻结
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


@scenario("earbud__pair_hero_validation")
def _build_pair_hero_validation() -> dict:
    payload: dict[str, dict[str, Any]] = {}
    for missing in ("earphoneName", "leftBatteryLevel", "rightBatteryLevel"):
        fields = _fields()
        fields.pop(missing)
        fields["isConnected"] = {"type": "boolean", "sampleValue": True}
        payload[f"missing_{missing}"] = _validation_error(
            "BluetoothDeviceOverviewEarbudPairHero@1", _pair_task(fields),
        )
    payload["legacy_hero_requires_connection"] = _validation_error(
        "BluetoothDeviceOverviewHero@1", _pair_task(_fields()),
    )
    return payload


def _facts_or_none(fields: dict[str, Any]) -> Any:
    facts = extract_bluetooth_device_overview_facts({"data": {"earphone": fields}})
    return None if facts is None else asdict(facts)


_INVALID_VALUES: tuple[tuple[Any, str], ...] = (
    (None, "null"), (True, "true"), ("76", "str76"), (-1, "neg1"), (101, "101"),
)


@scenario("earbud__facts_extraction_rejections")
def _build_facts_extraction_rejections() -> dict:
    payload: dict[str, Any] = {"valid_pair": _facts_or_none(_fields())}
    for side in ("leftBatteryLevel", "rightBatteryLevel"):
        for invalid, slug in _INVALID_VALUES:
            fields = _fields()
            fields[side] = {"type": "integer", "sampleValue": invalid}
            payload[f"{side}_{slug}"] = _facts_or_none(fields)
    for missing in ("leftBatteryLevel", "rightBatteryLevel"):
        fields = _fields()
        fields.pop(missing)
        payload[f"missing_{missing}"] = _facts_or_none(fields)
    first = _fields()
    first.pop("rightBatteryLevel")
    second = _fields()
    second.pop("leftBatteryLevel")
    payload["split_entities"] = _facts_or_none({"data": {"first": first, "second": second}})
    return payload


def test_earbud_pair_projection_scenarios() -> None:
    assert_golden_scenario("earbud__pair_hero_projection")
    assert_golden_scenario("earbud__pair_hero_validation")
    assert_golden_scenario("earbud__facts_extraction_rejections")


@pytest.mark.asyncio
async def test_pair_hero_body_model_called_once() -> None:
    _, _, _, model = await _run_pair_hero(76, 78)
    assert model.body_calls == 1
