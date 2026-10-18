# Compact DSL 数据绑定

本文件把工具3的 DataModel 语义等价序列化为 Compact DSL。业务路径、数据类型和动态更新
行为不变；只把 A2UI 完整表达式与 `updateDataModel` 改为 path 绑定和数据行。

## 两种赋值方式

静态字符串直接写入组件：

```text
["title","Text",{"content":"天气速览"}]
```

动态字符串使用 path 绑定，并在组件行之后初始化：

```text
["temperature","Text",{"content":{"path":"/data/weather/current/temperatureText"}}]
["/data/weather/current/temperatureText","29°C"]
```

- `Text.content` 的语义类型仍是 string；`{"path":"/..."}` 只是协议层取值方式。
- path 必须是以 `/` 开头的 JSON Pointer，禁止点记法和 `{{ ... }}` 表达式。
- `Text.content`、`Image.src`、`Button.label` 以及允许动态值的样式/状态属性均可使用 path 绑定。
- 未提供 Dynamic binding context 时，Text、Image 和 Button 的展示值使用静态字面量，不为预览值
  虚构 `/data/...` path；候选事件中已声明的动态参数仍按事件参数规则绑定。
- 每个 path 绑定必须有同路径数据行，初始数据行必须位于首次使用该绑定的组件行之后。
- 数据行 value 可以是 string、number、boolean、object、array 或 null，并保持 outputSchema 类型。

## Data capability 路径

- CardSpec `dataBindings[].writeResultTo` 是业务数据根路径，例如 `/data/weather`。
- 可见动态字段路径由 `writeResultTo` 加 capability `outputSchema` 字段组成，例如
  `/data/weather/current/temperatureText`。
- 不把动态天气、日程等能力结果固化成组件字面量；字面量只用于标题、单位、标签等静态内容。
- 只输出组件实际绑定的叶子数据行；不要再输出未被组件引用的聚合对象行。
- 初始化值优先来自 `taskSpec.dataModel` 或 capability schema 提供的示例/默认值。
- 当两者都没有可展示值时，按用户请求和 schema 描述生成类型正确、语义合理的预览值；预览值只用于
  首次渲染，运行时 capability 结果仍写入同一路径并覆盖它，不能因此取消 path 绑定。
- 可见字符串绑定不得初始化为 `""` 或 `null`；数字 `0` 只有在业务上确实表示零时才使用，不能把
  空字符串和零统一当作占位符。

## 字符串拼接

Compact DSL path 绑定不嵌入字面字符串。需要“前缀 + 动态值 + 后缀”时，使用一个 Row 包含
多个 Text，动态 Text 使用 path 绑定：

```text
["feels","Row",{"space":0},["feels_prefix","feels_value","feels_suffix"]]
["feels_prefix","Text",{"content":"体感 "}]
["feels_value","Text",{"content":{"path":"/data/weather/current/feelsLikeC"}}]
["/data/weather/current/feelsLikeC",31]
["feels_suffix","Text",{"content":"°"}]
```

禁止写成 `"体感 /data/weather/current/feelsLikeC°C"`、`"{{/path}}"` 或其它路径文本。

## 列表数据

Compact DSL v1 的 children 是静态 id 数组，不输出 A2UI 模板 children 对象。卡片确实需要展示
重复数据时，只展开当前尺寸能够显示的有限项，并把每一项绑定到带数组下标的 JSON Pointer；
不改变工具3原有的信息密度和布局策略。

## 事件参数

- `action.functionCall.call` 和 args 字段名必须来自输入 event candidate。
- 静态目标直接写 JSON 值；动态参数使用 `{"path":"/..."}` 并提供数据行。
- 不复制 schema 的 `type`、`description` 等元数据，不虚构 URL、参数或函数。

## 绑定检查清单

- 每个可见动态值都绑定到 CardSpec 和 outputSchema 可推导的路径。
- 每个 path 都有类型正确的数据行，且首次初始化位于使用它的组件之后。
- 没有 path 文本拼接、`{{ ... }}`、`formatString` 或未使用的聚合数据行。
- 静态标题和单位仍是字面量，不为减少字面量而制造无意义绑定。
