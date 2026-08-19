# 系统内存高级组件二层规则

## ResourceUsageOverview

- 调用：`Template("ResourceUsageOverview@1", "memory|memoryPeer", params)`。
- 单业务使用 `memory`；2x2 与手机电量对等组合使用 `memoryPeer`。
- `params` 只允许可选 `icon`，且只能复制 memory/resource 语义匹配的 `trustedAssetSources`；无素材时使用 `{}`。
- 禁止 storage 变体和推断内存压力状态。
- 不得输出旧 `ResourceUsageOverview(...)` 构造器。
