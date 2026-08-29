# 第二层业务模板使用规则

- Provider：`com.huawei.app-usage.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `AppUsageOverviewSingleApp@1`：2x2 单个应用的当日使用时长摘要，无动作时使用。 组件形态：singleApp。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。
  - `AppUsageOverviewSingleAppDetailed@1`：2x2 单个应用的当日使用时长摘要，为底部 PillAction 预留空间。 组件形态：singleAppDetailed。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。
  - `AppUsageOverviewSingleAppWide@1`：2x4 单个应用的当日使用时长摘要，可补充更新时间。 组件形态：singleAppWide。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。
  - `AppUsageOverviewSingleAppDetailedWide@1`：2x4 单个应用的当日使用时长摘要，可补充更新时间。 组件形态：singleAppDetailedWide。 必需数据：/appUsage/appName, /appUsage/durationText；可选数据：/updatedAt。

- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
- `appIcon` 表达本轮目标应用自身的应用图标或品牌标识，不得使用其他应用或通用计时图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配，没有合适候选时省略。
- 当目标尺寸为 `2x2`、`selectedActionEventId` 非空时，必须选择 `AppUsageOverviewSingleAppDetailed@1`，并放入带末尾 `PillAction` 的 `HeroActionLayout@1`；无动作的 2x2 仍选择 `AppUsageOverviewSingleApp@1`，2x4 仍选择 `AppUsageOverviewSingleAppWide@1`。
