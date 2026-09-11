# 第二层业务模板使用规则

- Provider：`com.huawei.countdown.cli`；业务领域为 `CountdownOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- `CountdownOverviewFull@1` 展示 `/countdownDays`，可传入本轮可信 `title`，用于
  `SingleFocusLayout@1`，或在存在语义匹配图标素材时用于 `FullIconActionLayout@1` 加一个
  `IconAction@1`。
- `CountdownOverviewHero@1` 展示同一份 `/countdownDays`，将单位“天”放在数字右侧，可传入本轮可信
  `title`，用于 `HeroActionLayout@1` 加一个 `PillAction@1`。
- `CountdownOverviewTravelSupport@1` 仅用于 `TwoSupportLayout@1` 的出行业务位置，左侧展示本轮可信
  出行标题或“出发倒计时”，右侧展示“剩余 /countdownDays 天”；可选倒计时语义的 `timerIcon` 计时图标；
  仅在分配了用户明确要求的闹钟跳转时传入 `actionId`，点击该胶囊响应跳转。主标题为 14vp，副标题为 10vp。
- `CountdownOverviewSupport@1` 第一行主文本展示“剩余 /countdownDays 天”，第二行辅助文本展示
  本轮可信 `title` 或默认“倒计时”；可选倒计时语义的 `timerIcon` 计时图标；只用于
  `TwoSupportLayout@1`。当前没有关联事件，必须省略 `actionId`，不能用闹钟或免打扰设置替代倒计时入口。
  主标题为 14vp，副标题为 10vp。
- `timerIcon` 只能从该参数 `allowedSources` 中的计时类素材中选择，例如沙漏或秒表；
  不使用普通时钟图标，缺少匹配素材时省略图标，不得借用闹钟、日历或天气图标，
  也不得为匹配图标修改剩余天数。
- 当前没有 Compact，因此不进入单业务双 PillAction 的 `2x2` 组合；不得用 Full、Hero 或 Support
  冒充缺失形态。
- `title` 只能来自本轮可信文本，例如“高考倒数”“运动会倒数日”“马拉松倒计时”；不得由天数反推
  事件名或目标日期。
- 选择模板前必须确认 `/countdownDays` 可用；0 天合法。
