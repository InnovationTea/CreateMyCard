# 手机电量高级组件首层规则

## BatteryOverview

- `BatteryOverviewChargingTemperatureFull@1` 用于充电温度与电量三项文本的2x2无动作卡片：
  参考HealthTemperature的状态与温度结构，标题使用传入title，缺省显示“手机电池”；
  大字充电状态、下方温度、左下角电量。
  三项均必需；无需电池健康、充电器类型、图标或数值电量。字段齐全时优先参考此完整模板，
  仅有温度和电量的请求仍使用TemperatureStatusFull，不推断温度正常或快充。

- `BatteryOverviewChargingTypePercentFull@1` 仅要求电量百分比文本、充电状态、充电器类型，
  支持 2x2 单焦点和 2x4 与天气 Full 组合。不要因缺少数值电量、等级或健康状态排除它。

- `BatteryOverviewTemperatureStatusFull@1` 是居中title/温度/电量三段2x2无动作Full：仅温度必需，
  电量文本、充电状态与充电器类型可选，无素材要求。title缺省为“手机电池”，电量位于底行。
- `BatteryOverviewPercentStatusFull@1` 是充电状态 Hero 的 2x2 无动作 Full：仅电量文本必需，
  充电状态、健康、等级、温度和更新时间可选。两者的充电状态均放在左下角，沿用通用排序。

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
- 电池温度 Full 的温度图标为可选项；没有温度素材时仍可选择，数据要求保持不变。
- `BatteryOverviewFull@1` 的电池图标为可选项；四项电量数据齐全时，无素材也可选择，
  保留进度环、百分比文本、充电状态和电量等级，环内默认显示字母“E”作为电量标识。
- 用户明确要求充电电流、充电电压、电量等级和电池识别状态，且四个字段均可用并带一个动作时，选择充电诊断 Hero 模板。

- 用户明确要求剩余电量、充电电流、充电电压和电池识别状态，且四个字段均可用时，选择充电诊断 WideFull 模板（2x4，无需动作）。
- `2x2` 多业务场景中，用户要求展示手机电量和充电状态且两个字段均可用时，可以选择
  `BatteryOverviewSupport@1`；该模板只占 `TwoSupportLayout@1` 的一个业务槽位。
  该 Support 的数值电量与充电状态均为硬必选；带单位电量文本可选，但不能替代缺失的数值电量。
- `2x2` 多业务场景中，用户要求展示电量百分比文本（可选叠加充电状态）且 `/batterySOCText` 可用、
  无数值电量时，可以选择 `BatteryOverviewPhoneTextSupport@1`；该模板只占
  `TwoSupportLayout@1` 的一个业务槽位，充电状态为可选辅行，缺失时省略。
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


### 单电量 2x2 的字段筛选优先规则

- `BatteryOverviewPercentHealthCurrentDetailsFull@1`：2x2 无动作的百分比、健康与电流详情 Full。
  必需 /batterySOCText、/chargingStatusDesc、/healthStatusDesc、/nowCurrentText，完整展示四项文本。
  无数值电量、素材或电压要求；当前电流保留原始文本及单位，沿用通用字段覆盖和候选排序。

- `BatteryOverviewPercentHealthDetailsFull@1`：2x2 无动作的百分比与健康详情 Full。
  必需 /batterySOCText、/chargingStatusDesc、/healthStatusDesc、/pluggedTypeDesc，完整展示四项文本。
  不依赖数值电量、电量等级或素材；沿用通用字段覆盖和布局排序，不改变用户明确需求。

- 先读取本轮 userQuery，区分明确要求与可选候选；标题、描述、样例值、输入候选齐全都不能扩大明确需求。
- 明确要求的字段必须保留。非必选、且未被用户明确禁止的字段才作为候选，模板有且输入存在时可附带展示；不要将候选放入 requiredOutputFieldsByCapability，不新增协议字段。
- 对“电池情况”“电池状态”等模糊概览，先以剩余电量为基本需求，结合明确提到的充电状态或健康等目标；不能自动展开为充电器类型、温度、电流、电压、更新时间等全部候选。
- 使用 batteryTemplateReference 核对当前全部可用模板的 displayFields、requiredInputFields、optionalInputFields 和 missingInputFields。先保证 query 明确需求被覆盖、模板输入齐全，再优先选择有完整方案的合理字段解释；不能为命中模板删掉明确需求，也不能伪造缺失的数值字段。
- “充电状态和电池情况”通常保留 /chargingStatusDesc 和可用的电量字段；有 /batterySOCText 时可用该文本字段。/healthStatusDesc、/pluggedTypeDesc、/batteryTemperatureText 未被明确要求且未被禁止时才作为候选。不能因为输入提供 /pluggedTypeDesc 就强制模板显示充电类型。
- 没有明确动作时，无合法候选动作或用户禁止交互则采用 Full；有合法候选动作且允许交互则 Full 与 Hero 加动作平等参与候选字段数量比较，不设 Full 优先；候选字段仍原样保留供后续模板绑定，不输出新的候选字段协议，不直接输出模板或布局。

- 多个模板完整覆盖必选字段且输入与动作布局满足时，尊重用户明确禁止的展示要求，并保证 primaryOutputFieldByCapability 所表达的显式唯一主焦点，最后比较实际展示的候选字段数量。仅声明、仅充当编译期条件或条件未满足而未渲染的字段不计入收益，不把候选提升为必选、不编造缺失字段。

- `BatteryOverviewChargingDiagnosticsFull@1` 支持 2×2 无动作的电流、电压、电量等级和电池在位状态展示；四项输入都必需，无图标要求。电量等级为主值，其余三项为辅助行。

- `BatteryOverviewHealthLevelFull@1`：2×2 无动作健康等级 Full。必需 /healthStatusDesc、/batteryCapacityLevelDesc，可选 /batterySOCText、/chargingStatusDesc。顶部“电池健康”，健康主值30fp/700，详情行12fp、标签400/值500左对齐；不依赖素材，不新增模板选择优先级。

- `BatteryOverviewPercentLevelFull@1`：2×2 无动作百分比等级 Full。必需 /batterySOCText、/batteryCapacityLevelDesc，无可选字段。居中三段式：顶部“手机电量”16fp/400、百分比主值38fp/700、底部实际电量等级12fp/400；段间距8vp，不显示电量等级标签；不依赖素材，不新增模板选择优先级。

- `BatteryOverviewCurrentVoltageFull@1`：2×2 电流电压 Full，仅必需 /nowCurrentText、/voltageText，可选 /batterySOCText、/batteryTemperatureText、/healthStatusDesc。标题12fp，所有数值12fp/500，标签12fp/400，各详情行高16vp，左对齐；无需图标或动作，字段存在时显示对应行，沿用通用检索和候选字段排序。

TemperatureStatusFull当前布局为居中三段式：顶部16fp title，缺省“手机电池”；
中间30fp温度，底部12fp“电量: ”加 /batterySOCText，只有温度必需。
电量、充电状态、充电器类型均可选；辅助信息存在时左侧展示，电量在右侧，
仅有电量时底行居中。没有任何底行数据时省略；请求标题非空时逐字传入title。
