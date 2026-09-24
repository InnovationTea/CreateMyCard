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
- 用户明确要求剩余电量、充电电流、充电电压和电池识别状态，且四个字段均可用时，选择充电诊断 WideFull 模板（2x4，无需动作）。
- `2x2` 多业务场景中，用户要求展示手机电量和充电状态且两个字段均可用时，可以选择
  `BatteryOverviewSupport@1`；该模板只占 `TwoSupportLayout@1` 的一个业务槽位。
  该 Support 的数值电量与充电状态均为硬必选；带单位电量文本可选，但不能替代缺失的数值电量。
- `BatteryOverviewSupportHero@1` 是预留的约 1.5x2 竖版电量面板，数据要求与
  `BatteryOverviewSupport@1` 一致；仅在布局提供对应 1.5x2 槽位时选择，当前没有布局提供该槽位。
- 根据 `userQuery` 判断出的必须显示电量字段存在支持集合之外的路径时，不得选择。
- `2x4` 多业务场景中，用户要求展示手机电量和充电状态且两个字段均可用时，可以选择
  `BatteryOverviewStatusHero@1`；该模板占据 `WideTwoFocus` 系列左右双焦点布局的一个 Hero 槽位，
  数值电量与充电状态均为硬必选。
- `2x4` 多业务场景中，用户要求展示手机电量且 `/batterySOC` 可用时，可以选择
  `BatteryOverviewChargeStatusHero@1`；该模板占据 `WideTwoFocus` 系列左右双焦点布局的一个 Hero
  槽位。充电状态与充电器类型为可选数据，可用时进入字段覆盖契约，缺失时不阻塞选择；模板不展示
  这两个字段，需要向用户展示充电状态时改选 `BatteryOverviewStatusHero@1`。电池温度为可选数据，
  可用时替换该模板顶部“手机”标题为电池温度文本；`2x4` 多业务场景中用户显式要求电池温度时，
  优先选择该模板展示电池温度。
