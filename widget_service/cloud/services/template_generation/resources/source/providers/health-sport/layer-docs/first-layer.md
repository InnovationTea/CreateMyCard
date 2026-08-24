# 健康运动高级组件首层规则

## ActivityOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/dailySteps`、`{{dataRoot:GetHealthAndSportSummary}}/dailyTotalCaloriesText`、`{{dataRoot:GetHealthAndSportSummary}}/dailyDistanceText`。
- `steps` 只需步数；`dailySummary` 必须同时有步数、热量和距离。不支持目标、达成率、趋势或活动环。

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
- 支持睡眠总时长、0 到 100 的可信睡眠得分、可信状态和 2x4 完整作息；不支持阶段、午睡、目标、趋势或建议。

根据 `userQuery` 判断出的任一必须显示字段不能由所选一个或多个组件的支持路径完整覆盖时，不得选择模板路线。
