"""验证左右耳机分割线不挤占原有布局。"""

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
