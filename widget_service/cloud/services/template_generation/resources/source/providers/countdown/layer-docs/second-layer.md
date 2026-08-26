# 第二层业务模板使用规则

- Provider：`com.huawei.countdown.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `CountdownOverview@1`：通用事件的剩余天数摘要。 组件形态：countdown。 必需数据：/countdownDays；可选数据：无。

- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
