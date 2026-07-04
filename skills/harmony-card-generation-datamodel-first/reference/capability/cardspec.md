# CardSpec 数据能力契约

CardSpec 与 DSL 一起描述同一张卡片。最终响应只有两个代码块：`genui` DSL JSONL + `cardspec` JSON。DSL 负责可渲染 Form 组件；CardSpec 只负责推荐尺寸、端侧数据能力和持久化契约。事件能力不属于 CardSpec，点击、拨号、打开应用或详情页只写 DSL `onClick`。

Agent 负责选择已声明能力、生成参数、设计 DataModel 初始结构，并让 DSL 与 CardSpec 对齐。端侧负责执行能力、处理权限、归一化结果、持久化配置，并在运行时发送 `updateDataModel`。

## 先决策

- 每张卡都输出 `genui` 和 `cardspec`；静态卡片也输出 CardSpec。
- 静态卡片只写 `suggestSize`，不要虚构 `dataBindings`。
- 动态卡片先选择已声明 data capability，再按其 `inputSchema` 填 `arguments`；不要沿用旧示例参数或自行改名。
- `writeResultTo` 使用 `/data/...` JSON Pointer；UI 路径由 `writeResultTo + outputSchema` 推导。
- `updateDataModel.value` 初始化 UI 会访问的根结构和加载态，不写死用户真实隐私数据。
- DSL 仍按 [`../protocol/protocol.md`](../protocol/protocol.md)、[`../protocol/component-catalog.md`](../protocol/component-catalog.md) 和 [`../protocol/data-binding.md`](../protocol/data-binding.md) 生成。

## 输出形态

静态卡片：

```json
{"suggestSize":"2x2"}
```

动态卡片：

```json
{"suggestSize":"2x4","dataBindings":[{"capabilityId":"calendar.events.search","arguments":{"timeInterval":[1766448000000,1766534399999]},"writeResultTo":"/data/calendar"}]}
```

## 字段规则

- `suggestSize` 必须与 DSL 尺寸一致，只能是 `"2x2"` 或 `"2x4"`。
- 动态卡片必须包含 `dataBindings`；每个 `dataBindings[]` 表示一次端侧能力调用。
- `capabilityId` 必须来自 [`data-capability/`](data-capability/) 中选定能力 manifest 的 `id`。
- `arguments` 只能使用该能力 `inputSchema.properties` 声明的字段；不要沿用旧示例参数或自行改名。
- `arguments` 是端侧能力入参配置，使用由用户需求或默认策略确定的 JSON 值；不要把 DSL 表达式、`{"path":...}` 或 `formatString` 绑定对象写进 `arguments`，除非能力 `inputSchema` 明确要求这种对象结构。
- `writeResultTo` 必须是 `/data` 下的 JSON Pointer，例如 `/data/weather`；多个 binding 的 `writeResultTo` 不得相同、互为父子或互相覆盖。
- 默认只写 `capabilityId`、`arguments`、`writeResultTo`；只有端侧明确需要时才加入 `bindingId` 或 `capabilityVersion`。

## 能力选择

按场景逐个读取必要能力文档，不要预先加载全部能力：

- 天气：[`data-capability/weather.md`](data-capability/weather.md)
- 日历：[`data-capability/calendar.md`](data-capability/calendar.md)

如果用户请求的动态能力未声明，不要编造能力；改用静态降级方案，或说明需要端侧补充 capability manifest。

## DataModel 映射

端侧执行 `dataBindings` 后，将标准化结果整体写入 `writeResultTo`。UI 访问路径由 `writeResultTo + outputSchema 字段` 推导：

- `writeResultTo = /data/calendar` 且输出有 `items`，列表路径是 `/data/calendar/items`。
- `writeResultTo = /data/status` 且输出有 `current.valueText`，主值路径是 `/data/status/current/valueText`。

初始化 DataModel 只放 UI 会访问的根结构和加载态：

```json
{"data":{"calendar":{"items":[]}},"state":{"loading":true}}
```

组件表达式示例：

```json
{"id":"current_value","component":"Text","content":"{{ ${/data/weather/current/temperatureText} }}"}
{"id":"event_list","component":"Column","children":{"componentId":"event_template","path":"/data/calendar/items"}}
{"id":"event_title","component":"Text","content":"{{ ${title} }}"}
{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${entityId} }}"}}}
```

## 检查清单

- DSL 与 CardSpec 的尺寸选择一致。
- DSL 和 CardSpec 是同一张卡，DataModel 访问路径互相对齐。
- 所有 UI 访问字段都能从 `writeResultTo + outputSchema` 推导。
- 事件参数若来自数据能力输出，也能从同一 DataModel 路径推导；事件能力本身不写入 CardSpec。
- `updateDataModel.value` 初始化了 `/data/...` 根结构和必要 `/state/...` 字段。
- 数组字段使用模板循环，不展开成固定重复组件。
- CardSpec 不包含 DSL catalog、组件规则、事件能力或示例结构的替代定义。
- 不暴露意图框架原始返回结构，不写死用户真实隐私数据。
