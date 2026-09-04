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
- 单业务天气卡片适用于以温度、湿度、紫外线或空气质量等级为主焦点的场景；天气现象作为辅助内容展示，
  当前不提供以天气现象为独立主焦点的模板。
- 用户只要求天气概览时，优先以温度为主焦点；用户明确要求湿度、紫外线或空气质量时，切换到对应主数据模板。
- 2x2 请求同时包含 `ViewWeather` 与其他数据能力，且 `userQuery`、`title` 或 `description` 明确要求展示天气、温度、天气现象、紫外线或空气质量时，必须保留 `WeatherOverview`，不得因为另一个业务组件可单独成卡而丢弃天气。
- 2x2 恰好包含两个数据业务和一个显式 Action 时，天气可使用 `WeatherOverviewHeroTitle@1`，
  并固定作为第一个业务位置；不得用 Hero 或 Full 冒充。此标题模板的城市、区县、温度及天气现象均可选，
  不要求温度字段必须存在；用户仅要求展示天气现象时，不得额外把温度加入必须展示字段。
- 组合标题右侧按可用字段显示“天气现象 | 温度”、单独现象或单独温度；两者都缺失时只保留城市标题。
  选择的模板仍须完整覆盖本轮用户显式要求的字段，不得借可选字段静默删减需求；单业务模板的必填门禁不变。
- 不支持小时/多日预报、风力、预警、AQI 数值、日出日落、气压或能见度。
- 根据 `userQuery` 判断出的必须显示天气字段存在上述支持集合之外的路径时，不得选择。
- 城市标题按可用性依次使用 `prefectureName`、`districtName`；两者都缺失时允许第二层传入受信的
  `location`，仍缺失则显示模板默认文案。该选择由模板生成期三元表达式确定，不生成运行时三元表达式。
