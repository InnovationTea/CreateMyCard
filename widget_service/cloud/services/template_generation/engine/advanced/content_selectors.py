"""Deterministic provider-schema selectors for content business components."""

from __future__ import annotations

import json
import math
import re
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from config.config import get_settings
from models.generation import TaskSpec

_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
_FULL_CALENDAR_DATE = re.compile(
    r"^(?P<year>\d{4})(?P<separator>[-/])(?P<month>\d{2})(?P=separator)(?P<day>\d{2})$"
)
_SHORT_CALENDAR_DATE = re.compile(r"^(?P<month>\d{2})-(?P<day>\d{2})$")
_UPDATED_AT_DATE = re.compile(
    r"^(?P<year>[1-9]\d{3})(?P<separator>[-/])(?P<month>\d{2})"
    r"(?P=separator)(?P<day>\d{2})(?:[ T].*)?$"
)

_BATCH_DATA_ADMISSION_ENABLED: ContextVar[bool] = ContextVar(
    "advanced_component_batch_data_admission_enabled",
    default=False,
)

_SELECTOR_COMPONENT_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "WeatherOverview": (
        "weather",
        ("city", "temperature", "condition", "airQuality", "temperatureRange"),
    ),
    "DateOverview": ("date", ("date", "weekday")),
    "ScheduleOverview": ("schedule", ("title", "timeText", "location")),
    "LocationOverview": ("location", ("label", "city", "updatedText")),
}

_SELECTOR_FALLBACK_FIELDS: dict[str, tuple[str, ...]] = {
    "WeatherOverview": (
        "condition",
        "temperatureText",
        "districtName",
        "prefectureName",
        "airQuality",
        "temperatureRangeText",
    ),
    "DateOverview": ("startDate", "weekday"),
    "ScheduleOverview": ("title", "dtStart", "dtEnd", "eventLocation"),
    "LocationOverview": ("districtName", "prefectureName", "updatedAt"),
}

_PROVIDER_COMPONENT_FIELDS: dict[str, tuple[str, ...]] = {
    "BatteryOverview": (
        "batterySOC",
        "batterySOCText",
        "batteryCapacityLevelDesc",
        "chargingStatusDesc",
    ),
    "ResourceUsageOverview": ("usagePercent", "availableMemText", "totalMemText"),
    "AppUsageOverview": (
        "appName",
        "durationText",
        "updatedAt",
        # Compatibility facts used by the exported v1 cross-language Golden.
        # They remain provider-derived and are only retained when present.
        "safeValue",
        "warningValue",
        "total",
        "firstLabel",
        "firstValue",
        "secondLabel",
        "secondValue",
    ),
    "ActivityOverview": ("dailySteps", "dailyTotalCaloriesText", "dailyDistanceText"),
    "HeartRateOverview": ("exerciseHeartRateAvg", "updatedAt"),
    "SleepOverview": (
        "sleepScore",
        "sleepStatus",
        "nightSleepDurationText",
        "fallAsleepTimeText",
        "wakeupTimeText",
    ),
    "BluetoothDeviceOverview": (
        "isConnected",
        "earphoneName",
        "leftBatteryLevel",
        "rightBatteryLevel",
        "batteryLevel",
    ),
    "CountdownOverview": ("countdownDays",),
}


@dataclass(frozen=True)
class WeatherOverviewFacts:
    city: str
    temperature: str
    condition: str
    air_quality: str
    temperature_range: str

    def as_selector(self) -> dict[str, dict[str, Any]]:
        return {
            "city": _field(self.city, "可信天气查询城市或地区"),
            "temperature": _field(self.temperature, "可信当前温度文本"),
            "condition": _field(self.condition, "可信当前天气状态"),
            "airQuality": _field(self.air_quality, "可信当前空气质量"),
            "temperatureRange": _field(self.temperature_range, "可信当日温度范围"),
        }


@dataclass(frozen=True)
class DateOverviewFacts:
    date: str
    weekday: str

    def as_selector(self) -> dict[str, dict[str, Any]]:
        return {
            "date": _field(self.date, "从可信日程开始日期派生的日文本"),
            "weekday": _field(self.weekday, "从可信日程开始日期派生的星期文本"),
        }


@dataclass(frozen=True)
class ScheduleOverviewFacts:
    title: str
    time_text: str
    location: str | None = None

    def as_selector(self) -> dict[str, dict[str, Any]]:
        selected = {
            "title": _field(self.title, "可信首项日程标题"),
            "timeText": _field(self.time_text, "可信首项日程起止时间"),
        }
        if self.location is not None:
            selected["location"] = _field(self.location, "可信首项日程地点")
        return selected


@dataclass(frozen=True)
class BatteryOverviewFacts:
    level_percent: int | float
    level_text: str
    capacity_level: str
    charging_status: str

    def as_selector(self) -> dict[str, dict[str, Any]]:
        number_type = "integer" if isinstance(self.level_percent, int) else "number"
        return {
            "batterySOC": {
                "type": number_type,
                "description": "可信手机本机电量百分比数值",
                "sampleValue": self.level_percent,
            },
            "batterySOCText": _field(self.level_text, "可信手机本机电量百分比文本"),
            "batteryCapacityLevelDesc": _field(self.capacity_level, "可信电量等级描述"),
            "chargingStatusDesc": _field(self.charging_status, "可信充电状态描述"),
        }

    @property
    def state(self) -> str:
        if self.level_percent <= 20:
            return "low"
        if _charging_status_is_active(self.charging_status):
            return "charging"
        return "normal"


@dataclass(frozen=True)
class BluetoothDeviceOverviewFacts:
    is_connected: bool
    earphone_name: str
    left_battery_level: int | float | None = None
    right_battery_level: int | float | None = None
    case_battery_level: int | float | None = None

    def as_selector(self) -> dict[str, dict[str, Any]]:
        selected: dict[str, dict[str, Any]] = {
            "isConnected": {
                "type": "boolean",
                "description": "可信蓝牙耳机连接状态",
                "sampleValue": self.is_connected,
            },
            "earphoneName": _field(self.earphone_name, "可信蓝牙耳机名称"),
        }
        for name, value, description in (
            ("leftBatteryLevel", self.left_battery_level, "可信左耳电量百分比"),
            ("rightBatteryLevel", self.right_battery_level, "可信右耳电量百分比"),
            ("batteryLevel", self.case_battery_level, "可信充电盒电量百分比"),
        ):
            if value is None:
                continue
            selected[name] = {
                "type": "integer" if isinstance(value, int) else "number",
                "description": description,
                "sampleValue": value,
            }
        return selected

    @property
    def battery_part_count(self) -> int:
        return sum(
            value is not None
            for value in (
                self.left_battery_level,
                self.right_battery_level,
                self.case_battery_level,
            )
        )


@dataclass(frozen=True)
class ResourceUsageOverviewFacts:
    usage_percent: int | float
    available_mem_text: str
    total_mem_text: str

    def as_selector(self) -> dict[str, dict[str, Any]]:
        return {
            "usagePercent": {
                "type": "number",
                "description": "可信系统内存占用百分比",
                "sampleValue": self.usage_percent,
            },
            "availableMemText": _field(
                self.available_mem_text,
                "可信系统可用内存文本",
            ),
            "totalMemText": _field(self.total_mem_text, "可信系统总内存文本"),
        }


@dataclass(frozen=True)
class DurationSegments:
    primary_value: str
    primary_unit: str
    secondary_value: str | None = None
    secondary_unit: str | None = None


@dataclass(frozen=True)
class AppUsageOverviewFacts:
    app_name: str
    duration_text: str
    updated_at: str | None
    duration: DurationSegments

    def as_selector(self) -> dict[str, dict[str, Any]]:
        selected = {
            "appName": _field(self.app_name, "可信单应用名称"),
            "durationText": _field(self.duration_text, "可信单应用今日使用时长原文"),
            "durationPrimaryValueText": _field(
                self.duration.primary_value,
                "从可信使用时长无损解析的主数值",
            ),
            "durationPrimaryUnitText": _field(
                self.duration.primary_unit,
                "从可信使用时长无损解析的主单位",
            ),
        }
        if self.updated_at is not None:
            selected["updatedAt"] = _field(
                self.updated_at,
                "可信应用使用时长更新时间",
            )
        if self.duration.secondary_value is not None:
            selected["durationSecondaryValueText"] = _field(
                self.duration.secondary_value,
                "从可信使用时长无损解析的次数值",
            )
            selected["durationSecondaryUnitText"] = _field(
                self.duration.secondary_unit or "",
                "从可信使用时长无损解析的次单位",
            )
        return selected


@dataclass(frozen=True)
class ActivityOverviewFacts:
    daily_steps: int
    calories_text: str | None = None
    distance_text: str | None = None

    @property
    def has_daily_summary(self) -> bool:
        return self.calories_text is not None and self.distance_text is not None

    def as_selector(self) -> dict[str, dict[str, Any]]:
        selected: dict[str, dict[str, Any]] = {
            "dailySteps": {
                "type": "integer",
                "description": "可信当日累计步数，0 为有效值",
                "sampleValue": self.daily_steps,
            }
        }
        if self.calories_text is not None:
            selected["dailyTotalCaloriesText"] = _field(
                self.calories_text,
                "可信当日总热量展示文本",
            )
        if self.distance_text is not None:
            selected["dailyDistanceText"] = _field(
                self.distance_text,
                "可信当日距离展示文本",
            )
        return selected


@dataclass(frozen=True)
class WorkoutLatestFacts:
    exercise_type_name: str
    calorie_text: str
    duration_text: str
    end_time_text: str

    def as_selector(self) -> dict[str, dict[str, Any]]:
        return {
            "exerciseTypeName": _field(self.exercise_type_name, "可信最近运动类型"),
            "exerciseCalorieText": _field(self.calorie_text, "可信最近运动热量文本"),
            "exerciseDurationText": _field(self.duration_text, "可信最近运动时长文本"),
            "exerciseEndTimeText": _field(self.end_time_text, "可信最近运动结束时刻"),
        }


@dataclass(frozen=True)
class CountdownOverviewFacts:
    countdown_days: int

    def as_selector(self) -> dict[str, dict[str, Any]]:
        return {
            "countdownDays": {
                "type": "integer",
                "description": "可信非负剩余天数，0 天为有效值",
                "sampleValue": self.countdown_days,
            }
        }


@dataclass(frozen=True)
class HeartRateOverviewFacts:
    average_bpm: int
    updated_at: str | None = None

    def as_selector(self) -> dict[str, dict[str, Any]]:
        selected: dict[str, dict[str, Any]] = {
            "exerciseHeartRateAvg": {
                "type": "integer",
                "description": "可信运动期间平均心率，不表示当前或静息心率",
                "sampleValue": self.average_bpm,
            }
        }
        if self.updated_at is not None:
            selected["updatedAt"] = _field(self.updated_at, "可信运动数据更新时间")
        return selected


@dataclass(frozen=True)
class SleepOverviewFacts:
    duration_text: str
    duration: DurationSegments
    score: int | float | None = None
    status: str | None = None
    fall_asleep_time: str | None = None
    wakeup_time: str | None = None

    @property
    def explicitly_insufficient(self) -> bool:
        if self.status is None:
            return False
        normalized, compact = _normalized_query(self.status)
        return _contains_query_term(
            normalized,
            compact,
            _EXPLICIT_INSUFFICIENT_SLEEP_STATUS_TERMS,
        )

    @property
    def has_schedule(self) -> bool:
        return self.fall_asleep_time is not None and self.wakeup_time is not None

    def as_selector(self) -> dict[str, dict[str, Any]]:
        selected = {
            "nightSleepDurationText": _field(
                self.duration_text,
                "可信夜间睡眠总时长原文",
            ),
            "sleepDurationPrimaryValueText": _field(
                self.duration.primary_value,
                "从可信夜间睡眠总时长无损解析的主数值",
            ),
            "sleepDurationPrimaryUnitText": _field(
                self.duration.primary_unit,
                "从可信夜间睡眠总时长无损解析的主单位",
            ),
        }
        if self.duration.secondary_value is not None:
            selected["sleepDurationSecondaryValueText"] = _field(
                self.duration.secondary_value,
                "从可信夜间睡眠总时长无损解析的次数值",
            )
            selected["sleepDurationSecondaryUnitText"] = _field(
                self.duration.secondary_unit or "",
                "从可信夜间睡眠总时长无损解析的次单位",
            )
        if self.status is not None:
            selected["sleepStatus"] = _field(self.status, "可信睡眠状态原文")
        if self.score is not None:
            selected["sleepScore"] = {
                "type": "integer" if isinstance(self.score, int) else "number",
                "description": "可信睡眠得分",
                "sampleValue": self.score,
            }
        if self.fall_asleep_time is not None:
            selected["fallAsleepTimeText"] = _field(
                self.fall_asleep_time,
                "可信入睡时刻原文",
            )
        if self.wakeup_time is not None:
            selected["wakeupTimeText"] = _field(
                self.wakeup_time,
                "可信醒来时刻原文",
            )
        return selected


_UNSUPPORTED_WEATHER_QUERY_TERMS = (
    "hourly",
    "hour by hour",
    "逐小时",
    "小时预报",
    "分时天气",
    "sunrise",
    "sunset",
    "日出",
    "日落",
    "barometric pressure",
    "air pressure",
    "气压",
    "visibility",
    "能见度",
    "aqi",
    "空气质量指数",
    # Note: Comfort-related terms (feels-like temp, humidity, wind, UV, cold level, alerts)
    # are removed from unsupported list to allow common weather queries through.
    # These queries will fall back to original generation if template can't cover them.
    # "feels like", "apparent temperature", "体感温度",
    # "humidity", "湿度",
    # "wind speed", "wind direction", "wind level", "风速", "风向", "风力",
    # "ultraviolet", "uv index", "紫外线",
    # "weather alert", "weather warning", "severe weather", "天气预警", "预警信息", "极端天气",
    # "cold index", "感冒指数",
    "rain probability",
    "precipitation probability",
    "降雨概率",
    "降水概率",
    "未来天气",
    "未来预报",
    "多日预报",
)

_DATE_EVENT_QUERY_TERMS = (
    "appointment",
    "calendar event",
    "event",
    "meeting",
    "schedule",
    "agenda",
    "会议",
    "日程",
    "事项",
    "行程",
    "活动安排",
)
_EXPLICIT_EVENT_DATE_QUERY_TERMS = (
    "date",
    "day of week",
    "weekday",
    "which day",
    "日期",
    "哪天",
    "几号",
    "星期",
    "周几",
)
_UNSUPPORTED_DATE_QUERY_TERMS = (
    "current date",
    "today's date",
    "what date is it",
    "what day is it",
    "today",
    "tomorrow",
    "yesterday",
    "this week",
    "next week",
    "last week",
    "relative date",
    "lunar",
    "festival",
    "holiday",
    "month",
    "year",
    "今天",
    "今日",
    "明天",
    "明日",
    "后天",
    "昨天",
    "昨日",
    "本周",
    "这周",
    "下周",
    "上周",
    "相对日期",
    "农历",
    "阴历",
    "节日",
    "节气",
    "月份",
    "几月",
    "哪月",
    "年份",
    "年度",
    "今年",
    "明年",
    "去年",
)

_SCHEDULE_QUERY_TERMS = (
    "appointment",
    "calendar event",
    "event",
    "meeting",
    "schedule",
    "next event",
    "next meeting",
    "日程",
    "会议",
    "下一项",
    "下一场",
    "预约",
    "入会",
)
_SCHEDULE_LOCATION_QUERY_TERMS = (
    "meeting room",
    "location",
    "where",
    "地点",
    "会议室",
    "在哪里",
)
_SCHEDULE_DATE_ONLY_QUERY_TERMS = (
    "date",
    "day of week",
    "weekday",
    "which day",
    "tomorrow",
    "month",
    "year",
    "lunar",
    "days until",
    "日期",
    "哪天",
    "几号",
    "星期几",
    "周几",
    "明天吗",
    "月份",
    "哪一年",
    "农历",
    "还有几天",
    "距离现在",
)
_UNSUPPORTED_SCHEDULE_QUERY_TERMS = (
    "agenda list",
    "all agenda",
    "all events",
    "multiple events",
    "today's agenda",
    "future events",
    "议程列表",
    "日程列表",
    "全部议程",
    "所有议程",
    "全部日程",
    "所有日程",
    "多条日程",
    "多场会议",
    "未来日程",
    "实时状态",
    "会议状态",
    "正在进行",
    "即将开始",
    "已经结束",
    "已结束",
    "starting soon",
    "ongoing",
    "ended",
    "minute countdown",
    "minutes until",
    "分钟倒计时",
    "还有几分钟",
    "几分钟后",
    "meeting id",
    "meeting number",
    "会议号",
    "备注",
    "邀请人",
    "发起人",
    "sender name",
    "can join",
    "是否可加入",
    "能否加入",
    "可加入状态",
    "todo",
    "task list",
    "memo",
    "待办",
    "任务",
    "备忘录",
)
_SCHEDULE_JOIN_ACTION_QUERY_TERMS = (
    "join meeting",
    "enter meeting",
    "return to meeting",
    "view meeting",
    "open meeting",
    "view calendar event",
    "view schedule",
    "加入会议",
    "入会",
    "返回会议",
    "查看会议",
    "打开会议",
    "查看日程",
    "打开日程",
)
_SCHEDULE_FOCUS_ACTION_QUERY_TERMS = (
    "enable focus",
    "start focus",
    "turn on focus",
    "开启专注",
    "打开专注",
    "进入专注",
)
_SCHEDULE_JOIN_ACTION_CANDIDATE_TERMS = (
    "enter meeting",
    "join meeting",
    "return meeting",
    "view meeting",
    "view calendar event",
    "calendar event",
    "加入会议",
    "入会",
    "返回会议",
    "查看会议",
    "查看日程",
)
_SCHEDULE_FOCUS_ACTION_CANDIDATE_TERMS = (
    "focus",
    "dnd",
    "do not disturb",
    "专注",
    "勿扰",
)
_SCHEDULE_NON_DATE_SUMMARY_TERMS = (
    "title",
    "time",
    "location",
    "summary",
    "schedule",
    "next event",
    "next meeting",
    "标题",
    "时间",
    "地点",
    "摘要",
    "日程",
    "下一项",
    "下一场",
    *_SCHEDULE_JOIN_ACTION_QUERY_TERMS,
    *_SCHEDULE_FOCUS_ACTION_QUERY_TERMS,
)
_SCHEDULE_ASSET_REQUEST_TERMS = {
    "source": ("source icon", "calendar icon", "来源图标", "日历图标", "日程图标"),
    "time": ("time icon", "clock icon", "时间图标", "时钟图标"),
    "location": ("location icon", "place icon", "地点图标", "位置图标"),
    "action": ("action icon", "button icon", "动作图标", "操作图标", "按钮图标"),
}
_SCHEDULE_ASSET_EXPECTED_TAGS = {
    "source": {"calendar", "schedule"},
    "time": {"time"},
    "location": {"location"},
}
_SCHEDULE_ASSET_TAG_TERMS = {
    "calendar": ("calendar", "日历"),
    "schedule": ("schedule", "日程"),
    "meeting": ("meeting", "conference", "会议", "入会"),
    "time": ("time", "clock", "时间", "时钟"),
    "location": ("location", "place", "room", "地点", "位置", "会议室"),
    "focus": ("focus", "dnd", "专注", "勿扰"),
}

_ACTIVITY_STEPS_QUERY_TERMS = (
    "daily steps",
    "step count",
    "steps",
    "walking steps",
    "今日步数",
    "每日步数",
    "当天步数",
    "步数",
    "走了多少步",
)
_ACTIVITY_CALORIES_QUERY_TERMS = (
    "daily calories",
    "activity calories",
    "calories burned",
    "今日热量",
    "活动热量",
    "消耗热量",
    "卡路里",
)
_ACTIVITY_DISTANCE_QUERY_TERMS = (
    "daily distance",
    "walking distance",
    "activity distance",
    "今日距离",
    "活动距离",
    "步行距离",
    "走了多远",
)
_ACTIVITY_SUMMARY_QUERY_TERMS = (
    "daily activity summary",
    "activity overview",
    "activity summary",
    "health overview",
    "health summary",
    "每日活动摘要",
    "今日活动",
    "活动概览",
    "活动摘要",
    "健康概览",
    "健康摘要",
)
_UNSUPPORTED_ACTIVITY_QUERY_TERMS = (
    "step goal",
    "target steps",
    "goal ratio",
    "completion rate",
    "goal ring",
    "activity ring",
    "progress ring",
    "progress bar",
    "active minutes",
    "exercise minutes",
    "standing hours",
    "activity trend",
    "activity history",
    "目标步数",
    "步数目标",
    "达成率",
    "完成率",
    "目标环",
    "活动环",
    "进度环",
    "进度条",
    "活动分钟",
    "锻炼分钟",
    "站立小时",
    "活动趋势",
    "活动历史",
    "单独热量",
    "仅热量",
    "单独锻炼",
    "仅锻炼",
)

_WORKOUT_LATEST_QUERY_TERMS = (
    "latest workout",
    "recent workout",
    "last workout",
    "workout summary",
    "exercise record",
    "recent training",
    "最近运动",
    "最近锻炼",
    "上次运动",
    "运动记录",
    "锻炼记录",
    "最近训练",
    "运动时长",
    "锻炼时长",
    "训练时长",
    "运动热量",
    "锻炼热量",
    "训练热量",
    "热量消耗",
    "workout duration",
    "exercise duration",
    "training duration",
    "calories burned",
    "calorie burn",
)
_WORKOUT_GENERIC_QUERY_TERMS = (
    "workout",
    "exercise",
    "training",
    "运动",
    "锻炼",
    "训练",
    "健身",
)
_COUNTDOWN_QUERY_TERMS = (
    "countdown",
    "days until",
    "remaining days",
    "days left",
    "倒计时",
    "倒数",
    "还剩",
    "剩余天数",
    "还有几天",
    "多少天",
)
_UNSUPPORTED_WORKOUT_QUERY_TERMS = (
    "live workout",
    "real-time workout",
    "ongoing workout",
    "planned workout status",
    "workout distance",
    "pace",
    "route",
    "heart rate zone",
    "race name",
    "event name",
    "training plan",
    "total mileage",
    "completion rate",
    "workout progress",
    "实时运动",
    "实时锻炼",
    "运动中",
    "正在运动",
    "计划状态",
    "运动距离",
    "单次距离",
    "配速",
    "轨迹",
    "心率区间",
    "赛事名称",
    "比赛名称",
    "训练计划",
    "总里程",
    "完成率",
    "运动进度",
)

_HEART_RATE_AVERAGE_QUERY_TERMS = (
    "average exercise heart rate",
    "average workout heart rate",
    "exercise heart rate average",
    "workout average bpm",
    "运动平均心率",
    "锻炼平均心率",
    "运动期间平均心率",
    "平均运动心率",
)
_HEART_RATE_UPDATED_AT_QUERY_TERMS = (
    "heart rate update time",
    "heart rate updated at",
    "when updated",
    "心率更新时间",
    "心率更新于",
    "何时更新",
    "更新时间",
)
_UNSUPPORTED_HEART_RATE_QUERY_TERMS = (
    "current heart rate",
    "live heart rate",
    "real-time heart rate",
    "resting heart rate",
    "heart rate alert",
    "heart rate risk",
    "heart rate zone",
    "heart rate trend",
    "heart rate waveform",
    "heart rate chart",
    "maximum heart rate",
    "minimum heart rate",
    "max heart rate",
    "min heart rate",
    "当前心率",
    "实时心率",
    "静息心率",
    "心率异常",
    "心率风险",
    "心率区间",
    "心率趋势",
    "心率波形",
    "心率曲线",
    "最大心率",
    "最低心率",
)

_SLEEP_QUERY_TERMS = (
    "sleep",
    "sleep duration",
    "night sleep",
    "bedtime",
    "wake up",
    "睡眠",
    "睡了多久",
    "睡眠时长",
    "入睡",
    "醒来",
    "起床",
    "作息",
)
_SLEEP_SCHEDULE_QUERY_TERMS = (
    "bedtime",
    "fall asleep time",
    "wake up time",
    "sleep schedule",
    "sleep and wake",
    "入睡时间",
    "醒来时间",
    "起床时间",
    "作息时间",
    "几点睡",
    "几点醒",
    "几点起",
)
_SLEEP_STATUS_QUERY_TERMS = (
    "sleep status",
    "sleep state",
    "睡眠状态",
    "睡得怎么样",
)
_SLEEP_INSUFFICIENT_QUERY_TERMS = (
    "insufficient sleep",
    "not enough sleep",
    "lack of sleep",
    "sleep deprived",
    "睡眠不足",
    "睡不够",
    "缺觉",
)
_EXPLICIT_INSUFFICIENT_SLEEP_STATUS_TERMS = (
    "insufficient",
    "not enough",
    "lack of sleep",
    "sleep deprived",
    "不足",
    "睡不够",
    "缺觉",
)
_EXTENDED_SLEEP_QUERY_TERMS = (
    "deep sleep",
    "light sleep",
    "rem sleep",
    "rapid eye movement",
    "nap",
    "sleep goal",
    "goal completion",
    "completion rate",
    "sleep trend",
    "sleep history",
    "sleep advice",
    "sleep recommendation",
    "sleep stage",
    "深睡",
    "浅睡",
    "快速眼动",
    "午睡",
    "小睡",
    "睡眠目标",
    "目标完成率",
    "达成率",
    "睡眠趋势",
    "睡眠历史",
    "睡眠建议",
    "改善建议",
    "睡眠阶段",
    "分期",
)
_SLEEP_SCORE_QUERY_TERMS = (
    "sleep score",
    "睡眠得分",
    "睡眠评分",
)
_BATTERY_QUERY_TERMS = (
    "battery",
    "battery level",
    "battery percentage",
    "battery status",
    "state of charge",
    "soc",
    "charging status",
    "is charging",
    "low battery",
    "battery saver",
    "power saving",
    "电池",
    "电量",
    "电量百分比",
    "电池状态",
    "剩余电量",
    "充电状态",
    "是否充电",
    "低电",
    "省电",
    "节电",
)
_UNSUPPORTED_BATTERY_ONLY_QUERY_TERMS = (
    "battery health",
    "battery temperature",
    "voltage",
    "current",
    "charger type",
    "power adapter",
    "remaining runtime",
    "battery runtime",
    "time remaining",
    "time to full",
    "full charge time",
    "预计充满",
    "充满时间",
    "剩余续航",
    "续航时间",
    "健康度",
    "电池健康",
    "电池温度",
    "电压",
    "电流",
    "充电器类型",
    "适配器类型",
)
_BATTERY_EXTERNAL_DEVICE_TERMS = (
    "earbud",
    "earphone",
    "headphone",
    "bluetooth device",
    "watch battery",
    "peripheral battery",
    "耳机",
    "蓝牙设备",
    "手表电量",
    "外设电量",
)
_BATTERY_PHONE_TERMS = ("phone", "handset", "手机", "本机")
_BATTERY_POWER_SAVING_QUERY_TERMS = (
    "battery saver",
    "power saving",
    "low power mode",
    "save power",
    "省电",
    "节电",
    "低电量模式",
)
_BATTERY_ASSET_TAG_TERMS = {
    "battery": ("battery", "电池", "电量"),
    "power": ("power", "energy", "电源", "电力"),
    "phone": ("phone", "smartphone", "手机", "本机"),
    "power-saving": (
        "battery saver",
        "power saving",
        "low power",
        "save power",
        "powersaving",
        "leaf",
        "省电",
        "节电",
        "叶子",
    ),
}

_BLUETOOTH_EARPHONE_QUERY_TERMS = (
    "bluetooth earbud",
    "bluetooth earphone",
    "bluetooth headphone",
    "wireless earbud",
    "wireless earphone",
    "earbud",
    "earphone",
    "headphone",
    "蓝牙耳机",
    "无线耳机",
    "耳塞",
    "耳机",
    "左右耳",
    "双耳",
)
_UNSUPPORTED_BLUETOOTH_DEVICE_QUERY_TERMS = (
    "bluetooth watch",
    "smart watch",
    "bluetooth car",
    "car audio",
    "bluetooth keyboard",
    "bluetooth mouse",
    "bluetooth speaker",
    "game controller",
    "智能手表",
    "蓝牙手表",
    "车机",
    "车载蓝牙",
    "蓝牙键盘",
    "蓝牙鼠标",
    "蓝牙音箱",
    "游戏手柄",
)
_UNSUPPORTED_BLUETOOTH_MEDIA_QUERY_TERMS = (
    "play pause",
    "pause music",
    "previous track",
    "next track",
    "current track",
    "song title",
    "playback progress",
    "播放暂停",
    "暂停音乐",
    "上一首",
    "下一首",
    "当前曲目",
    "歌曲名称",
    "播放进度",
)
_BLUETOOTH_LEFT_QUERY_TERMS = ("left ear", "left earbud", "左耳")
_BLUETOOTH_RIGHT_QUERY_TERMS = ("right ear", "right earbud", "右耳")
_BLUETOOTH_BOTH_EARS_QUERY_TERMS = ("both earbuds", "both ears", "双耳", "左右耳")
_BLUETOOTH_CASE_QUERY_TERMS = ("charging case", "earbud case", "case battery", "充电盒", "耳机盒")
_BLUETOOTH_CONNECTION_QUERY_TERMS = (
    "connection status",
    "connected",
    "connect",
    "连接状态",
    "已连接",
    "连上",
    "连没连",
    "是否连接",
)
_BLUETOOTH_BATTERY_QUERY_TERMS = ("battery", "电量", "剩余电")
_UNSUPPORTED_RESOURCE_USAGE_QUERY_TERMS = (
    "storage",
    "disk",
    "rom usage",
    "disk usage",
    "存储",
    "磁盘",
    "硬盘",
    "rom占用",
    "cache",
    "缓存",
    "process detail",
    "process list",
    "process ranking",
    "进程明细",
    "进程列表",
    "进程排行",
    "cpu",
    "gpu",
    "swap",
    "交换分区",
    "交换空间",
    "trend",
    "history curve",
    "historical curve",
    "趋势",
    "历史曲线",
    "历史趋势",
)
_FREE_MEMORY_QUERY_TERMS = (
    "freememtext",
    "free memory",
    "completely free memory",
    "完全空闲内存",
    "空闲内存",
)
_SUPPORTED_RESOURCE_USAGE_QUERY_TERMS = (
    "usagepercent",
    "availablememtext",
    "totalmemtext",
    "memory usage",
    "memory utilization",
    "available memory",
    "total memory",
    "内存占用",
    "内存使用",
    "可用内存",
    "总内存",
    "内存清理",
    "清理内存",
    "释放内存",
    "内存",
)
_APP_USAGE_DURATION_QUERY_TERMS = (
    "app usage duration",
    "usage duration",
    "usage time",
    "time spent",
    "how long",
    "使用时长",
    "使用时间",
    "用了多久",
    "用多久",
    "使用多久",
)
_UNSUPPORTED_APP_USAGE_QUERY_TERMS = (
    "total screen time",
    "overall screen time",
    "all apps",
    "multiple apps",
    "top apps",
    "app ranking",
    "screen time limit",
    "daily limit",
    "remaining time",
    "time remaining",
    "usage ratio",
    "usage percentage",
    "progress",
    "trend",
    "history",
    "historical",
    "category summary",
    "category breakdown",
    "总屏幕时间",
    "屏幕总时长",
    "全部应用",
    "所有应用",
    "多个应用",
    "多应用",
    "应用排行",
    "排名",
    "排行榜",
    "每日限额",
    "使用限额",
    "时长限额",
    "超限",
    "超时",
    "已超",
    "剩余可用时长",
    "剩余时长",
    "还可使用",
    "比例",
    "百分比",
    "进度",
    "趋势",
    "历史",
    "分类汇总",
    "分类统计",
)
_APP_USAGE_PLACEHOLDER_NAMES = frozenset(
    {
        "app",
        "application",
        "exampleapp",
        "sampleapp",
        "应用",
        "示例应用",
    }
)


def apply_content_selectors(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> TaskSpec:
    """Add trusted display aliases without changing provider or CardSpec contracts."""
    schema = deepcopy(task_spec.dataModelSchema)
    selectors: dict[str, dict[str, dict[str, Any]]] = {}

    if "ViewWeather" in capability_ids:
        weather_facts = extract_weather_overview_facts(schema)
        if weather_facts is not None:
            weather = weather_facts.as_selector()
            selectors["weather"] = weather
            updated_at = _first_trusted_string(schema, "updatedAt")
            if updated_at is not None:
                weather["updatedAt"] = _field(updated_at, "可信天气更新时间")
                selectors["location"] = {
                    "label": _field("天气位置", "可信天气查询位置标签"),
                    "city": weather["city"],
                    "updatedText": weather["updatedAt"],
                }

    if "GetCalendarEvents" in capability_ids:
        schedule, date = _calendar_selectors(schema)
        if schedule:
            selectors["schedule"] = schedule
        if date:
            selectors["date"] = date

    if "GetPhoneBatteryInfo" in capability_ids:
        battery_facts = extract_battery_overview_facts(schema)
        if battery_facts is not None:
            selectors["battery"] = battery_facts.as_selector()

    if "GetAppUsageDuration" in capability_ids:
        app_usage_facts = extract_app_usage_overview_facts(schema)
        if app_usage_facts is not None:
            selectors["appUsage"] = app_usage_facts.as_selector()

    if "GetHealthAndSportSummary" in capability_ids:
        sleep_facts = extract_sleep_overview_facts(schema)
        if sleep_facts is not None:
            selectors["sleep"] = sleep_facts.as_selector()

    if not selectors:
        return task_spec
    data = schema.setdefault("data", {})
    if not isinstance(data, dict):
        return task_spec
    data["_advancedSelectors"] = selectors
    return task_spec.model_copy(update={"dataModelSchema": schema})


def project_content_component_facts(
    task_spec: TaskSpec,
    capability_ids: set[str],
    component_ids: tuple[str, ...],
) -> TaskSpec:
    """Narrow the second-layer contract to selected component display facts.

    The first-layer scope planner still sees the complete provider schema. The
    mixed-body model receives only fields that the selected strict content
    component can render, so transport metadata does not become UI ``mustKeep``.
    """
    schema = task_spec.dataModelSchema
    selector_root = schema.get("data", {})
    selectors = (
        selector_root.get("_advancedSelectors", {}) if isinstance(selector_root, dict) else {}
    )
    projected: dict[str, dict[str, Any]] = {}
    for component_id in component_ids:
        selected: dict[str, Any] = {}
        selector_spec = _SELECTOR_COMPONENT_FIELDS.get(component_id)
        if component_id == "ActivityOverview":
            activity_facts = extract_activity_overview_facts(schema)
            if activity_facts is not None:
                selected = activity_facts.as_selector()
                variants = (
                    relaxed_activity_overview_variants(task_spec, capability_ids)
                    if advanced_component_data_admission_is_relaxed()
                    else activity_overview_variants(task_spec, capability_ids)
                )
                if "dailySummary" not in variants:
                    selected = {"dailySteps": selected["dailySteps"]}
        elif component_id == "WorkoutOverview":
            workout_variants = (
                relaxed_workout_overview_variants(task_spec, capability_ids)
                if advanced_component_data_admission_is_relaxed()
                else workout_overview_variants(task_spec, capability_ids)
            )
            if "latest" in workout_variants:
                latest_facts = extract_workout_latest_facts(schema)
                if latest_facts is not None:
                    selected.update(latest_facts.as_selector())
        elif component_id == "CountdownOverview":
            countdown_facts = extract_countdown_overview_facts(schema)
            if countdown_facts is not None:
                selected = countdown_facts.as_selector()
        elif component_id == "HeartRateOverview":
            heart_rate_facts = extract_heart_rate_overview_facts(schema)
            if heart_rate_facts is not None:
                selected = heart_rate_facts.as_selector()
        elif component_id == "SleepOverview":
            sleep_facts = extract_sleep_overview_facts(schema)
            if sleep_facts is not None:
                selected = sleep_facts.as_selector()
        elif component_id == "BatteryOverview":
            battery_facts = extract_battery_overview_facts(schema)
            if battery_facts is not None:
                selected = battery_facts.as_selector()
        elif component_id == "BluetoothDeviceOverview":
            bluetooth_facts = extract_bluetooth_device_overview_facts(schema)
            if bluetooth_facts is not None:
                selected = bluetooth_facts.as_selector()
        elif component_id == "AppUsageOverview":
            app_usage_facts = extract_app_usage_overview_facts(schema)
            if app_usage_facts is not None:
                selected = app_usage_facts.as_selector()
        elif component_id == "ScheduleOverview":
            schedule_facts = extract_schedule_overview_facts(schema)
            if schedule_facts is not None:
                selected = schedule_facts.as_selector()
        elif component_id == "DateOverview":
            date_facts = extract_date_overview_facts(schema)
            if date_facts is not None:
                selected = date_facts.as_selector()
        elif component_id == "ResourceUsageOverview":
            resource_facts = extract_resource_usage_overview_facts(schema)
            if resource_facts is not None:
                selected = resource_facts.as_selector()
        elif selector_spec is not None:
            selector_name, field_names = selector_spec
            selector = selectors.get(selector_name) if isinstance(selectors, dict) else None
            selected = _select_direct_fields(selector, field_names)
            if not selected:
                fallback_fields = _SELECTOR_FALLBACK_FIELDS[component_id]
                source = _best_source_object(schema, fallback_fields)
                selected = {
                    field_name: deepcopy(field)
                    for field_name in fallback_fields
                    if (field := _first_field(source, field_name)) is not None
                }
        else:
            field_names = _provider_fields(component_id, capability_ids)
            source = _best_source_object(schema, field_names)
            selected = {
                field_name: deepcopy(field)
                for field_name in field_names
                if (field := _first_field(source, field_name)) is not None
            }
        if selected:
            projected[component_id] = selected
    if not projected:
        raise ValueError("Selected advanced components have no renderable provider facts")
    return task_spec.model_copy(update={"dataModelSchema": {"data": projected}})


def _provider_fields(component_id: str, capability_ids: set[str]) -> tuple[str, ...]:
    if component_id != "WorkoutOverview":
        return _PROVIDER_COMPONENT_FIELDS.get(component_id, ())
    fields: list[str] = []
    if "GetHealthAndSportSummary" in capability_ids:
        fields.extend(
            (
                "exerciseTypeName",
                "exerciseCalorieText",
                "exerciseDurationText",
                "exerciseEndTimeText",
            )
        )
    return tuple(fields)


def _select_direct_fields(value: Any, field_names: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        field_name: deepcopy(value[field_name]) for field_name in field_names if field_name in value
    }


def _best_source_object(value: Any, field_names: tuple[str, ...]) -> Any:
    if not field_names:
        return {}
    wanted = set(field_names)
    best: tuple[int, int, dict[str, Any]] | None = None

    def visit(current: Any, depth: int) -> None:
        nonlocal best
        if isinstance(current, dict):
            names = _descendant_field_names(current)
            candidate = (len(wanted & names), depth, current)
            if candidate[0] and (best is None or candidate[:2] > best[:2]):
                best = candidate
            for child in current.values():
                visit(child, depth + 1)
        elif isinstance(current, list):
            for child in current:
                visit(child, depth + 1)

    visit(value, 0)
    return best[2] if best is not None else {}


def _descendant_field_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            item for child in value.values() for item in _descendant_field_names(child)
        }
    if isinstance(value, list):
        return {item for child in value for item in _descendant_field_names(child)}
    return set()


def _first_field(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        if field_name in value:
            return value[field_name]
        for child in value.values():
            selected = _first_field(child, field_name)
            if selected is not None:
                return selected
    elif isinstance(value, list):
        for child in value:
            selected = _first_field(child, field_name)
            if selected is not None:
                return selected
    return None


def activity_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Expose ActivityOverview only when query intent and trusted facts agree."""
    return bool(activity_overview_variants(task_spec, capability_ids))


def advanced_component_data_admission_is_relaxed() -> bool:
    """Temporarily relax adaptation gates only for explicitly enabled batch runs."""
    settings = get_settings()
    return bool(
        _BATCH_DATA_ADMISSION_ENABLED.get()
        and getattr(settings, "enable_widget_batch_recording", False)
        and getattr(
            settings,
            "enable_advanced_component_data_admission_bypass_for_batch",
            False,
        )
    )


@contextmanager
def advanced_component_batch_data_admission(enabled: bool):
    """Scope the temporary admission relaxation to one explicit batch request."""
    token = _BATCH_DATA_ADMISSION_ENABLED.set(enabled)
    try:
        yield
    finally:
        _BATCH_DATA_ADMISSION_ENABLED.reset(token)


def relaxed_activity_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    """Return renderable variants without applying query-intent admission."""
    if "GetHealthAndSportSummary" not in capability_ids:
        return ()
    facts = extract_activity_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return ()
    return ("steps", "dailySummary") if facts.has_daily_summary else ("steps",)


def activity_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    if "GetHealthAndSportSummary" not in capability_ids:
        return ()
    normalized, compact = _normalized_query(task_spec.userQuery)
    if _contains_query_term(normalized, compact, _UNSUPPORTED_ACTIVITY_QUERY_TERMS):
        return ()
    facts = extract_activity_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return ()
    requests_steps = _contains_query_term(
        normalized,
        compact,
        _ACTIVITY_STEPS_QUERY_TERMS,
    )
    requests_calories = _contains_query_term(
        normalized,
        compact,
        _ACTIVITY_CALORIES_QUERY_TERMS,
    )
    requests_distance = _contains_query_term(
        normalized,
        compact,
        _ACTIVITY_DISTANCE_QUERY_TERMS,
    )
    requests_summary = _contains_query_term(
        normalized,
        compact,
        _ACTIVITY_SUMMARY_QUERY_TERMS,
    )
    if not any((requests_steps, requests_calories, requests_distance, requests_summary)):
        return ()
    if requests_calories and facts.calories_text is None:
        return ()
    if requests_distance and facts.distance_text is None:
        return ()
    if requests_summary or requests_calories or requests_distance:
        return ("dailySummary",) if facts.has_daily_summary else ()
    return ("steps",) if requests_steps else ()


def workout_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Expose WorkoutOverview only for a fact-backed enabled variant."""
    return bool(workout_overview_variants(task_spec, capability_ids))


def relaxed_workout_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    """Return fact-backed Workout variants without applying query-intent admission."""
    variants: list[str] = []
    if (
        "GetHealthAndSportSummary" in capability_ids
        and extract_workout_latest_facts(task_spec.dataModelSchema) is not None
    ):
        variants.append("latest")
    return tuple(variants)


def workout_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    normalized, compact = _normalized_query(task_spec.userQuery)
    if _contains_query_term(normalized, compact, _UNSUPPORTED_WORKOUT_QUERY_TERMS):
        return ()
    requests_latest = _contains_query_term(
        normalized,
        compact,
        _WORKOUT_LATEST_QUERY_TERMS,
    )
    if not requests_latest:
        requests_latest = _contains_query_term(
            normalized,
            compact,
            _WORKOUT_GENERIC_QUERY_TERMS,
        )
    facts = extract_workout_latest_facts(task_spec.dataModelSchema)
    if not requests_latest and facts is not None:
        requests_latest = _contains_query_term(
            normalized,
            compact,
            (facts.exercise_type_name,),
        )
    variants: list[str] = []
    if requests_latest and "GetHealthAndSportSummary" in capability_ids:
        if facts is not None:
            variants.append("latest")
    return tuple(variants)


def countdown_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    return bool(countdown_overview_variants(task_spec, capability_ids))


def relaxed_countdown_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    if (
        "GetCountdownDays" in capability_ids
        and extract_countdown_overview_facts(task_spec.dataModelSchema) is not None
    ):
        return ("countdown",)
    return ()


def countdown_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    normalized, compact = _normalized_query(task_spec.userQuery)
    if not _contains_query_term(normalized, compact, _COUNTDOWN_QUERY_TERMS):
        return ()
    return relaxed_countdown_overview_variants(task_spec, capability_ids)


def heart_rate_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Accept only a positive trusted exercise-average heart-rate request."""
    if "GetHealthAndSportSummary" not in capability_ids:
        return False
    normalized, compact = _normalized_query(task_spec.userQuery)
    if _contains_query_term(normalized, compact, _UNSUPPORTED_HEART_RATE_QUERY_TERMS):
        return False
    if not _contains_query_term(normalized, compact, _HEART_RATE_AVERAGE_QUERY_TERMS):
        return False
    facts = extract_heart_rate_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return False
    requests_updated_at = _contains_query_term(
        normalized,
        compact,
        _HEART_RATE_UPDATED_AT_QUERY_TERMS,
    )
    return not requests_updated_at or facts.updated_at is not None


def sleep_overview_has_trusted_data(task_spec: TaskSpec) -> bool:
    """Require only the losslessly renderable night-duration admission fact."""
    return extract_sleep_overview_facts(task_spec.dataModelSchema) is not None


def sleep_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Expose a duration-backed SleepOverview for broad sleep-themed batch tests."""
    return bool(sleep_overview_variants(task_spec, capability_ids))


def sleep_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    if "GetHealthAndSportSummary" not in capability_ids:
        return ()
    normalized, compact = _normalized_query(task_spec.userQuery)
    relaxed = advanced_component_data_admission_is_relaxed()
    requests_extended_projection = _contains_query_term(
        normalized,
        compact,
        _EXTENDED_SLEEP_QUERY_TERMS,
    )
    if requests_extended_projection and not relaxed:
        return ()
    sleep_terms = (*_SLEEP_QUERY_TERMS, *_SLEEP_SCORE_QUERY_TERMS, *_EXTENDED_SLEEP_QUERY_TERMS)
    if not _contains_query_term(normalized, compact, sleep_terms):
        return ()
    facts = extract_sleep_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return ()
    requests_score = _contains_query_term(
        normalized,
        compact,
        _SLEEP_SCORE_QUERY_TERMS,
    )
    if requests_score and facts.score is None:
        return ()
    requests_schedule = _contains_query_term(
        normalized,
        compact,
        _SLEEP_SCHEDULE_QUERY_TERMS,
    )
    requests_status = _contains_query_term(
        normalized,
        compact,
        _SLEEP_STATUS_QUERY_TERMS,
    )
    requests_insufficient = _contains_query_term(
        normalized,
        compact,
        _SLEEP_INSUFFICIENT_QUERY_TERMS,
    )
    if not relaxed:
        if requests_schedule and (task_spec.size != "2x4" or not facts.has_schedule):
            return ()
        if requests_status and facts.status is None:
            return ()
        if requests_insufficient and not facts.explicitly_insufficient:
            return ()
    variants = ["duration"]
    if requests_score:
        variants.append("score")
    if facts.explicitly_insufficient:
        variants.append("insufficient")
    if requests_schedule and task_spec.size == "2x4" and facts.has_schedule:
        variants.append("schedule")
    return tuple(variants)


def battery_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Gate BatteryOverview before exposure and after first-layer selection."""
    if "GetPhoneBatteryInfo" not in capability_ids:
        return False
    if not battery_overview_query_is_supported(task_spec.userQuery):
        return False
    return extract_battery_overview_facts(task_spec.dataModelSchema) is not None


def bluetooth_device_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Expose only a fact-backed Bluetooth earphone overview."""
    return bool(bluetooth_device_overview_variants(task_spec, capability_ids))


def bluetooth_device_overview_variants(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> tuple[str, ...]:
    if "GetEarphoneInfo" not in capability_ids:
        return ()
    normalized, compact = _normalized_query(task_spec.userQuery)
    if not _contains_query_term(normalized, compact, _BLUETOOTH_EARPHONE_QUERY_TERMS):
        return ()
    if _contains_query_term(normalized, compact, _UNSUPPORTED_BLUETOOTH_DEVICE_QUERY_TERMS):
        return ()
    if _contains_query_term(normalized, compact, _UNSUPPORTED_BLUETOOTH_MEDIA_QUERY_TERMS):
        return ()
    facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return ()
    requests_left = _contains_query_term(normalized, compact, _BLUETOOTH_LEFT_QUERY_TERMS)
    requests_right = _contains_query_term(normalized, compact, _BLUETOOTH_RIGHT_QUERY_TERMS)
    requests_both = _contains_query_term(normalized, compact, _BLUETOOTH_BOTH_EARS_QUERY_TERMS)
    requests_case = _contains_query_term(normalized, compact, _BLUETOOTH_CASE_QUERY_TERMS)
    if requests_left and facts.left_battery_level is None:
        return ()
    if requests_right and facts.right_battery_level is None:
        return ()
    if requests_both and (
        facts.left_battery_level is None or facts.right_battery_level is None
    ):
        return ()
    if requests_case and facts.case_battery_level is None:
        return ()
    return ("earbuds",)


def bluetooth_device_overview_template_focus(query: str) -> Literal["connection", "case", "all"]:
    """Return the deterministic 2x2 Provider Template focus requested by the user."""
    normalized, compact = _normalized_query(query)
    requests_left = _contains_query_term(normalized, compact, _BLUETOOTH_LEFT_QUERY_TERMS)
    requests_right = _contains_query_term(normalized, compact, _BLUETOOTH_RIGHT_QUERY_TERMS)
    requests_both = _contains_query_term(normalized, compact, _BLUETOOTH_BOTH_EARS_QUERY_TERMS)
    requests_case = _contains_query_term(normalized, compact, _BLUETOOTH_CASE_QUERY_TERMS)
    requests_battery = _contains_query_term(normalized, compact, _BLUETOOTH_BATTERY_QUERY_TERMS)
    requests_connection = _contains_query_term(
        normalized,
        compact,
        _BLUETOOTH_CONNECTION_QUERY_TERMS,
    )
    if requests_connection and not requests_battery:
        return "connection"
    if requests_case and not any((requests_left, requests_right, requests_both)):
        return "case"
    return "all"


def battery_overview_query_is_supported(query: str) -> bool:
    """Accept current phone charge facts, never unsupported detail-only requests."""
    normalized, compact = _normalized_query(query)
    requests_external = _contains_query_term(
        normalized,
        compact,
        _BATTERY_EXTERNAL_DEVICE_TERMS,
    )
    requests_phone = _contains_query_term(normalized, compact, _BATTERY_PHONE_TERMS)
    if requests_external and not requests_phone:
        return False
    requests_supported = _contains_query_term(normalized, compact, _BATTERY_QUERY_TERMS)
    if not requests_supported:
        plain_charging_request = "charging" in normalized or "充电" in compact
        charger_detail_request = "charger" in normalized or "充电器" in compact
        requests_supported = plain_charging_request and not charger_detail_request
    if not requests_supported:
        return False
    requests_unsupported = _contains_query_term(
        normalized,
        compact,
        _UNSUPPORTED_BATTERY_ONLY_QUERY_TERMS,
    )
    explicit_current_state = _contains_query_term(
        normalized,
        compact,
        (
            "battery level",
            "battery percentage",
            "battery status",
            "state of charge",
            "soc",
            "charging status",
            "is charging",
            "low battery",
            "电量",
            "电池状态",
            "充电状态",
            "是否充电",
            "低电",
        ),
    )
    return not requests_unsupported or explicit_current_state


def battery_query_requests_power_saving(query: str) -> bool:
    normalized, compact = _normalized_query(query)
    return _contains_query_term(
        normalized,
        compact,
        _BATTERY_POWER_SAVING_QUERY_TERMS,
    )


def battery_asset_tags(asset: dict[str, Any]) -> set[str]:
    """Normalize TaskSpec asset semantics for battery content and actions."""
    explicit = {
        tag.casefold()
        for tag in asset.get("sceneTags", [])
        if isinstance(tag, str) and tag.strip()
    }
    searchable = " ".join(
        str(asset.get(key, "")) for key in ("id", "src", "description")
    ).casefold()
    inferred = {
        tag
        for tag, terms in _BATTERY_ASSET_TAG_TERMS.items()
        if any(term in searchable for term in terms)
    }
    return explicit | inferred


def weather_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Gate both LLM exposure and post-model acceptance for WeatherOverview."""
    if "ViewWeather" not in capability_ids or not weather_overview_query_is_supported(
        task_spec.userQuery
    ):
        return False
    return extract_weather_overview_facts(task_spec.dataModelSchema) is not None


def weather_overview_query_is_supported(query: str) -> bool:
    normalized = re.sub(r"[\s_./:-]+", " ", query.casefold())
    compact = normalized.replace(" ", "")
    return not any(
        term in normalized or term.replace(" ", "") in compact
        for term in _UNSUPPORTED_WEATHER_QUERY_TERMS
    )


def date_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Gate DateOverview before and after the first-layer LLM call."""
    if "GetCalendarEvents" not in capability_ids:
        return False
    if not date_overview_query_is_supported(task_spec.userQuery, task_spec.size):
        return False
    return extract_date_overview_facts(task_spec.dataModelSchema) is not None


def date_overview_query_is_supported(query: str, size: str) -> bool:
    """Accept only event-date intent, never generic or unsupported date requests."""
    normalized = re.sub(r"[\s_./:-]+", " ", query.casefold())
    compact = normalized.replace(" ", "")
    if any(
        term in normalized or term.replace(" ", "") in compact
        for term in _UNSUPPORTED_DATE_QUERY_TERMS
    ):
        return False
    has_event_context = any(
        term in normalized or term.replace(" ", "") in compact
        for term in _DATE_EVENT_QUERY_TERMS
    )
    explicitly_requests_date = any(
        term in normalized or term.replace(" ", "") in compact
        for term in _EXPLICIT_EVENT_DATE_QUERY_TERMS
    )
    if not has_event_context:
        return False
    return explicitly_requests_date or size == "2x4"


def schedule_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Gate ScheduleOverview before exposure and after the first-layer model."""
    if "GetCalendarEvents" not in capability_ids:
        return False
    facts = extract_schedule_overview_facts(task_spec.dataModelSchema)
    if facts is None or not schedule_overview_query_is_supported(task_spec.userQuery):
        return False
    if schedule_query_requests_location(task_spec.userQuery) and facts.location is None:
        return False
    return _requested_schedule_assets_are_available(task_spec)


def schedule_overview_query_is_supported(query: str) -> bool:
    """Accept the trusted first-event summary and reject unsupported calendar intents."""
    normalized, compact = _normalized_query(query)
    if _contains_query_term(normalized, compact, _UNSUPPORTED_SCHEDULE_QUERY_TERMS):
        return False
    if _contains_query_term(normalized, compact, _SCHEDULE_DATE_ONLY_QUERY_TERMS) and not (
        _contains_query_term(normalized, compact, _SCHEDULE_NON_DATE_SUMMARY_TERMS)
    ):
        return False
    return _contains_query_term(normalized, compact, _SCHEDULE_QUERY_TERMS)


def resource_usage_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Fail closed unless the current memory projection and query are supported."""
    if "GetSystemMemInfo" not in capability_ids:
        return False
    if not resource_usage_overview_query_is_supported(task_spec.userQuery):
        return False
    return extract_resource_usage_overview_facts(task_spec.dataModelSchema) is not None


def resource_usage_overview_query_is_supported(query: str) -> bool:
    normalized, compact = _normalized_query(query)
    if _contains_query_term(normalized, compact, _UNSUPPORTED_RESOURCE_USAGE_QUERY_TERMS):
        return False
    requests_free_memory = _contains_query_term(normalized, compact, _FREE_MEMORY_QUERY_TERMS)
    if not requests_free_memory:
        return True
    supported_without_generic_memory = tuple(
        term for term in _SUPPORTED_RESOURCE_USAGE_QUERY_TERMS if term != "内存"
    )
    return _contains_query_term(normalized, compact, supported_without_generic_memory)


def app_usage_overview_is_eligible(
    task_spec: TaskSpec,
    capability_ids: set[str],
) -> bool:
    """Gate single-app AppUsageOverview before and after first-layer selection."""
    if "GetAppUsageDuration" not in capability_ids:
        return False
    facts = extract_app_usage_overview_facts(task_spec.dataModelSchema)
    if facts is None:
        return False
    return app_usage_overview_query_is_supported(task_spec.userQuery, facts.app_name)


def app_usage_overview_query_is_supported(query: str, app_name: str) -> bool:
    """Accept one named app's duration intent; the Provider defines the current-day window."""
    normalized, compact = _normalized_query(query)
    unsupported = _contains_query_term(
        normalized,
        compact,
        _UNSUPPORTED_APP_USAGE_QUERY_TERMS,
    )
    requests_duration = _contains_query_term(
        normalized,
        compact,
        _APP_USAGE_DURATION_QUERY_TERMS,
    )
    normalized_app = re.sub(r"[\s_./:-]+", "", app_name.casefold())
    if unsupported or not requests_duration:
        return False
    if not normalized_app or normalized_app not in compact:
        if normalized_app not in _APP_USAGE_PLACEHOLDER_NAMES:
            return False
        return not _query_names_multiple_apps_without_reference(compact)
    return not _query_names_multiple_apps(compact, normalized_app)


def _query_names_multiple_apps(compact_query: str, compact_app_name: str) -> bool:
    """Reject a coordinated second app name without interpreting arbitrary nouns."""
    escaped = re.escape(compact_app_name)
    duration = r"(?:使用时长|使用时间|用了多久|用多久|使用多久|usagetime|usageduration)"
    forward = rf"{escaped}(?:和|与|及|、|,|，)[^，,。；;]{{1,20}}{duration}"
    backward = rf"(?:今天|今日|today)[^，,。；;]{{0,20}}(?:和|与|及|、|,|，){escaped}"
    return re.search(forward, compact_query) is not None or re.search(
        backward,
        compact_query,
    ) is not None


def _query_names_multiple_apps_without_reference(compact_query: str) -> bool:
    """Reject an obvious app list when the Provider schema only has a placeholder name."""
    duration = r"(?:使用时长|使用时间|用了多久|用多久|使用多久|usagetime|usageduration)"
    chinese = rf"[^，,。；;]{{1,20}}(?:和|与|及|、)[^，,。；;]{{1,20}}{duration}"
    english = rf"[^,.;]{{1,20}}\band\b[^,.;]{{1,20}}{duration}"
    return re.search(chinese, compact_query) is not None or re.search(
        english,
        compact_query,
    ) is not None


def schedule_query_requests_location(query: str) -> bool:
    normalized, compact = _normalized_query(query)
    return _contains_query_term(normalized, compact, _SCHEDULE_LOCATION_QUERY_TERMS)


def schedule_query_requests_focus(query: str) -> bool:
    return "focus" in _schedule_requested_action_kinds(query)


def approved_schedule_action_ids(task_spec: TaskSpec) -> tuple[str, ...]:
    """Return only query-requested event candidates that close the schedule action loop."""
    requested = _schedule_requested_action_kinds(task_spec.userQuery)
    if not requested:
        return ()
    if task_spec.size == "2x2" and len(requested) > 1:
        return ()
    approved_by_kind: dict[str, list[str]] = {kind: [] for kind in requested}
    for event in task_spec.eventCandidates:
        if not isinstance(event.id, str) or not event.id.strip():
            continue
        searchable = " ".join(
            (
                event.id,
                getattr(event, "displayLabel", None) or "",
                event.call,
                json.dumps(event.args, ensure_ascii=False, sort_keys=True),
            )
        )
        normalized, compact = _normalized_query(searchable)
        candidate_kinds = {
            kind
            for kind, terms in (
                ("schedule", _SCHEDULE_JOIN_ACTION_CANDIDATE_TERMS),
                ("focus", _SCHEDULE_FOCUS_ACTION_CANDIDATE_TERMS),
            )
            if _contains_query_term(normalized, compact, terms)
        }
        for kind in candidate_kinds & set(requested):
            approved_by_kind[kind].append(event.id)
    if any(not approved_by_kind[kind] for kind in requested):
        return ()
    approved = [
        event.id
        for event in task_spec.eventCandidates
        if any(event.id in approved_by_kind[kind] for kind in requested)
    ]
    return tuple(dict.fromkeys(approved))


def approved_schedule_focus_action_ids(task_spec: TaskSpec) -> tuple[str, ...]:
    """Return focus candidates only after the complete action request is closed."""
    approved = set(approved_schedule_action_ids(task_spec))
    if not approved or not schedule_query_requests_focus(task_spec.userQuery):
        return ()
    selected: list[str] = []
    for event in task_spec.eventCandidates:
        if event.id not in approved:
            continue
        searchable = " ".join(
            (
                event.id,
                getattr(event, "displayLabel", None) or "",
                event.call,
                json.dumps(event.args, ensure_ascii=False, sort_keys=True),
            )
        )
        normalized, compact = _normalized_query(searchable)
        if _contains_query_term(
            normalized,
            compact,
            _SCHEDULE_FOCUS_ACTION_CANDIDATE_TERMS,
        ):
            selected.append(event.id)
    return tuple(dict.fromkeys(selected))


def _requested_schedule_assets_are_available(task_spec: TaskSpec) -> bool:
    normalized, compact = _normalized_query(task_spec.userQuery)
    requested = {
        kind
        for kind, terms in _SCHEDULE_ASSET_REQUEST_TERMS.items()
        if kind != "action"
        if _contains_query_term(normalized, compact, terms)
    }
    if not requested:
        return True
    asset_tags = tuple(
        _schedule_asset_tags(asset)
        for asset in task_spec.assetCandidates
        if isinstance(asset, dict) and isinstance(asset.get("src"), str)
    )
    for kind in requested:
        expected = _SCHEDULE_ASSET_EXPECTED_TAGS.get(kind)
        if expected is None or not any(tags & expected for tags in asset_tags):
            return False
    return True


def _schedule_asset_tags(asset: dict[str, Any]) -> set[str]:
    explicit = {
        tag.casefold()
        for tag in asset.get("sceneTags", [])
        if isinstance(tag, str) and tag.strip()
    }
    searchable = " ".join(
        str(asset.get(key, "")) for key in ("id", "src", "description")
    ).casefold()
    inferred = {
        tag
        for tag, terms in _SCHEDULE_ASSET_TAG_TERMS.items()
        if any(term in searchable for term in terms)
    }
    return explicit | inferred


def _schedule_requested_action_kinds(query: str) -> tuple[str, ...]:
    normalized, compact = _normalized_query(query)
    requested = [
        kind
        for kind, terms in (
            ("schedule", _SCHEDULE_JOIN_ACTION_QUERY_TERMS),
            ("focus", _SCHEDULE_FOCUS_ACTION_QUERY_TERMS),
        )
        if _contains_query_term(normalized, compact, terms)
    ]
    return tuple(requested)


def _normalized_query(query: str) -> tuple[str, str]:
    normalized = re.sub(r"[\s_./:-]+", " ", query.casefold())
    return normalized, normalized.replace(" ", "")


def _contains_query_term(
    normalized: str,
    compact: str,
    terms: tuple[str, ...],
) -> bool:
    return any(term in normalized or term.replace(" ", "") in compact for term in terms)


def extract_battery_overview_facts(schema: dict[str, Any]) -> BatteryOverviewFacts | None:
    """Extract one coherent four-field phone battery projection."""
    for candidate in _projected_battery_candidates(schema):
        facts = _battery_facts_from_candidate(candidate)
        if facts is not None:
            return facts
    return None


def extract_bluetooth_device_overview_facts(
    schema: dict[str, Any],
) -> BluetoothDeviceOverviewFacts | None:
    """Extract one coherent earphone entity with at least one valid battery part."""
    data = schema.get("data")
    if isinstance(data, dict):
        projected = data.get("BluetoothDeviceOverview")
        if isinstance(projected, dict):
            facts = _bluetooth_facts_from_candidate(projected)
            if facts is not None:
                return facts
    for candidate in _named_provider_objects(schema, "GetEarphoneInfo"):
        for provider in _dict_nodes(candidate):
            facts = _bluetooth_facts_from_candidate(provider)
            if facts is not None:
                return facts
    required_identity = {"isConnected", "earphoneName"}
    battery_fields = {"leftBatteryLevel", "rightBatteryLevel", "batteryLevel"}
    for candidate in _dict_nodes(schema):
        if not required_identity.issubset(candidate) or not battery_fields.intersection(candidate):
            continue
        facts = _bluetooth_facts_from_candidate(candidate)
        if facts is not None:
            return facts
    return None


def _bluetooth_facts_from_candidate(
    candidate: dict[str, Any],
) -> BluetoothDeviceOverviewFacts | None:
    is_connected = _trusted_boolean(_first_field(candidate, "isConnected"))
    earphone_name = _trusted_string(_first_field(candidate, "earphoneName"))
    if is_connected is None or earphone_name is None:
        return None
    facts = BluetoothDeviceOverviewFacts(
        is_connected=is_connected,
        earphone_name=earphone_name,
        left_battery_level=_trusted_percentage_number(
            _first_field(candidate, "leftBatteryLevel")
        ),
        right_battery_level=_trusted_percentage_number(
            _first_field(candidate, "rightBatteryLevel")
        ),
        case_battery_level=_trusted_percentage_number(_first_field(candidate, "batteryLevel")),
    )
    return facts if facts.battery_part_count else None


def _projected_battery_candidates(schema: dict[str, Any]):
    data = schema.get("data")
    if isinstance(data, dict):
        direct = data.get("BatteryOverview")
        if isinstance(direct, dict):
            yield direct
        selectors = data.get("_advancedSelectors")
        if isinstance(selectors, dict) and isinstance(selectors.get("battery"), dict):
            yield selectors["battery"]
    for candidate in _dict_nodes(schema):
        provider = candidate.get("GetPhoneBatteryInfo")
        if isinstance(provider, dict):
            yield provider
    yield from _direct_field_objects(
        schema.get("data", {}),
        ("batterySOCText", "batteryCapacityLevelDesc", "chargingStatusDesc"),
    )


def _battery_facts_from_candidate(candidate: dict[str, Any]) -> BatteryOverviewFacts | None:
    level_field = _first_field(candidate, "batterySOC")
    level_text_field = _first_field(candidate, "batterySOCText")
    capacity_field = _first_field(candidate, "batteryCapacityLevelDesc")
    charging_field = _first_field(candidate, "chargingStatusDesc")
    level_text = _trusted_string(level_text_field)
    capacity_level = _trusted_string(capacity_field)
    charging_status = _trusted_string(charging_field)
    text_percent = _percentage_number_value(level_text_field)
    if level_text is None or capacity_level is None or charging_status is None:
        return None
    if text_percent is None:
        return None
    if level_field is None:
        level_percent = text_percent
    else:
        level_percent = _trusted_percentage_number(level_field)
        if level_percent is None:
            return None
        if abs(float(level_percent) - float(text_percent)) > 1e-9:
            return None
    return BatteryOverviewFacts(
        level_percent=level_percent,
        level_text=level_text,
        capacity_level=capacity_level,
        charging_status=charging_status,
    )


def _trusted_percentage_number(value: Any) -> int | float | None:
    if not isinstance(value, dict) or value.get("type") not in {"integer", "number"}:
        return None
    sample = value.get("sampleValue")
    if isinstance(sample, bool) or not isinstance(sample, (int, float)):
        return None
    if not 0 <= sample <= 100:
        return None
    number = float(sample)
    return int(number) if number.is_integer() else number


def _percentage_number_value(value: Any) -> int | float | None:
    sample = _sample_value(value)
    if not isinstance(sample, str):
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[%％]\s*", sample)
    if match is None:
        return None
    number = float(match.group(1))
    if not 0.0 <= number <= 100.0:
        return None
    return int(number) if number.is_integer() else number


def _charging_status_is_active(value: str) -> bool:
    normalized, compact = _normalized_query(value)
    if _contains_query_term(
        normalized,
        compact,
        ("not charging", "discharging", "unplugged", "未充电", "未在充电", "放电中"),
    ):
        return False
    return _contains_query_term(
        normalized,
        compact,
        ("charging", "charge in progress", "充电中", "正在充电"),
    )


def extract_resource_usage_overview_facts(
    schema: dict[str, Any],
) -> ResourceUsageOverviewFacts | None:
    """Extract the three trusted fields from one coherent memory provider subtree."""
    data = schema.get("data")
    if isinstance(data, dict):
        projected = data.get("ResourceUsageOverview")
        if isinstance(projected, dict):
            facts = _projected_resource_usage_facts(projected)
            if facts is not None:
                return facts
    for candidate in _named_provider_objects(schema, "GetSystemMemInfo"):
        for provider in _dict_nodes(candidate):
            if not all(
                field_name in provider
                for field_name in ("usagePercent", "availableMemText", "totalMemText")
            ):
                continue
            facts = _projected_resource_usage_facts(provider)
            if facts is not None:
                return facts
    for candidate in _direct_field_objects(
        schema.get("data", {}),
        ("usagePercent", "availableMemText", "totalMemText"),
    ):
        facts = _projected_resource_usage_facts(candidate)
        if facts is not None:
            return facts
    return None


def _projected_resource_usage_facts(
    value: dict[str, Any],
) -> ResourceUsageOverviewFacts | None:
    usage_field = value.get("usagePercent")
    if not isinstance(usage_field, dict) or usage_field.get("type") != "number":
        return None
    usage_percent = usage_field.get("sampleValue")
    usage_is_number = isinstance(usage_percent, (int, float)) and not isinstance(
        usage_percent,
        bool,
    )
    if (
        not usage_is_number
        or not math.isfinite(float(usage_percent))
        or not 0.0 <= float(usage_percent) <= 100.0
    ):
        return None
    available_mem_text = _trusted_string(value.get("availableMemText"))
    total_mem_text = _trusted_string(value.get("totalMemText"))
    if available_mem_text is None or total_mem_text is None:
        return None
    normalized_usage: int | float = (
        int(usage_percent) if float(usage_percent).is_integer() else float(usage_percent)
    )
    return ResourceUsageOverviewFacts(
        usage_percent=normalized_usage,
        available_mem_text=available_mem_text,
        total_mem_text=total_mem_text,
    )


def extract_app_usage_overview_facts(
    schema: dict[str, Any],
) -> AppUsageOverviewFacts | None:
    """Extract one named app, its lossless duration, and optional update time."""
    data = schema.get("data")
    if isinstance(data, dict):
        projected = data.get("AppUsageOverview")
        if isinstance(projected, dict):
            facts = _projected_app_usage_facts(projected)
            if facts is not None:
                return facts
    for provider in _named_provider_objects(schema, "GetAppUsageDuration"):
        app_usage = provider.get("appUsage")
        if not isinstance(app_usage, dict):
            continue
        candidate = {
            "appName": app_usage.get("appName"),
            "durationText": app_usage.get("durationText"),
            "updatedAt": provider.get("updatedAt"),
        }
        facts = _projected_app_usage_facts(candidate)
        if facts is not None:
            return facts
    for provider in _direct_field_objects(schema.get("data", {}), ("appUsage",)):
        app_usage = provider.get("appUsage")
        if not isinstance(app_usage, dict):
            continue
        facts = _projected_app_usage_facts(
            {
                "appName": app_usage.get("appName"),
                "durationText": app_usage.get("durationText"),
                "updatedAt": provider.get("updatedAt"),
            }
        )
        if facts is not None:
            return facts
    return None


def _projected_app_usage_facts(value: dict[str, Any]) -> AppUsageOverviewFacts | None:
    app_name = _trusted_string(value.get("appName"))
    duration_text = _trusted_string(value.get("durationText"))
    updated_at = _trusted_string(value.get("updatedAt"))
    if app_name is None or duration_text is None:
        return None
    duration = parse_duration_text(duration_text)
    if duration is None:
        return None
    return AppUsageOverviewFacts(
        app_name=app_name,
        duration_text=duration_text,
        updated_at=updated_at,
        duration=duration,
    )


def parse_duration_text(duration_text: str) -> DurationSegments | None:
    """Parse only hour/minute forms that preserve the provider's full duration."""
    normalized = re.sub(r"\s+", "", duration_text).casefold()
    match = re.fullmatch(
        r"(?:(?P<hours>\d+)(?:小时|时|h))?"
        r"(?:(?P<minutes>\d+)(?:分钟|分|m))?",
        normalized,
    )
    if match is None:
        return None
    hours = match.group("hours")
    minutes = match.group("minutes")
    if hours is None and minutes is None:
        return None
    if hours is None:
        return DurationSegments(primary_value=minutes or "", primary_unit="分钟")
    if minutes is None:
        return DurationSegments(primary_value=hours, primary_unit="小时")
    return DurationSegments(
        primary_value=hours,
        primary_unit="小时",
        secondary_value=minutes,
        secondary_unit="分钟",
    )


def _named_provider_objects(schema: dict[str, Any], provider_id: str):
    for candidate in _dict_nodes(schema):
        provider = candidate.get(provider_id)
        if isinstance(provider, dict):
            yield provider


def extract_activity_overview_facts(
    schema: dict[str, Any],
) -> ActivityOverviewFacts | None:
    """Extract activity facts from one coherent projected/provider object."""
    for candidate in _direct_or_provider_candidates(
        schema,
        "ActivityOverview",
        "GetHealthAndSportSummary",
    ):
        daily_steps = _trusted_nonnegative_integer(candidate.get("dailySteps"))
        if daily_steps is None:
            continue
        return ActivityOverviewFacts(
            daily_steps=daily_steps,
            calories_text=_trusted_string(candidate.get("dailyTotalCaloriesText")),
            distance_text=_trusted_string(candidate.get("dailyDistanceText")),
        )
    return None


def extract_workout_latest_facts(
    schema: dict[str, Any],
) -> WorkoutLatestFacts | None:
    """Extract one complete latest-workout session from one health subtree."""
    for candidate in _direct_or_provider_candidates(
        schema,
        "WorkoutOverview",
        "GetHealthAndSportSummary",
    ):
        exercise_type_name = _trusted_string(candidate.get("exerciseTypeName"))
        calorie_text = _trusted_string(candidate.get("exerciseCalorieText"))
        duration_text = _trusted_string(candidate.get("exerciseDurationText"))
        end_time_text = _trusted_string(candidate.get("exerciseEndTimeText"))
        if exercise_type_name == "暂无运动":
            continue
        required_values = (exercise_type_name, calorie_text, duration_text, end_time_text)
        if any(value is None for value in required_values):
            continue
        assert exercise_type_name is not None
        assert calorie_text is not None
        assert duration_text is not None
        assert end_time_text is not None
        return WorkoutLatestFacts(
            exercise_type_name=exercise_type_name,
            calorie_text=calorie_text,
            duration_text=duration_text,
            end_time_text=end_time_text,
        )
    return None


def extract_countdown_overview_facts(
    schema: dict[str, Any],
) -> CountdownOverviewFacts | None:
    """Extract a generic non-negative countdown; zero is a valid boundary value."""
    for candidate in _direct_or_provider_candidates(
        schema,
        "CountdownOverview",
        "GetCountdownDays",
    ):
        countdown_days = _trusted_nonnegative_integer(candidate.get("countdownDays"))
        if countdown_days is not None:
            return CountdownOverviewFacts(countdown_days=countdown_days)
    return None


def extract_heart_rate_overview_facts(
    schema: dict[str, Any],
) -> HeartRateOverviewFacts | None:
    """Extract one positive exercise-average bpm and optional trusted timestamp."""
    for candidate in _direct_or_provider_candidates(
        schema,
        "HeartRateOverview",
        "GetHealthAndSportSummary",
    ):
        average_bpm = _trusted_positive_integer(candidate.get("exerciseHeartRateAvg"))
        if average_bpm is None:
            continue
        return HeartRateOverviewFacts(
            average_bpm=average_bpm,
            updated_at=_trusted_string(candidate.get("updatedAt")),
        )
    return None


def extract_sleep_overview_facts(
    schema: dict[str, Any],
) -> SleepOverviewFacts | None:
    """Extract one coherent night-sleep record without inferring status."""
    for candidate in _direct_or_provider_candidates(
        schema,
        "SleepOverview",
        "GetHealthAndSportSummary",
    ):
        duration_text = _trusted_string(candidate.get("nightSleepDurationText"))
        if duration_text is None:
            continue
        duration = parse_duration_text(duration_text)
        if duration is None:
            continue
        return SleepOverviewFacts(
            duration_text=duration_text,
            duration=_normalize_sleep_duration(duration),
            score=_trusted_percentage_number(candidate.get("sleepScore")),
            status=_trusted_string(candidate.get("sleepStatus")),
            fall_asleep_time=_trusted_clock_text(candidate.get("fallAsleepTimeText")),
            wakeup_time=_trusted_clock_text(candidate.get("wakeupTimeText")),
        )
    return None


def _normalize_sleep_duration(duration: DurationSegments) -> DurationSegments:
    """Normalize an hour-minute pair while preserving its exact minute total."""
    if duration.primary_unit == "分钟":
        total_minutes = int(duration.primary_value)
    else:
        total_minutes = int(duration.primary_value) * 60
        if duration.secondary_value is not None:
            total_minutes += int(duration.secondary_value)
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return DurationSegments(primary_value=str(minutes), primary_unit="分钟")
    if minutes == 0:
        return DurationSegments(primary_value=str(hours), primary_unit="小时")
    return DurationSegments(
        primary_value=str(hours),
        primary_unit="小时",
        secondary_value=str(minutes),
        secondary_unit="分钟",
    )


def _trusted_clock_text(value: Any) -> str | None:
    text = _trusted_string(value)
    if text is None:
        return None
    match = re.fullmatch(r"(?P<hour>\d{2}):(?P<minute>\d{2})", text)
    if match is None:
        return None
    if int(match.group("hour")) > 23 or int(match.group("minute")) > 59:
        return None
    return text


def _direct_or_provider_candidates(
    schema: dict[str, Any],
    component_id: str,
    provider_id: str,
):
    data = schema.get("data")
    if isinstance(data, dict):
        direct = data.get(component_id)
        if isinstance(direct, dict):
            yield direct
    yield from _named_provider_objects(schema, provider_id)
    required_fields = {
        "ActivityOverview": ("dailySteps",),
        "WorkoutOverview": (
            (
                "exerciseTypeName",
                "exerciseCalorieText",
                "exerciseDurationText",
                "exerciseEndTimeText",
            )
            if provider_id == "GetHealthAndSportSummary"
            else ("countdownDays",)
        ),
        "CountdownOverview": ("countdownDays",),
        "HeartRateOverview": ("exerciseHeartRateAvg",),
        "SleepOverview": ("nightSleepDurationText",),
    }.get(component_id, ())
    if required_fields:
        yield from _direct_field_objects(schema.get("data", {}), required_fields)


def _trusted_nonnegative_integer(value: Any) -> int | None:
    if not isinstance(value, dict) or value.get("type") != "integer":
        return None
    sample = value.get("sampleValue")
    if isinstance(sample, bool) or not isinstance(sample, int) or sample < 0:
        return None
    return sample


def _trusted_positive_integer(value: Any) -> int | None:
    selected = _trusted_nonnegative_integer(value)
    return selected if selected is not None and selected > 0 else None


def extract_schedule_overview_facts(schema: dict[str, Any]) -> ScheduleOverviewFacts | None:
    """Extract title/time/location from one coherent trusted first-event subtree."""
    for candidate in _projected_schedule_candidates(schema):
        projected = _projected_schedule_facts(candidate)
        if projected is not None:
            return projected
    provider = _calendar_schedule_provider(schema)
    if provider is None:
        return None
    event_count = _sample_value(provider.get("eventCount"))
    if isinstance(event_count, (int, float)) and not isinstance(event_count, bool):
        if event_count <= 0:
            return None
    event = _first_event_object(provider.get("events"))
    if event is None:
        return None
    fields = event.get("properties") if isinstance(event.get("properties"), dict) else event
    title = _trusted_string(fields.get("title"))
    start = _trusted_string(fields.get("dtStart"))
    if title is None or start is None:
        return None
    end = _trusted_string(fields.get("dtEnd"))
    location = _trusted_string(fields.get("eventLocation"))
    time_text = f"{start} - {end}" if end is not None else start
    return ScheduleOverviewFacts(title=title, time_text=time_text, location=location)


def _projected_schedule_candidates(schema: dict[str, Any]):
    data = schema.get("data")
    if not isinstance(data, dict):
        return
    direct = data.get("ScheduleOverview")
    if isinstance(direct, dict):
        yield direct
    selectors = data.get("_advancedSelectors")
    if not isinstance(selectors, dict):
        return
    schedule = selectors.get("schedule")
    if isinstance(schedule, dict):
        yield schedule


def _projected_schedule_facts(value: dict[str, Any]) -> ScheduleOverviewFacts | None:
    title = _trusted_string(value.get("title"))
    time_text = _trusted_string(value.get("timeText"))
    if title is None or time_text is None:
        return None
    return ScheduleOverviewFacts(
        title=title,
        time_text=time_text,
        location=_trusted_string(value.get("location")),
    )


def _calendar_schedule_provider(schema: dict[str, Any]) -> dict[str, Any] | None:
    named_sources = tuple(
        child
        for candidate in _dict_nodes(schema)
        for key, child in candidate.items()
        if key == "GetCalendarEvents" and isinstance(child, dict)
    )
    for source in named_sources:
        provider = next(
            (candidate for candidate in _dict_nodes(source) if "events" in candidate),
            None,
        )
        if provider is not None:
            return provider
    return next(iter(_direct_field_objects(schema.get("data", {}), ("events",))), None)


def _first_event_object(events: Any) -> dict[str, Any] | None:
    if isinstance(events, list):
        return events[0] if events and isinstance(events[0], dict) else None
    if not isinstance(events, dict):
        return None
    sample = events.get("sampleValue")
    if isinstance(sample, list):
        return sample[0] if sample and isinstance(sample[0], dict) else None
    items = events.get("items")
    if isinstance(items, dict):
        return items
    return events if any(name in events for name in ("title", "dtStart")) else None


def extract_date_overview_facts(schema: dict[str, Any]) -> DateOverviewFacts | None:
    """Return a validated projected pair or derive it from events[].startDate."""
    for candidate in _projected_date_candidates(schema):
        projected = _projected_date_facts(candidate)
        if projected is not None:
            return projected
    calendar = _calendar_event_context(schema)
    if calendar is None:
        return None
    events, provider = calendar
    start_date = _first_sample(events, "startDate")
    updated_at = _first_sample(provider, "updatedAt")
    parsed = _parse_calendar_date(start_date, updated_at)
    if parsed is None:
        return None
    return DateOverviewFacts(
        date=f"{parsed.day}日",
        weekday=_WEEKDAYS[parsed.weekday()],
    )


def _projected_date_facts(value: dict[str, Any]) -> DateOverviewFacts | None:
    if "date" not in value or "weekday" not in value:
        return None
    date = _trusted_string(value.get("date"))
    weekday = _trusted_string(value.get("weekday"))
    if date is None or weekday is None:
        return None
    if re.fullmatch(r"(?:[1-9]|[12]\d|3[01])日", date) is None:
        return None
    if weekday not in _WEEKDAYS:
        return None
    return DateOverviewFacts(date=date, weekday=weekday)


def _projected_date_candidates(schema: dict[str, Any]):
    data = schema.get("data")
    if not isinstance(data, dict):
        return
    direct = data.get("DateOverview")
    if isinstance(direct, dict):
        yield direct
    selectors = data.get("_advancedSelectors")
    if not isinstance(selectors, dict):
        return
    date = selectors.get("date")
    if isinstance(date, dict):
        yield date


def extract_weather_overview_facts(schema: dict[str, Any]) -> WeatherOverviewFacts | None:
    """Return the five complete string facts from one coherent weather subtree."""
    for candidate in _dict_nodes(schema):
        projected = _projected_weather_facts(candidate)
        if projected is not None:
            return projected
        current = next(
            (
                node
                for node in _dict_nodes(candidate)
                if all(name in node for name in ("temperatureText", "condition", "airQuality"))
            ),
            None,
        )
        if current is None:
            continue
        city = _first_trusted_string(candidate, "districtName") or _first_trusted_string(
            candidate, "prefectureName"
        )
        temperature = _trusted_string(current.get("temperatureText"))
        condition = _trusted_string(current.get("condition"))
        air_quality = _trusted_string(current.get("airQuality"))
        temperature_range = _first_trusted_string(candidate, "temperatureRangeText")
        values = (city, temperature, condition, air_quality, temperature_range)
        if all(value is not None for value in values):
            return WeatherOverviewFacts(
                city=city or "",
                temperature=temperature or "",
                condition=condition or "",
                air_quality=air_quality or "",
                temperature_range=temperature_range or "",
            )
    return None


def _projected_weather_facts(value: dict[str, Any]) -> WeatherOverviewFacts | None:
    names = ("city", "temperature", "condition", "airQuality", "temperatureRange")
    if not all(name in value for name in names):
        return None
    selected = tuple(_trusted_string(value.get(name)) for name in names)
    if any(item is None for item in selected):
        return None
    return WeatherOverviewFacts(
        city=selected[0] or "",
        temperature=selected[1] or "",
        condition=selected[2] or "",
        air_quality=selected[3] or "",
        temperature_range=selected[4] or "",
    )


def _dict_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _dict_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _dict_nodes(child)


def _direct_field_objects(value: Any, field_names: tuple[str, ...]):
    """Yield deepest coherent objects containing all requested direct fields."""
    if isinstance(value, dict):
        for child in value.values():
            yield from _direct_field_objects(child, field_names)
        if all(field_name in value for field_name in field_names):
            yield value
    elif isinstance(value, list):
        for child in value:
            yield from _direct_field_objects(child, field_names)


def _first_trusted_string(value: Any, field_name: str) -> str | None:
    if isinstance(value, dict):
        if field_name in value:
            selected = _trusted_string(value[field_name])
            if selected is not None:
                return selected
        for child in value.values():
            selected = _first_trusted_string(child, field_name)
            if selected is not None:
                return selected
    elif isinstance(value, list):
        for child in value:
            selected = _first_trusted_string(child, field_name)
            if selected is not None:
                return selected
    return None


def _trusted_string(value: Any) -> str | None:
    if not isinstance(value, dict) or value.get("type") != "string":
        return None
    sample = value.get("sampleValue")
    if not isinstance(sample, str) or not sample.strip():
        return None
    return sample.strip()


def _trusted_boolean(value: Any) -> bool | None:
    if not isinstance(value, dict) or value.get("type") != "boolean":
        return None
    sample = value.get("sampleValue")
    return sample if isinstance(sample, bool) else None


def _calendar_selectors(
    schema: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    schedule_facts = extract_schedule_overview_facts(schema)
    schedule = schedule_facts.as_selector() if schedule_facts is not None else {}
    date_facts = extract_date_overview_facts(schema)
    return schedule, date_facts.as_selector() if date_facts is not None else {}


def _calendar_event_context(schema: dict[str, Any]) -> tuple[Any, dict[str, Any]] | None:
    """Locate one provider schema containing the authoritative events array."""
    named_sources = tuple(
        child
        for candidate in _dict_nodes(schema)
        for key, child in candidate.items()
        if key in {"GetCalendarEvents", "calendar"} and isinstance(child, dict)
    )
    for source in named_sources:
        selected = _event_context_from_source(source)
        if selected is not None:
            return selected
    fallback_by_provider: dict[int, tuple[Any, dict[str, Any]]] = {}
    for candidate in _dict_nodes(schema):
        selected = _event_context_from_source(candidate)
        if selected is not None:
            fallback_by_provider[id(selected[1])] = selected
    fallback = tuple(fallback_by_provider.values())
    if len(fallback) == 1:
        return fallback[0]
    return None


def _event_context_from_source(source: dict[str, Any]) -> tuple[Any, dict[str, Any]] | None:
    for candidate in _dict_nodes(source):
        events = candidate.get("events")
        if events is not None and _first_field(events, "startDate") is not None:
            return events, candidate
    return None


def _parse_calendar_date(start_date: Any, updated_at: Any) -> datetime | None:
    if not isinstance(start_date, str):
        return None
    normalized_start = start_date.strip()
    full_match = _FULL_CALENDAR_DATE.fullmatch(normalized_start)
    if full_match is not None:
        pattern = "%Y-%m-%d" if full_match.group("separator") == "-" else "%Y/%m/%d"
        try:
            return datetime.strptime(normalized_start, pattern)
        except ValueError:
            return None
    short_match = _SHORT_CALENDAR_DATE.fullmatch(normalized_start)
    if short_match is None or not isinstance(updated_at, str):
        return None
    updated_match = _UPDATED_AT_DATE.fullmatch(updated_at.strip())
    if updated_match is None:
        return None
    updated_prefix = (
        f"{updated_match.group('year')}-{updated_match.group('month')}-"
        f"{updated_match.group('day')}"
    )
    try:
        datetime.strptime(updated_prefix, "%Y-%m-%d")
        return datetime.strptime(
            f"{updated_match.group('year')}-{normalized_start}",
            "%Y-%m-%d",
        )
    except ValueError:
        return None


def _first_sample(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        if field_name in value:
            return _sample_value(value[field_name])
        for child in value.values():
            selected = _first_sample(child, field_name)
            if selected is not None:
                return selected
    elif isinstance(value, list):
        for child in value:
            selected = _first_sample(child, field_name)
            if selected is not None:
                return selected
    return None


def _sample_value(value: Any) -> Any:
    if isinstance(value, dict) and "sampleValue" in value:
        return value["sampleValue"]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list) and value:
        return _sample_value(value[0])
    return None


def _field(value: str, description: str) -> dict[str, Any]:
    return {
        "type": "string",
        "description": description,
        "sampleValue": value,
    }
