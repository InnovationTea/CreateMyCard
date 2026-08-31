# 第二层业务模板使用规则

- Provider：`com.huawei.battery.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BatteryOverviewNormalFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normal。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalHero@1`：手机电量摘要，面向 2x2 底部 PillAction 预留空间。 组件形态：normalHero。 布局场景：约 2x1.7；用于 2x2 主内容加一个 PillAction。主数据：/batterySOC；次要数据：/batteryCapacityLevelDesc；可选数据：/batterySOCText, /chargingStatusDesc。
  - `BatteryOverviewChargingFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：charging。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：low。 布局场景：完整 2x2；无 Action 时单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewPercentRingHero@1`：手机电量百分比环形 Hero，只表达顶部英雄内容，居中展示电量进度环和剩余电量百分比文本；底部按钮必须由第二层组合 `PillAction@1`。 组件形态：percentRingHero。 布局场景：约 2x1.7；主数据：/batterySOC, /batterySOCText；次要数据：无；可选数据：无。
  - `BatteryOverviewProgressCompact@1`：手机电量进度条紧凑区；约 2x1，用于一个 Compact 加两个 `PillAction@1` 的 2x2 组合。只表达上半区，展示“手机电量”、`/batterySOCText`、基于 `/batterySOC` 的横向进度条和 `/batteryCapacityLevelDesc` 状态文案；底部两个按钮必须由第二层组合 `PillAction@1`。主数据：/batterySOC, /batterySOCText；次要数据：/batteryCapacityLevelDesc；可选数据：无。props 不允许传入数据值。
  - `BatteryOverviewChargingProgressHero@1`：手机电量充电进度 Hero，只表达顶部英雄内容，展示“手机电量”、`/batterySOC` 数字、基于 `/batterySOC` 的横向进度条，以及 `/chargingStatusDesc`、`/healthStatusDesc`、`/pluggedTypeDesc` 状态摘要；底部按钮必须由第二层组合 `PillAction@1`。组件形态：chargingProgressHero。布局场景：约 2x1.7；主数据：/batterySOC；次要数据：/chargingStatusDesc, /healthStatusDesc, /pluggedTypeDesc；可选数据：无。props 不允许传入数据值。
  - `BatteryOverviewHealthLevelHero@1`：电池健康与当前电量等级 Hero，只表达顶部英雄内容，展示“电池体检”、`/healthStatusDesc` 和 `/batteryCapacityLevelDesc`；底部按钮必须由第二层组合 `PillAction@1`。组件形态：healthLevelHero。布局场景：约 2x1.7；主数据：/healthStatusDesc；次要数据：/batteryCapacityLevelDesc；可选数据：无。props 不允许传入数据值。
  - `BatteryOverviewChargingDiagnosticsHero@1`：充电诊断 Hero，只表达顶部英雄内容，展示“充电诊断”，并竖排展示 `/chargingStatusDesc`、`/nowCurrentText`、`/voltageText`、`/isBatteryPresentText` 四个 key-value；底部按钮必须由第二层组合 `PillAction@1`。组件形态：chargingDiagnosticsHero。布局场景：约 2x1.7；主数据：/chargingStatusDesc；次要数据：/nowCurrentText, /voltageText, /isBatteryPresentText；可选数据：无。props 不允许传入数据值。
  - `BatteryOverviewNormalWideFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalWide。 布局场景：完整 4x2；单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingWideFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingWide。 布局场景：完整 4x2；单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowWideFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowWide。 布局场景：完整 4x2；单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalWeatherCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalWeather。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingWeatherCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingWeather。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowWeatherCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowWeather。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewTemperatureIconCompact@1`：手机电池温度图标紧凑行；约 2x1，用于 2x2 双层 Compact 组合的下层。左侧固定展示 `/batteryTemperatureText` 和“手机温度”，右侧为 `batteryIcon` SVG 占位。主数据：/batteryTemperatureText；次要数据：无；可选数据：无。
  - `BatteryOverviewStatusIconCompact@1`：手机电量状态图标紧凑行；约 2x1，用于 2x2 双层 Compact 组合。左侧固定展示 `/batterySOCText` 和可选 `/batteryCapacityLevelDesc`，右侧为 `batteryIcon` SVG 占位。主数据：/batterySOCText；次要数据：无；可选数据：/batteryCapacityLevelDesc。
  - `BatteryOverviewNormalPowerTemperatureIconCompact@1`：正常电量状态下的手机电量与电池温度图标紧凑行；约 2x1，用于 2x2 双层 Compact 组合。左侧两行固定展示“手机电量 `/batterySOC`%”和“手机温度 `/batteryTemperatureText`”，右侧为 `batteryIcon` SVG 占位。主数据：/batterySOC, /batteryTemperatureText；次要数据：无；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `batteryIcon` 表达电池、电量或当前充电状态，不得使用动作图标或其他设备品类图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配。选择带 `batteryIcon` 参数的模板时，必须从本轮电量相关素材候选中传入一个匹配素材。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好两个、用户需要电量进度条并同时需要两个动作时，优先选择
  `BatteryOverviewProgressCompact@1`，并把两个动作分别作为末尾连续的 `PillAction@1` 放入
  `CompactTwoActionLayout@1`；业务模板本身不得携带按钮。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个时，按钮只能由第二层输出
  `PillAction@1` 并放入 `HeroActionLayout@1`，业务模板本身不得携带按钮；如果显式要求展示电量进度环和剩余电量百分比，
  只要 `/batterySOC` 与 `/batterySOCText` 可用，就可以选择 `BatteryOverviewPercentRingHero@1`，不要根据电量高低限制使用。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求充电进度条、电池健康和充电器类型，且
  `/batterySOC`、`/chargingStatusDesc`、`/healthStatusDesc`、`/pluggedTypeDesc` 均可用时，优先选择
  `BatteryOverviewChargingProgressHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求电池健康和当前电量等级，且
  `/healthStatusDesc`、`/batteryCapacityLevelDesc` 均可用时，优先选择
  `BatteryOverviewHealthLevelHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求充电诊断、充电电流、电压和电池状态，且
  `/chargingStatusDesc`、`/nowCurrentText`、`/voltageText`、`/isBatteryPresentText` 均可用时，优先选择
  `BatteryOverviewChargingDiagnosticsHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
