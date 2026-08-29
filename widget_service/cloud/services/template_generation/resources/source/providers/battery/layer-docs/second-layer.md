# 第二层业务模板使用规则

- Provider：`com.huawei.battery.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BatteryOverviewNormal@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normal。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalHero@1`：2x2 手机电量摘要，为底部 PillAction 预留空间。 组件形态：normalHero。 必需数据：/batterySOC, /batteryCapacityLevelDesc；可选数据：/batterySOCText, /chargingStatusDesc。
  - `BatteryOverviewCharging@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：charging。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLow@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：low。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalWide@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalWide。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingWide@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingWide。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowWide@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowWide。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalPeer@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalPeer。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingPeer@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingPeer。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowPeer@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowPeer。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewNormalPhone@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalPhone。 必需数据：/batterySOC, /batterySOCText；可选数据：无。
  - `BatteryOverviewChargingPhone@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingPhone。 必需数据：/batterySOC, /batterySOCText；可选数据：无。
  - `BatteryOverviewLowPhone@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowPhone。 必需数据：/batterySOC, /batterySOCText；可选数据：无。
  - `BatteryOverviewNormalWeather@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normalWeather。 必需数据：/batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewChargingWeather@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：chargingWeather。 必需数据：/batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
  - `BatteryOverviewLowWeather@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：lowWeather。 必需数据：/batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。

- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
- `batteryIcon` 表达电池、电量或当前充电状态，不得使用动作图标或其他设备品类图标替代；它不绑定固定素材 ID，只在本轮素材候选中匹配，没有合适候选时省略。
- 当目标尺寸为 `2x2`、`selectedActionEventId` 非空且电量状态为 normal 时，必须选择 `BatteryOverviewNormalHero@1`，并放入带末尾 `PillAction` 的 `HeroActionLayout@1`；无动作的 2x2 仍选择 `BatteryOverviewNormal@1`，2x4 仍选择 `BatteryOverviewNormalWide@1`。
