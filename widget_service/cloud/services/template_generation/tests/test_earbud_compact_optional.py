"""Compact 可选字段的缺失、零电量和未连接回归。"""

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
@pytest.mark.parametrize("connected", [None, False, True])
@pytest.mark.parametrize("battery", [None, 0, 80])
async def test_compact_optional_fields(connected: bool | None, battery: int | None) -> None:
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
    assert "CompactTwoActionLayout@1" in result.template_ids
    for line in result.a2ui.splitlines():
        for component in json.loads(line).get("updateComponents", {}).get("components", []):
            if component.get("onClick"):
                assert component.get("styles", {}).get("backgroundColor") == "#33FFFFFF"

    assert ("/isConnected" in result.a2ui) == (connected is not None)
    assert ("/batteryLevel" in result.a2ui) == (battery is not None)
    assert ("未连接" in result.a2ui) == (connected is not None)
    battery_rows = []
    for line in result.a2ui.splitlines():
        update = json.loads(line).get("updateComponents", {})
        for component in update.get("components", []):
            styles = component.get("styles", {})
            if component.get("component") == "Row" and styles.get("width") == "matchParent":
                if styles.get("height") == 12:
                    battery_rows.append(component)
    assert len(battery_rows) == 1
    row = battery_rows[0]
    assert row.get("itemMargin") == (12 if battery is None else 8)
    assert len(row.get("children", [])) == (2 if battery is None else 3)

    components = {}
    for line in result.a2ui.splitlines():
        for component in json.loads(line).get("updateComponents", {}).get("components", []):
            components[component.get("id")] = component
    title_rows = []
    for component in components.values():
        if component.get("component") != "Row":
            continue
        children = component.get("children", [])
        if len(children) != 3:
            continue
        separator = components.get(children[1], {})
        if separator.get("content") == "|":
            title_rows.append(component)
    assert len(title_rows) == (0 if connected is None else 1)
    for title in title_rows:
        for child_id in title.get("children", []):
            child = components.get(child_id)
            assert isinstance(child, dict)
            styles = child.get("styles", {})
            assert styles.get("fontSize") == 12
            assert styles.get("fontWeight") == 700
