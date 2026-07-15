# 数据绑定、表达式和模板

## 先判定

- 展示单个 DataModel 值时优先使用完整表达式，例如 `"{{ ${/json/pointer} }}"`。
- 静态文本和变量拼接使用完整表达式，例如 `"{{ ${/meeting/time} + ' 开始' }}"`。
- 最终 Form DSL 也支持 `{"path":"/..."}` PathBinding 和宿主明确注册的 FunctionCall；同一属性值只能三选一。新生成优先用表达式，修复/评审时合法 PathBinding 可以保留。
- `updateDataModel.path`、CardSpec `writeResultTo`、模板 `children.path` 是协议结构 JSON Pointer，不属于值绑定，仍按协议保留。
- 可见表达式引用必须能从 `updateDataModel.value`、CardSpec `writeResultTo + outputSchema` 或模板当前项推导。
- 模板循环只用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`；模板项内字段读取也用表达式。

## DataModel 与表达式

每个 surface 用 `updateDataModel` 更新 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

组件属性读取 DataModel 优先使用完整表达式。优选写法：

```json
{"id":"time","component":"Text","content":"{{ ${/meeting/time} }}"}
{"id":"time_label","component":"Text","content":"{{ ${/meeting/time} + ' 开始' }}"}
```

规则：

- 表达式必须是完整字符串；不要写 `"会议 {{ ${/meeting/time} }}"`，要写 `"{{ '会议 ' + ${/meeting/time} }}"`。
- JSON Pointer 以 `/` 开头，例如 `${/meeting/time}`；不要写点路径 `${/meeting.time}`。
- 当 `updateDataModel.path` 是 `/` 时，`value` 就是 DataModel 根对象；因此表达式 `${/meeting/time}` 对应 `value.meeting.time`。
- 也可使用 `$__dataModel.meeting.time`，但同一卡片内优先统一使用 `${/json/pointer}`，便于和 CardSpec `writeResultTo` 对齐。
- 数字、布尔、对象参数可由表达式返回对应运行时值；简单直取也可用 PathBinding，但同一卡片内尽量统一绑定风格。
- 需要复杂日期、货币、条件文案或多步格式化时，优先在 `updateDataModel.value` 中预计算展示字段，再用表达式读取。

## 表达式规则

```json
{"content":"{{ ${/user/firstName} + ' ' + ${/user/lastName} }}"}
```

规则：

- 一个字符串中只能有一对 `{{ ... }}`；不支持嵌套表达式。
- 表达式内字符串使用单引号。
- 布尔值写 `true` / `false`；内置函数仅使用 `size()`。
- 不使用 `$__widthBreakpoint`、`$__colorMode`。
- `id`、`component`、对象 key、EventHandler `call`、`updateDataModel.path`、CardSpec `writeResultTo`、模板 `children.path` 和整个 `styles` 对象不能写表达式。
- 可以把单个样式值写成表达式，例如 `"fontColor":"{{ ${/theme/titleColor} }}"`；不要把整个 `styles` 对象写成表达式。

## 结构 JSON Pointer

以下位置必须继续使用 JSON Pointer 字符串，不能改成表达式：

- `updateDataModel.path`，例如 `"/"`。
- CardSpec `dataBindings[].writeResultTo`，例如 `"/data/weather"`。
- 模板循环 `children.path`，例如 `"/items"`。

这些结构路径只负责定位数据写入或循环源；组件真正展示字段时仍用完整表达式。

## 模板循环

模板循环是协议特性，不是卡片生成模板。仅在确实需要重复数据时使用。Form 支持默认 `$item/$index`，也支持 `itemVar/indexVar` 自定义变量名；本 Skill 兼容 `${field}` 相对字段写法。

```json
{"id":"items","component":"List","children":{"componentId":"itemTpl","path":"/items"}}
{"id":"itemTpl","component":"Column","children":["itemName","itemValue","itemLine"]}
{"id":"itemName","component":"Text","content":"{{ ${name} }}"}
{"id":"itemValue","component":"Text","content":"{{ ${value} }}"}
{"id":"itemLine","component":"Text","content":"{{ ${name} + '：' + ${value} }}"}
```

对应 DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"items":[{"name":"早餐","value":"08:00"},{"name":"午餐","value":"12:00"}]}}}
```

规则：

- 只有 `Row`、`Column`、`List` 的 `children` 支持 `{ "componentId": "...", "path": "/items" }`，可选 `itemVar/indexVar`，变量名不带 `$` 前缀。
- `children.path` 指向数组，使用以 `/` 开头的 JSON Pointer。
- 模板组件及其子树内，`$item.field` / `$index` 或自定义 `$product.name` / `$i` 读取当前项与索引；`${field}` 也解析到当前数组项字段，`${/rootField}` 解析到根 DataModel。
- 模板项内拼接仍写成完整表达式；简单直取可以使用 PathBinding，但不要把 `{ "path": "field" }` 误写成非 JSON Pointer。
- 同一层模板如果 `itemVar` 与 `indexVar` 同名，按最终协议回退为默认 `$item/$index`。

## EventHandler 数据

事件 `args` 中的 DataModel 参数使用完整表达式或合法 PathBinding；Form EventHandler 不支持 `condition`、`as` 或 `$context`：

```json
"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/items/0/entityId} }}"}}}]
```

模板项内事件参数读取当前项字段：

```json
{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${entityId} }}"}}}
```

规则：

- `call` 优先使用 [`../capability/event-capability/`](../capability/event-capability/) 中声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 中的明确函数声明。
- `args` 必须符合对应 event capability 的 `parameters`，字段名不能改；跳转类能力还必须匹配 `supportedTargets` 中的合法目标组合。
- `clickToIntent.args.params` 只保留运行时参数，不复制 `type`、`description` 等 schema 元数据。
- 每个事件只写 1 个 handler；多个动作先在宿主侧合并成一个已声明函数，否则只保留最关键动作。
- `args` 读取 DataModel 时使用完整表达式或合法 PathBinding；静态固定目标仍直接写静态 JSON 值。
- 来自 data capability 输出的事件参数，必须能从 CardSpec `writeResultTo + outputSchema` 推导。
- 不要使用 `$context.componentId`、`$context.eventData`、`condition` 或 `as`。

## 绑定检查清单

- 动态组件值、样式动态值和事件参数只使用静态值、Expression、PathBinding 或已注册 FunctionCall；无法确认的 FunctionCall 先改为表达式或预计算字段。
- 每个可见表达式引用的数据都能从 DataModel、模板当前项或 `writeResultTo + outputSchema` 推导。
- 每个宿主动作或 event capability 参数来自 DataModel、模板当前项、事件上下文或合法静态目标。
- 每个模板来源路径都指向数组。
- 无法表达时，优先预计算展示字段或简化设计。
