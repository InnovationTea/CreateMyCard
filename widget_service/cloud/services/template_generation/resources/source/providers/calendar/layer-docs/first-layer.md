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
  不得用静态文案或其它日程字段补齐。`updatedAt` 只用于包含发起人、重要类型和提前提醒的提醒详情 Hero/Full。
- 原时区日期结束时间 Full 保留完整字段要求。新增同版式的时区起止时间 Full 必须有标题、时区、开始和结束时间；
  日期地点 Full 必须有标题、开始日期和地点；提醒详情 Full 必须有发起人、重要程度、提醒分钟数和更新时间。
  这三组分别匹配，不能拼接覆盖或要求用户补充另一组的字段。提醒详情不要求额外的日程标题或动作。
- 下一个日程 Full 的标题、开始时间和地点仍必需；结束时间可选，存在时保持原时间段展示，缺少时只显示开始时间。
  用户明确要求结束时间时，仍必须有真实结束时间路径，不能以开始时间代替。
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
- `2x2` 多业务场景中，日程 Support 按时间、标题加地点、标题加开始时间或标题加日期四种组合分别覆盖。
  时间 Support 以开始时间为必需数据，标题、结束时间和地点可选；无标题时把开始时间放在 14vp 主行，
  地点或查看提示放在 12vp 辅助行。其余辅助字段按对应模板必需；显式要求的结束时间仍必须可用。
  第一层只提取显式字段与主焦点，由 Search 和 Planner 选择能独立完整覆盖的模板；不得合并多个候选
  的字段覆盖来凑足一个槽位。
- `2x2` 恰好包含两个数据业务和一个显式 Action 时，日历也可以在标题、起止时间和地点都可用且能完整
  使用 `ScheduleOverviewHeroContent@1` 时进入 HeroTitle + HeroContent 组合，并固定作为第二个业务位置。
- 当前没有 Compact 模板，因此单业务双 Action 场景不进入模板路线。
- 使用包含 `allowCalendarViewFallback` 的 Search 首层协议时，单日历日程且用户未明确禁止按钮、
  操作或跳转，应标记 `allowCalendarViewFallback=true`；旧 LLM 选择器不输出此字段。
  “显示标题和时间”等未提到按钮的需求允许此兜底，“不要按钮”“不需要操作”“只展示不交互”等不允许。
  `action` 仍只提取用户显式要求的动作；不得在首层为了迁就 Hero 而直接选择查看动作。
  Search 后服务端优先匹配 Full，只有没有 Full 但有合适 Hero，且已有唯一、对象一致的
  `event.viewCalendarEvent` 候选时，才默认补一个“查看日程”按钮；不得补展示字段或编造事件。
