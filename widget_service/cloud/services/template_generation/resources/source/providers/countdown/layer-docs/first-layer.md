# 倒计时高级组件首层规则

## CountdownOverview

- 支持的 TaskSpec 数据路径：`{{dataRoot:GetCountdownDays}}/countdownDays`。
- 适用于高考、考试、节日、纪念日、旅行或赛事等通用剩余天数，0 天合法。
- 当前提供 Full、Hero、Compact 和 Support 模板。通用 Full/Hero 保留居中摘要；TargetDetailFull
  使用自适应内容布局并可补充可信标题、目标日期，2x4 蒙版由双 Full 布局统一提供；EventHero 用于
  节日或重要事件，DepartureHero 仅用于明确的旅行、返乡或出发语义；TargetCompact 用于目标日或
  比赛倒计时的紧凑蒙版。
- Hero 用于单业务加一个 PillAction，Compact 可用于 Compact 槽位，Support 用于
  `TwoSupportLayout@1` 的一个业务槽位。
- 同时出现节日/重要事件和返乡出发语义时，若倒计时目标明确命名为节日或重要事件，优先保留
  EventHero 的“天”单位；只有倒计时目标本身是行程出发且没有更高优先级事件目标时才使用
  DepartureHero 的“天后出发”。
- 事件名和目标日期只允许通过模板 Prop 使用本轮可信文本；不支持由天数反推事件名、目标日期、完成率
  或进度，这些内容不能由静态文案补造。
- 当前提供 Full、Hero、TravelSupport 和 Support 模板；Hero 用于单业务加一个 PillAction，两种 Support
  用于 `TwoSupportLayout@1` 的业务槽位。TravelSupport 固定展示出行标题与剩余天数，可消费用户明确要求的
  闹钟跳转。当前没有 Compact，单业务双 Action 场景不进入模板路线。
- 不支持事件名、目标日期、完成率或进度；这些内容不能由静态文案补造。
- 根据 `userQuery` 判断出的必须显示倒计时字段不是倒计时天数时，不得选择。
