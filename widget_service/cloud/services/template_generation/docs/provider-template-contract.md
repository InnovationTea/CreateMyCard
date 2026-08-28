# Provider 模板接入约定

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
    "templateId": "WeatherOverviewHero@1",
    "businessId": "WeatherOverview",
    "capabilityId": "ViewWeather",
    "description": "天气主视觉摘要。",
    "requiredData": ["/current/temperatureText", "/current/condition"],
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

- `$path` 声明模板展开必需的数据，必须进入 `requiredData`。
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
  Template("WeatherOverviewHero@1", {}),
  Template("BatteryOverviewNormalWeather@1", {})
)
```

模板文件不是可执行 Python。解析器只接受受限声明、白名单组件、字面量、受控引用和条件节点；模板展开后
仍执行 Catalog、节点数量、深度、素材、Action、TaskSpec 路径和最终 A2UI 校验。

可信展开后的最终 TerseDSL-Nested-2 产物包含组件树和 `data = {...}` 两条语句。组件动态值使用
现有 `"${data...}"` 字符串占位语法，`data` 初值由服务端从 TaskSpec 真实路径确定性生成；
`$path` 只属于
Provider 模板作者侧声明，不进入最终 Nested-2 语法。最终产物不得包含 `_advancedSelectors` 或
`_templateProjection`。

## 两层 LLM 规则

第一层顶层只能输出 `theme`、`componentCandidates`、`action`：

1. 从 `userQuery` 和 `taskSpecDataFields` 标定用户显式要求显示的字段；
2. Search 只允许选择一个业务组件；该组件下一个或多个模板的覆盖并集必须承载全部显式字段，任一字段全部
   或部分不能承载即失败；
3. 每个所选组件输出 `componentId` 与非空 `availableTemplateIds`，模板 ID 必须来自该组件；
4. 显式字段满足后，再检查候选模板自身 `requiredData` 在 TaskSpec 中全部存在；
5. `candidateOutputFields` 只是候选数据投影，不直接等于强制显示集合；
6. `action` 只输出显式动作对应的 `eventId`，不属于组件，也不参与数据覆盖。

显式请求包含多个数据能力，或必须联合多个业务组件才能覆盖字段时，Search 直接返回模板不匹配；单业务加
Action 仍属于支持范围。

成功示例：

```json
{
  "theme": "family-weather-care-blue",
  "componentCandidates": [
    {
      "componentId": "WeatherOverview",
      "availableTemplateIds": ["WeatherOverviewHero@1", "WeatherOverviewCompact@1"]
    }
  ],
  "action": null
}
```

失败时仍必须保留最匹配的候选 Theme，以空 `componentCandidates` 作为唯一失败标志，并清空 Action：

```json
{"theme":"family-weather-care-blue","componentCandidates":[],"action":null}
```

第二层只读取已选业务 Provider 的 `secondLayerRule`，从首层 `availableTemplateIds` 选择最终 UI 模板和
props；根布局也必须从 Layout
Provider 选择模板。若第一层输出了 `action`，第二层只可在布局模板末尾生成唯一
`PillAction({"actionId":"event.id"})`。

## 当前迁移范围

天气、日历、手机电量、耳机、健康运动、应用使用时长、倒计时和系统内存的 12 个旧模板族已拆成
73 个无 Variant 的业务 UI 模板；Layout Provider 另提供 10 个支持 `...children` 的布局模板。
新增或修改资源后执行：

```bash
.venv312/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv312/bin/pytest -q cloud/services/template_generation/tests
```
