# 第二层业务模板使用规则

- Provider：`com.huawei.battery.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `BatteryOverviewNormal@1`：手机电量摘要，展示电量数值、文本、充电状态和电量等级。 组件形态：normal。 必需数据：/batterySOC, /batterySOCText, /chargingStatusDesc, /batteryCapacityLevelDesc；可选数据：无。
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
