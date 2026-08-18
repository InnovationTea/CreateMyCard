# 蓝牙耳机高级组件二层规则

## BluetoothDeviceOverview

- 调用：`Template("BluetoothDeviceOverview@1", variant, params)`。
- 未连接单业务使用 `disconnected`，与手机组合使用 `disconnectedPhone`。
- 单业务 2x2 仅查连接状态使用 `connection`；仅查充电盒或充电盒加连接状态使用 `earbuds`；其它场景选实际字段最完整 Variant。
- 2x4 使用 `earbudsDynamicWide`；与手机组合的 2x2/2x4 分别使用 `earbudsPhone`/`earbudsPhoneWide`。
- `params` 只允许 Variant 签名声明且语义匹配的 `sourceIcon`、`leftEarIcon`、`rightEarIcon`；无素材时使用 `{}`。
- 音乐 Action 只能位于布局末尾；不得输出旧 `BluetoothDeviceOverview(...)` 构造器。
