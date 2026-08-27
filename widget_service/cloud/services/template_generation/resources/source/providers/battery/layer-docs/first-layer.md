# 手机电量高级组件首层规则

## BatteryOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetPhoneBatteryInfo}}/batterySOC`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batterySOCText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batteryTemperatureText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/chargingStatusDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batteryCapacityLevelDesc`
- 只表达手机本机电量、等级、充电状态和电池温度，0% 合法。
- 不支持续航、预计充满时间、健康度、电压、电流、充电器类型或外设电量。
- 根据 `userQuery` 判断出的必须显示电量字段存在支持集合之外的路径时，不得选择。
