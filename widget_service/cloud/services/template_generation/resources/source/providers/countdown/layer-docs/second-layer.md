# 第二层业务模板使用规则

- 倒计时橙色主题固定为浅色背景、深色内容：卡片外层背景使用 `#FFEAE6`，文字和单色图标内容使用 `#99331F`；带蒙版的 Compact 使用深色 10% 透明度蒙版底色，不得使用纯白蒙版。
- Provider：`com.huawei.countdown.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `CountdownOverviewFull@1`：通用事件的剩余天数摘要。 组件形态：countdown。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/countdownDays；次要数据：无；可选数据：无。应传入 `title` 文本属性展示本次业务标题，例如“高考倒数”“运动会倒数日”“马拉松倒计时”。
  - `CountdownOverviewCompact@1`：倒计时紧凑摘要；用于 2x2 双层 Compact 组合。主数据：/countdownDays；次要数据：无；可选数据：无。可传入 `title` 文本属性展示“距离出发”等业务标题；没有业务 Action 时不加图标。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
