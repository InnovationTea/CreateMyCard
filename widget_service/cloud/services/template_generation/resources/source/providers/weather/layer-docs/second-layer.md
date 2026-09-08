# 第二层业务模板使用规则

- Provider：`com.huawei.weather.cli`；业务领域为 `WeatherOverview`。
- 调用统一使用 `Template("TemplateId@1", props)`；不再输出 Variant。
- 可用模板：
  - `WeatherOverviewHeroTitle@1`：左侧城市，右侧可选天气现象和温度；只用于
    `HeroTitleContentActionLayout@1` 的第一个业务 child。
  - `WeatherOverviewCompact@1`：城市、温度、天气现象和感冒指数；可选 `conditionIcon`。
  - `WeatherOverviewUvCompact@1`：城市、温度、天气现象和紫外线等级；可选 `conditionIcon`。
  - `WeatherOverviewTemperatureSupport@1`：城市、温度和天气现象，兼容格式化温度或纯数值摄氏温度；
    体感温度可选并与天气现象合并到 12vp 辅助行。可选 `conditionIcon` 与内部事件 `actionId`，
    图标只在该 Support 收到 `actionId` 时显示。
  - `WeatherOverviewTemperatureUvSupport@1`：城市、温度、天气现象和紫外线等级；纯文本，
    不接收图标；可选内部事件 `actionId`。
  - `WeatherOverviewTemperaturecoldLevelSupport@1`：城市、温度、天气现象和感冒风险；纯文本，
    不接收图标；可选内部事件 `actionId`。保留声明中的小写 coldLevel，不更改模板 ID。
    基础 Support 以天气现象为必需数据，温度、体感、城市和区县可选；另两种 Support 仍以温度为主数据，
    天气现象及各自风险指数为次要数据；城市和区县可选，
    可接收 `location` 兜底。不能让基础温度模板覆盖不存在的紫外线或感冒风险展示。
  - `WeatherOverviewHero@1`：温度天气 Hero；可选 `conditionIcon`。
  - `WeatherOverviewConditionHero@1`：以当前天气现象为主焦点的 Hero；城市与 `conditionIcon` 可选。
  - `WeatherOverviewFull@1`：完整温度天气摘要；可选 `conditionIcon`。
  - `WeatherOverviewHumidityFull@1`：以湿度为主焦点的完整天气摘要。
  - `WeatherOverviewUvFull@1`：以紫外线为主焦点的完整天气摘要。
  - `WeatherOverviewAirQualityHero@1`：以空气质量为主焦点的 Hero。
  - `WeatherOverviewAlertFull@1`：以天气预警为主焦点并显示更新时间的 Full；可选地点、预警和时间图标。
  - `WeatherOverviewCareAlertFull@1`：展示城市、天气预警、紫外线和空气质量的三段式关怀型 Full；可选紫外线图标，底部为右下角电话动作预留空间。
  - `WeatherOverviewWindHero@1`：展示城市、当前风向、风力等级和更新时间的 Hero；可选风向、时间和位置图标。
  - `WeatherOverviewDualCityFull@1`：并列展示两个天气数据绑定的温度与天气现象；城市名称可选。
  - `WeatherOverviewDailyDateFull@1`：明日日期天气 Full，突出天气现象，并展示日期和星期。
  - `WeatherOverviewDailyRainFull@1`：明日降雨 Full，突出降雨概率，并展示温度范围。
  - `WeatherOverviewDailyCompareFull@1`：双日天气对比 Full，并列展示 `daily[0]`、`daily[1]` 的天气现象和空气质量。
  - `WeatherOverviewDailyHealthFull@1`：明日健康指数 Full，突出紫外线等级，并展示空气质量和感冒指数。
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
- `windIcon`、`timeIcon`、`locationIcon` 必须分别匹配风况、时间和地点语义；风力等级直接绑定
  `/current/windLevel`，模板单独追加“级”，不得把单位写入数据路径或伪造静态风力。
- `alertIcon`、`rainIcon`、`uvIcon` 分别表达天气预警、降雨和紫外线语义；
  仅从对应参数允许的可信素材中选择，缺少匹配素材时省略可选图标，不得跨语义借用。
- 日出日落和 AQI 数值不在当前数据契约内，不得用静态值伪造；天气预警必须绑定
  `/current/alertLevel`，更新时间必须绑定 `/updatedAt`。
- 单业务模板的 `conditionIcon` 只允许与本轮 `/current/condition`
  一致的天气状态图标，不允许温度计；状态未知或缺少匹配的状态资源时省略图标，保留天气文本。
- 双业务 `TwoSupportLayout@1` 中，基础温度 Support 的 `conditionIcon` 可以选择表达气温的温度计，
  也可以选择与当前天气一致的状态图标。状态未知或缺少对应状态资源时仍可使用气温温度计；
  两类素材均不可用时省略。其它双业务天气模板没有图标槽位，不得额外添加。
- 两类场景的图标都必须属于该参数的 `allowedSources`，不能借双业务规则放宽单业务槽位。
- 图标着色遵循模板 Image 的显式声明，不依据文件名或天气语义猜测颜色。当前带图标模板已声明
  `fillColor`，温度计和天气状态图标均保留该主题色；模型不得追加原色保护或指定黄色、白色覆盖模板。
  需要保留原色的插画应由模板作者声明 `_preserveOriginalColor: true`，且不同时声明 `fillColor`。
- 不得使用体温/发热专用图标冒充气温，也不得使用与实际天气不一致的晴、雨、雪等图标，
  或从搭档业务借用时钟、日历、运动、睡眠、心率图标。不得为了匹配图标改变天气数据，
  也不得把静态太阳当作通用天气标识。
