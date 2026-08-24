# 第二层业务模板使用规则

- Provider：`com.huawei.calendar.cli`。
- 业务领域统一为 `CalendarOverview`；日期模板与日程模板是同一业务下的不同内容形态。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 用户同时要求日期和日程时，在 2x2 中优先使用 `PeerPairLayout@1({}, ...)`，先放
  `DateOverviewCompact@1`，再放不带素材 props 且满足字段要求的 `ScheduleOverview*Compact@1`；
  两个纯文本 Compact 会自动纵向排列，不得拆成两个业务组件。
- 组合后的日期区占上半区，日程区占下半区；沿用 12vp 卡片安全边距，日期标签与主日期分别使用 12vp、
  38vp 字阶，日程时间轴使用 8vp 圆点、1vp 竖线和 14/10/10vp 文本层级。
- 可用模板：
  - `DateOverviewCompact@1`：首个日程日期的上半区主视觉。 组件形态：compactDate。 布局场景：约 2x1；优先与一个日程 Compact 纵向组合，也可与另一 Compact 组合。主数据：/events/0/startDate；次要数据：/updatedAt；可选数据：无。
  - `DateOverviewFull@1`：首个日程日期主视觉与数据更新时间。 组件形态：dateHero。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/events/0/startDate；次要数据：/updatedAt；可选数据：无。
  - `ScheduleOverviewNextEventFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：nextEvent。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewNextEventLocationFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：nextEventLocation。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompact。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingLocationCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactLocation。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingWideFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingExpanded。 布局场景：完整 4x2；单独使用。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingSourceCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactSource。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingLocationSourceCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactLocationSource。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingSourceWideFull@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingExpandedSource。 布局场景：完整 4x2；单独使用。主数据：/events/0/title, /events/0/dtStart；次要数据：/events/0/eventLocation, /events/0/dtEnd；可选数据：无。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- 素材参数不绑定固定素材 ID，只在本轮素材候选中匹配；没有合适候选时省略可选参数，并避免选择依赖必需素材的模板：
  - `sourceIcon`：日历应用、日程来源或会议来源语义，不是时间或地点图标。
  - `timeIcon`：时钟、时间或日程时刻语义。
  - `locationIcon`：地点、位置、会议室或地图标记语义。
