# 第二层业务模板使用规则

- Provider：`com.huawei.system-memory.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `ResourceUsageOverviewMemory@1`：系统内存占用摘要，展示占用率、可用内存和总内存。 组件形态：memory。 必需数据：/usagePercent, /availableMemText, /totalMemText；可选数据：无。
  - `ResourceUsageOverviewMemoryPeer@1`：系统内存占用摘要，展示占用率、可用内存和总内存。 组件形态：memoryPeer。 必需数据：/usagePercent, /availableMemText, /totalMemText；可选数据：无。

- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
