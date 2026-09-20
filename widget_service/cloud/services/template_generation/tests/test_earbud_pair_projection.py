"""耳机名称和左右耳电量从模板检索到数据投影的回归。"""

from typing import Any

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.content_selectors import (
    extract_bluetooth_device_overview_facts,
    project_content_component_facts,
)
from services.template_generation.engine.cardplan.compiler import _validate_provider_template_state
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.engine.tersel_converter import TerselConversionError


class _EarbudPairModel:
    def __init__(self) -> None:
        self.body_calls = 0

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "requiredOutputFieldsByCapability": {
                "GetEarphoneInfo": ["/earphoneName", "/leftBatteryLevel", "/rightBatteryLevel"]
            },
            "action": ["event.open.settings.bluetooth"],
        }

    async def generate(self, *_args: Any, **_kwargs: Any) -> str:
        self.body_calls += 1
        return (
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbudPairHero@1",{}),'
            'Template("PillAction@1",'
            '{"actionId":"event.open.settings.bluetooth","label":"蓝牙设置"}));'
        )


def _fields(left: Any = 76, right: Any = 78) -> dict[str, Any]:
    return {
        "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
        "leftBatteryLevel": {"type": "integer", "sampleValue": left},
        "rightBatteryLevel": {"type": "integer", "sampleValue": right},
    }


@pytest.mark.parametrize("left,right", [(76, 78), (0, 100), (100, 0)])
@pytest.mark.asyncio
async def test_pair_hero_plan_projects_all_required_fields(left: int, right: int) -> None:
    fields = _fields(left, right)
    task = TaskSpec(
        userQuery="显示耳机名称和左右耳机的剩余电量",
        size="2x2",
        dataModelSchema={"data": {"earphone": fields}},
        eventCandidates=[
            EventAction(
                id="event.open.settings.bluetooth",
                call="clickToDeeplink",
                args={"intentName": "Settings", "uri": "bluetooth_entry"},
            )
        ],
    )
    paths = ["/earphoneName", "/leftBatteryLevel", "/rightBatteryLevel"]
    bindings = (
        CandidateDataBinding(
            capabilityId="GetEarphoneInfo",
            writeResultTo="/data/earphone",
            candidateOutputFields=paths,
        ),
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"GetEarphoneInfo": paths},
        action=["event.open.settings.bluetooth"],
    )
    card = {
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "GetEarphoneInfo", "writeResultTo": "/data/earphone"}],
    }
    registry = get_cardplan_registry()
    search = search_template_variants(intent, task, registry, bindings, card)
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    assert plans[0].business_slots[0].template_id == "BluetoothDeviceOverviewEarbudPairHero@1"

    projected = project_content_component_facts(
        task, {"GetEarphoneInfo"}, ("BluetoothDeviceOverview",)
    )
    data = projected.dataModelSchema.get("data")
    assert isinstance(data, dict)
    selected = data.get("BluetoothDeviceOverview")
    assert isinstance(selected, dict)
    assert set(selected) == set(fields)
    for name, expected in fields.items():
        field = selected.get(name)
        assert isinstance(field, dict)
        assert field.get("sampleValue") == expected.get("sampleValue")
        assert field.get("type") == expected.get("type")
    assert task.dataModelSchema == {"data": {"earphone": fields}}

    model = _EarbudPairModel()
    output = await generate_template_a2ui(task, card, bindings, model)
    assert model.body_calls == 1
    assert "BluetoothDeviceOverviewEarbudPairHero@1" in output.template_ids
    for path in paths:
        assert "/data/earphone" + path in output.a2ui


@pytest.mark.parametrize("missing", ["earphoneName", "leftBatteryLevel", "rightBatteryLevel"])
def test_pair_hero_compiler_rejects_missing_required_field(missing: str) -> None:
    fields = _fields()
    fields.pop(missing)
    fields["isConnected"] = {"type": "boolean", "sampleValue": True}
    task = TaskSpec(
        userQuery="耳机电量", size="2x2", dataModelSchema={"data": {"earphone": fields}}
    )
    with pytest.raises(TerselConversionError):
        _validate_provider_template_state(
            "BluetoothDeviceOverviewEarbudPairHero@1",
            "default",
            task,
            business_names={"BluetoothDeviceOverview"},
        )


def test_old_hero_still_requires_connection_state() -> None:
    task = TaskSpec(
        userQuery="耳机电量", size="2x2", dataModelSchema={"data": {"earphone": _fields()}}
    )
    with pytest.raises(TerselConversionError, match="no trusted earphone identity"):
        _validate_provider_template_state(
            "BluetoothDeviceOverviewHero@1",
            "default",
            task,
            business_names={"BluetoothDeviceOverview"},
        )


@pytest.mark.parametrize("side", ["leftBatteryLevel", "rightBatteryLevel"])
@pytest.mark.parametrize("invalid", [None, True, "76", -1, 101])
def test_name_and_invalid_ear_battery_remain_rejected(side: str, invalid: Any) -> None:
    fields = _fields()
    fields[side] = {"type": "integer", "sampleValue": invalid}
    assert extract_bluetooth_device_overview_facts({"data": {"earphone": fields}}) is None


@pytest.mark.parametrize("missing", ["leftBatteryLevel", "rightBatteryLevel"])
def test_name_and_one_ear_remain_rejected(missing: str) -> None:
    fields = _fields()
    fields.pop(missing)
    assert extract_bluetooth_device_overview_facts({"data": {"earphone": fields}}) is None


def test_ear_battery_fields_cannot_be_combined_across_entities() -> None:
    first = _fields()
    first.pop("rightBatteryLevel")
    second = _fields()
    second.pop("leftBatteryLevel")
    schema = {"data": {"first": first, "second": second}}
    assert extract_bluetooth_device_overview_facts(schema) is None
