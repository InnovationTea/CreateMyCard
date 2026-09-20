"""独立三电量模板不依赖连接状态，且保持动作和充电状态布局。"""

import json

import pytest

from models.generation import CandidateDataBinding, EventAction
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.test_template_generation import (
    _bluetooth_card_spec,
    _bluetooth_task,
    _FixedTemplateModel,
    _provider_field,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("with_action", [False, True])
async def test_triple_templates_preserve_header_batteries_and_action(
    with_action: bool,
) -> None:
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
    assert template_id in result.template_ids
    for field in required_fields:
        assert field in result.a2ui
    if with_action:
        assert action_id in result.a2ui
    assert ("蓝牙耳机" in result.a2ui) == (not with_action)
    assert "isConnected" not in result.a2ui
    assert "已连接" not in result.a2ui
    assert "未连接" not in result.a2ui
    if with_action:
        assert "PillAction@1" in result.template_ids
        assert "IconAction@1" not in result.template_ids
        for name in ("leftChargingStatusDesc", "rightChargingStatusDesc", "chargingStatusDesc"):
            assert name in result.a2ui
        columns = []
        for line in result.a2ui.splitlines():
            update = json.loads(line).get("updateComponents", {})
            for component in update.get("components", []):
                styles = component.get("styles", {})
                if component.get("component") == "Column" and styles.get("width") == 44:
                    columns.append(component)
        assert len(columns) == 3
        assert all(column.get("styles", {}).get("height") == 26 for column in columns)
        return
    headers = []
    for line in result.a2ui.splitlines():
        message = json.loads(line)
        update = message.get("updateComponents", {})
        for component in update.get("components", []):
            styles = component.get("styles", {})
            if styles.get("height") in (18, 26) and component.get("component") == "Text":
                headers.append(styles)
    assert any(style.get("fontSize") == 12 and style.get("height") == 18 for style in headers)
    assert any(style.get("fontSize") == 18 and style.get("height") == 26 for style in headers)
