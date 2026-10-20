"""候选事件比较；已登记开关的可选整数标记等价，其它参数保持精确匹配。"""

from __future__ import annotations

import copy
import json
from typing import Any

_SETTING_SWITCH_ITEMS = frozenset({
    "battery_saving_mode", "near_link_setting", "bluetooth", "wlan",
})
_OPTIONAL_SWITCH_INTENTS = frozenset({
    ("clickToApi", "SetMobileData"),
    ("clickToIntent", "SetLocationSettingSwicth"),
    ("clickToIntent", "SetScreenUseTimeManageSwitch"),
    ("clickToIntent", "SetMicSettingSwicth"),
})


def is_optional_switch_event(handler: dict[str, Any]) -> bool:
    """仅识别已登记的开关调用及目标，不以参数同名扩大适用范围。"""
    args = handler.get("args")
    if not isinstance(args, dict):
        return False
    params = args.get("params")
    if not isinstance(params, dict):
        return False
    call = handler.get("call")
    intent = args.get("intentName")
    if not isinstance(call, str) or not isinstance(intent, str):
        return False
    if (call, intent) in _OPTIONAL_SWITCH_INTENTS:
        return True
    if call != "clickToIntent" or intent != "SetSettingSwitch":
        return False
    if params.get("appBundleName") != "com.huawei.hmos.settings":
        return False
    item_name = params.get("itemName")
    return isinstance(item_name, str) and item_name in _SETTING_SWITCH_ITEMS


def normalize_event_handler(handler: dict[str, Any]) -> dict[str, Any] | None:
    """返回比较和 schema 校验专用副本，非法兼容标记返回 None；不改写事件原值。"""
    result: dict[str, Any] | None = copy.deepcopy(handler)
    args = handler.get("args")
    if not isinstance(args, dict):
        return result
    params = args.get("params")
    if not isinstance(params, dict):
        return result
    if not is_optional_switch_event(handler):
        return result
    if "switchFlag" in params:
        flag = params.get("switchFlag")
        if type(flag) is not int or flag not in (0, 1):
            result = None
    if result is not None:
        comparable_params = dict(params)
        comparable_params.pop("switchFlag", None)
        result["args"] = {**args, "params": comparable_params}
    return result


def event_handlers_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """只比较，不改写事件；JSON 比较区分布尔、数字和字符串。"""
    normalized_actual = normalize_event_handler(actual)
    normalized_expected = normalize_event_handler(expected)
    if normalized_actual is None or normalized_expected is None:
        return False
    return json.dumps(normalized_actual, sort_keys=True, ensure_ascii=False) == json.dumps(
        normalized_expected, sort_keys=True, ensure_ascii=False,
    )
