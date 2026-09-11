# 倒计时高级组件首层规则

## CountdownOverview

- 支持的 TaskSpec 数据路径：`{{dataRoot:GetCountdownDays}}/countdownDays`。
- 适用于高考、考试、节日、纪念日、旅行或赛事等通用剩余天数，0 天合法。
- 当前提供 Full、Hero、TravelSupport 和 Support 模板；Hero 用于单业务加一个 PillAction，两种 Support
  用于 `TwoSupportLayout@1` 的业务槽位。TravelSupport 固定展示出行标题与剩余天数，可消费用户明确要求的
  闹钟跳转。当前没有 Compact，单业务双 Action 场景不进入模板路线。
- 不支持事件名、目标日期、完成率或进度；这些内容不能由静态文案补造。
- 根据 `userQuery` 判断出的必须显示倒计时字段不是倒计时天数时，不得选择。
