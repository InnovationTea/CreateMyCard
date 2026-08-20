# Provider 模板接入约定

## 两类 Provider

业务 Provider 同时提供数据能力、第一层/第二层规则和 UI 模板。`dataDomain` 明确能力数据写入
TaskSpec 后的绝对根路径；模板内的数据路径始终相对该根路径：

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
    },
    "templates": ["WeatherOverviewHero@1", "WeatherOverviewCompact@1"]
  }],
  "templates": [{
    "templateId": "WeatherOverviewHero@1",
    "description": "天气主视觉摘要。",
    "requiredData": ["/current/temperatureText", "/current/condition"],
    "optionalData": ["/current/airQuality"],
    "entry": "templates/weather-overview.cardtpl",
    "digest": "sha256:<生成时计算>"
  }]
}
```

布局 Provider 不拥有数据能力，因此 capability 条目只登记 `templates`，也不需要分层领域规则：

```json
{
  "providerId": "com.huawei.layout.cli",
  "capabilities": [{
    "templates": ["SingleFocusLayout@1", "HeroSupportLayout@1"]
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
- `props.xxx` 是第二层传入的可信字面量或素材；`data.xxx` 由服务端根据
  `dataDomain + 相对路径` 绑定为端侧表达式。
- 反引号 `${...}` 可混合 `props`、`data` 和静态分隔符；云侧保留为 A2UI 表达式，不投影样例值。
- 同一个 `.cardtpl` 可以包含多个 `#Template ... #End`，`provider.json` 中每个模板条目都指向同一文件
  并校验相同文件摘要。

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

## 两层 LLM 规则

第一层顶层只能输出 `theme`、`component`、`action`：

1. 从 `userQuery` 和 `taskSpecDataFields` 标定用户显式要求显示的字段；
2. 所选一个或多个组件的模板覆盖并集必须承载全部显式字段，任一字段全部或部分不能承载即失败；
3. 显式字段满足后，再检查所选模板自身 `requiredData` 在 TaskSpec 中全部存在；
4. `candidateOutputFields` 只是候选数据投影，不直接等于强制显示集合；
5. `action` 只输出显式动作对应的 `eventId`，不属于组件，也不参与数据覆盖。

成功示例：

```json
{"theme":"family-weather-care-blue","component":["WeatherOverview"],"action":null}
```

失败时仍必须保留最匹配的候选 Theme，以空 `component` 作为唯一失败标志，并清空 Action：

```json
{"theme":"family-weather-care-blue","component":[],"action":null}
```

第二层只读取已选业务 Provider 的 `secondLayerRule`，选择具体 UI 模板和 props；根布局也必须从 Layout
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
