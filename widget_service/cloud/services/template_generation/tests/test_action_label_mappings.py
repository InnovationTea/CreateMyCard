"""批准的 27 项动作文案及实际参数方向回归。"""

from copy import deepcopy
from typing import Any

import pytest

from models.generation import EventAction, TaskSpec
from services.template_generation.engine.cardplan.action_labels import (
    action_label_candidate,
    action_label_request,
    validate_action_label,
)
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.tests.test_focus_action_label import focus_task as focus_task
from services.template_generation.tests.test_generated_action_labels import (
    _event,
    _registered_events,
)

_FIXED_CASES = {
    "event.open.settings.sleepMode": "睡眠模式设置",
    "event.open.settings.studyMode": "学习模式设置",
    "event.open.settings.mobileNetwork": "移动网络设置",
    "event.open.settings.wifi": "Wi-Fi设置",
    "event.open.settings.mobileData": "移动数据设置",
    "event.open.settings.simManagement": "SIM卡管理",
    "event.open.settings.hotspot": "个人热点设置",
    "event.open.settings.dataUsage": "流量管理",
    "event.open.clock.worldClock": "世界时钟",
    "event.open.clock.alarmTab": "闹钟设置",
    "event.open.clock.stopwatch": "打开秒表",
    "event.open.clock.timer": "打开计时器",
    "event.open.health.sportsRecord": "运动记录",
    "event.open.health.activityRecord": "活动记录",
    "event.open.health.workoutDuration": "锻炼时长",
    "event.open.settings.darkMode": "显示设置",
    "event.openFlashlight": "打开手电筒",
    "event.closeFlashlight": "关闭手电筒",
}
_SWITCH_CASES = {
    "event.setMobileData": ("开启移动数据", "关闭移动数据"),
    "event.setNearLinkMode": ("开启星闪", "关闭星闪"),
    "event.setBluetoothMode": ("开启蓝牙", "关闭蓝牙"),
    "event.setWifiMode": ("开启Wi-Fi", "关闭Wi-Fi"),
    "event.setLocationSwitch": ("开启定位", "关闭定位"),
    "event.setScreenUseTimeManageSwitch": ("开启屏幕时长管控", "关闭屏幕时长管控"),
    "event.setMicPermissionSwitch": ("开启麦克风权限", "关闭麦克风权限"),
}
_SOUND_CASES = {"Vibrate": "设为振动", "Sound": "设为响铃", "Silent": "设为静音"}
_CAMERA_CASES = {
    "Photo": "拍照模式", "Video": "录像模式", "PORTRAIT": "人像模式",
    "CINEMA": "电影模式", "NIGHT": "夜景模式", "SUPER_MACRO": "微距模式",
    "LIGHT_PAINTING": "流光快门", "TIME_LAPSE": "延时摄影", "SLOW_MO": "慢动作",
    "STITCHING": "全景模式", "PRO": "专业模式",
}


def _with_param(event_id: str, key: str, value: Any) -> EventAction:
    event = _event(event_id)
    params = event.args.get("params")
    assert isinstance(params, dict)
    return event.model_copy(update={"args": {**event.args, "params": {**params, key: value}}})


def _assert_mapped(focus_task: TaskSpec, event: EventAction, expected: str) -> None:
    original = deepcopy(event.args)
    focus_task.eventCandidates = [event]
    binding = action_bindings(focus_task)[0]
    assert binding.display_label == expected
    assert binding.event_id == binding.action_id == event.id
    assert binding.call == event.call
    assert binding.args == event.args == original
    assert "labelPolicy" not in action_label_candidate(binding)
    assert action_label_request(focus_task.userQuery, (binding,)) == ()
    assert validate_action_label(binding, expected) == expected
    with pytest.raises(TerselConversionError, match="pair is not approved"):
        validate_action_label(binding, "另一项操作")


@pytest.mark.parametrize(("event_id", "label"), _FIXED_CASES.items())
def test_approved_fixed_labels(focus_task: TaskSpec, event_id: str, label: str) -> None:
    _assert_mapped(focus_task, _event(event_id), label)


@pytest.mark.parametrize(("event_id", "labels"), _SWITCH_CASES.items())
@pytest.mark.parametrize("switch_flag", [0, 1])
def test_switch_label_uses_actual_parameter_instead_of_query(
    focus_task: TaskSpec, event_id: str, labels: tuple[str, str], switch_flag: int,
) -> None:
    focus_task.userQuery = "日程与快捷操作：" + labels[1 - switch_flag]
    event = _with_param(event_id, "switchFlag", switch_flag)
    _assert_mapped(focus_task, event, labels[switch_flag])


@pytest.mark.parametrize(("option", "label"), _SOUND_CASES.items())
def test_sound_label_uses_actual_option(
    focus_task: TaskSpec, option: str, label: str,
) -> None:
    _assert_mapped(focus_task, _with_param("event.setSoundMode", "optionValue", option), label)


@pytest.mark.parametrize(("mode", "label"), _CAMERA_CASES.items())
def test_camera_label_names_selected_mode(focus_task: TaskSpec, mode: str, label: str) -> None:
    _assert_mapped(focus_task, _with_param("event.openCamera", "mode", mode), label)


@pytest.mark.parametrize(("event_id", "cases"), [
    ("event.setSoundMode", _SOUND_CASES), ("event.openCamera", _CAMERA_CASES),
])
def test_choice_cases_cover_registered_enum(event_id: str, cases: dict[str, str]) -> None:
    definition = _registered_events().get(event_id)
    assert definition is not None
    arguments = definition.get("dynamicArguments")
    assert isinstance(arguments, list)
    assert len(arguments) == 1
    assert set(arguments[0].get("enum", [])) == set(cases)


def _assert_fallback(focus_task: TaskSpec, event: EventAction) -> None:
    original = deepcopy(event.args)
    focus_task.eventCandidates = [event]
    binding = action_bindings(focus_task)[0]
    assert binding.display_label is None
    assert binding.args == event.args == original
    candidate = action_label_candidate(binding)
    assert candidate.get("labelPolicy") == "generate-from-request"
    assert candidate.get("description") == event.description
    assert candidate.get("readOnlyAction") == {"call": event.call, "args": original}
    assert action_label_request(focus_task.userQuery, (binding,))


@pytest.mark.parametrize("event_id", _SWITCH_CASES)
@pytest.mark.parametrize("value", [None, True, False, 0.0, "1", 2, [], {}])
def test_invalid_switch_parameter_preserves_fallback(
    focus_task: TaskSpec, event_id: str, value: Any,
) -> None:
    _assert_fallback(focus_task, _with_param(event_id, "switchFlag", value))


@pytest.mark.parametrize(("event_id", "key"), [
    ("event.setSoundMode", "optionValue"), ("event.openCamera", "mode"),
])
@pytest.mark.parametrize("value", [None, True, 0, [], {}, "Unknown", "photo", "silent"])
def test_unknown_choice_preserves_fallback(
    focus_task: TaskSpec, event_id: str, key: str, value: Any,
) -> None:
    _assert_fallback(focus_task, _with_param(event_id, key, value))


@pytest.mark.parametrize("event_id", [*_SWITCH_CASES, "event.setSoundMode", "event.openCamera"])
@pytest.mark.parametrize("args", [{}, {"params": {}}, {"params": None}, {"params": []}])
def test_missing_or_malformed_params_preserve_fallback(
    focus_task: TaskSpec, event_id: str, args: dict[str, Any],
) -> None:
    _assert_fallback(focus_task, _event(event_id).model_copy(update={"args": args}))


@pytest.mark.parametrize("event_id", ["event.open.settings.darkMode", "event.setWifiMode"])
def test_mapping_retains_explicit_trusted_label_priority(
    focus_task: TaskSpec, event_id: str,
) -> None:
    event = _event(event_id).model_copy(update={"displayLabel": " 自定义批准文案 "})
    _assert_mapped(focus_task, event, "自定义批准文案")
