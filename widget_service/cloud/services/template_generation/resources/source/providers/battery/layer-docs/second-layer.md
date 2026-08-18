# 手机电量高级组件二层规则

## BatteryOverview

- 调用：`Template("BatteryOverview@1", variant, params)`。
- 单业务 2x2 使用 `normal|charging|low`，2x4 使用对应 `Wide` 后缀。
- 与内存对等组合使用 `Peer` 后缀；与耳机组合使用 `Phone` 后缀；与天气 2x2 组合使用 `Weather` 后缀。
- Variant 前缀必须与可信充电/低电状态一致。
- `params` 只允许可选 `batteryIcon`，且只能复制语义匹配的 `trustedAssetSources`；无素材时使用 `{}`。
- Action 只能由布局末尾持有；不得输出旧 `BatteryOverview(...)` 构造器。
