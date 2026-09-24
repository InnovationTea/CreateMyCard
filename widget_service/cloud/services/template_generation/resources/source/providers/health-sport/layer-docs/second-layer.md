# 第二层业务模板使用规则

- Provider：`com.huawei.health-sport.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- Support 内嵌事件只允许使用该模板参数来源中的 `allowedActionIds`，不得借用其他业务的事件。
  步数、训练和运动心率允许关联锻炼页，但不得宣称直达步数、心率或某次训练详情；睡眠只关联睡眠详情。
  可用入口不代表默认增加点击，仍须遵循用户要求和所选 Plan 的唯一分配。
- 可用模板：
  - `ActivityOverviewSupport@1`：每日步数为主信息，第二行固定说明，可选 `stepsIcon`；不展示热量和距离。
  - `WorkoutOverviewSupport@1`：主数据 /exerciseCalorieText，次要数据 /exerciseDurationText，
    可选 /exerciseTypeName；主行展示热量，辅助行展示运动类型与时长，可选 `sourceIcon`。
  - `HeartRateOverviewSupport@1`：主数据 /exerciseHeartRateAvg；主行心率值和单位，辅助行
    “运动平均心率”，可选 `heartIcon`。不再提供 UpdatedSupport、IconSupport、UpdatedIconSupport。
  - `SleepOverviewSupport@1`：仅要求 /nightSleepDurationText，辅助行为睡眠说明，可选 `sourceIcon`；
    不展示得分或进度环，不能覆盖用户显式要求的得分。
    四种 Support 均只用于 `TwoSupportLayout@1`，可接收 Planner 分配的 `actionId` 并绑定根节点点击。
  - `ActivityOverviewYesterdayStepsSleepCompact@1`：昨日活动睡眠单行 Compact 双指标面板，参考 Q069
    深睡小睡布局：圆角底板内两行均为标签在左、数值在右，上行“昨日步数”展示步数加“步”单位，
    下行“昨晚睡眠”展示睡眠得分加“分”单位；不接收 Props、不展示图标、不内嵌 Action。只用于 2x4
    组合布局的右侧上 Compact 槽位（如 `WideFullTwoCompactLayout@1`），要求 /dailySteps 与
    /sleepScore 同时可用。
  - `ActivityOverviewCompact@1`：每日步数紧凑摘要，展示步数，可使用步数图标。 组件形态：compact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/dailySteps；次要数据：无；可选数据：无。
  - `ActivityOverviewFull@1`：今日活动完整摘要，展示步数与固定万步基准进度，可补充消耗热量和运动距离，可使用步数图标。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/dailySteps；次要数据：无；可选数据：/dailyTotalCaloriesText, /dailyDistanceText。
  - `ActivityOverviewTrainingSummaryFull@1`：备赛或训练综合摘要，展示每日步数、最近一次运动时长和运动平均心率，可传本轮可信 `title`。组件形态：full。主数据：/dailySteps；次要数据：/exerciseDurationText, /exerciseHeartRateAvg；可选数据：无。三项字段同时被明确要求时优先使用该模板；2x4 可与 `CountdownOverviewTargetCompact@1` 及承载 `event.open.health.sport` 的 `CompactAction@1` 放入 `WideFullTwoCompactLayout@1`，300×150 卡片需传 `compactRows: true` 使两行加间距恰好为 126vp；事件由 Action 模板承载，不向本 Full 传 `actionId`。
  - `ActivityOverviewTrainingMetricsWideFull@1`：训练概览四宫格宽卡，完整 4x2 内以两行两列排布四个 2x1 指标格：左上大号步数配“今日步数”副标题，右上平均心率配“平均心率”副标题，左下运动时长配“用时”副标题，右下热量配“总消耗热量”副标题，每格右侧可选对应语义图标。 组件形态：wideFull。 布局场景：完整 4x2；单独使用。主数据：/dailySteps；次要数据：/exerciseDurationText, /exerciseHeartRateAvg, /exerciseCalorieText；可选数据：无。
  - `ActivityOverviewHero@1`：今日活动步数主视觉，展示步数和固定万步基准进度，可使用步数图标。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/dailySteps；次要数据：无；可选数据：无。
  - `ActivityOverviewWideHero@1`：每日活动摘要，展示步数，可补充热量、距离和目标日期。 组件形态：wideHero。 布局场景：约 4x1.7；WideHero + 1 个 PillAction。 主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText, /targetDateText；可选数据：无。
  - `ActivityOverviewExerciseWideHero@1`：今日活动摘要，大号展示步数，存在运动类型时以类型名替代“今日活动”标题，可补充运动时长、消耗热量、运动距离和平均心率紧凑指标行，并以纯文本补充最低心率，数据缺失时隐藏对应指标，可使用对应图标。 组件形态：wideHero。 布局场景：约 4x1.7；WideHero + 1 个 PillAction。 主数据：/dailySteps；次要数据：无；可选数据：/exerciseTypeName, /exerciseDurationText, /exerciseCalorieText, /dailyDistanceText, /exerciseHeartRateAvg, /exerciseHeartRateMin。
  - `ActivityOverviewWideFull@1`：每日活动摘要，展示步数，可补充热量、距离和目标日期。 组件形态：wideFull。 布局场景：完整 4x2；单独使用。主数据：/dailySteps；次要数据：/dailyTotalCaloriesText, /dailyDistanceText, /targetDateText；可选数据：无。
  - `WorkoutOverviewFull@1`：最近一次单次运动训练摘要，展示该次热量和时长，可补充结束时间与运动类型。 组件形态：latest。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseDurationText；次要数据：/exerciseCalorieText；可选数据：/exerciseEndTimeText, /exerciseTypeName。
  - `WorkoutOverviewCompact@1`：最近一次单次运动训练摘要，展示该次热量和时长，可选展示运动类型，可使用运动图标。 组件形态：latestCompact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/exerciseDurationText；次要数据：/exerciseCalorieText；可选数据：/exerciseTypeName。
  - `WorkoutOverviewHero@1`：最近一次单次运动训练摘要，展示该次时长，可选展示热量和运动类型，可使用运动图标。 组件形态：latestHero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseDurationText；次要数据：无；可选数据：/exerciseTypeName, /exerciseCalorieText。
  - `WorkoutOverviewTrainingRecordWideFull@1`：训练记录宽卡完整摘要，左侧顶部展示运动类型（不展示右上角图标），中部紧凑组合大号运动时长与运动日期副标题，底部展示平均、最高心率；右侧两个胶囊块均以图标收尾，上块展示运动开始-结束时间并配“运动时间”副标题，下块为左对齐“打开锻炼”入口。 组件形态：wideFull。 布局场景：完整 4x2；单独使用，单动作内嵌。主数据：/exerciseDurationText；次要数据：/exerciseTypeName, /targetDateText, /exerciseStartTimeText, /exerciseEndTimeText, /exerciseHeartRateAvg, /exerciseHeartRateMax；可选数据：无。
  - `HeartRateOverviewFull@1`：运动平均心率摘要。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewMinMaxFull@1`：运动心率摘要，展示高低心率区间，可补充更新时间。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateMax, /exerciseHeartRateMin；次要数据：无；可选数据：/updatedAt。
  - `HeartRateOverviewCompact@1`：运动平均心率摘要。 组件形态：support。 布局场景：约 2x1；用于单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewIconCompact@1`：运动平均心率摘要。 组件形态：supportIcon。 布局场景：约 2x1；用于单 Compact 加两个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewIconHero@1`：运动平均心率主视觉，展示平均心率，使用心率图标。 组件形态：iconHero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewHero@1`：运动平均心率主视觉，展示平均心率。 组件形态：mainHero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：无；可选数据：无。
  - `HeartRateOverviewUpdatedHero@1`：运动平均心率主视觉，展示平均心率，可补充更新时间。 组件形态：mainHeroUpdated。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewUpdatedIconHero@1`：运动平均心率主视觉，展示平均心率，可补充更新时间，使用心率图标。 组件形态：mainHeroUpdatedIcon。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `HeartRateOverviewUpdatedFull@1`：运动平均心率摘要，展示平均心率与更新时间。 组件形态：fullUpdated。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/exerciseHeartRateAvg；次要数据：/updatedAt；可选数据：无。
  - `SleepOverviewFull@1`：睡眠情况完整摘要，展示时长和状态，可选展示得分进度、完整睡眠时段或小睡时长，可使用睡眠图标。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/nightSleepDurationText；次要数据：/sleepStatus；可选数据：/sleepScore, /fallAsleepTimeText, /wakeupTimeText, /totalNapDurationText。
  - `SleepOverviewNapFull@1`：作息提醒完整摘要，展示小睡累计时长，可选展示入睡-醒来时段，可使用睡眠图标。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/totalNapDurationText；次要数据：无；可选数据：/fallAsleepTimeText, /wakeupTimeText。
  - `SleepOverviewHero@1`：睡眠情况主视觉，展示时长，可选展示得分进度、睡眠状态或完整睡眠时段，可使用睡眠图标。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/nightSleepDurationText；次要数据：无；可选数据：/sleepStatus, /sleepScore, /fallAsleepTimeText, /wakeupTimeText。
  - `SleepOverviewNapHero@1`：作息提醒主视觉，展示小睡累计时长，可选展示入睡-醒来时段，可使用睡眠图标。 组件形态：hero。 布局场景：约 2x1.7；Hero + 1 个 PillAction。主数据：/totalNapDurationText；次要数据：无；可选数据：/fallAsleepTimeText, /wakeupTimeText。
  - `SleepOverviewCompact@1`：睡眠情况紧凑摘要，展示睡眠时长，可使用睡眠图标。 组件形态：compact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/nightSleepDurationText；次要数据：无；可选数据：无。
  - `SleepOverviewScoreCompact@1`：睡眠得分紧凑摘要，展示睡眠得分和得分进度环，可使用睡眠图标。 组件形态：compact。 布局场景：约 2x1；单 Compact + 2 个 PillAction。主数据：/sleepScore；次要数据：无；可选数据：无。
  - `SleepOverviewScoreFull@1`：睡眠得分完整摘要，以大号数字展示睡眠得分并配“分”单位，顶部展示睡眠健康状态，底部展示总睡眠时长，可选展示深睡眠时长，可使用睡眠图标。 组件形态：full。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/sleepScore；次要数据：/nightSleepDurationText；可选数据：/sleepStatus, /deepSleepDurationText。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `ActivityOverviewCompact@1` 与 `ActivityOverviewHero@1` 只表达步数；`ActivityOverviewFull@1` 展示步数与固定万步基准进度，可补充展示热量和距离，字段未提供时对应整行省略。`ActivityOverviewTrainingSummaryFull@1` 只在每日步数、最近一次运动时长和运动平均心率三项均可用时选择，不使用固定万步进度。`ActivityOverviewTrainingMetricsWideFull@1` 只在每日步数、最近一次运动时长、运动平均心率和运动热量四项均可用，且用户明确要求步数、用时、心率、消耗以四个并列指标格展示时选择，优先于 `ActivityOverviewTrainingSummaryFull@1` 与 `WorkoutOverviewTrainingRecordWideFull@1` 的组合路线。当 planCandidates 提供该模板的独立 WideFull 计划，且步数、用时、心率、消耗四项均为用户显式要求字段时，必须选择该独立计划；未被其覆盖的其它显式字段（如运动类型）随之省略，不得为补齐字段退回多槽组合。Hero 与常规 Full 的万步进度是固定展示基准，不得描述成用户个人目标或可信达成率。
- `WorkoutOverviewTrainingRecordWideFull@1` 面向训练记录场景：用户显式要求运动日期、运动类型、运动时长、开始时间、结束时间、平均心率和最高心率，且动作是打开锻炼页时优先选择；六项次要数据必须同时可用，动作由本模板内嵌承载，不再外挂 Action 槽位。
- `SleepOverviewCompact@1` 表达时长，`SleepOverviewScoreCompact@1` 表达得分。`SleepOverviewHero@1` 至少表达时长，并按得分、状态、
  完整睡眠时段的顺序选择一个补充区域；睡眠时段仅在入睡和醒来时刻同时存在时展示。
- 健身准备 2x4 组合（用户同时要求课程时间地点、昨日步数和昨晚睡眠得分，并要求训练前打开收藏歌单）：
  优先选择 `WideFullTwoCompactLayout@1`，左侧 Full 槽位放日程会议详情模板，右上放
  `ActivityOverviewYesterdayStepsSleepCompact@1`，右下为承载打开歌单动作的 `CompactAction@1`
  （右侧配音乐或歌单语义图标，label 使用批准的入口名称）；歌单动作由根 Action 槽位消费，
  不向业务模板传 `actionId`，也不得改用 Generic 指标槽凑位。双指标面板不接收展示类 Props，
  两个数值字段必须同时可用。
- `SleepOverviewFull@1` 要求时长和状态；得分存在时展示得分，得分缺失且入睡和醒来时刻都存在时
  补充完整睡眠时段。
- `SleepOverviewScoreFull@1` 以得分为主数值，要求得分和总睡眠时长，用户显式要求得分场景优先于
  `SleepOverviewFull@1`；睡眠健康状态和深睡眠时长可用时补充展示，缺失时省略对应内容。
- `SleepOverviewNapFull@1` 与 `SleepOverviewNapHero@1` 表达白天小睡累计时长；入睡-醒来时段仅在
  入睡和醒来时刻同时存在时补充展示。无 Action 时选择 Full 形态，带一个 Action 时选择 Hero 形态。
- 素材参数描述的是槽位语义，不代表固定素材清单；只在本轮素材候选中匹配，没有合适候选时省略可选参数：
  - `ActivityOverview*.stepsIcon`：步行、步数或日常活动语义。
  - `ActivityOverviewWideHero@1`、`ActivityOverviewWideFull@1`、`ActivityOverviewExerciseWideHero@1` 的 `caloriesIcon`：热量、能量消耗或火焰语义；`distanceIcon`：距离、里程或路线语义。其它活动模板不得传入这两个参数。
  - `ActivityOverviewExerciseWideHero@1` 的 `timeIcon`：运动计时或时长语义；`heartIcon`：心率或心脏语义。
  - `ActivityOverviewTrainingMetricsWideFull@1` 的 `stepsIcon`：步数或步行语义；`timeIcon`：运动计时或时长语义；`heartIcon`：心率或心脏语义；`caloriesIcon`：热量、能量消耗或火焰语义；四个槽位图标相互独立选图，不能共用同一素材。
  - `WorkoutOverview*.sourceIcon`：与本轮运动类型一致的训练或运动项目语义，仅用于 2x2 形态；`WorkoutOverviewTrainingRecordWideFull@1` 不使用右上角图标，只用 `timeIcon`：计时、秒表或运动时长语义，`actionIcon`：锻炼入口或运动项目语义。
  - `HeartRateOverview*.sourceIcon`：心率、脉搏或心脏健康语义；需要图标的模板只有存在匹配素材时才可选择。
  - `heartIcon`：HeartRateOverviewSupport 的心脏健康图标，不接受运动或天气资源。
  - `SleepOverview*.sourceIcon`：睡眠、夜间或月亮语义。
- 图标与文字共享紧凑指标行时，保留模板的自适应字号；禁止为了放入图标而截断必须展示的指标值。
- 双业务 Support 按各自素材参数的 `allowedSources` 独立选图，不能共用另一业务的候选语义。
  步数、训练、睡眠和心率槽位分别受 `steps`、`workout`、`sleep`、`heart` 约束；
  天气水滴不能用于步数、睡眠或训练。没有合适素材时省略可选参数，必选图标模板不能绕过约束。
