# 第二层业务模板使用规则

- Provider：`com.huawei.countdown.cli`；业务领域为 `CountdownOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- `CountdownOverviewFull@1` 展示 `/countdownDays`，可传入本轮可信 `title`，用于
  `SingleFocusLayout@1`，或在存在语义匹配图标素材时用于 `FullIconActionLayout@1` 加一个
  `IconAction@1`。
- `CountdownOverviewTargetDetailFull@1` 使用透明的自适应内容布局展示 `/countdownDays`，可传入本轮可信
  `title` 和 `targetDate`；用于 `SingleFocusLayout@1` 时直接填充 2x2 安全内容区，用于 2x4 的
  `WideTwoFullLayout@1` 半宽 Full 槽时，支撑背板、圆角和内边距由父布局统一提供。用户明确给出目标日
  以及事件标题并要求同时展示时，优先于只显示天数的 `CountdownOverviewFull@1`。
- `CountdownOverviewWideFull@1` 用于完整宽屏或 Full 组合布局；`CountdownOverviewWideHero@1`
  用于 WideHero + PillAction；`CountdownOverviewWideHalf@1` 用于对应半高组合布局。
- `CountdownOverviewHero@1` 展示同一份 `/countdownDays`，将单位“天”放在数字右侧，可传入本轮可信
  `title`，用于 `HeroActionLayout@1` 加一个 `PillAction@1`。
- `CountdownOverviewEventHero@1` 左对齐展示可信 `title` 和 `/countdownDays`，固定使用“天”作为单位；
  只用于节日或重要事件倒计时，操作仍由布局中的 Action 模板承载。
- `CountdownOverviewDepartureHero@1` 左对齐展示可信 `title` 和 `/countdownDays`，固定使用
  “天后出发”；只有用户需求明确包含旅行、返乡或其它出发语义时才选择，操作仍由 Action 模板承载。
- EventHero 与 DepartureHero 都符合时，明确命名的节日或重要事件优先 EventHero；例如“国庆返乡”
  以国庆为倒计时目标时显示“天”。DepartureHero 只用于倒计时目标本身是出发日、且没有命名节日或
  其它重要事件目标的场景，例如普通探亲或旅行出发。
- `CountdownOverviewTargetCompact@1` 使用当前 Compact 槽位的自适应蒙版，展示 `/countdownDays`
  和“距离目标日还有”；用于目标日、比赛或赛事倒计时。可选 `countdownIcon` 必须是本轮实际候选中具有计时语义
  的素材，没有匹配素材时省略，不能擅自使用日历或其它未批准资源。
- `CountdownOverviewSupport@1` 第一行主文本展示“剩余 /countdownDays 天”，第二行辅助文本展示
  本轮可信 `title` 或默认“倒计时”；只用于 `TwoSupportLayout@1`。当前没有关联事件，必须省略
  `actionId`，不能用闹钟或免打扰设置替代倒计时入口。
- 选择 Compact 时不得用 Full、Hero 或 Support 冒充；`CountdownOverviewTargetCompact@1` 不得用于
  明确要求显示标题、目标日期详情或出发后缀的场景。
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
- `targetDate` 只能原样使用当前 `GetCountdownDays.arguments.targetDate` 的可信 `YYYY-MM-DD` 字符串；
  不得从天数计算、改写格式或补造日期。
- 选择模板前必须确认 `/countdownDays` 可用；0 天合法。
