# 第二层业务模板使用规则

- Provider：`com.huawei.health-sport.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `ActivityOverviewSteps@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：steps。 必需数据：/dailySteps；可选数据：无。
  - `ActivityOverviewStepsSupport@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：stepsSupport。 必需数据：/dailySteps；可选数据：无。
  - `ActivityOverviewDailySummary@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：dailySummary。 必需数据：/dailySteps, /dailyTotalCaloriesText, /dailyDistanceText；可选数据：无。
  - `ActivityOverviewDailySummaryWide@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：dailySummaryWide。 必需数据：/dailySteps, /dailyTotalCaloriesText, /dailyDistanceText；可选数据：无。
  - `WorkoutOverview@1`：最近一次单次运动训练摘要，展示运动类型、该次热量、时长和结束时间。 组件形态：latest。 必需数据：/exerciseTypeName, /exerciseCalorieText, /exerciseDurationText, /exerciseEndTimeText；可选数据：无。props 只允许语义匹配的可选 `sourceIcon`，不得传入 `caloriesIcon`。
  - `HeartRateOverviewHero@1`：运动平均心率摘要，可补充更新时间。 组件形态：hero。 必需数据：/exerciseHeartRateAvg；可选数据：无。
  - `HeartRateOverviewHeroUpdated@1`：运动平均心率摘要，可补充更新时间。 组件形态：heroUpdated。 必需数据：/exerciseHeartRateAvg, /updatedAt；可选数据：无。
  - `HeartRateOverviewHeroIcon@1`：运动平均心率摘要，可补充更新时间。 组件形态：heroIcon。 必需数据：/exerciseHeartRateAvg；可选数据：无。
  - `HeartRateOverviewHeroUpdatedIcon@1`：运动平均心率摘要，可补充更新时间。 组件形态：heroUpdatedIcon。 必需数据：/exerciseHeartRateAvg, /updatedAt；可选数据：无。
  - `HeartRateOverviewSupport@1`：运动平均心率摘要，可补充更新时间。 组件形态：support。 必需数据：/exerciseHeartRateAvg；可选数据：无。
  - `HeartRateOverviewSupportUpdated@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportUpdated。 必需数据：/exerciseHeartRateAvg, /updatedAt；可选数据：无。
  - `HeartRateOverviewSupportIcon@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportIcon。 必需数据：/exerciseHeartRateAvg；可选数据：无。
  - `HeartRateOverviewSupportUpdatedIcon@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportUpdatedIcon。 必需数据：/exerciseHeartRateAvg, /updatedAt；可选数据：无。
  - `SleepOverviewDuration@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：duration。 必需数据：/nightSleepDurationText；可选数据：无。
  - `SleepOverviewDurationDetailed@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：durationDetailed。 必需数据：/nightSleepDurationText；可选数据：无。
  - `SleepOverviewDurationScore@1`：睡眠总时长与睡眠得分摘要。 组件形态：durationScore。 必需数据：/nightSleepDurationText, /sleepScore；可选数据：无。
  - `SleepOverviewDurationScoreSupport@1`：睡眠总时长与睡眠得分的紧凑辅助摘要。 组件形态：durationScoreSupport。 必需数据：/nightSleepDurationText, /sleepScore；可选数据：无。
  - `SleepOverviewInsufficient@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：insufficient。 必需数据：/sleepStatus, /nightSleepDurationText；可选数据：无。
  - `SleepOverviewInsufficientDetailed@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：insufficientDetailed。 必需数据：/sleepStatus, /nightSleepDurationText；可选数据：无。
  - `SleepOverviewSchedule@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：schedule。 必需数据：/fallAsleepTimeText, /wakeupTimeText, /nightSleepDurationText；可选数据：无。
  - `SleepOverviewScheduleDetailed@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：scheduleDetailed。 必需数据：/fallAsleepTimeText, /wakeupTimeText, /nightSleepDurationText；可选数据：无。
  - `SleepOverviewScheduleStatus@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：scheduleStatus。 必需数据：/sleepStatus, /fallAsleepTimeText, /wakeupTimeText, /nightSleepDurationText；可选数据：无。
  - `SleepOverviewScheduleDetailedStatus@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：scheduleDetailedStatus。 必需数据：/sleepStatus, /fallAsleepTimeText, /wakeupTimeText, /nightSleepDurationText；可选数据：无。
  - `SleepOverviewDurationSupport@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：durationSupport。 必需数据：/nightSleepDurationText；可选数据：无。
  - `SleepOverviewDurationDetailedSupport@1`：睡眠时长摘要，可补充睡眠状态和入睡、醒来时间。 组件形态：durationDetailedSupport。 必需数据：/nightSleepDurationText；可选数据：无。

- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
- 素材参数描述的是槽位语义，不代表固定素材清单；只在本轮素材候选中匹配，没有合适候选时省略可选参数：
  - `stepsIcon`：步行、步数或日常活动语义；`caloriesIcon`：热量、能量消耗或火焰语义；`distanceIcon`：距离、里程或路线语义。
  - `WorkoutOverview.sourceIcon`：与本轮运动类型一致的训练或运动项目语义。
  - `HeartRateOverview*.sourceIcon`：心率、脉搏或心脏健康语义；需要图标的模板只有存在匹配素材时才可选择。
  - `SleepOverview*.sourceIcon`：睡眠、夜间或月亮语义。
- 图标与文字共享紧凑指标行时，保留模板的自适应字号；禁止为了放入图标而截断必须展示的指标值。
