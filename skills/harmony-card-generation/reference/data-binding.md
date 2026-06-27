# 数据绑定、原生绑定和模板

## DataModel

每个 surface 都有一个由 `updateDataModel` 更新的 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

## 读取与绑定方式

组件属性读取 DataModel 时，使用原生 data binding：

- 用 `{"path":"/json/pointer"}` 直接绑定单个值。
- 需要把静态文本和变量拼成字符串时，用 `formatString` 函数调用绑定。见 [`function.md`](function.md)。
- 条件文案、复杂格式化或多值运算应预先写入 `updateDataModel` 的展示字段；无法表达时简化设计，不使用表达式。

优选写法：

```json
{"id":"time","component":"Text","content":{"path":"/meeting/time"}}
```

## A2UI 原生 data binding（优选）

组件的动态属性值可以是：

- 字面量：`"content":"会议"`
- 路径绑定（响应式）：`"content":{"path":"/meeting/time"}`
- 字符串拼接：`"content":{"call":"formatString","args":{"value":"${/meeting/time} 开始"}}`（见 [`function.md`](function.md)）

规则：

- `path` 使用 JSON Pointer：绝对路径以 `/` 开头，例如 `/meeting/time`。
- 模板循环内使用相对字段路径，例如 `{"path":"name"}`，由当前数组项作用域解析。
- 路径绑定是响应式的：`updateDataModel` 改变该路径的值后，组件自动刷新，无需重发组件树。
- 输入类组件（如 `Checkbox.value`）使用 `{"path":"/..."}` 实现双向绑定。
- 不要在 `path` 中使用点路径，例如 `/meeting.time`。

## JSON Pointer

`updateDataModel.path` 和模板 `children.path` 使用 JSON Pointer：

- `/meeting/title`
- `/weather/temperatureLabel`
- `/action/targetId`

不要使用 `/meeting.title` 这样的点路径作为 JSON Pointer。

## 表达式（禁用）

本 skill 生成结果禁用 `{{ ... }}` 表达式。不要用表达式读取 DataModel，也不要把表达式作为组件展示值、事件条件或事件上下文读取方式。

替代策略：

- 单值读取：使用 `{"path":"/..."}`。
- 字符串拼接：使用 `formatString`。
- 条件、多值运算、本地化格式化：预先写入 `updateDataModel` 展示字段。
- 事件条件或上下文读取：简化为不需要条件链的点击行为，或要求宿主补充已声明的动作函数。

禁用项：

- 不生成 `{{ ... }}`。
- 不使用 `$__dataModel`、`$context`、`size()`、`$__widthBreakpoint` 或 `$__colorMode`。
- 不在 `id`、`component`、对象 key、EventHandler `call`、EventHandler `as`、`updateDataModel.path`、模板 `children.path` 或任何组件属性中使用表达式。

## 模板循环

模板循环是协议特性，不是卡片生成模板。仅在确实需要重复数据时使用。

容器（`Row`/`Column`/`List`）把 `children` 绑定到一个数组路径，并用 `componentId` 指向模板组件。模板对象只有 `componentId` 和 `path` 两个字段：

```json
{"id":"items","component":"List","children":{"componentId":"itemTpl","path":"/items"}}
{"id":"itemTpl","component":"Column","children":["itemName","itemValue"]}
{"id":"itemName","component":"Text","content":{"path":"name"}}
{"id":"itemValue","component":"Text","content":{"path":"value"}}
```

对应的 DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"items":[{"name":"早餐","value":"08:00"},{"name":"午餐","value":"12:00"}]}}}
```

模板为数组每一项创建一个子作用域，项内取值用原生绑定：

- 相对路径（不以 `/` 开头）解析到当前项：`{"path":"name"}` → `/items/N/name`。
- 绝对路径（以 `/` 开头）仍解析到根：`{"path":"/title"}`。
- 拼接用 `formatString`，路径同样支持相对/绝对：`{"call":"formatString","args":{"value":"${name}：${value}"}}`。

规则：

- 只有 `Row`、`Column`、`List` 的 `children` 支持模板对象 `{ componentId, path }`。
- `path` 指向数组，使用 JSON Pointer（以 `/` 开头）。
- 模板组件及其子树内：相对路径解析到当前项，绝对路径解析到根。
- 不使用 `$item`、`$index`、`itemVar`、`indexVar` 变量机制。

## EventHandler 数据

事件 `args` 中的 DataModel 参数使用原生绑定读取；不要生成 `condition`、`$context` 或行为链变量表达式：

```json
"onClick":[
  {
    "call":"submitForm",
    "args":{"data":{"path":"/form"}}
  }
]
```

规则：

- `call` 优先使用 `reference/event-capability/` 中已声明的 `functionCall`；未声明时只能使用宿主 catalog 已声明的自定义函数名，或明确声明为宿主假设。
- `args` 必须符合对应 event capability 的 `parameters`。跳转类能力还必须匹配 `supportedTargets` 中的合法目标组合。
- `args` 中读取 DataModel 的值时，优先使用 `{"path":"/..."}`；需要拼接字符串时使用 `formatString`。
- 模板循环内的事件参数可使用当前项相对路径，例如 `{"path":"entityId"}`；非模板区域使用绝对 JSON Pointer。
- 来自 data capability 输出的事件参数，必须能从 CardSpec 的 `writeResultTo` 和该能力 `outputSchema` 推导。
- `as` 绑定变量只在当前事件行为链内有效。
- 避免依赖 `as`、`condition` 或事件上下文表达式；需要条件逻辑时让宿主动作函数内部处理，或简化为单步点击。

## 绑定检查清单

- 每个可见的原生绑定引用的数据都在 DataModel 中有对应字段。
- 每个宿主动作或 event capability 参数都从 DataModel、事件上下文或合法静态目标取得。
- 每个来自 data capability 的事件参数路径都能由 `writeResultTo + outputSchema` 推导。
- 每个模板来源路径都指向数组。
- 组件属性只使用 `{"path":"/..."}` 原生绑定、`formatString` 拼接或 `updateDataModel` 预计算展示字段；不使用表达式。
