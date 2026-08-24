# 第二层业务模板使用规则

- Provider：`com.huawei.countdown.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `CountdownOverviewFull@1`：通用事件的剩余天数摘要。 组件形态：countdown。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/countdownDays；次要数据：无；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
