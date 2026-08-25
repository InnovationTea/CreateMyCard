# 第二层业务模板使用规则

- Provider：`com.huawei.health-sport.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `ActivityOverviewCompact@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：compact。 布局场景：约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction。主数据：/dailySteps；次要数据：无；可选数据：无。
  - `ActivityOverviewFull@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：full。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText；可选数据：无。
  - `ActivityOverviewHero@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/dailySteps；次要数据：无；可选数据：无。
  - `ActivityOverviewDailySummaryWideFull@1`：每日活动摘要，展示步数，可补充热量和距离。 组件形态：dailySummaryWide。 布局场景：完整 4x2；单独使用。主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText；可选数据：无。
  - `WorkoutOverviewFull@1`：最近一次单次运动训练摘要，展示运动类型、该次热量、时长和结束时间。 组件形态：latest。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/exerciseTypeName, /exerciseDurationText；次要数据：/exerciseCalorieText, /exerciseEndTimeText；可选数据：无。
  - `HeartRateOverviewFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：hero。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：heroUpdated。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewIconFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：heroIcon。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedIconFull@1`：运动平均心率摘要，可补充更新时间。 组件形态：heroUpdatedIcon。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：support。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportUpdated。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewIconCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportIcon。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedIconCompact@1`：运动平均心率摘要，可补充更新时间。 组件形态：supportUpdatedIcon。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `SleepOverviewFull@1`：睡眠摘要，展示时长、得分和状态。 组件形态：full。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/nightSleepDurationText；次要数据：/sleepScore, /sleepStatus；可选数据：无。
  - `SleepOverviewHero@1`：睡眠摘要，展示时长和得分。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/nightSleepDurationText；次要数据：/sleepScore；可选数据：无。
  - `SleepOverviewCompact@1`：睡眠摘要，展示时长和得分。 组件形态：compact。 布局场景：约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction。主数据：/nightSleepDurationText；次要数据：/sleepScore；可选数据：无。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- 素材参数描述的是槽位语义，不代表固定素材清单；只在本轮素材候选中匹配，没有合适候选时省略可选参数：
  - `stepsIcon`：步行、步数或日常活动语义；`caloriesIcon`：热量、能量消耗或火焰语义；`distanceIcon`：距离、里程或路线语义。
  - `WorkoutOverviewFull.sourceIcon`：与本轮运动类型一致的训练或运动项目语义。
  - `HeartRateOverview*.sourceIcon`：心率、脉搏或心脏健康语义；需要图标的模板只有存在匹配素材时才可选择。
  - `SleepOverview*.sourceIcon`：睡眠、夜间或月亮语义。
- 图标与文字共享紧凑指标行时，保留模板的自适应字号；禁止为了放入图标而截断必须展示的指标值。
