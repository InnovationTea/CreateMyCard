# 日历日程业务首层规则

## CalendarOverview

- 当前模板只表达首项日程及其可信附属信息；日期 Full 与带日期会议 Hero 都必须和同一首项日程内容共同展示。
- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetCalendarEvents}}/events/0/startDate`
  - `{{dataRoot:GetCalendarEvents}}/events/0/title`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtStart`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`
  - `{{dataRoot:GetCalendarEvents}}/events/0/eventLocation`
  - `{{dataRoot:GetCalendarEvents}}/events/0/description`
  - `{{dataRoot:GetCalendarEvents}}/events/0/remindTime/0`
  - `{{dataRoot:GetCalendarEvents}}/events/0/timeZone`
  - `{{dataRoot:GetCalendarEvents}}/events/0/isAllDay`
  - `{{dataRoot:GetCalendarEvents}}/eventCount`
- 首项日程日期只在日期 Full 或带日期会议 Hero 中与标题、起止时间和地点共同展示；只请求日期时不得选择模板路线。
- 系统当前日期、月/年、农历、相对日期和日历数据更新时间不在当前模板范围内。
- 日程内容只表达同一可信首项日程；请求地点时必须有地点路径。
- `oneClickServiceLink`、`oneClickServiceType`、`isServiceValid` 和 `entityId` 是日历 Action 的执行或选择参数，
  不是默认展示字段。用户要求“一键加入会议”或“查看日程”时，应选择语义匹配的 Action，不得因为 Action
  引用了这些路径就把它们加入 `requiredOutputFieldsByCapability`；仅当用户明确要求把链接、服务类型、
  服务有效状态或日程 ID 显示在卡片上时，才按展示字段处理，并在模板不能覆盖时退出模板路线。
- 例如“显示下一场会议的标题和时间，并支持一键加入会议”只要求展示
  `{{dataRoot:GetCalendarEvents}}/events/0/title`、`{{dataRoot:GetCalendarEvents}}/events/0/dtStart` 和
  `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`，同时选择 `event.enter.meeting`；不得额外要求展示其 Action 参数。
- 用户同时要求日期、标题、起止时间和地点，并带一个日历动作时，可以选择带日期的会议 Hero；缺少其中任一必选字段时不得用静态文案补齐。
- 不支持多日程列表、实时状态、分钟倒计时、会议号、邀请人、待办或备忘录；仅支持首项日程备注。
- 根据 `userQuery` 判断出的必须显示日历字段存在上述支持集合之外的路径时，不得选择。
- 当前没有 Support 或 Compact 模板；双 Action 场景不进入模板路线。2x2 恰好包含两个数据业务和一个
  显式 Action 时，日历只有在标题、起止时间和地点都可用且能完整使用
  `ScheduleOverviewHeroContent@1` 时才可进入组合，并固定作为第二个业务位置。
