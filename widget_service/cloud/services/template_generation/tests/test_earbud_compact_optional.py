"""Compact 可选字段的缺失、零电量和未连接回归。

九种连接状态 × 电量组合的完整 A2UI 产物已固化为场景金样（Layer C）：
``earbud__compact_optional__conn_{absent|false|true}__batt_{absent|0|80}``，
快照整体冻结 ``isConnected`` / ``batteryLevel`` 的可选语义（未连接文案、
电量行的 itemMargin 与子项数、标题行的字号字重、点击态背景色等）。
引擎或模板改动后按 golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
"""

import asyncio

import pytest

from models.generation import CandidateDataBinding, EventAction
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

_CONNECTED: tuple[tuple[str, bool | None], ...] = (
    ("absent", None), ("false", False), ("true", True),
)
_BATTERY: tuple[tuple[str, int | None], ...] = (("absent", None), ("0", 0), ("80", 80))

_COMPACT_SCENARIO_IDS = tuple(
    f"earbud__compact_optional__conn_{conn_slug}__batt_{batt_slug}"
    for conn_slug, _ in _CONNECTED
    for batt_slug, _ in _BATTERY
)


async def _render_compact_optional(connected: bool | None, battery: int | None) -> dict:
    fields = {
        "earphoneName": _provider_field("测试耳机", "string"),
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    if connected is not None:
        fields["isConnected"] = _provider_field(connected, "boolean")
    if battery is not None:
        fields["batteryLevel"] = _provider_field(battery, "integer")
    events = []
    for action_id in ("event.open.music.daily", "event.open.music.favorite"):
        events.append(
            EventAction(id=action_id, call="clickToIntent", args={"intentName": action_id})
        )
    task = _bluetooth_task("耳机状态，每日推荐和心动歌单").model_copy(update={
        "dataModelSchema": {"data": {"earphone": fields}},
        "eventCandidates": events,
    })
    paths = tuple(f"/{name}" for name in fields)
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo", writeResultTo="/data/earphone",
        candidateOutputFields=list(paths),
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=("BluetoothDeviceOverviewEarbudPairCompact@1",),
        capability_id="GetEarphoneInfo", required_fields=paths,
        action_id=("event.open.music.daily", "event.open.music.favorite"),
        body=(
            'Template("CompactTwoActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbudPairCompact@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.music.daily","label":"每日推荐"}),'
            'Template("PillAction@1",{"actionId":"event.open.music.favorite","label":"心动歌单"}));'
        ),
    )
    result = await generate_template_a2ui(task, _bluetooth_card_spec(), (binding,), model)
    return a2ui_messages(result)


def _register_compact_optional_scenarios() -> None:
    for conn_slug, connected in _CONNECTED:
        for batt_slug, battery in _BATTERY:
            def _build(connected: bool | None = connected, battery: int | None = battery) -> dict:
                return asyncio.run(_render_compact_optional(connected, battery))

            scenario(
                f"earbud__compact_optional__conn_{conn_slug}__batt_{batt_slug}"
            )(_build)


_register_compact_optional_scenarios()


@pytest.mark.parametrize("scenario_id", _COMPACT_SCENARIO_IDS)
def test_compact_optional_fields(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
