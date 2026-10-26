"""布局规划与主题共享的业务归属；不识别视觉偏好、不决定布局或主题。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from services.compact_dsl_a2ui_converter import ComponentRow, DataRow, parse_compact_dsl_rows
from services.compact_plan import _compact_visible_state, compact_plan_data_paths
from services.event_matching import is_optional_switch_event

SLEEP_FIELDS = {
    "sleepScore", "sleepStatus", "sleepTypeDesc", "nightSleepDurationText",
    "deepSleepDurationText", "totalNapDurationText", "fallAsleepTimeText", "wakeupTimeText",
}
_SPORT_FIELD = re.compile(
    r"^(?:exercise|run|daily(?:Steps|Distance|TotalCalories)|steps|stepCount|activity|active|"
    r"calories|distance|heartRate|calorie|stand|move|workout|floors)", re.I,
)
_APP_USAGE_FIELD = re.compile(
    r"/data/(?:[^/]+/)+mostUsedApps/[0-9]+/(?:appName|totalDuration)",
)
_METADATA_FIELDS = frozenset({"updatedAt", "targetDateText"})


def _settings_action(action: dict, call: str, intent: str, arguments: dict) -> bool:
    if is_optional_switch_event(action):
        return True
    if call == "clickToDeeplink" and intent == "Settings":
        return arguments.get("bundleName") == "com.huawei.hmos.settings"
    if call != "clickToIntent":
        return False
    if intent in {"OpenFlashlight", "CloseFlashlight"}:
        return True
    parameters = arguments.get("params")
    if not isinstance(parameters, dict):
        return False
    return (intent in {"EnterSettingPage", "SetSettingOption"}
            and parameters.get("appBundleName") == "com.huawei.hmos.settings")


def _action_business(action: object) -> str | None:
    result: str | None = None
    if not isinstance(action, dict):
        return result
    arguments = action.get("args")
    if not isinstance(arguments, dict):
        return result
    call = action.get("call")
    intent = arguments.get("intentName")
    if not isinstance(call, str) or not isinstance(intent, str):
        return result
    if (call, intent) == ("clickToDeeplink", "Music"):
        result = "music"
    elif (call, intent) == ("clickToIntent", "StartNavigate"):
        result = "navigation"
    elif _settings_action(action, call, intent, arguments):
        result = "settings"
    return result


def _path_business(path: str) -> str | None:
    result: str | None = None
    date_paths = {
        "/data/currentTime/currentDate",
        "/data/currentTime/dayOfWeek",
        "/data/currentTime/lunarDate",
    }
    if path in date_paths:
        result = "calendar"
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
    # GetDailyMostUsage的写入根由请求指定，按其输出叶子识别，不依赖dailyUsage别名。
    if _APP_USAGE_FIELD.fullmatch(path):
        result = "app-usage"
    return result


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


@dataclass(frozen=True)
class VisibleBusinesses:
    """实际展示的业务证据；保留首项未知及数据优先于动作的既有语义。"""

    single: str | None
    first: str | None
    ordered: tuple[str | None, ...]
    data_businesses: frozenset[str | None]
    data_paths: frozenset[str]

    def payload(self) -> dict:
        return {
            "singleBusiness": self.single, "firstBusiness": self.first,
            "businesses": list(self.ordered), "hasUnknown": None in self.ordered,
        }


@dataclass
class BusinessContext:
    """请求内缓存，不跨用户、不读请求文案，也不改变能力或数据的授权。"""

    data: dict[str, str | None] = field(default_factory=dict)
    actions: dict[str, str | None] = field(default_factory=dict)
    candidate_actions: dict[str, str | None] = field(default_factory=dict)
    layout_route: str | None = None
    layout_block_count: int = 0

    @classmethod
    def from_task(cls, task: dict) -> BusinessContext:
        result = cls()
        for path in compact_plan_data_paths(task):
            result.data_business(path)
        candidates = task.get("eventCandidates", [])
        if not isinstance(candidates, list):
            candidates = []
        for candidate in candidates:
            if isinstance(candidate, dict):
                business = result.action_business(candidate)
                identity = candidate.get("id")
                if isinstance(identity, str):
                    result.candidate_actions[identity] = business
        return result

    def data_business(self, path: str) -> str | None:
        # 定稿可能包含列表的其它下标；仍复用同一注册归属函数，不猜测业务。
        if path not in self.data:
            self.data[path] = _path_business(path)
        return self.data.get(path)

    def action_business(self, action: object) -> str | None:
        value = action
        if isinstance(action, dict):
            value = {"call": action.get("call"), "args": action.get("args")}
        identity = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if identity not in self.actions:
            self.actions[identity] = _action_business(action)
        return self.actions.get(identity)

    def candidate_payload(self) -> dict:
        return {
            "data": dict(self.data), "actions": dict(self.candidate_actions),
            "scope": "available-candidates-not-selected-content",
        }

    def visible(self, rows: list[ComponentRow]) -> VisibleBusinesses:
        state = _compact_visible_state(rows)
        ordered_data = []
        data_businesses = set()
        for occurrence in state.path_occurrences:
            if occurrence.data_id.rsplit("/", 1)[-1] in _METADATA_FIELDS:
                continue
            business = self.data_business(occurrence.data_id)
            data_businesses.add(business)
            if business not in ordered_data:
                ordered_data.append(business)
        # paths是完整可见集合；顺序仍只由实际内容树中的occurrences决定。
        for path in state.paths:
            if path.rsplit("/", 1)[-1] not in _METADATA_FIELDS:
                data_businesses.add(self.data_business(path))
        actions = []
        for row in rows:
            handlers = row.props.get("onClick", [])
            if not isinstance(handlers, list):
                actions.append(None)
                continue
            for handler in handlers:
                actions.append(self.action_business(handler))
        single_pool = data_businesses if state.paths else set(actions)
        single = next(iter(single_pool)) if len(single_pool) == 1 else None
        ordered = ordered_data if ordered_data else list(dict.fromkeys(actions))
        # 兼容旧首动作规则：忽略无效handler；校验器另外拒绝无效动作。
        first = ordered_data[0] if ordered_data else None
        if not ordered_data and state.handlers:
            first = self.action_business(state.handlers[0])
        return VisibleBusinesses(
            single, first, tuple(ordered), frozenset(data_businesses), state.paths,
        )


@dataclass
class FinalBusinessContext:
    """对定稿只解析一次，按整卡/区域缓存业务；缺失或无效定稿不授权图片。"""

    catalog: BusinessContext
    by_id: dict[str, ComponentRow] = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    error: str | None = None
    _scopes: dict[str, VisibleBusinesses] = field(default_factory=dict)

    @classmethod
    def from_layout(cls, source: str | None, catalog: BusinessContext) -> FinalBusinessContext:
        result = cls(catalog)
        if not source:
            result.error = "图片内容限制需要定稿布局"
            return result
        try:
            parsed = parse_compact_dsl_rows(source, expand_layouts=False)
        except ValueError:
            result.error = "无法解析图片内容限制所需的定稿布局"
            return result
        for row in parsed:
            if isinstance(row, ComponentRow):
                result.by_id[row.component_id] = row
            elif isinstance(row, DataRow):
                result.values[row.path] = row.value
        return result

    def rows(self, identity: str = "root") -> list[ComponentRow]:
        return subtree(identity, self.by_id)

    def scope(self, identity: str = "root") -> VisibleBusinesses:
        if identity not in self._scopes:
            self._scopes[identity] = self.catalog.visible(self.rows(identity))
        facts = self._scopes.get(identity)
        if facts is None:
            raise ValueError("Missing finalized business scope")
        return facts

    def payload(self) -> dict:
        root = self.by_id.get("root")
        children = root.children if root is not None else ()
        primary_id = self._primary_id()
        groups = []
        for row in self.rows():
            region = row.component_type in {"Region", "Group", "InfoBlock"}
            if region or row.component_id in children:
                groups.append({
                    "id": row.component_id, "role": row.props.get("role"),
                    **self.scope(row.component_id).payload(),
                })
        return {
            "source": "final-visible-content", "complete": bool(self.rows()) and self.error is None,
            **self.scope().payload(), "regions": groups,
            "primaryRegionId": primary_id,
            "primaryBusiness": self.scope(primary_id).single if primary_id else None,
        }

    def _primary_id(self) -> str | None:
        """只说明语义Layout已声明的主槽；不替代图片方向、区域类型等准入检查。"""
        result: str | None = None
        root = self.by_id.get("root")
        if root is None or root.component_type != "Layout":
            return result
        layout = root.props.get("layout")
        if layout == "W-content-side-slots" and len(root.children) == 3:
            result = root.children[0]
        elif layout == "W-top-bottom" and len(root.children) in {2, 3}:
            result = root.children[-2]
        return result

