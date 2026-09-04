# 倒计时高级组件首层规则

## CountdownOverview

- 支持的 TaskSpec 数据路径：`{{dataRoot:GetCountdownDays}}/countdownDays`。
- 适用于高考、考试、节日、纪念日、旅行或赛事等通用剩余天数，0 天合法。
- 当前提供 Full 和 Hero 模板；Hero 用于单业务加一个 PillAction。双业务或双 Action 场景不进入模板路线。
- 不支持事件名、目标日期、完成率或进度；这些内容不能由静态文案补造。
- 根据 `userQuery` 判断出的必须显示倒计时字段不是倒计时天数时，不得选择。
