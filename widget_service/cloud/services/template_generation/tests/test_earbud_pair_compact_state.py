"""成对耳机 Compact 的必需数据与连接状态边界回归。

``_validate_provider_template_state`` 的接受/拒绝矩阵已固化为场景金样
（Layer C）：``earbud__pair_compact_state_validation`` 冻结 Compact 对三必需
字段的容忍与拒绝（TerselConversionError 报错类型 + 消息）、合法输入的
``{"error": "NO_ERROR"}`` 哨兵，以及旧 Hero / ConnectionSupport 仍要求连接
状态的报错。引擎或模板改动后按 golden 工作流
``check --diff`` / ``bless --declared`` 复核。
"""

from typing import Any

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _validate_provider_template_state,
)
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)


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


def _validation_error(template_id: str, task: TaskSpec) -> dict[str, Any]:
    try:
        _validate_provider_template_state(
            template_id, "default", task, business_names={"BluetoothDeviceOverview"},
        )
    except Exception as exc:  # noqa: BLE001 - 报错类型 + 消息整体冻结
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


@scenario("earbud__pair_compact_state_validation")
def _build_pair_compact_state_validation() -> dict[str, Any]:
    compact = "BluetoothDeviceOverviewEarbudPairCompact@1"
    payload: dict[str, dict[str, Any]] = {
        "pair_compact_accept": _validation_error(compact, _pair_task()),
    }
    for missing in ("earphoneName", "leftBatteryLevel", "rightBatteryLevel"):
        payload[f"pair_compact_missing_{missing}"] = _validation_error(
            compact, _pair_task(missing),
        )
    payload["legacy_hero_requires_connection"] = _validation_error(
        "BluetoothDeviceOverviewHero@1", _pair_task(),
    )
    payload["connection_support_requires_connection"] = _validation_error(
        "BluetoothDeviceOverviewConnectionSupport@1", _pair_task(),
    )
    return payload


def test_earbud_pair_compact_state_scenario() -> None:
    assert_golden_scenario("earbud__pair_compact_state_validation")
