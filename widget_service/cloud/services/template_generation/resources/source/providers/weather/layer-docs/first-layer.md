# 天气高级组件首层规则

## WeatherOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:ViewWeather}}/location/districtName`
  - `{{dataRoot:ViewWeather}}/current/temperatureText`
  - `{{dataRoot:ViewWeather}}/current/condition`
  - `{{dataRoot:ViewWeather}}/current/airQuality`
  - `{{dataRoot:ViewWeather}}/daily/0/temperatureRangeText`
- 适用于当前天气、天气卡片和天气通勤摘要。
- 不支持小时/多日预报、湿度、风力、紫外线、预警、AQI 数值、日出日落、气压或能见度。
- 根据 `userQuery` 判断出的必须显示天气字段存在上述支持集合之外的路径时，不得选择。
