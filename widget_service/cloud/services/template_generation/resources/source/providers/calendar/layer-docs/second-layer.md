# 第二层业务模板使用规则

- Provider：`com.huawei.calendar.cli`。
- 业务领域统一为 `CalendarOverview`；日期模板与日程模板是同一业务下的不同内容形态。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 用户同时要求日期和日程时，在 2x2 中使用 `TwoCompactLayout@1({}, ...)`，先放
  `DateOverviewCompact@1`，再放不带素材 props 且满足字段要求的 `ScheduleOverview*Compact@1`；
  两个纯文本 Compact 会自动纵向排列，不得拆成两个业务组件。
- 组合后的日期区占上半区，日程区占下半区；沿用 12vp 卡片安全边距，日期标签与主日期分别使用 12vp、
  38vp 字阶，日程时间轴使用 8vp 圆点、1vp 竖线和 14/10/10vp 文本层级。
- 可用模板：
  - `DateOverviewCompact@1`：首个日程日期的上半区主视觉。 组件形态：compactDate。 布局场景：约 2x1；优先与一个日程 Compact 纵向组合，也可与另一 Compact 组合。主数据：/events/0/startDate；次要数据：/updatedAt；可选数据：无。
  - `DateOverviewFull@1`：首个日程日期主视觉与数据更新时间。 组件形态：dateHero。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/events/0/startDate；次要数据：/updatedAt；可选数据：无。
  - `ScheduleOverviewNextEventFull@1`：无底部动作的首个日程摘要；日程标题必需，时间槽支持时间范围、开始时间、提前提醒或全天/时区，并可补充地点。 组件形态：nextEvent。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/events/0/title；次要数据：无；可选数据：/events/0/dtStart, /events/0/dtEnd, /events/0/remindTime/0, /events/0/timeZone, /events/0/isAllDay, /events/0/eventLocation。
  - `ScheduleOverviewNextEventLocationFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：nextEventLocation。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompact。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingLocationCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactLocation。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingWideFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingExpanded。 布局场景：完整 4x2；单独使用。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingSourceCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactSource。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingLocationSourceCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactLocationSource。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingSourceWideFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingExpandedSource。 布局场景：完整 4x2；单独使用。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewNextEventHero@1`：带一个日历动作的首项日程 Hero 主内容；日程标题必需，时间槽支持时间范围、开始时间、提前提醒或全天/时区，并可补充日程数量、备注与地点。主数据：/events/0/title；次要数据：无；可选数据：/events/0/dtStart, /events/0/dtEnd, /events/0/remindTime/0, /eventCount, /events/0/description, /events/0/timeZone, /events/0/isAllDay, /events/0/eventLocation。
  - `ScheduleOverviewReminderHero@1`：带一个闹钟动作的日程提醒 Hero 主内容；以时间轴同时展示标题、开始时间和提前提醒。主数据：/events/0/title；次要数据：/events/0/dtStart, /events/0/remindTime/0；可选数据：无。
  - `ScheduleOverviewTimezoneFull@1`：时区日程详情；以时区为主视觉，时间轴依次展示标题、全天/非全天状态和会议地点。主数据：/events/0/timeZone, /events/0/title；次要数据：/events/0/isAllDay, /events/0/eventLocation；可选数据：无。
  - `ScheduleOverviewProgressHero@1`：带一个查看日程动作的今日日程进度 Hero；展示剩余件数、进度条，以及最近日程的标题、开始时间和备注。主数据：/eventCount, /events/0/title；次要数据：/events/0/dtStart, /events/0/description；可选数据：无。
  - `ScheduleOverviewDatedMeetingHero@1`：带一个日历动作的会议 Hero 主内容；日期、标题、开始时间、结束时间与地点都来自 Provider 运行时数据。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/startDate, /events/0/dtEnd, /events/0/eventLocation；可选数据：无。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- `ScheduleOverviewNextEventHero@1`、`ScheduleOverviewReminderHero@1`、
  `ScheduleOverviewProgressHero@1` 与
  `ScheduleOverviewDatedMeetingHero@1` 只用于带一个 PillAction 的
  2x2 场景：使用 `HeroActionLayout@1`，并把一个 `PillAction@1` 作为最后一个直接 child；业务模板本身
  不得携带按钮。无底部 PillAction 时选择 `ScheduleOverviewNextEventFull@1`。
- 用户同时显式要求 `/events/0/title`、`/events/0/dtStart` 和 `/events/0/remindTime/0`，并要求进入闹钟时，
  必须选择 `ScheduleOverviewReminderHero@1`，不得选择会隐藏提前提醒信息的通用日程 Hero。
- 用户同时显式要求 `/events/0/title`、`/events/0/timeZone`、`/events/0/isAllDay` 和
  `/events/0/eventLocation` 时，必须选择 `ScheduleOverviewTimezoneFull@1`；`headerLabel` 逐字复用
  `cardComposition.businessTitleCandidate`，没有可信标题时省略。
- 用户同时显式要求 `/eventCount`、`/events/0/title`、`/events/0/dtStart` 和
  `/events/0/description`，并要求展示日程进度和进入日程详情时，必须选择
  `ScheduleOverviewProgressHero@1`，使用 `HeroActionLayout@1`，并把一个 `PillAction@1` 作为最后一个
  直接 child；`headerLabel` 逐字复用 `cardComposition.businessTitleCandidate`。该模板仅用于用户明确给出
  “今日计划 5 件事”的场景，进度总数为 5，剩余件数始终绑定 `/eventCount`。
- `ScheduleOverviewNextEventHero@1` 不按时间来源拆分模板；`dtStart`、`dtEnd`、`remindTime/0`、
  `timeZone` 和 `isAllDay` 通过 `$optionalPath` 与条件节点复用同一时间槽。
- `ScheduleOverviewNextEventFull@1` 和 `ScheduleOverviewNextEventHero@1` 的可选 `headerLabel` 只能逐字复用
  `cardComposition.businessTitleCandidate`；不得把“下一场日程”改写为“下一个日程”，没有可信标题时省略。
- `event.open.settings.dnd` 使用 `PillAction@1` 时，`label` 必须使用批准的“免打扰”，`icon` 只允许选择
  `focus`/`dnd`/月亮语义素材；不得把业务模板的 `calendarIcon` 当作动作图标。
- `event.open.clock.alarm` 与 `ScheduleOverviewReminderHero@1` 组合时，`label` 必须使用批准的“设置闹钟”，
  `icon` 只允许选择闹钟或提醒语义素材；Reminder Hero 标题栏不接收素材，闹钟素材只用于底部动作。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- 素材参数不绑定固定素材 ID，只在本轮素材候选中匹配；没有合适候选时省略可选参数，并避免选择依赖必需素材的模板：
  - `sourceIcon`：只选择日历应用、日程来源或会议来源语义，不得使用时钟、时间、地点或导航素材。
    当前 Calendar 来源素材为单色图标，由主题主内容色着色；不得按多色素材保留原始白色。
  - `calendarIcon`：日历本或日程管理语义；没有语义匹配素材时省略。
  - `timeIcon`：只选择时钟、时间或日程时刻语义，不得复用来源、地点或 Action 素材。
  - `locationIcon`：只选择地点、位置、会议室或地图标记语义，不得复用来源、时间或 Action 素材。
- 同一业务模板同时填写多个素材参数时，各槽位必须选择各自语义匹配的不同素材，不得把同一个素材同时填入
  `sourceIcon`、`timeIcon` 和 `locationIcon`。
- Action 图标必须与动作语义一致：查看日程使用日历或日程入口语义，进入会议使用会议语义；不得复用时间或
  地点素材。`PillAction@1` 没有匹配素材时省略 `icon`，不得为了显示图标而复用业务内容素材。
