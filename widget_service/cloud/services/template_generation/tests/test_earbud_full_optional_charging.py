"""现有连接状态模板的充电状态必须整行展示。

16 种充电字段掩码 × 主题（普通 / 融球）组合的完整 A2UI 产物已固化为场景
金样（Layer C）：``earbud__pair_full_charging__mask{0..7}__{plain|fusion}``。
掩码位依次为 leftChargingStatusDesc、rightChargingStatusDesc、
chargingStatusDesc；快照整体冻结电量列几何（高 34/50、alignItems、百分比
字号字重字色）、充电状态整行样式（宽 36、字号 10、字色 #99FFFFFF 等）与
融球/非融球主题差异。引擎或模板改动后按 golden 工作流
``check --diff`` / ``bless --declared`` 复核。
"""

import asyncio

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.test_support.golden_scenarios import (
    a2ui_messages,
    assert_golden_scenario,
    scenario,
)
from services.template_generation.tests.test_template_generation import (
    _bluetooth_card_spec,
    _bluetooth_task,
    _FixedTemplateModel,
    _provider_field,
)

_CHARGE_FIELDS = ("leftChargingStatusDesc", "rightChargingStatusDesc", "chargingStatusDesc")
_THEMES: tuple[tuple[str, bool], ...] = (("plain", False), ("fusion", True))

_FULL_CHARGING_SCENARIO_IDS = tuple(
    f"earbud__pair_full_charging__mask{mask}__{theme_slug}"
    for mask in range(8)
    for theme_slug, _ in _THEMES
)


async def _render_pair_full_charging(mask: int, fusion: bool) -> dict:
    fields = {
        "earphoneName": _provider_field("测试耳机", "string"),
        "isConnected": _provider_field(False, "boolean"),
        "batteryLevel": _provider_field(0, "integer"),
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    for index, field in enumerate(_CHARGE_FIELDS):
        if mask & (1 << index):
            fields[field] = _provider_field("未充电", "string")
    task = _bluetooth_task("查看耳机名称、连接状态及电量").model_copy(
        update={"dataModelSchema": {"data": {"earphone": fields}}, "eventCandidates": []},
    )
    required = ["/earphoneName", "/isConnected", "/leftBatteryLevel", "/rightBatteryLevel"]
    if mask == 7:
        required.extend(f"/{field}" for field in _CHARGE_FIELDS)
    template_id = "BluetoothDeviceOverviewEarbudPairFull@1"
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal" if fusion else "audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=(template_id,),
        capability_id="GetEarphoneInfo",
        required_fields=tuple(required),
        body='Template("SingleFocusLayout@1",{},'
        'Template("BluetoothDeviceOverviewEarbudPairFull@1",{}));',
    )
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo", writeResultTo="/data/earphone",
        candidateOutputFields=[f"/{field}" for field in fields],
    )
    result = await generate_template_a2ui(
        task, _bluetooth_card_spec(), (binding,), model, enable_fusion_ball=fusion,
    )
    return a2ui_messages(result)


def _register_full_charging_scenarios() -> None:
    for mask in range(8):
        for theme_slug, fusion in _THEMES:
            def _build(mask: int = mask, fusion: bool = fusion) -> dict:
                return asyncio.run(_render_pair_full_charging(mask, fusion))

            scenario(f"earbud__pair_full_charging__mask{mask}__{theme_slug}")(_build)


_register_full_charging_scenarios()


@pytest.mark.parametrize("scenario_id", _FULL_CHARGING_SCENARIO_IDS)
def test_full_charging_row_requires_all_three_fields(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
