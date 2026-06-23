# 数据绑定、表达式和模板

## DataModel

每个 surface 都有一个由 `updateDataModel` 更新的 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

Form 组件属性默认用表达式读取 DataModel：

```json
{"id":"time","component":"Text","content":"{{ $__dataModel.meeting.time }}"}
```

## JSON Pointer

`updateDataModel.path` 和模板 `children.path` 使用 JSON Pointer：

- `/meeting/title`
- `/weather/temperatureLabel`
- `/action/targetId`

不要使用 `/meeting.title` 这样的点路径作为 JSON Pointer。

## 表达式中的路径

表达式中访问 DataModel 使用点路径：

```json
{"content":"{{ $__dataModel.user.profile.name }}"}
```

也可使用 `${/json/pointer}` 语法：

```json
{"content":"{{ ${/user/profile/name} + ' 您好' }}"}
```

一句话卡片生成中，优先在 `updateDataModel` 中放入展示字符串，避免复杂表达式。

## 表达式完整性

表达式必须是完整字符串：

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

## 禁止使用表达式的位置

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

```json
{"id":"items","component":"List","children":{"componentId":"itemTpl","path":"/items","itemVar":"item","indexVar":"index"}}
{"id":"itemTpl","component":"Row","children":["itemName","itemValue"]}
{"id":"itemName","component":"Text","content":"{{ $item.name }}"}
{"id":"itemValue","component":"Text","content":"{{ $item.value }}"}
```

规则：

- 只有 `Row`、`Column`、`List` 的 `children` 支持 `{ componentId, path }`。
- `path` 指向数组，外层使用 JSON Pointer。
- 默认变量是 `$item` 和 `$index`。
- `itemVar` / `indexVar` 的值不带 `$`，引用时加 `$`。
- 自定义变量名必须匹配 `^[a-zA-Z_][a-zA-Z0-9_]*$`。
- 嵌套模板中，为外层设置自定义 `itemVar` 以避免被内层 `$item` 遮蔽。

## EventHandler 数据

事件参数可用表达式读取 DataModel、事件上下文或行为链变量：

```json
"onClick":[
  {
    "call":"validateForm",
    "args":{"data":"{{ $__dataModel.form }}"},
    "as":"valid"
  },
  {
    "call":"submitForm",
    "condition":"{{ $valid == true }}",
    "args":{"x":"{{ $context.eventData.x }}"}
  }
]
```

规则：

- `call` 优先来自 [`event-capability/click-event.md`](event-capability/click-event.md) 中的 `functionCall`，例如 `clickToCallPhone`、`clickToDeeplink`、`clickToIntent`。
- 如果使用 `clickToIntent` 打开日程详情，`args.intentName` 固定为 `ViewCalendarEvent`，`args.params.entityId` 绑定日历数据的 `entityId`，模板内通常写作 `"{{ $event.entityId }}"`。
- 如果使用 `clickToDeeplink`，`args.bundleName`、`args.abilityName`、`args.uri` 必须来自 event-capability 的同一个 `supportedTargets` 项。
- 只有用户或宿主明确提供其它自定义函数时，才允许作为宿主假设使用。
- `as` 绑定变量只在当前事件行为链内有效。
- `$context.componentId` 和 `$context.eventData` 只在事件处理表达式中可用。

## 绑定检查清单

- 每个可见表达式引用的数据都在 DataModel 中有对应字段。
- 每个宿主动作参数都从 DataModel 或事件上下文取得。
- 每个模板来源路径都指向数组。
- 组件属性中不要默认使用 `{ "path": "..." }` 绑定对象；除非宿主明确确认该属性 schema 支持。
