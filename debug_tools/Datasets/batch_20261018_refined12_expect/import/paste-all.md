# 12 条期望的粘贴清单

每条按「导入期望输出」页的三个输入框分块；图标只写资源名，页面按文件名比较，忽略目录与扩展名。

## Q001 西湖天气（2x2／天气）

- 期望数据 4 行：
```text
/data/weather/current/condition
/data/weather/location/cityCode
/data/weather/location/districtName
/data/weather/location/prefectureName
```
- 期望动作 1 行：
```text
clickToDeeplink:Weather_CityCode
```
- 期望图标 1 行：
```text
local_fill
```

## Q004 天气预警（2x2／天气）

- 期望数据 1 行：
```text
/data/weather/current/alertLevel
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 1 行：
```text
ic_warning_monochrome
```

## Q006 明日双会（2x2／日程）

- 期望数据 4 行：
```text
/data/calendar/events/0/dtStart
/data/calendar/events/0/title
/data/calendar/events/1/dtStart
/data/calendar/events/1/title
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 1 行：
```text
calendar_fill
```

## Q009 左右耳机（2x2／设备）

- 期望数据 4 行：
```text
/data/earphone/leftBatteryLevel
/data/earphone/leftChargingStatusDesc
/data/earphone/rightBatteryLevel
/data/earphone/rightChargingStatusDesc
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 2 行：
```text
icon_left
icon_right
```

## Q010 周末露营（2x2／出行）

- 期望数据 4 行：
```text
/data/weather/daily/1/airQuality
/data/weather/daily/1/condition
/data/weather/daily/2/airQuality
/data/weather/daily/2/condition
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 0 行：
```text
（无）
```

## Q014 设备充电（2x2／设备）

- 期望数据 3 行：
```text
/data/earphone/chargingStatusDesc
/data/phoneBattery/chargingStatusDesc
/data/phoneBattery/pluggedTypeDesc
```
- 期望动作 1 行：
```text
clickToDeeplink:Settings
```
- 期望图标 1 行：
```text
bolt_fill
```

## Q034 双城天气（2x2／天气）

- 期望数据 4 行：
```text
/data/weather1/current/condition
/data/weather1/current/temperatureC
/data/weather2/current/condition
/data/weather2/current/temperatureC
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 1 行：
```text
local_fill
```

## Q037 今日运动（2x2／健康）

- 期望数据 3 行：
```text
/data/healthSport/dailyDistanceText
/data/healthSport/dailySteps
/data/healthSport/dailyTotalCaloriesText
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 1 行：
```text
figure_run
```

## Q054 电池检测（2x4／设备）

- 期望数据 4 行：
```text
/data/phoneBattery/batterySOC
/data/phoneBattery/isBatteryPresentText
/data/phoneBattery/nowCurrentText
/data/phoneBattery/voltageText
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 2 行：
```text
battery_leaf_fill
bolt_fill
```

## Q056 客户现场（2x4／日程）

- 期望数据 5 行：
```text
/data/calendar/events/0/dtStart
/data/calendar/events/0/eventLocation
/data/weather/current/condition
/data/weather/current/temperatureC
/data/weather/location/cityCode
```
- 期望动作 1 行：
```text
clickToDeeplink:Weather_CityCode
```
- 期望图标 2 行：
```text
calendar_fill
local_fill
```

## Q069 睡眠分析（2x4／健康）

- 期望数据 5 行：
```text
/data/healthSport/deepSleepDurationText
/data/healthSport/nightSleepDurationText
/data/healthSport/sleepScore
/data/healthSport/sleepStatus
/data/healthSport/totalNapDurationText
```
- 期望动作 0 行：
```text
（无）
```
- 期望图标 1 行：
```text
moon_z_fill_1
```

## Q076 日出准备（2x4／出行）

- 期望数据 7 行：
```text
/data/phoneBattery/batteryTemperatureText
/data/weather/current/alertLevel
/data/weather/current/humidityPercent
/data/weather/current/temperatureText
/data/weather/current/windDirection
/data/weather/current/windLevel
/data/weather/location/cityCode
```
- 期望动作 1 行：
```text
clickToDeeplink:Weather_CityCode
```
- 期望图标 0 行：
```text
（无）
```
