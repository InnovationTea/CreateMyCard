"""候选事件比较；设置开关的两个整数标记等价，其它参数保持精确匹配。"""

from __future__ import annotations

import copy
import json
from typing import Any


def _comparison_handler(handler: dict[str, Any]) -> dict[str, Any] | None:
    result: dict[str, Any] | None = copy.deepcopy(handler)
    args = handler.get("args")
    if handler.get("call") != "clickToIntent" or not isinstance(args, dict):
        return result
    params = args.get("params")
    if args.get("intentName") != "SetSettingSwitch" or not isinstance(params, dict):
        return result
    if params.get("appBundleName") != "com.huawei.hmos.settings":
        return result
    flag = params.get("switchFlag")
    if type(flag) is not int or flag not in (0, 1):
        result = None
    else:
        result["args"] = {**args, "params": {**params, "switchFlag": 0}}
    return result


def event_handlers_match(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """只比较，不改写事件；JSON 比较区分布尔、数字和字符串。"""
    normalized_actual = _comparison_handler(actual)
    normalized_expected = _comparison_handler(expected)
    if normalized_actual is None or normalized_expected is None:
        return False
    return json.dumps(normalized_actual, sort_keys=True, ensure_ascii=False) == json.dumps(
        normalized_expected, sort_keys=True, ensure_ascii=False,
    )
