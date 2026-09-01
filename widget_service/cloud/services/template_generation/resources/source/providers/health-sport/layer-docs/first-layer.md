# 健康运动高级组件首层规则

## ActivityOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/dailySteps`、`{{dataRoot:GetHealthAndSportSummary}}/dailyTotalCaloriesText`、`{{dataRoot:GetHealthAndSportSummary}}/dailyDistanceText`。
- `steps` 只需步数，可使用紧凑摘要或带固定万步基准进度的主视觉；`dailySummary` 必须同时有步数、热量和距离，2x2 完整摘要以文字展示热量和距离。
- 模板中的万步进度只是固定展示基准，不代表 Provider 返回了用户目标或可信达成率。用户明确要求个人目标、达成率、趋势或活动环时仍不支持。

## WorkoutOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/exerciseTypeName`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseCalorieText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseEndTimeText`。
- 表达最近一次特定运动训练会话，而不是全天累计活动；模板自身要求运动类型、该次运动热量、时长和结束时间四项完整。
- 用户明确请求运动记录、锻炼数据、训练信息、运动时长、热量消耗或特定运动类型时，可以选择 `WorkoutOverview`；主数据与次要数据合计四项，均为模板准入条件，不要求 userQuery 逐项点名。
- 与 `ActivityOverview` 默认互斥。只有 userQuery 明确要求今日综合活动概览，并同时要求全天步数与热量或距离等全天累计数据时，才允许两者组合。
- 不支持计划/实时状态、距离、配速、轨迹、心率区间、赛事名、训练计划、总里程或完成率。

## HeartRateOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateAvg`、`{{dataRoot:GetHealthAndSportSummary}}/updatedAt`。
- 只表达运动平均心率；不支持当前/静息心率、异常结论、区间、趋势或波形。

## SleepOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/nightSleepDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/sleepScore`、`{{dataRoot:GetHealthAndSportSummary}}/sleepStatus`、`{{dataRoot:GetHealthAndSportSummary}}/fallAsleepTimeText`、`{{dataRoot:GetHealthAndSportSummary}}/wakeupTimeText`。
- 睡眠总时长是模板准入必需字段。带一个 Action 时可使用主视觉：得分存在时优先展示 0 到 100 的
  得分进度；缺少得分时展示可信睡眠状态；得分和状态都缺少时，仅在入睡、醒来时刻同时存在时展示
  完整睡眠时段。紧凑摘要仍要求睡眠得分。
- 无 Action 的 2x2 完整摘要还要求可信睡眠状态；得分和完整睡眠时段均为可选展示内容，时段只有在
  入睡、醒来时刻同时存在时才能展示。
- 支持 2x4 完整作息；不支持阶段、午睡、目标、趋势或建议。

根据 `userQuery` 判断出的任一必须显示字段不能由所选一个或多个组件的支持路径完整覆盖时，不得选择模板路线。
