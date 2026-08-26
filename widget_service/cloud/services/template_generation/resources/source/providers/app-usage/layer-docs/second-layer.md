# 第二层业务模板使用规则

- Provider：`com.huawei.app-usage.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `AppUsageOverviewFull@1`：单个应用的当日使用时长摘要，无动作时使用。 组件形态：full。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/appUsage/appName, /appUsage/durationText；次要数据：无；可选数据：/updatedAt。
  - `AppUsageOverviewHero@1`：单个应用的当日使用时长摘要，为底部 PillAction 预留空间。 组件形态：hero。 布局场景：约 2x1.7；用于 2x2 主内容加一个 PillAction。主数据：/appUsage/appName, /appUsage/durationText；次要数据：无；可选数据：/updatedAt。
  - `AppUsageOverviewCompact@1`：单个应用的当日使用时长摘要，展示时长。 组件形态：compact。 布局场景：约 2x1；双 Compact 组成 2x2，或单 Compact + 2 个 PillAction。主数据：/appUsage/appName, /appUsage/durationText；次要数据：无；可选数据：/updatedAt。
  - `AppUsageOverviewWideFull@1`：单个应用的当日使用时长摘要，可补充更新时间。 组件形态：wideFull。 布局场景：完整 4x2；单独使用。主数据：/appUsage/appName, /appUsage/durationText；次要数据：无；可选数据：/updatedAt。
  - `AppUsageOverviewWideHero@1`：单个应用的当日使用时长摘要，可补充更新时间。 组件形态：wideHero。 布局场景：约 4x1.7；用于 2x4 主内容加一个 PillAction。主数据：/appUsage/appName, /appUsage/durationText；次要数据：无；可选数据：/updatedAt。
- 已有 Provider 全局路径的值必须由模板 `data` 绑定；props 可传无全局路径的受控派生值、排版参数和
  素材。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `appIcon` 表达本轮目标应用自身的应用图标或品牌标识，不得使用其他应用或通用计时图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配，没有合适候选时省略。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个时，必须选择 `AppUsageOverviewHero@1`，并放入
  带末尾 `PillAction` 的 `HeroActionLayout@1`；无动作的 2x2 选择 `AppUsageOverviewFull@1`，2x4 按动作
  情况选择 `AppUsageOverviewWideHero@1` 或 `AppUsageOverviewWideFull@1`。
