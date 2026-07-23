# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact DSL protocol prompt and validation in one isolated module."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, TypedDict, TypeGuard

COMPACT_DSL_FORMAT = "compact-dsl"

COMPONENT_WHITELIST = (
    "Text",
    "Image",
    "Divider",
    "Progress",
    "Button",
    "Checkbox",
    "Row",
    "Column",
    "List",
    "Stack",
)

CONTAINER_COMPONENTS = {"Row", "Column", "List", "Stack"}
ROOT_COMPONENTS = {"Column", "Stack"}
_DEGREE_VALUE_PATTERN = re.compile(
    r"^\s*-?\d+(?:\.\d+)?\s*(?:°|℃|°C)\s*$",
    re.IGNORECASE,
)
_FEELS_LIKE_VALUE_PATTERN = re.compile(
    r"^\s*(?:体感\s*)?-?\d+(?:\.\d+)?\s*(?:°|℃|°C)?\s*$",
    re.IGNORECASE,
)
_PERCENT_VALUE_PATTERN = re.compile(r"^\s*\d+(?:\.\d+)?\s*%\s*$")
_TIME_VALUE_PATTERN = re.compile(r"^\s*\d{1,2}:\d{2}(?:\s*[-~至]\s*\d{1,2}:\d{2})?\s*$")
_NUMBER_IN_TEXT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
_VISIBLE_PERCENT_PATTERN = re.compile(r"\d+(?:\.\d+)?%")
_VISIBLE_STORAGE_PATTERN = re.compile(r"\d+(?:\.\d+)?(?:[kmgt]i?b)", re.IGNORECASE)
_VISIBLE_DURATION_PATTERN = re.compile(
    r"\d+(?:\.\d+)?(?:小时|分钟|时|分|hours?|hrs?|minutes?|mins?|h|m)",
    re.IGNORECASE,
)
_PATH_TEMPLATE_PATTERN = re.compile(
    r"^\s*\{\{\s*(?:\$\{\s*)?(?P<path>/[^{}\s]+)\s*(?:\}\s*)?\}\}\s*$"
)
_COMPONENT_TYPE_PATTERN = "|".join(re.escape(item) for item in COMPONENT_WHITELIST)
_COMPONENT_STREAM_PATTERN = re.compile(
    rf'(?<!\\)"(?P<id>[^"\\]+)"\s*,\s*'
    rf'"(?P<type>{_COMPONENT_TYPE_PATTERN})"\s*,\s*'
)
_LEGACY_DATA_STREAM_PATTERN = re.compile(
    r'(?<!\\)"(?P<path>/?data/[^"\\]+)"\s*,\s*"object"\s*,\s*'
)
_INLINE_BINDING_PATH_PATTERN = re.compile(
    r"/(?:[A-Za-z0-9_~.-]+/)*[A-Za-z0-9_~.-]+"
)
_DAILY_WEEKDAY_PATH_PATTERN = re.compile(
    r"^(?P<prefix>/.*?/daily/)(?P<index>\d+)(?P<suffix>/weekday)$"
)
_NUMERIC_STRING_PATTERN = re.compile(r"^-?(?:\d+(?:\.\d*)?|\.\d+)$")
_DIMENSION_PATTERN = re.compile(r"^(-?\d+(?:\.\d+)?)(?:vp|fp|px)?$")
_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
_NORMALIZABLE_NUMBER_PROPS = (
    "width",
    "height",
    "space",
    "padding",
    "fontSize",
)
_LAYOUT_PIXEL_TOLERANCE = 1
_MISSING = object()
_SCHEMA_DESCRIPTION_LIMIT = 32
FORM_FONT_SIZES = {10, 12, 14, 16, 18, 20, 32, 40}
FORM_SPACING = {0, 2, 4, 6, 8, 10, 12, 14, 16}
_SURFACE_BACKGROUND_PROPS = ("backgroundColor", "linearGradient", "backgroundImage")
_DARK_SURFACE_FALLBACK = {
    "direction": "RightBottom",
    "colors": [["#FF3B4A54", 0], ["#FF202326", 1]],
}
_LIGHT_SURFACE_FALLBACK = {
    "direction": "RightBottom",
    "colors": [["#FFE8F1F5", 0], ["#FFE2ECE4", 1]],
}
_LOW_POWER_SURFACE_GRADIENT = {
    "direction": "RightBottom",
    "colors": [["#FF61CFBE", 0], ["#FF92C48D", 1]],
}
_SLEEP_SURFACE_GRADIENT = {
    "direction": "RightBottom",
    "colors": [["#FF202224", 0], ["#FF634794", 0.58], ["#FF5F58C7", 1]],
}
_LOW_POWER_KEYWORDS = ("低电", "省电", "low power", "battery saver")
_SLEEP_KEYWORDS = ("睡眠", "sleep")
_RELATIVE_DAY_INDEX = {
    "today": 0,
    "今日": 0,
    "今天": 0,
    "tomorrow": 1,
    "明日": 1,
    "明天": 1,
    "后天": 2,
    "大后天": 3,
}

REQUIRED_PROPS: dict[str, tuple[str, ...]] = {
    "Row": (),
    "Column": (),
    "List": (),
    "Stack": (),
    "Text": ("content",),
    "Image": ("src",),
    "Divider": (),
    "Progress": ("value", "total"),
    "Button": ("label",),
    "Checkbox": (),
}

_ISSUE_SYNTAX = "SYNTAX"
_ISSUE_STRUCTURE = "STRUCTURE"
_ISSUE_LAYOUT = "LAYOUT"
_ISSUE_BINDING = "BINDING"
_ISSUE_SEMANTIC = "SEMANTIC"


@dataclass(frozen=True)
class CompactDSLDiagnostic:
    category: str
    severity: str
    message: str


@dataclass(frozen=True)
class CompactDSLPreflightResult:
    genui: str
    repairs: tuple[str, ...]
    diagnostics: tuple[CompactDSLDiagnostic, ...]

    @property
    def passed(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)

    @property
    def error_messages(self) -> tuple[str, ...]:
        return tuple(
            item.message
            for item in self.diagnostics
            if item.severity == "error"
        )


class _PathBinding(TypedDict):
    path: str


@dataclass(frozen=True)
class _DynamicBindingRule:
    capability_id: str
    relative_path: tuple[str, ...]
    strong_aliases: tuple[str, ...]
    weak_aliases: tuple[str, ...] = ()
    source_aliases: tuple[str, ...] = ()
    value_pattern: re.Pattern[str] | None = None
    display_prefix: str = ""
    display_suffix: str = ""
    preview_value: Any = _MISSING


@dataclass(frozen=True)
class _DynamicBindingTarget:
    rule: _DynamicBindingRule
    binding_root: str
    path: str
    schema_type: str
    initial_value: Any


@dataclass(frozen=True)
class _VisibleContentRequirement:
    name: str
    path_fragments: tuple[str, ...] = ()
    visible_labels: tuple[str, ...] = ()
    value_kind: str = ""


@dataclass(frozen=True)
class _VisibleActionRequirement:
    name: str
    argument_fragments: tuple[str, ...]
    visible_labels: tuple[str, ...]


@dataclass(frozen=True)
class _CardScenarioRequirement:
    match_terms: tuple[str, ...]
    excluded_terms: tuple[str, ...] = ()
    content_hints: tuple[str, ...] = ()
    content_requirements: tuple[_VisibleContentRequirement, ...] = ()
    action_requirements: tuple[_VisibleActionRequirement, ...] = ()


_CARD_SCENARIO_REQUIREMENTS = (
    _CardScenarioRequirement(
        match_terms=("雨天打车",),
        content_hints=("天气状况", "降水概率"),
        content_requirements=(
            _VisibleContentRequirement(
                name="天气状况",
                path_fragments=("/current/condition",),
            ),
            _VisibleContentRequirement(
                name="降水概率",
                path_fragments=("rainprobabilitypercent",),
                visible_labels=("降水概率", "降雨概率"),
            ),
        ),
        action_requirements=(
            _VisibleActionRequirement(
                name="打车去公司",
                argument_fragments=("startnavigate",),
                visible_labels=("打车去公司",),
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("低电模式",),
        content_hints=("电量", "电池状态"),
        content_requirements=(
            _VisibleContentRequirement(
                name="电量",
                visible_labels=("电量",),
                value_kind="percent",
            ),
            _VisibleContentRequirement(
                name="电池状态",
                visible_labels=(
                    "电量偏低",
                    "电量低",
                    "低电量",
                    "电量正常",
                    "电量充足",
                    "需省电",
                    "充电中",
                    "未充电",
                    "状态良好",
                ),
            ),
        ),
        action_requirements=(
            _VisibleActionRequirement(
                name="开启省电模式",
                argument_fragments=("battery_saving_mode",),
                visible_labels=("开启省电", "省电模式"),
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("耳机播控", "戴耳机播控"),
        content_hints=("耳机电量", "华为音乐每日推荐"),
        content_requirements=(
            _VisibleContentRequirement(
                name="耳机电量",
                visible_labels=("耳机电量", "电量"),
                value_kind="percent",
            ),
            _VisibleContentRequirement(
                name="华为音乐每日推荐",
                visible_labels=("每日推荐",),
            ),
        ),
        action_requirements=(
            _VisibleActionRequirement(
                name="打开华为音乐每日推荐",
                argument_fragments=("hwmusic",),
                visible_labels=("打开歌单", "打开音乐", "播放", "每日推荐"),
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("睡眠卡片", "睡眠助手"),
        content_hints=("睡眠状态", "睡眠时长", "睡眠时长占比"),
        content_requirements=(
            _VisibleContentRequirement(
                name="睡眠状态",
                visible_labels=(
                    "睡眠中",
                    "已入睡",
                    "深度睡眠",
                    "浅睡眠",
                    "清醒",
                    "已醒",
                    "未入睡",
                ),
            ),
            _VisibleContentRequirement(
                name="睡眠时长",
                visible_labels=("睡眠时长",),
                value_kind="duration",
            ),
            _VisibleContentRequirement(
                name="睡眠时长占比",
                visible_labels=("占比", "完成", "目标"),
                value_kind="percent",
            ),
        ),
        action_requirements=(
            _VisibleActionRequirement(
                name="设置闹钟提醒",
                argument_fragments=("com.huawei.hmos.clock",),
                visible_labels=("设置闹钟", "设闹钟", "闹钟提醒"),
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("专注模式",),
        content_hints=("下一场会议名称", "下一场会议开始时间"),
        content_requirements=(
            _VisibleContentRequirement(
                name="下一场会议名称",
                path_fragments=("/items/0/title",),
            ),
            _VisibleContentRequirement(
                name="下一场会议开始时间",
                path_fragments=("/items/0/dtstart",),
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("当下日程",),
        content_hints=("今日日程名称", "今日日程开始时间"),
        content_requirements=(
            _VisibleContentRequirement(
                name="今日日程名称",
                path_fragments=("/items/0/title",),
            ),
            _VisibleContentRequirement(
                name="今日日程开始时间",
                path_fragments=("/items/0/dtstart",),
            ),
        ),
        action_requirements=(
            _VisibleActionRequirement(
                name="查看日程",
                argument_fragments=("viewcalendarevent",),
                visible_labels=("查看日程",),
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("防沉迷",),
        content_hints=("本周APP使用时长",),
        content_requirements=(
            _VisibleContentRequirement(
                name="本周范围",
                visible_labels=("本周", "本周监控"),
            ),
            _VisibleContentRequirement(
                name="APP使用时长",
                visible_labels=("APP使用时长", "应用使用时长"),
                value_kind="duration",
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("清理无忧",),
        content_hints=("剩余空间", "占用占比"),
        content_requirements=(
            _VisibleContentRequirement(
                name="剩余空间",
                visible_labels=("剩余空间", "剩余", "可用空间", "可用"),
                value_kind="storage",
            ),
            _VisibleContentRequirement(
                name="占用占比",
                visible_labels=("占用占比", "占用", "已用", "使用率"),
                value_kind="percent",
            ),
        ),
    ),
    _CardScenarioRequirement(
        match_terms=("天气",),
        excluded_terms=("打车",),
        content_hints=("天气状况", "温度", "湿度"),
        content_requirements=(
            _VisibleContentRequirement(
                name="天气状况",
                path_fragments=("/current/condition",),
            ),
            _VisibleContentRequirement(
                name="温度",
                path_fragments=("/current/temperaturetext",),
            ),
            _VisibleContentRequirement(
                name="湿度",
                path_fragments=("/current/humiditypercent",),
            ),
        ),
    ),
)

_WEATHER_FORECAST_HINT = "天气预报"
_WEATHER_FORECAST_REQUIREMENTS = (
    _VisibleContentRequirement(
        name=_WEATHER_FORECAST_HINT,
        path_fragments=("temperaturerangetext",),
    ),
)
_WEATHER_ICON_ID_TERMS = ("weather", "condition", "天气", "状况")
_WEATHER_ICON_CONDITION_RULES = (
    (("sun", "sunny"), ("晴",)),
    (("cloud", "overcast"), ("云", "阴")),
    (("rain", "drop"), ("雨",)),
    (("snow",), ("雪",)),
)


@dataclass
class _LayoutContainerState:
    row: list[Any]
    used_space: float = 0.0
    child_count: int = 0
    is_root: bool = False


_DYNAMIC_BINDING_RULES = (
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "temperatureText"),
        strong_aliases=(
            "temperaturetext",
            "temperaturevalue",
            "currenttemperature",
            "tempvalue",
        ),
        weak_aliases=("primaryvalue",),
        source_aliases=("temperature", "temp"),
        value_pattern=_DEGREE_VALUE_PATTERN,
        preview_value="26°C",
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "condition"),
        strong_aliases=(
            "weatherstate",
            "weatherstatus",
            "weathercondition",
            "weatherbadgetext",
            "condition",
            "conditiontext",
            "statuspill",
        ),
        source_aliases=("condition", "state", "status", "weatherdesc"),
        preview_value="小雨",
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "humidityPercent"),
        strong_aliases=(
            "humidityvalue",
            "humiditypercent",
            "humiditytext",
            "humidity",
        ),
        source_aliases=("humidity",),
        value_pattern=_PERCENT_VALUE_PATTERN,
        display_suffix="%",
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "feelsLikeC"),
        strong_aliases=(
            "feelslike",
            "feelstext",
            "feelsvalue",
            "apparenttemperature",
        ),
        weak_aliases=("primarycaption",),
        source_aliases=("feelslike", "caption"),
        value_pattern=_FEELS_LIKE_VALUE_PATTERN,
        display_prefix="体感 ",
        display_suffix="°",
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "airQuality"),
        strong_aliases=("airquality", "aqi"),
        source_aliases=("airquality", "aqi"),
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "windDirection"),
        strong_aliases=("winddirection",),
        source_aliases=("winddirection",),
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("current", "windLevel"),
        strong_aliases=("windlevel", "windvalue"),
        source_aliases=("windlevel",),
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("daily", "0", "weekday"),
        strong_aliases=("forecastday", "weekday"),
        source_aliases=("forecastday", "weekday"),
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("daily", "0", "temperatureRangeText"),
        strong_aliases=("trendvalue", "forecasttemperature", "temperaturerange"),
        source_aliases=("forecast", "daily", "temperaturerange"),
        preview_value="24° / 32°",
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("daily", "0", "rainProbabilityPercent"),
        strong_aliases=(
            "rainprobabilitypercent",
            "rainprobability",
            "precipitationprobability",
            "rainchance",
        ),
        weak_aliases=("primaryvalue",),
        source_aliases=("rainprobability", "precipitationprobability", "rainchance"),
        value_pattern=_PERCENT_VALUE_PATTERN,
        preview_value="72%",
    ),
    _DynamicBindingRule(
        capability_id="ViewWeather",
        relative_path=("updatedAt",),
        strong_aliases=("updatedat", "updatetime"),
        source_aliases=("updatedat", "updatetime"),
    ),
    _DynamicBindingRule(
        capability_id="calendar.events.search",
        relative_path=("items", "0", "title"),
        strong_aliases=("eventtitle", "scheduletitle", "itemtitle"),
        weak_aliases=("contexttitle", "primaryvalue"),
        source_aliases=("eventtitle", "scheduletitle", "title"),
        preview_value="下一场日程",
    ),
    _DynamicBindingRule(
        capability_id="calendar.events.search",
        relative_path=("items", "0", "dtStart"),
        strong_aliases=("eventtime", "starttime", "dtstart"),
        weak_aliases=("contextmeta",),
        source_aliases=("eventtime", "starttime", "dtstart"),
        value_pattern=_TIME_VALUE_PATTERN,
        preview_value="09:00",
    ),
    _DynamicBindingRule(
        capability_id="calendar.events.search",
        relative_path=("items", "0", "dtEnd"),
        strong_aliases=("endtime", "dtend"),
        source_aliases=("endtime", "dtend"),
        value_pattern=_TIME_VALUE_PATTERN,
        preview_value="10:00",
    ),
    _DynamicBindingRule(
        capability_id="calendar.events.search",
        relative_path=("items", "0", "eventLocation"),
        strong_aliases=("eventlocation", "locationtext", "locationvalue"),
        source_aliases=("eventlocation", "location"),
        preview_value="待确认",
    ),
    _DynamicBindingRule(
        capability_id="calendar.events.search",
        relative_path=("items", "0", "description"),
        strong_aliases=("eventdescription", "descriptiontext"),
        source_aliases=("eventdescription", "description"),
        preview_value="日程详情",
    ),
)

_TEXT_VISUAL_PROPS = {
    "fontSize",
    "fontWeight",
    "fontColor",
    "maxLines",
    "textOverflow",
    "textAlign",
}
_STATIC_TEXT_ROLE_TERMS = ("label", "caption", "prefix", "suffix", "unit", "hint")


def is_compact_dsl(protocol_profile: dict[str, Any]) -> bool:
    """Return whether a loaded profile uses tuple-based Compact DSL."""
    return protocol_profile.get("format") == COMPACT_DSL_FORMAT


def build_compact_dsl_system_prompt(protocol_profile: dict[str, Any]) -> str:
    """Build a Form-equivalent prompt whose only delta is Compact serialization."""
    allowed = ", ".join(protocol_profile.get("componentWhitelist", COMPONENT_WHITELIST))
    documents = protocol_profile.get("documents", {})
    prompt_template = documents.get("system-prompt.md")
    if not isinstance(prompt_template, str) or not prompt_template.strip():
        raise ValueError("Compact DSL profile requires system-prompt.md")
    return prompt_template.strip().replace("{{COMPONENT_WHITELIST}}", allowed)


def _match_card_scenario(
    task_spec: dict[str, Any] | str | None,
) -> _CardScenarioRequirement | None:
    normalized_text = _normalized_task_text(task_spec)
    if not normalized_text:
        return None

    for scenario in _CARD_SCENARIO_REQUIREMENTS:
        excluded = False
        for term in scenario.excluded_terms:
            if _normalize_visible_text(term) in normalized_text:
                excluded = True
                break
        if excluded:
            continue
        for term in scenario.match_terms:
            if _normalize_visible_text(term) in normalized_text:
                return scenario
    return None


def _normalized_task_text(task_spec: dict[str, Any] | str | None) -> str:
    task_spec_value = _object_as_dict(task_spec)
    if task_spec_value is None:
        return ""

    text_parts: list[str] = []
    for key in ("userQuery", "title", "description"):
        value = task_spec_value.get(key)
        if isinstance(value, str) and value.strip():
            text_parts.append(value)
    return _normalize_visible_text(" ".join(text_parts))


def _normalized_user_query(task_spec: dict[str, Any] | str | None) -> str:
    task_spec_value = _object_as_dict(task_spec)
    if task_spec_value is None:
        return ""
    user_query = task_spec_value.get("userQuery")
    if not isinstance(user_query, str):
        return ""
    return _normalize_visible_text(user_query)


def _is_weather_forecast_task(task_spec: dict[str, Any] | str | None) -> bool:
    normalized_query = _normalized_user_query(task_spec)
    has_weather = _normalize_visible_text("天气") in normalized_query
    has_forecast = _normalize_visible_text("预报") in normalized_query
    has_taxi = _normalize_visible_text("打车") in normalized_query
    return has_weather and has_forecast and not has_taxi


def _active_action_requirements(
    task_spec: dict[str, Any] | str | None,
    scenario: _CardScenarioRequirement,
) -> tuple[_VisibleActionRequirement, ...]:
    task_spec_value = _object_as_dict(task_spec)
    if task_spec_value is None:
        return scenario.action_requirements
    source_events = task_spec_value.get("eventCandidates")
    if not isinstance(source_events, list):
        return scenario.action_requirements

    active_requirements: list[_VisibleActionRequirement] = []
    for requirement in scenario.action_requirements:
        for source_event in source_events:
            event_value = _object_as_dict(source_event)
            if event_value is None:
                continue
            event_text = json.dumps(
                event_value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            normalized_event = _normalize_visible_text(event_text)
            if not _action_arguments_match(
                requirement.argument_fragments,
                normalized_event,
            ):
                continue
            active_requirements.append(requirement)
            break
    return tuple(active_requirements)


def build_compact_generation_context(
    task_spec: dict[str, Any],
    removed_capability_summary: str = "",
) -> dict[str, Any]:
    """Build a compact model-only task context without duplicate runtime metadata."""
    compact_task: dict[str, Any] = {}
    for key in ("size", "title"):
        value = task_spec.get(key)
        if value is not None:
            compact_task[key] = value

    scenario = _match_card_scenario(task_spec)
    if scenario is None:
        description = task_spec.get("description")
        if description is not None:
            compact_task["description"] = description
    if scenario is not None:
        content_hints = list(scenario.content_hints)
        if _is_weather_forecast_task(task_spec):
            content_hints.append(_WEATHER_FORECAST_HINT)
        if content_hints:
            compact_task["requiredContent"] = content_hints
        active_actions = _active_action_requirements(task_spec, scenario)
        if active_actions:
            compact_task["requiredActions"] = []
            for requirement in active_actions:
                compact_task["requiredActions"].append(requirement.name)

    events: list[dict[str, Any]] = []
    source_events = task_spec.get("eventCandidates")
    if isinstance(source_events, list):
        for source_event in source_events:
            event_value = _object_as_dict(source_event)
            if event_value is None:
                continue
            call = event_value.get("call")
            args = event_value.get("args")
            if isinstance(call, str) and call and isinstance(args, dict):
                events.append({"call": call, "args": args})
    if events:
        compact_task["events"] = events

    assets: list[dict[str, str]] = []
    source_assets = task_spec.get("assetCandidates")
    if isinstance(source_assets, list):
        for source_asset in source_assets:
            asset_value = _object_as_dict(source_asset)
            if asset_value is None:
                continue
            src = asset_value.get("src")
            if not isinstance(src, str) or not src:
                continue
            asset = {"src": src}
            description = asset_value.get("description")
            if isinstance(description, str) and description:
                asset["description"] = description[:_SCHEMA_DESCRIPTION_LIMIT]
            assets.append(asset)
    if assets:
        compact_task["assets"] = assets

    context = {"task": compact_task}
    if removed_capability_summary:
        context["degradation"] = removed_capability_summary
    return context


def build_compact_binding_context(
    cardspec: dict[str, Any] | None,
    data_capabilities: list[Any] | None,
) -> dict[str, Any] | None:
    """Flatten output schemas into short canonical field paths for model generation."""
    cardspec_value = _object_as_dict(cardspec)
    if cardspec_value is None:
        return None
    source_bindings = cardspec_value.get("dataBindings")
    if not isinstance(source_bindings, list):
        return None

    fields_by_capability: dict[str, list[list[Any]]] = {}
    for source_capability in data_capabilities or []:
        capability_value = _object_as_dict(source_capability)
        if capability_value is None:
            continue
        capability_id = capability_value.get("id")
        output_schema = capability_value.get("outputSchema")
        if not isinstance(capability_id, str) or not isinstance(output_schema, dict):
            continue
        fields_by_capability[capability_id] = _compact_schema_fields(output_schema)

    bindings: list[dict[str, Any]] = []
    for source_binding in source_bindings:
        binding_value = _object_as_dict(source_binding)
        if binding_value is None:
            continue
        capability_id = binding_value.get("capabilityId")
        write_result_to = binding_value.get("writeResultTo")
        if not isinstance(capability_id, str):
            continue
        if not _is_json_pointer_value(write_result_to):
            continue
        compact_binding: dict[str, Any] = {
            "id": capability_id,
            "root": write_result_to,
        }
        arguments = binding_value.get("arguments")
        if isinstance(arguments, dict) and arguments:
            compact_binding["args"] = arguments
        fields = fields_by_capability.get(capability_id)
        if fields:
            compact_binding["fields"] = fields
        bindings.append(compact_binding)
    if not bindings:
        return None
    return {"bindings": bindings}


def _compact_schema_fields(output_schema: dict[str, Any]) -> list[list[Any]]:
    """Return leaf fields as relative JSON Pointer, type, and short description rows."""
    fields: list[list[Any]] = []
    _append_compact_schema_fields(output_schema, "", fields)
    return fields


def _append_compact_schema_fields(
    schema: dict[str, Any],
    pointer: str,
    fields: list[list[Any]],
) -> None:
    schema_type = schema.get("type")
    properties = schema.get("properties")
    if schema_type == "object" and isinstance(properties, dict) and properties:
        for key, child_schema in properties.items():
            if not isinstance(child_schema, dict):
                continue
            escaped_key = str(key).replace("~", "~0").replace("/", "~1")
            _append_compact_schema_fields(child_schema, f"{pointer}/{escaped_key}", fields)
        return

    items = schema.get("items")
    if schema_type == "array" and isinstance(items, dict):
        _append_compact_schema_fields(items, f"{pointer}/0", fields)
        return

    field_type = schema_type if isinstance(schema_type, str) else "any"
    field: list[Any] = [pointer or "/", field_type]
    description = schema.get("description")
    if isinstance(description, str) and description:
        field.append(description[:_SCHEMA_DESCRIPTION_LIMIT])
    fields.append(field)


def apply_compact_dsl_data_bindings(
    genui_text: str,
    cardspec: dict[str, Any] | str | None,
    data_capabilities: list[Any] | None,
    event_candidates: list[Any] | None = None,
) -> str:
    """Bind visible dynamic fields to existing CardSpec capability output paths."""
    normalized, _ = _prepare_compact_dsl(
        genui_text,
        cardspec,
        data_capabilities,
        event_candidates,
        None,
    )
    return normalized


def preflight_compact_dsl(
    genui_text: str,
    cardspec: dict[str, Any] | str | None,
    data_capabilities: list[Any] | None,
    event_candidates: list[Any] | None = None,
    task_spec: dict[str, Any] | str | None = None,
) -> CompactDSLPreflightResult:
    """Normalize and check the deterministic Compact DSL boundary."""
    try:
        normalized, repairs = _prepare_compact_dsl(
            genui_text,
            cardspec,
            data_capabilities,
            event_candidates,
            task_spec,
        )
    except ValueError as exc:
        message = str(exc)
        diagnostic = CompactDSLDiagnostic(
            category=_preflight_error_category(message),
            severity="error",
            message=message,
        )
        return CompactDSLPreflightResult(
            genui="",
            repairs=(),
            diagnostics=(diagnostic,),
        )
    return CompactDSLPreflightResult(
        genui=normalized,
        repairs=repairs,
        diagnostics=(),
    )


def _prepare_compact_dsl(
    genui_text: str,
    cardspec: dict[str, Any] | str | None,
    data_capabilities: list[Any] | None,
    event_candidates: list[Any] | None,
    task_spec: dict[str, Any] | str | None,
) -> tuple[str, tuple[str, ...]]:
    repairs: set[str] = set()
    rows = _read_compact_rows(genui_text, repairs)
    before_contract_repair = _serialize_compact_rows(rows)
    _repair_form_contract_props(rows, cardspec)
    if _serialize_compact_rows(rows) != before_contract_repair:
        repairs.add("FORM_CONTRACT_REPAIRED")
    _materialize_unbacked_display_bindings(rows, cardspec)
    targets = _build_dynamic_binding_targets(cardspec, data_capabilities)
    bound_rows = _apply_dynamic_binding_targets(rows, targets)
    before_presentation_repair = _serialize_compact_rows(bound_rows)
    _ensure_sleep_calendar_binding(bound_rows, cardspec, targets)
    _repair_relative_day_bindings(bound_rows)
    _repair_button_like_action_row(bound_rows, event_candidates)
    _repair_calendar_event_presentation(bound_rows)
    if _repair_required_content_bindings(bound_rows, task_spec, targets):
        repairs.add("REQUIRED_CONTENT_REPAIRED")
        _repair_form_text_fit(bound_rows)
    if _serialize_compact_rows(bound_rows) != before_presentation_repair:
        repairs.add("PRESENTATION_BINDING_REPAIRED")
    _validate_compact_function_calls(bound_rows, event_candidates, cardspec)
    return _serialize_compact_rows(bound_rows), tuple(sorted(repairs))


def _preflight_error_category(message: str) -> str:
    normalized = message.lower()
    if "invalid json" in normalized or "line must be a json array" in normalized:
        return _ISSUE_SYNTAX
    if "must use an available eventcandidate" in normalized:
        return _ISSUE_SEMANTIC
    if "functioncall" in normalized or "eventcandidate" in normalized:
        return _ISSUE_BINDING
    return _ISSUE_STRUCTURE


def _repair_required_content_bindings(
    rows: list[list[Any]],
    task_spec: dict[str, Any] | str | None,
    targets: list[_DynamicBindingTarget],
) -> bool:
    requirements = _required_dynamic_content_requirements(task_spec)
    if not requirements or not targets:
        return False

    visible_paths = _compact_visible_binding_paths(rows)
    required_fragment_values: list[str] = []
    for requirement in requirements:
        for fragment in requirement.path_fragments:
            required_fragment_values.append(fragment.lower())
    required_fragments = tuple(required_fragment_values)
    repaired = False
    for requirement in requirements:
        if _requirement_has_visible_path(requirement, visible_paths):
            continue
        target = _target_for_content_requirement(requirement, targets)
        if target is None or not _has_renderable_preview(target.initial_value):
            continue
        inserted = _insert_required_binding_in_row(rows, target)
        if not inserted:
            inserted = _replace_optional_dynamic_binding(
                rows,
                target,
                required_fragments,
            )
        if not inserted:
            continue
        rows.append([target.path, target.initial_value])
        visible_paths.add(target.path.lower())
        repaired = True
    return repaired


def _required_dynamic_content_requirements(
    task_spec: dict[str, Any] | str | None,
) -> tuple[_VisibleContentRequirement, ...]:
    scenario = _match_card_scenario(task_spec)
    if scenario is None:
        return ()

    requirements = list(scenario.content_requirements)
    if _is_weather_forecast_task(task_spec):
        requirements.extend(_WEATHER_FORECAST_REQUIREMENTS)
    dynamic_requirements: list[_VisibleContentRequirement] = []
    for requirement in requirements:
        if requirement.path_fragments:
            dynamic_requirements.append(requirement)
    return tuple(dynamic_requirements)


def _compact_visible_binding_paths(rows: list[list[Any]]) -> set[str]:
    paths: set[str] = set()
    for row in rows:
        if not _is_component_row(row):
            continue
        props = row[2]
        for prop_name in _dynamic_prop_names(row[1], props):
            binding = props.get(prop_name)
            if _is_path_binding(binding):
                paths.add(binding["path"].lower())
    return paths


def _requirement_has_visible_path(
    requirement: _VisibleContentRequirement,
    visible_paths: set[str],
) -> bool:
    for fragment in requirement.path_fragments:
        normalized_fragment = fragment.lower()
        for path in visible_paths:
            if normalized_fragment in path:
                return True
    return False


def _target_for_content_requirement(
    requirement: _VisibleContentRequirement,
    targets: list[_DynamicBindingTarget],
) -> _DynamicBindingTarget | None:
    for fragment in requirement.path_fragments:
        normalized_fragment = fragment.lower()
        for target in targets:
            if normalized_fragment in target.path.lower():
                return target
    return None


def _has_renderable_preview(value: Any) -> bool:
    if value is _MISSING or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return _is_number(value)


def _insert_required_binding_in_row(
    rows: list[list[Any]],
    target: _DynamicBindingTarget,
) -> bool:
    components = {
        row[0]: row
        for row in rows
        if _is_component_row(row)
    }
    preview_text = str(target.initial_value)
    minimum_width = max(24, math.ceil(_estimate_text_width(preview_text, 10)))
    candidates: list[tuple[float, list[Any]]] = []
    for row in components.values():
        free_width = _row_free_width_for_new_child(row, components)
        if free_width is None or free_width < minimum_width:
            continue
        candidates.append((free_width, row))
    if not candidates:
        return False

    _, parent = min(candidates, key=lambda candidate: candidate[0])
    component_id = _unique_required_component_id(components, target)
    props = _required_binding_text_props(parent, components, target, minimum_width)
    parent[3].append(component_id)
    rows.append([component_id, "Text", props])
    return True


def _row_free_width_for_new_child(
    row: list[Any],
    components: dict[str, list[Any]],
) -> float | None:
    if row[1] != "Row" or len(row) != 4:
        return None
    capacity = _layout_capacity(row[2], "width")
    if capacity is None:
        return None
    spacing = _numeric_value(row[2].get("space")) or 0.0
    used_width = spacing * len(row[3])
    for child_id in row[3]:
        child = components.get(child_id)
        if child is None:
            return None
        child_width = _numeric_value(child[2].get("width"))
        if child_width is None:
            return None
        used_width += child_width
    return max(0.0, capacity - used_width)


def _unique_required_component_id(
    components: dict[str, list[Any]],
    target: _DynamicBindingTarget,
) -> str:
    path_name = target.rule.relative_path[-1]
    normalized_name = re.sub(r"[^A-Za-z0-9_]", "_", path_name)
    base_id = f"required_{normalized_name}"
    component_id = base_id
    suffix = 2
    while component_id in components:
        component_id = f"{base_id}_{suffix}"
        suffix += 1
    return component_id


def _required_binding_text_props(
    parent: list[Any],
    components: dict[str, list[Any]],
    target: _DynamicBindingTarget,
    width: int,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        "width": width,
        "height": min(16, int(_numeric_value(parent[2].get("height")) or 16)),
        "content": {"path": target.path},
        "fontSize": 10,
        "maxLines": 1,
        "textAlign": "end",
    }
    for child_id in reversed(parent[3]):
        sibling = components.get(child_id)
        if sibling is None or sibling[1] != "Text":
            continue
        sibling_props = sibling[2]
        for prop_name in ("fontWeight", "fontColor"):
            if prop_name in sibling_props:
                props[prop_name] = sibling_props[prop_name]
        break
    return props


def _replace_optional_dynamic_binding(
    rows: list[list[Any]],
    target: _DynamicBindingTarget,
    required_fragments: tuple[str, ...],
) -> bool:
    candidates: list[tuple[float, list[Any]]] = []
    for row in rows:
        if not _is_component_row(row) or row[1] != "Text":
            continue
        binding = row[2].get("content")
        if not _is_path_binding(binding):
            continue
        source_path = binding["path"]
        if not _path_is_at_or_below(source_path, target.binding_root):
            continue
        normalized_path = source_path.lower()
        if any(fragment in normalized_path for fragment in required_fragments):
            continue
        width = _numeric_value(row[2].get("width")) or 0.0
        candidates.append((width, row))
    if not candidates:
        return False

    _, component = max(candidates, key=lambda candidate: candidate[0])
    component[2]["content"] = {"path": target.path}
    component[2]["fontSize"] = 10
    component[2]["maxLines"] = 1
    return True


def _ensure_sleep_calendar_binding(
    rows: list[list[Any]],
    cardspec: dict[str, Any] | str | None,
    targets: list[_DynamicBindingTarget],
) -> None:
    cardspec_value = _object_as_dict(cardspec)
    if cardspec_value is None:
        return
    bindings = cardspec_value.get("dataBindings")
    if not isinstance(bindings, list):
        return

    for binding in bindings:
        binding_value = _object_as_dict(binding)
        if binding_value is None:
            continue
        capability_id = binding_value.get("capabilityId")
        binding_root = binding_value.get("writeResultTo")
        if capability_id != "calendar.events.search":
            continue
        if not _is_json_pointer_value(binding_root):
            continue
        root_name = _normalize_semantic_name(binding_root.rsplit("/", 1)[-1])
        if "sleep" not in root_name:
            continue
        if _rows_use_binding_root(rows, binding_root):
            continue
        target = _sleep_calendar_title_target(targets, binding_root)
        if target is None:
            continue
        _bind_sleep_status_text(rows, target)


def _rows_use_binding_root(rows: list[list[Any]], binding_root: str) -> bool:
    for row in rows:
        if not _is_component_row(row):
            continue
        for _, path, _ in _path_bindings(row[2]):
            if _path_is_at_or_below(path, binding_root):
                return True
    return False


def _sleep_calendar_title_target(
    targets: list[_DynamicBindingTarget],
    binding_root: str,
) -> _DynamicBindingTarget | None:
    for target in targets:
        if target.binding_root != binding_root:
            continue
        if target.rule.capability_id != "calendar.events.search":
            continue
        if target.rule.relative_path == ("items", "0", "title"):
            return target
    return None


def _bind_sleep_status_text(
    rows: list[list[Any]],
    target: _DynamicBindingTarget,
) -> None:
    selected_index: int | None = None
    selected_score = -1
    for index, row in enumerate(rows):
        score = _sleep_status_text_score(row)
        if score <= selected_score:
            continue
        selected_index = index
        selected_score = score
    if selected_index is None:
        return

    selected_row = rows[selected_index]
    preview_value = selected_row[2].get("content")
    if not isinstance(preview_value, str) or not preview_value.strip():
        preview_value = target.initial_value
    if not isinstance(preview_value, str) or not preview_value.strip():
        return
    selected_row[2]["content"] = {"path": target.path}
    rows.insert(selected_index + 1, [target.path, preview_value])


def _sleep_status_text_score(row: list[Any]) -> int:
    if not _is_component_row(row) or row[1] != "Text":
        return -1
    content = row[2].get("content")
    if not isinstance(content, str) or not content.strip():
        return -1

    normalized_id = _normalize_semantic_name(row[0])
    if "alarm" in normalized_id or "calendar" in normalized_id:
        return -1
    if normalized_id == "statustext":
        return 100
    if "sleep" in normalized_id and "status" in normalized_id:
        return 95
    if normalized_id in {"statuspill", "statusbadge"}:
        return 90
    if "status" in normalized_id:
        return 80
    if "sleep" in normalized_id and "stage" in normalized_id:
        return 70
    return -1


def _materialize_unbacked_display_bindings(
    rows: list[list[Any]],
    cardspec: dict[str, Any] | str | None,
) -> None:
    """Keep preview-only display values static when no capability can update them."""
    binding_roots = _cardspec_data_binding_roots(cardspec)
    data_values: dict[str, Any] = {}
    for row in rows:
        if _is_compact_data_row(row) and len(row) == 2:
            _record_compact_data_values(row[0], row[1], data_values)

    for row in rows:
        if not _is_component_row(row):
            continue
        component_type = row[1]
        props = row[2]
        for prop_name in _dynamic_prop_names(component_type, props):
            binding = props.get(prop_name)
            if not _is_path_binding(binding):
                continue
            path = binding["path"]
            if any(_path_is_at_or_below(path, root) for root in binding_roots):
                continue
            literal = _display_literal(data_values.get(path, _MISSING))
            if literal is _MISSING:
                continue
            props[prop_name] = literal


def _cardspec_data_binding_roots(
    cardspec: dict[str, Any] | str | None,
) -> tuple[str, ...]:
    cardspec_value = _object_as_dict(cardspec)
    if cardspec_value is None:
        return ()
    bindings = cardspec_value.get("dataBindings")
    if not isinstance(bindings, list):
        return ()

    roots: list[str] = []
    for binding in bindings:
        binding_value = _object_as_dict(binding)
        if binding_value is None:
            continue
        root = binding_value.get("writeResultTo")
        if _is_json_pointer_value(root):
            roots.append(root)
    return tuple(roots)


def _display_literal(value: Any) -> str | object:
    if value is _MISSING or value is None or isinstance(value, (dict, list)):
        return _MISSING
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _repair_relative_day_bindings(rows: list[list[Any]]) -> None:
    replacements: dict[str, str] = {}
    for row in rows:
        if not _is_compact_data_row(row) or len(row) != 2:
            continue
        path, value = row
        if not isinstance(path, str) or not isinstance(value, str):
            continue
        match = _DAILY_WEEKDAY_PATH_PATTERN.fullmatch(path)
        expected_index = _RELATIVE_DAY_INDEX.get(value.strip().lower())
        if match is None or expected_index is None:
            continue
        current_index = int(match.group("index"))
        if current_index == expected_index:
            continue
        replacements[path] = (
            f'{match.group("prefix")}{expected_index}{match.group("suffix")}'
        )

    if not replacements:
        return

    for row in rows:
        if _is_component_row(row):
            _replace_compact_binding_paths(row[2], replacements)
        elif _is_compact_data_row(row) and row[0] in replacements:
            row[0] = replacements[row[0]]
    _deduplicate_compact_data_rows(rows)


def _replace_compact_binding_paths(
    value: Any,
    replacements: dict[str, str],
) -> None:
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str) and path in replacements:
            value["path"] = replacements[path]
        for child_value in value.values():
            _replace_compact_binding_paths(child_value, replacements)
    elif isinstance(value, list):
        for child_value in value:
            _replace_compact_binding_paths(child_value, replacements)


def _deduplicate_compact_data_rows(rows: list[list[Any]]) -> None:
    seen_paths: set[str] = set()
    deduplicated: list[list[Any]] = []
    for row in rows:
        if not _is_compact_data_row(row):
            deduplicated.append(row)
            continue
        path = row[0]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        deduplicated.append(row)
    rows[:] = deduplicated


def _repair_button_like_action_row(
    rows: list[list[Any]],
    event_candidates: list[Any] | None,
) -> None:
    fallback_function_call = _single_static_function_call(event_candidates)
    fallback_used = False
    components: dict[str, list[Any]] = {}
    for row in rows:
        if _is_component_row(row):
            components[row[0]] = row

    removed_ids: set[str] = set()
    for row in rows:
        if not _is_button_like_action_row(row):
            continue
        label_row = _button_like_action_label(row, components)
        if label_row is None:
            continue
        function_call = _button_like_function_call(row[2])
        if "action" in row[2] and function_call is None:
            continue
        if function_call is None:
            if fallback_function_call is None or fallback_used:
                continue
            function_call = fallback_function_call
            fallback_used = True
        props = dict(row[2])
        for prop_name in ("alignItems", "justifyContent", "space"):
            props.pop(prop_name, None)
        for prop_name in ("fontSize", "fontWeight", "fontColor"):
            if prop_name in label_row[2]:
                props[prop_name] = label_row[2][prop_name]
        props["label"] = label_row[2]["content"]
        props["enabled"] = True
        props["action"] = {"functionCall": function_call}
        removed_ids.update(row[3])
        row[:] = [row[0], "Button", props]
    if not removed_ids:
        return

    remaining_rows: list[list[Any]] = []
    for row in rows:
        if _is_component_row(row) and row[0] in removed_ids:
            continue
        remaining_rows.append(row)
    rows[:] = _order_reachable_compact_rows(remaining_rows)


def _button_like_function_call(props: dict[str, Any]) -> dict[str, Any] | None:
    action = props.get("action")
    if not isinstance(action, dict):
        return None
    function_call = action.get("functionCall")
    if not isinstance(function_call, dict):
        return None
    call = function_call.get("call")
    args = function_call.get("args")
    if not isinstance(call, str) or not call or not isinstance(args, dict):
        return None
    return {"call": call, "args": args}


def _repair_calendar_event_presentation(rows: list[list[Any]]) -> None:
    if not _repair_view_calendar_button_labels(rows):
        return
    _remove_generic_calendar_description(rows)


def _repair_view_calendar_button_labels(rows: list[list[Any]]) -> bool:
    found_view_calendar_action = False
    for row in rows:
        if not _is_component_row(row) or row[1] != "Button":
            continue
        action = row[2].get("action")
        function_call = action.get("functionCall") if isinstance(action, dict) else None
        if not isinstance(function_call, dict):
            continue
        args = function_call.get("args")
        if not isinstance(args, dict):
            continue
        if args.get("intentName") != "ViewCalendarEvent":
            continue
        found_view_calendar_action = True
        label = row[2].get("label")
        if isinstance(label, str) and ("日程" in label or "日历" in label):
            continue
        row[2]["label"] = "查看日程"
    return found_view_calendar_action


def _remove_generic_calendar_description(rows: list[list[Any]]) -> None:
    data_values = {
        row[0]: row[1]
        for row in rows
        if _is_compact_data_row(row) and len(row) == 2
    }
    parents: dict[str, list[Any]] = {}
    for row in rows:
        if not _is_component_row(row) or len(row) != 4:
            continue
        for child_id in row[3]:
            parents.setdefault(child_id, row)

    removed_ids: set[str] = set()
    removed_paths: set[str] = set()
    for row in rows:
        if not _is_component_row(row) or row[1] != "Text":
            continue
        content = row[2].get("content")
        if not _is_path_binding(content):
            continue
        path = content["path"]
        if not path.endswith("/description"):
            continue
        if data_values.get(path) not in {"日程详情", "事件详情", "详情"}:
            continue
        parent = parents.get(row[0])
        if parent is None or len(parent[3]) <= 1:
            continue
        parent[3] = [child_id for child_id in parent[3] if child_id != row[0]]
        if parent[1] == "Column":
            parent[2].setdefault("justifyContent", "center")
        removed_ids.add(row[0])
        removed_paths.add(path)

    if not removed_ids:
        return
    remaining_rows: list[list[Any]] = []
    for row in rows:
        if _is_component_row(row) and row[0] in removed_ids:
            continue
        remaining_rows.append(row)

    referenced_paths: set[str] = set()
    for row in remaining_rows:
        if not _is_component_row(row):
            continue
        for _, path, _ in _path_bindings(row[2]):
            referenced_paths.add(path)

    repaired_rows: list[list[Any]] = []
    for row in remaining_rows:
        if _is_compact_data_row(row):
            path = row[0]
            if path in removed_paths and path not in referenced_paths:
                continue
        repaired_rows.append(row)
    rows[:] = repaired_rows


def _single_static_function_call(
    event_candidates: list[Any] | None,
) -> dict[str, Any] | None:
    if event_candidates is None or len(event_candidates) != 1:
        return None
    candidate_value = _object_as_dict(event_candidates[0])
    if candidate_value is None:
        return None
    call = candidate_value.get("call")
    args = candidate_value.get("args")
    if not isinstance(call, str) or not isinstance(args, dict):
        return None
    if _contains_path_binding(args):
        return None
    return {"call": call, "args": args}


def _contains_path_binding(value: Any) -> bool:
    if _is_path_binding(value):
        return True
    if isinstance(value, dict):
        for child_value in value.values():
            if _contains_path_binding(child_value):
                return True
    elif isinstance(value, list):
        for child_value in value:
            if _contains_path_binding(child_value):
                return True
    return False


def _is_button_like_action_row(row: list[Any]) -> bool:
    if not _is_component_row(row):
        return False
    if row[1] != "Row" or len(row) != 4:
        return False
    normalized_id = _normalize_semantic_name(row[0])
    if "action" not in normalized_id and "button" not in normalized_id:
        return False
    props = row[2]
    if "onClick" in props:
        return False
    if "backgroundColor" not in props and "borderRadius" not in props:
        return False
    height = _numeric_value(props.get("height"))
    return height is not None and height >= 24


def _button_like_action_label(
    row: list[Any],
    components: dict[str, list[Any]],
) -> list[Any] | None:
    label_row: list[Any] | None = None
    for child_id in row[3]:
        child = components.get(child_id)
        if child is None or child[1] not in {"Image", "Text"}:
            return None
        if child[1] == "Image":
            continue
        content = child[2].get("content")
        if label_row is not None:
            return None
        if not isinstance(content, str) or not content.strip():
            return None
        label_row = child
    return label_row


def _validate_compact_function_calls(
    rows: list[list[Any]],
    event_candidates: list[Any] | None,
    cardspec: dict[str, Any] | str | None,
) -> None:
    if event_candidates is None:
        return

    candidate_keys: set[tuple[str, str]] = set()
    candidate_calls: list[tuple[str, dict[str, Any]]] = []
    for candidate in event_candidates:
        candidate_value = _object_as_dict(candidate)
        if candidate_value is None:
            continue
        call = candidate_value.get("call")
        args = candidate_value.get("args")
        if not isinstance(call, str) or not call or not isinstance(args, dict):
            continue
        candidate_keys.add(_function_call_key(call, args))
        candidate_calls.append((call, args))

    generated_calls: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        if not _is_component_row(row) or row[1] != "Button":
            continue
        action = row[2].get("action")
        function_call = action.get("functionCall") if isinstance(action, dict) else None
        if not isinstance(function_call, dict):
            continue
        call = function_call.get("call")
        args = function_call.get("args")
        if not isinstance(call, str) or not isinstance(args, dict):
            continue
        generated_calls.append((call, args))

    binding_roots = _cardspec_data_binding_roots(cardspec)
    for call, args in generated_calls:
        key = _function_call_key(call, args)
        if key in candidate_keys:
            continue
        if _matches_event_candidate(call, args, candidate_calls, binding_roots):
            continue
        raise ValueError("Compact DSL contains a functionCall outside eventCandidates.")
    if candidate_keys and not generated_calls:
        raise ValueError("Compact DSL must use an available eventCandidate in a Button.")


def _matches_event_candidate(
    call: str,
    args: dict[str, Any],
    candidate_calls: list[tuple[str, dict[str, Any]]],
    binding_roots: tuple[str, ...],
) -> bool:
    for candidate_call, candidate_args in candidate_calls:
        if call != candidate_call:
            continue
        if _event_arg_values_match(args, candidate_args, binding_roots):
            return True
    return False


def _event_arg_values_match(
    generated: Any,
    candidate: Any,
    binding_roots: tuple[str, ...],
) -> bool:
    if _is_path_binding(candidate):
        return _event_binding_paths_match(generated, candidate, binding_roots)
    if isinstance(candidate, dict):
        if not isinstance(generated, dict) or set(generated) != set(candidate):
            return False
        for key, candidate_value in candidate.items():
            if not _event_arg_values_match(generated[key], candidate_value, binding_roots):
                return False
        return True
    if isinstance(candidate, list):
        if not isinstance(generated, list) or len(generated) != len(candidate):
            return False
        for index, candidate_value in enumerate(candidate):
            if not _event_arg_values_match(generated[index], candidate_value, binding_roots):
                return False
        return True
    return generated == candidate


def _event_binding_paths_match(
    generated: Any,
    candidate: _PathBinding,
    binding_roots: tuple[str, ...],
) -> bool:
    if not _is_path_binding(generated):
        return False
    candidate_path = candidate["path"]
    generated_path = generated["path"]
    if candidate_path.startswith("/"):
        return generated_path == candidate_path
    if not generated_path.endswith(f"/{candidate_path.strip('/')}"):
        return False
    for binding_root in binding_roots:
        if _path_is_at_or_below(generated_path, binding_root):
            return True
    return False


def _function_call_key(call: str, args: dict[str, Any]) -> tuple[str, str]:
    serialized_args = json.dumps(
        args,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return call, serialized_args


def _read_compact_rows(
    genui_text: str,
    repair_codes: set[str] | None = None,
) -> list[list[Any]]:
    parsed_rows: list[list[Any]] = []
    parse_errors: list[str] = []
    rebuild_nested_layout = False
    for line_number, raw_line in enumerate(genui_text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            _record_preflight_repair(repair_codes, "MARKDOWN_FENCE_REMOVED")
            if parsed_rows:
                break
            continue
        strict_json_array = _is_strict_json_array(line)
        row, error = _parse_compact_line(line)
        if row is None:
            sequence_rows = _parse_concatenated_compact_rows(line)
            if sequence_rows:
                _record_preflight_repair(
                    repair_codes,
                    "CONCATENATED_ROWS_SPLIT",
                )
                parsed_rows.extend(sequence_rows)
                continue
            stream_rows = _extract_compact_component_stream(
                line,
                require_root=not parsed_rows,
            )
            if stream_rows:
                _record_preflight_repair(
                    repair_codes,
                    "COMPONENT_STREAM_RECOVERED",
                )
                parsed_rows.extend(stream_rows)
                if stream_rows[0][0] == "root":
                    rebuild_nested_layout = True
                continue
            parse_errors.append(f"Compact DSL line {line_number} is invalid JSON: {error}.")
            continue
        if not strict_json_array:
            _record_preflight_repair(repair_codes, "JSON_SYNTAX_REPAIRED")
        if _contains_nested_component_rows(row):
            _record_preflight_repair(repair_codes, "NESTED_ROWS_FLATTENED")
            rebuild_nested_layout = True
        parsed_rows.extend(_flatten_compact_value(row))

    if _root_children_are_missing(parsed_rows):
        _record_preflight_repair(repair_codes, "ROOT_CHILDREN_REBUILT")
        rebuild_nested_layout = True
    rows = _normalize_compact_rows(parsed_rows, rebuild_nested_layout)
    has_root = any(_is_component_row(row) and row[0] == "root" for row in rows)
    if not has_root:
        if parse_errors:
            raise ValueError(parse_errors[0])
        raise ValueError("Compact DSL output does not contain a valid root component.")
    tree_error = _compact_tree_error(rows)
    if tree_error is not None:
        raise ValueError(
            "Compact DSL output does not contain a complete renderable tree: "
            f"{tree_error}."
        )
    return rows


def _record_preflight_repair(
    repair_codes: set[str] | None,
    code: str,
) -> None:
    if repair_codes is not None:
        repair_codes.add(code)


def _is_strict_json_array(value: str) -> bool:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, list)


def _root_children_are_missing(rows: list[list[Any]]) -> bool:
    for row in rows:
        if not _is_component_row(row) or row[0] != "root":
            continue
        if row[1] not in CONTAINER_COMPONENTS:
            return False
        if len(row) != 4 or not isinstance(row[3], list):
            return True
        return not row[3]
    return False


def _parse_compact_line(line: str) -> tuple[list[Any] | None, str]:
    candidate = line.rstrip().removesuffix(",").rstrip()
    repaired = _repair_compact_line(candidate)
    candidates = [candidate]
    if repaired != candidate:
        candidates.append(repaired)

    last_error = "line must be a JSON array"
    for item in candidates:
        try:
            value = json.loads(item)
        except json.JSONDecodeError as exc:
            last_error = str(exc)
            continue
        if isinstance(value, list):
            return value, ""
        last_error = "line must be a JSON array"
    return None, last_error


def _parse_concatenated_compact_rows(line: str) -> list[list[Any]]:
    candidate = line.rstrip().removesuffix(",").rstrip()
    repaired = _repair_compact_line(candidate)
    candidates = [candidate]
    if repaired != candidate:
        candidates.append(repaired)

    for item in candidates:
        values = _decode_concatenated_arrays(item)
        if len(values) <= 1:
            continue
        first_value = values[0]
        if not _is_component_row(first_value) or first_value[0] != "root":
            continue
        if any(not _is_top_level_compact_value(value) for value in values[1:]):
            continue

        rows = _flatten_compact_value(first_value)
        if not rows or len(rows[0]) != 4:
            continue
        root_children = rows[0][3]
        referenced_ids = _referenced_component_ids(rows)
        valid_sequence = True
        for value in values[1:]:
            if _is_component_row(value):
                component_id = value[0]
                if component_id == "root":
                    valid_sequence = False
                    break
                if component_id not in referenced_ids:
                    root_children.append(component_id)
            flattened_rows = _flatten_compact_value(value)
            rows.extend(flattened_rows)
            referenced_ids.update(_referenced_component_ids(flattened_rows))
        if valid_sequence:
            return rows
    return []


def _decode_concatenated_arrays(value: str) -> list[list[Any]]:
    decoder = json.JSONDecoder()
    arrays: list[list[Any]] = []
    index = 0
    while index < len(value):
        while index < len(value) and (value[index].isspace() or value[index] == ","):
            index += 1
        if index >= len(value):
            break
        try:
            decoded, index = decoder.raw_decode(value, index)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, list):
            return []
        arrays.append(decoded)
    return arrays


def _is_top_level_compact_value(value: list[Any]) -> bool:
    if _is_component_row(value) or _is_compact_data_row(value):
        return True
    return _legacy_compact_data_row(value) is not None


def _referenced_component_ids(rows: list[list[Any]]) -> set[str]:
    referenced_ids: set[str] = set()
    for row in rows:
        if not _is_component_row(row) or len(row) != 4:
            continue
        referenced_ids.update(
            child_id
            for child_id in row[3]
            if isinstance(child_id, str) and child_id
        )
    return referenced_ids


def _extract_compact_component_stream(
    line: str,
    require_root: bool = True,
) -> list[list[Any]]:
    decoder = json.JSONDecoder()
    rows: list[list[Any]] = []
    component_ids: set[str] = set()
    matches = list(_COMPONENT_STREAM_PATTERN.finditer(line))
    for index, match in enumerate(matches):
        component_id = match.group("id")
        if component_id == "root" and rows:
            break
        decoded_props = _decode_component_stream_props(line, match.end(), decoder)
        if decoded_props is None:
            continue
        props, props_end = decoded_props
        if not isinstance(props, dict) or component_id in component_ids:
            continue
        component_ids.add(component_id)
        component_type = match.group("type")
        row = [component_id, component_type, props]
        if component_type in CONTAINER_COMPONENTS:
            component_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            children = _extract_component_stream_children(
                line[props_end:component_end],
                decoder,
            )
            row.append(children)
        rows.append(row)

    if not rows:
        return []
    if require_root:
        if rows[0][0] != "root":
            return []
        rows.extend(_extract_legacy_data_stream(line, decoder))
        return rows
    if len(rows) == 1 and rows[0][1] in CONTAINER_COMPONENTS and not rows[0][3]:
        return []
    return rows


def _decode_component_stream_props(
    line: str,
    start: int,
    decoder: json.JSONDecoder,
) -> tuple[dict[str, Any], int] | None:
    try:
        value, end = decoder.raw_decode(line, start)
    except json.JSONDecodeError:
        value = None
        end = start
    if isinstance(value, dict):
        return value, end

    repaired: list[str] = []
    stack: list[str] = []
    in_string = False
    escaped = False
    expected_opening = {"}": "{", "]": "["}
    for index in range(start, len(line)):
        char = line[index]
        repaired.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char in "{[":
            stack.append(char)
            continue
        if char not in expected_opening:
            continue
        expected = expected_opening[char]
        if stack and stack[-1] == expected:
            stack.pop()
        elif char == "]" and stack == ["{"]:
            repaired[-1] = "}"
            stack.pop()
        else:
            return None
        if stack:
            continue
        try:
            props = json.loads("".join(repaired))
        except json.JSONDecodeError:
            return None
        return (props, index + 1) if isinstance(props, dict) else None
    return None


def _extract_component_stream_children(
    segment: str,
    decoder: json.JSONDecoder,
) -> list[str]:
    candidate = segment.lstrip(" \t\r\n],")
    if not candidate:
        return []
    if candidate.startswith("["):
        try:
            value, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            value = None
        if _is_component_id_list(value):
            return value

    children: list[str] = []
    index = 0
    while index < len(candidate):
        while index < len(candidate) and candidate[index] in " \t\r\n,[]":
            index += 1
        if index >= len(candidate):
            break
        try:
            value, index = decoder.raw_decode(candidate, index)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, str) or not value:
            return []
        children.append(value)
    return children


def _is_component_id_list(value: Any) -> TypeGuard[list[str]]:
    if not isinstance(value, list):
        return False
    return all(isinstance(item, str) and item for item in value)


def _extract_legacy_data_stream(
    line: str,
    decoder: json.JSONDecoder,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for match in _LEGACY_DATA_STREAM_PATTERN.finditer(line):
        try:
            value, _ = decoder.raw_decode(line, match.end())
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        path = match.group("path")
        normalized_path = path if path.startswith("/") else f"/{path}"
        rows.append([normalized_path, value])
    return rows


def _repair_compact_line(line: str) -> str:
    repaired = re.sub(r',\s*"$', "", line)
    children_pattern = r',\s*"children"\s*:'
    repaired = re.sub(children_pattern, ",", repaired)
    repaired = re.sub(r',\s*"value"\s*:', ",", repaired)
    nested_types = f"{_COMPONENT_TYPE_PATTERN}|object"
    nested_quote_pattern = rf',\s*"\[(?="[^"]+","(?:{nested_types})"\s*,)'
    repaired = re.sub(nested_quote_pattern, ",[", repaired)
    return _remove_unmatched_closers(repaired)


def _remove_unmatched_closers(value: str) -> str:
    opening_chars = {"{", "["}
    expected_opening = {"}": "{", "]": "["}
    stack: list[str] = []
    output: list[str] = []
    in_string = False
    escaped = False
    for char in value:
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            output.append(char)
        elif char in opening_chars:
            stack.append(char)
            output.append(char)
        elif char in expected_opening:
            if stack and stack[-1] == expected_opening[char]:
                stack.pop()
                output.append(char)
        else:
            output.append(char)
    if not in_string:
        closing_chars = {"{": "}", "[": "]"}
        output.extend(closing_chars.get(char, "") for char in reversed(stack))
    return "".join(output)


def _flatten_compact_value(value: list[Any]) -> list[list[Any]]:
    if _is_compact_data_row(value):
        return [value]
    legacy_data_row = _legacy_compact_data_row(value)
    if legacy_data_row is not None:
        return [legacy_data_row]
    if _is_component_row(value):
        return _flatten_component_row(value)

    rows: list[list[Any]] = []
    for item in value:
        if isinstance(item, list):
            rows.extend(_flatten_compact_value(item))
    return rows


def _contains_nested_component_rows(value: list[Any]) -> bool:
    if not _is_component_row(value):
        return False
    for item in value[3:]:
        if not isinstance(item, list):
            continue
        if _is_component_row(item):
            return True
        if _contains_nested_component_rows_in_list(item):
            return True
    return False


def _contains_nested_component_rows_in_list(value: list[Any]) -> bool:
    for item in value:
        if not isinstance(item, list):
            continue
        if _is_component_row(item):
            return True
        if _contains_nested_component_rows_in_list(item):
            return True
    return False


def _is_component_row(value: list[Any]) -> bool:
    if len(value) < 3:
        return False
    component_id, component_type, props = value[:3]
    if not isinstance(component_id, str) or component_id.startswith("/"):
        return False
    if not isinstance(component_type, str):
        return False
    return isinstance(props, dict)


def _flatten_component_row(value: list[Any]) -> list[list[Any]]:
    component_id, component_type, props = value[:3]
    child_ids: list[str] = []
    nested_children: list[list[Any]] = []
    nested_data_rows: list[list[Any]] = []
    for item in value[3:]:
        _collect_compact_children(
            item,
            child_ids,
            nested_children,
            nested_data_rows,
        )

    row = [component_id, component_type, props]
    if component_type in CONTAINER_COMPONENTS:
        row.append(child_ids)

    rows = [row]
    for child in nested_children:
        rows.extend(_flatten_component_row(child))
    rows.extend(nested_data_rows)
    return rows


def _collect_compact_children(
    value: Any,
    child_ids: list[str],
    nested_children: list[list[Any]],
    nested_data_rows: list[list[Any]],
) -> None:
    if isinstance(value, list):
        legacy_data_row = _legacy_compact_data_row(value)
        if legacy_data_row is not None:
            nested_data_rows.append(legacy_data_row)
            return
    if isinstance(value, list) and _is_component_row(value):
        child_ids.append(value[0])
        nested_children.append(value)
        return
    if not isinstance(value, list):
        return
    if all(isinstance(item, str) and item for item in value):
        child_ids.extend(value)
        return
    for item in value:
        _collect_compact_children(
            item,
            child_ids,
            nested_children,
            nested_data_rows,
        )


def _legacy_compact_data_row(value: list[Any]) -> list[Any] | None:
    if len(value) != 3 or value[1] != "object" or not isinstance(value[2], dict):
        return None
    source_path = value[0]
    if not isinstance(source_path, str):
        return None
    if source_path.startswith("data/"):
        return [f"/{source_path}", value[2]]
    if source_path.startswith("/data/"):
        return [source_path, value[2]]
    return None


def _normalize_compact_rows(
    rows: list[list[Any]],
    rebuild_nested_layout: bool = False,
) -> list[list[Any]]:
    normalized_rows: list[list[Any]] = []
    for row in rows:
        if _is_compact_data_row(row):
            normalized_rows.append(_normalize_compact_data_row(row))
            continue
        if not _is_component_row(row):
            continue
        normalized_rows.append(_normalize_compact_component_row(row))
    if rebuild_nested_layout:
        normalized_rows = _rebuild_nested_compact_layout(normalized_rows)
    _repair_decorative_text_content(normalized_rows)
    _repair_dense_sleep_layout(normalized_rows)
    ordered_rows = _order_reachable_compact_rows(normalized_rows)
    _repair_main_axis_padding_overflow(ordered_rows)
    return ordered_rows


def _repair_decorative_text_content(rows: list[list[Any]]) -> None:
    for row in rows:
        if not _is_component_row(row) or row[1] != "Text":
            continue
        props = row[2]
        if "content" in props or "backgroundColor" not in props:
            continue
        width = _numeric_value(props.get("width"))
        height = _numeric_value(props.get("height"))
        if width is None or height is None:
            continue
        props["content"] = ""


def _repair_dense_sleep_layout(rows: list[list[Any]]) -> None:
    components = {
        row[0]: row
        for row in rows
        if _is_component_row(row)
    }
    required_ids = {
        "root",
        "header_row",
        "title_group",
        "mode_badge",
        "sleep_icon",
        "title_text",
        "mode_dot",
        "mode_text",
        "main_row",
        "meter_stack",
        "sleep_ring",
        "meter_icon",
        "primary_info",
        "primary_value",
        "status_row",
        "status_dot",
        "status_text",
        "action_row",
        "sleep_action",
        "alarm_action",
    }
    if not required_ids.issubset(components):
        return
    if components["root"][1] != "Column":
        return

    children_by_id = {
        "root": ["header_row", "main_row", "action_row"],
        "header_row": ["title_group", "mode_badge"],
        "title_group": ["sleep_icon", "title_text"],
        "mode_badge": ["mode_dot", "mode_text"],
        "main_row": ["meter_stack", "primary_info"],
        "meter_stack": ["sleep_ring", "meter_icon"],
        "primary_info": ["primary_value", "status_row"],
        "status_row": ["status_dot", "status_text"],
        "action_row": ["sleep_action", "alarm_action"],
    }
    for component_id, child_ids in children_by_id.items():
        row = components[component_id]
        if row[1] not in CONTAINER_COMPONENTS:
            return
        row[3] = child_ids

    components["root"][2]["space"] = 4
    components["header_row"][2]["height"] = 20
    components["main_row"][2]["height"] = 56
    components["meter_stack"][2]["width"] = 56
    components["meter_stack"][2]["height"] = 56
    components["sleep_ring"][2]["width"] = 56
    components["sleep_ring"][2]["height"] = 56
    components["primary_info"][2]["height"] = 56
    components["action_row"][2]["height"] = 32


def _repair_main_axis_padding_overflow(rows: list[list[Any]]) -> None:
    components = {
        row[0]: row
        for row in rows
        if _is_component_row(row)
    }
    for parent in components.values():
        axis = _layout_main_axis(parent[1])
        if axis is None or len(parent) != 4 or not parent[3]:
            continue
        raw_capacity = parent[2].get(axis)
        padded_capacity = _layout_capacity(parent[2], axis)
        if not _is_number(raw_capacity) or padded_capacity is None:
            continue

        child_sizes: list[float] = []
        for child_id in parent[3]:
            child = components.get(child_id)
            child_size = child[2].get(axis) if child is not None else None
            if not _is_number(child_size):
                child_sizes = []
                break
            child_sizes.append(float(child_size))
        if not child_sizes:
            continue

        spacing = parent[2].get("space", 0)
        if not _is_number(spacing):
            spacing = 0
        required_size = sum(child_sizes)
        required_size += float(spacing) * max(0, len(child_sizes) - 1)
        if required_size <= padded_capacity + _LAYOUT_PIXEL_TOLERANCE:
            continue
        if _repair_main_axis_spacing(
            parent,
            child_sizes,
            float(spacing),
            padded_capacity,
        ):
            continue
        repaired_padding = _padding_without_main_axis(parent[2].get("padding"), axis)
        if repaired_padding is None:
            continue
        if required_size > float(raw_capacity) + _LAYOUT_PIXEL_TOLERANCE:
            repaired_spacing = _repair_main_axis_spacing(
                parent,
                child_sizes,
                float(spacing),
                float(raw_capacity),
            )
            if not repaired_spacing:
                continue
        parent[2]["padding"] = repaired_padding


def _repair_main_axis_spacing(
    parent: list[Any],
    child_sizes: list[float],
    current_spacing: float,
    capacity: float,
) -> bool:
    gap_count = max(0, len(child_sizes) - 1)
    if gap_count == 0 or current_spacing <= 0:
        return False
    child_extent = sum(child_sizes)
    for candidate in sorted(FORM_SPACING, reverse=True):
        if candidate >= current_spacing:
            continue
        required_size = child_extent + candidate * gap_count
        if required_size > capacity + _LAYOUT_PIXEL_TOLERANCE:
            continue
        parent[2]["space"] = candidate
        return True
    return False


def _padding_without_main_axis(value: Any, axis: str) -> dict[str, Any] | None:
    if _is_number(value) and value >= 0:
        if axis == "width":
            return {"left": 0, "right": 0, "top": value, "bottom": value}
        return {"left": value, "right": value, "top": 0, "bottom": 0}
    if not isinstance(value, dict):
        return None
    repaired = dict(value)
    side_names = ("left", "right") if axis == "width" else ("top", "bottom")
    for side_name in side_names:
        repaired[side_name] = 0
    return repaired


def _rebuild_nested_compact_layout(rows: list[list[Any]]) -> list[list[Any]]:
    components = [row for row in rows if _is_component_row(row)]
    data_rows = [row for row in rows if _is_compact_data_row(row)]
    if not components or components[0][0] != "root":
        return rows

    rebuilt_components: list[list[Any]] = []
    stack: list[_LayoutContainerState] = []
    for index, source_row in enumerate(components):
        row = [source_row[0], source_row[1], source_row[2]]
        if source_row[1] in CONTAINER_COMPONENTS:
            row.append([])
        if index == 0:
            rebuilt_components.append(row)
            stack.append(_LayoutContainerState(row=row, is_root=True))
            continue

        while stack and not _layout_container_accepts(stack[-1], row):
            stack.pop()
        if not stack:
            return [rebuilt_components[0], *data_rows]

        parent_state = stack[-1]
        parent_state.row[3].append(row[0])
        _consume_layout_space(parent_state, row)
        rebuilt_components.append(row)
        if row[1] in CONTAINER_COMPONENTS:
            stack.append(_LayoutContainerState(row=row))

    rebuilt_rows = [*rebuilt_components, *data_rows]
    return rebuilt_rows


def _layout_container_accepts(
    state: _LayoutContainerState,
    child: list[Any],
) -> bool:
    if state.is_root:
        return True
    if state.row[1] == "Stack":
        return _stack_container_accepts(state.row, child)
    axis = _layout_main_axis(state.row[1])
    if axis is None:
        return False
    capacity = _layout_capacity(state.row[2], axis)
    child_size = child[2].get(axis)
    if capacity is None or not _is_number(child_size):
        return False
    spacing = state.row[2].get("space", 0)
    if not _is_number(spacing):
        spacing = 0
    required_space = child_size
    if state.child_count:
        required_space += spacing
    return state.used_space + required_space <= capacity + _LAYOUT_PIXEL_TOLERANCE


def _stack_container_accepts(parent: list[Any], child: list[Any]) -> bool:
    for axis in ("width", "height"):
        capacity = _layout_capacity(parent[2], axis)
        child_size = _numeric_value(child[2].get(axis))
        if capacity is None or child_size is None:
            return False
        if child_size > capacity + _LAYOUT_PIXEL_TOLERANCE:
            return False
    return True


def _consume_layout_space(
    state: _LayoutContainerState,
    child: list[Any],
) -> None:
    if state.is_root:
        state.child_count += 1
        return
    axis = _layout_main_axis(state.row[1])
    child_size = child[2].get(axis, 0) if axis is not None else 0
    spacing = state.row[2].get("space", 0)
    if not _is_number(spacing):
        spacing = 0
    if state.child_count:
        state.used_space += spacing
    if _is_number(child_size):
        state.used_space += child_size
    state.child_count += 1


def _layout_main_axis(component_type: str) -> str | None:
    if component_type == "Row":
        return "width"
    if component_type in {"Column", "List"}:
        return "height"
    return None


def _layout_capacity(props: dict[str, Any], axis: str) -> float | None:
    capacity = _numeric_value(props.get(axis))
    if capacity is None:
        return None
    padding_extent = _padding_extent(props.get("padding"), axis)
    if padding_extent is None:
        return None
    return max(0.0, capacity - padding_extent)


def _padding_extent(value: Any, axis: str) -> float | None:
    if value is None:
        return 0.0
    numeric_value = _numeric_value(value)
    if numeric_value is not None:
        return numeric_value * 2 if numeric_value >= 0 else None
    if not isinstance(value, dict):
        return None
    side_names = ("left", "right") if axis == "width" else ("top", "bottom")
    extent = 0.0
    for side_name in side_names:
        side_value = _numeric_value(value.get(side_name, 0))
        if side_value is None or side_value < 0:
            return None
        extent += side_value
    return extent


def _normalize_compact_data_row(row: list[Any]) -> list[Any]:
    if len(row) != 2 or not isinstance(row[1], dict):
        return row
    if set(row[1]) == {"value"}:
        return [row[0], row[1]["value"]]
    return row


def _normalize_compact_component_row(row: list[Any]) -> list[Any]:
    component_id, component_type, source_props = row[:3]
    props = dict(source_props)
    _flatten_style_wrappers(props)
    source_children = row[3] if len(row) == 4 and isinstance(row[3], list) else []
    prop_children = props.pop("children", None)
    if not source_children and isinstance(prop_children, list):
        source_children = prop_children

    if component_id == "root":
        props["width"] = "matchParent"
    if component_type in {"Row", "Column"} and "space" not in props:
        item_margin = props.pop("itemMargin", None)
        if item_margin is not None:
            props["space"] = item_margin
    if component_type in {"Row", "Column", "List"}:
        props.setdefault("space", 0)
    if "font" in props:
        props.setdefault("fontSize", props["font"])
        props.pop("font")
    _normalize_numeric_props(props)
    if component_type == "Text" and "color" in props and "fontColor" not in props:
        props["fontColor"] = props.pop("color")
    _normalize_direct_path_prop(component_type, props)
    if component_type == "Button":
        props.setdefault("enabled", True)
        _normalize_button_action(props)

    normalized = [component_id, component_type, props]
    if component_type in CONTAINER_COMPONENTS:
        normalized.append(source_children)
    return normalized


def _flatten_style_wrappers(props: dict[str, Any]) -> None:
    for wrapper_name in ("styles", "style"):
        wrapped_props = props.get(wrapper_name)
        if not isinstance(wrapped_props, dict):
            continue
        props.pop(wrapper_name)
        for prop_name, prop_value in wrapped_props.items():
            props.setdefault(prop_name, prop_value)


def _repair_form_contract_props(
    rows: list[list[Any]],
    cardspec: dict[str, Any] | str | None,
) -> None:
    cardspec_value = _object_as_dict(cardspec)
    size = cardspec_value.get("suggestSize") if cardspec_value is not None else None
    root_radius = {"2x2": 18, "2x4": 22}.get(size)
    root_width = {"2x2": 140, "2x4": 300}.get(size)

    for row in rows:
        if not _is_component_row(row):
            continue
        component_id, component_type, props = row[:3]
        if component_id == "root" and root_radius is not None:
            props["height"] = 140
            props["borderRadius"] = root_radius
            props["clip"] = True
            props["constraintSize"] = {
                "minWidth": root_width,
                "maxWidth": root_width,
                "minHeight": 140,
                "maxHeight": 140,
            }
        if component_type == "Image":
            props.setdefault("objectFit", "contain")
        if component_type == "Text":
            _repair_protected_text_overflow(props)
        _repair_form_font_size(props)
    _repair_form_text_fit(rows)
    _repair_surface_background(rows)
    _repair_bottom_anchor_spacing(rows)


def _repair_bottom_anchor_spacing(rows: list[list[Any]]) -> None:
    components = {
        row[0]: row
        for row in rows
        if _is_component_row(row)
    }
    root = components.get("root")
    if root is None:
        return
    if root[1] != "Column" or len(root) != 4:
        return
    if len(root[3]) < 2:
        return

    height = _numeric_value(root[2].get("height"))
    if height is None:
        return
    child_heights: list[float] = []
    for child_id in root[3]:
        child = components.get(child_id)
        child_height = _numeric_value(child[2].get("height")) if child else None
        if child_height is None:
            return
        child_heights.append(child_height)

    padding_top, _, _, _ = _padding_values(root[2].get("padding"))
    current_spacing = _numeric_value(root[2].get("space")) or 0.0
    gap_count = len(child_heights) - 1
    child_extent = sum(child_heights)
    bottom_gap = height - padding_top - child_extent - current_spacing * gap_count
    if bottom_gap <= 16 or bottom_gap > 20:
        return

    for candidate in sorted(FORM_SPACING):
        if candidate <= current_spacing:
            continue
        candidate_gap = height - padding_top - child_extent - candidate * gap_count
        if candidate_gap > 16:
            continue
        if candidate_gap < 8:
            return
        root[2]["space"] = candidate
        return


def _repair_form_font_size(props: dict[str, Any]) -> None:
    font_size = _numeric_value(props.get("fontSize"))
    if font_size is None or font_size in FORM_FONT_SIZES:
        return
    props["fontSize"] = min(
        FORM_FONT_SIZES,
        key=lambda candidate: (abs(candidate - font_size), candidate),
    )


def _repair_protected_text_overflow(props: dict[str, Any]) -> None:
    if props.get("textOverflow") in {"ellipsis", "clip", "marquee"}:
        props["textOverflow"] = "none"


def _repair_form_text_fit(rows: list[list[Any]]) -> None:
    data_values: dict[str, Any] = {}
    components: dict[str, list[Any]] = {}
    parents: dict[str, list[Any]] = {}
    for row in rows:
        if _is_compact_data_row(row) and len(row) == 2:
            data_values[row[0]] = row[1]
        elif _is_component_row(row):
            components[row[0]] = row
    for row in components.values():
        if len(row) != 4:
            continue
        for child_id in row[3]:
            parents[child_id] = row

    removed_component_ids: set[str] = set()
    for row in rows:
        if not _is_component_row(row) or row[1] not in {"Text", "Button"}:
            continue
        if row[0] in removed_component_ids:
            continue
        component_type = row[1]
        props = row[2]
        prop_name = "content" if component_type == "Text" else "label"
        text = _preview_text(props.get(prop_name), data_values)
        width = _numeric_value(props.get("width"))
        font_size = _numeric_value(props.get("fontSize")) or 14.0
        if text is None or width is None:
            continue

        capacity = width
        if component_type == "Button":
            capacity -= _button_horizontal_safety_space(text)
        if component_type == "Text":
            max_lines = int(_numeric_value(props.get("maxLines")) or 1)
            capacity *= max_lines
        estimated_width = _estimate_text_width(text, font_size)
        if estimated_width <= capacity:
            continue
        fitting_font_size = _fitting_smaller_form_font_size(
            text,
            font_size,
            capacity,
        )
        if fitting_font_size is not None:
            props["fontSize"] = int(fitting_font_size)
            continue
        if component_type != "Text":
            continue
        if _redistribute_text_row_width(
            row,
            text,
            font_size,
            components,
            parents,
            data_values,
        ):
            continue
        smaller_font_size = _next_smaller_form_font_size(font_size)
        _reclaim_decorative_image_space(
            row,
            text,
            font_size,
            smaller_font_size,
            components,
            parents,
            removed_component_ids,
        )

    if removed_component_ids:
        remaining_rows: list[list[Any]] = []
        for row in rows:
            if _is_component_row(row) and row[0] in removed_component_ids:
                continue
            remaining_rows.append(row)
        rows[:] = remaining_rows


def _next_smaller_form_font_size(font_size: float) -> float | None:
    for candidate in sorted(FORM_FONT_SIZES, reverse=True):
        if candidate >= font_size:
            continue
        if candidate / font_size < 0.75:
            return None
        return float(candidate)
    return None


def _fitting_smaller_form_font_size(
    text: str,
    font_size: float,
    capacity: float,
) -> float | None:
    for candidate in sorted(FORM_FONT_SIZES, reverse=True):
        if candidate >= font_size:
            continue
        if candidate / font_size < 0.75:
            return None
        if _estimate_text_width(text, candidate) <= capacity:
            return float(candidate)
    return None


def _redistribute_text_row_width(
    text_row: list[Any],
    text: str,
    font_size: float,
    components: dict[str, list[Any]],
    parents: dict[str, list[Any]],
    data_values: dict[str, Any],
) -> bool:
    parent = parents.get(text_row[0])
    if parent is None or parent[1] != "Row" or len(parent) != 4:
        return False
    if len(parent[3]) < 2:
        return False
    if int(_numeric_value(text_row[2].get("maxLines")) or 1) != 1:
        return False

    parent_capacity = _layout_capacity(parent[2], "width")
    current_width = _numeric_value(text_row[2].get("width"))
    spacing = _numeric_value(parent[2].get("space")) or 0.0
    if parent_capacity is None or current_width is None:
        return False

    current_extent = spacing * (len(parent[3]) - 1)
    donors: list[tuple[list[Any], float, float]] = []
    for child_id in parent[3]:
        child = components.get(child_id)
        if child is None:
            return False
        child_width = _numeric_value(child[2].get("width"))
        if child_width is None:
            return False
        current_extent += child_width
        if child_id == text_row[0]:
            continue
        donor = _text_width_donor(child, child_width, data_values)
        if donor is not None:
            donors.append(donor)

    if current_extent > parent_capacity + _LAYOUT_PIXEL_TOLERANCE:
        return False
    unused_width = max(0.0, parent_capacity - current_extent)

    selected_font_size: float | None = None
    selected_width = 0.0
    available_width = unused_width + sum(donor[2] for donor in donors)
    for candidate_font_size in _form_font_size_candidates(font_size):
        required_width = float(math.ceil(_estimate_text_width(text, candidate_font_size)))
        width_delta = max(0.0, required_width - current_width)
        if width_delta > available_width + _LAYOUT_PIXEL_TOLERANCE:
            continue
        selected_font_size = candidate_font_size
        selected_width = required_width
        break
    if selected_font_size is None:
        return False

    text_row[2]["width"] = int(selected_width)
    text_row[2]["fontSize"] = int(selected_font_size)
    remaining_reduction = max(0.0, selected_width - current_width - unused_width)
    for sibling, sibling_width, sibling_slack in sorted(
        donors,
        key=lambda donor: donor[2],
        reverse=True,
    ):
        if remaining_reduction <= 0:
            break
        reduction = min(sibling_slack, remaining_reduction)
        repaired_width = sibling_width - reduction
        sibling[2]["width"] = int(repaired_width) if repaired_width.is_integer() else repaired_width
        remaining_reduction -= reduction
    return True


def _text_width_donor(
    component: list[Any],
    width: float,
    data_values: dict[str, Any],
) -> tuple[list[Any], float, float] | None:
    if component[1] != "Text":
        return None
    props = component[2]
    if int(_numeric_value(props.get("maxLines")) or 1) != 1:
        return None
    text = _preview_text(props.get("content"), data_values)
    if text is None:
        return None
    font_size = _numeric_value(props.get("fontSize")) or 14.0
    minimum_width = float(math.ceil(_estimate_text_width(text, font_size)))
    return component, width, max(0.0, width - minimum_width)


def _form_font_size_candidates(font_size: float) -> tuple[float, ...]:
    candidates = [font_size]
    for candidate in sorted(FORM_FONT_SIZES, reverse=True):
        if candidate >= font_size:
            continue
        if candidate / font_size < 0.75:
            continue
        candidates.append(float(candidate))
    return tuple(candidates)


def _reclaim_decorative_image_space(
    text_row: list[Any],
    text: str,
    font_size: float,
    smaller_font_size: float | None,
    components: dict[str, list[Any]],
    parents: dict[str, list[Any]],
    removed_component_ids: set[str],
) -> None:
    parent = parents.get(text_row[0])
    if parent is None:
        return
    if parent[1] != "Row" or len(parent) != 4:
        return
    sibling_ids = [child_id for child_id in parent[3] if child_id != text_row[0]]
    if len(sibling_ids) != 1:
        return
    sibling = components.get(sibling_ids[0])
    if sibling is None or sibling[1] != "Image":
        return
    capacity = _layout_capacity(parent[2], "width")
    if capacity is None:
        return

    selected_font_size = font_size
    if _estimate_text_width(text, selected_font_size) > capacity:
        if smaller_font_size is None:
            return
        selected_font_size = smaller_font_size
    if _estimate_text_width(text, selected_font_size) > capacity:
        return

    text_row[2]["width"] = int(capacity) if capacity.is_integer() else capacity
    text_row[2]["fontSize"] = int(selected_font_size)
    parent[3] = [text_row[0]]
    removed_component_ids.add(sibling[0])


def _preview_text(source: Any, data_values: dict[str, Any]) -> str | None:
    if isinstance(source, str):
        return source
    if not _is_path_binding(source):
        return None
    value = data_values.get(source["path"], _MISSING)
    if value is _MISSING or value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return None


def _repair_surface_background(rows: list[list[Any]]) -> None:
    root = next(
        (row for row in rows if _is_component_row(row) and row[0] == "root"),
        None,
    )
    if root is None:
        return
    props = root[2]
    preferred_gradient = _preferred_surface_gradient(rows)
    if preferred_gradient is not None and not _has_rich_surface_background(props):
        props.pop("backgroundColor", None)
        _set_surface_gradient(props, preferred_gradient)
        return
    if _has_surface_background(props):
        return

    components = [
        (row[1], row[2])
        for row in rows
        if _is_component_row(row)
    ]
    fallback = _DARK_SURFACE_FALLBACK
    if not _uses_only_light_foreground(components):
        fallback = _LIGHT_SURFACE_FALLBACK
    _set_surface_gradient(props, fallback)


def _preferred_surface_gradient(rows: list[list[Any]]) -> dict[str, Any] | None:
    if _card_contains_keywords(rows, _LOW_POWER_KEYWORDS):
        return _LOW_POWER_SURFACE_GRADIENT
    if _card_contains_keywords(rows, _SLEEP_KEYWORDS):
        return _SLEEP_SURFACE_GRADIENT
    return None


def _card_contains_keywords(
    rows: list[list[Any]],
    keywords: tuple[str, ...],
) -> bool:
    for row in rows:
        if not _is_component_row(row):
            continue
        source: Any = None
        if row[1] == "Text":
            source = row[2].get("content")
        elif row[1] == "Button":
            source = row[2].get("label")
        if not isinstance(source, str):
            continue
        normalized = source.lower()
        for keyword in keywords:
            if keyword in normalized:
                return True
    return False


def _has_rich_surface_background(props: dict[str, Any]) -> bool:
    for prop_name in ("linearGradient", "backgroundImage"):
        if props.get(prop_name) not in (None, "", {}):
            return True
    return False


def _set_surface_gradient(
    props: dict[str, Any],
    gradient: dict[str, Any],
) -> None:
    props["linearGradient"] = {
        "direction": gradient["direction"],
        "colors": [list(stop) for stop in gradient["colors"]],
    }


def _has_surface_background(props: dict[str, Any]) -> bool:
    for prop_name in _SURFACE_BACKGROUND_PROPS:
        value = props.get(prop_name)
        if value not in (None, "", {}):
            return True
    return False


def _uses_only_light_foreground(
    components: list[tuple[str, dict[str, Any]]],
) -> bool:
    has_foreground = False
    for component_type, props in components:
        if component_type not in {"Text", "Button"}:
            continue
        color = props.get("fontColor")
        if not isinstance(color, str) or not _is_light_color(color):
            return False
        has_foreground = True
    return has_foreground


def _is_light_color(value: str) -> bool:
    if _HEX_COLOR_PATTERN.fullmatch(value) is None:
        return False
    rgb = value[-6:]
    red = int(rgb[0:2], 16)
    green = int(rgb[2:4], 16)
    blue = int(rgb[4:6], 16)
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return luminance >= 0.75


def _normalize_numeric_props(props: dict[str, Any]) -> None:
    for prop_name in _NORMALIZABLE_NUMBER_PROPS:
        value = props.get(prop_name)
        if isinstance(value, str):
            normalized_value = _number_from_numeric_string(value)
            if normalized_value is not None:
                props[prop_name] = normalized_value
    padding = props.get("padding")
    sequence_padding = _normalize_padding_sequence(padding)
    if sequence_padding is not None:
        props["padding"] = sequence_padding
        return
    if not isinstance(padding, dict):
        return
    normalized_padding = dict(padding)
    for key, value in padding.items():
        if not isinstance(value, str):
            continue
        normalized_value = _number_from_numeric_string(value)
        if normalized_value is not None:
            normalized_padding[key] = normalized_value
    props["padding"] = normalized_padding


def _normalize_padding_sequence(value: Any) -> dict[str, int | float] | None:
    if not isinstance(value, list):
        return None
    if len(value) != 4:
        return None

    normalized: dict[str, int | float] = {}
    side_names = ("top", "right", "bottom", "left")
    for side_name, side_value in zip(side_names, value, strict=True):
        if isinstance(side_value, bool):
            return None
        if isinstance(side_value, (int, float)):
            number = side_value
        elif isinstance(side_value, str):
            number = _number_from_numeric_string(side_value)
        else:
            return None
        if number is None or number < 0:
            return None
        normalized[side_name] = number
    return normalized


def _number_from_numeric_string(value: str) -> int | float | None:
    stripped_value = value.strip()
    if _NUMERIC_STRING_PATTERN.fullmatch(stripped_value) is None:
        return None
    return float(stripped_value) if "." in stripped_value else int(stripped_value)


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _DIMENSION_PATTERN.fullmatch(value.strip())
    return float(match.group(1)) if match is not None else None


def _padding_values(value: Any) -> tuple[float, float, float, float]:
    numeric_value = _numeric_value(value)
    if numeric_value is not None:
        return numeric_value, numeric_value, numeric_value, numeric_value
    if not isinstance(value, dict):
        return 0.0, 0.0, 0.0, 0.0

    values: list[float] = []
    for side in ("top", "right", "bottom", "left"):
        side_value = _numeric_value(value.get(side)) or 0.0
        values.append(side_value)
    return values[0], values[1], values[2], values[3]


def _normalize_direct_path_prop(component_type: str, props: dict[str, Any]) -> None:
    prop_names = {
        "Text": "content",
        "Image": "src",
        "Button": "label",
    }
    prop_name = prop_names.get(component_type)
    if prop_name is None:
        return
    value = props.get(prop_name)
    path = _path_from_string_source(value)
    if path is None:
        return
    props[prop_name] = {"path": path}


def _path_from_string_source(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if _is_json_pointer(value) and not any(char.isspace() for char in value):
        return value
    match = _PATH_TEMPLATE_PATTERN.fullmatch(value)
    if match is None:
        return None
    path = match.group("path")
    return path if _is_json_pointer(path) else None


def _normalize_button_action(props: dict[str, Any]) -> None:
    action = props.get("action")
    if not isinstance(action, dict):
        return
    function_call = action.get("functionCall")
    if isinstance(function_call, str):
        args = action.get("args")
        props["action"] = {
            "functionCall": {
                "call": function_call,
                "args": args if isinstance(args, dict) else {},
            }
        }
        return
    if isinstance(function_call, dict) and "args" in action and "args" not in function_call:
        updated_call = dict(function_call)
        updated_call["args"] = action["args"] if isinstance(action["args"], dict) else {}
        props["action"] = {"functionCall": updated_call}


def _order_reachable_compact_rows(rows: list[list[Any]]) -> list[list[Any]]:
    components: dict[str, list[Any]] = {}
    data_rows: list[list[Any]] = []
    for row in rows:
        if _is_compact_data_row(row):
            data_rows.append(row)
        elif _is_component_row(row) and row[0] not in components:
            components[row[0]] = row

    ordered: list[list[Any]] = []
    visited: set[str] = set()
    claimed: set[str] = {"root"}

    def visit(component_id: str, ancestors: set[str]) -> None:
        row = components.get(component_id)
        if row is None or component_id in visited:
            return
        if component_id in ancestors:
            return
        visited.add(component_id)
        child_ids: list[str] = []
        if len(row) == 4:
            for child_id in row[3]:
                if child_id not in components or child_id in claimed:
                    continue
                if child_id in ancestors:
                    continue
                claimed.add(child_id)
                child_ids.append(child_id)
        ordered_row = [row[0], row[1], row[2]]
        if row[1] in CONTAINER_COMPONENTS:
            ordered_row.append(child_ids)
        ordered.append(ordered_row)
        next_ancestors = ancestors | {component_id}
        for child_id in child_ids:
            visit(child_id, next_ancestors)

    visit("root", set())
    return [*ordered, *data_rows]


def _compact_tree_error(rows: list[list[Any]]) -> str | None:
    has_visible_component = False
    for row in rows:
        if not _is_component_row(row):
            continue
        component_type = row[1]
        if component_type in CONTAINER_COMPONENTS:
            if len(row) != 4 or not row[3]:
                return f'container "{row[0]}" has no reachable children'
            continue
        if row[0] != "root":
            has_visible_component = True
    if not has_visible_component:
        return "no visible leaf component is reachable from root"
    return None


def _serialize_compact_rows(rows: list[list[Any]]) -> str:
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in rows
    )


def _build_dynamic_binding_targets(
    cardspec: dict[str, Any] | str | None,
    data_capabilities: list[Any] | None,
) -> list[_DynamicBindingTarget]:
    cardspec_value = _object_as_dict(cardspec)
    if cardspec_value is None:
        return []

    capabilities_by_id: dict[str, dict[str, Any]] = {}
    for capability in data_capabilities or []:
        capability_value = _object_as_dict(capability)
        if capability_value is None:
            continue
        capability_id = capability_value.get("id")
        if isinstance(capability_id, str):
            capabilities_by_id[capability_id] = capability_value

    bindings = cardspec_value.get("dataBindings")
    if not isinstance(bindings, list):
        return []

    targets: list[_DynamicBindingTarget] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        capability_id = binding.get("capabilityId")
        write_result_to = binding.get("writeResultTo")
        if not isinstance(capability_id, str) or not _is_json_pointer_value(write_result_to):
            continue
        capability = capabilities_by_id.get(capability_id)
        if capability is None:
            continue
        output_schema = capability.get("outputSchema")
        if not isinstance(output_schema, dict):
            continue
        update_model = binding.get("updateModel")
        if not isinstance(update_model, dict):
            update_model = {}
        targets.extend(
            _targets_for_capability_binding(
                capability_id,
                write_result_to,
                output_schema,
                update_model,
            )
        )
    return targets


def _object_as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dumped if isinstance(dumped, dict) else None
    return None


def _targets_for_capability_binding(
    capability_id: str,
    write_result_to: str,
    output_schema: dict[str, Any],
    update_model: dict[str, Any],
) -> list[_DynamicBindingTarget]:
    targets: list[_DynamicBindingTarget] = []
    for rule in _DYNAMIC_BINDING_RULES:
        if rule.capability_id != capability_id:
            continue
        field_schema = _schema_at_path(output_schema, rule.relative_path)
        if field_schema is None:
            continue
        initial_value = _value_at_relative_path(update_model, rule.relative_path)
        if initial_value is _MISSING:
            initial_value = field_schema.get("sampleValue", _MISSING)
        if initial_value is _MISSING and rule.preview_value is not _MISSING:
            initial_value = rule.preview_value
        if initial_value is _MISSING:
            initial_value = _default_value_for_schema(field_schema)
        targets.append(
            _DynamicBindingTarget(
                rule=rule,
                binding_root=write_result_to,
                path=_join_json_pointer(write_result_to, rule.relative_path),
                schema_type=str(field_schema.get("type", "")),
                initial_value=initial_value,
            )
        )
    return targets


def _schema_at_path(
    output_schema: dict[str, Any],
    relative_path: tuple[str, ...],
) -> dict[str, Any] | None:
    current: Any = output_schema
    for segment in relative_path:
        if not isinstance(current, dict):
            return None
        schema_type = current.get("type")
        if schema_type == "array" or ("items" in current and segment.isdigit()):
            if not segment.isdigit():
                return None
            current = current.get("items")
            continue
        properties = current.get("properties")
        if not isinstance(properties, dict):
            return None
        current = properties.get(segment)
    return current if isinstance(current, dict) else None


def _value_at_relative_path(value: Any, relative_path: tuple[str, ...]) -> Any:
    current = value
    for segment in relative_path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
            continue
        if isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if index < len(current):
                current = current[index]
                continue
        return _MISSING
    return current


def _default_value_for_schema(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    default_value: Any = None
    if schema_type == "string":
        default_value = ""
    elif schema_type in {"number", "integer"}:
        default_value = 0
    elif schema_type == "boolean":
        default_value = False
    elif schema_type == "array":
        default_value = []
    elif schema_type == "object":
        default_value = {}
    return default_value


def _join_json_pointer(base_path: str, relative_path: tuple[str, ...]) -> str:
    escaped = [segment.replace("~", "~0").replace("/", "~1") for segment in relative_path]
    suffix = "/".join(escaped)
    return f"{base_path.rstrip('/')}/{suffix}" if suffix else base_path


def _is_json_pointer_value(value: Any) -> bool:
    return isinstance(value, str) and _is_json_pointer(value)


def _apply_dynamic_binding_targets(
    rows: list[list[Any]],
    targets: list[_DynamicBindingTarget],
) -> list[list[Any]]:
    data_values: dict[str, Any] = {}
    original_data_rows: list[list[Any]] = []
    component_ids: set[str] = set()
    for row in rows:
        if _is_compact_data_row(row) and len(row) == 2:
            _record_compact_data_values(row[0], row[1], data_values)
            original_data_rows.append(row)
            continue
        if len(row) >= 3 and isinstance(row[0], str):
            component_ids.add(row[0])

    output_rows: list[list[Any]] = []
    emitted_paths: set[str] = set()
    referenced_paths: set[str] = set()
    replaced_source_paths: set[str] = set()
    existing_value_ids, decoration_literal_ids = _find_existing_text_decorations(
        rows,
        targets,
    )
    for row in rows:
        if _is_compact_data_row(row):
            continue
        transformed_rows, initial_values, replaced_paths = _bind_component_row(
            row,
            targets,
            data_values,
            component_ids,
            existing_value_ids,
            decoration_literal_ids,
        )
        replaced_source_paths.update(replaced_paths)
        for transformed_row in transformed_rows:
            output_rows.append(transformed_row)
            if len(transformed_row) < 3 or not isinstance(transformed_row[2], dict):
                continue
            for _, path, initializes_value in _path_bindings(transformed_row[2]):
                referenced_paths.add(path)
                if not initializes_value:
                    continue
                initial_value = initial_values.get(path, data_values.get(path, ""))
                output_rows.append([path, initial_value])
                emitted_paths.add(path)

    for data_row in original_data_rows:
        path = data_row[0]
        if path in emitted_paths or path in replaced_source_paths:
            continue
        if path not in referenced_paths:
            continue
        output_rows.append(data_row)
    return output_rows


def _record_compact_data_values(
    path: str,
    value: Any,
    data_values: dict[str, Any],
    depth: int = 0,
) -> None:
    data_values[path] = value
    if depth >= 12:
        return
    if isinstance(value, dict):
        for key, child_value in value.items():
            child_path = _join_json_pointer(path, (str(key),))
            _record_compact_data_values(
                child_path,
                child_value,
                data_values,
                depth + 1,
            )
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            child_path = _join_json_pointer(path, (str(index),))
            _record_compact_data_values(
                child_path,
                child_value,
                data_values,
                depth + 1,
            )


def _bind_component_row(
    row: list[Any],
    targets: list[_DynamicBindingTarget],
    data_values: dict[str, Any],
    component_ids: set[str],
    existing_value_ids: set[str],
    decoration_literal_ids: set[str],
) -> tuple[list[list[Any]], dict[str, Any], set[str]]:
    if len(row) not in {3, 4}:
        return [row], {}, set()
    component_id, component_type, source_props = row[:3]
    if not isinstance(component_id, str):
        return [row], {}, set()
    if not isinstance(source_props, dict):
        return [row], {}, set()
    if component_id in decoration_literal_ids:
        return [row], {}, set()
    if _is_static_semantic_text(component_id, component_type, source_props):
        return [row], {}, set()

    props = dict(source_props)
    prop_names = _dynamic_prop_names(component_type, props)
    initial_values: dict[str, Any] = {}
    replaced_source_paths: set[str] = set()
    for prop_name in prop_names:
        value = props.get(prop_name)
        expanded_rows, expanded_values = _expand_inline_binding_text_component(
            component_id,
            component_type,
            prop_name,
            props,
            value,
            targets,
            data_values,
            component_ids,
        )
        if expanded_rows:
            return expanded_rows, expanded_values, replaced_source_paths
        source_path = value.get("path") if _is_path_binding(value) else None
        target = _select_dynamic_binding_target(
            targets,
            component_id,
            value,
            source_path,
        )
        if target is None:
            continue
        if source_path is not None and source_path != target.path:
            replaced_source_paths.add(source_path)
        initial_value = _initial_value_for_target(
            value,
            source_path,
            target,
            data_values,
        )
        needs_decoration = _needs_decorated_text(component_type, prop_name, target)
        if needs_decoration:
            if component_id not in existing_value_ids:
                expanded_rows, expanded_values = _expand_decorated_text_component(
                    component_id,
                    props,
                    target,
                    initial_value,
                    component_ids,
                )
                return expanded_rows, expanded_values, replaced_source_paths
        props[prop_name] = {"path": target.path}
        initial_values[target.path] = initial_value

    updated_row = [component_id, component_type, props]
    if len(row) == 4:
        updated_row.append(row[3])
    return [updated_row], initial_values, replaced_source_paths


def _is_static_semantic_text(
    component_id: str,
    component_type: Any,
    props: dict[str, Any],
) -> bool:
    if component_type != "Text" or not isinstance(props.get("content"), str):
        return False
    normalized_id = _normalize_semantic_name(component_id)
    return any(term in normalized_id for term in _STATIC_TEXT_ROLE_TERMS)


def _find_existing_text_decorations(
    rows: list[list[Any]],
    targets: list[_DynamicBindingTarget],
) -> tuple[set[str], set[str]]:
    component_rows: dict[str, list[Any]] = {}
    for row in rows:
        if len(row) < 3:
            continue
        component_id = row[0]
        if not isinstance(component_id, str):
            continue
        component_rows[component_id] = row

    existing_value_ids: set[str] = set()
    decoration_literal_ids: set[str] = set()
    for row in rows:
        if len(row) != 4:
            continue
        child_ids = row[3]
        if not isinstance(child_ids, list):
            continue
        child_rows: list[list[Any]] = []
        for child_id in child_ids:
            child_row = component_rows.get(child_id)
            if child_row is not None:
                child_rows.append(child_row)
        for child_row in child_rows:
            target = _existing_decoration_target(child_row, targets)
            if target is None:
                continue
            literal_ids = _matching_decoration_literal_ids(
                child_row[0],
                child_rows,
                target.rule,
            )
            if not literal_ids:
                continue
            existing_value_ids.add(child_row[0])
            decoration_literal_ids.update(literal_ids)
    return existing_value_ids, decoration_literal_ids


def _existing_decoration_target(
    row: list[Any],
    targets: list[_DynamicBindingTarget],
) -> _DynamicBindingTarget | None:
    if len(row) < 3:
        return None
    if row[1] != "Text":
        return None
    component_id = row[0]
    props = row[2]
    if not isinstance(component_id, str):
        return None
    if not isinstance(props, dict):
        return None
    value = props.get("content")
    source_path = value.get("path") if _is_path_binding(value) else None
    target = _select_dynamic_binding_target(targets, component_id, value, source_path)
    if target is None:
        return None
    if not _needs_decorated_text("Text", "content", target):
        return None
    if _is_path_binding(value):
        return target
    if _is_number(value):
        return target
    pattern = target.rule.value_pattern
    if not isinstance(value, str):
        return None
    if pattern is None:
        return None
    if pattern.fullmatch(value) is None:
        return None
    return target


def _matching_decoration_literal_ids(
    value_component_id: str,
    sibling_rows: list[list[Any]],
    rule: _DynamicBindingRule,
) -> set[str]:
    expected_texts = []
    if rule.display_prefix:
        expected_texts.append(rule.display_prefix)
    if rule.display_suffix:
        expected_texts.append(rule.display_suffix)

    matching_ids: set[str] = set()
    for sibling_row in sibling_rows:
        if len(sibling_row) < 3:
            continue
        if sibling_row[0] == value_component_id:
            continue
        if sibling_row[1] != "Text":
            continue
        if not isinstance(sibling_row[2], dict):
            continue
        content = sibling_row[2].get("content")
        if not isinstance(content, str):
            continue
        for expected_text in expected_texts:
            if content.strip() == expected_text.strip():
                matching_ids.add(sibling_row[0])
                break
    return matching_ids


def _dynamic_prop_names(component_type: Any, props: dict[str, Any]) -> tuple[str, ...]:
    if component_type == "Text" and "content" in props:
        return ("content",)
    if component_type == "Image" and _is_path_binding(props.get("src")):
        return ("src",)
    if component_type == "Button" and _is_path_binding(props.get("label")):
        return ("label",)
    return ()


def _select_dynamic_binding_target(
    targets: list[_DynamicBindingTarget],
    component_id: str,
    value: Any,
    source_path: str | None,
) -> _DynamicBindingTarget | None:
    if source_path is not None:
        exact_target = next((target for target in targets if target.path == source_path), None)
        if exact_target is not None:
            return exact_target
        suffix_target = _target_with_matching_schema_suffix(targets, source_path)
        if suffix_target is not None:
            return suffix_target
        source_is_canonical = any(
            _path_is_at_or_below(source_path, target.binding_root)
            for target in targets
        )
        if source_is_canonical:
            return None

    scored_targets = [
        (
            _dynamic_target_score(target, component_id, value, source_path),
            target,
        )
        for target in targets
    ]
    scored_targets.sort(key=lambda item: item[0], reverse=True)
    if not scored_targets or scored_targets[0][0] < 90:
        return None
    if len(scored_targets) > 1 and scored_targets[0][0] == scored_targets[1][0]:
        return None
    return scored_targets[0][1]


def _target_with_matching_schema_suffix(
    targets: list[_DynamicBindingTarget],
    source_path: str,
) -> _DynamicBindingTarget | None:
    matching_target: _DynamicBindingTarget | None = None
    for target in targets:
        suffix = "/" + "/".join(target.rule.relative_path)
        if not source_path.endswith(suffix):
            continue
        if matching_target is not None:
            return None
        matching_target = target
    return matching_target


def _dynamic_target_score(
    target: _DynamicBindingTarget,
    component_id: str,
    value: Any,
    source_path: str | None,
) -> int:
    rule = target.rule
    normalized_id = _normalize_semantic_name(component_id)
    normalized_source = _normalize_semantic_name(source_path or "")
    score = _alias_score(normalized_id, rule.strong_aliases, 120, 100)
    score += _alias_score(normalized_id, rule.weak_aliases, 45, 35)
    score += _alias_score(normalized_source, rule.source_aliases, 90, 80)
    if isinstance(value, str) and rule.value_pattern is not None:
        if rule.value_pattern.fullmatch(value):
            score += 80
    return score


def _alias_score(
    normalized_value: str,
    aliases: tuple[str, ...],
    exact_score: int,
    contains_score: int,
) -> int:
    best_score = 0
    for alias in aliases:
        normalized_alias = _normalize_semantic_name(alias)
        if not normalized_alias:
            continue
        if normalized_value == normalized_alias:
            best_score = max(best_score, exact_score)
        elif normalized_alias in normalized_value:
            best_score = max(best_score, contains_score)
    return best_score


def _normalize_semantic_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _initial_value_for_target(
    value: Any,
    source_path: str | None,
    target: _DynamicBindingTarget,
    data_values: dict[str, Any],
) -> Any:
    if source_path is not None and source_path in data_values:
        initial_value = data_values[source_path]
    elif not _is_path_binding(value):
        initial_value = value
    else:
        initial_value = target.initial_value

    if target.schema_type in {"number", "integer"}:
        numeric_value = _number_from_display_value(initial_value)
        if numeric_value is not _MISSING:
            return numeric_value
        return target.initial_value if _is_number(target.initial_value) else 0
    if target.schema_type == "string" and not isinstance(initial_value, str):
        return "" if initial_value is None else str(initial_value)
    return initial_value


def _number_from_display_value(value: Any) -> int | float | object:
    if _is_number(value):
        return value
    if not isinstance(value, str):
        return _MISSING
    match = _NUMBER_IN_TEXT_PATTERN.search(value)
    if match is None:
        return _MISSING
    number_text = match.group(0)
    return float(number_text) if "." in number_text else int(number_text)


def _needs_decorated_text(
    component_type: Any,
    prop_name: str,
    target: _DynamicBindingTarget,
) -> bool:
    rule = target.rule
    return (
        component_type == "Text"
        and prop_name == "content"
        and target.schema_type in {"number", "integer"}
        and bool(rule.display_prefix or rule.display_suffix)
    )


def _expand_decorated_text_component(
    component_id: str,
    props: dict[str, Any],
    target: _DynamicBindingTarget,
    initial_value: Any,
    component_ids: set[str],
) -> tuple[list[list[Any]], dict[str, Any]]:
    text_props = {
        key: value
        for key, value in props.items()
        if key in _TEXT_VISUAL_PROPS
    }
    container_props = {
        key: value
        for key, value in props.items()
        if key not in _TEXT_VISUAL_PROPS and key != "content"
    }
    text_align = text_props.get("textAlign")
    if text_align in {"start", "center", "end"}:
        container_props.setdefault("justifyContent", text_align)
    else:
        container_props.setdefault("justifyContent", "center")
    container_props.setdefault("alignItems", "center")
    container_props.setdefault("space", 0)

    child_ids: list[str] = []
    child_rows: list[list[Any]] = []
    rule = target.rule
    if rule.display_prefix:
        prefix_id = _new_component_id(f"{component_id}_prefix", component_ids)
        child_ids.append(prefix_id)
        child_rows.append(
            [prefix_id, "Text", {**text_props, "content": rule.display_prefix}]
        )

    value_id = _new_component_id(f"{component_id}_value", component_ids)
    child_ids.append(value_id)
    child_rows.append(
        [value_id, "Text", {**text_props, "content": {"path": target.path}}]
    )

    if rule.display_suffix:
        suffix_id = _new_component_id(f"{component_id}_suffix", component_ids)
        child_ids.append(suffix_id)
        child_rows.append(
            [suffix_id, "Text", {**text_props, "content": rule.display_suffix}]
        )

    parent_row = [component_id, "Row", container_props, child_ids]
    return [parent_row, *child_rows], {target.path: initial_value}


def _expand_inline_binding_text_component(
    component_id: str,
    component_type: Any,
    prop_name: str,
    props: dict[str, Any],
    value: Any,
    targets: list[_DynamicBindingTarget],
    data_values: dict[str, Any],
    component_ids: set[str],
) -> tuple[list[list[Any]], dict[str, Any]]:
    if component_type != "Text" or prop_name != "content" or not isinstance(value, str):
        return [], {}

    matches = []
    for match in _INLINE_BINDING_PATH_PATTERN.finditer(value):
        path = match.group(0)
        is_canonical = any(
            _path_is_at_or_below(path, target.binding_root)
            for target in targets
        )
        if is_canonical:
            matches.append(match)
    if not matches:
        return [], {}

    text_props = {
        key: prop_value
        for key, prop_value in props.items()
        if key in _TEXT_VISUAL_PROPS
    }
    container_props = {
        key: prop_value
        for key, prop_value in props.items()
        if key not in _TEXT_VISUAL_PROPS and key != "content"
    }
    max_lines = text_props.get("maxLines")
    use_column = len(matches) > 1 and _is_number(max_lines) and max_lines > 1
    container_type = "Column" if use_column else "Row"
    container_props.setdefault("justifyContent", "start")
    container_props.setdefault("alignItems", "center" if not use_column else "start")
    container_props.setdefault("space", 2 if use_column else 0)
    if use_column:
        text_props["maxLines"] = 1

    child_ids: list[str] = []
    child_rows: list[list[Any]] = []
    initial_values: dict[str, Any] = {}
    part_number = 1

    def append_part(content: Any) -> None:
        nonlocal part_number
        child_id = _new_component_id(
            f"{component_id}_part_{part_number}",
            component_ids,
        )
        part_number += 1
        child_ids.append(child_id)
        child_rows.append([child_id, "Text", {**text_props, "content": content}])

    cursor = 0
    for match in matches:
        literal = value[cursor:match.start()]
        if literal.strip():
            append_part(literal)
        path = match.group(0)
        append_part({"path": path})
        initial_values[path] = data_values.get(path, "")
        cursor = match.end()
    suffix = value[cursor:]
    if suffix.strip():
        append_part(suffix)

    parent_row = [component_id, container_type, container_props, child_ids]
    return [parent_row, *child_rows], initial_values


def _new_component_id(base_id: str, component_ids: set[str]) -> str:
    candidate = base_id
    suffix = 2
    while candidate in component_ids:
        candidate = f"{base_id}_{suffix}"
        suffix += 1
    component_ids.add(candidate)
    return candidate


@dataclass(frozen=True)
class CompactDSLValidationReport:
    errors: list[str]
    warnings: list[str]
    diagnostics: tuple[CompactDSLDiagnostic, ...]

    def passed(self, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)


@dataclass(frozen=True)
class _ComponentRecord:
    line: int
    component_id: str
    component_type: str
    props: dict[str, Any]
    children: list[str]


class _Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.diagnostics: list[CompactDSLDiagnostic] = []
        self.category = _ISSUE_STRUCTURE

    def set_category(self, category: str) -> None:
        self.category = category

    def error(self, message: str) -> None:
        self.errors.append(message)
        self.diagnostics.append(
            CompactDSLDiagnostic(
                category=self.category,
                severity="error",
                message=message,
            )
        )

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        self.diagnostics.append(
            CompactDSLDiagnostic(
                category=self.category,
                severity="warning",
                message=message,
            )
        )


def validate_compact_dsl(
    genui_text: str,
    cardspec: dict[str, Any] | str,
    component_whitelist: list[str] | tuple[str, ...] | None = None,
    strict: bool = False,
    task_spec: dict[str, Any] | str | None = None,
) -> CompactDSLValidationReport:
    """Validate raw tuple-based GenUI NDJSON and its CardSpec boundary."""
    reporter = _Reporter()
    allowed = set(component_whitelist or COMPONENT_WHITELIST)
    reporter.set_category(_ISSUE_STRUCTURE)
    _check_cardspec(cardspec, reporter)

    reporter.set_category(_ISSUE_SYNTAX)
    if "```" in genui_text:
        reporter.error("genui must be raw NDJSON without Markdown fences.")

    components: dict[str, _ComponentRecord] = {}
    component_order: list[_ComponentRecord] = []
    data_rows: dict[str, list[tuple[int, Any]]] = defaultdict(list)
    record_order: list[tuple[str, int, str]] = []

    for line_number, raw_line in enumerate(genui_text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        reporter.set_category(_ISSUE_SYNTAX)
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            reporter.error(f"genui line {line_number} is invalid JSON: {exc}.")
            continue
        if not isinstance(value, list):
            reporter.error(f"genui line {line_number} must be a JSON array.")
            continue

        reporter.set_category(_ISSUE_STRUCTURE)
        if _is_compact_data_row(value):
            _read_data_line(value, line_number, data_rows, record_order, reporter)
            continue
        component = _read_component_line(value, line_number, allowed, reporter)
        if component is None:
            continue
        record_order.append(("component", line_number, component.component_id))
        if component.component_id in components:
            reporter.error(f"line {line_number}: duplicate component id {component.component_id}.")
            continue
        components[component.component_id] = component
        component_order.append(component)

    reporter.set_category(_ISSUE_STRUCTURE)
    if not record_order:
        reporter.error("genui must contain at least one NDJSON line.")
    else:
        first_kind, first_line, first_key = record_order[0]
        if first_kind != "component" or first_key != "root":
            reporter.error(f'line {first_line}: first genui line must create component "root".')

    _check_component_tree(components, component_order, reporter)
    reporter.set_category(_ISSUE_LAYOUT)
    _check_root_visual_contract(components.get("root"), cardspec, reporter)
    _check_surface_readability(components.get("root"), component_order, reporter)
    _check_layout_capacity(components, component_order, reporter)
    _check_bottom_anchor(components.get("root"), components, reporter)
    _check_form_component_layout(component_order, data_rows, reporter)
    reporter.set_category(_ISSUE_BINDING)
    _check_bindings(component_order, data_rows, reporter)
    _check_cardspec_data_usage(cardspec, component_order, reporter)
    reporter.set_category(_ISSUE_SEMANTIC)
    _check_query_content_requirements(
        task_spec,
        cardspec,
        component_order,
        data_rows,
        reporter,
    )
    _check_weather_condition_asset(
        task_spec,
        component_order,
        data_rows,
        reporter,
    )

    errors = reporter.errors + reporter.warnings if strict else reporter.errors
    return CompactDSLValidationReport(
        errors=errors,
        warnings=reporter.warnings,
        diagnostics=tuple(reporter.diagnostics),
    )


def _is_compact_data_row(value: list[Any]) -> bool:
    if not value:
        return False
    first_item = value[0]
    if not isinstance(first_item, str):
        return False
    return first_item.startswith("/")


def _read_data_line(
    value: list[Any],
    line_number: int,
    data_rows: dict[str, list[tuple[int, Any]]],
    record_order: list[tuple[str, int, str]],
    reporter: _Reporter,
) -> None:
    if len(value) != 2:
        reporter.error(f"line {line_number}: data line must contain exactly 2 items.")
        return
    path = value[0]
    if not isinstance(path, str) or not _is_json_pointer(path):
        reporter.error(f"line {line_number}: data path must be an absolute JSON Pointer.")
        return
    data_rows[path].append((line_number, value[1]))
    record_order.append(("data", line_number, path))


def _read_component_line(
    value: list[Any],
    line_number: int,
    allowed: set[str],
    reporter: _Reporter,
) -> _ComponentRecord | None:
    if len(value) not in {3, 4}:
        reporter.error(f"line {line_number}: component line must contain 3 or 4 items.")
        return None
    component_id, component_type, props = value[:3]
    if not isinstance(component_id, str):
        reporter.error(f"line {line_number}: component id must be a non-empty non-path string.")
        return None
    if not component_id or component_id.startswith("/"):
        reporter.error(f"line {line_number}: component id must be a non-empty non-path string.")
        return None
    if not isinstance(component_type, str):
        reporter.error(f"line {line_number}: component type must be a string.")
        return None
    if component_type not in allowed:
        reporter.error(f"{component_id}: unsupported component {component_type}.")
    if not isinstance(props, dict):
        reporter.error(f"{component_id}: props must be a JSON object.")
        return None
    for wrapper_name in ("style", "styles"):
        if wrapper_name in props:
            reporter.error(
                f"{component_id}: props must not contain a {wrapper_name} wrapper."
            )
    if "onClick" in props:
        reporter.error(f"{component_id}: onClick is unsupported; use Button.action.")
    if component_type != "Button" and "action" in props:
        reporter.error(f"{component_id}: only Button may contain action.")

    children: list[str] = []
    if component_type in CONTAINER_COMPONENTS:
        if len(value) != 4:
            reporter.error(f"{component_id}: {component_type} requires a children array.")
        elif not isinstance(value[3], list) or not all(
            isinstance(child, str) and child for child in value[3]
        ):
            reporter.error(f"{component_id}: children must be an array of non-empty string IDs.")
        else:
            children = value[3]
            if not children:
                reporter.error(f"{component_id}: {component_type} children must not be empty.")
            if len(children) != len(set(children)):
                reporter.error(f"{component_id}: children must not contain duplicate IDs.")
    elif len(value) == 4:
        reporter.error(f"{component_id}: {component_type} must not have a children array.")

    _check_required_props(component_id, component_type, props, reporter)
    _check_component_prop_types(component_id, component_type, props, reporter)
    return _ComponentRecord(line_number, component_id, component_type, props, children)


def _check_cardspec(cardspec: dict[str, Any] | str, reporter: _Reporter) -> None:
    if isinstance(cardspec, str):
        try:
            cardspec = json.loads(cardspec)
        except json.JSONDecodeError as exc:
            reporter.error(f"cardspec is invalid JSON: {exc}.")
            return
    if not isinstance(cardspec, dict):
        reporter.error("cardspec must be a JSON object.")
        return
    if cardspec.get("suggestSize") not in {"2x2", "2x4"}:
        reporter.error('cardspec.suggestSize must be "2x2" or "2x4".')
    if any(key in cardspec for key in ("onClick", "events", "click", "actions")):
        reporter.error("CardSpec must not contain click behavior.")


def _check_required_props(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    for key in REQUIRED_PROPS.get(component_type, ()):
        if key not in props:
            reporter.error(f"{component_id}: {component_type} requires prop {key}.")


def _check_component_prop_types(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    _check_numeric_style_props(component_id, props, reporter)
    if component_type in {"Row", "Column", "List"} and "space" in props:
        space = _numeric_value(props["space"])
        if space is None or space < 0:
            reporter.error(
                f"{component_id}: {component_type}.space must be a non-negative number."
            )
    elif component_type == "Text" and "content" in props:
        _require_string_source(component_id, "content", props["content"], reporter)
    elif component_type == "Image" and "src" in props:
        _require_string_source(component_id, "src", props["src"], reporter)
        if "filter" in props:
            reporter.error(
                f"{component_id}: Image.filter is unsupported; use a contrasting surface."
            )
    elif component_type == "Progress":
        for key in ("value", "total"):
            source = props.get(key)
            if key in props and not _is_number_source(source):
                reporter.error(
                    f"{component_id}: Progress.{key} must be a number or path binding."
                )
        value = props.get("value")
        total = props.get("total")
        if _is_number(value) and not 0 <= value <= 100:
            reporter.error(f"{component_id}: Progress.value must be between 0 and 100.")
        if _is_number(total) and total <= 0:
            reporter.error(f"{component_id}: Progress.total must be greater than 0.")
        if _is_number(value) and _is_number(total):
            if value > total:
                reporter.error(f"{component_id}: Progress.value must not exceed total.")
    elif component_type == "Button":
        if "label" in props:
            _require_string_source(component_id, "label", props["label"], reporter)
            label = props["label"]
            if isinstance(label, str) and not label.strip():
                reporter.error(f"{component_id}: Button.label must not be empty.")
        enabled = props.get("enabled")
        if "enabled" in props and not _is_bool_source(enabled):
            reporter.error(
                f"{component_id}: Button.enabled must be a boolean or path binding."
            )
        if "action" in props:
            _check_button_action(component_id, props["action"], reporter)
    elif component_type == "Checkbox":
        for prop_name in ("label", "value", "group"):
            if prop_name in props:
                _require_string_source(component_id, prop_name, props[prop_name], reporter)
        selected = props.get("select")
        if "select" in props and not _is_bool_source(selected):
            reporter.error(
                f"{component_id}: Checkbox.select must be a boolean or path binding."
            )


def _check_numeric_style_props(
    component_id: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    for prop_name in ("width", "height", "padding", "fontSize"):
        value = props.get(prop_name)
        if not isinstance(value, str):
            continue
        if _NUMERIC_STRING_PATTERN.fullmatch(value.strip()) is not None:
            reporter.error(f"{component_id}: {prop_name} must use a JSON number, not a string.")

    if "padding" not in props:
        return
    padding = props["padding"]
    horizontal_extent = _padding_extent(padding, "width")
    vertical_extent = _padding_extent(padding, "height")
    if horizontal_extent is None or vertical_extent is None:
        reporter.error(
            f"{component_id}: padding must be a non-negative number or a numeric side object."
        )


def _require_string_source(
    component_id: str,
    prop_name: str,
    value: Any,
    reporter: _Reporter,
) -> None:
    if not isinstance(value, str) and not _is_path_binding(value):
        reporter.error(
            f"{component_id}: {prop_name} must be a string literal or path binding object."
        )


def _is_number_source(value: Any) -> bool:
    return _is_number(value) or _is_path_binding(value)


def _is_bool_source(value: Any) -> bool:
    return isinstance(value, bool) or _is_path_binding(value)


def _check_button_action(component_id: str, action: Any, reporter: _Reporter) -> None:
    if not isinstance(action, dict):
        reporter.error(f"{component_id}: Button.action must be an object.")
        return
    if set(action) != {"functionCall"}:
        reporter.error(
            f"{component_id}: Button.action must contain only functionCall."
        )
        return
    function_call = action["functionCall"]
    if not isinstance(function_call, dict):
        reporter.error(f"{component_id}: Button.action.functionCall must be an object.")
        return
    if not _is_non_empty_string(function_call.get("call")):
        reporter.error(f"{component_id}: functionCall.call must be a non-empty string.")
    if not isinstance(function_call.get("args"), dict):
        reporter.error(f"{component_id}: functionCall.args must be an object.")


def _check_component_tree(
    components: dict[str, _ComponentRecord],
    component_order: list[_ComponentRecord],
    reporter: _Reporter,
) -> None:
    root = components.get("root")
    if root is None:
        reporter.error('genui must define component "root".')
        return
    if not component_order or component_order[0].component_id != "root":
        reporter.error('the first component line must define component "root".')
    if root.component_type not in ROOT_COMPONENTS:
        reporter.error("root component type must be Column or Stack.")
    if root.props.get("width") != "matchParent":
        reporter.error('root props.width must be "matchParent".')
    has_visible_component = any(
        component.component_type not in CONTAINER_COMPONENTS
        for component in component_order
    )
    if not has_visible_component:
        reporter.error("genui must contain at least one visible non-container component.")

    parents: dict[str, list[_ComponentRecord]] = defaultdict(list)
    for parent in component_order:
        for child_id in parent.children:
            parents[child_id].append(parent)
            child = components.get(child_id)
            if child is None:
                reporter.error(f"{parent.component_id}: child id {child_id} is never created.")
            elif child.line <= parent.line:
                reporter.error(
                    f"{parent.component_id}: child {child_id} must be created after its parent."
                )

    for component in component_order:
        if component.component_id == "root":
            if component.component_id in parents:
                reporter.error("root must not appear in another component's children.")
            continue
        declared_by = [
            parent
            for parent in parents.get(component.component_id, [])
            if parent.line < component.line
        ]
        if not declared_by:
            reporter.error(
                f"{component.component_id}: component must first appear in an earlier "
                "parent's children."
            )
        elif len(declared_by) > 1:
            reporter.error(
                f"{component.component_id}: component must have exactly one parent, found "
                f"{len(declared_by)}."
            )


def _check_root_visual_contract(
    root: _ComponentRecord | None,
    cardspec: dict[str, Any] | str,
    reporter: _Reporter,
) -> None:
    if root is None:
        return
    cardspec_value = _object_as_dict(cardspec)
    if cardspec_value is None:
        return
    size = cardspec_value.get("suggestSize")
    if size not in {"2x2", "2x4"}:
        return

    height = _numeric_value(root.props.get("height"))
    if height != 140:
        reporter.error("root: height must be 140 for 2x2 and 2x4 Form cards.")
    expected_radius = 18 if size == "2x2" else 22
    radius = _numeric_value(root.props.get("borderRadius"))
    if radius != expected_radius:
        reporter.error(
            f"root: borderRadius must be {expected_radius} for a {size} Form card."
        )
    if root.props.get("clip") is not True:
        reporter.error("root: clip must be true.")
    if not _is_uniform_padding(root.props.get("padding"), 12):
        reporter.warn("root: padding should be 12 on every side for the Form safe area.")


def _is_uniform_padding(value: Any, expected: int | float) -> bool:
    return _padding_values(value) == (expected, expected, expected, expected)


def _check_surface_readability(
    root: _ComponentRecord | None,
    component_order: list[_ComponentRecord],
    reporter: _Reporter,
) -> None:
    if root is None or _has_surface_background(root.props):
        return
    components = [
        (component.component_type, component.props)
        for component in component_order
    ]
    if _uses_only_light_foreground(components):
        reporter.error(
            "root: light foreground requires backgroundColor, linearGradient, or "
            "backgroundImage to avoid an unreadable default white surface."
        )
        return
    reporter.error(
        "root: backgroundColor, linearGradient, or backgroundImage is required."
    )


def _check_layout_capacity(
    components: dict[str, _ComponentRecord],
    component_order: list[_ComponentRecord],
    reporter: _Reporter,
) -> None:
    for parent in component_order:
        axis = _layout_main_axis(parent.component_type)
        if axis is None or not parent.children:
            continue
        capacity = _layout_capacity(parent.props, axis)
        if capacity is None:
            continue

        child_sizes: list[float] = []
        for child_id in parent.children:
            child = components.get(child_id)
            child_size = _numeric_value(child.props.get(axis)) if child is not None else None
            if child_size is None:
                child_sizes = []
                break
            child_sizes.append(child_size)
        if not child_sizes:
            continue

        spacing = _numeric_value(parent.props.get("space")) or 0
        required_size = sum(child_sizes)
        required_size += spacing * max(0, len(child_sizes) - 1)
        if required_size <= capacity + _LAYOUT_PIXEL_TOLERANCE:
            continue
        has_padding = _padding_extent(parent.props.get("padding"), axis) not in {None, 0.0}
        capacity_label = " after padding" if has_padding else ""
        reporter.error(
            f"{parent.component_id}: children require {required_size:g} {axis}, "
            f"but the container provides {capacity:g}{capacity_label}."
        )


def _check_bottom_anchor(
    root: _ComponentRecord | None,
    components: dict[str, _ComponentRecord],
    reporter: _Reporter,
) -> None:
    if root is None:
        return
    if root.component_type != "Column" or not root.children:
        return
    height = _numeric_value(root.props.get("height"))
    if height is None:
        return

    padding_top, _, padding_bottom, _ = _padding_values(root.props.get("padding"))
    gap = _numeric_value(root.props.get("space")) or 0.0
    used = padding_top + padding_bottom
    used += gap * max(0, len(root.children) - 1)
    for child_id in root.children:
        child = components.get(child_id)
        if child is None:
            return
        child_height = _numeric_value(child.props.get("height"))
        if child_height is None:
            return
        used += child_height

    bottom_gap = height - used + padding_bottom
    if bottom_gap > 16:
        reporter.error(
            f"root: last section bottom gap is {bottom_gap:g}, exceeding 16."
        )
    elif bottom_gap < 8:
        reporter.warn(
            f"root: last section bottom gap is {bottom_gap:g}; "
            "typical 2x2/2x4 bottom gap is 8-14."
        )


def _check_form_component_layout(
    component_order: list[_ComponentRecord],
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    for component in component_order:
        _check_form_style_scale(component, reporter)
        if component.component_type == "Image":
            _check_image_layout(component, reporter)
        if component.component_type in {"Text", "Button"}:
            _check_text_or_button_fit(component, data_rows, reporter)


def _check_form_style_scale(
    component: _ComponentRecord,
    reporter: _Reporter,
) -> None:
    font_size = _numeric_value(component.props.get("fontSize"))
    if font_size is not None and int(font_size) not in FORM_FONT_SIZES:
        reporter.error(
            f"{component.component_id}: fontSize {font_size:g} is outside the approved scale."
        )

    overflow = component.props.get("textOverflow")
    if overflow in {"ellipsis", "clip", "marquee"}:
        reporter.error(
            f"{component.component_id}: textOverflow {overflow} is not allowed for "
            "generated protected text."
        )

    for prop_name in ("padding", "margin"):
        for value in _padding_values(component.props.get(prop_name)):
            if value not in FORM_SPACING:
                reporter.warn(
                    f"{component.component_id}: {prop_name} value {value:g} is outside "
                    "the spacing scale."
                )

    space = _numeric_value(component.props.get("space"))
    if space is not None and space not in FORM_SPACING:
        reporter.warn(
            f"{component.component_id}: space {space:g} is outside the spacing scale."
        )


def _check_image_layout(component: _ComponentRecord, reporter: _Reporter) -> None:
    width = _numeric_value(component.props.get("width"))
    height = _numeric_value(component.props.get("height"))
    if width is None or height is None:
        reporter.error(
            f"{component.component_id}: Image must have explicit numeric width and height."
        )
    if component.props.get("objectFit") != "contain":
        reporter.warn(
            f"{component.component_id}: Image should use objectFit contain unless "
            "deliberately cropped."
        )


def _check_text_or_button_fit(
    component: _ComponentRecord,
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    prop_name = "content" if component.component_type == "Text" else "label"
    text = _visible_text(component, prop_name, data_rows)
    if text is None:
        return

    font_size = _numeric_value(component.props.get("fontSize")) or 14.0
    width = _numeric_value(component.props.get("width"))
    if component.component_type == "Text":
        max_lines = int(_numeric_value(component.props.get("maxLines")) or 1)
        if width is None:
            return
        estimated_width = _estimate_text_width(text, font_size)
        if estimated_width > width * max_lines:
            reporter.error(
                f"{component.component_id}: text {text!r} estimated width "
                f"{estimated_width:.1f} exceeds {width:g} x {max_lines} lines."
            )
        return

    height = _numeric_value(component.props.get("height"))
    if height is not None and height < 24:
        reporter.error(f"{component.component_id}: Button height must be at least 24.")
    if width is None:
        return
    estimated_width = _estimate_text_width(text, font_size)
    estimated_width += _button_horizontal_safety_space(text)
    if estimated_width > width:
        reporter.error(
            f"{component.component_id}: Button label {text!r} may not fit width {width:g}."
        )


def _visible_text(
    component: _ComponentRecord,
    prop_name: str,
    data_rows: dict[str, list[tuple[int, Any]]],
) -> str | None:
    source = component.props.get(prop_name)
    if isinstance(source, str):
        return source
    if not _is_path_binding(source):
        return None
    for line, value in data_rows.get(source["path"], []):
        if line <= component.line:
            continue
        if value is None:
            return ""
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return None
    return None


def _estimate_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for char in text:
        if _CJK_PATTERN.match(char):
            width += font_size
        elif char.isspace():
            width += 0.35 * font_size
        elif char in ".,;:!?'\"°%/|":
            width += 0.4 * font_size
        else:
            width += 0.6 * font_size
    return width


def _button_horizontal_safety_space(text: str) -> float:
    if _CJK_PATTERN.search(text) is not None:
        return 28.0
    return 16.0


def _check_cardspec_data_usage(
    cardspec: dict[str, Any] | str,
    component_order: list[_ComponentRecord],
    reporter: _Reporter,
) -> None:
    cardspec_value = _object_as_dict(cardspec)
    if cardspec_value is None:
        return
    bindings = cardspec_value.get("dataBindings")
    if not isinstance(bindings, list):
        return

    used_paths: set[str] = set()
    for component in component_order:
        for _, path, _ in _path_bindings(component.props):
            used_paths.add(path)

    checked_paths: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        write_result_to = binding.get("writeResultTo")
        if not _is_json_pointer_value(write_result_to):
            continue
        if write_result_to in checked_paths:
            continue
        checked_paths.add(write_result_to)
        if any(_path_is_at_or_below(path, write_result_to) for path in used_paths):
            continue
        capability_id = binding.get("capabilityId", "unknown")
        reporter.error(
            f"CardSpec data binding {capability_id} requires a visible path under "
            f"{write_result_to}."
        )


def _check_query_content_requirements(
    task_spec: dict[str, Any] | str | None,
    cardspec: dict[str, Any] | str,
    component_order: list[_ComponentRecord],
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    scenario = _match_card_scenario(task_spec)
    if scenario is None:
        return
    visible_text = _visible_semantic_text(component_order, data_rows)
    used_paths = _visible_binding_paths(component_order)
    binding_roots = _cardspec_data_binding_roots(cardspec)

    for requirement in scenario.content_requirements:
        if requirement.path_fragments and not binding_roots:
            continue
        _check_visible_content_requirement(
            requirement,
            visible_text,
            used_paths,
            reporter,
        )
    if _is_weather_forecast_task(task_spec) and binding_roots:
        for requirement in _WEATHER_FORECAST_REQUIREMENTS:
            _check_visible_content_requirement(
                requirement,
                visible_text,
                used_paths,
                reporter,
            )
    active_actions = _active_action_requirements(task_spec, scenario)
    for requirement in active_actions:
        _check_visible_action_requirement(requirement, component_order, reporter)


def _check_weather_condition_asset(
    task_spec: dict[str, Any] | str | None,
    component_order: list[_ComponentRecord],
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    if _normalize_visible_text("天气") not in _normalized_task_text(task_spec):
        return
    condition = _weather_condition_preview(data_rows)
    if not condition:
        return

    for component in component_order:
        if component.component_type != "Image":
            continue
        component_id = component.component_id.lower()
        if not any(term in component_id for term in _WEATHER_ICON_ID_TERMS):
            continue
        src = component.props.get("src")
        if not isinstance(src, str):
            continue
        allowed_conditions = _weather_asset_conditions(src)
        if not allowed_conditions:
            continue
        if any(term in condition for term in allowed_conditions):
            continue
        reporter.warn(
            f'{component.component_id}: weather asset "{src}" does not match preview condition '
            f'"{condition}"; omit the image when no matching asset is available.'
        )


def _weather_condition_preview(
    data_rows: dict[str, list[tuple[int, Any]]],
) -> str:
    for path, entries in data_rows.items():
        if not path.lower().endswith("/current/condition") or not entries:
            continue
        value = entries[-1][1]
        if isinstance(value, str):
            return _normalize_visible_text(value)
    return ""


def _weather_asset_conditions(src: str) -> tuple[str, ...]:
    normalized_src = src.lower()
    for asset_terms, condition_terms in _WEATHER_ICON_CONDITION_RULES:
        if any(term in normalized_src for term in asset_terms):
            return condition_terms
    return ()


def _visible_binding_paths(component_order: list[_ComponentRecord]) -> set[str]:
    used_paths: set[str] = set()
    for component in component_order:
        for _, path, _ in _path_bindings(component.props):
            used_paths.add(path.lower())
    return used_paths


def _check_visible_content_requirement(
    requirement: _VisibleContentRequirement,
    visible_text: str,
    used_paths: set[str],
    reporter: _Reporter,
) -> None:
    if requirement.path_fragments:
        has_dynamic_value = False
        for fragment in requirement.path_fragments:
            for path in used_paths:
                if fragment.lower() in path:
                    has_dynamic_value = True
                    break
            if has_dynamic_value:
                break
        if not has_dynamic_value:
            reporter.error(
                f'userQuery content "{requirement.name}" requires a visible dynamic value.'
            )

    if requirement.visible_labels:
        has_visible_label = False
        for label in requirement.visible_labels:
            if _normalize_visible_text(label) in visible_text:
                has_visible_label = True
                break
        if not has_visible_label:
            reporter.error(
                f'userQuery content "{requirement.name}" requires a visible semantic label; '
                "icons and bare values are insufficient."
            )

    if requirement.value_kind and not _visible_value_matches(
        visible_text,
        requirement.value_kind,
    ):
        reporter.error(
            f'userQuery content "{requirement.name}" requires a visible {requirement.value_kind} '
            "value."
        )


def _visible_value_matches(visible_text: str, value_kind: str) -> bool:
    if value_kind == "percent":
        return _VISIBLE_PERCENT_PATTERN.search(visible_text) is not None
    if value_kind == "storage":
        return _VISIBLE_STORAGE_PATTERN.search(visible_text) is not None
    if value_kind == "duration":
        return _VISIBLE_DURATION_PATTERN.search(visible_text) is not None
    return False


def _check_visible_action_requirement(
    requirement: _VisibleActionRequirement,
    component_order: list[_ComponentRecord],
    reporter: _Reporter,
) -> None:
    for component in component_order:
        if component.component_type != "Button":
            continue
        label = component.props.get("label")
        if not isinstance(label, str):
            continue
        normalized_label = _normalize_visible_text(label)
        if not _action_label_matches(requirement.visible_labels, normalized_label):
            continue
        action = component.props.get("action")
        if not isinstance(action, dict):
            continue
        function_call = action.get("functionCall")
        if not isinstance(function_call, dict):
            continue
        action_text = json.dumps(
            function_call,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        normalized_action = _normalize_visible_text(action_text)
        if _action_arguments_match(requirement.argument_fragments, normalized_action):
            return
    reporter.error(
        f'userQuery action "{requirement.name}" requires a matching Button action.'
    )


def _action_label_matches(labels: tuple[str, ...], normalized_label: str) -> bool:
    for label in labels:
        if _normalize_visible_text(label) in normalized_label:
            return True
    return False


def _action_arguments_match(fragments: tuple[str, ...], action_text: str) -> bool:
    for fragment in fragments:
        if _normalize_visible_text(fragment) not in action_text:
            return False
    return True


def _visible_semantic_text(
    component_order: list[_ComponentRecord],
    data_rows: dict[str, list[tuple[int, Any]]],
) -> str:
    text_parts: list[str] = []
    for component in component_order:
        prop_name = "content" if component.component_type == "Text" else "label"
        value = component.props.get(prop_name)
        if isinstance(value, str):
            text_parts.append(value)
            continue
        if component.component_type != "Text" or not isinstance(value, dict):
            continue
        path = value.get("path")
        if not isinstance(path, str):
            continue
        entries = data_rows.get(path)
        if not entries:
            continue
        preview_value = entries[-1][1]
        if isinstance(preview_value, (str, int, float)) and not isinstance(
            preview_value,
            bool,
        ):
            text_parts.append(str(preview_value))
    return _normalize_visible_text(" ".join(text_parts))


def _normalize_visible_text(value: str) -> str:
    return "".join(value.lower().split())


def _path_is_at_or_below(path: str, base_path: str) -> bool:
    if base_path == "/":
        return path.startswith("/")
    normalized_base = base_path.rstrip("/")
    return path == normalized_base or path.startswith(f"{normalized_base}/")


def _check_bindings(
    component_order: list[_ComponentRecord],
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    for component in component_order:
        for location, path, initializes_value in _path_bindings(component.props):
            if not _is_json_pointer(path):
                reporter.error(
                    f"{component.component_id}: binding at props.{location} must use an absolute "
                    "JSON Pointer."
                )
                continue
            rows = data_rows.get(path, [])
            if not rows:
                reporter.error(
                    f"{component.component_id}: binding path {path} has no data line in this genui."
                )
                continue
            if initializes_value and not any(line > component.line for line, _ in rows):
                reporter.error(
                    f"{component.component_id}: binding path {path} must be initialized after "
                    "the component line."
                )

        _check_string_binding_value(component, "content", data_rows, reporter)
        _check_string_binding_value(component, "src", data_rows, reporter)
        _check_string_binding_value(component, "label", data_rows, reporter)


def _check_string_binding_value(
    component: _ComponentRecord,
    prop_name: str,
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    value = component.props.get(prop_name)
    if not _is_path_binding(value):
        return
    path = value["path"]
    later_values = [item for line, item in data_rows.get(path, []) if line > component.line]
    initial_value = later_values[0] if later_values else _MISSING
    text_accepts_number = prop_name == "content" and _is_number(initial_value)
    if later_values and not isinstance(initial_value, str) and not text_accepts_number:
        reporter.error(
            f"{component.component_id}: {prop_name} binding {path} must initialize a string value."
        )
        return
    if isinstance(initial_value, str) and not initial_value.strip():
        reporter.error(
            f"{component.component_id}: {prop_name} binding {path} must initialize a "
            "non-empty preview value."
        )


def _path_bindings(
    value: Any,
    path: tuple[str, ...] = (),
) -> list[tuple[str, str, bool]]:
    if _is_path_binding(value):
        location = ".".join(path)
        is_event_context = path[:3] == ("action", "event", "context")
        return [(location, value["path"], not is_event_context)]
    result: list[tuple[str, str, bool]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(_path_bindings(child, (*path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(_path_bindings(child, (*path, str(index))))
    return result


def _is_path_binding(value: Any) -> TypeGuard[_PathBinding]:
    return (
        isinstance(value, dict)
        and set(value) == {"path"}
        and isinstance(value["path"], str)
    )


def _is_json_pointer(value: str) -> bool:
    if not value.startswith("/"):
        return False
    if any("." in segment for segment in value[1:].split("/")):
        return False
    index = 0
    while index < len(value):
        if value[index] != "~":
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] not in {"0", "1"}:
            return False
        index += 2
    return True


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
