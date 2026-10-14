# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""当前 Compact 规则使用的常量，不登记另一份运行时合同。"""

from __future__ import annotations

import re

from services.compact_component_runtime import VISUAL_RECIPE_VERSION

_EXPRESSION_PATTERN = re.compile("^\\{\\{\\s*(?P<body>.*?)\\s*\\}\\}$")

_REFERENCE_PATTERN = re.compile("\\$\\{(?P<path>[^{}]*)\\}")

_STRING_LITERAL_PATTERN = re.compile("'(?:\\\\.|[^'\\\\])*'|\\\"(?:\\\\.|[^\\\"\\\\])*\\\"")

_SIMPLE_FORMATTED_EXPRESSION_PATTERN = re.compile(
    "^\\{\\{\\s*\\$\\{(?P<path>/[^{}]+)\\}\\s*\\+\\s*'(?P<unit>[^']+)'\\s*\\}\\}$"
)

_NON_EMPTY_CONTAINER_TYPES = frozenset({"Row", "Column", "Stack"})

_VISUAL_RECIPE_MARKER_PREFIX = f"{VISUAL_RECIPE_VERSION}:"

_TWO_BY_FOUR_MULTI_LARGE_WIDTH = 132

_TWO_BY_FOUR_MULTI_LARGE_HEIGHT = 126

_TWO_BY_FOUR_MULTI_INNER_WIDTH = 116

_NUMERIC_SCHEMA_TYPES = frozenset({"integer", "number"})

_COMMON_DISPLAY_UNITS = frozenset(
    {
        "%",
        "°C",
        "℃",
        "°F",
        "天",
        "小时",
        "分钟",
        "分",
        "秒",
        "毫秒",
        "步",
        "次",
        "件",
        "个",
        "条",
        "项",
        "人",
        "级",
        "公里",
        "千米",
        "米",
        "厘米",
        "毫米",
        "km",
        "m",
        "cm",
        "mm",
        "kg",
        "g",
        "mg",
        "kcal",
        "千卡",
        "cal",
        "mL",
        "ml",
        "L",
        "A",
        "mA",
        "V",
        "W",
        "kW",
        "kWh",
        "bpm",
        "次/分钟",
        "mV",
        "μA",
        "uA",
        "kHz",
        "MHz",
        "Pa",
        "kPa",
        "Wh",
        "MB",
        "GB",
        "TB",
        "km/h",
        "m/s",
    }
)

_MEASUREMENT_DESCRIPTION_MARKERS = (
    "温度",
    "电量",
    "电池电量",
    "剩余电量",
    "占比",
    "比例",
    "电流",
    "电压",
    "功率",
    "频率",
    "速度",
    "距离",
    "容量",
    "湿度",
    "压力",
    "海拔",
    "重量",
    "体重",
    "长度",
    "宽度",
    "高度",
)

_MEASUREMENT_SAMPLE_PATTERN = re.compile(
    "[+-]?\\d+(?:\\.\\d+)?\\s*(?:°C|℃|°F|mA|μA|uA|A|mV|V|kW|W|kWh|Wh|MHz|kHz|Hz|"
    "km/h|m/s|km|千米|公里|m|米|cm|厘米|mm|毫米|kg|g|mg|MB|GB|TB|Pa|kPa|%|毫秒|小时|分钟|分|秒)$"
)

_AMBIGUOUS_METRIC_DESCRIPTION_MARKERS = (
    "指数",
    "等级",
    "评分",
    "得分",
    "概率",
    "风险",
    "质量",
    "健康",
)

_AMBIGUOUS_STATUS_MARKERS = (
    "良",
    "中等",
    "低",
    "高",
    "正常",
    "异常",
    "未知",
    "未充电",
    "已充电",
    "未连接",
    "已连接",
)
