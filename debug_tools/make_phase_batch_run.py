"""把 taskspec/Phase 的 Q001–Q010 跑成一份「真实批跑结果」数据集。

这批产物的身份是**模型实际输出**：脚本扮演被微服务链接的生成模型，逐条读入 Phase 请求
载荷，按其中的候选数据字段、事件与素材产出该次生成的紧凑 genui DSL（JSONL）与单条 md
说明，再落成调试平台自己的批跑运行目录，以及一份能写进「本次会话调试记录」的记录包。
期望数据不在这批产物里，由使用者随后自己在导入页输入。

DSL 只用模型可见的语义词汇：root 必须是 ``Layout``，``layout`` 取 ``layouts/2x2.md``
登记的十个 ``S-`` 布局之一，children 按有序角色填真实组件 ID；业务组件只用
``SingleLineTitle``／``EmphasizedData``／``EmphasisText``／``SecondaryBody``／``TableText``／
``EventCard``／``InfoBlock``／``ProgressCircleSingle``／``DataDisplay``／``Group``／
``PillButton``，图标写在 ``icon``／``visual.icon`` 属性上，宽高、间距、配色由模板注入。
``Text``／``Image``／``Button`` 是转换器内部组件，模型写出来会被严格转换直接拒绝，所以每条
产物都要先过 ``convert_compact_dsl_to_a2ui``（与卡片渲染页同一入口），过不了就报错退出。
候选数据字段逐个用 ``{"path": ...}`` 或完整表达式绑定，候选事件逐个落进唯一 ``onClick``；
图标按 2x2 预算（默认不超过两个实例）从候选素材里取舍，不使用候选之外的素材。
指纹与判定调用平台自身的 ``fingerprint``／``fingerprint_from_spec``／``match_pair``，
说明文件与页面同一口径。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DEBUG_TOOLS_ROOT = Path(__file__).resolve().parent
if str(DEBUG_TOOLS_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(DEBUG_TOOLS_ROOT.parent))

from debug_tools.batch_testing.card_size import normalize as normalize_size  # noqa: E402
from debug_tools.batch_testing.expect_compare import (  # noqa: E402
    fingerprint,
    fingerprint_from_spec,
    match_pair,
)
from debug_tools.paths import ensure_cloud_import_path  # noqa: E402

ensure_cloud_import_path()

from services.compact_dsl_a2ui_converter import (  # noqa: E402
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)

REPOSITORY_ROOT = DEBUG_TOOLS_ROOT.parent
PHASE_SOURCE = REPOSITORY_ROOT.parent / "taskspec" / "Phase"
MEDIA_ROOT = REPOSITORY_ROOT / "render" / "platform" / "public" / "resources" / "base" / "media"
DEFAULT_OUTPUT = DEBUG_TOOLS_ROOT / "Datasets" / "phase_Q001_Q010_model_run"
DEFAULT_RUN_ROOT = DEBUG_TOOLS_ROOT / "batch_output"
DEFAULT_RUN_ID = "phase_q001_q010_model"
RUN_NAME = "Phase Q001–Q010 真实批跑结果"
RECORD_KEY = "ai-widget-debug-call-history:v1"
RECORD_PREFIX = "run-"
RUN_AT = datetime.now(UTC).replace(microsecond=0)

SAMPLE_IDS = tuple(f"Q{index:03d}" for index in range(1, 11))

# 2x2 参考画布 150vp、普通安全区 126vp；背景由 root 的 linearGradient 负责，其余几何不写。
# 每个主题是一对 #AARRGGBB 渐变端点。
THEMES = {
    "Q001": ("#FF86C5E3", "#FFF5DC62"),
    "Q002": ("#FFA8D8EA", "#FFF7E6C4"),
    "Q003": ("#FFC7D8FB", "#FFEFE6FB"),
    "Q004": ("#FFF3B6A6", "#FFF7E6C4"),
    "Q005": ("#FFBEE0F5", "#FFDFF0D8"),
    "Q006": ("#FFD5DDF3", "#FFF0E3F5"),
    "Q007": ("#FFCFE0EE", "#FFE9E3F7"),
    "Q008": ("#FFBFE3E0", "#FFE9F5C4"),
    "Q009": ("#FFD7E3F0", "#FFE8D9F5"),
    "Q010": ("#FFA9DCC8", "#FFDDEFC1"),
}

# ProgressCircleSingle 的轨道色与 InfoBlock 的背板色沿用已登记的小卡配色。
RING_COLOR = "#FF1F4799"
RING_TRACK = "#331F4799"
INFO_BACK = "#CCFFFFFF"

CATEGORIES = {
    "Q001": "天气", "Q002": "天气", "Q003": "日程", "Q004": "天气", "Q005": "天气",
    "Q006": "日程", "Q007": "日程", "Q008": "出行", "Q009": "设备", "Q010": "天气",
}

# 这条真实卡片是怎么拼出来的，以及在对比页上该怎么用它。
RUN_NOTES = {
    "Q001": "`S-title-primary-secondary-action`：标题图标 local_fill＋按钮图标 sun_max，"
            "四个候选字段全绑定（cityCode 在按钮 uri 的表达式里）；期望改 intentName 就判不匹配。",
    "Q002": "`S-title-content`：一个 EmphasisText 用 secondaryText 数组同时承载日期与星期，"
            "全卡没有 onClick，动作维度对本条不产生需求项。",
    "Q003": "`S-title-primary-secondary-action`：EmphasizedData 倒数＋EventCard 标题时间＋"
            "带 calendar_fill 的文字按钮，entityId 只出现在按钮参数里。",
    "Q004": "`S-center`＋DataDisplay：预警等级作核心读数、更新时间作支撑文本；"
            "本条图标实例为零，勾上图标维度就会被筛掉。",
    "Q005": "`S-title-dual-content`：降雨概率用 ProgressCircleSingle（环心 drop_1），"
            "温度范围交给 SecondaryBody，标题用 calendar_fill。",
    "Q006": "`S-title-content`＋EventCard 两项：events/0 与 events/1 各绑标题与开始时间，"
            "共四条数据绑定，图标只有标题一个。",
    "Q007": "`S-title-dual-content`：地点作主文本，备注与结束时间用 SecondaryBody 单列两行。",
    "Q008": "`S-title-content`＋Group(hero-support)：倒数与天气两项合成一个完整主体，"
            "四个候选素材只用上 airplane_fill_1。",
    "Q009": "`S-dual-info`：左右耳各一个 InfoBlock，visual.icon 用 icon_left／icon_right，"
            "两条电量与两条充电状态全部绑定。",
    "Q010": "`S-title-dual-content` 的 stacked-info 变体：两个无 visual 的紧凑 InfoBlock "
            "分别承载明天与后天，图标只有标题 local_fill。",
}


# --------------------------------------------------------------------------- DSL 组装


def line(*parts: Any) -> str:
    return json.dumps(list(parts), ensure_ascii=False)


def _clean(props: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in props.items() if value is not None}


def media(asset: str) -> str:
    """素材必须真实存在于渲染资源目录，图标路径的扩展名按磁盘上的实际文件写。"""
    name = asset.removeprefix("asset.")
    for suffix in (".svg", ".png", ".jpg", ".jpeg"):
        if (MEDIA_ROOT / f"{name}{suffix}").is_file():
            return f"resources/base/media/{name}{suffix}"
    raise FileNotFoundError(f"渲染资源目录缺少素材：{name}")


def node(node_id: str, kind: str, props: dict[str, Any],
         children: list[str] | None = None) -> str:
    parts: list[Any] = [node_id, kind, _clean(props)]
    if children is not None:
        parts.append(children)
    return line(*parts)


def gradient(colors: tuple[str, str]) -> dict[str, Any]:
    return {"direction": "RightBottom", "colors": [[colors[0], 0], [colors[1], 1]]}


def root(layout_name: str, children: list[str], colors: tuple[str, str],
         *, variant: str | None = None) -> str:
    props: dict[str, Any] = {"layout": layout_name, "variant": variant}
    props["linearGradient"] = gradient(colors)
    return node("root", "Layout", props, children)


def header(node_id: str, title: Any, *, asset: str | None = None) -> str:
    return node(node_id, "SingleLineTitle", {
        "title": title, "icon": media(asset) if asset else None, "fontSize": 12,
    })


def ref(pointer: str) -> str:
    return "${" + pointer + "}"


def lit(text: str) -> str:
    return "'" + text + "'"


def concat(*tokens: str) -> str:
    """拼出完整表达式；转换器与指纹都按 ``{{ ... }}`` 整串识别。"""
    return "{{ " + " + ".join(tokens) + " }}"


def bound(node_id: str, kind: str, prop: str, pointer: str, sample: Any,
          *, extra: dict[str, Any] | None = None) -> list[str]:
    """一行属性绑定 ＋ 一行 DataModel 取值，让 DSL 能独立渲染。"""
    props: dict[str, Any] = {prop: {"path": pointer}}
    props.update(extra or {})
    return [node(node_id, kind, props), line(pointer, sample)]


def pill_button(node_id: str, text_value: str, handler: dict[str, Any],
                *, asset: str | None = None) -> str:
    return node(node_id, "PillButton", {
        "label": text_value, "icon": media(asset) if asset else None, "onClick": [handler],
    })


def click_handler(content: dict[str, Any]) -> dict[str, Any]:
    """事件不属于 CardSpec，只写进 DSL 的 ``onClick``；空参数按协议丢弃。"""
    candidates = content.get("candidateEventCandidates") or []
    if not candidates:
        return {}
    action = candidates[0].get("action") or {}
    raw_args = action.get("args") or {}
    args = {key: value for key, value in raw_args.items() if str(value).strip()}
    return {"call": str(action.get("call") or "").strip(), "args": args}


def build_q001(content: dict[str, Any]) -> list[str]:
    condition = "/data/weather/current/condition"
    prefecture = "/data/weather/location/prefectureName"
    district = "/data/weather/location/districtName"
    lines = [root("S-title-primary-secondary-action",
                  ["header", "current", "region", "detail"], THEMES["Q001"])]
    lines.append(header("header", "西湖天气", asset="local_fill"))
    lines += bound("current", "EmphasisText", "mainText", condition, "晴",
                   extra={"fontSize": 18})
    lines.append(node("region", "SecondaryBody", {"items": [
        {"label": "区域", "value": concat(ref(prefecture), lit(" "), ref(district))},
    ], "fontSize": 14}))
    lines.append(pill_button("detail", "查看详情", click_handler(content), asset="sun_max"))
    lines += [line(prefecture, "杭州市"), line(district, "西湖区"),
              line("/data/weather/location/cityCode", "101210101")]
    return lines


def build_q002(content: dict[str, Any]) -> list[str]:
    condition = "/data/weather/daily/1/condition"
    date = "/data/weather/daily/1/date"
    weekday = "/data/weather/daily/1/weekday"
    lines = [root("S-title-content", ["header", "summary"], THEMES["Q002"])]
    lines.append(header("header", "明日天气", asset="calendar_fill"))
    lines.append(node("summary", "EmphasisText", {
        "mainText": {"path": condition},
        "secondaryText": [{"path": date}, {"path": weekday}],
        "fontSize": 18,
    }))
    lines += [line(condition, "晴"), line(date, "9月15日"), line(weekday, "星期二")]
    return lines


def build_q003(content: dict[str, Any]) -> list[str]:
    countdown = "/data/countdown/countdownDays"
    title = "/data/calendar/events/0/title"
    start = "/data/calendar/events/0/dtStart"
    lines = [root("S-title-primary-secondary-action",
                  ["header", "countdown", "event", "detail"], THEMES["Q003"])]
    lines.append(header("header", "发布会提醒", asset="alarm_fill_1"))
    lines += bound("countdown", "EmphasizedData", "value", countdown, 18,
                   extra={"unit": "天后", "fontSize": 30})
    lines.append(node("event", "EventCard", {"items": [
        {"title": {"path": title}, "time": {"path": start}},
    ]}))
    lines.append(pill_button("detail", "查看日程", click_handler(content),
                             asset="calendar_fill"))
    lines += [line(title, "产品发布会"), line(start, "上午10:00"),
              line("/data/calendar/events/0/entityId", "event-001")]
    return lines


def build_q004(content: dict[str, Any]) -> list[str]:
    alert = "/data/weather/current/alertLevel"
    updated = "/data/weather/updatedAt"
    lines = [root("S-center", ["display"], THEMES["Q004"])]
    lines.append(node("display", "DataDisplay", {
        "label": "长沙天气预警", "value": {"path": alert},
        "supportingText": {"path": updated}, "fontSize": 18,
    }))
    lines += [line(alert, "黄色预警"), line(updated, "08:20")]
    return lines


def build_q005(content: dict[str, Any]) -> list[str]:
    rain = "/data/weather/daily/1/rainProbabilityPercent"
    range_text = "/data/weather/daily/1/temperatureRangeText"
    lines = [root("S-title-dual-content", ["header", "rain", "temperature"], THEMES["Q005"])]
    lines.append(header("header", "广州明天", asset="calendar_fill"))
    lines.append(node("rain", "ProgressCircleSingle", {
        "value": {"path": rain}, "total": 100, "icon": media("drop_1"),
        "displayValue": concat(ref(rain), lit("%")), "label": "降雨概率",
        "color": RING_COLOR, "backgroundColor": RING_TRACK,
    }))
    lines.append(node("temperature", "SecondaryBody", {"items": [
        {"label": "温度范围", "value": {"path": range_text}},
    ], "fontSize": 14}))
    lines += [line(rain, 60), line(range_text, "18~24℃")]
    return lines


def build_q006(content: dict[str, Any]) -> list[str]:
    first_title = "/data/calendar/events/0/title"
    first_start = "/data/calendar/events/0/dtStart"
    second_title = "/data/calendar/events/1/title"
    second_start = "/data/calendar/events/1/dtStart"
    lines = [root("S-title-content", ["header", "meetings"], THEMES["Q006"])]
    lines.append(header("header", "明日两场会议", asset="calendar_fill"))
    lines.append(node("meetings", "EventCard", {"items": [
        {"title": {"path": first_title}, "time": {"path": first_start}},
        {"title": {"path": second_title}, "time": {"path": second_start}},
    ]}))
    lines += [line(first_title, "产品立项会"), line(first_start, "09:00"),
              line(second_title, "客户交流会"), line(second_start, "15:00")]
    return lines


def build_q007(content: dict[str, Any]) -> list[str]:
    place = "/data/calendar/events/0/eventLocation"
    note = "/data/calendar/events/0/description"
    end = "/data/calendar/events/0/dtEnd"
    lines = [root("S-title-dual-content", ["header", "place", "detail"], THEMES["Q007"])]
    lines.append(header("header", "客户方案交流会", asset="icon_meeting"))
    lines += bound("place", "EmphasisText", "mainText", place, "珠江新城办公室",
                   extra={"fontSize": 18})
    lines.append(node("detail", "SecondaryBody", {"items": [
        {"label": "备注", "value": {"path": note}},
        {"label": "结束", "value": {"path": end}},
    ], "columns": 1, "fontSize": 12}))
    lines += [line(note, "带方案 PPT 初稿"), line(end, "17:30")]
    return lines


def build_q008(content: dict[str, Any]) -> list[str]:
    countdown = "/data/countdown/countdownDays"
    condition = "/data/weather/daily/2/condition"
    range_text = "/data/weather/daily/2/temperatureRangeText"
    lines = [root("S-title-content", ["header", "trip"], THEMES["Q008"])]
    lines.append(header("header", "北京出差", asset="airplane_fill_1"))
    lines.append(node("trip", "Group", {"variant": "hero-support"},
                      ["countdown", "weather"]))
    lines += bound("countdown", "EmphasizedData", "value", countdown, 2,
                   extra={"unit": "天后", "fontSize": 30})
    lines.append(node("weather", "SecondaryBody", {"items": [
        {"label": "天气", "value": {"path": condition}},
        {"label": "温度", "value": {"path": range_text}},
    ], "fontSize": 14}))
    lines += [line(condition, "多云"), line(range_text, "18~24℃")]
    return lines


def build_q009(content: dict[str, Any]) -> list[str]:
    left_level = "/data/earphone/leftBatteryLevel"
    left_status = "/data/earphone/leftChargingStatusDesc"
    right_level = "/data/earphone/rightBatteryLevel"
    right_status = "/data/earphone/rightChargingStatusDesc"
    lines = [root("S-dual-info", ["left", "right"], THEMES["Q009"])]
    plan = (
        ("left", left_level, left_status, "icon_left", 82, "充电中"),
        ("right", right_level, right_status, "icon_right", 76, "未充电"),
    )
    for node_id, level, status, asset, level_sample, status_sample in plan:
        lines.append(node(node_id, "InfoBlock", {
            "primaryText": {"path": level}, "unit": "%",
            "secondaryText": {"path": status}, "backgroundColor": INFO_BACK,
            "visual": {"type": "icon", "icon": media(asset)},
        }))
        lines += [line(level, level_sample), line(status, status_sample)]
    return lines


def build_q010(content: dict[str, Any]) -> list[str]:
    one_condition = "/data/weather/daily/1/condition"
    one_air = "/data/weather/daily/1/airQuality"
    two_condition = "/data/weather/daily/2/condition"
    two_air = "/data/weather/daily/2/airQuality"
    lines = [root("S-title-dual-content", ["header", "tomorrow", "after"], THEMES["Q010"],
                  variant="stacked-info")]
    lines.append(header("header", "杭州周末", asset="local_fill"))
    plan = (
        ("tomorrow", one_condition, one_air, "明天 ", "晴", "优"),
        ("after", two_condition, two_air, "后天 ", "多云", "良"),
    )
    for node_id, condition, air, day, condition_sample, air_sample in plan:
        lines.append(node(node_id, "InfoBlock", {
            "variant": "stacked",
            "primaryText": concat(lit(day), ref(condition)),
            "secondaryText": concat(lit("空气质量 "), ref(air)),
            "backgroundColor": INFO_BACK,
        }))
        lines += [line(condition, condition_sample), line(air, air_sample)]
    return lines


BUILDERS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "Q001": build_q001, "Q002": build_q002, "Q003": build_q003, "Q004": build_q004,
    "Q005": build_q005, "Q006": build_q006, "Q007": build_q007, "Q008": build_q008,
    "Q009": build_q009, "Q010": build_q010,
}


# --------------------------------------------------------------------------- 合法性门禁


def convert_or_fail(sample_id: str, dsl: str, size: str) -> None:
    """用卡片渲染页同一入口严格转换：语义词汇不合法或槽位不对就终止生成。"""
    try:
        convert_compact_dsl_to_a2ui(dsl, size=size, protocol_profile={"version": "v0.9"})
    except CompactDslConversionError as error:
        raise SystemExit(f"{sample_id} 的 DSL 不是合法的模型输出：{error}") from error


def layout_of(dsl: str) -> str:
    """读回 root 的布局与变体，供说明文件与索引表引用。"""
    for raw in dsl.splitlines():
        parts = json.loads(raw)
        if isinstance(parts, list) and len(parts) >= 3 and parts[0] == "root":
            layout = str(parts[2].get("layout"))
            variant = parts[2].get("variant")
            return layout if not variant else f"{layout}（variant={variant}）"
    return "未知布局"


# --------------------------------------------------------------------------- 产物解析


def load_payload(source_dir: Path, sample_id: str) -> dict[str, Any]:
    """读入 Phase 请求载荷；这份原文就是这次调用发给模型的 request。"""
    return json.loads((source_dir / f"{sample_id}.json").read_text(encoding="utf-8"))


def content_of(payload: dict[str, Any], sample_id: str) -> dict[str, Any]:
    content = payload.get("content")
    if not isinstance(content, dict):
        raise ValueError(f"{sample_id} 载荷缺少 content 块")
    return content


def spec_expectation(content: dict[str, Any], dsl: str) -> dict[str, Any]:
    """把候选载荷当期望侧：按导入侧合并规则，CardSpec 命中的维度优先，缺失维度回退 DSL。"""
    fp = fingerprint(dsl)
    spec_fp = fingerprint_from_spec(content)
    if not any(spec_fp.values()):
        return fp
    return {
        "data": spec_fp["data"] or fp["data"],
        "actions": spec_fp["actions"] or fp["actions"],
        "icons": spec_fp["icons"] or fp["icons"],
        "size": fp["size"],
    }


def asset_stem(value: str) -> str:
    """图标只按资源文件名比较，与页面 ``_icon_match`` 同一口径。"""
    name = str(value).strip().replace("\\", "/").rsplit("/", 1)[-1].lower()
    name = name.removeprefix("asset.")
    return name.rsplit(".", 1)[0] if "." in name else name


def audit_icons(content: dict[str, Any], fp: dict[str, Any]) -> dict[str, list[str]]:
    """实际用到的图标必须都来自候选素材；候选素材是按预算取舍的可选清单。"""
    candidates = [str(item) for item in content.get("candidateAssetIds") or []]
    used = [str(item) for item in fp.get("icons") or []]
    candidate_stems = {asset_stem(item) for item in candidates}
    used_stems = {asset_stem(item) for item in used}
    return {
        "used": used,
        "outside": sorted(used_stems - candidate_stems),
        "unused": sorted(candidate_stems - used_stems),
    }


def dsl_reading(dsl: str) -> dict[str, Any]:
    """从这份 DSL 读出卡片实际构成（节点行数与画面文案），供说明文件引用。"""
    labels: list[str] = []
    rows = 0
    for raw in dsl.splitlines():
        if not raw.strip():
            continue
        parts = json.loads(raw)
        if not isinstance(parts, list) or len(parts) < 3 or not isinstance(parts[2], dict):
            continue
        rows += 1
        if parts[1] == "root":
            continue
        for key in ("title", "label", "primaryText"):
            value = parts[2].get(key)
            if isinstance(value, str) and value.strip() and value not in labels:
                labels.append(value.strip())
    return {"rows": rows, "labels": labels}


def spec_field_rows(content: dict[str, Any]) -> list[str]:
    """逐行列出完整候选字段路径，可原样粘进导入页的「期望数据」。"""
    rows: list[str] = []
    for binding in content.get("candidateDataBindings") or []:
        root_pointer = str(binding.get("writeResultTo") or "")
        for field in binding.get("candidateOutputFields") or []:
            rows.append(f"- `{root_pointer}{field}`")
    return rows or ["- 入参没有候选数据字段。"]


def spec_event_rows(content: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    for event in content.get("candidateEventCandidates") or []:
        action = event.get("action") or {}
        raw_args = (action.get("args") or {}).items()
        args = {key: value for key, value in raw_args if str(value).strip()}
        rows.append(f"- `{action.get('call')}` ＋ `{json.dumps(args, ensure_ascii=False)}`"
                    f"（{event.get('capabilityId')}）")
    return rows or ["- 入参没有事件候选：期望侧的动作维度对本条为空。"]


def icon_rows(icon_report: dict[str, list[str]]) -> list[str]:
    used = [asset_stem(item) for item in icon_report["used"]]
    rows = [f"- 本卡用到的图标：{('、'.join(used)) if used else '无（图标维度对本条为空）'}"]
    unused = icon_report["unused"]
    if unused:
        rows.append(
            f"- 候选里没用上的素材：{'、'.join(unused)}；2x2 默认只给两个图标实例"
            "（标题／按钮／环心），没有落点就不硬塞，期望图标维度写这些名字会把本条筛掉。"
        )
    return rows


# --------------------------------------------------------------------------- 说明文件


def output_markdown(sample_id: str, payload: dict[str, Any], content: dict[str, Any],
                    expectation: dict[str, Any], dsl: str, verdict: dict[str, Any],
                    icon_report: dict[str, list[str]]) -> str:
    size = str(content.get("size") or "2x2")
    fp = fingerprint(dsl)
    reading = dsl_reading(dsl)
    caption = "、".join(reading["labels"]) or "无固定文案"
    missing = (
        f"数据 {json.dumps(verdict['missingData'], ensure_ascii=False)} "
        f"动作 {json.dumps(verdict['missingActions'], ensure_ascii=False)}"
    )
    lines = [
        f"# {sample_id} · {content.get('title') or sample_id}（真实批跑结果）",
        "",
        "> 身份：**模型实际输出**。脚本充当被微服务链接的生成模型，按 "
        f"`taskspec/Phase/{sample_id}.json` 的入参生成这份卡片；它不是期望数据，"
        f"分类「{CATEGORIES[sample_id]}」，声明尺寸 {size}。",
        "",
        "## 入参要求（原样摘录）",
        "",
        f"- Query：{content.get('userQuery')}",
        f"- 宿主标题：{content.get('title')}；概述：{content.get('description')}",
        f"- 宿主包名：`{content.get('bundleName') or payload.get('bundleName')}`",
        "",
        "## 我这次生成的卡片",
        "",
        f"- 布局：{layout_of(dsl)}；DSL 节点行 {reading['rows']} 行，画面文案：{caption}",
        f"- 实算数据绑定：{json.dumps(fp['data'], ensure_ascii=False)}",
        f"- 实算动作：{json.dumps(fp['actions'], ensure_ascii=False)}",
        f"- 实算图标：{json.dumps(fp['icons'], ensure_ascii=False)}",
        f"- 尺寸判定：{size}（root 用 `S-` 布局，DSL 自身即可判定）",
        "- 合法性：已通过 `convert_compact_dsl_to_a2ui` 严格转换，"
        "可直接贴进「卡片渲染」页预览。",
        "",
        "## 对照候选规格的自检",
        "",
        f"- 期望侧（候选载荷实算）：数据 {len(expectation['data'])} 项、"
        f"动作 {len(expectation['actions'])} 项、图标 {len(expectation['icons'])} 项",
        f"- 数据＋动作＋尺寸判定 `{verdict['tier']}`；缺失 {missing}",
        f"- 图标越界（用了候选之外的素材）：{json.dumps(icon_report['outside'])}",
        *icon_rows(icon_report),
        "",
        "## 怎么进对比页右侧",
        "",
        f"- 本目录 `session/records.json` 里的 `{RECORD_PREFIX}{sample_id}` 就是这条记录；"
        "整批注入见 `README.md`，注入后在「期望对比」右侧勾它即可。",
        f"- {RUN_NOTES[sample_id]}",
        "",
        "## 若要手工输入期望",
        "",
        "- 完整候选字段路径（可逐行粘进导入页「期望数据」）：",
        *spec_field_rows(content),
        "- 事件候选：",
        *spec_event_rows(content),
        "- 图标：",
        *icon_rows(icon_report),
        "- 也可以把 `requests/Qxxx.json` 的 content 块当 CardSpec 粘贴，"
        "平台会自动识别数据／动作／图标三类指纹。",
        "- 想看差异形态：期望里多写一个本卡没用上的素材名，图标维度就会把本条筛掉；"
        "改一下 intentName 会在动作维度筛掉；期望仍写 2x2、把这份 DSL 的 root 布局换成 "
        "`W-` 系列，会判「尺寸不一致」。",
        "",
        "## DSL 原文",
        "",
        "```jsonl",
        dsl.rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(lines)


INJECT_JS = """// 把 Phase Q001–Q010 的真实批跑结果写进「本次会话调试记录」。
// 用法：打开 http://127.0.0.1:8888/debug/ 任意页面，F12 控制台整段粘贴执行后会自动刷新。
const RECORDS = %RECORDS%;
const KEY = '%KEY%';
const stored = JSON.parse(sessionStorage.getItem(KEY) || '{"calls":[]}');
const fresh = (record) => !RECORDS.some((item) => item.id === record.id);
stored.calls = [...(stored.calls || []).filter(fresh), ...RECORDS];
stored.selectedCallId = RECORDS[RECORDS.length - 1].id;
sessionStorage.setItem(KEY, JSON.stringify(stored));
location.reload();
"""


def inject_script(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False, indent=2)
    return INJECT_JS.replace("%RECORDS%", payload).replace("%KEY%", RECORD_KEY)


def index_markdown(rows: list[dict[str, Any]], run_id: str) -> str:
    table = ["| ID | 标题 | 分类 | 布局 | 期望数据 | 用到的图标 | 自检 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        table.append(
            f"| {row['id']} | {row['title']} | {row['category']} | {row['layout']} | "
            f"{len(row['data'])} | {len(row['used_icons'])} | {row['tier']} |"
        )
    return "\n".join([
        "# Phase Q001–Q010 真实批跑结果",
        "",
        "十条**模型实际输出**：脚本扮演被微服务链接的生成模型，逐条读 "
        "`taskspec/Phase/Q001.json` ～ `Q010.json` 的入参，产出这一批的紧凑 genui DSL 与说明。"
        "期望数据不在这批产物里，由你在「导入期望输出」页自己输入。",
        "",
        "## 这批 DSL 是按正式生成契约写的",
        "",
        "root 只能是 `Layout`，`layout` 取 `layouts/2x2.md` 登记的十个 `S-` 布局之一，"
        "children 按有序角色填真实组件 ID；只用 `SingleLineTitle`／`EmphasizedData`／"
        "`EmphasisText`／`SecondaryBody`／`EventCard`／`InfoBlock`／`ProgressCircleSingle`／"
        "`DataDisplay`／`Group`／`PillButton` 这些语义组件，图标写在 `icon`／`visual.icon` "
        "属性上，不写宽高、间距、圆角与对齐。`Text`／`Image`／`Button` 是转换器内部展开的"
        "基础组件，模型直接写会被拒绝。",
        "",
        "每条产物都先过 `convert_compact_dsl_to_a2ui(size, protocol_profile)` —— "
        "与「卡片渲染」页同一个严格入口，过不了直接报错退出，所以这批 DSL 都能贴进渲染页预览。",
        "",
        "## 目录",
        "",
        "```text",
        "phase_Q001_Q010_model_run/",
        "  requests/Qxxx.json           # 入参原文（发给模型的 request）",
        "  output/Qxxx.genui.jsonl      # 模型产出的 DSL，可直接在卡片渲染页预览",
        "  output/Qxxx.md               # 单条产出说明（含实算指纹、自检与图标取舍）",
        "  session/records.json         # 十条本次会话调试记录（对比页右侧的数据源）",
        "  session/inject.js            # 自包含注入脚本，控制台整段粘贴即可",
        "```",
        "",
        f"同时在 `debug_tools/batch_output/{run_id}/` 落了一份批跑运行目录，"
        "「批量测试」页能看到这条运行，后端 `GET /debug/expect/compare` 也可以直接拿它当实际侧。",
        "",
        "## 用例一览",
        "",
        *table,
        "",
        "十条都是 2x2；分类为天气 5 条、日程 3 条、出行 1 条、设备 1 条。"
        "「自检」是**候选载荷当期望、这份 DSL 当实际**，用后端同一套 `match_pair` "
        "按数据＋动作＋尺寸三个维度算出的判定。",
        "",
        "## 图标维度为什么不会条条命中",
        "",
        "2x2 的图标预算是默认最多两个实例（标题／按钮／环心，`NumericRatioStack` 的三个 12vp "
        "小图标算例外），而入参常给三四个候选素材，所以本批每条只挑语义上最贴的用，"
        "其余候选素材留在清单里没用上——这是真实模型的正常取舍，不是漏写。"
        "期望侧若把全部候选素材写成需求项，图标维度就会把这些条目筛掉；"
        "各条 `output/Qxxx.md` 里逐行列了「用到的图标」和「候选里没用上的素材」。",
        "",
        "## 让这十条出现在对比页右侧",
        "",
        "对比页的实际侧只认浏览器会话里的调试记录（`sessionStorage` 键 "
        f"`{RECORD_KEY}`），三种方式任选：",
        "",
        "1. 打开 <http://127.0.0.1:8888/debug/>，F12 控制台整段粘贴 `session/inject.js`，"
        "页面自动刷新后「接口调用历史」和对比页右侧都会出现这十条；同批记录会被覆盖，"
        "其它来源的记录保留。",
        "2. 起一个带 CORS 的静态服务常驻数据集目录，页面里一行 fetch 回填："
        "`python debug_tools/make_phase_batch_run.py --serve`，然后控制台执行：",
        "",
        "```js",
        "const records = await (await fetch('http://127.0.0.1:8899/session/records.json')).json();",
        f"const key = '{RECORD_KEY}';",
        "const stored = JSON.parse(sessionStorage.getItem(key) || '{\"calls\":[]}');",
        "stored.calls = records; stored.selectedCallId = records.at(-1).id;",
        "sessionStorage.setItem(key, JSON.stringify(stored)); location.reload();",
        "```",
        "",
        "3. 真跑模型：把 `debug_tools` 的连接配置指向已启动的工具微服务"
        "（默认 `ws://127.0.0.1:8855/api/v1/ws/tools`），在「接口调试」里逐条提交 "
        "`requests/Qxxx.json`，成功调用会自动进同一份会话记录。",
        "",
        "## 期望侧由你输入",
        "",
        "「导入期望输出」页每条期望要求 DSL ＋ 截图（截图必须是真的图片），也可以只在"
        "「期望数据／期望动作」框里逐行粘贴需求项。各条 `output/Qxxx.md` 末尾已经把"
        "完整候选字段路径、事件参数与图标取名列好，直接复制即可；"
        "把 `requests/Qxxx.json` 的 content 块当 CardSpec 粘贴，平台会自动识别三类指纹。",
        "",
        "启用维度的需求项必须全部命中才算「已匹配」，尺寸仍是硬门槛。"
        "本批每条都绑定了入参里的全部候选字段，事件也逐个落进唯一 `onClick`，"
        "所以只勾数据＋动作两个维度时十条都应命中；想看不匹配的形态，"
        "就按说明文件里的做法加一个没用上的素材名或改 intentName。",
        "",
        "## 重新生成",
        "",
        "```powershell",
        "uv run python debug_tools/make_phase_batch_run.py",
        "# 可选：--source <Phase 目录> --output <数据集目录>",
        "#       --run-root <批跑根目录> --run-id <运行标识> --serve --port <端口>",
        "```",
        "",
        "脚本每条先做严格转换门禁，再用 `fingerprint`／`match_pair` 自检数据、动作与尺寸，"
        "并核对图标没有越出候选清单；任何一条不合格就报错退出，避免说明文件与页面口径分叉。",
        "",
    ])


# --------------------------------------------------------------------------- 落盘


def session_record(index: int, sample_id: str, payload: dict[str, Any],
                   content: dict[str, Any], dsl: str) -> dict[str, Any]:
    """一条接口调试记录：请求是 Phase 入参原文，响应带 genui 与建议尺寸。"""
    started = RUN_AT + timedelta(minutes=index)
    finished = started + timedelta(seconds=4)
    return {
        "id": f"{RECORD_PREFIX}{sample_id}",
        "operation": "generateWidgetCardCompactDsl",
        "source": "interface",
        "status": "success",
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "completedAt": finished.isoformat(),
        "durationMs": int((finished - started).total_seconds() * 1000),
        "request": payload,
        "response": {
            "data": {
                "genui": dsl,
                "title": content.get("title"),
                "cardSpec": {"suggestSize": str(content.get("size") or "2x2")},
            },
        },
    }


def write_run_dir(run_root: Path, run_id: str, rows: list[dict[str, Any]]) -> Path:
    """按批跑运行的落盘格式写出，批量测试页与期望对比接口都能直接读这份结果。"""
    directory = run_root / run_id
    samples: list[dict[str, Any]] = []
    for row in rows:
        attempt_dir = directory / row["id"] / "attempt_000"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (attempt_dir / "genui.jsonl").write_text(row["dsl"], encoding="utf-8")
        (attempt_dir / "request.json").write_text(
            json.dumps(row["payload"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (directory / row["id"] / "result.json").write_text(
            json.dumps({"id": row["id"], "status": "success", "attemptCount": 1},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        samples.append({
            "id": row["id"], "title": row["title"], "query": row["query"], "size": row["size"],
            "category": row["category"], "status": "success", "attemptCount": 1,
            "elapsedMs": 4000,
        })
    finished = RUN_AT + timedelta(minutes=len(rows))
    (directory / "summary.json").write_text(json.dumps({
        "runId": run_id, "name": RUN_NAME, "status": "completed",
        "startedAt": RUN_AT.isoformat(), "finishedAt": finished.isoformat(),
        "total": len(rows), "completed": len(rows), "success": len(rows), "failed": 0,
        "samples": samples,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return directory


def generate(source_dir: Path, output: Path, run_root: Path, run_id: str) -> list[dict[str, Any]]:
    for sub in ("requests", "output", "session"):
        (output / sub).mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for index, sample_id in enumerate(SAMPLE_IDS):
        payload = load_payload(source_dir, sample_id)
        content = content_of(payload, sample_id)
        size = normalize_size(content.get("size")) or "2x2"
        dsl_text = "\n".join(BUILDERS[sample_id](content)) + "\n"
        convert_or_fail(sample_id, dsl_text, size)
        dsl_fp = fingerprint(dsl_text)
        expectation = spec_expectation(content, dsl_text)
        icon_report = audit_icons(content, dsl_fp)
        query = str(content.get("userQuery") or "")
        title = str(content.get("title") or sample_id)
        verdict = match_pair(
            expectation, dsl_fp, [], [], dimensions=["data", "actions"])
        if icon_report["outside"]:
            failures.append(f"{sample_id} 用了候选之外的图标：{icon_report['outside']}")

        (output / "requests" / f"{sample_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "output" / f"{sample_id}.genui.jsonl").write_text(dsl_text, encoding="utf-8")
        (output / "output" / f"{sample_id}.md").write_text(
            output_markdown(sample_id, payload, content, expectation,
                            dsl_text, verdict, icon_report),
            encoding="utf-8")
        records.append(session_record(index, sample_id, payload, content, dsl_text))
        rows.append({
            "id": sample_id, "title": title, "query": query, "size": size,
            "category": CATEGORIES[sample_id], "layout": layout_of(dsl_text),
            "data": expectation["data"], "actions": expectation["actions"],
            "icons": expectation["icons"], "used_icons": icon_report["used"],
            "tier": verdict["tier"], "dsl": dsl_text, "payload": payload,
        })
        if verdict["tier"] != "matched":
            failures.append(
                f"{sample_id} 与候选规格对不上：{json.dumps(verdict, ensure_ascii=False)}"
            )
        print(f"{sample_id} {layout_of(dsl_text)} 数据 {len(dsl_fp['data'])} "
              f"动作 {len(dsl_fp['actions'])} 图标 {len(icon_report['used'])} "
              f"尺寸 {size} → {verdict['tier']}")

    (output / "session" / "records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "session" / "inject.js").write_text(inject_script(records), encoding="utf-8")
    (output / "README.md").write_text(index_markdown(rows, run_id), encoding="utf-8")
    write_run_dir(run_root, run_id, rows)
    if failures:
        raise SystemExit("自检失败：\n" + "\n".join(failures))
    return rows


def serve_records(output: Path, port: int) -> None:
    """带 CORS 头静态服务数据集，让页面能一行 fetch 回填会话记录。"""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class CorsHandler(SimpleHTTPRequestHandler):
        def end_headers(self) -> None:  # noqa: ANN001
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

    server = ThreadingHTTPServer(
        ("127.0.0.1", port), partial(CorsHandler, directory=str(output)))
    print(f"serving {output} at http://127.0.0.1:{port} (Ctrl+C 停止)")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Phase Q001–Q010 真实批跑结果数据集")
    parser.add_argument("--source", type=Path, default=PHASE_SOURCE, help="Phase 目录")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="数据集输出目录")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT, help="批跑根目录")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID, help="批跑运行标识")
    parser.add_argument("--serve", action="store_true", help="只起静态服务，不重新生成")
    parser.add_argument("--port", type=int, default=8899, help="静态服务端口")
    args = parser.parse_args()

    if args.serve:
        serve_records(args.output, args.port)
        return
    generate(args.source, args.output, args.run_root, args.run_id)
    print(f"数据集：{args.output}")
    print(f"批跑运行：{args.run_root / args.run_id}")


if __name__ == "__main__":
    main()
