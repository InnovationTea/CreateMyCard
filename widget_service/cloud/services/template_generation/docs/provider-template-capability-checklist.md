# Provider 模板能力整改 Checklist

> 本表以各业务 `provider.json` 为事实源；主数据和次要数据均为硬必选数据，只有可选数据允许缺省。

## 整改总览

- [x] 170 个业务模板全部使用 `HeroTitle`、`HeroContent`、`Support`、`Compact`、`Hero`、`Full`、`WideHero`、`WideFull`、`WideHalf` 后缀。
- [x] 业务模板尺寸和动作组合由后缀推导，不再由 Provider 重复声明。
- [x] Provider 数据统一拆为 `primaryData`、`secondaryData`、`optionalData`。
- [x] `primaryData` 与 `secondaryData` 均参与模板准入硬校验。
- [x] Search 按数据覆盖返回 Support 等全部尺寸可用模板；Planner 可选择双 Support，并把 Action 分配给
  支持 `actionId` 的垂域模板，也可选择 HeroTitle + HeroContent + 单 PillAction；Compact 使用双
  PillAction；Full 用于无 Action，或搭配一个 IconAction。
- [x] PillAction/IconAction/CompactSubtitleAction 使用独立 Action Provider 模板，第二层只输出批准的展示 Props。
- [x] 第一层支持选择零到两个不重复 eventId。
- [x] 每个业务模板均在 `provider.json` 中声明主数据、次要数据、可选数据和布局场景。

## 布局后缀

| 后缀 | 布局及组合场景 | 卡片尺寸 |
| --- | --- | --- |
| HeroTitle | 双业务单 Action 的位置 0；后接 HeroContent | 2x2 |
| HeroContent | 双业务单 Action 的位置 1；前置 HeroTitle | 2x2 |
| Support | 约 2x1；由 Planner 组成双 Support，可在业务内部消费 Action | 2x2 |
| Compact | 约 2x1；单 Compact + 2 个 PillAction | 2x2 |
| Hero | 约 2x1.7；Hero + 1 个 PillAction；2x4 双焦点布局中可在根节点内嵌底板事件 | 2x2 |
| Full | 完整 2x2；无 Action，或 Full + 1 个 IconAction | 2x2 |
| WideHero | 约 4x1.7；WideHero + 1 个 PillAction | 2x4 |
| WideFull | 完整 4x2；单 WideFull | 2x4 |
| WideHalf | 约 4x1；用于 2x4 半高组合布局 | 2x4 |

## 业务与运行状态

| Provider | 数据能力 | 数据根 | 模板数 | 当前状态 |
| --- | --- | --- | ---: | --- |
| battery | `GetPhoneBatteryInfo` | `/data/phoneBattery` | 25 | 启用 |
| calendar | `GetCalendarEvents` | `/data/calendar` | 31 | 启用 |
| countdown | `GetCountdownDays` | `/data/countdown` | 11 | 启用 |
| earphone | `GetEarphoneInfo` | `/data/earphone` | 27 | 启用 |
| health-sport | `GetHealthAndSportSummary` | `/data/healthSport` | 38 | 启用 |
| system-memory | `GetSystemMemInfo` | `/data/systemMem` | 3 | 启用 |
| weather | `ViewWeather` | `/data/weather` | 39 | 启用 |

下方列出主要形态及本轮调整的 Support；非 Support 条目保留原有摘要，
精确全集以当前 `provider.json` 为准。Support 与 Compact 不要求一一对应；Search 只判断数据可用性，
双业务布局与 Action 消费位置统一由 Planner 决定。

应用使用时长能力已下线，其 6 个模板和专属主题已移出运行目录；历史设计见 Git 历史。

## BatteryOverview

- Provider：`com.huawei.battery.cli`；运行状态：启用。
- 数据能力：`GetPhoneBatteryInfo`；模板数：24。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BatteryOverviewPercentRingHero@1` | 约 2x1.7；百分比环 Hero + 1 个 PillAction | `/batterySOC` | 无 | 无 |
| ✅ | `BatteryOverviewPercentRingCompact@1` | 约 2x1；圆角底板内左侧 20vp 电量百分比大字与“手机电量”辅行，右侧 40vp 电量环、可选 16vp 内图标，不展示充电状态；用于宽版右列 2x1 组合槽位 | `/batterySOC` | 无 | 无 |
| ✅ | `BatteryOverviewPercentStatusCompact@1` | 约 2x1；圆角底板内左侧电量百分比大字与充电状态辅行，右侧 40vp 电量环、可选 16vp 内图标，不展示标题；用于宽版右列 2x1 组合槽位 | `/batterySOC` | `/chargingStatusDesc` | 无 |
| ✅ | `BatteryOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewHero@1` | 约 2x1.7；2x2 Hero + 1 个 PillAction | `/batterySOC` | `/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewWideFull@1` | 完整 4x2；单 WideFull | `/batterySOC`<br>`/batterySOCText` | `/chargingStatusDesc`<br>`/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewCompact@1` | 约 2x1；36vp 环形进度 Compact + 2 个 PillAction，电量图标可选 | `/batterySOC` | `/chargingStatusDesc` | 无 |
| ✅ | `BatteryOverviewSupport@1` | 约 2x1；左侧文本（充电状态可选辅行，缺失时回退展示电池温度，均缺失时单行），右侧 40vp 环、可选 16vp 内图标，事件在模板内部 | `/batterySOC` | 无 | `/chargingStatusDesc`<br>`/batterySOCText`<br>`/batteryTemperatureText` |
| ✅ | `BatteryOverviewStatusSupport@1` | 约 2x1；左侧双行文本展示充电状态与充电器类型，右侧可选 24vp 电池图标，事件在模板内部 | `/chargingStatusDesc` | `/pluggedTypeDesc` | 无 |
| ✅ | `BatteryOverviewStatusHero@1` | 约 2x2 焦点面板；顶部“手机电量”标签行 + 电量大字 + 充电状态辅行，用于 `WideTwoFocus` 系列双焦点布局 | `/batterySOC` | `/chargingStatusDesc` | 无 |
| ✅ | `BatteryOverviewChargingProgressHero@1` | 约 2x1.7；充电状态 Hero + 1 个 PillAction | `/batterySOCText` | 无 | `/chargingStatusDesc`<br>`/healthStatusDesc` |
| ✅ | `BatteryOverviewHealthLevelHero@1` | 约 2x1.7；电池体检 Hero + 1 个 PillAction | `/healthStatusDesc` | `/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewPercentLevelHero@1` | 单电量 2×2；旧模板无完整覆盖且显式要求文本百分比与等级时，Hero + 1 个 PillAction | `/batterySOCText` | `/batteryCapacityLevelDesc` | 无 |
| ✅ | `BatteryOverviewChargingProgressFull@1` | 完整 2x2；充电进度单 Full | `/batterySOC` | `/chargingStatusDesc`<br>`/healthStatusDesc`<br>`/pluggedTypeDesc` | 无 |
| ✅ | `BatteryOverviewChargingDiagnosticsHero@1` | 约 2x1.7；充电诊断 Hero + 1 个 PillAction | `/nowCurrentText`<br>`/voltageText` | `/batteryCapacityLevelDesc`<br>`/isBatteryPresentText` | 无 |
| ✅ | `BatteryOverviewChargingDiagnosticsWideFull@1` | 完整 4x2；充电诊断 WideFull，标题+图标+电量进度条+三胶囊，无 Action | `/batterySOC` | `/nowCurrentText`<br>`/voltageText`<br>`/isBatteryPresentText` | 无 |
| ✅ | `BatteryOverviewChargingRingHero@1` | 约 2x1.7；充电状态环 Hero + 1 个 PillAction | `/batterySOC` | `/chargingStatusDesc` | 无 |
| ✅ | `BatteryOverviewChargeStatusHero@1` | 约 2x2 焦点面板；顶部标题（默认“手机”，电池温度可用时替换为电池温度文本）+ 44vp 电量环（可选手机图标）+ 百分比标题和“手机电量”副标题，不展示充电状态与充电器类型 | `/batterySOC` | 无 | `/chargingStatusDesc`<br>`/pluggedTypeDesc`<br>`/batteryTemperatureText` |
| ✅ | `BatteryOverviewSupportHero@1` | 约 1.5x2 竖版电量面板（预留 1.5x2 槽位）；内部元素与 Support 一致：左侧电量主行 + 可选辅行（充电状态优先，回退电池温度），右侧 40vp 电量环、可选 16vp 手机图标，事件在模板内部 | `/batterySOC` | 无 | `/chargingStatusDesc`<br>`/batterySOCText`<br>`/batteryTemperatureText` |
| ✅ | `BatteryOverviewTemperatureFull@1` | 完整 2x2；电池温度单 Full | `/batteryTemperatureText` | `/pluggedTypeDesc`<br>`/updatedAt` | 无 |
| ✅ | `BatteryOverviewStatusWideFull@1` | 完整 4x2；左侧电量环+百分比+充电器状态（可选），右侧电池温度（可选）与电池健康信息块，两个信息块右侧各支持可选 24vp 图标（`temperatureIcon`/`healthIcon`），事件在模板内部 | `/batterySOC` | 无 | `/healthStatusDesc`<br>`/batteryTemperatureText`<br>`/pluggedTypeDesc`<br>`/chargingStatusDesc` |
| ✅ | `BatteryOverviewTemperatureHero@1` | 约 2x1.7 焦点面板；顶部手机电池温度标题行（温度图标可选）+ 温度大字 + 充电状态/充电器辅行，用于 `WideTwoFocus` 系列双焦点布局 | `/batteryTemperatureText` | 无 | `/pluggedTypeDesc`<br>`/chargingStatusDesc` |
| ✅ | `BatteryOverviewTemperatureRingHero@1` | 约 2x1.7 面板；标题行展示电池温度，中部电量环在左、环内固定 16x16 电池图标（必选 `batteryIcon`）、百分比与充电状态在右，用于 `WideFullHeroAction` 系列布局 | `/batterySOC` | `/batteryTemperatureText` | `/chargingStatusDesc` |

## CalendarOverview

- Provider：`com.huawei.calendar.cli`；运行状态：启用。
- 数据能力：`GetCalendarEvents`；模板数：31。
- 当前没有 Compact；真实日期通过 `ScheduleOverviewDateFull@1` 或
  `ScheduleOverviewDatedMeetingHero@1` 与同一首项日程共同展示。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ScheduleOverviewNextEventHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewReminderHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/title` | `/events/0/dtStart`<br>`/events/0/remindTime/0` | 无 |
| ✅ | `ScheduleOverviewTimezoneFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/events/0/timeZone`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewDateFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/events/0/startDate`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewDatedMeetingHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/events/0/startDate`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewHeroContent@1` | 双业务单 Action 的位置 1 | `/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewNextEventLocationFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/eventLocation` | `/events/0/dtEnd` |
| ✅ | `ScheduleOverviewTimezoneTimeFull@1` | 完整 2x2；沿用时区日期日程版式 | `/events/0/timeZone`<br>`/events/0/title` | `/events/0/dtStart`<br>`/events/0/dtEnd` | 无 |
| ✅ | `ScheduleOverviewDateLocationFull@1` | 完整 2x2；沿用时区日期日程版式 | `/events/0/startDate`<br>`/events/0/title` | `/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewReminderDetailsFull@1` | 完整 2x2；沿用时区日期日程版式 | `/events/0/senderName` | `/events/0/importantEventType`<br>`/events/0/remindTime/0`<br>`/updatedAt` | 无 |
| ✅ | `ScheduleOverviewMeetingWideFull@1` | 完整 4x2；单 WideFull | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewMeetingSourceWideFull@1` | 完整 4x2；单 WideFull | `/events/0/title`<br>`/events/0/dtStart` | `/events/0/dtEnd`<br>`/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewTimeSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/events/0/dtStart` | 无 | `/events/0/title`<br>`/events/0/dtEnd`<br>`/events/0/eventLocation` |
| ✅ | `ScheduleOverviewLocationSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/events/0/title` | `/events/0/eventLocation` | 无 |
| ✅ | `ScheduleOverviewStartTimeSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/events/0/title` | `/events/0/dtStart` | 无 |
| ✅ | `ScheduleOverviewDateSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/events/0/title` | `/events/0/startDate` | 无 |
| ✅ | `ScheduleOverviewMeetingSenderFull@1` | 完整 2x2；作为 2x4 组合布局的整列 Full 槽位（如 WideFullTwoCompactLayout），不内嵌 Action；标题 14vp/700，副标题 10vp/400 | `/events/0/dtStart` | `/events/0/eventLocation` | `/events/0/title`<br>`/events/0/dtEnd` |

## CountdownOverview

- Provider：`com.huawei.countdown.cli`；运行状态：启用。
- 数据能力：`GetCountdownDays`；模板数：11；当前没有 Compact。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `CountdownOverviewFull@1` | 完整 2x2；无 Action，或加一个 IconAction | `/countdownDays` | 无 | 无 |
| ✅ | `CountdownOverviewWideFull@1` | 完整 4x2；单 WideFull 或 Full 组合布局 | `/countdownDays` | 无 | 无 |
| ✅ | `CountdownOverviewWideHero@1` | 约 4x1.7；WideHero + 1 个 PillAction | `/countdownDays` | 无 | 无 |
| ✅ | `CountdownOverviewWideHalf@1` | 约 4x1；用于 2x4 半高组合布局 | `/countdownDays` | 无 | 无 |
| ✅ | `CountdownOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/countdownDays` | 无 | 无 |
| ✅ | `CountdownOverviewTravelSupport@1` | 双 Support；出行倒计时，可选计时图标，可内嵌闹钟跳转 | `/countdownDays` | 无 | 无 |
| ✅ | `CountdownOverviewSupport@1` | 约 2x1；双 Support，可选计时图标，事件在模板内部 | `/countdownDays` | 无 | 无 |

## BluetoothDeviceOverview

- Provider：`com.huawei.earphone.cli`；运行状态：启用。
- 数据能力：`GetEarphoneInfo`；模板数：25。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `BluetoothDeviceOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/isConnected`<br>`/earphoneName` | 无 | `/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsPhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | 无 | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsDynamicWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | 无 | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudsSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 | 无 |
| ✅ | `BluetoothDeviceOverviewConnectionSupport@1` | 约 2x1；连接状态主行加粗、可选仓电量次行与 40vp 电量环，事件在模板内部 | `/isConnected` | 无 | `/batteryLevel` |
| ✅ | `BluetoothDeviceOverviewEarbudPairFull@1` | 完整 2x2；无 Action 或加一个 IconAction | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 | `/isConnected`<br>`/earphoneName`<br>`/leftChargingStatusDesc`<br>`/rightChargingStatusDesc`<br>`/chargingStatusDesc`（三项齐全才展示） |
| ✅ | `BluetoothDeviceOverviewCompleteWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarbudPairCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/earphoneName` | `/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewCompletePhoneWideFull@1` | 完整 4x2；单 WideFull | `/isConnected`<br>`/earphoneName` | `/batteryLevel`<br>`/leftBatteryLevel`<br>`/rightBatteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarphoneCaseHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/batteryLevel` | `/chargingStatusDesc` | 无 |
| ✅ | `BluetoothDeviceOverviewEarphoneCaseCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/batteryLevel` | `/chargingStatusDesc` | 无 |
| ✅ | `BluetoothDeviceOverviewCaseConnectionCompact@1` | 约 2x1；主行连接状态加粗、次行充电盒电量，可选充电盒图标；用于宽版右列 2x1 组合槽位 | `/isConnected`<br>`/batteryLevel` | 无 | 无 |
| ✅ | `BluetoothDeviceOverviewMusicCompact@1` | 约 2x1；歌单入口：标题打开歌单、副标题播放我的收藏，右侧 24vp 音乐图标，根节点绑定收藏歌单事件；不展示耳机数据，仅作宽版右列伴生动作槽位 | 无 | 无 | 无 |
| ✅ | `BluetoothDeviceOverviewEarphoneHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/earphoneName` | `/batteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewEarphoneCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/earphoneName` | `/batteryLevel` | 无 |
| ✅ | `BluetoothDeviceOverviewChargeSupport@1` | 约 2x1；左侧双行文本（电量可选，缺失时省略电量行与电量环），右侧 40vp 环与 16vp 盒图标，事件在模板内部 | 无 | `/chargingStatusDesc` | `/batteryLevel` |

## ActivityOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：11。
- 展示说明：Compact 只展示每日步数；Hero 展示步数和固定万步基准进度；2x2 Full 还以文字展示热量和距离，
  三者均只接受可选步数图标。Wide 模板继续保留热量和距离图标槽位。
  目标进度 WideFull 以固定八千步目标展示步数进度，底部三格展示距离、热量和更新时间，仅接受可选步数图标。
  昨日活动睡眠 Compact 为 2x4 组合右侧单行双指标面板（昨日步数、昨晚睡眠得分，参考 Q069 深睡小睡
  布局，无图标），歌单动作由根 `CompactAction@1` 承载。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ActivityOverviewYesterdayStepsSleepCompact@1` | 约 2x1；2x4 组合右侧单行双指标面板（如 WideFullTwoCompactLayout），两行标签在左、数值在右：昨日步数加“步”单位、昨晚睡眠得分加“分”单位，无图标无内嵌动作 | `/dailySteps` | `/sleepScore` | 无 |
| ✅ | `ActivityOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/dailySteps` | 无 | 无 |
| ✅ | `ActivityOverviewWideHero@1` | 约 4x1.7；WideHero + 1 个 PillAction | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText`<br>`/targetDateText` | 无 |
| ✅ | `ActivityOverviewFull@1` | 完整 2x2；无 Action 的单 Full；作为 2x4 组合槽位时不展示右上角步数图标（`stepsIcon` 按尺寸隐藏） | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText` | 无 |
| ✅ | `ActivityOverviewWideFull@1` | 完整 4x2；单 WideFull | `/dailySteps` | `/dailyTotalCaloriesText`<br>`/dailyDistanceText`<br>`/targetDateText` | 无 |
| ✅ | `ActivityOverviewGoalProgressWideFull@1` | 完整 4x2；目标进度 WideFull，标题+可选步数图标+步数大字与固定八千步目标线性进度条+距离/热量/更新时间三胶囊，无 Action | `/dailySteps` | `/dailyDistanceText`<br>`/dailyTotalCaloriesText`<br>`/updatedAt` | 无 |
| ✅ | `ActivityOverviewSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/dailySteps` | 无 | 无 |

## WorkoutOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：6。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WorkoutOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseDurationText` | `/exerciseCalorieText` | `/exerciseEndTimeText`<br>`/exerciseTypeName` |
| ✅ | `WorkoutOverviewSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/exerciseCalorieText` | `/exerciseDurationText` | `/exerciseTypeName` |

## HeartRateOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：10。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `HeartRateOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewMinMaxFull@1` | 完整 2x2；无 Action 的单 Full | `/exerciseHeartRateMax`<br>`/exerciseHeartRateMin` | 无 | `/updatedAt` |
| ✅ | `HeartRateOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewIconCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/exerciseHeartRateAvg` | 无 | 无 |
| ✅ | `HeartRateOverviewSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/exerciseHeartRateAvg` | 无 | 无 |

## SleepOverview

- Provider：`com.huawei.health-sport.cli`；运行状态：启用。
- 数据能力：`GetHealthAndSportSummary`；模板数：9。
- 展示说明：Compact 以得分环展示时长和得分；Hero 展示时长，并按得分、状态、完整睡眠时段的顺序
  选择一个补充区域；Full 展示时长和状态，可选展示得分或完整睡眠时段。时段仅在入睡、醒来时刻
  同时存在时展示，三者均可使用睡眠图标。
  昨日睡眠 Compact 已并入昨日活动睡眠双指标面板（见 ActivityOverview），歌单动作由根
  `CompactAction@1` 承载。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `SleepOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/nightSleepDurationText` | `/sleepStatus` | `/sleepScore`<br>`/fallAsleepTimeText`<br>`/wakeupTimeText` |
| ✅ | `SleepOverviewScoreFull@1` | 完整 2x2；无 Action 的单 Full，宽版下用于通栏槽位：顶部睡眠健康状态、大号得分数字、底部总睡眠行（深睡眠可选） | `/sleepScore` | `/nightSleepDurationText` | `/sleepStatus`<br>`/deepSleepDurationText` |
| ✅ | `SleepOverviewScoreDetailWideFull@1` | 完整 2x4；无 Action 的单 WideFull：左侧大号得分数字配“睡眠得分”副标题和睡眠状况行，右侧两个带图标的胶囊块——上块总睡眠时长（时间大字+副标题），下块小睡时长和深睡眠时长（缺失时隐藏对应指标行或胶囊块） | `/sleepScore` | `/nightSleepDurationText` | `/sleepStatus`<br>`/totalNapDurationText`<br>`/deepSleepDurationText` |
| ✅ | `SleepOverviewHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/nightSleepDurationText` | 无 | `/sleepStatus`<br>`/sleepScore`<br>`/fallAsleepTimeText`<br>`/wakeupTimeText` |
| ✅ | `SleepOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/nightSleepDurationText` | `/sleepScore` | 无 |
| ✅ | `SleepOverviewSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/nightSleepDurationText` | 无 | 无 |

## ResourceUsageOverview

- Provider：`com.huawei.system-memory.cli`；运行状态：启用。
- 数据能力：`GetSystemMemInfo`；模板数：3。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `ResourceUsageOverviewFull@1` | 完整 2x2；无 Action 的单 Full | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |
| ✅ | `ResourceUsageOverviewCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/usagePercent` | `/availableMemText`<br>`/totalMemText` | 无 |

## WeatherOverview

- Provider：`com.huawei.weather.cli`；运行状态：启用。
- 数据能力：`ViewWeather`；模板数：39。

| 状态 | 模板 | 布局场景 | 主数据 | 次要数据 | 可选数据 |
| --- | --- | --- | --- | --- | --- |
| ✅ | `WeatherOverviewHeroTitle@1` | 双业务单 Action 的位置 0；左城市、右现象及温度 | 无 | 无 | `/location/prefectureName`<br>`/location/districtName`<br>`/current/temperatureText`<br>`/current/condition` |
| ✅ | `WeatherOverviewCompact@1` | 约 2x1；可选天气图标；Compact + 2 个 PillAction | `/current/temperatureText` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/coldLevel` |
| ✅ | `WeatherOverviewUvCompact@1` | 约 2x1；单 Compact + 2 个 PillAction | `/current/temperatureText`<br>`/current/uvIndex` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName` |
| ✅ | `WeatherOverviewTemperatureSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/current/condition` | 无 | `/current/temperatureText`<br>`/current/temperatureC`<br>`/current/feelsLikeC`<br>`/location/prefectureName`<br>`/location/districtName` |
| ✅ | `WeatherOverviewDaily2TravelSupport@1` | 约 2x1；后日出行天气双层信息块，可选温度计或天气状态图标 | `/daily/2/condition` | `/daily/2/temperatureRangeText` | 无 |
| ✅ | `WeatherOverviewTravelSupport@1` | 双 Support；ConditionHero 风格的出行天气主视觉，可选温度计或天气状态图标，可内嵌天气跳转 | 无 | 无 | `/daily/4/condition`<br>`/daily/4/temperatureRangeText`<br>`/daily/4/rainProbabilityPercent`<br>`/current/temperatureC`<br>`/current/condition` |
| ✅ | `WeatherOverviewTemperatureUvSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/current/temperatureText` | `/current/condition`<br>`/current/uvIndex` | `/location/prefectureName`<br>`/location/districtName` |
| ✅ | `WeatherOverviewHero@1` | 约 2x1.7；可选天气图标；Hero + 1 个 PillAction | `/current/temperatureText` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/coldLevel` |
| ✅ | `WeatherOverviewFull@1` | 完整 2x2；可选天气图标；无 Action 的单 Full | `/current/temperatureText` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/airQuality`<br>`/current/coldLevel` |
| ✅ | `WeatherOverviewHumidityFull@1` | 完整 2x2；无 Action 的单 Full | `/current/humidityPercent` | `/current/condition`<br>`/current/temperatureText` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/airQuality`<br>`/current/coldLevel` |
| ✅ | `WeatherOverviewUvFull@1` | 完整 2x2；无 Action 的单 Full | `/current/uvIndex` | `/current/condition`<br>`/current/temperatureText` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/airQuality`<br>`/current/coldLevel` |
| ✅ | `WeatherOverviewAirQualityHero@1` | 约 2x1.7；Hero + 1 个 PillAction | `/current/airQuality` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/coldLevel` |
| ✅ | `WeatherOverviewWideFull@1` | 完整 4x2；单 WideFull 或 Full 组合布局 | `/current/temperatureText` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/feelsLikeC`<br>`/current/humidityPercent`<br>`/current/airQuality`<br>`/current/windDirection`<br>`/current/windLevel`<br>`/daily/0/temperatureRangeText`<br>`/daily/0/rainProbabilityPercent` |
| ✅ | `WeatherOverviewWideHero@1` | 约 4x1.7；WideHero + 1 个 PillAction | `/current/temperatureText` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/feelsLikeC`<br>`/daily/0/temperatureRangeText`<br>`/daily/0/rainProbabilityPercent` |
| ✅ | `WeatherOverviewWideHalf@1` | 约 4x1；用于 2x4 半高组合布局 | `/current/temperatureText` | `/current/condition` | `/location/prefectureName`<br>`/location/districtName`<br>`/current/airQuality`<br>`/daily/0/rainProbabilityPercent` |
| ✅ | `WeatherOverviewConditionFeelsLikeAlertFull@1` | 完整 2x2；圆角底板内天气现象大字，底部体感温度（可选）与天气预警（可选，缺失展示无预警） | `/current/condition` | 无 | `/current/feelsLikeC`<br>`/current/alertLevel`<br>`/location/prefectureName`<br>`/location/districtName` |
| ✅ | `WeatherOverviewHumidityWindLevelHero@1` | 约 2x1.7 焦点面板；城市行+温度大字+空气湿度、风向风力与天气预警（可选）行，用于 `WideTwoFocus` 系列双焦点布局 | `/current/temperatureText`<br>`/current/humidityPercent` | `/current/windDirection`<br>`/current/windLevel` | `/current/alertLevel`<br>`/location/prefectureName`<br>`/location/districtName` |
| ✅ | `WeatherOverviewRainWindFull@1` | 完整 2x2；城市行+当天降水概率进度环，底部风力（风向可选） | `/daily/0/rainProbabilityPercent` | `/current/windLevel` | `/current/windDirection`<br>`/location/prefectureName`<br>`/location/districtName` |

说明：最新天气 UX 中的日出日落与 AQI 数值不在当前 `ViewWeather` 数据契约内，本轮未生成伪数据模板。
HeroTitle 的温度与现象均可选：同时可用时显示“现象 | 温度”，缺少其中之一时只显示另一项；两者都缺失时
只保留城市标题。其余天气模板仍按各自主数据和次要数据准入，不因标题模板的可选字段而放宽。
| ✅ | `WeatherOverviewTemperaturecoldLevelSupport@1` | 约 2x1；双 Support，事件在模板内部 | `/current/temperatureText` | `/current/condition`<br>`/current/coldLevel` | `/location/prefectureName`<br>`/location/districtName` |

## 验收口径

- 业务模板 ID 不符合上述八类后缀时，Provider Bundle 加载失败。
- Wide 后缀只能进入 2x4；其余六类只能进入 2x2。
- 任一主数据或次要数据在 TaskSpec 中缺失时，模板不准入。
- 三组数据路径必须分别唯一且互不重叠。
- 模板 `$path` 只能引用主数据或次要数据；`$optionalPath` 只能引用可选数据。
- 模板展开前确定性校验布局尺寸、业务模板数量、Action 数量和 Action 类型。
- Earphone 与 Calendar 均已启用并进入线上候选。

新增三电量模板（独立于既有成对模板）：

| 模板 | 展示 | 必需字段 |
| --- | --- | --- |
| `BluetoothDeviceOverviewEarbudTripleHero@1` | 三列图标电量及下方充电状态，单个 PillAction | 名称、三处电量；三处充电状态可选，齐全才显示 |

EarbudPairCompact 的可选字段：`/batteryLevel`、`/isConnected`；必需字段不变。
