# 非日期问题样本：用人话证据链分析

已排除：TRE-019、TRE-020、TRE-028、TRE-032、TRE-036（日期相关）。

每条均按“用户和数据 → 模型输出/发生位置 → 真实结果 → 结论”写；不以“检索不一致”代替原因。

### TRE-021｜做一张下一个会议提醒，必须显示会议标题和开始结束时间

1. 用户和数据：用户要“做一张下一个会议提醒，必须显示会议标题和开始结束时间”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/eventLocation。
2. 检索模型：GetCalendarEvents 要展示 /events/0/title, /events/0/dtStart, /events/0/dtEnd。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-021.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-022｜显示下一场日程的标题、时间和地点

1. 用户和数据：用户要“显示下一场日程的标题、时间和地点”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/eventLocation。
2. 检索模型：GetCalendarEvents 要展示 /events/0/title, /events/0/dtStart, /events/0/eventLocation。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-022.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-023｜给我做个专注风格的下一场会议卡，只看标题和时间

1. 用户和数据：用户要“给我做个专注风格的下一场会议卡，只看标题和时间”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd。
2. 检索模型：GetCalendarEvents 要展示 /events/0/title, /events/0/dtStart。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-023.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-024｜今天有什么安排，显示第一条日程标题

1. 用户和数据：用户要“今天有什么安排，显示第一条日程标题”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd。
2. 检索模型：GetCalendarEvents 要展示 /events/0/title。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-024.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-026｜日程卡必须显示参会人

1. 用户和数据：用户要“日程卡必须显示参会人”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/attendees。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/events/0/attendees`（参会人）不在 GetCalendarEvents 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-027｜日程提醒里要有会议号

1. 用户和数据：用户要“日程提醒里要有会议号”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/conferenceId。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/events/0/conferenceId`（会议号）不在 GetCalendarEvents 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-031｜用睡眠夜紫主题显示下一场会议

1. 用户和数据：用户要“用睡眠夜紫主题显示下一场会议”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd。
2. 检索模型：GetCalendarEvents 要展示 /events/0/title, /events/0/dtStart, /events/0/dtEnd。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-031.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-037｜倒计时卡要显示进度百分比

1. 用户和数据：用户要“倒计时卡要显示进度百分比”。本条实际给链路的数据是：GetCountdownDays → /data/countdown：/countdownDays, /progressPercent。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/progressPercent` 不在 GetCountdownDays 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-039｜做个屏幕使用时间卡，显示应用名称和今天用了多久

1. 用户和数据：用户要“做个屏幕使用时间卡，显示应用名称和今天用了多久”。本条实际给链路的数据是：GetAppUsageDuration → /data/appUsageStats：/appUsage/appName, /appUsage/durationText。
2. 检索模型：GetAppUsageDuration 要展示 /appUsage/appName, /appUsage/durationText。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-040｜暖黄色风格显示我今天刷短视频用了多久

1. 用户和数据：用户要“暖黄色风格显示我今天刷短视频用了多久”。本条实际给链路的数据是：GetAppUsageDuration → /data/appUsageStats：/appUsage/appName, /appUsage/durationText。
2. 检索模型：GetAppUsageDuration 要展示 /appUsage/appName, /appUsage/durationText。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-040.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-041｜做一个应用使用概览，显示应用名

1. 用户和数据：用户要“做一个应用使用概览，显示应用名”。本条实际给链路的数据是：GetAppUsageDuration → /data/appUsageStats：/appUsage/appName, /appUsage/durationText。
2. 检索模型：GetAppUsageDuration 要展示 /appUsage/appName。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-042｜应用使用卡还要展示今天的使用上限和剩余时长

1. 用户和数据：用户要“应用使用卡还要展示今天的使用上限和剩余时长”。本条实际给链路的数据是：GetAppUsageDuration → /data/appUsageStats：/appUsage/appName, /appUsage/durationText, /dailyLimitText, /remainingTimeText。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/dailyLimitText`、`/remainingTimeText` 不在 GetAppUsageDuration 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-043｜应用使用卡显示上次更新时间

1. 用户和数据：用户要“应用使用卡显示上次更新时间”。本条实际给链路的数据是：GetAppUsageDuration → /data/appUsageStats：/appUsage/appName, /appUsage/durationText, /updatedAt。
2. 检索模型：GetAppUsageDuration 要展示 /updatedAt。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-044｜做一张2x4的应用使用时长卡

1. 用户和数据：用户要“做一张2x4的应用使用时长卡”。本条实际给链路的数据是：GetAppUsageDuration → /data/appUsageStats：/appUsage/appName, /appUsage/durationText。
2. 检索模型：GetAppUsageDuration 要展示 /appUsage/appName, /appUsage/durationText。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-044.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-047｜给我一个低电量蓝牙耳机卡，显示总电量

1. 用户和数据：用户要“给我一个低电量蓝牙耳机卡，显示总电量”。本条实际给链路的数据是：GetEarphoneInfo → /data/earphone：/isConnected, /earphoneName, /batteryLevel, /leftBatteryLevel, /rightBatteryLevel。
2. 检索模型：GetEarphoneInfo 要展示 /batteryLevel。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-047.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-052｜耳机卡要展示降噪模式

1. 用户和数据：用户要“耳机卡要展示降噪模式”。本条实际给链路的数据是：GetEarphoneInfo → /data/earphone：/isConnected, /earphoneName, /noiseCancelMode。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/noiseCancelMode` 不在 GetEarphoneInfo 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-053｜耳机连接状态用会议纸张主题展示

1. 用户和数据：用户要“耳机连接状态用会议纸张主题展示”。本条实际给链路的数据是：GetEarphoneInfo → /data/earphone：/isConnected, /earphoneName。
2. 检索模型：GetEarphoneInfo 要展示 /isConnected, /earphoneName。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-059｜电量卡必须显示预计充满时间

1. 用户和数据：用户要“电量卡必须显示预计充满时间”。本条实际给链路的数据是：GetPhoneBatteryInfo → /data/phoneBattery：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc, /estimatedFullTimeText。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/estimatedFullTimeText` 不在 GetPhoneBatteryInfo 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-060｜电量卡要有电池健康度

1. 用户和数据：用户要“电量卡要有电池健康度”。本条实际给链路的数据是：GetPhoneBatteryInfo → /data/phoneBattery：/batterySOC, /batterySOCText, /batteryHealthText。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/batteryHealthText` 不在 GetPhoneBatteryInfo 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-067｜昨晚平均心率是多少

1. 用户和数据：用户要“昨晚平均心率是多少”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/exerciseHeartRateAvg, /updatedAt。
2. 检索模型：GetHealthAndSportSummary 要展示 /exerciseHeartRateAvg。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-067.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-068｜做一个心率卡，平均心率和更新时间都要有

1. 用户和数据：用户要“做一个心率卡，平均心率和更新时间都要有”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/exerciseHeartRateAvg, /updatedAt。
2. 检索模型：GetHealthAndSportSummary 要展示 /exerciseHeartRateAvg, /updatedAt。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-069｜我要睡眠时长卡，重点显示昨晚睡了多久

1. 用户和数据：用户要“我要睡眠时长卡，重点显示昨晚睡了多久”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/nightSleepDurationText, /sleepStatus, /fallAsleepTimeText, /wakeupTimeText。
2. 检索模型：GetHealthAndSportSummary 要展示 /nightSleepDurationText。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-069.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-070｜显示昨晚睡眠时长和睡眠状态

1. 用户和数据：用户要“显示昨晚睡眠时长和睡眠状态”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/nightSleepDurationText, /sleepStatus。
2. 检索模型：GetHealthAndSportSummary 要展示 /nightSleepDurationText, /sleepStatus。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-070.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-071｜做一张2x4睡眠作息卡，显示入睡、起床和睡眠时长

1. 用户和数据：用户要“做一张2x4睡眠作息卡，显示入睡、起床和睡眠时长”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/nightSleepDurationText, /fallAsleepTimeText, /wakeupTimeText。
2. 检索模型：GetHealthAndSportSummary 要展示 /nightSleepDurationText, /fallAsleepTimeText, /wakeupTimeText。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-071.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-074｜运动卡必须展示配速

1. 用户和数据：用户要“运动卡必须展示配速”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/exerciseTypeName, /exerciseDurationText, /exerciseCalorieText, /paceText。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/paceText` 不在 GetHealthAndSportSummary 的当前 outputSchema。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-075｜睡眠卡要有睡眠评分和各阶段图

1. 用户和数据：用户要“睡眠卡要有睡眠评分和各阶段图”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/nightSleepDurationText, /sleepScore, /sleepStages。
2. 发生位置：请求还没有到 DeepSeek。生成前的 outputSchema 校验检查到 `/sleepScore` 存在，但 `/sleepStages` 不在 GetHealthAndSportSummary 的当前 outputSchema；“睡眠阶段图”无法提供。
3. 结论：这不是检索或模板问题；端侧能力不产出该字段。若要保留为负例，应标为 `preflight_reject`；若要出卡，只能改用户诉求，不能让模板伪造这个值。

### TRE-076｜显示平均心率

1. 用户和数据：用户要“显示平均心率”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/exerciseHeartRateAvg。
2. 检索模型：GetHealthAndSportSummary 要展示 /exerciseHeartRateAvg。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-080｜我要一张深色专注风的平均心率卡

1. 用户和数据：用户要“我要一张深色专注风的平均心率卡”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/exerciseHeartRateAvg。
2. 检索模型：GetHealthAndSportSummary 要展示 /exerciseHeartRateAvg。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-080.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-081｜做一张内存占用卡，显示占用比例、可用内存和总内存

1. 用户和数据：用户要“做一张内存占用卡，显示占用比例、可用内存和总内存”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-082｜系统内存还剩多少，给我蓝色卡

1. 用户和数据：用户要“系统内存还剩多少，给我蓝色卡”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-083｜内存卡要展示存储空间使用情况

1. 用户和数据：用户要“内存卡要展示存储空间使用情况”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText, /storageUsagePercent。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-084｜显示内存占用趋势和历史曲线

1. 用户和数据：用户要“显示内存占用趋势和历史曲线”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText, /usageTrend。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-085｜系统内存占用

1. 用户和数据：用户要“系统内存占用”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-086｜用赛跑主题做内存使用卡

1. 用户和数据：用户要“用赛跑主题做内存使用卡”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-087｜内存卡显示可用内存

1. 用户和数据：用户要“内存卡显示可用内存”。本条实际给链路的数据是：GetSystemMemInfo → /data/systemMemory：/usagePercent, /availableMemText, /totalMemText。
2. 发生位置：测试驱动在构造 GetSystemMemInfo 的 arguments 时就失败，报错是 `candidateDataBindings.0.arguments` 不是字典。没有进入 WidgetGenerationService、检索或 DeepSeek。
3. 结论：这是当前测试驱动与 system-memory capability 输入契约不匹配，不是“内存模板不支持”。这组应先修测试驱动的参数构造；修完后再判断设备 capability registry 是否注册该能力。

### TRE-090｜显示股票价格和涨跌

1. 用户和数据：用户要“显示股票价格和涨跌”。本条实际给链路的数据是：GetStockQuote → /data/stock：/price, /changePercent。
2. 发生位置：测试驱动构造 GetStockQuote 请求时 arguments 不符合 capability 入参契约，请求在服务前失败。
3. 结论：当前 100 条测试集没有可用的股票 capability 调用输入；这条不能用于模板检索结论，应单列为 unsupported-capability / request-contract 负例。

### TRE-091｜做天气卡显示温度

1. 用户和数据：用户要“做天气卡显示温度”。本条实际给链路的数据是：ViewWeather → /data/weather：/current/temperatureText。
2. 检索模型：ViewWeather 要展示 /current/temperatureText。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-092｜做一个天气卡

1. 用户和数据：用户要“做一个天气卡”。本条实际给链路的数据是：ViewWeather → /data/weather：/current/temperatureText。
2. 检索模型：ViewWeather 要展示 /current/temperatureText。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-093｜做天气卡显示温度

1. 用户和数据：用户要“做天气卡显示温度”。本条实际给链路的数据是：ViewWeather → /data/weather：/current/temperatureText。
2. 检索模型：ViewWeather 要展示 /current/temperatureText。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-094｜做天气卡显示温度

1. 用户和数据：用户要“做天气卡显示温度”。本条实际给链路的数据是：ViewWeather → /data/weather：/current/temperatureText；ViewWeather → /data/weatherBackup：/current/temperatureText。
2. 检索模型：ViewWeather 要展示 /current/temperatureText。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-095｜显示下一场会议的标题和时间

1. 用户和数据：用户要“显示下一场会议的标题和时间”。本条实际给链路的数据是：GetCalendarEvents → /data/calendar：/events/0/title, /events/0/dtStart, /events/0/dtEnd, /events/0/eventLocation。
2. 检索模型：GetCalendarEvents 要展示 /events/0/title, /events/0/dtStart。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-095.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-096｜看睡眠时长

1. 用户和数据：用户要“看睡眠时长”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/nightSleepDurationText, /sleepStatus, /fallAsleepTimeText, /wakeupTimeText。
2. 检索模型：GetHealthAndSportSummary 要展示 /nightSleepDurationText。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-096.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。

### TRE-097｜显示平均心率

1. 用户和数据：用户要“显示平均心率”。本条实际给链路的数据是：GetHealthAndSportSummary → /data/healthSport：/exerciseHeartRateAvg, /updatedAt。
2. 检索模型：GetHealthAndSportSummary 要展示 /exerciseHeartRateAvg。之后链路进入了 DeepSeek 全量生成，而不是模板直出。
3. 模型实际返回：一段以 ````genui ["root","Column",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"line` 开头的 GenUI/DSL。服务随后给出 `VALIDATION_FAILED`，表示这段 DSL 未通过最终 A2UI 校验，因此没有 artifact/A2UI 文件。
4. 结论：失败点在全量生成后的 DSL 校验，不是字段缺失。现有 results.jsonl 没持久化校验器逐节点报错，不能诚实地把它说成某个具体布局属性；下一步应把 validator errors 写入结果行，才能精确到组件和属性。

### TRE-098｜做一个耳机连接状态卡

1. 用户和数据：用户要“做一个耳机连接状态卡”。本条实际给链路的数据是：GetEarphoneInfo → /data/earphone：/isConnected, /earphoneName, /batteryLevel。
2. 检索模型：GetEarphoneInfo 要展示 /isConnected, /earphoneName, /batteryLevel。模型已经提出的字段都来自本条数据。
3. 真实结果：没有模板直出，但服务状态是 success，A2UI 已在 `a2ui/TRE-098.a2ui`。这说明链路转入模型生成后仍完成了卡片。
4. 结论：这是“应直出的样本走了 LLM 卡片生成”。这里的直接证据是实际字段与路由；是否是主题门槛、组件信任门槛或模板编译失败，需要像 TRE-019 一样从对应 scope/compile 异常继续逐条定位，不能把它笼统归咎给模型。
