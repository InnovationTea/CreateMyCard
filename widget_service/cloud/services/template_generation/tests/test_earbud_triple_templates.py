"""独立三电量模板不依赖连接状态，且保持动作和充电状态布局。

完整 A2UI 产物已固化为场景金样（Layer C）：无动作的 Full 渲染与
Hero+PillAction 渲染各一份；充电状态列几何、主题色、onClick 载荷与
连接语义的缺省（isConnected/已连接 不得出现）都由快照整体冻结。引擎或
模板改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

import asyncio
import json

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


async def _render_triple_templates(with_action: bool):
    fields = {
        "earphoneName": _provider_field("测试耳机", "string"),
        "batteryLevel": _provider_field(80, "integer"),
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    if with_action:
        fields["leftChargingStatusDesc"] = _provider_field("未充电", "string")
        fields["rightChargingStatusDesc"] = _provider_field("充电中", "string")
        fields["chargingStatusDesc"] = _provider_field("充电中", "string")
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
                    "sceneTags": [],
                }
            ],
        }
    )
    required_fields = ("/batteryLevel", "/leftBatteryLevel", "/rightBatteryLevel")
    body = (
        'Template("SingleFocusLayout@1",{},Template("BluetoothDeviceOverviewEarbudTripleFull@1",{}));'
    )
    selected_action: str | None = None
    if with_action:
        selected_action = action_id
        body = (
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbudTripleFull@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.music.favorite",'
            '"label":"心动歌单"}));'
        )
    template_id = "BluetoothDeviceOverviewEarbudTripleFull@1"
    if with_action:
        template_id = "BluetoothDeviceOverviewEarbudTripleHero@1"
        body = body.replace("EarbudTripleFull@1", "EarbudTripleHero@1")
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


@scenario("earbud_triple__full_no_action")
def _build_full_no_action() -> dict:
    return asyncio.run(_render_triple_templates(with_action=False))


@scenario("earbud_triple__hero_pill_action")
def _build_hero_pill_action() -> dict:
    return asyncio.run(_render_triple_templates(with_action=True))


def test_triple_templates_preserve_header_batteries_and_action() -> None:
    assert_golden_scenario("earbud_triple__full_no_action")
    assert_golden_scenario("earbud_triple__hero_pill_action")
