# 第二层业务模板使用规则

- Provider：`com.huawei.weather.cli`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `WeatherOverviewCompact@1`：当前天气摘要，展示地点、温度和天气状态，可补充空气质量与温度范围。 组件形态：compact。 必需数据：/location/districtName, /current/temperatureText, /current/condition, /current/airQuality, /daily/0/temperatureRangeText；可选数据：无。
  - `WeatherOverviewCompactIcon@1`：当前天气摘要，展示地点、温度和天气状态，可补充空气质量与温度范围。 组件形态：compactIcon。 必需数据：/location/districtName, /current/temperatureText, /current/condition, /current/airQuality, /daily/0/temperatureRangeText；可选数据：无。
  - `WeatherOverviewHero@1`：当前天气摘要，展示地点、温度和天气状态，可补充空气质量与温度范围。 组件形态：hero。 必需数据：/location/districtName, /current/temperatureText, /current/condition, /current/airQuality, /daily/0/temperatureRangeText；可选数据：无。
  - `WeatherOverviewHeroIcon@1`：当前天气摘要，展示地点、温度和天气状态，可补充空气质量与温度范围。 组件形态：heroIcon。 必需数据：/location/districtName, /current/temperatureText, /current/condition, /current/airQuality, /daily/0/temperatureRangeText；可选数据：无。

- props 只能使用本次 Prompt 下发的可信文本、数值或素材；不得输出数据路径。
- 选择能够完整表达用户显式要求字段且自身 requiredData 全部可用的模板。
- `conditionIcon` 必须表达本轮 `/current/condition` 对应的天气现象，不得用泛天气图标覆盖明显不同的晴、雨、雪等状态；它不绑定固定素材 ID，只在本轮素材候选中匹配，没有合适候选时选择无图标模板。
