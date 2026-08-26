# 日历高级组件首层规则

## DateOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetCalendarEvents}}/events/0/startDate`
  - `{{dataRoot:GetCalendarEvents}}/updatedAt`
- 只表达首个有效事件的日期和星期；用户必须明确询问事件日期或星期。
- 系统当前日期、月/年、农历、相对日期和纯日程内容请求不得选择。

## ScheduleOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetCalendarEvents}}/events/0/title`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtStart`
  - `{{dataRoot:GetCalendarEvents}}/events/0/dtEnd`
  - `{{dataRoot:GetCalendarEvents}}/events/0/eventLocation`
- 只表达同一可信首项日程；请求地点时必须有地点路径。
- 不支持多日程列表、实时状态、分钟倒计时、会议号、备注、邀请人、待办或备忘录。
- 根据 `userQuery` 判断出的必须显示日历字段存在所选组件支持集合之外的路径时，不得选择。
