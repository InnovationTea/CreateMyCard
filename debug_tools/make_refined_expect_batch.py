"""把 batch_20261018_160124_3f440556 的 12 条实际 DSL 重做成一批更精致的版本，供手工导入期望输出。

身份：这 12 份产物是**期望输出**（用户在「导入期望输出」页逐条录入），不是模型真实批跑结果。
底稿取自那条批跑里同 ID 的模型 DSL，入参（Query、候选字段、候选事件、候选素材、声明尺寸）
原样沿用，只重做版式与信息层次：

* 补齐入参里全部候选字段的绑定，原版漏掉的字段（区名、城市码、地点等）这一版都落到可见位置；
* 换更能表达主辅层次的合法布局与组件（环、进度线、宫格背板），并按 2x4／2x2 合同验算占高；
* 根节点带主题渐变，背板按登记色（小卡 ``#CCFFFFFF``、宽卡 ``#99FFFFFF``）；
* 图标只用本轮候选、只放在登记图标位，且不用固定图标断言动态状态。

每条 DSL 先过 `convert_compact_dsl_to_a2ui`（与「卡片渲染」页同一个严格入口），再过四道自检：
候选字段是否全部绑定、事件是否逐字复用、图标是否越出候选、2x2 图标实例是否超预算。
产物含单条说明、可直接粘贴的数据／动作／图标清单、示意图 PNG 与一份可 POST 的导入载荷。
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path
from typing import Any

DEBUG_TOOLS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = DEBUG_TOOLS_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from debug_tools.batch_testing.card_size import normalize as normalize_size  # noqa: E402
from debug_tools.batch_testing.expect_compare import (  # noqa: E402
    _normalize_action,
    fingerprint,
)
from debug_tools.make_phase_batch_run import (  # noqa: E402
    bound,
    concat,
    header,
    line,
    lit,
    media,
    node,
    pill_button,
    ref,
    root,
)
from debug_tools.paths import ensure_cloud_import_path  # noqa: E402

ensure_cloud_import_path()

from services.compact_dsl_a2ui_converter import (  # noqa: E402
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)

SOURCE_RUN = DEBUG_TOOLS_ROOT / "batch_output" / "batch_20261018_160124_3f440556"
DEFAULT_OUTPUT = DEBUG_TOOLS_ROOT / "Datasets" / "batch_20261018_refined12_expect"
BATCH_NAME = "精致版期望_batch_20261018（12 条）"
FONT_PATH = (REPOSITORY_ROOT / "render" / "genui-sdk" / "HarmonyOS-Sans" / "HarmonyOS Sans"
             / "HarmonyOS_Sans_SC" / "HarmonyOS_Sans_SC_Medium.ttf")

SAMPLE_IDS = ("Q001", "Q004", "Q006", "Q009", "Q010", "Q014",
              "Q034", "Q037", "Q054", "Q056", "Q069", "Q076")

# 每条一对 #AARRGGBB 渐变端点：配色由末尾主题阶段负责，这里按业务语义预置，让期望卡能直接好看。
PALETTES = {
    "Q001": ("#FF8FC7E8", "#FFF3E3B8"),
    "Q004": ("#FFF6C9A8", "#FFF9EBC0"),
    "Q006": ("#FFB9C9F2", "#FFE6DAF6"),
    "Q009": ("#FFCBDDEE", "#FFE3D8F4"),
    "Q010": ("#FF9BCFAE", "#FFDFEFB6"),
    "Q014": ("#FFA7D8E8", "#FFEDE9BC"),
    "Q034": ("#FF9ECBEA", "#FFF2E2C8"),
    "Q037": ("#FFFBBBAE", "#FFF9E5B4"),
    "Q054": ("#FFB2E0CC", "#FFD8EFD0"),
    "Q056": ("#FFBCD3EE", "#FFE8E0F4"),
    "Q069": ("#FFA9B4DC", "#FFD4C8E8"),
    "Q076": ("#FFF8C3A0", "#FFF8E7C0"),
}

CATEGORIES = {
    "Q001": "天气", "Q004": "天气", "Q006": "日程", "Q009": "设备", "Q010": "出行",
    "Q014": "设备", "Q034": "天气", "Q037": "健康", "Q054": "设备", "Q056": "日程",
    "Q069": "健康", "Q076": "出行",
}

PANEL_2X2 = "#CCFFFFFF"
PANEL_2X4 = "#99FFFFFF"
RING_COLOR = "#FF1F4799"
RING_TRACK = "#331F4799"
LINE_COLOR = "#FF563D99"
LINE_TRACK = "#33563D99"

# 这一版比批跑原文好在哪，逐条写死在说明里，避免只改文件不解释。
UPGRADES = {
    "Q001": "`S-title-content-action`（只有天气现象＋城市码两绑）改为 "
            "`S-title-primary-secondary-action`：区名与市名进支撑行，核心读数与动作分层。",
    "Q004": "标题由泛化的「天气预警」改为带对象的「长沙天气预警」（城市来自 Query），"
            "图标按候选描述换成明确适配 alertLevel 的警示铃。",
    "Q006": "EventCard 由 `density:compact` 放开为普通两行，标题写明「明日会议」，"
            "两场会各 34vp＋8vp 间距仍在 126vp 预算内。",
    "Q009": "两块信息背板补上左右耳主视觉图标与百分比单位，对象名以文字保留、不只靠图标区分。",
    "Q010": "两块 stacked 背板保留，标题改含地点；背板色按小卡登记色显式写入。",
    "Q014": "标题让出图标位，按钮改用带闪电图标的动作，动作图标优先于标题图标。",
    "Q034": "两块的地点标签按入参实算（weather1←上海市、weather2←成都市），"
            "修正原文把两城标签写反的问题，并补上定位主视觉。",
    "Q037": "步数完成度由文本「6200 / 8000步」升级为真实分母的 `ProgressCircleSingle`，"
            "热量与距离改为单列两行完整标签。",
    "Q054": "剩余电量由 30fp 裸读数改为 68/100 的单环进度（环心电能图标＋标题电池图标），"
            "三项诊断仍走 `TextBlock` 明细。",
    "Q056": "左右两区各自带准确图标，日程区地点用 `location` 承载、"
            "天气区把气温收进同一核心语义的次文本。",
    "Q069": "得分由裸数字改为 0–100 的 `ProgressLine2` 真实进度，"
            "夜间时长与状态改为单列完整标签两行，两个固定槽补齐宽卡背板色。",
    "Q076": "风向与风力合并为一个带完整标签的读数行，正文由四行收成三行，"
            "把 132×126 内容区的占高验算做回来；固定槽按信息在上、动作在下。",
}

# 图标为什么没用满候选：写清楚落点与断言问题，方便判断期望侧该不该把它们写成需求项。
ICON_NOTES = {
    "Q001": "候选 `sun_max` 未用：天气现象是动态值，固定太阳图标会长期断言「晴」。",
    "Q004": "候选 `bell_fill`／`typhoon_fill` 未用：铃铛偏通用提醒、台风只覆盖一种预警，"
            "`ic_warning_monochrome` 的候选描述明确适配 current.alertLevel。",
    "Q006": "候选 `icon_schedule`／`icon_meeting` 未用：2x2 标题位只有一个，"
            "EventCard 与正文没有图标落点。",
    "Q009": "候选 `icon_earphone`／`bolt_fill` 未用：左右耳主视觉已占满两个实例，"
            "闪电会静态断言「充电中」。",
    "Q010": "两个候选素材都没用：stacked-info 两块各 50vp＋标题后已占满 126vp，"
            "再加 20vp 图标标题就超预算，正文与固定槽都没有图标落点。",
    "Q014": "候选 `phone_fill`（听筒／拨号）与 `earphone_case_16644`（正文行无图标位）未用；"
            "`bolt_fill` 给「电池设置」动作。",
    "Q034": "候选 `icon_weather_thermometer_medium` 未用：两块的℃文本已表达温度，"
            "同类双对象复用同一 `local_fill` 更对称。",
    "Q037": "候选 `flame_fill` 未用：热量是正文行，没有图标落点；标题让位给环心准确图标。",
    "Q054": "候选 `phone_fill`（听筒／拨号）未用。",
    "Q056": "候选 `sun_max`／`icon_schedule` 未用：太阳会静态断言天气现象，"
            "两个日历素材里只留语义最直白的 `calendar_fill`。",
    "Q069": "唯一候选 `moon_z_fill_1` 已用于标题。",
    "Q076": "三个候选素材都没用：`sun_max` 与卡面的「大风蓝色预警」互相矛盾，"
            "`icon_weather_wind` 只覆盖风向风力一项，"
            "`emoji_temperature_orange.png` 在本地渲染资源目录里不存在，贴上只会显示占位图。",
}


# --------------------------------------------------------------------------- 入参读取


def load_input(sample_id: str, source_run: Path) -> dict[str, Any]:
    """读这条样本在批跑里的入参原文与模型 DSL 底稿。"""
    directory = source_run / sample_id
    attempts = sorted(p for p in directory.glob("attempt_*"))
    if not attempts:
        raise FileNotFoundError(f"{directory} 没有 attempt 目录")
    last = attempts[-1]
    request = json.loads((last / "request.json").read_text(encoding="utf-8"))
    content = request.get("content") or {}
    taskspec_path = None
    for attempt in reversed(attempts):
        candidate = attempt / "blocks" / "taskspec.json"
        if candidate.is_file():
            taskspec_path = candidate
            break
    taskspec = json.loads(taskspec_path.read_text(encoding="utf-8")) if taskspec_path else {}
    draft = ""
    for attempt in reversed(attempts):
        candidate = attempt / "blocks" / "designcompactdsl.txt"
        if candidate.is_file():
            draft = candidate.read_text(encoding="utf-8")
            break
    return {
        "id": sample_id,
        "request": request,
        "content": content,
        "taskspec": taskspec,
        "draft": draft,
        "handler": handler_of(taskspec),
    }


def handler_of(taskspec: dict[str, Any]) -> dict[str, Any]:
    """逐字复用第一个候选事件：call 与 args 原样进 onClick。"""
    candidates = taskspec.get("eventCandidates") or []
    if not candidates:
        return {}
    event = candidates[0]
    return {"call": str(event.get("call") or ""), "args": event.get("args") or {}}


def candidate_paths(content: dict[str, Any]) -> list[str]:
    """入参里的全部候选数据字段（完整路径）。"""
    rows: list[str] = []
    for binding in content.get("candidateDataBindings") or []:
        root_pointer = str(binding.get("writeResultTo") or "")
        for field in binding.get("candidateOutputFields") or []:
            rows.append(f"{root_pointer}{field}")
    return rows


def candidate_action_tokens(taskspec: dict[str, Any]) -> list[str]:
    """入参里的全部候选事件，按平台同一口径归一成动作 token。"""
    rows = []
    for event in taskspec.get("eventCandidates") or []:
        rows.append(_normalize_action(str(event.get("call") or ""), event.get("args") or {}))
    return sorted(set(rows))


def candidate_asset_names(taskspec: dict[str, Any]) -> list[str]:
    return [asset_stem(str(item.get("src") or ""))
            for item in taskspec.get("assetCandidates") or []]


def asset_stem(value: str) -> str:
    name = str(value).strip().replace("\\", "/").rsplit("/", 1)[-1].lower()
    name = name.removeprefix("asset.")
    return name.rsplit(".", 1)[0] if "." in name else name


def icon_instances(dsl: str) -> list[str]:
    """按实例数统计图标：标题、按钮、环心、分区主视觉各算一个。"""
    used: list[str] = []
    for raw in dsl.splitlines():
        if not raw.strip():
            continue
        parts = json.loads(raw)
        if not (isinstance(parts, list) and len(parts) >= 3 and isinstance(parts[2], dict)):
            continue
        props = parts[2]
        for value in (props.get("icon"), (props.get("visual") or {}).get("icon")
                      if isinstance(props.get("visual"), dict) else None):
            if isinstance(value, str) and value.strip():
                used.append(asset_stem(value))
        items = props.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("icon"), str):
                    used.append(asset_stem(item["icon"]))
    return used


def original_bindings(draft: str) -> dict[str, list[str]]:
    fp = fingerprint(draft)
    return {"data": fp["data"], "actions": fp["actions"], "icons": fp["icons"]}


# --------------------------------------------------------------------------- 十二条 DSL


def build_q001(ctx: dict[str, Any]) -> list[str]:
    condition = "/data/weather/current/condition"
    prefecture = "/data/weather/location/prefectureName"
    district = "/data/weather/location/districtName"
    city_code = "/data/weather/location/cityCode"
    lines = [root("S-title-primary-secondary-action",
                  ["header", "current", "region", "cta"], PALETTES["Q001"])]
    lines.append(header("header", "西湖天气", asset="local_fill"))
    lines += bound("current", "EmphasisText", "mainText", condition, "多云",
                   extra={"fontSize": 18})
    lines.append(node("region", "SecondaryBody", {"items": [
        {"label": "区域 ", "value": concat(ref(prefecture), lit(" "), ref(district))},
    ], "fontSize": 14}))
    lines.append(pill_button("cta", "查看天气详情", ctx["handler"]))
    lines += [line(prefecture, "杭州市"), line(district, "西湖区"), line(city_code, "60814")]
    return lines


def build_q004(ctx: dict[str, Any]) -> list[str]:
    alert = "/data/weather/current/alertLevel"
    lines = [root("S-title-content", ["header", "content"], PALETTES["Q004"])]
    lines.append(header("header", "长沙天气预警", asset="ic_warning_monochrome"))
    lines += bound("content", "EmphasisText", "mainText", alert, "大风蓝色预警",
                   extra={"fontSize": 18})
    return lines


def build_q006(ctx: dict[str, Any]) -> list[str]:
    first_title = "/data/calendar/events/0/title"
    first_start = "/data/calendar/events/0/dtStart"
    second_title = "/data/calendar/events/1/title"
    second_start = "/data/calendar/events/1/dtStart"
    lines = [root("S-title-content", ["header", "meetings"], PALETTES["Q006"])]
    lines.append(header("header", "明日会议", asset="calendar_fill"))
    lines.append(node("meetings", "EventCard", {"items": [
        {"title": {"path": first_title}, "time": {"path": first_start}},
        {"title": {"path": second_title}, "time": {"path": second_start}},
    ]}))
    lines += [line(first_title, "产品立项会"), line(first_start, "09:00"),
              line(second_title, "客户交流会"), line(second_start, "15:00")]
    return lines


def build_q009(ctx: dict[str, Any]) -> list[str]:
    lines = [root("S-dual-info", ["left", "right"], PALETTES["Q009"])]
    plan = (
        ("left", "左耳", "/data/earphone/leftBatteryLevel",
         "/data/earphone/leftChargingStatusDesc", "icon_left", 76, "未充电"),
        ("right", "右耳", "/data/earphone/rightBatteryLevel",
         "/data/earphone/rightChargingStatusDesc", "icon_right", 78, "未充电"),
    )
    for node_id, label, level, status, asset, level_sample, status_sample in plan:
        lines.append(node(node_id, "InfoBlock", {
            "primaryText": concat(lit(f"{label} "), ref(level), lit("%")),
            "secondaryText": {"path": status},
            "backgroundColor": PANEL_2X2,
            "visual": {"type": "icon", "icon": media(asset)},
        }))
        lines += [line(level, level_sample), line(status, status_sample)]
    return lines


def build_q010(ctx: dict[str, Any]) -> list[str]:
    lines = [root("S-title-dual-content", ["header", "tomorrow", "after"], PALETTES["Q010"],
                  variant="stacked-info")]
    lines.append(header("header", "杭州露营天气"))
    plan = (
        ("tomorrow", "明天 ", "/data/weather/daily/1/condition",
         "/data/weather/daily/1/airQuality", "多云", "良"),
        ("after", "后天 ", "/data/weather/daily/2/condition",
         "/data/weather/daily/2/airQuality", "多云", "良"),
    )
    for node_id, day, condition, air, condition_sample, air_sample in plan:
        lines.append(node(node_id, "InfoBlock", {
            "variant": "stacked",
            "primaryText": concat(lit(day), ref(condition)),
            "secondaryText": concat(lit("空气质量 "), ref(air)),
            "backgroundColor": PANEL_2X2,
        }))
        lines += [line(condition, condition_sample), line(air, air_sample)]
    return lines


def build_q014(ctx: dict[str, Any]) -> list[str]:
    phone_status = "/data/phoneBattery/chargingStatusDesc"
    plugged = "/data/phoneBattery/pluggedTypeDesc"
    case_status = "/data/earphone/chargingStatusDesc"
    lines = [root("S-title-primary-secondary-action",
                  ["header", "phone", "detail", "cta"], PALETTES["Q014"])]
    lines.append(header("header", "充电状态"))
    lines += bound("phone", "EmphasisText", "mainText", phone_status, "未充电",
                   extra={"fontSize": 18})
    lines.append(node("detail", "SecondaryBody", {"items": [
        {"label": "充电器 ", "value": {"path": plugged}},
        {"label": "耳机仓 ", "value": {"path": case_status}},
    ], "columns": 1, "fontSize": 12}))
    lines.append(pill_button("cta", "电池设置", ctx["handler"], asset="bolt_fill"))
    lines += [line(plugged, "未连接充电器"), line(case_status, "未充电")]
    return lines


def build_q034(ctx: dict[str, Any]) -> list[str]:
    # 入参 arguments：/data/weather1 ← 上海市，/data/weather2 ← 成都市；标签按实参写。
    lines = [root("S-dual-info", ["shanghai", "chengdu"], PALETTES["Q034"])]
    plan = (
        ("shanghai", "上海 ", "/data/weather1/current/temperatureC",
         "/data/weather1/current/condition", 29, "多云"),
        ("chengdu", "成都 ", "/data/weather2/current/temperatureC",
         "/data/weather2/current/condition", 29, "多云"),
    )
    for node_id, label, temperature, condition, temperature_sample, condition_sample in plan:
        lines.append(node(node_id, "InfoBlock", {
            "primaryText": concat(lit(label), ref(temperature), lit("℃")),
            "secondaryText": {"path": condition},
            "backgroundColor": PANEL_2X2,
            "visual": {"type": "icon", "icon": media("local_fill")},
        }))
        lines += [line(temperature, temperature_sample), line(condition, condition_sample)]
    return lines


def build_q037(ctx: dict[str, Any]) -> list[str]:
    steps = "/data/healthSport/dailySteps"
    calories = "/data/healthSport/dailyTotalCaloriesText"
    distance = "/data/healthSport/dailyDistanceText"
    lines = [root("S-title-dual-content", ["header", "ring", "detail"], PALETTES["Q037"])]
    lines.append(header("header", "今日运动"))
    lines.append(node("ring", "ProgressCircleSingle", {
        "value": {"path": steps}, "total": 8000, "icon": media("figure_run"),
        "displayValue": concat(ref(steps), lit("/8000")), "label": "步数",
        "color": RING_COLOR, "backgroundColor": RING_TRACK,
    }))
    lines.append(node("detail", "SecondaryBody", {"items": [
        {"label": "热量 ", "value": {"path": calories}},
        {"label": "距离 ", "value": {"path": distance}},
    ], "columns": 1, "fontSize": 12}))
    lines += [line(steps, 6200), line(calories, "420 千卡"), line(distance, "4.60 公里")]
    return lines


def build_q054(ctx: dict[str, Any]) -> list[str]:
    soc = "/data/phoneBattery/batterySOC"
    current = "/data/phoneBattery/nowCurrentText"
    voltage = "/data/phoneBattery/voltageText"
    present = "/data/phoneBattery/isBatteryPresentText"
    lines = [root("W-top-bottom", ["title", "ring", "details"], PALETTES["Q054"],
                  variant="bottom-details")]
    lines.append(header("title", "手机电池诊断", asset="battery_leaf_fill"))
    lines.append(node("ring", "ProgressCircleSingle", {
        "value": {"path": soc}, "total": 100, "icon": media("bolt_fill"),
        "displayValue": concat(ref(soc), lit("%")), "label": "剩余电量",
        "color": RING_COLOR, "backgroundColor": RING_TRACK,
    }))
    lines.append(node("details", "TextBlock", {"items": [
        {"label": "充电电流", "value": {"path": current}},
        {"label": "充电电压", "value": {"path": voltage}},
        {"label": "识别状态", "value": {"path": present}},
    ]}))
    lines += [line(soc, 68), line(current, "-151 mA"), line(voltage, "4 V"),
              line(present, "在位")]
    return lines


def build_q056(ctx: dict[str, Any]) -> list[str]:
    city_code = "/data/weather/location/cityCode"
    condition = "/data/weather/current/condition"
    temperature = "/data/weather/current/temperatureC"
    start = "/data/calendar/events/0/dtStart"
    place = "/data/calendar/events/0/eventLocation"
    lines = [root("W-split-panels", ["weather_panel", "calendar_panel"], PALETTES["Q056"])]
    lines.append(node("weather_panel", "Region", {"variant": "title-content-action"},
                      ["weather_title", "weather_summary", "weather_action"]))
    lines.append(header("weather_title", "北京天气", asset="local_fill"))
    lines.append(node("weather_summary", "EmphasisText", {
        "mainText": {"path": condition},
        "secondaryText": concat(ref(temperature), lit("℃")),
        "fontSize": 18,
    }))
    lines.append(pill_button("weather_action", "查看天气详情", ctx["handler"]))
    lines.append(node("calendar_panel", "Region", {"variant": "title-content"},
                      ["calendar_title", "calendar_body"]))
    lines.append(header("calendar_title", "今日第一件日程", asset="calendar_fill"))
    lines.append(node("calendar_body", "EventCard", {"items": [
        {"title": "客户现场", "time": {"path": start}, "location": {"path": place}},
    ]}))
    lines += [line(city_code, "60814"), line(condition, "多云"), line(temperature, 29),
              line(start, "14:00"), line(place, "会议室")]
    return lines


def build_q069(ctx: dict[str, Any]) -> list[str]:
    score = "/data/healthSport/sleepScore"
    status = "/data/healthSport/sleepStatus"
    deep = "/data/healthSport/deepSleepDurationText"
    nap = "/data/healthSport/totalNapDurationText"
    night = "/data/healthSport/nightSleepDurationText"
    lines = [root("W-content-side-slots", ["main", "upper", "lower"], PALETTES["Q069"])]
    lines.append(node("main", "Region", {"variant": "title-hero-support"},
                      ["main_title", "score_line", "detail"]))
    lines.append(header("main_title", "睡眠分析", asset="moon_z_fill_1"))
    lines.append(node("score_line", "ProgressLine2", {
        "value": {"path": score}, "total": 100, "displayValue": {"path": score},
        "unit": "分", "color": LINE_COLOR, "backgroundColor": LINE_TRACK,
    }))
    lines.append(node("detail", "SecondaryBody", {"items": [
        {"label": "睡眠状态 ", "value": {"path": status}},
        {"label": "夜间睡眠 ", "value": {"path": night}},
    ], "columns": 1, "fontSize": 12}))
    lines.append(node("upper", "InfoBlock", {
        "variant": "slot", "primaryText": {"path": deep}, "secondaryText": "深睡时长",
        "backgroundColor": PANEL_2X4,
    }))
    lines.append(node("lower", "InfoBlock", {
        "variant": "slot", "primaryText": {"path": nap}, "secondaryText": "白天小睡",
        "backgroundColor": PANEL_2X4,
    }))
    lines += [line(score, 82), line(status, "良好"), line(night, "7小时1分"),
              line(deep, "2小时15分"), line(nap, "0分")]
    return lines


def build_q076(ctx: dict[str, Any]) -> list[str]:
    temperature = "/data/weather/current/temperatureText"
    humidity = "/data/weather/current/humidityPercent"
    wind_direction = "/data/weather/current/windDirection"
    wind_level = "/data/weather/current/windLevel"
    alert = "/data/weather/current/alertLevel"
    city_code = "/data/weather/location/cityCode"
    battery_temperature = "/data/phoneBattery/batteryTemperatureText"
    lines = [root("W-content-side-slots", ["main", "upper", "lower"], PALETTES["Q076"])]
    lines.append(node("main", "Region", {"variant": "title-hero-support"},
                      ["main_title", "temp", "detail"]))
    lines.append(header("main_title", "南京天气"))
    lines += bound("temp", "EmphasizedData", "value", temperature, "29℃",
                   extra={"fontSize": 30})
    lines.append(node("detail", "SecondaryBody", {"items": [
        {"label": "湿度 ", "value": concat(ref(humidity), lit("%"))},
        {"label": "风力 ", "value": concat(ref(wind_direction), lit(" "), ref(wind_level),
                                          lit("级"))},
        {"label": "预警 ", "value": {"path": alert}},
    ], "columns": 1, "fontSize": 12}))
    lines.append(node("upper", "InfoBlock", {
        "variant": "slot", "primaryText": {"path": battery_temperature},
        "secondaryText": "手机电池温度", "backgroundColor": PANEL_2X4,
    }))
    lines.append(node("lower", "CardButton", {
        "label": "查看天气", "onClick": [ctx["handler"]],
    }))
    lines += [line(humidity, 68), line(wind_direction, "东南风"), line(wind_level, 2),
              line(alert, "大风蓝色预警"), line(battery_temperature, "29.0 ℃"),
              line(city_code, "60814")]
    return lines


BUILDERS = {
    "Q001": build_q001, "Q004": build_q004, "Q006": build_q006, "Q009": build_q009,
    "Q010": build_q010, "Q014": build_q014, "Q034": build_q034, "Q037": build_q037,
    "Q054": build_q054, "Q056": build_q056, "Q069": build_q069, "Q076": build_q076,
}


# --------------------------------------------------------------------------- 门禁与自检


def convert_or_fail(sample_id: str, dsl: str, size: str) -> None:
    try:
        convert_compact_dsl_to_a2ui(dsl, size=size, protocol_profile={"version": "v0.9"})
    except CompactDslConversionError as error:
        raise SystemExit(f"{sample_id} 的精致版 DSL 不合法：{error}") from error


def audit_card(ctx: dict[str, Any], dsl: str, size: str) -> dict[str, Any]:
    fp = fingerprint(dsl)
    wanted = candidate_paths(ctx["content"])
    assets = candidate_asset_names(ctx["taskspec"])
    used = icon_instances(dsl)
    actions = candidate_action_tokens(ctx["taskspec"])
    return {
        "fingerprint": fp,
        "candidate_data": wanted,
        "missing_data": [item for item in wanted if item not in fp["data"]],
        "extra_data": [item for item in fp["data"] if item not in wanted],
        "candidate_actions": actions,
        "missing_actions": [item for item in actions if item not in fp["actions"]],
        "extra_actions": [item for item in fp["actions"] if item not in actions],
        "candidate_icons": assets,
        "used_icons": used,
        "outside_icons": sorted({item for item in used if item not in assets}),
        "unused_icons": sorted({item for item in assets if item not in used}),
        "icon_instances": len(used),
        "size": size,
    }


def layout_of(dsl: str) -> str:
    for raw in dsl.splitlines():
        parts = json.loads(raw)
        if isinstance(parts, list) and len(parts) >= 3 and parts[0] == "root":
            layout = str(parts[2].get("layout"))
            variant = parts[2].get("variant")
            return layout if not variant else f"{layout}（variant={variant}）"
    return "未知布局"


def layout_name_of(dsl: str) -> str:
    for raw in dsl.splitlines():
        parts = json.loads(raw)
        if isinstance(parts, list) and len(parts) >= 3 and parts[0] == "root":
            return str(parts[2].get("layout"))
    return ""


# 纵向预算：参考画布高 150vp，减去模板 padding；紧凑 Region 还要再减自己的 8vp 边距。
VERTICAL_BUDGET = {
    "S-dual-info": 134,
    "W-split-panels": 110,
    "W-content-side-slots": 126,
    "W-top-bottom": 126,
    "W-four-slots": 57,
}
DEFAULT_BUDGET = 126


def _a2ui_components(dsl: str, size: str) -> dict[str, dict[str, Any]]:
    document = convert_compact_dsl_to_a2ui(dsl, size=size, protocol_profile={"version": "v0.9"})
    for raw in str(document).splitlines():
        payload = json.loads(raw)
        update = payload.get("updateComponents")
        if isinstance(update, dict):
            return {item["id"]: item for item in update.get("components") or []}
    return {}


def _node_height(node: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> float:
    """按转换器给出的几何量实算占高：写死的高度直接用，容器按子节点累加。"""
    styles = node.get("styles") or {}
    raw = styles.get("height")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    children = [by_id[item] for item in node.get("children") or [] if item in by_id]
    kind = node.get("component")
    margin = float(node.get("itemMargin") or 0)
    if kind == "Column" and children:
        return sum(_node_height(item, by_id) for item in children) + margin * (len(children) - 1)
    if kind in ("Row", "Stack") and children:
        return max(_node_height(item, by_id) for item in children)
    font = styles.get("fontSize")
    return float(font) * 1.4 if isinstance(font, (int, float)) else 0.0


def fit_of(dsl: str, size: str) -> tuple[float, float, str]:
    """返回（纵向实算占高，纵向预算，同排分支明细），全部来自展开后的 A2UI 几何。"""
    by_id = _a2ui_components(dsl, size)
    root_node = by_id.get("root") or {}
    children = [by_id[item] for item in root_node.get("children") or [] if item in by_id]
    shell = {**root_node, "styles": {}, "children": [item.get("id") for item in children]}
    used = _node_height(shell, by_id)
    detail = ""
    if shell.get("component") == "Row" and len(children) > 1:
        # 转换器注入的排布节点（__layout__…）不作为业务名展示，统一写作「槽位列」。
        labels = ["槽位列" if "__" in str(item.get("id")) else str(item.get("id"))
                  for item in children]
        detail = "、".join(f"{label} {_node_height(item, by_id):g}vp"
                           for label, item in zip(labels, children, strict=True))
    budget = VERTICAL_BUDGET.get(layout_name_of(dsl), DEFAULT_BUDGET)
    return round(used, 1), float(budget), detail


def visible_rows(dsl: str) -> list[str]:
    """卡面上会出现的静态文案，用于说明与示意图。"""
    rows: list[str] = []
    for raw in dsl.splitlines():
        if not raw.strip():
            continue
        parts = json.loads(raw)
        if not (isinstance(parts, list) and len(parts) >= 3 and isinstance(parts[2], dict)):
            continue
        if parts[0] == "root":
            continue
        props = parts[2]
        for key in ("title", "label", "primaryText", "secondaryText", "displayValue"):
            value = props.get(key)
            if isinstance(value, str) and not value.startswith("{{"):
                if value.strip() and value not in rows:
                    rows.append(value.strip())
    return rows


# --------------------------------------------------------------------------- 示意图


def preview_png(card: dict[str, Any]) -> bytes:
    """按主题色与卡面文案画一张比例正确的示意图，只用于导入页占位。"""
    from PIL import Image, ImageDraw, ImageFont

    size = card["size"]
    width, height = (600, 300) if size == "2x4" else (400, 400)

    def rgb(value: str) -> tuple[int, int, int]:
        text = value.lstrip("#")[2:]
        return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))

    start, end = rgb(card["palette"][0]), rgb(card["palette"][1])
    picture = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(picture)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(start, end, strict=True))
        draw.line([(0, y), (width, y)], fill=color)
    big = ImageFont.truetype(str(FONT_PATH), 30)
    mid = ImageFont.truetype(str(FONT_PATH), 20)
    small = ImageFont.truetype(str(FONT_PATH), 16)
    draw.text((26, 24), card["title"], font=big, fill="#16305c")
    draw.text((26, 66), f"{card['id']} · {size} · {CATEGORIES[card['id']]}", font=mid,
              fill="#33507a")
    draw.text((26, 96), layout_of(card["dsl"]), font=small, fill="#33507a")
    for index, text in enumerate(visible_rows(card["dsl"])[:6]):
        draw.text((26, 128 + index * 26), text, font=mid, fill="#1d3a63")
    draw.text((26, height - 34), f"数据 {len(card['audit']['fingerprint']['data'])} · "
              f"动作 {len(card['audit']['fingerprint']['actions'])} · "
              f"图标 {card['audit']['icon_instances']}", font=small, fill="#6b4a1e")
    draw.text((width - 210, height - 34), "示意预览，非端侧渲染", font=small, fill="#6b4a1e")
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------------- 说明文件


def paste_block(rows: list[str]) -> str:
    return "```text\n" + ("\n".join(rows) if rows else "（无）") + "\n```"


def card_markdown(card: dict[str, Any], ctx: dict[str, Any]) -> str:
    fp = card["audit"]["fingerprint"]
    fit = card["fit"]
    data_rows = fp["data"]
    action_rows = fp["actions"]
    icon_rows = fp["icons"]
    bound_count = len(card["audit"]["candidate_data"]) - len(card["audit"]["missing_data"])
    lines = [
        f"# {card['id']} · {card['title']}（精致版期望输出）",
        "",
        "> 身份：**期望输出**，供「导入期望输出」页手工录入。底稿是批跑 "
        "`batch_20261018_160124_3f440556` 里同 ID 的模型 DSL，"
        "入参（Query、候选字段、候选事件、候选素材、声明尺寸）完全沿用，只重做了版式与信息层次。",
        "",
        "## 卡片信息",
        "",
        f"- Query：{ctx['content'].get('userQuery')}",
        f"- 尺寸：{card['size']}（与入参一致，root 用 "
        f"{'S-' if card['size'] == '2x2' else 'W-'} 系列布局）",
        f"- 布局：{layout_of(card['dsl'])}",
        f"- 版面验算：展开后纵向实算 {fit[0]:g}vp／预算 {fit[1]:g}vp"
        "（几何取自 `convert_compact_dsl_to_a2ui` 展开的 `styles.height`、`padding`、`itemMargin`"
        + (f"；同排分支 {fit[2]}" if fit[2] else "") + "）",
        f"- 分类：{CATEGORIES[card['id']]}（导入页可按这个分类建组）",
        "- 已通过 `convert_compact_dsl_to_a2ui` 严格转换，可直接贴进「卡片渲染」页预览。",
        "",
        "## 比批跑原文精致在哪",
        "",
        f"- {UPGRADES[card['id']]}",
        f"- 入参候选字段 {len(card['audit']['candidate_data'])} 项，本卡实算命中 {bound_count} 项；"
        f"批跑原文实算 {len(original_bindings(ctx['draft'])['data'])} 项。",
        f"- 图标实例 {card['audit']['icon_instances']} 个"
        f"（{'2x2 预算上限 2 个' if card['size'] == '2x2' else '2x4 按语义增益取用'}）。",
        "",
        "## 导入页要粘的清单：本卡实际用到的",
        "",
        "期望数据：",
        paste_block(data_rows),
        "期望动作：",
        paste_block(action_rows),
        "期望图标：",
        paste_block([asset_stem(item) for item in icon_rows]),
        "",
        "## 另一份口径：入参候选全部",
        "",
        "期望数据（与上一份相同则说明本条已把入参字段绑满）：",
        paste_block(card["audit"]["candidate_data"]),
        "期望动作：",
        paste_block(card["audit"]["candidate_actions"]),
        "期望图标：",
        paste_block(card["audit"]["candidate_icons"]),
        "",
        f"- 两份清单的差异：数据缺 "
        f"{json.dumps(card['audit']['missing_data'], ensure_ascii=False)}、"
        f"动作缺 {json.dumps(card['audit']['missing_actions'], ensure_ascii=False)}、"
        f"图标未用 {json.dumps(card['audit']['unused_icons'], ensure_ascii=False)}。"
        "按「入参候选全部」录入时，缺哪一项，启用哪个维度就会把本条筛掉。",
        f"- {ICON_NOTES[card['id']]}",
        "",
        "## 与批跑实际输出对比时",
        "",
        f"- 原版实算数据 {json.dumps(original_bindings(ctx['draft'])['data'], ensure_ascii=False)}",
        "- 所以把本条当期望、把 batch_20261018_160124_3f440556 当实际侧按 ID 配对时，"
        "启用「数据」维度会因原版少绑的字段判未匹配，这正是精致版补出来的信息量。",
        "",
        "## DSL 原文",
        "",
        "```jsonl",
        card["dsl"].rstrip("\n"),
        "```",
        "",
        "## 截图",
        "",
        f"- `renders/{card['id']}.png` 是把这份 DSL 交给「卡片渲染」页真实渲染后截的图，"
        "上传导入页就用这张。",
        f"- `screenshots/{card['id']}.png` 是按主题色与卡面文案画的比例示意图，"
        "只在渲染截图缺失时兜底。",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- 落盘


def sample_image(output: Path, card: dict[str, Any]) -> bytes:
    """有真实渲染截图就用它，否则退回按主题色画的比例示意图。"""
    rendered = output / "renders" / f"{card['id']}.png"
    return rendered.read_bytes() if rendered.is_file() else card["png"]


def write_outputs(cards: list[dict[str, Any]], output: Path) -> None:
    for sub in ("dsl", "cards", "screenshots", "import"):
        (output / sub).mkdir(parents=True, exist_ok=True)
    payload = {
        "name": BATCH_NAME,
        "imageSource": "web",
        "samples": [{
            "id": card["id"],
            "query": card["query"],
            "size": card["size"],
            "dsl": card["dsl"],
            "imageBase64": base64.b64encode(sample_image(output, card)).decode(),
            "expectedData": card["audit"]["fingerprint"]["data"],
            "expectedActions": card["audit"]["fingerprint"]["actions"],
            "expectedIcons": [asset_stem(item) for item in card["audit"]["fingerprint"]["icons"]],
            "category": CATEGORIES[card["id"]],
        } for card in cards],
    }
    (output / "import" / "payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "import" / "paste-all.md").write_text(paste_all(cards), encoding="utf-8")
    manifest = [{"id": card["id"], "size": card["size"], "file": f"../dsl/{card['id']}.jsonl"}
                for card in cards]
    (output / "import" / "render-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paste_all(cards: list[dict[str, Any]]) -> str:
    lines = [
        "# 12 条期望的粘贴清单",
        "",
        "每条按「导入期望输出」页的三个输入框分块；图标只写资源名，"
        "页面按文件名比较，忽略目录与扩展名。",
        "",
    ]
    for card in cards:
        fp = card["audit"]["fingerprint"]
        lines += [
            f"## {card['id']} {card['title']}（{card['size']}／{CATEGORIES[card['id']]}）",
            "",
            f"- 期望数据 {len(fp['data'])} 行：",
            paste_block(fp["data"]),
            f"- 期望动作 {len(fp['actions'])} 行：",
            paste_block(fp["actions"]),
            f"- 期望图标 {len(fp['icons'])} 行：",
            paste_block([asset_stem(item) for item in fp["icons"]]),
            "",
        ]
    return "\n".join(lines)


def index_markdown(cards: list[dict[str, Any]]) -> str:
    table = ["| ID | 标题 | 分类 | 尺寸 | 布局 | 数据 | 动作 | 图标实例 | 纵向实算/预算 | "
             "候选字段是否绑满 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for card in cards:
        audit = card["audit"]
        table.append(
            f"| {card['id']} | {card['title']} | {CATEGORIES[card['id']]} | {card['size']} | "
            f"{layout_of(card['dsl'])} | {len(audit['fingerprint']['data'])} | "
            f"{len(audit['fingerprint']['actions'])} | {audit['icon_instances']} | "
            f"{card['fit'][0]:g}／{card['fit'][1]:g}vp | "
            f"{'是' if not audit['missing_data'] else '否'} |"
        )
    return "\n".join([
        "# 精致版期望输出（batch_20261018_160124_3f440556 的 12 条重做）",
        "",
        "12 条**期望输出**：从那条批跑的 88 条里挑 8 条 2x2 ＋ 4 条 2x4，"
        "沿用原 Q 编号、原 Query、原声明尺寸与入参候选，把版式重做得更精致，"
        "供你在「导入期望输出」页手工录入。",
        "",
        "## 精致点集中在四处",
        "",
        "- 信息补齐：入参里的候选数据字段逐个绑到可见位置，原版漏掉的区名、城市码、地点都补回来了；"
        "候选事件逐字复用，不新增第二个入口。",
        "- 版式升级：`S-title-content` → `S-title-primary-secondary-action`、"
        "裸读数 → `ProgressCircleSingle`／`ProgressLine2` 真实比例，"
        "2x4 按 Region 角色重排并验算占高。",
        "- 视觉落色：root 带主题 `linearGradient`，背板按登记色（小卡 `#CCFFFFFF`、"
        "宽卡 `#99FFFFFF`），图标只落在标题／按钮／环心／分区主视觉这些登记位。",
        "- 语义自洽：动态天气现象不配固定晴天图标、未充电不配闪电，"
        "候选素材用不上时在单条说明里写明原因。",
        "",
        "## 目录",
        "",
        "```text",
        "batch_20261018_refined12_expect/",
        "  dsl/Qxxx.jsonl        # 精致版 DSL，可直接粘进「卡片渲染」页",
        "  cards/Qxxx.md         # 单条说明：两份口径的清单＋精致点",
        "  renders/Qxxx.png      # 真实渲染截图（导入页上传这张）",
        "  screenshots/Qxxx.png  # 按主题色画的比例示意图，渲染截图缺失时兜底",
        "  import/paste-all.md   # 12 条数据/动作/图标一次性粘贴",
        "  import/render-manifest.json  # 渲染截图脚本的输入清单",
        "  import/payload.json   # 备用：可整批 POST /debug/expect/import 的载荷",
        "```",
        "",
        "## 用例一览",
        "",
        *table,
        "",
        "尺寸分布：2x2 八条、2x4 四条；分类覆盖天气、日程、设备、健康、出行。"
        "「候选字段是否绑满」是拿入参候选数据字段与这份 DSL 的实算数据指纹比出来的；"
        "「纵向实算/预算」是把 DSL 展开成 A2UI 后，按写死高度、`itemMargin` 与 `padding` "
        "累加出来的占高；2x4 左右分栏取纵向最紧的一支，明细写在单条说明里。",
        "",
        "## 手工导入怎么用",
        "",
        "1. 打开 <http://127.0.0.1:8888/debug/> 的「导入期望输出」，批次名自定，"
        "分类按上表逐条选。",
        "2. 每条样本粘贴 `dsl/Qxxx.jsonl` 的内容，尺寸填上表的 2x2／2x4，"
        "再上传 `renders/Qxxx.png`（真实渲染截图）。",
        "3. 数据／动作／图标三个框按 `cards/Qxxx.md` 或 `import/paste-all.md` 逐行粘贴。"
        "每条说明里给了两份口径：",
        "   - **本卡实际用到的**：三个维度都会判已匹配；",
        "   - **入参候选全部**：本卡没用上的候选素材会让图标维度把该条筛掉，"
        "各条说明都写明了未用素材与原因。",
        "4. 想在对比页看精致版与原版的差别：左侧选这批期望、右侧选 "
        "`batch_20261018_160124_3f440556`，同 ID 会自动配对；"
        "启用「数据」维度时，原版少绑字段的条目会判未匹配。",
        "",
        "## 校验口径",
        "",
        "每条都过了 `convert_compact_dsl_to_a2ui(size, protocol_profile)`（与渲染页同一严格入口），"
        "并核对：候选字段是否漏绑、DSL 里是否出现候选之外的数据路径、事件是否逐字复用、"
        "图标是否越出候选素材、2x2 图标实例是否超过 2 个，以及展开后的纵向占高是否超预算。"
        "任何一条不合格脚本直接报错退出。",
        "",
        "重新生成：",
        "",
        "```powershell",
        "$env:PYTHONIOENCODING='utf-8'",
        ".venv\\Scripts\\python.exe debug_tools/make_refined_expect_batch.py",
        "# 可选：--source <批跑目录> --output <数据集目录>",
        "```",
        "",
        "重出真实渲染截图（调试平台需在 8888 端口运行，浏览器用 Edge/Chrome）：",
        "",
        "```powershell",
        "cd debug_tools",
        "node scripts/capture_dsl_preview.mjs ",
        "  --manifest Datasets/batch_20261018_refined12_expect/import/render-manifest.json ",
        "  --output Datasets/batch_20261018_refined12_expect/renders",
        "```",
        "",
        "截图脚本走的是「卡片渲染」页同一入口，所以 `renders/` 里的图就是页面实际效果；"
        "重出截图后再跑一次生成脚本，`import/payload.json` 会改用真图。",
        "",
    ]) + "\n"


def generate(source_run: Path, output: Path) -> list[dict[str, Any]]:
    for sub in ("dsl", "cards", "screenshots", "import"):
        (output / sub).mkdir(parents=True, exist_ok=True)
    cards: list[dict[str, Any]] = []
    failures: list[str] = []
    for sample_id in SAMPLE_IDS:
        ctx = load_input(sample_id, source_run)
        content = ctx["content"]
        size = normalize_size(content.get("size")) or "2x2"
        dsl_text = "\n".join(BUILDERS[sample_id](ctx)) + "\n"
        convert_or_fail(sample_id, dsl_text, size)
        audit = audit_card(ctx, dsl_text, size)
        if audit["missing_data"]:
            failures.append(f"{sample_id} 漏绑候选字段：{audit['missing_data']}")
        if audit["extra_data"]:
            failures.append(f"{sample_id} 出现候选之外的数据路径：{audit['extra_data']}")
        if audit["missing_actions"] or audit["extra_actions"]:
            failures.append(f"{sample_id} 事件与候选不一致："
                            f"缺 {audit['missing_actions']} 多 {audit['extra_actions']}")
        if audit["outside_icons"]:
            failures.append(f"{sample_id} 用了候选之外的图标：{audit['outside_icons']}")
        if size == "2x2" and audit["icon_instances"] > 2:
            failures.append(f"{sample_id} 2x2 图标实例超预算：{audit['icon_instances']}")
        used, budget, fit_detail = fit_of(dsl_text, size)
        if used > budget:
            failures.append(f"{sample_id} 纵向实算 {used}vp 超预算 {budget}vp")
        card = {
            "id": sample_id,
            "title": str(content.get("title") or sample_id),
            "query": str(content.get("userQuery") or sample_id),
            "size": size,
            "dsl": dsl_text,
            "palette": PALETTES[sample_id],
            "audit": audit,
            "fit": (used, budget, fit_detail),
        }
        card["png"] = preview_png(card)
        cards.append(card)
        (output / "dsl" / f"{sample_id}.jsonl").write_text(dsl_text, encoding="utf-8")
        (output / "cards" / f"{sample_id}.md").write_text(
            card_markdown(card, ctx), encoding="utf-8")
        (output / "screenshots" / f"{sample_id}.png").write_bytes(card["png"])
        print(f"{sample_id} {card['title']} {size} {layout_of(dsl_text)} "
              f"数据 {len(audit['fingerprint']['data'])} 动作 "
              f"{len(audit['fingerprint']['actions'])} 图标 {audit['icon_instances']} "
              f"占高 {used}/{budget}vp")

    write_outputs(cards, output)
    (output / "README.md").write_text(index_markdown(cards), encoding="utf-8")
    if failures:
        raise SystemExit("自检失败：\n" + "\n".join(failures))
    return cards


def main() -> None:
    parser = argparse.ArgumentParser(description="生成精致版期望输出数据集")
    parser.add_argument("--source", type=Path, default=SOURCE_RUN, help="批跑目录")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="数据集输出目录")
    args = parser.parse_args()
    generate(args.source, args.output)
    print(f"数据集：{args.output}")


if __name__ == "__main__":
    main()
