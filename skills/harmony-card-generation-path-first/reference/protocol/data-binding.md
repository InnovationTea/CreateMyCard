# 数据绑定、路径表达和模板

## 先判定

- 展示单个 DataModel 值时优先用 `{"path":"/json/pointer"}`。
- 静态文本和变量拼接时优先用 `formatString`；它是组件属性绑定值，不是事件函数。
- 本版本不输出表达式 `{{ ... }}`；修复已有 DSL 时也改写为路径绑定、`formatString` 或预计算展示字段。无法等价改写时说明能力边界。
- 可见绑定路径必须能从 `updateDataModel.value`、CardSpec `writeResultTo + outputSchema` 或模板当前项推导。
- 模板循环只用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`。

## DataModel 与原生绑定

每个 surface 用 `updateDataModel` 更新 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

组件属性读取 DataModel 只使用路径表达。优选写法：

```json
{"id":"time","component":"Text","content":{"path":"/meeting/time"}}
{"id":"time_label","component":"Text","content":{"call":"formatString","args":{"value":"${/meeting/time} 开始"}}}
```

规则：

- `path` 是 JSON Pointer，绝对路径以 `/` 开头，例如 `/meeting/time`；不要写点路径 `/meeting.time`。
- 当 `updateDataModel.path` 是 `/` 时，`value` 就是 DataModel 根对象；因此组件路径 `/meeting/time` 对应 `value.meeting.time`。
- 模板循环内可用相对字段路径，例如 `{"path":"name"}`，解析到当前数组项。
- 路径绑定是响应式的；`updateDataModel` 更新该路径后，组件自动刷新，无需重发组件树。
- 输入类组件如 `Checkbox.value` 使用 `{"path":"/..."}` 实现双向绑定。
- 无法用单值或 `formatString` 表达时，优先在 `updateDataModel.value` 中预计算展示字段；仍无法表达时简化设计或说明能力边界。

## formatString 字符串拼接

`formatString` 只用于组件属性值，例如 `Text.content`、`Button.label`。它把静态文本和 DataModel 变量拼成字符串，与 `{"path":"/..."}` 同属优选原生绑定。

```json
{"call":"formatString","args":{"value":"${/meeting/time} 开始"}}
```

规则：

- `args` 只包含 `value`；`${...}` 内只能放 JSON Pointer 或模板项相对路径。
- 绝对路径写 `${/data/weather/current/temperatureText}`；模板循环内可写 `${name}`。
- 一个字符串里可以有多个 `${...}`；字面量 `${` 转义为 `\${`。
- 数字、布尔按字符串输出；null 或缺失路径输出空字符串。
- 不支持内嵌函数、嵌套 `${...}`、`formatNumber`、`formatCurrency`、`formatDate`、`pluralize`。
- 需要条件、运算、货币、日期等格式化时，优先在 `updateDataModel` 中预计算展示字段。
- `formatString` 不是 EventHandler 的 `call`，不能替代点击、跳转或宿主动作能力。

## 路径闭环

- 静态或预计算展示字段直接初始化在 `updateDataModel.value`，UI 用同名绝对路径读取。
- data capability 字段必须先由 CardSpec 选能力，再由 `writeResultTo + outputSchema` 推导 UI 路径；例如 `writeResultTo: "/data/weather"` 且输出 `current.temperatureText`，UI 路径是 `/data/weather/current/temperatureText`。
- 初始化时至少创建运行时根结构和加载态，例如访问 `/data/weather/current/temperatureText` 时，`value` 至少包含 `{"data":{"weather":{"current":{}}},"state":{"loading":true}}`。
- 不要让 UI 访问 CardSpec `arguments`、能力原始响应或未归一化字段；只访问 `updateDataModel` 中存在或可由能力输出推导的路径。

## 模板循环

模板循环是协议特性，不是卡片生成模板。仅在确实需要重复数据时使用。

```json
{"id":"items","component":"List","children":{"componentId":"itemTpl","path":"/items"}}
{"id":"itemTpl","component":"Column","children":["itemName","itemValue"]}
{"id":"itemName","component":"Text","content":{"path":"name"}}
{"id":"itemValue","component":"Text","content":{"path":"value"}}
```

对应 DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"items":[{"name":"早餐","value":"08:00"},{"name":"午餐","value":"12:00"}]}}}
```

规则：

- 只有 `Row`、`Column`、`List` 的 `children` 支持 `{ "componentId": "...", "path": "/items" }`。
- `children.path` 指向数组，使用以 `/` 开头的 JSON Pointer。
- 模板组件及其子树内，相对路径解析到当前项，绝对路径解析到根。
- 拼接仍用 `formatString`，例如 `{"call":"formatString","args":{"value":"${name}：${value}"}}`。
- 不使用 `$item`、`$index`、`itemVar`、`indexVar`。

## EventHandler 数据

事件 `args` 中的 DataModel 参数使用路径绑定；本版本默认不生成 `condition`，需要条件时优先删减事件或把可判断结果预计算到 DataModel：

```json
"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":{"path":"/data/calendar/items/0/entityId"}}}}]
```

规则：

- `call` 优先使用 [`../capability/event-capability/`](../capability/event-capability/) 中声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 中的明确函数声明。
- `args` 必须符合对应 event capability 的 `parameters`，字段名不能改；跳转类能力还必须匹配 `supportedTargets` 中的合法目标组合。
- `clickToIntent.args.params` 只保留运行时参数，不复制 `type`、`description` 等 schema 元数据。
- `args` 读取 DataModel 时优先用 `{"path":"/..."}`；模板循环内事件参数可用当前项相对路径；需要拼接时用 `formatString`。
- 来自 data capability 输出的事件参数，必须能从 CardSpec `writeResultTo + outputSchema` 推导。
- `as` 绑定变量只在当前事件行为链内有效；没有已声明返回值时不要为了串联动作而虚构 `as`。
- 不为了条件事件虚构 `$context` 表达式；无法用静态目标或路径参数表达时删除点击行为。

## 绑定检查清单

- 没有 `{{ ... }}` 表达式残留。
- 每个可见路径引用的数据都能从 DataModel、模板当前项或 `writeResultTo + outputSchema` 推导。
- 每个宿主动作或 event capability 参数来自 DataModel、模板当前项或合法静态目标。
- 每个模板来源路径都指向数组。
- 无法路径表达时，优先预计算展示字段或简化设计。
