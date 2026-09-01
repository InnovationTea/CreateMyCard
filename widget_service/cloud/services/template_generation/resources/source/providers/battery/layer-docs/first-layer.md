# 手机电量高级组件首层规则

## BatteryOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetPhoneBatteryInfo}}/batterySOC`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batterySOCText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/chargingStatusDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batteryCapacityLevelDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/healthStatusDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/pluggedTypeDesc`
- 只表达手机本机电量、等级、充电状态、电池健康和充电器类型，0% 合法。
- 支持电池健康状态和充电器类型；不支持充电电流、电压、电池存在状态、续航、预计充满时间或外设电量。
- 当前模板不展示电池温度；用户明确要求温度时不得进入模板路线。
- 根据 `userQuery` 判断出的必须显示电量字段存在支持集合之外的路径时，不得选择。
