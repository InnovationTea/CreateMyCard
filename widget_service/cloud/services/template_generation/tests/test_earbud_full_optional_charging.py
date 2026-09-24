"""现有连接状态模板的充电状态必须整行展示。"""

import json

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.pipeline import (
    TemplateRouteNotApplicable,
    generate_template_a2ui,
)
from services.template_generation.tests.test_template_generation import (
    _bluetooth_card_spec,
    _bluetooth_task,
    _FixedTemplateModel,
    _provider_field,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("mask", range(8))
@pytest.mark.parametrize("header", ["both", "name", "connected", "none"])
async def test_full_charging_row_requires_all_three_fields(
    mask: int, fusion: bool, header: str,
) -> None:
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
    charge_fields = ("leftChargingStatusDesc", "rightChargingStatusDesc", "chargingStatusDesc")
    for index, field in enumerate(charge_fields):
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
    if header == "none":
        with pytest.raises(TemplateRouteNotApplicable):
            await generate_template_a2ui(
                task, _bluetooth_card_spec(), (binding,), model, enable_fusion_ball=fusion,
                trusted_template_candidate_ids=(template_id,),
            )
        return
    result = await generate_template_a2ui(
        task, _bluetooth_card_spec(), (binding,), model, enable_fusion_ball=fusion,
    )
    assert template_id in result.template_ids
    assert ("蓝牙耳机" in result.a2ui) == (header != "both")
    assert ("/isConnected" in result.a2ui) == (header != "name")
    assert ("/earphoneName" in result.a2ui) == (header != "connected")
    assert ("未连接" in result.a2ui) == (header != "name")
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


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("charging", [False, True])
async def test_earbuds_divider(fusion: bool, charging: bool) -> None:
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
    components = []
    for line in output.a2ui.splitlines():
        components.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    dividers = []
    for item in components:
        if item.get("component") == "Divider" and item.get("styles", {}).get("strokeWidth") == 0.5:
            dividers.append(item)
    assert len(dividers) == 1
    divider = dividers[0]
    styles = divider.get("styles", {})
    assert styles.get("width") == 62
    assert styles.get("height") == 0.5
    assert styles.get("strokeWidth") == 0.5
    assert styles.get("color") == "#19FFFFFF"
    row = next(item for item in components if divider.get("id") in item.get("children", []))
    assert row.get("styles", {}).get("justifyContent") == "end"
    stack = next(item for item in components if row.get("id") in item.get("children", []))
    assert stack.get("component") == "Stack"
    assert stack.get("styles", {}).get("alignContent") == "center"
    assert len(stack.get("children", [])) == 2
    rings = [item for item in components if item.get("component") == "Progress"]
    assert len(rings) == 2
