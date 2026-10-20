"""2×2 整卡详情动作的共享适用性合同；不改写事实、事件或组件。"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

WHOLE_CARD_LAYOUTS = ("S-title-content", "S-title-dual-content")
_READ_ONLY_DETAILS = {
    "event.open.weather": ("weather", "clickToDeeplink", "Weather_CityCode"),
    "event.viewCalendarEvent": ("calendar", "clickToIntent", "ViewCalendarEvent"),
}
_BUTTON_REQUEST = re.compile(r"按钮|按键|独立入口|入口文案|动作文案|button|\bCTA\b", re.I)
_NO_BUTTON_REQUEST = re.compile(
    r"(?:不需要|不要|不用|无需|不)(?:显示|展示|添加|保留)?(?:独立)?按钮|"
    r"(?:去掉|删除|移除)按钮|without buttons?|no buttons?", re.I,
)
_PURE_DISPLAY = re.compile(r"纯展示|不(?:要|需要|支持)(?:整卡)?点击|不可点击")
_CALENDAR_ENTITY = re.compile(r"/data/calendar/events/(?P<index>\d+)/entityId")
_SINGLE_PATH_EXPRESSION = re.compile(r"\s*\{\{\s*\$\{(?P<path>/[^}]+)\}\s*\}\}\s*")
_WEATHER_CITY_URI = re.compile(
    r"\s*\{\{\s*(['\"])hww://www\.huawei\.com/totemweather\?enterType=share&cityCode=\1"
    r"\s*\+\s*\$\{/data/weather/location/cityCode\}\s*\}\}\s*"
)


@dataclass(frozen=True)
class WholeCardClick:
    action_id: str
    handler: dict[str, Any]


def select_whole_card_click(
    task: dict[str, Any], facts: list[dict[str, Any]],
) -> WholeCardClick | None:
    """只对唯一匹配的正式只读详情目标派生承载方式，不从动作描述猜测权限。"""
    if task.get("size") != "2x2":
        return None
    query = task.get("userQuery")
    if not isinstance(query, str):
        return None
    if _BUTTON_REQUEST.search(_NO_BUTTON_REQUEST.sub("", query)) or _PURE_DISPLAY.search(query):
        return None
    actions = [fact for fact in facts if isinstance(fact.get("actionId"), str)]
    if len(actions) != 1:
        return None
    action_id = actions[0].get("actionId")
    if not isinstance(action_id, str):
        return None
    contract = _READ_ONLY_DETAILS.get(action_id)
    if contract is None:
        return None
    business, call, intent = contract
    schema = task.get("dataModelSchema")
    data = schema.get("data") if isinstance(schema, dict) else None
    if not isinstance(data, dict) or set(data) != {business}:
        return None
    candidates = task.get("eventCandidates")
    if not isinstance(candidates, list):
        return None
    matches = []
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("id") == action_id:
            matches.append(candidate)
    if len(matches) != 1:
        return None
    candidate = matches[0]
    args = candidate.get("args")
    if candidate.get("call") != call or not isinstance(args, dict):
        return None
    if args.get("intentName") != intent:
        return None
    paths = []
    for fact in facts:
        path = fact.get("dataId")
        if isinstance(path, str):
            paths.append(path)
    if not paths or not _matches_detail_object(business, args, paths):
        return None
    result: WholeCardClick | None = WholeCardClick(
        action_id=action_id, handler={"call": call, "args": copy.deepcopy(args)},
    )
    return result


def accepted_whole_card_click(
    task: dict[str, Any], plan: dict[str, Any] | None,
) -> WholeCardClick | None:
    """复核服务端接受标记；标记本身不能绕过用户要求或目标一致性。"""
    if not isinstance(plan, dict):
        return None
    facts = plan.get("info_required")
    if not isinstance(facts, list) or not all(isinstance(fact, dict) for fact in facts):
        return None
    selected = select_whole_card_click(task, facts)
    result: WholeCardClick | None = None
    if selected is not None and plan.get("wholeCardActionId") == selected.action_id:
        result = selected
    return result


def _matches_detail_object(business: str, args: dict[str, Any], paths: list[str]) -> bool:
    if business == "weather":
        if set(args) != {"intentName", "bundleName", "abilityName", "uri"}:
            return False
        uri = args.get("uri")
        if not isinstance(uri, str):
            return False
        if args.get("bundleName") != "" or args.get("abilityName") != "":
            return False
        correct_city = _WEATHER_CITY_URI.fullmatch(uri) is not None
        same_business = all(path.startswith("/data/weather/") for path in paths)
        return correct_city and same_business
    if set(args) != {"intentName", "params"}:
        return False
    params = args.get("params")
    if not isinstance(params, dict) or set(params) != {"entityId"}:
        return False
    entity = params.get("entityId")
    path: str | None = None
    if isinstance(entity, dict) and set(entity) == {"path"}:
        path = entity.get("path")
    elif isinstance(entity, str):
        match = _SINGLE_PATH_EXPRESSION.fullmatch(entity)
        if match is not None:
            path = match.group("path")
    if not isinstance(path, str):
        return False
    match = _CALENDAR_ENTITY.fullmatch(path)
    if match is None:
        return False
    event_prefix = f"/data/calendar/events/{match.group('index')}/"
    return all(display_path.startswith(event_prefix) for display_path in paths)
