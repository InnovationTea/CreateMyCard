# 第二层业务模板使用规则

- Provider：`com.huawei.app-usage.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `AppUsageOverviewSingleApp@1`：单个应用的当日使用时长摘要，可补充更新时间。 组件形态：singleApp。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。
  - `AppUsageOverviewSingleAppDetailed@1`：单个应用的当日使用时长摘要，可补充更新时间。 组件形态：singleAppDetailed。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。
  - `AppUsageOverviewSingleAppWide@1`：单个应用的当日使用时长摘要，可补充更新时间。 组件形态：singleAppWide。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。
  - `AppUsageOverviewSingleAppDetailedWide@1`：单个应用的当日使用时长摘要，可补充更新时间。 组件形态：singleAppDetailedWide。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。

- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
