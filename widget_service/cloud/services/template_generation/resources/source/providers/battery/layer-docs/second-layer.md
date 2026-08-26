# 第二层业务模板使用规则

- Provider：`com.huawei.battery.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BatteryOverviewNormalFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normal。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalHero@1`：手机电量摘要，面向 2x2 底部 PillAction 预留空间。 组件形态：normalHero。 布局场景：约 2x1.7；用于 2x2 主内容加一个 PillAction。主数据：/batterySOC；次要数据：/batteryCapacityLevelDesc；可选数据：/batterySOCText, /chargingStatusDesc。
  - `BatteryOverviewChargingFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：charging。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：low。 布局场景：完整 2x2；单独使用，或加一个 IconAction。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewPercentRingHero@1`：手机电量百分比环形 Hero，只表达顶部英雄内容，居中展示电量进度环和剩余电量百分比文本；底部按钮必须由第二层组合 `PillAction@1`。 组件形态：percentRingHero。 布局场景：约 2x1.7；主数据：/batterySOC, /batterySOCText；次要数据：无；可选数据：无。
  - `BatteryOverviewNormalWideFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalWide。 布局场景：完整 4x2；单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingWideFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingWide。 布局场景：完整 4x2；单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowWideFull@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowWide。 布局场景：完整 4x2；单独使用。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalPeer。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingPeer。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowPeer。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOC, /batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalPhoneCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalPhone。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOC, /batterySOCText；次要数据：无；可选数据：无。
  - `BatteryOverviewChargingPhoneCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingPhone。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOC, /batterySOCText；次要数据：无；可选数据：无。
  - `BatteryOverviewLowPhoneCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowPhone。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOC, /batterySOCText；次要数据：无；可选数据：无。
  - `BatteryOverviewNormalWeatherCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalWeather。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingWeatherCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingWeather。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowWeatherCompact@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowWeather。 布局场景：约 2x1；用于双 Compact 组合，或单 Compact 加两个 PillAction。主数据：/batterySOCText；次要数据：/chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `batteryIcon` 表达电池、电量或当前充电状态，不得使用动作图标或其他设备品类图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配，没有合适候选时省略。
- 当目标尺寸为 `2x2` 且 `selectedActionEventIds` 恰好一个时，按钮只能由第二层输出
  `PillAction@1` 并放入 `HeroActionLayout@1`，业务模板本身不得携带按钮；如果显式要求展示电量进度环和剩余电量百分比，
  只要 `/batterySOC` 与 `/batterySOCText` 可用，就可以选择 `BatteryOverviewPercentRingHero@1`，不要根据电量高低限制使用。
