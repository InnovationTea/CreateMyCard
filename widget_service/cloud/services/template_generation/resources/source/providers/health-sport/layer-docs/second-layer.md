# 第二层业务模板使用规则

- Provider：`com.huawei.health-sport.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `ActivityOverviewCompact@1`：每日步数紧凑摘要，展示步数，可使用步数图标。 组件形态：compact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/dailySteps；次要数据：无；可选数据：无。
  - `ActivityOverviewFull@1`：今日活动完整摘要，展示步数、固定万步基准进度、消耗热量和运动距离，可使用步数图标。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText；可选数据：无。
  - `ActivityOverviewHero@1`：今日活动步数主视觉，展示步数和固定万步基准进度，可使用步数图标。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/dailySteps；次要数据：无；可选数据：无。
  - `ActivityOverviewWideHero@1`：每日活动摘要，展示步数，可补充热量、距离和目标日期。 组件形态：wideHero。 布局场景：约 4x1.7；WideHero + 1 个 PillAction。 主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText, /targetDateText；可选数据：无。
  - `ActivityOverviewWideFull@1`：每日活动摘要，展示步数，可补充热量、距离和目标日期。 组件形态：wideFull。 布局场景：完整 4x2；单独使用。主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText, /targetDateText；可选数据：无。
  - `WorkoutOverviewFull@1`：最近一次单次运动训练摘要，展示运动类型、该次热量、时长和结束时间。 组件形态：latest。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseTypeName, /exerciseDurationText；次要数据：/exerciseCalorieText, /exerciseEndTimeText；可选数据：无。
  - `WorkoutOverviewCompact@1`：最近一次单次运动训练摘要，展示运动类型、该次热量和时长，可使用运动图标。 组件形态：latestCompact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/exerciseTypeName, /exerciseDurationText；次要数据：/exerciseCalorieText；可选数据：无。
  - `WorkoutOverviewHero@1`：最近一次单次运动训练摘要，展示运动类型、该次热量和时长，可使用运动图标。 组件形态：latestHero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseTypeName, /exerciseDurationText；次要数据：/exerciseCalorieText；可选数据：无。
  - `HeartRateOverviewFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：fullUpdated。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewIconFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：fullIcon。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedIconFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：fullUpdatedIcon。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：support。 布局场景：约 2x1；用于单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportUpdated。 布局场景：约 2x1；用于单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewIconCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportIcon。 布局场景：约 2x1；用于单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedIconCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportUpdatedIcon。 布局场景：约 2x1；用于单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewIconHero@1`：运动平均心率主视觉，展示平均心率，使用心率图标。 组件形态：iconHero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewHero@1`：运动平均心率主视觉，展示平均心率。 组件形态：mainHero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedHero@1`：运动平均心率主视觉，展示平均心率，可补充更新时间。 组件形态：mainHeroUpdated。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewUpdatedIconHero@1`：运动平均心率主视觉，展示平均心率，可补充更新时间，使用心率图标。 组件形态：mainHeroUpdatedIcon。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `SleepOverviewFull@1`：睡眠情况完整摘要，展示时长和状态，可选展示得分进度或完整睡眠时段，可使用睡眠图标。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/nightSleepDurationText；次要数据：/sleepStatus；可选数据：/sleepScore, /fallAsleepTimeText, /wakeupTimeText。
  - `SleepOverviewHero@1`：睡眠情况主视觉，展示时长，可选展示得分进度、睡眠状态或完整睡眠时段，可使用睡眠图标。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/nightSleepDurationText；次要数据：无；可选数据：/sleepStatus, /sleepScore, /fallAsleepTimeText, /wakeupTimeText。
  - `SleepOverviewCompact@1`：睡眠情况紧凑摘要，展示时长和得分环，可使用睡眠图标。 组件形态：compact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/nightSleepDurationText；次要数据：/sleepScore；可选数据：无。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `ActivityOverviewCompact@1` 与 `ActivityOverviewHero@1` 只表达步数；`ActivityOverviewFull@1` 还要求并展示热量和距离。Hero 与 Full 的万步进度是固定展示基准，不得描述成用户个人目标或可信达成率。
- `SleepOverviewCompact@1` 表达时长和得分。`SleepOverviewHero@1` 至少表达时长，并按得分、状态、
  完整睡眠时段的顺序选择一个补充区域；睡眠时段仅在入睡和醒来时刻同时存在时展示。
- `SleepOverviewFull@1` 要求时长和状态；得分存在时展示得分，得分缺失且入睡和醒来时刻都存在时
  补充完整睡眠时段。
- 素材参数描述的是槽位语义，不代表固定素材清单；只在本轮素材候选中匹配，没有合适候选时省略可选参数：
  - `ActivityOverview*.stepsIcon`：步行、步数或日常活动语义。
  - `ActivityOverviewWideHero@1`、`ActivityOverviewWideFull@1` 的 `caloriesIcon`：热量、能量消耗或火焰语义；`distanceIcon`：距离、里程或路线语义。其它活动模板不得传入这两个参数。
  - `WorkoutOverview*.sourceIcon`：与本轮运动类型一致的训练或运动项目语义。
  - `HeartRateOverview*.sourceIcon`：心率、脉搏或心脏健康语义；需要图标的模板只有存在匹配素材时才可选择。
  - `SleepOverview*.sourceIcon`：睡眠、夜间或月亮语义。
- 图标与文字共享紧凑指标行时，保留模板的自适应字号；禁止为了放入图标而截断必须展示的指标值。
