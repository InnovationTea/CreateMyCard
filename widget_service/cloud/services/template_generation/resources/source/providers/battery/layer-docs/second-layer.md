# 第二层业务模板使用规则

- Provider：`com.huawei.battery.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BatteryOverviewFull@1`：完整 2x2 电量摘要；展示电量进度环、剩余电量文本、充电状态和电量等级。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewHero@1`：约 2x1.7 的通用电量 Hero；展示电量进度环和电量等级，用于主内容加一个 `PillAction@1`。主数据：/batterySOC；次要数据：/batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewWideFull@1`：完整 4x2 电量摘要；横向展示电量进度环、剩余电量文本、充电状态和电量等级。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewCompact@1`：约 2x1 的通用电量摘要，用于一个 Compact 加两个 `PillAction@1`；固定展示 `/batterySOCText`，有 `/batteryCapacityLevelDesc` 时优先展示电量等级，否则在有值时展示 `/chargingStatusDesc`。主数据：/batterySOCText；次要数据：无；可选数据：/batteryCapacityLevelDesc, /chargingStatusDesc。
  - `BatteryOverviewPercentRingHero@1`：手机电量百分比环形 Hero，只表达顶部英雄内容，居中展示电量进度环和剩余电量百分比文本；底部按钮必须由第二层组合 `PillAction@1`。主数据：/batterySOC, /batterySOCText；次要数据：无；可选数据：无。
  - `BatteryOverviewChargingProgressHero@1`：手机电量充电进度 Hero，只表达顶部英雄内容，展示“手机电量”、`/batterySOC` 数字、横向进度条，以及 `/chargingStatusDesc`、`/healthStatusDesc`、`/pluggedTypeDesc` 状态摘要；底部按钮必须由第二层组合 `PillAction@1`。主数据：/batterySOC；次要数据：/chargingStatusDesc, /healthStatusDesc, /pluggedTypeDesc；可选数据：无。
  - `BatteryOverviewHealthLevelHero@1`：电池健康与当前电量等级 Hero，只表达顶部英雄内容，展示“电池体检”、`/healthStatusDesc` 和 `/batteryCapacityLevelDesc`；底部按钮必须由第二层组合 `PillAction@1`。主数据：/healthStatusDesc；次要数据：/batteryCapacityLevelDesc；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `batteryIcon` 表达电池、电量或当前充电状态，不得使用动作图标或其他设备品类图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配。选择带 `batteryIcon` 参数的模板时，必须从本轮电量相关素材候选中传入一个匹配素材。
- 通用 Full、Hero、WideFull 和 Compact 同时覆盖普通、充电中和低电量状态，不再根据状态选择重复模板 ID。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个时，按钮只能由第二层输出
  `PillAction@1` 并放入 `HeroActionLayout@1`，业务模板本身不得携带按钮；如果显式要求展示电量进度环和剩余电量百分比，
  只要 `/batterySOC` 与 `/batterySOCText` 可用，就可以选择 `BatteryOverviewPercentRingHero@1`，不要根据电量高低限制使用。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求充电进度条、电池健康和充电器类型，且
  `/batterySOC`、`/chargingStatusDesc`、`/healthStatusDesc`、`/pluggedTypeDesc` 均可用时，优先选择
  `BatteryOverviewChargingProgressHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个，用户显式要求电池健康和当前电量等级，且
  `/healthStatusDesc`、`/batteryCapacityLevelDesc` 均可用时，优先选择
  `BatteryOverviewHealthLevelHero@1`，并把动作作为末尾 `PillAction@1` 放入 `HeroActionLayout@1`。
