# Provider 模板接入约定

全部业务模板的主数据、次要数据、可选数据、布局场景和运行状态见
[`provider-template-capability-checklist.md`](provider-template-capability-checklist.md)。

## 两类 Provider

业务 Provider 同时提供数据能力、第一层/第二层规则和 UI 模板。`dataDomain` 明确能力数据写入
TaskSpec 后的绝对根路径；模板内的数据路径始终相对该根路径：

`provider.json` 同时是业务模板归属的唯一事实源：

- 每个业务模板直接声明 `businessId` 和 `capabilityId`；
- `capabilities` 只声明数据根和 Schema，不重复枚举模板；
- Registry 从模板条目派生业务分组和模板归属，不维护独立高级组件清单；
- Layout Provider 使用 `layoutComponents` 声明布局尺寸、业务子节点和 Action 约束；
- 全局 UX 配置只保留 Token、Theme 场景映射和尺寸预算。

同一个模板 ID 只能在 `templates` 中出现一次。业务分组、数据能力归属和 Provider 归属均从该条目推导，
避免 `capabilities[].templates`、`businessComponents[].localTemplateIds` 和 `templates[]` 三处同步。

```json
{
  "firstLayerRule": {"path": "layer-docs/first-layer.md"},
  "secondLayerRule": {"path": "layer-docs/second-layer.md"},
  "capabilities": [{
    "capabilityId": "ViewWeather",
    "dataDomain": "/data/weather",
    "dataSchema": {
      "path": "capabilities/app-11.7.5.205_rom-6.0/data_capabilities.json",
      "version": "app-11.7.5.205_rom-6.0"
    }
  }],
  "templates": [{
    "templateId": "WeatherOverviewFull@1",
    "businessId": "WeatherOverview",
    "capabilityId": "ViewWeather",
    "description": "天气主视觉摘要。",
    "primaryData": ["/current/temperatureText"],
    "secondaryData": ["/current/condition"],
    "optionalData": ["/current/airQuality"],
    "entry": "templates/weather-overview.cardtpl"
  }]
}
```

布局 Provider 不拥有数据能力，因此不声明 `capabilities`、`businessId` 或 `capabilityId`，也不需要分层
领域规则：

```json
{
  "providerId": "com.huawei.layout.cli",
  "templates": [{
    "templateId": "SingleFocusLayout@1",
    "description": "单一焦点纵向骨架。",
    "entry": "templates/layout.cardtpl"
  }]
}
```

`dataSchema.path` 优先引用上游能力数据；没有稳定上游路径时允许指向 Provider 内的本地 Schema。
业务 Provider 的 CardSpec `writeResultTo` 必须和 `dataDomain` 完全一致，否则模板准入失败。

## UI 模板语法

### 条件能力边界

本轮暂缓运行时 `IF(...)`，模板、Tersel、A2UI-Compact 和公共 A2UI 均不接受 `If` 组件。
编译期 `#if/#elseif/#else/#endif/#end`、`#Expr` 和运行时属性表达式 `Expr(...)` 继续支持；
不得读取 `sampleValue` 来模拟运行时组件分支。保留能力、暂缓范围与验收要求见
[模板专项方案](template-generation-design.md)。

### 模板后缀与布局

业务模板 ID 必须以 `HeroTitle`、`HeroContent`、`Support`、`Compact`、`Hero`、`Full`、`WideHero`、
`WideFull` 之一结束。八类后缀分别表示：

- `HeroTitle`：双业务单 Action 的位置 0，后接一个 HeroContent；
- `HeroContent`：双业务单 Action 的位置 1，前置一个 HeroTitle；
- `Support`：约 `2x1`，保留给旧 LLM 选择器兼容测试和原子预览；事件按需绑定在 Support 内部，当前 Search 不可达；
- `Compact`：约 `2x1`，只用于一个 Compact 加两个 PillAction；
- `Hero`：约 `2x1.7`，用于 `2x2` 的 Hero 加一个 PillAction；
- `Full`：完整 `2x2`，无 Action 时单独使用，或在存在语义匹配图标素材时加一个 IconAction；
- `WideHero`：约 `4x1.7`，用于 `2x4` 的 WideHero 加一个 PillAction；
- `WideFull`：完整 `4x2`，单独使用。

业务模板不再重复声明 `supportedCardSizes` 和 `requiresLayoutAction`，Registry 直接从后缀推导。业务语义或
需要区分的状态写在后缀前，例如 `BatteryOverviewChargingProgressHero@1`；同一结构能够覆盖不同状态时使用
通用名称，例如 `BatteryOverviewCompact@1`。布局 Provider 不受此后缀约束。
同一 UI 形态的 `Support` 与 `Compact` 在业务族状态校验中使用相同状态判定规则，但形态标识和布局身份
仍分别保持 `Support` 与 `Compact`，不得把双业务 Support 放入单业务 Compact 布局。

每个 `Support` 模板提供可选的 `actionId` Prop，并在业务根节点的 options 中写入受控事件：

```text
"onClick": EventAction(props?.actionId)
```

`props?.actionId` 只允许作为 `EventAction` 的参数；Prop 有值时解析为对应 Action ID，缺失或值为
`None` 时返回 `None`，编译器随后省略整个 `onClick`，不创建 `EventAction`。没有已选事件时第二层省略
该 Prop；事件值只能来自第一层已批准候选，并由服务端按原始 `call/args` 可信绑定。

### `2x2` 固定布局组合

模板生成侧的 `2x2` 动作预算最多为一个主动作和一个次动作。Search 和第二层必须按下表
组合业务模板、布局和动作：

| 业务数 | 已选事件数 | 业务模板 | 布局与动作 |
| --- | ---: | --- | --- |
| 1 | 0 | `Full` | `SingleFocusLayout`，不生成 Action |
| 1 | 1 | `Hero` | `HeroActionLayout` + 1 个 `PillAction` |
| 1 | 1 | `Full` | 仅存在语义匹配的已批准图标素材时，使用 `FullIconActionLayout` + 1 个 `IconAction` |
| 1 | 2 | `Compact` | `CompactTwoActionLayout` + 2 个连续的 `PillAction` |
| 2 | 1 | 位置 0 为 `HeroTitle`；位置 1 为 `HeroContent` | `HeroTitleContentActionLayout` + 1 个末尾 `PillAction` |

当前 Search 的 `2x2` 组合只包含上表场景。双业务仅在两侧候选分别完整覆盖显式字段时适用，且由服务端
确定性重排为 HeroTitle、HeroContent；其它多业务组合在二层模型调用前显式拒绝。
`TwoSupportLayout`、`2x2-two-support` 与 Support 内部事件绑定仍保留给 `firstLayerComponentSelector="llm"` 兼容路径和原子预览，
但不进入当前 Search 生产路径。

Search 只保留能够独立完整覆盖所属业务显式字段的模板候选，不提前在 `Hero` 与
`Full + IconAction` 之间做最终视觉选择。第二层只能使用 Search 返回的候选、已批准事件和
已批准素材组成一个完整布局。已选事件必须各消费一次，不得重复、遗漏或改写归属；编译器对模板后缀、
布局、动作类型、位置和消费次数做确定性校验。

Provider 画廊可通过内部受信参数指定待测模板。该模式仍须经过 Search，并把第一层返回的展示字段与
受信模板声明路径取交集，避免仅用于状态判定的 TaskSpec 运行时字段被误判为模板展示需求；该参数不属于
公开生成接口，普通用户请求不得使用。

模板 ID 直接表达 UI 形态，不再声明 `Variant`、`allowedParentComponents` 或 `limits`。模板头只定义外部
`props`；`?` 表示可选，支持 `string`、`asset`、`number`、`integer` 和 `boolean`：

Provider `.cardtpl` 中的组件统一采用 Tersel Option 3，只写内联样式，不写 DesignToken。模板是受信资源，
不需要使用 DesignToken 缩短模型 Prompt；需要随 Theme 变化的颜色在内联样式值中使用受限
`$theme('<path>')` 引用。业务模板使用主辅内容色、进度色和 Action 色路径；布局模板还可使用
`supportContentStyle.backgroundColor` 与 `supportContentStyle.borderRadius`。允许路径统一由
`themes/base/theme-base.json` 声明，最终产物不得残留 `$theme`。

```text
#Template WeatherSummaryHero@1(props: { title: string, icon?: asset })
data = {
  temperature: $path("/current/temperatureText"),
  condition: $path("/current/condition"),
  airQuality: $optionalPath("/current/airQuality")
}

Column({"width": "matchParent", "itemMargin": 4},
  Text(`${props.title}`, {
    "fontSize": 20,
    "fontWeight": 700,
    "fontColor": $theme('primaryColor')
  }),
  Text(`${data.temperature}`, {
    "fontSize": 14,
    "fontWeight": 400,
    "fontColor": $theme('primaryColor')
  }),
  #if data.airQuality
    Text(`${data.condition}｜${data.airQuality}`, {
      "fontSize": 12,
      "fontWeight": 500,
      "fontColor": $theme('supportContentColor')
    })
  #else
    Text(`${data.condition}`, {
      "fontSize": 12,
      "fontWeight": 500,
      "fontColor": $theme('supportContentColor')
    })
  #endif
)
#End
```

声明 `...children` 的模板有两种互斥放置方式：可变数量容器使用 `children` 展开；固定槽位布局使用
`children[0]`、`children[1]` 等索引。索引必须为从 `0` 开始的连续整数字面量，每个索引只出现一次，
调用时 child 数量必须和槽位数一致。布局模板应直接写出需要保留到最终 A2UI 的容器、尺寸和间距；
不得只放一个同名内部布局组件，再依赖编译器硬编码重建骨架。

- `$path` 声明模板展开必需的数据，必须按视觉层级进入 `primaryData` 或 `secondaryData`；两组数据都必须
  在 TaskSpec 中存在，只有 `optionalData` 可以缺省。
- `$optionalPath` 声明可选数据，引用必须位于 `#if data.xxx` / `#elseif data.xxx` 的存在分支，
  或由 `#Expr` 对该字段先做编译期选择，并进入 `optionalData`。
- 组件结构的编译期选择使用独占行指令 `#if data.xxx` / `#if props.xxx`、零个或多个 `#elseif`、
  可选的 `#else` 和 `#endif`；`#end` 是条件结束指令的等价别名，模板结束标记仍为大小写敏感的 `#End`。
  条件判断的是本轮 binding 或参数是否可用，不读取运行时值；Prop 已提供且不为 `None` 时
  视为存在，因此 `false`、`0` 和空字符串仍属于存在分支。所有指令在 Provider Template 编译阶段删除，
  不进入 Tersel 或最终 A2UI。
- 两个可选数据字段必须同时存在时，可写 `#if data.first && data.second`。仅当两个字段都存在时展开
  存在分支；任一字段缺失时进入 `#else`。`&&` 只允许连接两个直接的 `data.xxx`，表示编译期存在性
  “与”，不表示运行时逻辑表达式。存在分支可以安全引用这两个字段，缺失分支不得引用它们。
- `#elseif` 支持与 `#if` 相同的三种条件：`data.xxx`、`props.xxx`、`data.first && data.second`。
  从上到下只展开首个命中分支；即使该分支为空，也不继续匹配。没有命中时使用 `#else`，未声明
  `#else` 时不生成内容。每个条件块最多一个 `#else`，其后不能再声明 `#elseif`；嵌套块独立匹配和闭合。
  所有分支仍需通过绑定、参数、动作等校验，后续分支不能借用先前分支的可选数据存在性保证。
- Provider 全局路径中已经存在的值必须使用 `data.xxx`，由服务端根据 `dataDomain + 相对路径`
  绑定为端侧表达式，不得在 `props` 中重复传递。没有对应全局路径的受控派生展示值，以及素材、
  排版等模板参数，
  可以由第二层通过 `props.xxx` 传入，但仍须满足本轮可信文本、数值和素材白名单。
- 每个 `asset` prop 必须在 Provider 的第二层规则中描述业务语义和省略条件。描述不得枚举或假定固定
  素材全集；第二层只从本轮 TaskSpec 实际下发的素材候选中按 description 匹配，没有合适候选时省略
  可选参数，或选择不依赖该素材的模板。
- 反引号 `${...}` 可混合 `props`、`data` 和静态分隔符；包含 `data` 时云侧保留为 A2UI 表达式且不投影
  样例值，只含 `props` 与静态文本时在可信展开阶段直接拼成确定字符串。
- 仅需按路径或 Prop 是否可用选择一个值时，使用显式的编译期语法，例如
  `#Expr(data.city ? data.city : (data.district ? data.district : (props.location ? props.location : "当前城市")))`。
  条件只允许单个
  `data.xxx` 或 `props.xxx`；分支只允许 `data.xxx`、`props.xxx`、字面量或继续加括号的三元表达式。
  编译器按本轮已解析数据绑定和二层 Props 的可用性选择分支并删除三元结构：选中 `data.xxx` 时保留该字段的
  直接 A2UI 数据绑定，选中 Prop 或字面量时写入对应确定值；不得读取 `sampleValue` 固化展示内容，也不会
  生成 A2UI `Expr`。可选数据或 Prop 只允许在自身条件的真分支中引用；未使用 `#Expr` 包裹的普通三元
  表达式不再接受。
- 需要算术、比较、逻辑、按运行时值计算的三元条件或 `size()` 时直接使用 `Expr(...)`，无需外层引号，
  例如 `Expr(data.score <= 20 ? "#FFF9A01E" : "#FF64BB5C")`。`Expr` 至少引用一个 `data` binding，
  不接受 `props`、对象字面量、裸 identifier、未知函数或任意可执行调用；纯静态值继续写字面量。
- 表达式内字符串支持单双引号，双引号转换为 A2UI 要求的单引号；反引号字符串支持 `${data.xxx}`
  插值。例如 ``Expr(data.start == "" ? "" : `${data.start} - ${data.end}`)`` 与
  `Expr(data.start == "" ? "" : data.start + " - " + data.end)` 都表示条件满足后的时间拼接。
  插值占位只接受已声明的 `data.xxx`，不接受额外计算或任意路径；普通引号内的 `data.xxx` 是静态文本。
  编译过程只构建绑定 IR，生成 A2UI 时才映射到实际 path，不读取样例值、不计算条件或拼接结果。
- 整个 Expr 参数用反引号包裹的旧 ``Expr(`...`)`` 保留旧的表达式正文语义以兼容历史模板；
  新模板统一使用无外层引号写法。表达式中的反引号分支则按字符串插值解析。
- `#Expr(...)` 与 `Expr(...)` 语义不同：前者只做编译期值来源选择；后者需要按运行时值计算，
  与普通反引号插值最终都归一化为完整 A2UI
  `{{ ... }}` 属性值，并按本轮 TaskSpec 路径、
  A2UI Form 表达式语法、2048 字符长度和 20 层嵌套限制校验。
- 同一个 `.cardtpl` 可以包含多个 `#Template ... #End`，`provider.json` 中每个模板条目可指向同一文件；
  文件完整性由 CardPlan bundle 清单统一校验，不在模板条目重复维护摘要。

编译期多分支示例（可选字段须事先通过 `$optionalPath` 声明）：

```text
#if data.city
  Text(data.city)
#elseif data.district
  Text(data.district)
#elseif props.location
  Text(props.location)
#else
  Text("当前城市")
#end
```

上述 `#end` 可替换为 `#endif`；指令只影响编译期组件选择，不会输出成 A2UI `If`。

允许接收子组件的布局模板显式声明 `...children`，且正文只能放置一次 `children`：

```text
#Template TwoSupportLayout@1(props: {  }, ...children)
data = {
}

Column({
  "width": "matchParent",
  "height": "matchParent",
  "itemMargin": 8
}, children)
#End
```

第二层调用统一为：

```text
Template("HeroActionLayout@1", {},
  Template("ScheduleOverviewNextEventHero@1", {}),
  Template("PillAction@1", {
    "actionId": "event.viewCalendarEvent",
    "label": "查看日程"
  })
)
```

模板文件不是可执行 Python。解析器只接受受限声明、白名单组件、字面量、受控引用和条件节点；模板展开后
仍执行 Catalog、节点数量、深度、素材、Action、TaskSpec 路径和最终 A2UI 校验。

可信展开后的最终 Tersel 产物包含组件树和 `data = {...}` 两条语句。组件动态值使用
现有 `"${data...}"` 字符串占位语法；需要复合运行时计算时使用 `Expr("...")`，并与 Provider
作者侧的 `Expr(...)` 归一化到相同 A2UI 表达式。作者语法的优化不改变展开后 Tersel 的协议。
`data` 初值由服务端从 TaskSpec 真实路径确定性生成；
`$path` 只属于
Provider 模板作者侧声明，不进入最终 Tersel 语法。最终产物不得包含 `_advancedSelectors` 或
`_templateProjection`。

## 2x2 融球背景

主题回归以当前 `theme.json` 中的明确颜色为基准，不从待测对象生成预期值。进度使用 `progressColor` 和
`progressBackgroundColor` 引用；测试夹具必须提供这两个值，不回退到主辅文本色。业务插画及应用图标按模板
声明保留原色；耳机、心率和睡眠模板明确声明 `fillColor` 的单色图标使用主题辅助内容色。运动记录模板未声明
颜色及原色保护的图标沿用主题主内容色补值，不能统一按原色图处理。活动步数模板保留进度，运动记录 Full
模板当前仅展示文字及图标，不要求补回进度组件。

`TemplateSourceGenerator` 读取已有 `TaskSpec.appVersion`，与 `CONFIG.fusion_ball_min_prd_version` 比较后
裁决模板融球；配置或版本缺失、非法、低于配置版本时关闭。模板模块不重新读取请求版本，也不维护第二份
应用版本。内部模板入口要求调用方显式传入裁决后的 `enable_fusion_ball`。为 `false` 时，所有包含
`fusionBallStyle` 的 Theme 在首层 Prompt 构造前即从请求级 Registry 视图移除，检索、二层组合和编译也不能
再查找或接受这些 Theme。

模板 Search 当前整体不支持 `2x4`，此尺寸在任何首层 Prompt 或模型调用前直接判定模板不适用。Wide
Provider 和 Layout 资源只作后续能力预留，当前不进入生产模板链。

融球背景由模板可信编译器展开为标准 Tersel 组件树，不属于业务 Provider，也不交给二层模型选择。每套融球 Theme
在自身 `themes/<theme-id>/theme.json` 的 `fusionBallStyle` 中保存允许的 `businessIds` 以及大、中、小球真实
`#AARRGGBB` 颜色，不得在代码中维护按场景索引的第二份固定色板。

`fusion-sport-orange` 同时覆盖活动、心率、运动和倒计时业务；倒计时的数据能力 `GetCountdownDays` 与
业务 `CountdownOverview` 必须分别声明在主题的 `supportedCapabilityIds` 和 `fusionBallStyle.businessIds`
中。只声明数据能力仍会被首层主题候选和编译器的业务门禁过滤。回归测试应独立断言倒计时 `Full` 在融球开启时
选中该主题、展开真实背景，并要求画廊用例预期融球；不得仅以同一份主题白名单推导预期结果来证明覆盖有效。

单业务融球包装适用于 `2x2`，且实际选中的业务模板后缀为 `Full`、`Hero` 或 `Compact` 的场景。单业务
可以组合零到两个显式 Action：零 Action 使用 `Full`、单 Action 使用 `Hero`、双 Action 使用 `Compact`；
Action 和 Layout 模板不参与业务数量计算。主题适用能力还必须覆盖该业务模板的数据能力。
双业务仅允许 `HeroTitle + HeroContent + PillAction` 例外：以 `HeroContent` 所属主业务确定全局主题，
该业务及能力必须匹配主题；版本门禁开启时为整卡统一展开一次背景，标题与动作继承该主题。
`WideHero`、`WideFull`、无业务和其它多业务组合均不应用融球包装。

`2x2` 模板中间根节点使用 `Stack("card", ...)`，ID 为 `root`，两个直接子节点依次为标准融球背景树和内容
前景 Stack `template_root`。`template_root` 使用 `padding: 12`，其唯一子节点是防溢出 Stack
`__genui_render_component__template_root`；防溢出 Stack 的唯一子节点是原布局骨架 `root_1`，骨架自身不加
防溢出前缀。模板编译器根据 Theme 中的三个 `#AARRGGBB` 颜色直接展开球体、定位容器和玻璃层。
不满足门禁的卡片继续使用 Theme 原有纯色或线性渐变。融球包装只替换卡片根背景，不改写业务文本、图标或
Action 内容颜色。业务 Provider 必须显式区分主内容与辅助内容，分别使用 `$theme('primaryColor')` 和
`$theme('supportContentColor')`；服务端只给未配置颜色的内容组件补 `primaryColor`，不得猜测主辅语义。
PillAction 模板使用 `$theme('actionStyle.backgroundColor')` 和 `$theme('actionStyle.contentColor')`；Theme 不得
覆盖 Action Template 节点已经显式声明的高度、圆角、字号和字重。

### 完整 A2UI 转换

融球树在模板 CardPlan/Tersel 阶段已经由标准组件组成：`Stack` 承载定位层，三球和玻璃层使用无 children
约束的 `Divider` 视觉叶节点，并在进入 A2UI-Compact 前完成。玻璃层使用 5% 白色和
`backdropBlur: {"radius": 120}`。模板路径在 `template_root` 与 `root_1` 之间注入 ID 为
`__genui_render_component__template_root` 的标准 Stack，以启用端侧内容层防溢出能力；`root_1` 保持普通布局
骨架 ID。A2UI-Compact 不声明 `FusionBall` 组件能力，任何残留均按不支持组件拒绝。

非融球模板和预览数据集同样保留 `root → template_root`，公共校验根始终为 `root`。
`template_root` 是模板内容层的固定标识：公共对比度校验只跳过该节点及其子树，
并列的非模板内容仍按原规则检查；组件、表达式、数据、事件和素材校验不受影响。

## 首层 Search、确定性检索与第二层 LLM 规则

当前默认配置 `firstLayerComponentSelector: "search"`。第一层模型不直接选择业务组件或模板，只输出
`TemplateRetrievalQuery`，顶层字段为 `themeId`、`requiredOutputFieldsByCapability`、`action`：

1. `themeId` 必须来自当前可用 Theme；
2. `requiredOutputFieldsByCapability` 按数据能力列出用户显式要求展示的字段；
3. `action` 输出零到两个不重复、与显式动作对应的 `eventId`，不参与数据覆盖；
4. 模型不得输出组件 ID、模板 ID、布局或最终 props。

成功示例：

```json
{
  "themeId": "fusion-weather-blue",
  "requiredOutputFieldsByCapability": {
    "ViewWeather": ["currentTemperature", "weatherCondition", "hourlyForecast"]
  },
  "action": []
}
```

服务随后由 `retrieve_template_variants()` 做确定性检索，结合能力字段、注册表和模板候选生成
`TemplateRouteSelection`。只有这个内部结果才包含 `componentCandidates` 和
`availableTemplateIds`：

1. `2x2` Search 允许一个业务组件，或恰好两个业务组件加一个 Action；保留模板必须独立完整承载所属业务的显式字段；
2. 显式字段满足后，再检查候选模板自身 `primaryData` 与 `secondaryData` 在 TaskSpec 中全部存在；
3. `candidateOutputFields` 只是候选数据投影，不直接等于强制显示集合；
4. 双业务仅在一侧存在完整 `HeroTitle`、另一侧存在完整 `HeroContent` 时按该顺序进入第二层；其它多业务组合或任一字段无法覆盖时返回模板不匹配；
5. Search 保留字段匹配、模板准入、候选排序和数量上限能力；同一业务可同时返回多个 Hero、Full 或 Compact
   等同形态候选，不能退化为无序枚举；
6. Action 独立于数据业务计数；单业务按零、一个、两个 Action 分别保留 Full、Hero+Full、Compact；
7. Action 不影响数据业务计数；双业务路线必须恰好选择一个 Action，且不得用 Action 覆盖或合并第二个数据业务；
8. Support 和 `TwoSupportLayout` 仅保留给兼容路径，当前 Search 不将其作为多业务回退。

配置 `firstLayerComponentSelector: "llm"` 时，系统可走兼容选择器
`plan_template_route_with_llm()`，由第一层直接产出 Theme、组件候选和 Action；该路径不是当前默认生产路径。

第二层只读取确定性检索选中的业务 Provider `secondLayerRule`，从
`availableTemplateIds` 按尺寸、布局和 Action 数量选择最终 UI 模板及展示 props；根布局也必须从 Layout
Provider 选择模板。第二层不接收 TaskSpec、`dataFacts`、`mustKeep` 或数据样例，不重新判断展示字段，
不得用基础组件补充业务内容。候选筛选后为空或必需 props 无法满足时直接失败。若第一层输出了 `action`，
第二层按最终模板后缀选择完整组合：Hero/WideHero 使用一个
`Template("PillAction@1", props)`，单 Compact 使用两个 PillAction 模板；Full 仅可在
`FullIconActionLayout` 中使用一个 IconAction；WideFull 不生成 Action。旧 LLM 兼容路径仍可将双 Support 的 actionId
各一次写入业务模板内部。PillAction Props
包含 `actionId`、`label` 和可选 `icon`，IconAction Props 包含 `actionId`、`icon`。第二层只决定展示内容，
必选 Action CardTpl 必须在交互组件样式中写入 `onClick: EventAction(props.actionId)`；可选事件的
Support CardTpl 使用 `onClick: EventAction(props?.actionId)`。微服务校验候选配对，将该模板声明绑定为
可信事件并注入主题色。模型不得输出 `call`、`args`、`onClick`。

## 当前迁移范围

天气、日历、手机电量、耳机、健康运动、应用使用时长、倒计时和系统内存当前共有
74 个无 Variant 的业务 UI 模板，其中 12 个是 Support；当前形成 11 个业务组。Layout Provider 另提供
7 个支持 `...children` 的布局模板，Action Provider 提供 2 个动作模板，运行时 Registry 共 83 个模板。
名称包含 `Wide` 的布局只用于 `2x4`，其余布局只用于 `2x2`，两类布局不得混用。
新增或修改资源后执行：

```bash
.venv312/bin/python cloud/services/template_generation/tools/build_cardplan_bundle.py
PYTHONPATH=cloud .venv312/bin/pytest -q cloud/services/template_generation/tests
```
