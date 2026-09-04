# 日历日程业务首层规则

## CalendarOverview

- 除双日程 Full 明确展示按开始时间排序的前两项日程外，其余模板只表达首项日程及其可信附属信息。
- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetCalendarEvents}}/eventCount`
  - `{{dataRoot:GetCalendarEvents}}/updatedAt`
  - `{{dataRoot:GetCalendarEvents}}/events/0/startDate`
  - `{{dataRoot:GetCalendarEvents}}/events/0/title`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtStart`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`
  - `{{dataRoot:GetCalendarEvents}}/events/0/eventLocation`
  - `{{dataRoot:GetCalendarEvents}}/events/0/description`
  - `{{dataRoot:GetCalendarEvents}}/events/0/remindTime/0`
  - `{{dataRoot:GetCalendarEvents}}/events/0/timeZone`
  - `{{dataRoot:GetCalendarEvents}}/events/0/isAllDay`
  - `{{dataRoot:GetCalendarEvents}}/events/0/senderName`
  - `{{dataRoot:GetCalendarEvents}}/events/0/importantEventType`
  - `{{dataRoot:GetCalendarEvents}}/events/1/title`
  - `{{dataRoot:GetCalendarEvents}}/events/1/dtStart`
- 双日程摘要只有在前两项日程的标题和开始时间四个字段都存在时可选；`events/1` 必须对应真实第二项，
  不得用首项数据回退补齐。其它模板请求地点时必须有首项地点路径。
- 标题日程 Hero 与地点日程 Hero 分开准入：前者要求标题和开始时间，后者要求地点和开始时间，结束时间均可选。
  每个候选必须独立覆盖用户显式要求的展示字段；同时显式要求标题和地点时，不得用其中任一 Hero 丢弃另一字段。
- 日期、全天状态、时区、备注、提醒详情和日程总数只在相应专用模板的完整字段组合可用时展示，缺少字段时
  不得用静态文案或其它日程字段补齐。`updatedAt` 只用于包含发起人、重要类型和提前提醒的提醒详情 Hero。
- 系统当前日期、月/年、农历和相对日期不在当前模板范围内。
- `oneClickServiceLink`、`oneClickServiceType`、`isServiceValid` 和 `entityId` 是日历 Action 的执行或选择参数，
  不是默认展示字段。用户要求“一键加入会议”或“查看日程”时，应选择语义匹配的 Action，不得因为 Action
  引用了这些路径就把它们加入 `requiredOutputFieldsByCapability`；仅当用户明确要求把链接、服务类型、
  服务有效状态或日程 ID 显示在卡片上时，才按展示字段处理，并在模板不能覆盖时退出模板路线。
- 例如“显示下一场会议的标题和时间，并支持一键加入会议”只要求展示
  `{{dataRoot:GetCalendarEvents}}/events/0/title`、`{{dataRoot:GetCalendarEvents}}/events/0/dtStart` 和
  `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`，同时选择 `event.enter.meeting`；不得额外要求展示其 Action 参数。
- 用户同时要求日期、标题、起止时间和地点，并带一个日历动作时，可以选择带日期的会议 Hero；缺少其中任一必选字段时不得用静态文案补齐。
- 不支持超过两项的日程列表、实时状态、分钟倒计时、会议号或待办。发起人和备注只在完整匹配提醒详情、
  备注详情或日程清点模板时支持，不能据此放宽其它模板。
- 根据 `userQuery` 判断出的必须显示日历字段存在上述支持集合之外的路径时，不得选择。
- `2x2` 多业务场景中，首项日程标题和开始时间均可用时，可以选择 `ScheduleOverviewSupport@1`；结束时间
  和地点按实际可用性追加到第二行。该模板只占 `TwoSupportLayout@1` 的一个业务槽位。
- `2x2` 恰好包含两个数据业务和一个显式 Action 时，日历也可以在标题、起止时间和地点都可用且能完整
  使用 `ScheduleOverviewHeroContent@1` 时进入 HeroTitle + HeroContent 组合，并固定作为第二个业务位置。
- 当前没有 Compact 模板，因此单业务双 Action 场景不进入模板路线。
