# 第二层业务模板使用规则

- Provider：`com.huawei.calendar.cli`；业务领域统一为 `CalendarOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 当前日历 Provider 没有 `Compact` 模板，因此不进入单业务双 Action 组合；不得用 Hero、Full 或
  WideFull 冒充缺失形态。双业务可选择四种日程 Support 进入 `TwoSupportLayout@1`；
  双业务单 Action 也可以使用 `ScheduleOverviewHeroContent@1`，并固定放在
  `HeroTitleContentActionLayout@1` 的第二个业务位置。
- 可用模板：
  - `ScheduleOverviewNextEventHero@1`：下一个日程 Hero；标题为主数据，起止时间和地点为次要数据；
    可选 `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewReminderHero@1`：日程提醒 Hero；展示标题、开始时间和提前提醒；可选
    `headerLabel`。提醒文案通过端侧 Expr 判断开始时间是否为空，不在云侧读取样例值。
  - `ScheduleOverviewTimezoneFull@1`：时区日程 Full；展示时区、标题、起止时间和地点；可选
    `headerLabel`。
  - `ScheduleOverviewDateFull@1`：日期日程 Full；展示真实日期、标题、起止时间和地点；可选
    `headerLabel`。
  - `ScheduleOverviewDatedMeetingHero@1`：带日期会议 Hero；展示真实日期、标题、起止时间和地点，
    不接收展示 Prop。
  - `ScheduleOverviewHeroContent@1`：日程 HeroContent；展示标题、起止时间和地点；只用于
    `HeroTitleContentActionLayout@1` 的第二个业务 child。
  - `ScheduleOverviewTimeSupport@1`：首项标题及时间段；标题、开始时间必需，结束时间可选，
    缺失时只显示开始时间，不残留分隔符。
  - `ScheduleOverviewLocationSupport@1`：首项标题及地点，两者必需。
  - `ScheduleOverviewStartTimeSupport@1`：首项标题及开始时间，两者必需。
  - `ScheduleOverviewDateSupport@1`：首项标题及真实日期，两者必需。
    四种 Support 均只用于 `TwoSupportLayout@1`，支持可选 24vp `calendarIcon` 和 Planner 分配的
    `actionId`；必须独立覆盖日历业务的全部显式字段，不得混拼四种模板的覆盖结果。
  - `ScheduleOverviewNextEventLocationFull@1`：下一个日程 Full；展示标题、起止时间和地点；可选
    `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewMeetingWideFull@1`：宽版会议摘要；展示标题、起止时间和地点；可选
    `timeIcon` 与 `locationIcon`。
  - `ScheduleOverviewMeetingSourceWideFull@1`：带来源图标的宽版会议摘要；`sourceIcon` 必填，
    `timeIcon` 与 `locationIcon` 可选。
  - `ScheduleOverviewTwoEventsFull@1`：双日程 Full；按顺序展示前两项日程各自的标题和开始时间，
    不接收展示 Prop。
  - `ScheduleOverviewLocationDescriptionEndFull@1`：备注详情 Full；展示首项日程的备注、结束时间和地点；
    可选 `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewDatedAllDayHero@1`：带日期全天日程 Hero；展示日期、标题和全天状态，
    不接收展示 Prop；全天文案由端侧 `Expr(...)` 按运行时布尔值计算。
  - `ScheduleOverviewLocationHero@1`：地点日程 Hero；展示地点和开始时间，可选结束时间；可选
    `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewTimezoneDateEndFull@1`：时区日期日程 Full；展示标题、日期、时区和结束时间；可选
    `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewReminderDetailsHero@1`：提醒详情 Hero；展示数据更新时间、发起人、重要类型和提前
    提醒分钟数，不接收展示 Prop。
  - `ScheduleOverviewTitleHero@1`：标题日程 Hero；展示标题和开始时间，可选结束时间；可选
    `calendarIcon` 与 `headerLabel`。
  - `ScheduleOverviewEventCountDetailsHero@1`：近期日程清点 Hero；展示日程总数及首项日程的标题、
    开始时间和备注，不接收展示 Prop。
  - `ScheduleOverviewTimezoneAllDayFull@1`：时区全天日程 Full；展示标题、全天状态、时区和地点；可选
    `calendarIcon` 与 `headerLabel`；全天文案由端侧 `Expr(...)` 按运行时布尔值计算。
- Hero 只用于 `HeroActionLayout@1` 加一个 `PillAction@1`；Full 只用于 `SingleFocusLayout@1`，
  或在存在语义匹配图标素材时用于 `FullIconActionLayout@1` 加一个 `IconAction@1`。WideFull 当前只作
  `2x4` 预留。
- HeroContent 必须位于 HeroTitle 之后，且布局第三个直接 child 必须是一个 `PillAction@1`；不得交换
  两个业务位置或在业务模板内嵌 Action。
- `headerLabel` 只能逐字复用 `cardComposition.businessTitleCandidate`，没有可信标题时省略。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；Props 只能使用本轮 Prompt 下发的可信文本或素材，
  不得输出数据路径。
- 选择能够完整表达用户显式字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。标题 Hero 与地点
  Hero 是两个独立候选；二者都只在自身完整覆盖显式字段时可选。缺少真实日期、时间、提醒、时区、地点、
  发起人、重要类型、备注或日程总数时，不得用静态文案或其它数组项补齐。
- 素材参数不绑定固定素材 ID，只从本轮素材候选中按语义匹配：
  - `sourceIcon`：日历应用、日程来源或会议来源语义，使用 Theme 主内容色着色；
  - `calendarIcon`：日历本或日程管理语义，使用 Theme 辅助内容色着色；
  - `timeIcon`：时钟、时间或日程时刻语义；
  - `locationIcon`：地点、位置、会议室或地图标记语义。
- 同一模板的多个素材槽位必须分别匹配语义，不得复用同一素材填充来源、时间和地点。
- Action 图标必须与动作语义一致；`PillAction@1` 没有匹配素材时省略 `icon`，不得复用业务内容素材。
