"""独立三电量模板不依赖连接状态，且保持动作和充电状态布局。

完整 A2UI 产物已固化为场景金样（Layer C）：无动作 Full 渲染（charge_mask=0）
与 Hero+PillAction 的 charge_mask{0..7} 各一份；充电状态列几何、主题色、
onClick 载荷与连接语义的缺省（isConnected/已连接 不得出现）都由快照整体冻结。
引擎或模板改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
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

_CHARGE_FIELDS = ("leftChargingStatusDesc", "rightChargingStatusDesc", "chargingStatusDesc")

_TRIPLE_SCENARIOS: tuple[tuple[str, bool, int], ...] = (
    ("earbud_triple__full_no_action__mask0", False, 0),
    *(
        (f"earbud_triple__hero_pill_action__mask{mask}", True, mask)
        for mask in range(8)
    ),
)


async def _render_triple_templates(with_action: bool, charge_mask: int = 0) -> dict:
    fields = {
        "earphoneName": _provider_field("测试耳机", "string"),
        "batteryLevel": _provider_field(80, "integer"),
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    for index, field in enumerate(_CHARGE_FIELDS):
        if charge_mask & (1 << index):
            fields[field] = _provider_field("未充电", "string")
    action_id = "event.open.music.favorite"
    events: list[EventAction] = []
    if with_action:
        events.append(
            EventAction(
                id=action_id,
                displayLabel="收藏歌单",
                call="clickToIntent",
                args={"intentName": action_id},
            )
        )
    task = _bluetooth_task("查看左耳、右耳和充电盒电量").model_copy(
        update={
            "dataModelSchema": {"data": {"earphone": fields}},
            "eventCandidates": events,
            "assetCandidates": [
                {
                    "src": "resources/base/media/icon_music.svg",
                    "description": "音乐、歌曲、歌单或音频内容。",
                    "sceneTags": ["action", "music"],
                }
            ],
        }
    )
    required_fields = ("/batteryLevel", "/leftBatteryLevel", "/rightBatteryLevel")
    body = (
        'Template("SingleFocusLayout@1",{},Template("BluetoothDeviceOverviewEarbudPairFull@1",{}));'
    )
    selected_action: str | None = None
    if with_action:
        selected_action = action_id
        body = (
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbudPairFull@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.music.favorite",'
            '"label":"心动歌单"}));'
        )
    template_id = "BluetoothDeviceOverviewEarbudPairFull@1"
    if with_action:
        template_id = "BluetoothDeviceOverviewEarbudTripleHero@1"
        body = body.replace("EarbudPairFull@1", "EarbudTripleHero@1")
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=(template_id,),
        capability_id="GetEarphoneInfo",
        required_fields=required_fields,
        action_id=selected_action,
        body=body,
    )
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=[f"/{name}" for name in fields],
    )
    result = await generate_template_a2ui(task, _bluetooth_card_spec(), (binding,), model)
    return a2ui_messages(result)


def _register_triple_scenarios() -> None:
    for scenario_id, with_action, charge_mask in _TRIPLE_SCENARIOS:
        def _build(with_action: bool = with_action, charge_mask: int = charge_mask) -> dict:
            return asyncio.run(_render_triple_templates(with_action, charge_mask))

        scenario(scenario_id)(_build)


_register_triple_scenarios()


@pytest.mark.parametrize("scenario_id", [item[0] for item in _TRIPLE_SCENARIOS])
def test_triple_templates_preserve_header_batteries_and_action(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
