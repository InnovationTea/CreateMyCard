# 天气高级组件二层规则

## WeatherOverview

- 调用：`Template("WeatherOverview@1", "heroIcon|compactIcon", params)`。
- 单业务或 2x4 主视觉使用 `heroIcon`；2x2 多业务、support 或 peer 使用 `compactIcon`。
- `params` 只允许 `conditionIcon`，必须逐字复制与天气状态语义匹配的 `trustedAssetSources` 项。
- `conditionIcon` 不得省略或自行生成路径；不得输出旧 `WeatherOverview(...)` 构造器。
- 城市、温度、天气状态、空气质量和温度范围由服务端从可信路径绑定，模型不得重复传参或改写。
