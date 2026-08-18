# Provider 模板接入约定

## Provider 清单

每个 CLI 数据提供方在自己的资源目录中提供 `provider.json`、两份分层规则 MD、数据 Schema 和一个或多个 `.cardtpl`。
能力与模板的关联只保留以下核心信息：

```json
{
  "firstLayerRule": {"path": "layer-docs/first-layer.md"},
  "secondLayerRule": {"path": "layer-docs/second-layer.md"},
  "capabilities": [{
  "capabilityId": "ViewWeather",
  "dataSchema": {
    "path": "capabilities/app-11.7.5.205_rom-6.0/data_capabilities.json",
    "version": "app-11.7.5.205_rom-6.0"
  },
  "templates": ["WeatherOverview@1"]
  }]
}
```

`dataSchema.path` 优先引用上游能力数据；上游没有稳定路径时，允许指向 Provider 目录内的本地 Schema。
模板名使用短业务名加主版本，例如 `WeatherOverview@1`，不再增加 Provider 前缀。

两个规则路径相对 `provider.json` 所在目录解析，只允许非空 UTF-8 `.md` 文件，禁止绝对路径和目录越界：

- `firstLayerRule.path`：只描述高级组件、该组件支持的数据路径和首层选择边界。路径使用
  `{{dataRoot:CapabilityId}}/...`，服务端在本轮 Prompt 中替换成 `writeResultTo` 对应的 TaskSpec 绝对路径。
- `secondLayerRule.path`：只描述高级组件 Variant、参数、素材和 Action 使用规则。只有首层最终选中的
  Provider 文档才进入第二层 Prompt。

Theme 不属于 Provider，在 `theme-profiles.json` 的每个主题条目中用
`firstLayerRule.path` 指向独立 MD。Theme 文档只进入第一层，不提供二层规则。

## 模板语法

模板只允许声明式组件、绑定、受控表达式和 Variant。运行时字符串拼接使用 A2UI 表达式，不在云侧投影为
某一轮样例值：

```text
Text(Expr(`${condition}|${airQuality}`))
```

编译后的标准 A2UI 使用完整表达式，例如：

```text
{{ ${/data/weather/current/condition} + '|' + ${/data/weather/current/airQuality} }}
```

模板文件不是可执行 Python，不允许任意函数、文件访问、网络访问或动态 import。解析器只接受白名单 AST，
并拒绝 `__proto__`、`prototype` 和 `constructor` 等危险键。

由上游字段确定性派生的模板参数必须声明来源，例如：

```text
durationPrimaryValueText: {
  type: "string",
  required: true,
  sourcePaths: ["/appUsage/durationText"]
}
```

`sourcePaths` 只允许指向本能力 `outputSchema` 的叶子字段；素材参数不允许声明。模板覆盖集合等于 Variant
直接绑定路径与其参数来源路径的并集。

## 完整覆盖要求

第一层 LLM 顶层只能输出 `theme`、`component`、`action`，服务端必须再次确认：

- 每个 `candidateDataBinding.capabilityId` 都有可用 Provider 模板。
- 第一层只能根据 `userQuery` 和 TaskSpec 全量字段在内部判断必须显示字段，且这些字段都落在所选组件的
  首层规则支持路径内；不得把 `candidateOutputFields` 整体当成强制展示集合。
- `theme`、`component`、`action` 都来自本轮 Prompt 候选；Action 候选由服务端按组件白名单预过滤并
  标注 `supportedComponent`，Action ID 不参与数据覆盖判断。
- 所选组件至少存在一个能从本轮 TaskSpec/CardSpec 唯一解析必需绑定的 Provider Variant。
- 所选 Variant 的必需绑定能从 TaskSpec 与 CardSpec 唯一解析。
- 模板参数只来自可信事实、批准事件和批准素材。
- 任一字段不满足时，整个模板判断失败，不能用模板只展示一部分后继续。

## 当前 Provider 模板

资源目录当前包含天气、日历、手机电量、耳机、健康运动、应用使用时长、倒计时和系统内存等 Provider，
共 12 个版本化业务模板。新增 Provider 时只修改本模块 `resources/source/providers/` 及对应独立测试。
