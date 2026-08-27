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

业务模板 ID 必须以 `Compact`、`Hero`、`Full`、`WideHero`、`WideFull` 之一结束。五类后缀分别表示：

- `Compact`：约 `2x1`，用于两个 Compact 拼成 `2x2`，或一个 Compact 加两个 PillAction；
- `Hero`：约 `2x1.7`，用于 `2x2` 的 Hero 加一个 PillAction；
- `Full`：完整 `2x2`，无 Action 时单独使用；
- `WideHero`：约 `4x1.7`，用于 `2x4` 的 WideHero 加一个 PillAction；
- `WideFull`：完整 `4x2`，单独使用。

业务模板不再重复声明 `supportedCardSizes` 和 `requiresLayoutAction`，Registry 直接从后缀推导。业务语义或
状态写在后缀前，例如 `BatteryOverviewChargingWeatherCompact@1`。布局 Provider 不受此后缀约束。

模板 ID 直接表达 UI 形态，不再声明 `Variant`、`allowedParentComponents` 或 `limits`。模板头只定义外部
`props`；`?` 表示可选，支持 `string`、`asset`、`number`、`integer` 和 `boolean`：

Provider `.cardtpl` 中的组件统一采用 Tersel Option 3，只写内联样式，不写 DesignToken。模板是受信资源，
不需要使用 DesignToken 缩短模型 Prompt；需要随 Theme 变化的颜色在内联样式值中使用受限
`$theme('<path>')` 引用。

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
  IfPresent(data.airQuality,
    Text(`${data.condition}｜${data.airQuality}`, {
      "fontSize": 12,
      "fontWeight": 500,
      "fontColor": $theme('supportContentColor')
    })
  )
)
#End
```

声明 `...children` 的模板有两种互斥放置方式：可变数量容器使用 `children` 展开；固定槽位布局使用
`children[0]`、`children[1]` 等索引。索引必须为从 `0` 开始的连续整数字面量，每个索引只出现一次，
调用时 child 数量必须和槽位数一致。布局模板应直接写出需要保留到最终 A2UI 的容器、尺寸和间距；
不得只放一个同名内部布局组件，再依赖编译器硬编码重建骨架。

- `$path` 声明模板展开必需的数据，必须按视觉层级进入 `primaryData` 或 `secondaryData`；两组数据都必须
  在 TaskSpec 中存在，只有 `optionalData` 可以缺省。
- `$optionalPath` 声明可选数据，引用必须位于 `IfPresent(data.xxx, ...)` 或
  `IfAbsent(data.xxx, ...)` 内，并进入 `optionalData`。
- Provider 全局路径中已经存在的值必须使用 `data.xxx`，由服务端根据 `dataDomain + 相对路径`
  绑定为端侧表达式，不得在 `props` 中重复传递。没有对应全局路径的受控派生展示值，以及素材、
  排版等模板参数，
  可以由第二层通过 `props.xxx` 传入，但仍须满足本轮可信文本、数值和素材白名单。
- 每个 `asset` prop 必须在 Provider 的第二层规则中描述业务语义和省略条件。描述不得枚举或假定固定
  素材全集；第二层只从本轮 TaskSpec 实际下发的素材候选中按 description 匹配，没有合适候选时省略
  可选参数，或选择不依赖该素材的模板。
- 反引号 `${...}` 可混合 `props`、`data` 和静态分隔符；云侧保留为 A2UI 表达式，不投影样例值。
- 需要算术、比较、逻辑、三元条件或 `size()` 时使用 ``Expr(`...`)``，例如
  ``Expr(`${data.score} <= 20 ? '#FFF9A01E' : '#FF64BB5C'`)``。`Expr` 至少引用一个 `data` binding，
  不接受 `props`、对象字面量、裸 identifier、未知函数或任意可执行调用；纯静态值继续写字面量。
- `Expr` 与普通反引号插值最终都归一化为完整 A2UI `{{ ... }}` 属性值，并按本轮 TaskSpec 路径、
  A2UI Form 表达式语法、2048 字符长度和 20 层嵌套限制校验。
- 同一个 `.cardtpl` 可以包含多个 `#Template ... #End`，`provider.json` 中每个模板条目可指向同一文件；
  文件完整性由 CardPlan bundle 清单统一校验，不在模板条目重复维护摘要。

允许接收子组件的布局模板显式声明 `...children`，且正文只能放置一次 `children`：

```text
#Template TwoCompactLayout@1(props: {  }, ...children)
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
Template("TwoCompactLayout@1", {},
  Template("DateOverviewCompact@1", {}),
  Template("ScheduleOverviewMeetingCompact@1", {})
)
```

模板文件不是可执行 Python。解析器只接受受限声明、白名单组件、字面量、受控引用和条件节点；模板展开后
仍执行 Catalog、节点数量、深度、素材、Action、TaskSpec 路径和最终 A2UI 校验。

可信展开后的最终 Tersel 产物包含组件树和 `data = {...}` 两条语句。组件动态值使用
现有 `"${data...}"` 字符串占位语法；需要复合运行时计算时使用 `Expr("...")`，并与 Provider
作者侧的 ``Expr(`...`)`` 归一化到相同 A2UI 表达式。`data` 初值由服务端从 TaskSpec 真实路径确定性生成；
`$path` 只属于
Provider 模板作者侧声明，不进入最终 Tersel 语法。最终产物不得包含 `_advancedSelectors` 或
`_templateProjection`。

## 2x2 融球背景

模板生产入口要求调用方显式传入 `enable_fusion_ball`。为 `false` 时，所有包含 `fusionBallStyle` 的 Theme
在首层 Prompt 构造前即从请求级 Registry 视图移除，检索、二层组合和编译也不能再查找或接受这些 Theme。

融球背景是模板可信展开后插入的微服务云侧组件，不属于业务 Provider，也不交给二层模型选择。每套融球 Theme
在自身 `themes/<theme-id>/theme.json` 的 `fusionBallStyle` 中保存允许的 `businessIds` 以及大、中、小球真实
`#AARRGGBB` 颜色，不得在代码中维护按场景索引的第二份固定色板。

融球包装仅适用于 `2x2`、单业务，且实际选中的业务模板后缀为 `Full` 或 `Hero` 的场景。主题适用能力还必须
覆盖该业务模板的数据能力。`Compact`、`WideHero`、`WideFull`、无业务和多业务组合均不应用融球包装。

`2x2` 模板中间根节点使用 `Stack("card", ...)`，子节点顺序固定为“`FusionBall`、原卡片内容”；原卡片内容
移除 `backgroundColor`、`linearGradient` 和背景图片字段后作为前景层。模板内部不再维护或展开球体、定位
容器和玻璃层。`FusionBall(largeColor, mediumColor, smallColor)` 只接受三个 `#AARRGGBB` 位置参数。
不满足门禁的卡片继续使用 Theme 原有纯色或线性渐变。融球包装只替换卡片根背景，不改写业务文本、图标或
Action 内容颜色。业务 Provider 必须显式区分主内容与辅助内容，分别使用 `$theme('primaryColor')` 和
`$theme('supportContentColor')`；服务端只给未配置颜色的内容组件补 `primaryColor`，不得猜测主辅语义。
PillAction 模板使用 `$theme('actionStyle.backgroundColor')` 和 `$theme('actionStyle.contentColor')`；Theme 不得
覆盖 Action Template 节点已经显式声明的高度、圆角、字号和字重。

### 完整 A2UI 转换

Tersel 转 A2UI 后，云侧组件使用顶层 `largeColor`、`mediumColor`、`smallColor` 字段；A2UI 回转
A2UI-Compact 时保留为同名 Props。三种源格式都先转换成完整 A2UI，再由确定性入口
`convert_a2ui_with_fusion_ball(a2ui)` 统一展开。A2UI 输入必须是 `v0.9` 的三行完整 JSONL，依次包含
`createSurface`、`updateComponents` 和 `updateDataModel`。颜色只从 `FusionBall` 本身读取，不再额外传 palette。

入口实现位于 `engine/fusion_ball_a2ui_converter.py`，该文件只使用 Python 标准库，不依赖模板引擎、
CardPlan、Tersel 节点或项目配置，可以单文件复制到其他项目直接调用：

```python
from fusion_ball_a2ui_converter import convert_a2ui_with_fusion_ball

converted = convert_a2ui_with_fusion_ball(a2ui)
```

转换保留 surface、DataModel、原业务组件和根组件 ID，把 `FusionBall` 替换为 Form Catalog 标准 `Stack`
组成的三球、定位层和玻璃层；玻璃层使用 5% 白色和 `backdropBlur: {"radius": 120}`，空层显式保留
`children: []`。与 `FusionBall` 相邻的内容组件 ID 增加 `__genui_render_component__` 前缀，父组件引用同步
更新，以启用端侧内容层防溢出能力。转换完成后不得残留 `FusionBall`。转换器拒绝三色非法、父子关系不唯一、
相邻内容缺失和预留 ID 冲突的输入；无 `FusionBall` 或已经展开的标准 A2UI 原样返回。

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

1. Search 最多允许命中两个业务组件；每个保留模板必须独立完整承载所属业务的显式字段；
2. 显式字段满足后，再检查候选模板自身 `primaryData` 与 `secondaryData` 在 TaskSpec 中全部存在；
3. `candidateOutputFields` 只是候选数据投影，不直接等于强制显示集合；
4. 显式请求包含三个及以上数据业务，或任一字段无法在自己的业务组件内覆盖时，在进入第二层前返回模板不匹配；
5. Search 保留字段匹配、模板准入、候选排序和数量上限能力；同一业务可同时返回多个 Hero、多个 Compact
   等同形态候选，不能退化为无序枚举；
6. Action 独立于数据业务计数；Search 不按 Action 数量过滤模板后缀，最终形态由第二层处理。

配置 `firstLayerComponentSelector: "llm"` 时，系统可走兼容选择器
`plan_template_route_with_llm()`，由第一层直接产出 Theme、组件候选和 Action；该路径不是当前默认生产路径。

第二层只读取确定性检索选中的业务 Provider `secondLayerRule`，从
`availableTemplateIds` 按尺寸、布局和 Action 数量选择最终 UI 模板及展示 props；根布局也必须从 Layout
Provider 选择模板。第二层不接收 TaskSpec、`dataFacts`、`mustKeep` 或数据样例，不重新判断展示字段，
不得用基础组件补充业务内容。候选筛选后为空或必需 props 无法满足时直接失败。若第一层输出了 `action`，
第二层按最终模板后缀在布局模板末尾调用 Action Provider：Hero/WideHero 使用一个
`Template("PillAction@1", props)`，单 Compact 使用两个 PillAction 模板；Full、WideFull 和双 Compact
不生成 Action。PillAction Props
包含 `actionId`、`label` 和可选 `icon`，IconAction Props 包含 `actionId`、`icon`。第二层只决定展示内容，
Action CardTpl 必须在交互组件样式中写入 `onClick: EventAction(props.actionId)`；微服务校验候选配对，
将该模板声明绑定为可信事件并注入主题色。模型不得输出 `call`、`args`、`onClick`。

## 当前迁移范围

天气、日历、手机电量、耳机、健康运动、应用使用时长、倒计时和系统内存当前共有
75 个无 Variant 的业务 UI 模板；日期与日程归并后形成 11 个 Provider 业务领域。Layout Provider
另提供 5 个支持 `...children` 的布局模板：名称包含 `Wide` 的布局只用于 `2x4`，其余布局只用于
`2x2`，两类布局不得混用。
新增或修改资源后执行：

```bash
.venv312/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv312/bin/pytest -q cloud/services/template_generation/tests
```
