# 第二层业务模板使用规则

- Provider：`com.huawei.weather.cli`；业务领域为 `WeatherOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `WeatherOverviewHeroTitle@1`：左侧城市，右侧可选天气现象和温度；只用于
    `HeroTitleContentActionLayout@1` 的第一个业务 child。
  - `WeatherOverviewCompact@1`：城市、温度、天气现象和感冒指数；可选 `conditionIcon`。
  - `WeatherOverviewUvCompact@1`：城市、温度、天气现象和紫外线等级；可选 `conditionIcon`。
  - `WeatherOverviewTemperatureSupport@1`：城市、温度和天气现象；可选
    `conditionIcon` 与内部事件 `actionId`。
  - `WeatherOverviewTemperatureUvSupport@1`：城市、温度、天气现象和紫外线等级；纯文本，
    不接收图标；可选内部事件 `actionId`。
  - `WeatherOverviewTemperaturecoldLevelSupport@1`：城市、温度、天气现象和感冒风险；纯文本，
    不接收图标；可选内部事件 `actionId`。保留声明中的小写 coldLevel，不更改模板 ID。
    三种 Support 均以温度为主数据，天气现象及各自风险指数为次要数据；城市和区县可选，
    可接收 `location` 兜底。不能让基础温度模板覆盖不存在的紫外线或感冒风险展示。
  - `WeatherOverviewHero@1`：温度天气 Hero；可选 `conditionIcon`。
  - `WeatherOverviewFull@1`：完整温度天气摘要；可选 `conditionIcon`。
  - `WeatherOverviewHumidityFull@1`：以湿度为主焦点的完整天气摘要。
  - `WeatherOverviewUvFull@1`：以紫外线为主焦点的完整天气摘要。
  - `WeatherOverviewAirQualityHero@1`：以空气质量为主焦点的 Hero。
- Compact 只用于 `CompactTwoActionLayout@1` 加两个 `PillAction@1`；Hero 只用于
  `HeroActionLayout@1` 加一个 `PillAction@1`；Full 用于无 Action，或搭配一个语义匹配的
  `IconAction@1`。
- HeroTitle 只用于双业务单 Action 的 `HeroTitleContentActionLayout@1`，并且必须位于
  HeroContent 之前的第一个业务位置；布局最后一个 child 必须是 `PillAction@1`。
- 天气 HeroTitle 的城市、区县、温度及天气现象均为可选绑定；不得因缺少温度拒绝该模板或要求补造温度。
  模板固定采用高 18、间距 4、左对齐的紧凑 Row，以 12vp 辅助色文本依次展示城市和天气信息；天气信息
  依次选择“天气现象 | 温度”、单独现象或单独温度，两者都缺失时不生成后续内容，也不保留分隔符。
  模型不要重排或拆分模板内部布局。
  分支由编译器按绑定存在性裁剪，不读取空样例值；城市兜底仍遵循下方 location 规则。
- Support 只用于 `TwoSupportLayout@1`。Planner 可在数据 Search 后选择该布局；该业务有已批准事件时
  传入 `actionId`，没有对应事件时省略，模板根节点不生成 `onClick`。
- Props 只能使用本轮 Prompt 下发的可信素材或批准事件 ID，不得输出数据路径。
- 候选模板声明 `location?: string` 时，该 Prop 只作为可选兜底文案。模板优先使用可用的城市或区县
  数据绑定；只有两个位置数据路径都不可用时才使用该 Prop，Prop 也缺失时显示“当前城市”。
- 选择能够完整表达用户显式字段且自身 `primaryData` 与 `secondaryData` 全部可用的模板。
- 单业务 Compact、UvCompact、Hero、Full 的 `conditionIcon` 只允许与本轮 `/current/condition`
  一致的天气状态图标，不允许温度计；状态未知或缺少匹配的状态资源时省略图标，保留天气文本。
- 双业务 `TwoSupportLayout@1` 中，基础温度 Support 的 `conditionIcon` 可以选择表达气温的温度计，
  也可以选择与当前天气一致的状态图标。状态未知或缺少对应状态资源时仍可使用气温温度计；
  两类素材均不可用时省略。其它双业务天气模板没有图标槽位，不得额外添加。
- 两类场景的图标都必须属于该参数的 `allowedSources`，不能借双业务规则放宽单业务槽位。
- 不得使用体温/发热专用图标冒充气温，也不得使用与实际天气不一致的晴、雨、雪等图标，
  或从搭档业务借用时钟、日历、运动、睡眠、心率图标。不得为了匹配图标改变天气数据，
  也不得把静态太阳当作通用天气标识。
- 日出日落、天气预警和 AQI 数值不在当前数据契约内，不得用静态值伪造。
