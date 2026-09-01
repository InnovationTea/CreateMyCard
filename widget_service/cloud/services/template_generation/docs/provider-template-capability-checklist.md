# Provider 模板能力整改 Checklist

> 本表以各业务 `provider.json` 为事实源；主数据和次要数据均为硬必选数据，只有可选数据允许缺省。

## 整改总览

- [x] 88 个业务模板全部使用 `Support`、`Compact`、`Hero`、`Full`、`WideHero`、`WideFull` 后缀。
- [x] 业务模板尺寸和动作组合由后缀推导，不再由 Provider 重复声明。
- [x] Provider 数据统一拆为 `primaryData`、`secondaryData`、`optionalData`。
- [x] `primaryData` 与 `secondaryData` 均参与模板准入硬校验。
- [x] Support/TwoSupport 底层资源仍保留，但当前 Search 显式拒绝 `2x2` 多业务；Compact 使用双
  PillAction；Full 用于无 Action，或搭配一个 IconAction。
- [x] PillAction/IconAction 使用独立 Action Provider 模板，第二层只输出批准的展示 Props。
- [x] 第一层支持选择零到两个不重复 eventId。
- [x] 每个业务模板均在 `provider.json` 中声明主数据、次要数据、可选数据和布局场景。

## 布局后缀

| 后缀 | 布局及组合场景 | 卡片尺寸 |
| --- | --- | --- |
| Support | 约 2x1；底层双 Support 资源保留，当前 Search 不可达 | 2x2 |
| Compact | 约 2x1；单 Compact + 2 个 PillAction | 2x2 |
| Hero | 约 2x1.7；Hero + 1 个 PillAction | 2x2 |
| Full | 完整 2x2；无 Action，或 Full + 1 个 IconAction | 2x2 |
| WideHero | 约 4x1.7；WideHero + 1 个 PillAction | 2x4 |
| WideFull | 完整 4x2；单 WideFull | 2x4 |

## 业务与运行状态

| Provider | 数据能力 | 数据根 | 模板数 | 当前状态 |
| --- | --- | --- | ---: | --- |
| app-usage | `GetAppUsageDuration` | `/data/appUsageStats` | 6 | 启用 |
| battery | `GetPhoneBatteryInfo` | `/data/phoneBattery` | 21 | 启用 |
| calendar | `GetCalendarEvents` | `/data/calendar` | 8 | 启用 |
| countdown | `GetCountdownDays` | `/data/countdown` | 1 | 启用 |
| earphone | `GetEarphoneInfo` | `/data/earphone` | 10 | 启用 |
| health-sport | `GetHealthAndSportSummary` | `/data/healthSport` | 30 | 启用 |
| system-memory | `GetSystemMemInfo` | `/data/systemMem` | 3 | 启用 |
| weather | `ViewWeather` | `/data/weather` | 9 | 启用 |

下方完整展开本轮调整的 Calendar、Countdown、Earphone 和 Weather；其他 Provider 保留基础形态摘要，
精确全集以当前 `provider.json` 为准。Support 与 Compact 不要求一一对应；Support/TwoSupport 底层资源
继续保留，但当前 Search 会显式拒绝 `2x2` 多业务组合。

## AppUsageOverview

- Provider：`com.huawei.app-usage.cli`；运行状态：启用。
- 数据能力：`GetAppUsageDuration`；模板数：6。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `AppUsageOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewHero@1` | 约 2x1.7；2x2 Hero + 1 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | 无 |
| ✅ | `AppUsageOverviewWideFull@1` | 完整 4x2；单 WideFull | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |
| ✅ | `AppUsageOverviewWideHero@1` | 约 4x1.7；2x4 WideHero + 1 个 PillAction | `/appUsage/appName`<br>`/appUsage/durationText` | 无 | `/updatedAt` |

## BatteryOverview

- Provider：`com.huawei.battery.cli`；运行状态：启用。
- 数据能力：`GetPhoneBatteryInfo`；模板数：21。

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
| ✅ | `BatteryOverviewNormalWeatherCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingWeatherCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewLowWeatherCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewStatusIconCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batterySOCText` | 无 | `/batteryCapacityLevelDesc` |

## CalendarOverview

- Provider：`com.huawei.calendar.cli`；运行状态：启用。
- 数据能力：`GetCalendarEvents`；模板数：8。
- 当前没有 Support 或 Compact；真实日期通过 `ScheduleOverviewDateFull@1` 或
  `ScheduleOverviewDatedMeetingHero@1` 与同一首项日程共同展示。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ScheduleOverviewNextEventHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewReminderHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title` | `/events/0/dtStart`<br>`/events/0/remindTime/0` | 无 |
| ✅ | `ScheduleOverviewTimezoneFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/events/0/timeZone`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewDateFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/events/0/startDate`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewDatedMeetingHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/startDate`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewNextEventLocationFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewMeetingWideFull@1` | 完整 4x2；单 WideFull | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewMeetingSourceWideFull@1` | 完整 4x2；单 WideFull | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |

## CountdownOverview

- Provider：`com.huawei.countdown.cli`；运行状态：启用。
- 数据能力：`GetCountdownDays`；模板数：1；当前没有 Support、Compact 或 Hero。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `CountdownOverviewFull@1` | 完整 2x2；无 Action，或加一个 IconAction | `/countdownDays` | 无 | 无 |

## BluetoothDeviceOverview

- Provider：`com.huawei.earphone.cli`；运行状态：启用。
- 数据能力：`GetEarphoneInfo`；模板数：10。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BluetoothDeviceOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/isConnected`<br>`/earphoneName` | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompleteWideHero@1` | 约 4x1.7；WideHero + 1 个 PillAction | `/isConnected`<br>`/earphoneName`<br>`/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | `/chargingStatusDesc`<br>`/leftChargingStatusDesc`<br>`/rightChargingStatusDesc` | 无 |
| ✅ | `BluetoothDeviceOverviewCaseStatusCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batteryLevel`<br>`/chargingStatusDesc` | 无 | `/leftChargingStatusDesc`<br>`/rightChargingStatusDesc` |
| ✅ | `BluetoothDeviceOverviewEarbudsPhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | 无 | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsDynamicWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | 无 | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/isConnected`<br>`/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompleteWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/earphoneName` | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompletePhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |

## ActivityOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：6。
- 展示说明：Compact 只展示每日步数；Hero 展示步数和固定万步基准进度；2x2 Full 还以文字展示热量和距离，
  三者均只接受可选步数图标。Wide 模板继续保留热量和距离图标槽位。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ActivityOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewWideHero@1` | 约 4x1.7；WideHero + 1 个 PillAction | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText`<br>`/targetDateText` | 无 |
| ✅ | `ActivityOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText` | 无 |
| ✅ | `ActivityOverviewWideFull@1` | 完整 4x2；单 WideFull | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText`<br>`/targetDateText` | 无 |

## WorkoutOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：4。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WorkoutOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseTypeName`<br>`/exerciseDurationText` | `/exerciseCalorieText`<br>`/exerciseEndTimeText` | 无 |

## HeartRateOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：16。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `HeartRateOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewIconFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedIconFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |
| ✅ | `HeartRateOverviewIconCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewUpdatedIconCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | `/updatedAt` | 无 |

## SleepOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：4。
- 展示说明：Compact 以得分环展示时长和得分；Hero 以线性进度展示时长和得分；Full 还展示睡眠状态，
  三者均可使用睡眠图标。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `SleepOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/nightSleepDurationText` | `/sleepScore`<br>`/sleepStatus` | 无 |
| ✅ | `SleepOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |
| ✅ | `SleepOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |

## ResourceUsageOverview

- Provider：`com.huawei.system-memory.cli`；运行状态：启用。
- 数据能力：`GetSystemMemInfo`；模板数：3。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ResourceUsageOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |
| ✅ | `ResourceUsageOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |

## WeatherOverview

- Provider：`com.huawei.weather.cli`；运行状态：启用。
- 数据能力：`ViewWeather`；模板数：9。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WeatherOverviewCompact@1` | 约 2x1；可选天气图标；Compact + 2 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewUvCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/current/temperatureText`<br>`/current/uvIndex` | `/location/districtName`<br>`/current/condition` | 无 |
| ✅ | `WeatherOverviewTemperatureSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewTemperatureUvSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/current/temperatureText`<br>`/current/uvIndex` | `/location/districtName`<br>`/current/condition` | 无 |
| ✅ | `WeatherOverviewHero@1` | 约 2x1.7；可选天气图标；Hero + 1 个 PillAction | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewFull@1` | 完整 2x2；可选天气图标；无 Action 的单 Full | `/current/temperatureText` | `/location/districtName`<br>`/current/condition`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewHumidityFull@1` | 完整 2x2；无 Action 的单 Full | `/current/humidityPercent` | `/location/districtName`<br>`/current/condition`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewUvFull@1` | 完整 2x2；无 Action 的单 Full | `/current/uvIndex` | `/location/districtName`<br>`/current/condition`<br>`/current/temperatureText`<br>`/current/airQuality`<br>`/current/coldLevel` | 无 |
| ✅ | `WeatherOverviewAirQualityHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/current/airQuality` | `/location/districtName`<br>`/current/condition`<br>`/current/coldLevel` | 无 |

说明：最新天气 UX 中的日出日落与 AQI 数值不在当前 `ViewWeather` 数据契约内，本轮未生成伪数据模板。

## 验收口径

- 业务模板 ID 不符合六类后缀时，Provider Bundle 加载失败。
- Wide 后缀只能进入 2x4；其余四类只能进入 2x2。
- 任一主数据或次要数据在 TaskSpec 中缺失时，模板不准入。
- 三组数据路径必须分别唯一且互不重叠。
- 模板 `$path` 只能引用主数据或次要数据；`$optionalPath` 只能引用可选数据。
- 模板展开前确定性校验布局尺寸、业务模板数量、Action 数量和 Action 类型。
- Earphone 与 Calendar 均已启用并进入线上候选。
