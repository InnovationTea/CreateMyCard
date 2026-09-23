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
- `2x2` 多业务场景中，用户要求展示手机电量和充电状态且两个字段均可用时，可以选择
  `BatteryOverviewSupport@1`；该模板只占 `TwoSupportLayout@1` 的一个业务槽位。
  该 Support 的数值电量与充电状态均为硬必选；带单位电量文本可选，但不能替代缺失的数值电量。
- 根据 `userQuery` 判断出的必须显示电量字段存在支持集合之外的路径时，不得选择。

### 单电量 2x2 的字段筛选优先规则

- 先读取本轮 userQuery，区分明确要求与可选候选；标题、描述、样例值、输入候选齐全都不能扩大明确需求。
- 明确要求的字段必须保留。未提及的字段只作为可选候选：模板有且输入存在就可附带展示，模板没有就不展示，不应加入 requiredOutputFieldsByCapability。
- 对“电池情况”“电池状态”等模糊概览，先以剩余电量为基本需求，结合明确提到的充电状态或健康等目标；不能自动展开为充电器类型、温度、电流、电压、更新时间等全部候选。
- 使用 batteryTemplateReference 核对当前全部可用模板的 displayFields、requiredInputFields、optionalInputFields 和 missingInputFields。先保证 query 明确需求被覆盖、模板输入齐全，再优先选择有完整方案的合理字段解释；不能为命中模板删掉明确需求，也不能伪造缺失的数值字段。
- “充电状态和电池情况”通常保留 /chargingStatusDesc 和可用的电量字段；有 /batterySOCText 时可用该文本字段。/healthStatusDesc、/pluggedTypeDesc、/batteryTemperatureText 未被明确要求时仅为候选。不能因为输入提供 /pluggedTypeDesc 就强制模板显示充电类型。
- 没有明确动作时，无合法候选动作或用户禁止交互则采用 Full；有合法候选动作且允许交互则 Full 与 Hero 加动作平等参与候选字段数量比较，不设 Full 优先；候选字段仍原样保留供后续模板绑定，不输出新的候选字段协议，不直接输出模板或布局。

- 多个模板完整覆盖必选字段且输入与动作布局满足时，优先选择能展示更多候选字段的模板。只计算输入实际提供且模板支持的不同字段，不把候选提升为必选、不编造缺失字段。
