"""从定稿可见内容识别图片业务；抽象图保留既有颜色映射。"""

import re

from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_plan import _VISIBLE_PROP_NAMES, _compact_visible_state
from services.display_text import concatenated_display_text
from services.square_photo_expansion import SLEEP_FIELDS

_SPORT_FIELD = re.compile(
    r"^(?:exercise|run|daily(?:Steps|Distance|TotalCalories)|steps|stepCount|activity|active|"
    r"calories|distance|heartRate|calorie|stand|move|workout|floors)", re.I,
)


def subtree(identity: str, by_id: dict) -> list[ComponentRow]:
    result = []
    pending = [identity]
    visited = set()
    while pending:
        current = pending.pop()
        row = by_id.get(current)
        if row is None or current in visited:
            return []
        visited.add(current)
        result.append(row)
        pending.extend(reversed(row.children))
    return result


def _only_music_actions(rows: list[ComponentRow]) -> bool:
    found = False
    for row in rows:
        for action in row.props.get("onClick", []):
            if not isinstance(action, dict):
                return False
            arguments = action.get("args", {})
            if not isinstance(arguments, dict) or action.get("call") != "clickToDeeplink":
                return False
            if arguments.get("intentName") != "Music":
                return False
            found = True
    return found


def _path_business(path: str) -> str | None:
    result: str | None = None
    prefixes = {
        "/data/calendar/": "calendar", "/data/phoneBattery/": "battery",
        "/data/earphone/": "earphone", "/data/weather/": "weather",
        "/data/countdown/": "countdown", "/data/travel/": "travel",
        "/data/flight/": "travel", "/data/news/": "information",
        "/data/information/": "information", "/data/smartHome/": "smart-home",
        "/data/music/": "music",
    }
    for prefix, business in prefixes.items():
        if path.startswith(prefix):
            result = business
            break
    if path.startswith("/data/healthSport/"):
        field_name = path.rsplit("/", 1)[-1]
        if field_name in SLEEP_FIELDS:
            result = "sleep"
        elif _SPORT_FIELD.match(field_name):
            result = "sport"
    return result


def visible_business(rows: list[ComponentRow]) -> str | None:
    state = _compact_visible_state(rows)
    result: str | None = None
    if not state.paths:
        result = "music" if _only_music_actions(rows) else None
    businesses = set()
    unknown = False
    for path in state.paths:
        if path.rsplit("/", 1)[-1] in {"updatedAt", "targetDateText"}:
            continue
        business = _path_business(path)
        if business is None:
            unknown = True
            break
        businesses.add(business)
    if len(businesses) == 1 and not unknown:
        result = next(iter(businesses))
    return result


def _holiday_name(text: str) -> bool:
    other_countdown = re.search(
        r"生日|考试|纪念|旅行|出游|婚礼|面试|会议|马拉松|跑步|训练|赛事|比赛|"
        r"\b(?:birthday|exam|anniversary|meeting|wedding|trip|marathon|running|race)\b",
        text, re.I,
    )
    category = re.search(
        r"节|假期|假日|放假|休假|年假|寒假|暑假|调休|元旦|新年|中秋|国庆|"
        r"清明|端午|重阳|除夕|跨年|周末|周日|周天|星期日|星期天|"
        r"holiday|vacation|festival|weekend|sunday|christmas|new year", text, re.I,
    )
    return category is not None and other_countdown is None


def _display_strings(value: object, values: dict) -> list[str]:
    result = []
    if isinstance(value, str):
        resolved = concatenated_display_text(value, values.get)
        if resolved is not None:
            result.append(resolved)
    elif isinstance(value, dict):
        if set(value) == {"path"}:
            bound = values.get(value.get("path"))
            if isinstance(bound, str):
                result.append(bound)
        else:
            for child in value.values():
                result.extend(_display_strings(child, values))
    elif isinstance(value, list):
        for child in value:
            result.extend(_display_strings(child, values))
    return result


def holiday_countdown(rows: list[ComponentRow], values: dict) -> bool:
    """逐个可见倒计时确认节假日；一个节假日不能替其它未知/非节假日对象放行。"""
    if visible_business(rows) != "countdown":
        return False
    by_id = {row.component_id: row for row in rows}
    names: dict[str, list[str]] = {}
    for path in _compact_visible_state(rows).paths:
        if path.startswith("/data/countdown/") and path.endswith("/countdownDays"):
            names[path.rsplit("/", 1)[0]] = []
    for row in rows:
        scoped = subtree(row.component_id, by_id)
        scoped = [item for item in scoped if not item.component_type.endswith("Button")]
        state = _compact_visible_state(scoped)
        prefixes = set()
        for path in state.paths:
            if path.startswith("/data/countdown/"):
                prefixes.add(path.rsplit("/", 1)[0])
        if len(prefixes) != 1:
            continue
        texts = names.get(next(iter(prefixes)))
        if texts is None:
            continue
        for item in scoped:
            for key, value in item.props.items():
                if key in _VISIBLE_PROP_NAMES:
                    texts.extend(_display_strings(value, values))
    return bool(names) and all(_holiday_name(" ".join(texts)) for texts in names.values())
