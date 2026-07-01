# 数据绑定、原生绑定、表达式和模板

## 先判定

- 展示单个 DataModel 值时优先用 `{"path":"/json/pointer"}`。
- 静态文本和变量拼接时优先用 `formatString`，详见 [`function.md`](function.md)。
- 新卡片不要使用表达式 `{{ ... }}`；修复遗留 DSL 时，只有原生绑定无法等价表达且用户要求保留行为，才作为受限例外。事件 `condition` 和 `$context` 表达式除外。
- 可见绑定路径必须能从 `updateDataModel.value`、CardSpec `writeResultTo + outputSchema` 或模板当前项推导。
- 模板循环只用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`。

## DataModel 与原生绑定

每个 surface 用 `updateDataModel` 更新 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

组件属性读取 DataModel 有两种方式：优选原生绑定；表达式只用于遗留受限例外。优选写法：

```json
{"id":"time","component":"Text","content":{"path":"/meeting/time"}}
{"id":"time_label","component":"Text","content":{"call":"formatString","args":{"value":"${/meeting/time} 开始"}}}
```

规则：

- `path` 是 JSON Pointer，绝对路径以 `/` 开头，例如 `/meeting/time`；不要写点路径 `/meeting.time`。
- 模板循环内可用相对字段路径，例如 `{"path":"name"}`，解析到当前数组项。
- 路径绑定是响应式的；`updateDataModel` 更新该路径后，组件自动刷新，无需重发组件树。
- 输入类组件如 `Checkbox.value` 使用 `{"path":"/..."}` 实现双向绑定。
- 无法用单值或 `formatString` 表达时，优先在 `updateDataModel.value` 中预计算展示字段，而不是回退表达式。

## 表达式受限例外

新卡片禁止表达式；优先用 `{path}`、`formatString` 或 `updateDataModel` 预计算展示字段。保留遗留表达式时必须满足：

- 表达式是完整字符串，例如 `{"content":"{{ $__dataModel.firstName + ' ' + $__dataModel.lastName }}"}`。
- 表达式内使用单引号字符串；一个字符串只能有一对 `{{ ... }}`；不支持嵌套表达式。
- 布尔值写 `true` / `false`；内置函数仅使用 `size()`。
- DataModel 可用点路径 `$__dataModel.user.profile.name`，也可用 `${/json/pointer}`。
- 不使用 `$__widthBreakpoint`、`$__colorMode`。

禁止在以下位置使用表达式：`id`、`component`、对象 key、EventHandler `call`、EventHandler `as`、`updateDataModel.path`、模板 `children.path`、整个 `styles` 对象。

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

事件 `args` 中的 DataModel 参数优先用原生绑定；`condition`、事件上下文或行为链变量继续用表达式。事件 `condition` / `$context` 是事件语法，不等同于新卡片展示表达式兜底：

```json
"onClick":[{"call":"clickToIntent","condition":"{{ $context.eventData.x >= 0 }}","args":{"intentName":"ViewCalendarEvent","params":{"entityId":{"path":"/data/calendar/items/0/entityId"}}}}]
```

规则：

- `call` 优先使用 [`../capability/event-capability/`](../capability/event-capability/) 中声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 中的明确函数声明。
- `args` 必须符合对应 event capability 的 `parameters`，字段名不能改；跳转类能力还必须匹配 `supportedTargets` 中的合法目标组合。
- `clickToIntent.args.params` 只保留运行时参数，不复制 `type`、`description` 等 schema 元数据。
- `args` 读取 DataModel 时优先用 `{"path":"/..."}`；模板循环内事件参数可用当前项相对路径；需要拼接时用 `formatString`。
- 来自 data capability 输出的事件参数，必须能从 CardSpec `writeResultTo + outputSchema` 推导。
- `as` 绑定变量只在当前事件行为链内有效；没有已声明返回值时不要为了串联动作而虚构 `as`。
- `$context.componentId` 和 `$context.eventData` 只在事件处理表达式中可用。

## 绑定检查清单

- 新卡片没有表达式；遗留表达式都有用户要求或无法等价改写的原因。
- 每个可见路径或表达式引用的数据都能从 DataModel、模板当前项或 `writeResultTo + outputSchema` 推导。
- 每个宿主动作或 event capability 参数来自 DataModel、事件上下文或合法静态目标。
- 每个模板来源路径都指向数组。
- 无法原生表达时，优先预计算展示字段或简化设计。
