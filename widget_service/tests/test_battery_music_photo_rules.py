"""T6电量与音乐分流只读现有布局，不推测尺寸、不以关键词代替可见数据。"""

import json

from test_autumn_calendar_photos import expanded
from test_metronome_photo import ACTION, earphone_sample

SQUARES = ["photo-ux-texture-blue-diamond-square", "photo-ux-texture-blue-diamond-square"]
WIDE = "photo-ux-texture-blue-diamond-wide"
BATTERY_PATH = "/data/phoneBattery/batteryLevel"


def battery_sample():
    sample = earphone_sample()
    rows = [json.loads(line) for line in sample.compact.splitlines()]
    task = {"size": "2x2", "userQuery": "手机电量和设置", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"phoneBattery": {}}}}
    compact = json.dumps(rows).replace("/data/earphone/earphoneBatteryLevel", BATTERY_PATH)
    return expanded(json.loads(compact), task)


def wide_battery_sample(layout):
    children = ["main", "upper", "lower"]
    rows = [
        ["root", "Layout", {"layout": layout}, children],
        ["main", "Region", {"variant": "title-content"}, ["header", "reading"]],
        ["header", "SingleLineTitle", {"title": "设备电量"}],
        ["reading", "EmphasisText", {"mainText": {"path": BATTERY_PATH}}],
        ["upper", "InfoBlock", {"variant": "slot", "primaryText": "正常",
                                "secondaryText": "电池状态"}],
        ["lower", "CardButton", {"label": "设置", "onClick": ACTION}],
        [BATTERY_PATH, 68],
    ]
    if layout == "W-split-panels":
        children[:] = ["main", "other"]
        rows.extend([
            ["other", "Region", {"variant": "title-content"}, ["weather", "temperature"]],
            ["weather", "SingleLineTitle", {"title": "天气"}],
            ["temperature", "EmphasisText", {
                "mainText": {"path": "/data/weather/temperature"}}],
            ["/data/weather/temperature", 29],
        ])
        rows = [row for row in rows if row[0] not in {"upper", "lower"}]
    task = {"size": "2x4", "userQuery": "手机电量和天气", "appVersion": "99.0.0",
            "dataModelSchema": {"data": {"phoneBattery": {}, "weather": {}}}}
    return expanded(rows, task)
