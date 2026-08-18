# 日历高级组件二层规则

## DateOverview

- 调用：`Template("DateOverview@1", "compactDate|dateHero", {})`。
- 单业务使用 `dateHero`；日期与日程组合时，2x2 使用 `compactDate`，2x4 使用 `dateHero`。
- 日期和星期由服务端可信投影补齐；不得输出旧 `DateOverview(...)` 构造器。

## ScheduleOverview

- 调用：`Template("ScheduleOverview@1", variant, params)`。
- 单业务使用 `nextEvent`，有可信地点时使用 `nextEventLocation`。
- 日期组合在 2x2 使用 `meetingCompact` 或 `meetingCompactLocation`；2x4 有地点时使用 `meetingExpanded`。
- 需要来源图标时使用对应 `Source` 后缀。
- `params` 只允许 Variant 签名声明且语义匹配的 `sourceIcon`、`timeIcon`、`locationIcon`；缺失时使用 `{}`。
- `timeText` 由服务端可信投影补齐；不得输出旧 `ScheduleOverview(...)` 构造器。
