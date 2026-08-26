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
- `Full`：完整 `2x2`，单独使用或加一个 IconAction；
- `WideHero`：约 `4x1.7`，用于 `2x4` 的 WideHero 加一个 PillAction；
- `WideFull`：完整 `4x2`，单独使用。

业务模板不再重复声明 `supportedCardSizes` 和 `requiresLayoutAction`，Registry 直接从后缀推导。业务语义或
状态写在后缀前，例如 `BatteryOverviewChargingCompact@1`。布局 Provider 不受此后缀约束。

模板 ID 直接表达 UI 形态，不再声明 `Variant`、`allowedParentComponents` 或 `limits`。模板头只定义外部
`props`；`?` 表示可选，支持 `string`、`asset`、`number`、`integer` 和 `boolean`：

```text
#Template WeatherSummaryHero@1(props: { title: string, icon?: asset })
data = {
  temperature: $path("/current/temperatureText"),
  condition: $path("/current/condition"),
  airQuality: $optionalPath("/current/airQuality")
}

Column("compact",
  Text(`${props.title}`, "title"),
  Text(`${data.temperature}`, "body"),
  IfPresent(data.airQuality,
    Text(`${data.condition}｜${data.airQuality}`, "subtitle")
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
#Template HeroSupportLayout@1(props: {  }, ...children)
data = {
}

HeroSupportLayout(children)
#End
```

第二层调用统一为：

```text
Template("HeroSupportLayout@1", {},
  Template("WeatherOverviewFull@1", {}),
  Template("BatteryOverviewNormalWeatherCompact@1", {})
)
```

模板文件不是可执行 Python。解析器只接受受限声明、白名单组件、字面量、受控引用和条件节点；模板展开后
仍执行 Catalog、节点数量、深度、素材、Action、TaskSpec 路径和最终 A2UI 校验。

可信展开后的最终 TerseDSL-Nested-2 产物包含组件树和 `data = {...}` 两条语句。组件动态值使用
现有 `"${data...}"` 字符串占位语法；需要复合运行时计算时使用 `Expr("...")`，并与 Provider
作者侧的 ``Expr(`...`)`` 归一化到相同 A2UI 表达式。`data` 初值由服务端从 TaskSpec 真实路径确定性生成；
`$path` 只属于
Provider 模板作者侧声明，不进入最终 Nested-2 语法。最终产物不得包含 `_advancedSelectors` 或
`_templateProjection`。

## 2x2 融球背景

融球背景是模板可信展开后的微服务装饰模板，不属于业务 Provider，也不交给两层模型选择。它只对天气、
运动健康和睡眠三类高饱和场景生效，并根据已选 Theme 使用固定色板：

- 天气：大、中、小球依次为 `#003399`、`#0089BF`、`#4174D9`；
- 运动健康：大、中、小球依次为 `#B33C24`、`#FF8833`、`#F7E6C3`；
- 睡眠：大、中、小球依次为 `#43388C`、`#5761D9`、`#B398D9`。

Theme 是否命中场景由 `theme-profiles.json` 的内部 `fusionBallScene` 配置声明；该字段不进入 A2UI 协议或
模型输出。其它 Theme 不应用融球背景，也不从 Theme 的原颜色动态派生融球色板。

`2x2` 最终根节点使用 `Stack("card", ...)`，子节点顺序固定为“融球背景、原卡片内容”；原卡片内容移除
`backgroundColor`、`linearGradient` 和背景图片字段后作为前景层。Form Catalog 不支持 ArkUI 的
`position`，因此模板使用嵌套 `Stack` 的尺寸与对齐复现三球位置；玻璃层使用 5% 白色覆盖和
`backdropBlur: {"radius": 120}`。最外层 `Stack("card", ...)` 不设置 `backgroundColor`，融球背景容器也不
铺设额外底色，背景由三个球体组合提供。球体和覆盖层使用 A2UI 允许 `children: []` 的空 `Stack`，不添加占位文本。
`2x4` 不应用该装饰模板；其它场景的 `2x2` 与全部 `2x4` 都继续使用 Theme 原有纯色或线性渐变。
融球内容层中非 PillAction 的 `Text` 统一使用 `fontColor: "#CCFFFFFF"`，即 80% 白色。
天气图标保留原始多色素材和原有 `fillColor`；运动健康与睡眠场景的可染色语义图标继续使用白色前景。
PillAction 的背景色、图标和文本均保留自身 Theme 原色，不应用融球内容前景色规则。

### 完整 A2UI 转换

模板模块同时提供确定性的完整 A2UI 转换入口
`convert_a2ui_with_fusion_ball(a2ui, scene)`。A2UI 输入必须是 `v0.9` 的三行完整 JSONL，依次包含
`createSurface`、`updateComponents` 和 `updateDataModel`；`scene` 只接受 `weather`、`health-sport` 或
`sleep`。转换只接受根组件为 `Stack` 且根样式包含纯色或线性渐变背景的卡片；融球颜色由场景固定色板
决定，不读取原背景色或渐变色。背景图片不参与转换。

入口实现位于 `engine/fusion_ball_a2ui_converter.py`，该文件只使用 Python 标准库，不依赖模板引擎、
CardPlan、Terse 节点或项目配置，可以单文件复制到其他项目直接调用：

```python
from fusion_ball_a2ui_converter import convert_a2ui_with_fusion_ball

converted = convert_a2ui_with_fusion_ball(a2ui, "weather")
```

转换保留 surface、DataModel、原业务组件和根组件 ID。原根节点改为无背景的外层 `Stack`，其第一个
子节点是固定融球结构，第二个子节点是改名为 `cardContent`、移除纯色和线性渐变后的原根组件。
`cardContent` 不携带端侧内容防溢出前缀，融球产物不启用内容层防溢出能力，也不扩展 A2UI 协议。
转换器拒绝保留 ID 与融球固定 ID 冲突的输入，对已经完整转换的输入原样返回；旧版
`__genui_render_component__cardContent` 融球产物再次转换时只移除内容 ID 标记。

## 两层 LLM 规则

第一层顶层只能输出 `theme`、`componentCandidates`、`action`：

1. 从 `userQuery` 和 `taskSpecDataFields` 标定用户显式要求显示的字段；
2. Search 只允许选择一个业务组件；该组件下一个或多个模板的覆盖并集必须承载全部显式字段，任一字段全部
   或部分不能承载即失败；
3. 每个所选组件输出 `componentId` 与非空 `availableTemplateIds`，模板 ID 必须来自该组件；
4. 显式字段满足后，再检查候选模板自身 `primaryData` 与 `secondaryData` 在 TaskSpec 中全部存在；
5. `candidateOutputFields` 只是候选数据投影，不直接等于强制显示集合；
6. `action` 输出零到两个不重复、显式动作对应的 `eventId`，不属于组件，也不参与数据覆盖。

显式请求包含多个数据能力，或必须联合多个业务组件才能覆盖字段时，Search 直接返回模板不匹配；单业务加
Action 仍属于支持范围。

成功示例：

```json
{
  "theme": "family-weather-care-blue",
  "componentCandidates": [
    {
      "componentId": "WeatherOverview",
      "availableTemplateIds": ["WeatherOverviewFull@1", "WeatherOverviewCompact@1"]
    }
  ],
  "action": []
}
```

失败时仍必须保留最匹配的候选 Theme，以空 `componentCandidates` 作为唯一失败标志，并清空 Action：

```json
{"theme":"family-weather-care-blue","componentCandidates":[],"action":[]}
```

第二层只读取已选业务 Provider 的 `secondLayerRule`，从首层 `availableTemplateIds` 选择最终 UI 模板和
props；根布局也必须从 Layout
Provider 选择模板。若第一层输出了 `action`，第二层按最终模板后缀在布局模板末尾调用 Action Provider：
Hero/WideHero 使用一个 `Template("PillAction@1", props)`，单 Compact 使用两个 PillAction 模板，Full
最多使用一个 `Template("IconAction@1", props)`；WideFull 和双 Compact 不生成 Action。PillAction Props
包含 `actionId`、`label` 和可选 `icon`，IconAction Props 包含 `actionId`、`icon`。第二层只决定展示内容，
微服务校验候选配对并注入主题色和可信事件，模型不得输出 `call`、`args`、`onClick`。

## 当前迁移范围

天气、日历、手机电量、耳机、健康运动、应用使用时长、倒计时和系统内存的 12 个旧模板前缀已拆成
82 个无 Variant 的业务 UI 模板；日期与日程归并后形成 11 个 Provider 业务领域。Layout Provider
另提供 10 个支持 `...children` 的布局模板。
新增或修改资源后执行：

```bash
.venv312/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv312/bin/pytest -q cloud/services/template_generation/tests
```
