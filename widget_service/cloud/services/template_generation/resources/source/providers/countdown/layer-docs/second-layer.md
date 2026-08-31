# 第二层业务模板使用规则

- Provider：`com.huawei.countdown.cli`；业务领域为 `CountdownOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 当前只提供 `CountdownOverviewFull@1`：展示 `/countdownDays`，可传入本轮可信 `title`，用于
  `SingleFocusLayout@1`，或在存在语义匹配图标素材时用于 `FullIconActionLayout@1` 加一个
  `IconAction@1`。
- 当前没有 Support、Compact 或 Hero，因此不进入双业务、双 PillAction 或单 PillAction 的 `2x2`
  组合；不得用 Full 冒充缺失形态。
- `title` 只能来自本轮可信文本，例如“高考倒数”“运动会倒数日”“马拉松倒计时”；不得由天数反推
  事件名或目标日期。
- 选择模板前必须确认 `/countdownDays` 可用；0 天合法。
