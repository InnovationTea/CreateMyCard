"""现有连接状态模板的充电状态必须整行展示。

{mask}×{header}×主题（普通 / 融球）组合与分割线渲染的完整 A2UI 产物已固化为
场景金样（Layer C）：``earbud__pair_full_charging__mask{0..7}__{header}__{plain|fusion}``
（header ∈ both/name/connected/none；none = 头部字段全缺，必须路由失败，冻结
TemplateRouteNotApplicable 的报错类型 + 消息）以及
``earbud__divider__charging{on|off}__{plain|fusion}``。快照整体冻结电量列几何
（高 34/50、alignItems、百分比字号字重字色）、充电状态整行样式（宽 36、字号 10、
字色 #99FFFFFF 等）、头部字段显隐与融球/非融球主题差异。引擎或模板改动后按
golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
"""

import asyncio

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.pipeline import (
    TemplateRouteNotApplicable,
    generate_template_a2ui,
)
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
_HEADERS = ("both", "name", "connected", "none")
_THEMES: tuple[tuple[str, bool], ...] = (("plain", False), ("fusion", True))

_FULL_CHARGING_SCENARIO_IDS = tuple(
    f"earbud__pair_full_charging__mask{mask}__{header}__{theme_slug}"
    for mask in range(8)
    for header in _HEADERS
    for theme_slug, _ in _THEMES
)

_DIVIDER_SCENARIO_IDS = tuple(
    f"earbud__divider__charging{'on' if charging else 'off'}__{theme_slug}"
    for charging in (False, True)
    for theme_slug, _ in _THEMES
)


async def _render_pair_full_charging(mask: int, fusion: bool, header: str) -> dict:
    fields = {
        "earphoneName": _provider_field("测试耳机", "string"),
        "isConnected": _provider_field(False, "boolean"),
        "batteryLevel": _provider_field(0, "integer"),
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    if header in {"name", "none"}:
        fields.pop("isConnected")
    if header in {"connected", "none"}:
        fields.pop("earphoneName")
    for index, field in enumerate(_CHARGE_FIELDS):
        if mask & (1 << index):
            fields[field] = _provider_field("未充电", "string")
    task = _bluetooth_task("查看耳机名称、连接状态及电量").model_copy(
        update={"dataModelSchema": {"data": {"earphone": fields}}, "eventCandidates": []},
    )
    required = ["/earphoneName", "/isConnected", "/leftBatteryLevel", "/rightBatteryLevel"]
    if header in {"name", "none"}:
        required.remove("/isConnected")
    if header in {"connected", "none"}:
        required.remove("/earphoneName")
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
    if header == "none":
        try:
            await generate_template_a2ui(
                task, _bluetooth_card_spec(), (binding,), model, enable_fusion_ball=fusion,
                trusted_template_candidate_ids=(template_id,),
            )
        except TemplateRouteNotApplicable as exc:
            return {"errorType": type(exc).__name__, "message": str(exc)}
        raise AssertionError("header=none 必须路由失败（TemplateRouteNotApplicable）")
    result = await generate_template_a2ui(
        task, _bluetooth_card_spec(), (binding,), model, enable_fusion_ball=fusion,
    )
    return a2ui_messages(result)


def _register_pair_full_charging_scenarios() -> None:
    for mask in range(8):
        for header in _HEADERS:
            for theme_slug, fusion in _THEMES:
                def _build(
                    mask: int = mask, fusion: bool = fusion, header: str = header,
                ) -> dict:
                    return asyncio.run(_render_pair_full_charging(mask, fusion, header))

                scenario(
                    f"earbud__pair_full_charging__mask{mask}__{header}__{theme_slug}"
                )(_build)


_register_pair_full_charging_scenarios()


async def _render_pair_divider(fusion: bool, charging: bool) -> dict:
    fields = {
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    if charging:
        fields["leftChargingStatusDesc"] = _provider_field("未充电", "string")
        fields["rightChargingStatusDesc"] = _provider_field("充电中", "string")
    task = _bluetooth_task("显示左右耳机剩余电量").model_copy(
        update={"dataModelSchema": {"data": {"earphone": fields}}, "eventCandidates": []},
    )
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal" if fusion else "audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=("BluetoothDeviceOverviewEarbudsFull@1",),
        capability_id="GetEarphoneInfo",
        required_fields=tuple(f"/{field}" for field in fields),
        body='Template("SingleFocusLayout@1",{},'
        'Template("BluetoothDeviceOverviewEarbudsFull@1",{}));',
    )
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo", writeResultTo="/data/earphone",
        candidateOutputFields=[f"/{field}" for field in fields],
    )
    output = await generate_template_a2ui(
        task, _bluetooth_card_spec(), (binding,), model, enable_fusion_ball=fusion,
    )
    return a2ui_messages(output)


def _register_divider_scenarios() -> None:
    for charging in (False, True):
        for theme_slug, fusion in _THEMES:
            def _build(fusion: bool = fusion, charging: bool = charging) -> dict:
                return asyncio.run(_render_pair_divider(fusion, charging))

            scenario(
                f"earbud__divider__charging{'on' if charging else 'off'}__{theme_slug}"
            )(_build)


_register_divider_scenarios()


@pytest.mark.parametrize("scenario_id", _FULL_CHARGING_SCENARIO_IDS)
def test_full_charging_row_requires_all_three_fields(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)


@pytest.mark.parametrize("scenario_id", _DIVIDER_SCENARIO_IDS)
def test_earbuds_divider(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
