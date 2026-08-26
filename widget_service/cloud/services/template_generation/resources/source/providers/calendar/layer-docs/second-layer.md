# 第二层业务模板使用规则

- Provider：`com.huawei.calendar.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `DateOverviewCompactDate@1`：首个日程的日期和星期摘要。 组件形态：compactDate。 必需数据：/events/0/startDate, /updatedAt；可选数据：无。
  - `DateOverviewDateHero@1`：首个日程的日期和星期摘要。 组件形态：dateHero。 必需数据：/events/0/startDate, /updatedAt；可选数据：无。
  - `ScheduleOverviewNextEvent@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：nextEvent。 必需数据：/events/0/title, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewNextEventLocation@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：nextEventLocation。 必需数据：/events/0/title, /events/0/eventLocation, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingCompact@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompact。 必需数据：/events/0/title, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingCompactLocation@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactLocation。 必需数据：/events/0/title, /events/0/eventLocation, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingExpanded@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingExpanded。 必需数据：/events/0/title, /events/0/eventLocation, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingCompactSource@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactSource。 必需数据：/events/0/title, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingCompactLocationSource@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingCompactLocationSource。 必需数据：/events/0/title, /events/0/eventLocation, /events/0/dtStart, /events/0/dtEnd；可选数据：无。
  - `ScheduleOverviewMeetingExpandedSource@1`：首个日程摘要，展示标题和时间，可补充结束时间与地点。 组件形态：meetingExpandedSource。 必需数据：/events/0/title, /events/0/eventLocation, /events/0/dtStart, /events/0/dtEnd；可选数据：无。

- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
- 素材参数不绑定固定素材 ID，只在本轮素材候选中匹配；没有合适候选时省略可选参数，并避免选择依赖必需素材的模板：
  - `sourceIcon`：日历应用、日程来源或会议来源语义，不是时间或地点图标。
  - `timeIcon`：时钟、时间或日程时刻语义。
  - `locationIcon`：地点、位置、会议室或地图标记语义。
