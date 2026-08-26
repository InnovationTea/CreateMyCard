# 第二层业务模板使用规则

- Provider：`com.huawei.weather.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
- `WeatherOverviewCompact@1`：温度紧凑摘要；约 2x1，用于双 Compact，或单 Compact 加两个
  PillAction。主数据：`/current/temperatureText`；次要数据：`/location/districtName`、
  `/current/condition`、`/current/coldLevel`；可选数据：无。
- `WeatherOverviewHero@1`：温度 Hero 摘要；约 2x1.7，只用于一个 Hero 加一个 PillAction。
  主数据：`/current/temperatureText`；次要数据：`/location/districtName`、
  `/current/condition`；可选数据：无。
- `WeatherOverviewFull@1`：完整温度摘要；完整 2x2，可单独使用或加一个 IconAction。
  主数据：`/current/temperatureText`；次要数据：`/location/districtName`、
  `/current/condition`、`/current/airQuality`、`/current/coldLevel`；可选数据：无。
- `WeatherOverviewConditionFull@1`：天气现象摘要；完整 2x2，可单独使用或加一个 IconAction。
  主数据：`/current/condition`；次要数据：`/location/districtName`、
  `/current/temperatureText`、`/current/airQuality`、`/current/coldLevel`；可选数据：无。
- `WeatherOverviewHumidityFull@1`：湿度摘要；完整 2x2，可单独使用或加一个 IconAction。
  主数据：`/current/humidityPercent`；次要数据：`/location/districtName`、
  `/current/condition`、`/current/temperatureText`、`/current/airQuality`、
  `/current/coldLevel`；可选数据：无。
- `WeatherOverviewUvFull@1`：紫外线摘要；完整 2x2，可单独使用或加一个 IconAction。
  主数据：`/current/uvIndex`；次要数据：`/location/districtName`、`/current/condition`、
  `/current/temperatureText`、`/current/airQuality`、`/current/coldLevel`；可选数据：无。
- `WeatherOverviewAirQualityHero@1`：空气质量 Hero 摘要；约 2x1.7，只用于一个 Hero 加一个
  PillAction。主数据：`/current/airQuality`；次要数据：`/location/districtName`、
  `/current/condition`；可选数据：无。
- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- `conditionIcon` 表达本轮 `/current/condition` 对应的天气现象，不得用泛天气图标覆盖明显不同的
  晴、雨、雪等状态。所有天气业务模板都将它作为可选素材参数，不绑定固定素材 ID；只在本轮
  素材候选中存在语义匹配项时传入，没有合适候选时省略参数，模板内部通过 `IfPresent` 决定是否
  渲染图标。
- HTML 中的日出日落和 AQI 数值场景不在当前 `ViewWeather` 数据契约内，不得用静态值伪造。
