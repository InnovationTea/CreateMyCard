# Provider 模板能力整改 Checklist

> 本表以各业务 `provider.json` 为事实源；主数据和次要数据均为硬必选数据，只有可选数据允许缺省。

## 整改总览

- [x] 72 个业务模板全部使用 `Compact`、`Hero`、`Full`、`WideHero`、`WideFull` 后缀。
- [x] 业务模板尺寸和动作组合由后缀推导，不再由 Provider 重复声明。
- [x] Provider 数据统一拆为 `primaryData`、`secondaryData`、`optionalData`。
- [x] `primaryData` 与 `secondaryData` 均参与模板准入硬校验。
- [x] Compact 支持双模板组合或双 PillAction；Full 支持可选 IconAction。
- [x] 第一层支持选择零到两个不重复 eventId。
- [x] 每个业务模板均在下方按主数据、次要数据、可选数据和布局场景展开。

## 布局后缀

| 后缀 | 布局及组合场景 | 卡片尺寸 |
| --- | --- | --- |
| Compact | 约 2x1；双 Compact，或单 Compact + 2 个 PillAction | 2x2 |
| Hero | 约 2x1.7；Hero + 1 个 PillAction | 2x2 |
| Full | 完整 2x2；单 Full，或 Full + 1 个 IconAction | 2x2 |
| WideHero | 约 4x1.7；WideHero + 1 个 PillAction | 2x4 |
| WideFull | 完整 4x2；单 WideFull | 2x4 |

## 业务与运行状态

| Provider | 数据能力 | 数据根 | 模板数 | 当前状态 |
| --- | --- | --- | ---: | --- |
| app-usage | `GetAppUsageDuration` | `/data/appUsageStats` | 4 | 启用 |
| battery | `GetPhoneBatteryInfo` | `/data/phoneBattery` | 16 | 启用 |
| calendar | `GetCalendarEvents` | `/data/calendar` | 10 | 配置禁用 |
| countdown | `GetCountdownDays` | `/data/countdown` | 1 | 启用 |
| earphone | `GetEarphoneInfo` | `/data/earphone` | 14 | 配置禁用 |
| health-sport | `GetHealthAndSportSummary` | `/data/healthSport` | 16 | 启用 |
| system-memory | `GetSystemMemInfo` | `/data/systemMem` | 2 | 启用 |
| weather | `ViewWeather` | `/data/weather` | 9 | 启用 |

## AppUsageOverview

- Provider：`com.huawei.app-usage.cli`；运行状态：启用。
- 数据能力：`GetAppUsageDuration`；模板数：4。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `AppUsageOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewHero@1` | 约 2x1.7；2x2 Hero + 1 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewWideFull@1` | 完整 4x2；单 WideFull | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewWideHero@1` | 约 4x1.7；2x4 WideHero + 1 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |

## BatteryOverview

- Provider：`com.huawei.battery.cli`；运行状态：启用。
- 数据能力：`GetPhoneBatteryInfo`；模板数：16。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BatteryOverviewNormalFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalHero@1` | 约 2x1.7；2x2 Hero + 1 个 PillAction | `/batterySOC` | `/batteryCapacityLevelDesc` | `/batterySOCText`<br>`/chargingStatusDesc` |
| ✅ | `BatteryOverviewChargingFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOC`<br>`/batterySOCText` | 无 | 无 |
| ✅ | `BatteryOverviewChargingPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOC`<br>`/batterySOCText` | 无 | 无 |
| ✅ | `BatteryOverviewLowPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOC`<br>`/batterySOCText` | 无 | 无 |
| ✅ | `BatteryOverviewNormalWeatherCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingWeatherCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowWeatherCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |

## CalendarOverview

- Provider：`com.huawei.calendar.cli`；运行状态：配置禁用。
- 数据能力：`GetCalendarEvents`；模板数：10。
- 日期与日程已合并为同一业务领域；日期日程组合场景使用
  `DateOverviewCompact@1` + 一个 `ScheduleOverview*Compact@1` 组成 2x2。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `DateOverviewCompact@1` | 约 2x1；优先与一个日程 Compact 纵向组成 2x2 | `/events/0/startDate` | `/updatedAt` | 无 |
| ✅ | `DateOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/events/0/startDate` | `/updatedAt` | 无 |
| ✅ | `ScheduleOverviewNextEventFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewNextEventLocationFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation`<br>`/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewMeetingCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewMeetingLocationCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation`<br>`/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewMeetingWideFull@1` | 完整 4x2；单 WideFull | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation`<br>`/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewMeetingSourceCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewMeetingLocationSourceCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation`<br>`/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewMeetingSourceWideFull@1` | 完整 4x2；单 WideFull | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation`<br>`/events/0/dtEnd` | 无 |

## CountdownOverview

- Provider：`com.huawei.countdown.cli`；运行状态：启用。
- 数据能力：`GetCountdownDays`；模板数：1。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `CountdownOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/countdownDays` | 无 | 无 |

## BluetoothDeviceOverview

- Provider：`com.huawei.earphone.cli`；运行状态：配置禁用。
- 数据能力：`GetEarphoneInfo`；模板数：14。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BluetoothDeviceOverviewDisconnectedFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/isConnected` | `/earphoneName` | 无 |
| ✅ | `BluetoothDeviceOverviewConnectionFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/isConnected` | `/earphoneName` | 无 |
| ✅ | `BluetoothDeviceOverviewDisconnectedPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | 无 | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudsPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | 无 | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsPhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsDynamicWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewCaseFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/isConnected` | `/earphoneName`<br>`/batteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewLeftEarbudCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | `/earphoneName`<br>`/leftBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewRightEarbudCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | `/earphoneName`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/isConnected` | `/earphoneName`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewPairVisualFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/isConnected` | `/earphoneName`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompleteWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName`<br>`/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompletePhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName`<br>`/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |

## ActivityOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：4。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ActivityOverviewStepsFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewStepsCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewDailySummaryFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText` | 无 |
| ✅ | `ActivityOverviewDailySummaryWideFull@1` | 完整 4x2；单 WideFull | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText` | 无 |

## WorkoutOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：1。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WorkoutOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/exerciseTypeName`<br>`/exerciseDurationText` | `/exerciseCalorieText`<br>`/exerciseEndTimeText` | 无 |

## HeartRateOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：8。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `HeartRateOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewIconFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedIconFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewIconCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedIconCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |

## SleepOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：3。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `SleepOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/nightSleepDurationText` | `/sleepScore`<br>`/sleepStatus` | 无 |
| ✅ | `SleepOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |
| ✅ | `SleepOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |

## ResourceUsageOverview

- Provider：`com.huawei.system-memory.cli`；运行状态：启用。
- 数据能力：`GetSystemMemInfo`；模板数：2。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ResourceUsageOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |
| ✅ | `ResourceUsageOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |

## WeatherOverview

- Provider：`com.huawei.weather.cli`；运行状态：启用。
- 数据能力：`ViewWeather`；模板数：9。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WeatherOverviewCompact@1` | 约 2x1；双 Compact，或 Compact + 2 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewIconCompact@1` | 约 2x1；双 Compact，或 Compact + 2 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewIconFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewConditionFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/current/condition` | `/location/districtName`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewHumidityFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/current/humidityPercent` | `/location/districtName`<br>`/current/condition`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewUvFull@1` | 完整 2x2；单 Full，或 Full + 1 个 IconAction | `/current/uvIndex` | `/location/districtName`<br>`/current/condition`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewAirQualityHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/current/airQuality` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |

说明：最新天气 UX 中的日出日落与 AQI 数值不在当前 `ViewWeather` 数据契约内，本轮未生成伪数据模板。

## 验收口径

- 业务模板 ID 不符合五类后缀时，Provider Bundle 加载失败。
- Wide 后缀只能进入 2x4；其余三类只能进入 2x2。
- 任一主数据或次要数据在 TaskSpec 中缺失时，模板不准入。
- 三组数据路径必须分别唯一且互不重叠。
- 模板 `$path` 只能引用主数据或次要数据；`$optionalPath` 只能引用可选数据。
- 模板展开前确定性校验布局尺寸、业务模板数量、Action 数量和 Action 类型。
- Calendar 与 Earphone 当前仍受运行配置禁用；本次已完成资源整改，但不会进入线上候选。
