# 第二层业务模板使用规则

- Provider：`com.huawei.battery.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BatteryOverviewFull@1`：完整 2x2 电量摘要；展示电量进度环、剩余电量文本、充电状态和电量等级。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewHero@1`：约 2x1.7 的通用电量 Hero；展示电量进度环和电量等级，用于主内容加一个 `PillAction@1`。主数据：/batterySOC；次要数据：/batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewWideFull@1`：完整 4x2 电量摘要；横向展示电量进度环、剩余电量文本、充电状态和电量等级。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewCompact@1`：约 2x1 的电量摘要，用于一个 Compact 加两个 `PillAction@1`；左侧以 44vp 环形进度展示 `/batterySOC` 并在环内放置电量图标，右侧展示百分比和 `/chargingStatusDesc`。主数据：/batterySOC；次要数据：/chargingStatusDesc；可选数据：无。
  - `BatteryOverviewPercentRingHero@1`：手机电量百分比环形 Hero，居中展示电量进度环和剩余电量百分比；
    显示文本通过端侧 Expr 拼接数值和百分号，不依赖格式化电量字段。底部按钮由第二层组合
    `PillAction@1`。主数据：/batterySOC；次要数据：无；可选数据：无。
  - `BatteryOverviewChargingRingHero@1`：手机电量充电状态环形 Hero，只表达顶部英雄内容，环内展示 `/batterySOC` 数字及百分号，环形进度同样使用 `/batterySOC`，环下展示 `/chargingStatusDesc`；底部按钮必须由第二层组合 `PillAction@1`。主数据：/batterySOC；次要数据：/chargingStatusDesc；可选数据：无。
  - `BatteryOverviewChargingProgressHero@1`：手机充电状态 Hero，展示“手机电量”、包含百分号的
    `/batterySOCText`、充电状态和电池健康；不展示进度条或充电器类型。
    底部按钮必须由第二层组合 `PillAction@1`。主数据：/batterySOCText；
    次要数据：无；可选数据：/chargingStatusDesc, /healthStatusDesc。两个可选字段都可用时合并展示，
    仅一个可用时单独展示，都不可用时不生成状态行；分支只按字段是否存在于本轮绑定进行编译期选择，
    不按样例值选择分支。
  - `BatteryOverviewChargingProgressFull@1`：手机电量充电进度 Full；顶部为标题，中部以 44vp 环形进度和电量图标展示 `/batterySOC` 与 `/chargingStatusDesc`，底部以两行相邻 key-value 展示 `/healthStatusDesc` 和 `/pluggedTypeDesc`。主数据：/batterySOC；次要数据：/chargingStatusDesc, /healthStatusDesc, /pluggedTypeDesc；可选数据：无。
  - `BatteryOverviewChargingDiagnosticsHero@1`：充电诊断 Hero，只表达顶部英雄内容；以两个圆角信息面板、每个面板两行 key-value 展示 `/nowCurrentText`、`/voltageText`、`/batteryCapacityLevelDesc` 和 `/isBatteryPresentText`；底部按钮必须由第二层组合 `PillAction@1`。主数据：/nowCurrentText, /voltageText；次要数据：/batteryCapacityLevelDesc, /isBatteryPresentText；可选数据：无。
  - `BatteryOverviewHealthLevelHero@1`：电池健康与当前电量等级 Hero，只表达顶部英雄内容，展示“电池体检”、`/healthStatusDesc` 和 `/batteryCapacityLevelDesc`；底部按钮必须由第二层组合 `PillAction@1`。主数据：/healthStatusDesc；次要数据：/batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewTemperatureFull@1`：电池温度 Full，顶部展示“电池温度”和右侧温度图标，中部依次展示 `/batteryTemperatureText` 与 `/pluggedTypeDesc`，底部两行展示“更新时间：”和 `/updatedAt`。主数据：/batteryTemperatureText；次要数据：/pluggedTypeDesc, /updatedAt；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `batteryIcon` 表达电池、电量或当前充电状态，不得使用动作图标或其他设备品类图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配。选择带 `batteryIcon` 参数的模板时，必须从本轮电量相关素材候选中传入一个匹配素材。
- 通用 Full、Hero、WideFull 和 Compact 同时覆盖普通、充电中和低电量状态，不再根据状态选择重复模板 ID。
- 选择 `BatteryOverviewCompact@1` 时，必须同时具备 `/batterySOC` 与 `/chargingStatusDesc`；`batteryIcon` 从本轮电量相关素材候选中选择。
- 当目标尺寸为 `2x2`、没有动作，且用户显式要求电池温度、充电器类型和更新时间时，三个字段均可用才选择
  `BatteryOverviewTemperatureFull@1`；`temperatureIcon` 从本轮温度相关素材候选中选择，优先使用 `asset.heat_generation`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个时，按钮只能由第二层输出
  `PillAction@1` 并放入 `HeroActionLayout@1`，业务模板本身不得携带按钮；如果显式要求展示电量进度环和剩余电量百分比，
  只要 `/batterySOC` 可用，就可以选择 `BatteryOverviewPercentRingHero@1`，不要根据电量高低限制使用。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求用电量进度环展示剩余电量和充电状态，且
  `/batterySOC`、`/chargingStatusDesc` 均可用时，优先选择 `BatteryOverviewChargingRingHero@1`，并把动作作为末尾
  `PillAction@1` 放入 `HeroActionLayout@1`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求电量百分比、充电状态和电池健康，且
  `/batterySOCText` 可用且显式要求的可选字段也可用时，优先选择
  `BatteryOverviewChargingProgressHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
- 当目标尺寸为 `2x2`、没有动作，用户显式要求充电进度条、充电状态、电池健康和充电类型，且
  `/batterySOC`、`/chargingStatusDesc`、`/healthStatusDesc`、`/pluggedTypeDesc` 均可用时，选择
  `BatteryOverviewChargingProgressFull@1` 并放入 `SingleFocusLayout@1`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求充电电流、充电电压、电量等级和电池识别状态，且
  `/nowCurrentText`、`/voltageText`、`/batteryCapacityLevelDesc`、`/isBatteryPresentText` 均可用时，优先选择
  `BatteryOverviewChargingDiagnosticsHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求电池健康和当前电量等级，且
  `/healthStatusDesc`、`/batteryCapacityLevelDesc` 均可用时，优先选择
  `BatteryOverviewHealthLevelHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
