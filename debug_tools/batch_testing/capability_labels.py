"""把数据路径、动作 token 与图标资源翻成中文，供期望对比展示。

标签优先取 ``widget_service/cloud/data/capabilities`` 下的能力声明：

* ``data_capabilities.json``：``outputSchema`` 的属性路径与属性描述；
* ``event_capabilities.json``：``actionTemplate.args.intentName`` 与事件描述；
* ``asset_capabilities.json``：``src`` 与图标概览描述。

能力未覆盖的 token 退回内置词表；仍无法翻译时保留原始 token，不臆造中文。
翻译只服务展示，不参与指纹与匹配计算。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CAPABILITY_ROOT = _REPO_ROOT / "widget_service" / "cloud" / "data" / "capabilities"
_CAMEL_WORD = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_LABEL_LIMIT = 18

_DATA_SEGMENTS = {
    "weather": "天气", "battery": "电量", "calendar": "日程", "countdown": "倒计时",
    "earphone": "耳机", "health": "健康", "sport": "运动", "time": "时间",
    "music": "音乐", "alarm": "闹钟", "reminder": "提醒", "steps": "步数",
    "current": "当前", "daily": "每日预报", "location": "地区", "condition": "天气状况",
    "temperature": "温度", "temperaturec": "温度", "temperaturetext": "温度",
    "feelslikec": "体感温度", "humidity": "湿度", "humiditypercent": "湿度",
    "airquality": "空气质量", "winddirection": "风向", "windlevel": "风力",
    "uvindex": "紫外线", "coldlevel": "感冒指数", "alertlevel": "气象预警",
    "date": "日期", "weekday": "星期", "rainprobabilitypercent": "降雨概率",
    "citycode": "城市代码", "districtname": "区县", "prefecturename": "城市",
    "updatedat": "更新时间", "level": "电量等级", "batterysoc": "剩余电量",
    "batterysocctext": "剩余电量", "batterylevel": "剩余电量",
    "chargingstatus": "充电状态", "chargingstatusdesc": "充电状态",
    "batterycapacityleveldesc": "电量等级", "healthstatusdesc": "健康状态",
    "pluggedtypedesc": "充电器类型", "batterytemperaturetext": "电池温度",
    "voltagetext": "电压", "nowcurrenttext": "电流", "isbatterypresenttext": "电池状态",
    "eventcount": "日程数量", "events": "日程列表", "title": "标题", "entityname": "实体名",
    "entityid": "实体 ID", "sendername": "发起方", "eventlocation": "地点",
    "description": "备注", "dtstart": "开始时间", "dtend": "结束时间",
    "timezone": "时区", "importanteventtype": "重要程度", "remindtime": "提醒时间",
    "oneclickservicetype": "轻服务", "oneclickservicelink": "轻服务链接",
    "isservicevalid": "服务是否可用", "startdate": "开始日期",
    "countdowndays": "倒计时天数", "isallday": "是否全天",
    "sleepscore": "睡眠得分", "sleepstatus": "睡眠状态", "steptext": "步数",
    "rankinglist": "耗电排行", "appname": "应用", "powertext": "耗电占比",
    "mostusedapps": "常用应用", "totalduration": "使用时长",
    "currentdate": "当前日期", "dayofweek": "星期", "lunardate": "农历日期",
}

_ACTION_FUNCTIONS = {
    "clickToApi": "调用服务", "clickToDeeplink": "跳转链接", "clickToIntent": "打开页面",
    "clickToApp": "打开应用", "clickToWeb": "打开网页",
}

_INTENTS = {
    "Weather_CityCode": "天气城市页", "Settings": "系统设置", "Music": "音乐",
    "Health": "健康", "Clock": "时钟", "OpenCamera": "相机", "CallPhone": "拨号",
    "CleanRAMMemory": "清理内存", "StartNavigate": "开始导航",
    "ViewCalendarEvent": "查看日程", "EnterMeeting": "进入会议",
    "OpenFlashlight": "打开手电筒", "CloseFlashlight": "关闭手电筒",
    "SetMobileData": "移动数据", "SetLocationSettingSwicth": "定位设置",
    "SetMicSettingSwicth": "麦克风设置", "SetSettingOption": "设置项",
    "SetSettingSwitch": "设置开关", "SetScreenUseTimeManageSwitch": "屏幕时间管理",
    "EnterSettingPage": "设置页", "Battery_Settings": "电池设置",
}

_CAPABILITIES = {
    "ViewWeather": "天气", "GetCalendarEvents": "日程",
    "GetCountdownDays": "倒计时", "GetEarphoneInfo": "耳机",
    "GetPhoneBatteryInfo": "电量", "GetHealthAndSportSummary": "健康与运动",
    "GetCurrentTime": "时间", "GetAppPowerConsumptionRanking": "耗电排行",
    "GetDailyMostUsage": "应用使用排行",
}


def _short(text: Any, limit: int = _LABEL_LIMIT) -> str:
    """取第一分句，去掉「点击」「当前」等无信息前缀，并按展示宽度截断。"""
    cleaned = str(text or "").strip()
    cleaned = re.split(r"[，。；;,、]", cleaned, maxsplit=1)[0].strip()
    for prefix in ("点击", "当前"):
        if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 2:
            cleaned = cleaned[len(prefix):]
    if len(cleaned) > limit:
        cleaned = cleaned[:limit]
    return cleaned


def _words(segment: str) -> list[str]:
    return [word.lower() for word in _CAMEL_WORD.split(segment) if word]


def _segment_label(segment: str) -> str:
    key = segment.rstrip("[]").lower()
    if key in _DATA_SEGMENTS:
        return _DATA_SEGMENTS[key]
    words = _words(segment.rstrip("[]"))
    translated = [_DATA_SEGMENTS[word] for word in words if word in _DATA_SEGMENTS]
    if len(translated) == len(words) and translated:
        return "".join(translated)
    return ""


def _walk_schema(properties: Any, prefix: str, out: dict[str, str]) -> None:
    if not isinstance(properties, dict):
        return
    for key, value in properties.items():
        if not isinstance(value, dict):
            continue
        relative = f"{prefix}/{key}" if prefix else key
        description = value.get("description")
        if description:
            out[relative] = str(description)
        _walk_schema(value.get("properties"), relative, out)
        items = value.get("items")
        if isinstance(items, dict):
            _walk_schema(items.get("properties"), relative + "[]", out)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, str], dict[str, str], dict[str, str], tuple[dict[str, str], ...]]:
    """一次性构建「绝对数据路径→描述」「意图→描述」「图标→概览」与事件清单。"""
    data_paths: dict[str, str] = {}
    intents: dict[str, str] = {}
    icons: dict[str, str] = {}
    events: list[dict[str, str]] = []
    if not _CAPABILITY_ROOT.is_dir():
        return data_paths, intents, icons, tuple(events)
    for directory in sorted(path for path in _CAPABILITY_ROOT.iterdir() if path.is_dir()):
        data_rows = _load_json(directory / "data_capabilities.json")
        for item in data_rows if isinstance(data_rows, list) else []:
            if not isinstance(item, dict):
                continue
            capability_id = str(item.get("id") or "")
            base = str(item.get("defaultWriteResultTo") or "")
            schema = item.get("outputSchema")
            schema = schema if isinstance(schema, dict) else {}
            properties: dict[str, str] = {}
            _walk_schema(schema.get("properties"), "", properties)
            for relative, description in properties.items():
                path = f"{base}/{relative}" if base else ""
                if path:
                    data_paths[path] = description
            if base and capability_id:
                data_paths.setdefault(base, _CAPABILITIES.get(capability_id, ""))
        event_rows = _load_json(directory / "event_capabilities.json")
        for item in event_rows if isinstance(event_rows, list) else []:
            if not isinstance(item, dict):
                continue
            template = item.get("actionTemplate")
            args = template.get("args") if isinstance(template, dict) else None
            intent = args.get("intentName") if isinstance(args, dict) else None
            call = template.get("call") if isinstance(template, dict) else None
            if isinstance(call, str) and isinstance(intent, str) and call and intent:
                events.append({
                    "eventId": str(item.get("id") or ""), "call": call, "intent": intent,
                    "description": str(item.get("description") or ""),
                })
            if isinstance(intent, str) and intent and intent not in intents:
                intents[intent] = str(item.get("description") or "")
        asset_rows = _load_json(directory / "asset_capabilities.json")
        for item in asset_rows if isinstance(asset_rows, list) else []:
            if not isinstance(item, dict):
                continue
            source = str(item.get("src") or "").lstrip("/")
            if source:
                icons[source] = str(
                    item.get("overviewDescription") or item.get("description") or ""
                )
    return data_paths, intents, icons, tuple(events)


def _capability_for(pointer: str) -> tuple[str, str]:
    """返回（最长匹配的能力根路径，剩余段）；没有匹配时返回空根。"""
    data_paths, _, _, _ = _tables()
    root = ""
    for candidate in data_paths:
        if pointer == candidate or pointer.startswith(candidate + "/"):
            if len(candidate) > len(root):
                root = candidate
    if not root:
        return "", pointer
    return root, pointer[len(root):].lstrip("/")


def data_label(pointer: str) -> str:
    """把数据路径翻成「能力 · 层级 · 字段」的中文；未知片段保留原文。"""
    token = str(pointer or "").strip()
    if not token.startswith("/"):
        if token in _CAPABILITIES:
            return _CAPABILITIES[token]
        parts = [part for part in re.split(r"[/.]", token) if part and part.lower() != "data"]
        return " · ".join(filter(None, (_segment_label(part) for part in parts)))
    data_paths, _, _, _ = _tables()
    root, rest = _capability_for(token)
    parts: list[str] = []
    if root:
        root_label = _segment_label(root.rsplit("/", 1)[-1])
        parts.append(root_label or _short(data_paths.get(root, "")))
    for segment in (item for item in rest.split("/") if item and item.lower() != "data"):
        parts.append(_segment_label(segment) or segment)
    label = " · ".join(filter(None, parts))
    exact = _short(data_paths.get(token, ""))
    return label or exact


def action_label(token: str) -> str:
    """把动作 token 翻成「动作函数 · 目标」；目标优先取事件能力描述。"""
    value = str(token or "").strip()
    if not value:
        return ""
    call, separator, identity = value.partition(":")
    call = call if separator else ""
    identity = identity if separator else value
    if identity.startswith("uri:"):
        target = "链接 " + identity[len("uri:"):]
    else:
        target = _INTENTS.get(identity, "")
        if not target:
            _, intent_descriptions, _, _ = _tables()
            description = intent_descriptions.get(identity, "")
            target = _short(description) if description else ""
        if not target:
            parts = [part for part in identity.replace("-", "_").split("_") if part]
            target = "".join(
                filter(None, (_segment_label(part) for part in parts))
            ) or identity
    function = _ACTION_FUNCTIONS.get(call, call)
    return " · ".join(part for part in (function, target) if part)


def icon_label(token: str) -> str:
    """图标以资源文件名匹配素材库概览；未知图标保留文件名。"""
    source = str(token or "").strip().lstrip("/")
    if not source:
        return ""
    _, _, icons, _ = _tables()
    description = icons.get(source, "")
    if not description:
        name = source.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        parts = [part for part in re.split(r"[_\-]", name) if part]
        translated = [part for part in (_segment_label(item) for item in parts) if part]
        description = "".join(translated) or name
    return _short(description)


def asset_key(value: str) -> str:
    """素材标识归一：去目录、扩展名与规格里的 ``asset.`` 前缀，小写。

    判断「是不是同一个素材」与「有没有在能力表声明过」都用这一套口径，
    免得比对与过滤在归一步骤上分叉。
    """
    name = str(value or "").strip().replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()
    if name.startswith("asset."):
        name = name[len("asset."):]
    return name.rsplit(".", 1)[0] if "." in name else name


def declared_asset_keys() -> frozenset[str]:
    """能力表声明过的素材标识集合。

    空集表示能力目录不可读：调用方按「不过滤」处理，避免把图标维度静默清空。
    """
    _, _, icons, _ = _tables()
    return frozenset(asset_key(source) for source in icons)


def build_labels(
    data: Iterable[str], actions: Iterable[str], icons: Iterable[str],
) -> dict[str, dict[str, str]]:
    """只返回与原文不同、确有中文的标签，避免前端重复展示原文。"""
    def collect(items: Iterable[str], translate) -> dict[str, str]:
        labels: dict[str, str] = {}
        for item in items:
            label = translate(item)
            if label and label != item:
                labels[item] = label
        return labels

    return {
        "data": collect(data, data_label),
        "actions": collect(actions, action_label),
        "icons": collect(icons, icon_label),
    }


@lru_cache(maxsize=1)
def options() -> dict[str, list[dict[str, str]]]:
    """导入期望时可选的三种 token：数据路径、动作与图标，都带中文标签。

    数据取能力声明里登记的全部出参路径，动作取事件声明里出现的 ``函数:意图`` 组合，
    图标取素材能力登记的 ``src``；三者与匹配时比较的 token 完全同形，供页面做下拉与模糊提示。
    """
    data_paths, _, icons, events = _tables()

    def rows(values: Iterable[str], translate) -> list[dict[str, str]]:
        # 能力声明的数组写作 ``daily[]``，而 DSL 指纹里是具体下标 ``daily/1``；
        # 给出 0 号槽位让候选本身就能命中，用户要别的槽位可以改数字。
        unique = sorted({item for item in values if item})
        table: dict[str, str] = {}
        for item in unique:
            table.setdefault(item.replace("[]", "/0"), translate(item) or item)
        return sorted(
            ({"value": value, "label": label} for value, label in table.items()),
            key=lambda row: (row["label"], row["value"]),
        )

    actions = [f"{event['call']}:{event['intent']}" for event in events]
    return {
        "data": rows(data_paths, data_label),
        "actions": rows(actions, action_label),
        "icons": rows(icons, icon_label),
    }
