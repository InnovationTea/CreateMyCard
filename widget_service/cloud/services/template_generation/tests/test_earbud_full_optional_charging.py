"""现有连接状态模板的充电状态必须整行展示。"""

import json

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.tests.test_template_generation import (
    _bluetooth_card_spec,
    _bluetooth_task,
    _FixedTemplateModel,
    _provider_field,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("mask", range(8))
async def test_full_charging_row_requires_all_three_fields(mask: int, fusion: bool) -> None:
    fields = {
        "earphoneName": _provider_field("测试耳机", "string"),
        "isConnected": _provider_field(False, "boolean"),
        "batteryLevel": _provider_field(0, "integer"),
        "leftBatteryLevel": _provider_field(76, "integer"),
        "rightBatteryLevel": _provider_field(78, "integer"),
    }
    charge_fields = ("leftChargingStatusDesc", "rightChargingStatusDesc", "chargingStatusDesc")
    for index, field in enumerate(charge_fields):
        if mask & (1 << index):
            fields[field] = _provider_field("未充电", "string")
    task = _bluetooth_task("查看耳机名称、连接状态及电量").model_copy(
        update={"dataModelSchema": {"data": {"earphone": fields}}, "eventCandidates": []},
    )
    required = ["/earphoneName", "/isConnected", "/leftBatteryLevel", "/rightBatteryLevel"]
    if mask == 7:
        required.extend(f"/{field}" for field in charge_fields)
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
    assert template_id in result.template_ids
    components = []
    for line in result.a2ui.splitlines():
        components.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    charge_nodes = []
    battery_columns = []
    for component in components:
        styles = component.get("styles", {})
        if component.get("component") == "Column" and styles.get("height") in (34, 50):
            battery_columns.append(component)
        if component.get("component") != "Text":
            continue
        content = json.dumps(component.get("content"))
        if any(field in content for field in charge_fields):
            charge_nodes.append(component)
    assert len(battery_columns) == 3
    for column in battery_columns:
        assert column.get("styles", {}).get("alignItems") == "start"
        assert column.get("styles", {}).get("height") == (50 if mask == 7 else 34)
        children = column.get("children", [])
        assert len(children) == (3 if mask == 7 else 2)
        percent = next(item for item in components if item.get("id") == children[1])
        assert percent.get("styles", {}).get("fontSize") == 12
        assert percent.get("styles", {}).get("fontWeight") == 500
        assert percent.get("styles", {}).get("fontColor") == "#FFFFFFFF"
    assert len(charge_nodes) == (3 if mask == 7 else 0)
    for component in charge_nodes:
        styles = component.get("styles", {})
        assert styles.get("width") == 36
        assert styles.get("fontSize") == 10
        assert styles.get("fontWeight") == 400
        assert styles.get("fontColor") == "#99FFFFFF"
        assert styles.get("textAlign") == "start"
