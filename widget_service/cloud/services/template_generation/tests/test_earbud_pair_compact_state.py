"""成对耳机 Compact 的必需数据与连接状态边界回归。"""

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _validate_provider_template_state,
)
from services.template_generation.engine.tersel_converter import TerselConversionError


def _pair_task(missing_field: str | None = None) -> TaskSpec:
    fields = {
        "earphoneName": {"type": "string", "sampleValue": "示例耳机"},
        "leftBatteryLevel": {"type": "integer", "sampleValue": 76},
        "rightBatteryLevel": {"type": "integer", "sampleValue": 78},
    }
    if missing_field is not None:
        fields.pop(missing_field)
    return TaskSpec(
        userQuery="查看耳机名称和左右耳电量",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={"data": {"earphone": fields}},
    )


def test_pair_compact_accepts_data_without_connection_state() -> None:
    _validate_provider_template_state(
        "BluetoothDeviceOverviewEarbudPairCompact@1",
        "default",
        _pair_task(),
        business_names={"BluetoothDeviceOverview"},
    )


@pytest.mark.parametrize("missing_field", ["earphoneName", "leftBatteryLevel", "rightBatteryLevel"])
def test_pair_compact_rejects_missing_required_data(missing_field: str) -> None:
    with pytest.raises(TerselConversionError):
        _validate_provider_template_state(
            "BluetoothDeviceOverviewEarbudPairCompact@1",
            "default",
            _pair_task(missing_field),
            business_names={"BluetoothDeviceOverview"},
        )


@pytest.mark.parametrize(
    "template_id",
    [
        "BluetoothDeviceOverviewHero@1",
        "BluetoothDeviceOverviewConnectionSupport@1",
    ],
)
def test_connection_templates_still_require_connection_state(template_id: str) -> None:
    with pytest.raises(TerselConversionError):
        _validate_provider_template_state(
            template_id,
            "default",
            _pair_task(),
            business_names={"BluetoothDeviceOverview"},
        )
