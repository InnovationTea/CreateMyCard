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
  - `{{dataRoot:ViewWeather}}/current/windDirection`
  - `{{dataRoot:ViewWeather}}/current/windLevel`
  - `{{dataRoot:ViewWeather}}/current/alertLevel`
  - `{{dataRoot:ViewWeather}}/updatedAt`
  - `{{dataRoot:ViewWeather}}/daily/0/condition`
  - `{{dataRoot:ViewWeather}}/daily/0/airQuality`
  - `{{dataRoot:ViewWeather}}/daily/1/date`
  - `{{dataRoot:ViewWeather}}/daily/1/weekday`
  - `{{dataRoot:ViewWeather}}/daily/1/condition`
  - `{{dataRoot:ViewWeather}}/daily/1/temperatureRangeText`
  - `{{dataRoot:ViewWeather}}/daily/1/rainProbabilityPercent`
  - `{{dataRoot:ViewWeather}}/daily/1/airQuality`
  - `{{dataRoot:ViewWeather}}/daily/1/uvIndex`
  - `{{dataRoot:ViewWeather}}/daily/1/coldLevel`
- 适用于以温度、天气现象、湿度、紫外线、空气质量等级、天气预警或风况为主焦点的天气卡片。
- 用户只要求天气概览时，若本轮提供 `temperatureText` 则优先以温度为主焦点；仅提供 `condition` 时，
  使用天气现象 Hero。用户明确要求湿度、紫外线或空气质量时，切换到对应主数据模板。
- 用户明确要求天气预警和更新时间，且 `alertLevel`、`updatedAt` 均可用时，使用天气预警 Full。
- 用户明确要求城市、风向、风力和更新时间，且对应字段均可用时，使用风况天气 Hero。
- 2x2 请求同时包含 `ViewWeather` 与其他数据能力，且 `userQuery`、`title` 或 `description` 明确要求展示天气、温度、天气现象、紫外线或空气质量时，必须保留 `WeatherOverview`，不得因为另一个业务组件可单独成卡而丢弃天气。
- 2x2 恰好包含两个数据业务和一个显式 Action 时，天气可使用 `WeatherOverviewHeroTitle@1`，
  并固定作为第一个业务位置；不得用 Hero 或 Full 冒充。此标题模板的城市、区县、温度及天气现象均可选，
  不要求温度字段必须存在；用户仅要求展示天气现象时，不得额外把温度加入必须展示字段。
- 组合标题右侧按可用字段显示“天气现象 | 温度”、单独现象或单独温度；两者都缺失时只保留城市标题。
  选择的模板仍须完整覆盖本轮用户显式要求的字段，不得借可选字段静默删减需求；单业务模板的必填门禁不变。
- 支持模板已声明的 `daily[0]`、`daily[1]` 逐日 Item 字段；不支持小时预报、超出模板声明范围的多日列表、AQI 数值、日出日落、气压或能见度。
- 根据 `userQuery` 判断出的必须显示天气字段存在上述支持集合之外的路径时，不得选择。
- 城市标题按可用性依次使用 `prefectureName`、`districtName`；两者都缺失时允许第二层传入受信的
  `location`，仍缺失则显示模板默认文案。该选择由模板生成期三元表达式确定，不生成运行时三元表达式。
