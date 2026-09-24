# 健康运动高级组件首层规则

## ActivityOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/dailySteps`、`{{dataRoot:GetHealthAndSportSummary}}/dailyTotalCaloriesText`、`{{dataRoot:GetHealthAndSportSummary}}/dailyDistanceText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateAvg`。
- `steps` 只需步数，可使用紧凑摘要或带固定万步基准进度的主视觉；`dailySummary` 必须同时有步数、热量和距离，2x2 完整摘要以文字展示热量和距离。
- `trainingSummary` 必须同时有每日步数、最近一次运动时长和运动平均心率；只用于用户明确要求将三项数据合并成备赛或训练概览的场景，可与目标日倒计时和锻炼页入口组合，不要求运动热量或距离。
- `trainingMetrics` 必须同时有每日步数、最近一次运动时长、运动平均心率和运动热量四项；只用于用户明确要求以四个同等重要的 2x1 指标格（步数、用时、心率、消耗）组成 2x4 训练概览的场景，整体单独占满完整 4x2，不再组合其它业务或 Action，不展示万步进度或运动类型。
- 用户要求步数与其它业务（如日程）组合成 2x4 卡片，并同时要求睡眠得分时，步数与得分可由
  昨日活动睡眠 Compact 单行双指标面板承载（两行分别为昨日步数与昨晚睡眠得分）；该面板面向
  健身准备场景，不承载热量、距离、运动明细或睡眠时段，两个数值字段必须同时可用。
- 模板中的万步进度只是固定展示基准，不代表 Provider 返回了用户目标或可信达成率。用户明确要求个人目标、达成率、趋势或活动环时仍不支持。

## WorkoutOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/exerciseTypeName`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseCalorieText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseEndTimeText`、`{{dataRoot:GetHealthAndSportSummary}}/targetDateText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseStartTimeText`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateAvg`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateMax`。
- 表达最近一次特定运动训练会话，而不是全天累计活动；模板自身要求该次运动热量和时长两项完整，运动类型为可选补充，结束时间仅完整摘要形态需要。
- 训练记录 2x4 宽卡面向用户显式要求运动日期、运动类型、运动时长、开始时间、结束时间、平均心率和最高心率并同时要求打开锻炼页入口的场景；该模板要求上述七项字段全部可用，热量、距离等其它字段不参与。
- 用户明确请求运动记录、锻炼数据、训练信息、运动时长、热量消耗或特定运动类型时，可以选择 `WorkoutOverview`；该次运动热量与时长为模板准入条件，不要求 userQuery 逐项点名。
- 与 `ActivityOverview` 默认互斥。只有 userQuery 明确要求今日综合活动概览，并同时要求全天步数与热量或距离等全天累计数据时，才允许两者组合；每日步数、最近一次运动时长和运动平均心率同时被要求时，改由 `ActivityOverview` 的 `trainingSummary` 单组件完整承载，不再拆成多个业务组件。
- 不支持计划/实时状态、距离、配速、轨迹、心率区间、赛事名、训练计划、总里程或完成率。

## HeartRateOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateAvg`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateMax`、`{{dataRoot:GetHealthAndSportSummary}}/exerciseHeartRateMin`、`{{dataRoot:GetHealthAndSportSummary}}/updatedAt`。
- 只表达运动平均心率或高低心率（最大/最小心率）；不支持当前/静息心率、异常结论、心率区间分布、趋势或波形。

## SleepOverview

- 支持路径：`{{dataRoot:GetHealthAndSportSummary}}/nightSleepDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/totalNapDurationText`、`{{dataRoot:GetHealthAndSportSummary}}/sleepScore`、`{{dataRoot:GetHealthAndSportSummary}}/sleepStatus`、`{{dataRoot:GetHealthAndSportSummary}}/fallAsleepTimeText`、`{{dataRoot:GetHealthAndSportSummary}}/wakeupTimeText`。
- 睡眠总时长是模板准入必需字段。带一个 Action 时可使用主视觉：得分存在时优先展示 0 到 100 的
  得分进度；缺少得分时展示可信睡眠状态；得分和状态都缺少时，仅在入睡、醒来时刻同时存在时展示
  完整睡眠时段。紧凑摘要仍要求睡眠得分。
- 作息提醒（白天小睡）模板以 `/totalNapDurationText` 为准入必需字段；入睡、醒来时刻为可选补充，
  两者同时存在时才展示时段。无 Action 时选择完整摘要形态，带一个 Action 时选择主视觉形态。
- 无 Action 的 2x2 完整摘要还要求可信睡眠状态；得分和完整睡眠时段均为可选展示内容，时段只有在
  入睡、醒来时刻同时存在时才能展示。
- 支持 2x4 完整作息；不支持阶段、目标、趋势或建议。

根据 `userQuery` 判断出的任一必须显示字段不能由所选一个或多个组件的支持路径完整覆盖时，不得选择模板路线。
