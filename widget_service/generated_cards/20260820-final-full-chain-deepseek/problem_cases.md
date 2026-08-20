# DeepSeek 完整链路测试报告（新版契约）

- 测试数：100
- 成功 A2UI：71（文件在 `a2ui/`）
- 模板直出：30
- 明确记录为全量生成成功：21
- 需要人工复核的样本：49

说明：测试集已按当前 provider 数据根路径、requiredData 和 capability 契约迁移。下面每条均列出用户请求、实际候选数据及真实链路结果。

## 问题样本

### TRE-019 — 显示今天日期和星期几

- 预期：阶段 `retrieval`；模板 `DateOverviewDateHero@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/startDate, /updatedAt。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-019.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=family-weather-care-blue；它要求展示：GetCalendarEvents: /events/0/startDate。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-020 — 来一个暖黄色的今天日期卡

- 预期：阶段 `retrieval`；模板 `DateOverviewDateHero@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/startDate, /updatedAt。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-020.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=focus-warm-amber；它要求展示：（空）。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-021 — 做一张下一个会议提醒，必须显示会议标题和开始结束时间

- 预期：阶段 `retrieval`；模板 `ScheduleOverviewNextEvent@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/eventLocation。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-021.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=meeting-paper-neutral；它要求展示：GetCalendarEvents: /events/0/title, /events/0/dtStart, /events/0/dtEnd。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-022 — 显示下一场日程的标题、时间和地点

- 预期：阶段 `retrieval`；模板 `ScheduleOverviewNextEventLocation@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/eventLocation。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-022.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=meeting-paper-neutral；它要求展示：GetCalendarEvents: /events/0/title, /events/0/dtStart, /events/0/eventLocation。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-023 — 给我做个专注风格的下一场会议卡，只看标题和时间

- 预期：阶段 `retrieval`；模板 `ScheduleOverviewNextEvent@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-023.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=focus-warm-amber；它要求展示：GetCalendarEvents: /events/0/title, /events/0/dtStart。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-024 — 今天有什么安排，显示第一条日程标题

- 预期：阶段 `retrieval`；模板 `ScheduleOverviewNextEvent@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-024.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=meeting-paper-neutral；它要求展示：GetCalendarEvents: /events/0/title。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-026 — 日程卡必须显示参会人

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/attendees。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：日程能力的 outputSchema 没有 /events/0/attendees（参会人）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-027 — 日程提醒里要有会议号

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/conferenceId。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：日程能力的 outputSchema 没有 /events/0/conferenceId（会议号）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-028 — 做日期卡，显示上次同步时间

- 预期：阶段 `retrieval`；模板 `DateOverviewDateHero@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/startDate, /updatedAt。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-028.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=meeting-paper-neutral；它要求展示：GetCalendarEvents: /updatedAt。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-031 — 用睡眠夜紫主题显示下一场会议

- 预期：阶段 `retrieval`；模板 `ScheduleOverviewNextEvent@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-031.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=sleep-night-violet；它要求展示：GetCalendarEvents: /events/0/title, /events/0/dtStart, /events/0/dtEnd。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-032 — 做一个只显示今天日期的2x2卡

- 预期：阶段 `retrieval`；模板 `DateOverviewDateHero@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/startDate, /updatedAt。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-032.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=family-weather-care-blue；它要求展示：GetCalendarEvents: /events/0/startDate。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-036 — 倒计时里必须写出目标日期

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/countdown`。
- 实际候选数据：GetCountdownDays 写入 /data/countdown，可用字段：/countdownDays, /targetDate。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：倒计时能力的 outputSchema 没有 /targetDate（目标日期）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-037 — 倒计时卡要显示进度百分比

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/countdown`。
- 实际候选数据：GetCountdownDays 写入 /data/countdown，可用字段：/countdownDays, /progressPercent。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：倒计时能力的 outputSchema 没有 /progressPercent（进度百分比）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-039 — 做个屏幕使用时间卡，显示应用名称和今天用了多久

- 预期：阶段 `retrieval`；模板 `AppUsageOverviewSingleApp@1`；尺寸 `/data/appUsageStats`。
- 实际候选数据：GetAppUsageDuration 写入 /data/appUsageStats，可用字段：/appUsage/appName, /appUsage/durationText。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-040 — 暖黄色风格显示我今天刷短视频用了多久

- 预期：阶段 `retrieval`；模板 `AppUsageOverviewSingleApp@1`；尺寸 `/data/appUsageStats`。
- 实际候选数据：GetAppUsageDuration 写入 /data/appUsageStats，可用字段：/appUsage/appName, /appUsage/durationText。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-040.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=focus-warm-amber；它要求展示：GetAppUsageDuration: /appUsage/appName, /appUsage/durationText。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-041 — 做一个应用使用概览，显示应用名

- 预期：阶段 `retrieval`；模板 `AppUsageOverviewSingleApp@1`；尺寸 `/data/appUsageStats`。
- 实际候选数据：GetAppUsageDuration 写入 /data/appUsageStats，可用字段：/appUsage/appName, /appUsage/durationText。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-042 — 应用使用卡还要展示今天的使用上限和剩余时长

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/appUsageStats`。
- 实际候选数据：GetAppUsageDuration 写入 /data/appUsageStats，可用字段：/appUsage/appName, /appUsage/durationText, /dailyLimitText, /remainingTimeText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：应用使用时长能力没有 /dailyLimitText 和 /remainingTimeText（上限、剩余时长）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-043 — 应用使用卡显示上次更新时间

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/appUsageStats`。
- 实际候选数据：GetAppUsageDuration 写入 /data/appUsageStats，可用字段：/appUsage/appName, /appUsage/durationText, /updatedAt。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-044 — 做一张2x4的应用使用时长卡

- 预期：阶段 `retrieval`；模板 `AppUsageOverviewSingleAppWide@1`；尺寸 `/data/appUsageStats`。
- 实际候选数据：GetAppUsageDuration 写入 /data/appUsageStats，可用字段：/appUsage/appName, /appUsage/durationText。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-044.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=digital-wellbeing-neutral-dark；它要求展示：GetAppUsageDuration: /appUsage/appName, /appUsage/durationText。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-047 — 给我一个低电量蓝牙耳机卡，显示总电量

- 预期：阶段 `retrieval`；模板 `BluetoothDeviceOverviewEarbuds@1`；尺寸 `/data/earphone`。
- 实际候选数据：GetEarphoneInfo 写入 /data/earphone，可用字段：/isConnected, /earphoneName, /batteryLevel, /leftBatteryLevel, /rightBatteryLevel。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-047.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=audio-product-neutral-violet；它要求展示：GetEarphoneInfo: /batteryLevel。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-052 — 耳机卡要展示降噪模式

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/earphone`。
- 实际候选数据：GetEarphoneInfo 写入 /data/earphone，可用字段：/isConnected, /earphoneName, /noiseCancelMode。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：耳机能力没有 /noiseCancelMode（降噪模式）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-053 — 耳机连接状态用会议纸张主题展示

- 预期：阶段 `retrieval`；模板 `BluetoothDeviceOverviewConnection@1`；尺寸 `/data/earphone`。
- 实际候选数据：GetEarphoneInfo 写入 /data/earphone，可用字段：/isConnected, /earphoneName。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFFFF5EF",0],["#FFFFFCF8",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-059 — 电量卡必须显示预计充满时间

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/phoneBattery`。
- 实际候选数据：GetPhoneBatteryInfo 写入 /data/phoneBattery，可用字段：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc, /estimatedFullTimeText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：电池能力没有 /estimatedFullTimeText（预计充满时间）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-060 — 电量卡要有电池健康度

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/phoneBattery`。
- 实际候选数据：GetPhoneBatteryInfo 写入 /data/phoneBattery，可用字段：/batterySOC, /batterySOCText, /batteryHealthText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：电池能力没有 /batteryHealthText（电池健康度）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-067 — 昨晚平均心率是多少

- 预期：阶段 `retrieval`；模板 `HeartRateOverviewHero@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/exerciseHeartRateAvg, /updatedAt。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-067.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=device-clean-blue-teal；它要求展示：GetHealthAndSportSummary: /exerciseHeartRateAvg。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-068 — 做一个心率卡，平均心率和更新时间都要有

- 预期：阶段 `retrieval`；模板 `HeartRateOverviewHeroUpdated@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/exerciseHeartRateAvg, /updatedAt。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-069 — 我要睡眠时长卡，重点显示昨晚睡了多久

- 预期：阶段 `retrieval`；模板 `SleepOverviewDuration@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/nightSleepDurationText, /sleepStatus, /fallAsleepTimeText, /wakeupTimeText。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-069.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=sleep-night-violet；它要求展示：GetHealthAndSportSummary: /nightSleepDurationText。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-070 — 显示昨晚睡眠时长和睡眠状态

- 预期：阶段 `retrieval`；模板 `SleepOverviewInsufficient@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/nightSleepDurationText, /sleepStatus。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-070.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=sleep-night-violet；它要求展示：GetHealthAndSportSummary: /nightSleepDurationText, /sleepStatus。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-071 — 做一张2x4睡眠作息卡，显示入睡、起床和睡眠时长

- 预期：阶段 `retrieval`；模板 `SleepOverviewSchedule@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/nightSleepDurationText, /fallAsleepTimeText, /wakeupTimeText。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-071.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=sleep-night-violet；它要求展示：GetHealthAndSportSummary: /nightSleepDurationText, /fallAsleepTimeText, /wakeupTimeText。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-074 — 运动卡必须展示配速

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/exerciseTypeName, /exerciseDurationText, /exerciseCalorieText, /paceText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：运动健康能力没有 /paceText（配速）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-075 — 睡眠卡要有睡眠评分和各阶段图

- 预期：阶段 `preflight_reject`；模板 `None`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/nightSleepDurationText, /sleepScore, /sleepStages。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是输入契约问题，不是模板漏画：运动健康能力虽有 /sleepScore，但没有 /sleepStages（睡眠阶段图）。 服务在生成前拒绝了这份候选字段列表，所以没有调用 DeepSeek，也不会产生 A2UI。

### TRE-076 — 显示平均心率

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/exerciseHeartRateAvg。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-080 — 我要一张深色专注风的平均心率卡

- 预期：阶段 `retrieval`；模板 `HeartRateOverviewHero@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/exerciseHeartRateAvg。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-080.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=focus-warm-amber；它要求展示：GetHealthAndSportSummary: /exerciseHeartRateAvg。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-081 — 做一张内存占用卡，显示占用比例、可用内存和总内存

- 预期：阶段 `unsupported_capability`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是当前设备能力清单缺口：测试写了 GetSystemMemInfo，但 app-11.7.5.205_rom-6.0 的 capability registry 没有注册它。Provider 文件存在不等于运行时设备可调用；请求在模型前被拒绝。

### TRE-082 — 系统内存还剩多少，给我蓝色卡

- 预期：阶段 `unsupported_capability`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是当前设备能力清单缺口：测试写了 GetSystemMemInfo，但 app-11.7.5.205_rom-6.0 的 capability registry 没有注册它。Provider 文件存在不等于运行时设备可调用；请求在模型前被拒绝。

### TRE-083 — 内存卡要展示存储空间使用情况

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText, /storageUsagePercent。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：请求在完整链路的前置校验阶段抛出异常：ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type

### TRE-084 — 显示内存占用趋势和历史曲线

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText, /usageTrend。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：请求在完整链路的前置校验阶段抛出异常：ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type

### TRE-085 — 系统内存占用

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：请求在完整链路的前置校验阶段抛出异常：ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type

### TRE-086 — 用赛跑主题做内存使用卡

- 预期：阶段 `unsupported_capability`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：这是当前设备能力清单缺口：测试写了 GetSystemMemInfo，但 app-11.7.5.205_rom-6.0 的 capability registry 没有注册它。Provider 文件存在不等于运行时设备可调用；请求在模型前被拒绝。

### TRE-087 — 内存卡显示可用内存

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/systemMemory`。
- 实际候选数据：GetSystemMemInfo 写入 /data/systemMemory，可用字段：/usagePercent, /availableMemText, /totalMemText。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：请求在完整链路的前置校验阶段抛出异常：ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type

### TRE-090 — 显示股票价格和涨跌

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/stock`。
- 实际候选数据：GetStockQuote 写入 /data/stock，可用字段：/price, /changePercent。
- 实际结果：路由 `template_route_failed`，服务状态 `exception`，A2UI `无`。
- 具体原因：请求在完整链路的前置校验阶段抛出异常：ValidationError: 1 validation error for GenerateWidgetCardRequest
candidateDataBindings.0.arguments
  Input should be a valid dictionary [type=dict_type, input_value='测试值', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/dict_type

### TRE-091 — 做天气卡显示温度

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/weather`。
- 实际候选数据：ViewWeather 写入 /data/weather，可用字段：/current/temperatureText。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-092 — 做一个天气卡

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/weather`。
- 实际候选数据：ViewWeather 写入 /data/weather，可用字段：/current/temperatureText。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-093 — 做天气卡显示温度

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/weather`。
- 实际候选数据：ViewWeather 写入 /data/weather，可用字段：/current/temperatureText。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-094 — 做天气卡显示温度

- 预期：阶段 `retrieval`；模板 `None`；尺寸 `/data/weather`。
- 实际候选数据：ViewWeather 写入 /data/weather，可用字段：/current/temperatureText；ViewWeather 写入 /data/weatherBackup，可用字段：/current/temperatureText。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFDCEEFF",0],["#FFF4FAFF",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-095 — 显示下一场会议的标题和时间

- 预期：阶段 `retrieval`；模板 `ScheduleOverviewNextEvent@1`；尺寸 `/data/calendar`。
- 实际候选数据：GetCalendarEvents 写入 /data/calendar，可用字段：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/eventLocation。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-095.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=meeting-paper-neutral；它要求展示：GetCalendarEvents: /events/0/title, /events/0/dtStart。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-096 — 看睡眠时长

- 预期：阶段 `retrieval`；模板 `SleepOverviewDuration@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/nightSleepDurationText, /sleepStatus, /fallAsleepTimeText, /wakeupTimeText。
- 实际结果：路由 `template_route_failed`，服务状态 `success`，A2UI `a2ui/TRE-096.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=sleep-night-violet；它要求展示：GetHealthAndSportSummary: /nightSleepDurationText。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。

### TRE-097 — 显示平均心率

- 预期：阶段 `retrieval`；模板 `HeartRateOverviewHero@1`；尺寸 `/data/healthSport`。
- 实际候选数据：GetHealthAndSportSummary 写入 /data/healthSport，可用字段：/exerciseHeartRateAvg, /updatedAt。
- 实际结果：路由 `full_generation_failed`，服务状态 `failed`，A2UI `无`。
- 具体原因：DeepSeek 已进入全量生成，但生成结果没通过 A2UI/DSL 校验（服务码 VALIDATION_FAILED）：卡片生成过程中校验失败，请稍后再试。。模型输出开头是：```genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"linearGradient":{"direction":"RightBottom","colors":[["#FFE2F6EE",0],["#FFF8FCFA",1]]},"justifyContent":"spaceBetween","alignItems":"center"},["

### TRE-098 — 做一个耳机连接状态卡

- 预期：阶段 `retrieval`；模板 `BluetoothDeviceOverviewConnection@1`；尺寸 `/data/earphone`。
- 实际候选数据：GetEarphoneInfo 写入 /data/earphone，可用字段：/isConnected, /earphoneName, /batteryLevel。
- 实际结果：路由 `full_generation_success`，服务状态 `success`，A2UI `a2ui/TRE-098.a2ui`。
- 具体原因：测试预期能用模板直出，但本次实际没有直出；已仍然成功得到 A2UI。DeepSeek 检索调用输出 themeId=audio-product-neutral-violet；它要求展示：GetEarphoneInfo: /isConnected, /earphoneName, /batteryLevel。 这表示当前具体请求、字段集合或卡片尺寸没有落到可直接编译的模板候选上，需要按该条的字段和尺寸复核。
