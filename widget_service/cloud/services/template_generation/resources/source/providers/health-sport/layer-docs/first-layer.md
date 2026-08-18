# 健康运动高级组件首层规则

## ActivityOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/dailySteps`、`{{dataRoot:GetHealthAndSportSummary}}/dailyTotalCaloriesText`、`{{dataRoot:GetHealthAndSportSummary}}/dailyDistanceText`。
- `steps` 只需步数；`dailySummary` 必须同时有步数、热量和距离。不支持目标、达成率、趋势或活动环。

## WorkoutOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/exerciseTypeName`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseCalorieText`。
- 只支持最近一次运动；不支持计划/实时状态、距离、配速、轨迹、心率区间或完成率。

## HeartRateOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateAvg`、`{{dataRoot:GetHealthAndSportSummary}}/updatedAt`。
- 只表达运动平均心率；不支持当前/静息心率、异常结论、区间、趋势或波形。

## SleepOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/nightSleepDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/sleepStatus`、`{{dataRoot:GetHealthAndSportSummary}}/fallAsleepTimeText`、`{{dataRoot:GetHealthAndSportSummary}}/wakeupTimeText`。
- 支持睡眠总时长、可信状态和 2x4 完整作息；不支持得分、阶段、午睡、目标、趋势或建议。

根据 `userQuery` 判断出的任一必须显示字段不能由所选一个或多个组件的支持路径完整覆盖时，不得选择模板路线。
