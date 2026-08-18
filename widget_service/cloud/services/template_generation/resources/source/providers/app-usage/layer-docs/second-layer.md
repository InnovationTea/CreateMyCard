# 应用使用时长高级组件二层规则

## AppUsageOverview

- 调用：`Template("AppUsageOverview@1", variant, params)`。
- 2x2/2x4 分别使用 `singleApp`/`singleAppWide`；存在可信次数值和单位时使用对应 `Detailed` 后缀。
- `params` 只允许可选 `appIcon`，且只能复制 app/application 语义匹配的 `trustedAssetSources`；无素材时使用 `{}`。
- 时长分段由服务端可信投影自动补齐；管控 Action 只能位于布局末尾。
- 不得输出旧 `AppUsageOverview(...)` 构造器。
