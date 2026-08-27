# 倒计时高级组件首层规则

## CountdownOverview

- 支持的 TaskSpec 数据路径：`{{dataRoot:GetCountdownDays}}/countdownDays`。
- 适用于高考、考试、节日、纪念日、旅行或赛事等通用剩余天数，0 天合法。
- 2x2 请求同时包含 `GetCountdownDays` 与 `ViewWeather`，且 `userQuery`、`title` 或 `description` 明确要求展示天气、温度、天气现象、紫外线或空气质量时，必须同时保留 `CountdownOverview` 与 `WeatherOverview`，不得退化成单倒计时 Full。
- 不支持事件名、目标日期、完成率或进度；这些内容不能由静态文案补造。
- 根据 `userQuery` 判断出的必须显示倒计时字段不是倒计时天数时，不得选择。
