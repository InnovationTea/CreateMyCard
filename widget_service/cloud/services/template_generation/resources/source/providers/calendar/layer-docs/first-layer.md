# 日历日期日程业务首层规则

## CalendarOverview

- 日期和日程属于同一个日历业务领域，可按用户要求表达日期、首项日程，或组合表达两者。
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
  - `{{dataRoot:GetCalendarEvents}}/updatedAt`
- 日期内容只取首个有效事件的日期；系统当前日期、月/年、农历和相对日期不在当前数据能力范围内。
- 日程内容只表达同一可信首项日程；请求地点时必须有地点路径。
- 用户同时要求日期和日程时，必须保留两类显式字段，交由第二层组合日期 Compact 与日程 Compact。
- 不支持多日程列表、实时状态、分钟倒计时、会议号、邀请人、待办或备忘录；仅支持首项日程备注。
- 根据 `userQuery` 判断出的必须显示日历字段存在上述支持集合之外的路径时，不得选择。
