# 手机电量高级组件首层规则

## BatteryOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:GetPhoneBatteryInfo}}/batterySOC`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batterySOCText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/chargingStatusDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batteryCapacityLevelDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/healthStatusDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/pluggedTypeDesc`
  - `{{dataRoot:GetPhoneBatteryInfo}}/batteryTemperatureText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/nowCurrentText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/voltageText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/isBatteryPresentText`
  - `{{dataRoot:GetPhoneBatteryInfo}}/updatedAt`
- 只表达手机本机电量、等级、充电状态、电池健康、充电器类型、电池温度、充电电流、充电电压、电池识别状态和更新时间，0% 合法。
- 支持电池健康状态、充电器类型、充电电流、充电电压和电池识别状态；不支持续航、预计充满时间或外设电量。
- 用户明确要求电池温度、充电器类型和更新时间，且三个字段均可用时，选择电池温度 Full 模板。
- 用户明确要求充电电流、充电电压、电量等级和电池识别状态，且四个字段均可用并带一个动作时，选择充电诊断 Hero 模板。
- 根据 `userQuery` 判断出的必须显示电量字段存在支持集合之外的路径时，不得选择。
