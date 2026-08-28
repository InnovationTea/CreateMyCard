# 日历日程业务首层规则

## CalendarOverview

- 当前模板只表达首项日程及其可信附属信息，不再提供独立日期卡或日期与日程的双 Compact 组合。
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
- 首项日程日期只在带日期的会议场景中与标题、起止时间和地点共同展示；只请求日期时不得选择模板路线。
- 系统当前日期、月/年、农历、相对日期和日历数据更新时间不在当前模板范围内。
- 日程内容只表达同一可信首项日程；请求地点时必须有地点路径。
- 用户同时要求日期、标题、起止时间和地点，并带一个日历动作时，可以选择带日期的会议 Hero；缺少其中任一必选字段时不得用静态文案补齐。
- 不支持多日程列表、实时状态、分钟倒计时、会议号、邀请人、待办或备忘录；仅支持首项日程备注。
- 根据 `userQuery` 判断出的必须显示日历字段存在上述支持集合之外的路径时，不得选择。
