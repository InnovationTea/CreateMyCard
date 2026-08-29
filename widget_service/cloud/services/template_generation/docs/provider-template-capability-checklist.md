# Provider 模板能力整改 Checklist

> 本表以各业务 `provider.json` 为事实源；主数据和次要数据均为硬必选数据，只有可选数据允许缺省。

## 整改总览

- [x] 81 个业务模板全部使用 `Compact`、`Hero`、`Full`、`WideHero`、`WideFull` 后缀。
- [x] 业务模板尺寸和动作组合由后缀推导，不再由 Provider 重复声明。
- [x] Provider 数据统一拆为 `primaryData`、`secondaryData`、`optionalData`。
- [x] `primaryData` 与 `secondaryData` 均参与模板准入硬校验。
- [x] Compact 支持双模板组合或双 PillAction；Full 仅用于无 Action 的单模板布局。
- [x] PillAction/IconAction 使用独立 Action Provider 模板，第二层只输出批准的展示 Props。
- [x] 第一层支持选择零到两个不重复 eventId。
- [x] 每个业务模板均在下方按主数据、次要数据、可选数据和布局场景展开。

## 布局后缀

| 后缀 | 布局及组合场景 | 卡片尺寸 |
| --- | --- | --- |
| Compact | 约 2x1；双 Compact，或单 Compact + 2 个 PillAction | 2x2 |
| Hero | 约 2x1.7；Hero + 1 个 PillAction | 2x2 |
| Full | 完整 2x2；无 Action 的单 Full | 2x2 |
| WideHero | 约 4x1.7；WideHero + 1 个 PillAction | 2x4 |
| WideFull | 完整 4x2；单 WideFull | 2x4 |

## 业务与运行状态

| Provider | 数据能力 | 数据根 | 模板数 | 当前状态 |
| --- | --- | --- | ---: | --- |
| app-usage | `GetAppUsageDuration` | `/data/appUsageStats` | 5 | 启用 |
| battery | `GetPhoneBatteryInfo` | `/data/phoneBattery` | 13 | 启用 |
| calendar | `GetCalendarEvents` | `/data/calendar` | 13 | 启用 |
| countdown | `GetCountdownDays` | `/data/countdown` | 1 | 启用 |
| earphone | `GetEarphoneInfo` | `/data/earphone` | 16 | 启用 |
| health-sport | `GetHealthAndSportSummary` | `/data/healthSport` | 17 | 启用 |
| system-memory | `GetSystemMemInfo` | `/data/systemMem` | 2 | 启用 |
| weather | `ViewWeather` | `/data/weather` | 7 | 启用 |

## AppUsageOverview

- Provider：`com.huawei.app-usage.cli`；运行状态：启用。
- 数据能力：`GetAppUsageDuration`；模板数：5。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `AppUsageOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewHero@1` | 约 2x1.7；2x2 Hero + 1 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | 无 |
| ✅ | `AppUsageOverviewWideFull@1` | 完整 4x2；单 WideFull | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewWideHero@1` | 约 4x1.7；2x4 WideHero + 1 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |

## BatteryOverview

- Provider：`com.huawei.battery.cli`；运行状态：启用。
- 数据能力：`GetPhoneBatteryInfo`；模板数：13。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BatteryOverviewPercentRingHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/batterySOC`<br>`/batterySOCText` | 无 | 无 |
| ✅ | `BatteryOverviewNormalFull@1` | 完整 2x2；无 Action 的单 Full | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalHero@1` | 约 2x1.7；2x2 Hero + 1 个 PillAction | `/batterySOC` | `/batteryCapacityLevelDesc` | `/batterySOCText`<br>`/chargingStatusDesc` |
| ✅ | `BatteryOverviewChargingFull@1` | 完整 2x2；无 Action 的单 Full | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowFull@1` | 完整 2x2；无 Action 的单 Full | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewNormalWeatherCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingWeatherCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowWeatherCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewTemperatureIconCompact@1` | 约 2x1；双 Compact 组成 2x2 | `/batteryTemperatureText` | 无 | 无 |
| ✅ | `BatteryOverviewStatusIconCompact@1` | 约 2x1；双 Compact 组成 2x2 | `/batterySOCText` | 无 | `/batteryCapacityLevelDesc` |

## CalendarOverview

- Provider：`com.huawei.calendar.cli`；运行状态：启用。
- 数据能力：`GetCalendarEvents`；模板数：13。
- 当前只提供日程模板；独立日期单卡与日期加日程的双 Compact 组合已下架。真实日期仍可通过
  `ScheduleOverviewDatedMeetingHero@1` 与会议标题、起止时间和地点共同展示。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ScheduleOverviewNextEventFull@1` | 完整 2x2；无 Action 的单 Full | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewNextEventHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title` | 无 | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/remindTime/0`<br>`/eventCount`<br>`/events/0/description`<br>`/events/0/timeZone`<br>`/events/0/isAllDay`<br>`/events/0/eventLocation` |
| ✅ | `ScheduleOverviewReminderHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title` | `/events/0/dtStart`<br>`/events/0/remindTime/0` | 无 |
| ✅ | `ScheduleOverviewTimezoneFull@1` | 完整 2x2；无 Action 的单 Full | `/events/0/timeZone`<br>`/events/0/title` | `/events/0/isAllDay`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewEventCountHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/eventCount`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/description` | 无 |
| ✅ | `ScheduleOverviewDatedMeetingHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/startDate`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewNextEventLocationFull@1` | 完整 2x2；无 Action 的单 Full | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation`<br>`/events/0/dtEnd` | 无 |
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
| ✅ | `CountdownOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/countdownDays` | 无 | 无 |

## BluetoothDeviceOverview

- Provider：`com.huawei.earphone.cli`；运行状态：启用。
- 数据能力：`GetEarphoneInfo`；模板数：16。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BluetoothDeviceOverviewDisconnectedFull@1` | 完整 2x2；无 Action 的单 Full | `/isConnected` | `/earphoneName` | 无 |
| ✅ | `BluetoothDeviceOverviewConnectionFull@1` | 完整 2x2；无 Action 的单 Full | `/isConnected` | `/earphoneName` | 无 |
| ✅ | `BluetoothDeviceOverviewDisconnectedPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | 无 | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudsPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | 无 | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewCaseStatusCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batteryLevel`<br>`/chargingStatusDesc` | 无 | `/leftChargingStatusDesc`<br>`/rightChargingStatusDesc` |
| ✅ | `BluetoothDeviceOverviewEarbudsPhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsDynamicWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewCaseFull@1` | 完整 2x2；无 Action 的单 Full | `/isConnected` | `/earphoneName`<br>`/batteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewLeftEarbudCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | `/earphoneName`<br>`/leftBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewRightEarbudCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | `/earphoneName`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairFull@1` | 完整 2x2；无 Action 的单 Full | `/isConnected` | `/earphoneName`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewPairVisualFull@1` | 完整 2x2；无 Action 的单 Full | `/isConnected` | `/earphoneName`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompleteWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName`<br>`/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairPhoneCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/isConnected` | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompletePhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected` | `/earphoneName`<br>`/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction；顶部展示 `title` 文本属性 | `/isConnected`<br>`/earphoneName` | 无 | 无 |

## ActivityOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：5。
- 展示说明：Compact 只展示每日步数；Hero 展示步数和固定万步基准进度；2x2 Full 还以文字展示热量和距离，
  三者均只接受可选步数图标。Wide 模板继续保留热量和距离图标槽位。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ActivityOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewWideHero@1` | 约 4x1.7；WideHero + 1 个 PillAction | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText`<br>`/targetDateText` | 无 |
| ✅ | `ActivityOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText` | 无 |
| ✅ | `ActivityOverviewWideFull@1` | 完整 4x2；单 WideFull | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText`<br>`/targetDateText` | 无 |

## WorkoutOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：1。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WorkoutOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseTypeName`<br>`/exerciseDurationText` | `/exerciseCalorieText`<br>`/exerciseEndTimeText` | 无 |

## HeartRateOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：8。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `HeartRateOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewIconFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedIconFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewIconCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedIconCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |

## SleepOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：3。
- 展示说明：Compact 以得分环展示时长和得分；Hero 以线性进度展示时长和得分；Full 还展示睡眠状态，
  三者均可使用睡眠图标。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `SleepOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/nightSleepDurationText` | `/sleepScore`<br>`/sleepStatus` | 无 |
| ✅ | `SleepOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |
| ✅ | `SleepOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |

## ResourceUsageOverview

- Provider：`com.huawei.system-memory.cli`；运行状态：启用。
- 数据能力：`GetSystemMemInfo`；模板数：2。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ResourceUsageOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |
| ✅ | `ResourceUsageOverviewCompact@1` | 约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |

## WeatherOverview

- Provider：`com.huawei.weather.cli`；运行状态：启用。
- 数据能力：`ViewWeather`；模板数：7。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WeatherOverviewCompact@1` | 约 2x1；可选天气图标；双 Compact，或 Compact + 2 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewTemperatureIconCompact@1` | 约 2x1；温度、城市与天气图标；双 Compact | `/current/temperatureText` | `/location/districtName` | 无 |
| ✅ | `WeatherOverviewHero@1` | 约 2x1.7；可选天气图标；Hero + 1 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewFull@1` | 完整 2x2；可选天气图标；无 Action 的单 Full | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewHumidityFull@1` | 完整 2x2；无 Action 的单 Full | `/current/humidityPercent` | `/location/districtName`<br>`/current/condition`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewUvFull@1` | 完整 2x2；无 Action 的单 Full | `/current/uvIndex` | `/location/districtName`<br>`/current/condition`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewAirQualityHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/current/airQuality` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |

说明：最新天气 UX 中的日出日落与 AQI 数值不在当前 `ViewWeather` 数据契约内，本轮未生成伪数据模板。

## 验收口径

- 业务模板 ID 不符合五类后缀时，Provider Bundle 加载失败。
- Wide 后缀只能进入 2x4；其余三类只能进入 2x2。
- 任一主数据或次要数据在 TaskSpec 中缺失时，模板不准入。
- 三组数据路径必须分别唯一且互不重叠。
- 模板 `$path` 只能引用主数据或次要数据；`$optionalPath` 只能引用可选数据。
- 模板展开前确定性校验布局尺寸、业务模板数量、Action 数量和 Action 类型。
- Earphone 与 Calendar 均已启用并进入线上候选。
