# 数据绑定、原生绑定、表达式和模板

## 先判定

- 展示单个 DataModel 值时优先用 `{"path":"/json/pointer"}`。
- 静态文本和变量拼接时优先用 `formatString`。
- 表达式 `{{ ... }}` 只在原生绑定无法表达时兜底；事件 `condition` 和 `$context` 表达式除外。
- 可见绑定路径必须能从 `updateDataModel.value`、CardSpec `writeResultTo + outputSchema` 或模板当前项推导。
- 模板循环只用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`。

## DataModel

每个 surface 都有一个由 `updateDataModel` 更新的 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

## 两种读取与绑定方式

组件属性读取 DataModel 有两种方式，优先级不同：

- **优选：A2UI 原生 data binding。** 用 `{"path":"/json/pointer"}` 直接绑定单个值；需要把静态文本和变量拼成字符串时，用 `formatString` 函数调用绑定。见 [`function.md`](function.md)。
- **兜底：表达式 `{{ ... }}`。** 仅在原生绑定无法表达（例如同一字符串内需要条件或多值运算），或属性 schema 不支持对象绑定时使用。

优选写法：

```json
{"id":"time","component":"Text","content":{"path":"/meeting/time"}}
```

等价的兜底表达式写法（不优选）：

```json
{"id":"time","component":"Text","content":"{{ $__dataModel.meeting.time }}"}
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

## 表达式（兜底）

这里的“兜底”特指用表达式读取 DataModel 作为组件展示值：优先用上面的原生 `{"path":"/..."}` 绑定或 `formatString` 拼接，只有原生无法表达（同一字符串内的条件或多值运算）时才用表达式。

注意：下文“EventHandler 数据”的 `condition`/`$context` 表达式是事件场景的固有写法，没有原生 `{path}` 等价物，不属于这里说的可被原生绑定替代的兜底。事件 `args` 中的 DataModel 参数优先使用原生 `{"path":"/..."}`。

### 表达式中的路径

表达式中访问 DataModel 使用点路径：

```json
{"content":"{{ $__dataModel.user.profile.name }}"}
```

也可使用 `${/json/pointer}` 语法：

```json
{"content":"{{ ${/user/profile/name} + ' 您好' }}"}
```

一句话卡片生成中，优先在 `updateDataModel` 中放入展示字符串，避免复杂表达式。

### 表达式完整性

使用兜底表达式时，表达式必须是完整字符串：

```json
{"content":"{{ $__dataModel.firstName + ' ' + $__dataModel.lastName }}"}
```

不要写：

```json
{"content":"{{ $__dataModel.firstName }} {{ $__dataModel.lastName }}"}
```

规则：

- 表达式内使用单引号字符串。
- 一个字符串中只能有一对 `{{ ... }}`。
- 不支持嵌套表达式。
- 布尔值必须是 `true` / `false`。
- 内置函数仅使用 `size()`。
- 不使用 `$__widthBreakpoint` 或 `$__colorMode`。

### 禁止使用表达式的位置

不要在以下位置使用表达式：

- `id`
- `component`
- 对象 key
- EventHandler `call`
- EventHandler `as`
- `updateDataModel.path`
- 模板 `children.path`
- 整个 `styles` 对象值，例如 `"styles": "{{ ... }}"`

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

事件 `args` 中的 DataModel 参数优先用原生绑定读取；`condition`、事件上下文或行为链变量继续用表达式：

```json
"onClick":[
  {
    "call":"clickToIntent",
    "condition":"{{ $context.eventData.x >= 0 }}",
    "args":{
      "intentName":"ViewCalendarEvent",
      "params":{
        "entityId":{"path":"/data/calendar/items/0/entityId"}
      }
    }
  }
]
```

规则：

- `call` 优先使用 [`../capability/event-capability/`](../capability/event-capability/) 中已声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 中的明确函数声明。
- `args` 必须符合对应 event capability 的 `parameters`。跳转类能力还必须匹配 `supportedTargets` 中的合法目标组合。
- `args` 中读取 DataModel 的值时，优先使用 `{"path":"/..."}`；需要拼接字符串时使用 `formatString`。
- 模板循环内的事件参数可使用当前项相对路径，例如 `{"path":"entityId"}`；非模板区域使用绝对 JSON Pointer。
- 来自 data capability 输出的事件参数，必须能从 CardSpec 的 `writeResultTo` 和该能力 `outputSchema` 推导。
- `as` 绑定变量只在当前事件行为链内有效；没有已声明返回值时不要为了串联动作而虚构 `as`。
- `$context.componentId` 和 `$context.eventData` 只在事件处理表达式中可用。

## 绑定检查清单

- 每个可见的原生绑定或表达式引用的数据都在 DataModel 中有对应字段。
- 每个宿主动作或 event capability 参数都从 DataModel、事件上下文或合法静态目标取得。
- 每个来自 data capability 的事件参数路径都能由 `writeResultTo + outputSchema` 推导。
- 每个模板来源路径都指向数组。
- 组件属性默认优先使用 `{"path":"/..."}` 原生绑定或 `formatString` 拼接；仅当属性 schema 不支持对象绑定时才退回表达式。
