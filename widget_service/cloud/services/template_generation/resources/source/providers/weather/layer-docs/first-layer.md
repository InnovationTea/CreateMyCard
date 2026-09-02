# 天气高级组件首层规则

## WeatherOverview

- 支持的 TaskSpec 数据路径：
  - `{{dataRoot:ViewWeather}}/location/prefectureName`
  - `{{dataRoot:ViewWeather}}/location/districtName`
  - `{{dataRoot:ViewWeather}}/current/temperatureText`
  - `{{dataRoot:ViewWeather}}/current/condition`
  - `{{dataRoot:ViewWeather}}/current/humidityPercent`
  - `{{dataRoot:ViewWeather}}/current/airQuality`
  - `{{dataRoot:ViewWeather}}/current/uvIndex`
  - `{{dataRoot:ViewWeather}}/current/coldLevel`
- 适用于以温度、湿度、紫外线或空气质量等级为主焦点的天气卡片；天气现象作为辅助内容展示，
  当前不提供以天气现象为独立主焦点的模板。
- 用户只要求天气概览时，优先以温度为主焦点；用户明确要求湿度、紫外线或空气质量时，切换到对应主数据模板。
- 2x2 请求同时包含 `ViewWeather` 与其他数据能力，且 `userQuery`、`title` 或 `description` 明确要求展示天气、温度、天气现象、紫外线或空气质量时，必须保留 `WeatherOverview`，不得因为另一个业务组件可单独成卡而丢弃天气。
- 不支持小时/多日预报、风力、预警、AQI 数值、日出日落、气压或能见度。
- 根据 `userQuery` 判断出的必须显示天气字段存在上述支持集合之外的路径时，不得选择。
- 城市标题按可用性依次使用 `prefectureName`、`districtName`；两者都缺失时允许第二层传入受信的
  `location`，仍缺失则显示模板默认文案。该选择由模板生成期三元表达式确定，不生成运行时三元表达式。
