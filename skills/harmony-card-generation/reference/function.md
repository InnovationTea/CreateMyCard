# 函数：formatString

## 用途

`formatString` 是 A2UI 原生函数，把静态文本和 DataModel 中的变量拼成一个字符串。它是组件属性的一种绑定值，与 `{"path":"/..."}` 同属优选的原生绑定方式，专门解决「字符串拼接」。

需要拼接时优先用它，不要用表达式 `{{ ... }}`。

## 语法

```json
{"call":"formatString","args":{"value":"hello ${/data/name} ${/data/count}"}}
```

- `args` 只包含 `value`，`value` 是一个字符串模板。
- 用 `${...}` 插入 DataModel 的值，`${...}` 内只能是 JSON Pointer 路径：
  - 绝对路径：`${/data/status/current/valueText}`
  - 模板循环内的相对路径：`${name}`，由当前数组项作用域解析。
- 一个字符串里可以有多个 `${...}`。这是它相对表达式的关键优势：表达式一个字符串只能有一对 `{{ ... }}`，而 `formatString` 可以自由拼接多个变量和静态文本。
- 字面量 `${` 需要转义为 `\${`。
- 取值类型转换：数字、布尔按其字符串形式输出；null 或缺失路径输出空字符串 `""`。

## 示例

状态卡片拼接主值和单位：

```json
{"id":"metric","component":"Text","content":{"call":"formatString","args":{"value":"${/data/status/current/valueText}${/data/status/current/unit}"}}}
```

对应的 DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"data":{"status":{"current":{"valueText":"26","unit":"%"}}}}}}
```

渲染结果：`26%`。

## 不支持

`formatString` 只做简单的「静态文本 + DataModel 变量」拼接。以下不支持：

- 内嵌函数调用插值，例如 `${now()}`、`${formatDate(value:${/d}, format:'yyyy-MM-dd')}`。
- 嵌套 `${...}`。
- 其它格式化函数：`formatNumber`、`formatCurrency`、`formatDate`、`pluralize`。

需要数字、货币、日期、复数等格式化时：

- 优先在 `updateDataModel` 中预先放入已格式化好的展示字符串，例如 `"price":"¥19.98"`。
- 或退回表达式 `{{ ... }}` 处理。

## 与其它能力的边界

- `formatString` 是组件属性的绑定值（如 `Text.content`、`Button.label`），不是事件函数。EventHandler 的 `call` 优先引用 event capability 的 `functionCall` 或宿主声明的自定义动作函数，二者不同。
- 表达式内置的 `size()` 只在 `{{ ... }}` 表达式中使用，与 `formatString` 无关。
