# 第二层业务模板使用规则

- Provider：`com.huawei.system-memory.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `ResourceUsageOverviewFull@1`：系统内存占用摘要，展示占用率、可用内存和总内存。 组件形态：memory。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/usagePercent；次要数据：/availableMemText, /totalMemText；可选数据：无。
  - `ResourceUsageOverviewCompact@1`：系统内存占用摘要，展示占用率、可用内存和总内存。 组件形态：memoryPeer。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/usagePercent；次要数据：/availableMemText, /totalMemText；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `icon` 表达内存、RAM 或系统资源占用语义，不得使用清理动作图标代替状态图标；它不绑定固定素材 ID，只在本轮素材候选中匹配，没有合适候选时省略。
