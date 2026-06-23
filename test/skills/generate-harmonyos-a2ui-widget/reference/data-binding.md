# 数据绑定和表达式

## DataModel

每个 Surface 都有一个由 `updateDataModel` 更新的 JSON DataModel：

```json
{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{"meeting":{"time":"14:00"}}}}
```

组件通过 JSON Pointer 路径读取它：

```json
{"id":"time","component":"Text","content":{"path":"/meeting/time"}}
```

## 绝对路径

在重复项子树之外，使用绝对 JSON Pointer 路径：

- `/meeting/title`
- `/weather/temperatureLabel`
- `/action/targetId`

不要使用 `/meeting.title` 这样的点路径。

## 重复项路径

这是用于重复数据的协议特性，不是卡片生成模板。

当容器使用：

```json
{"children":{"componentId":"itemRow","path":"/items"}}
```

重复项组件及其后代可以用相对路径绑定当前项：

```json
{"id":"itemName","component":"Text","content":{"path":"name"}}
```

嵌套重复项结构可使用 `"items"` 这样的相对路径访问当前 `$item` 下的数据。

## 表达式

表达式只在 extended catalog 中可用，并且只可用于 `updateComponents` 内的标量值：

```json
{"content":"{{ '总共' + size($__dataModel.items) }}"}
```

使用：

- 表达式内使用单引号字符串。
- 用 `$__dataModel.xxx` 访问 DataModel 变量。
- 用 `$__widthBreakpoint` 处理响应式布局。
- 用 `$__colorMode` 处理亮/暗模式。
- 在重复项子树内使用 `$item` 和 `$index`。

除非表达式能明显减少数据重复，否则一句话卡片生成中应避免表达式。优先在 `updateDataModel` 中放入展示字符串。

## 禁止使用表达式的位置

不要在以下位置使用表达式：

- `id`
- `component`
- `{"path": "..."}`
- event `call`
- 对象键
- `"styles": "{{ ... }}"` 这样的完整对象值

## 绑定检查清单

- 每个可见文本/图片/进度绑定都指向数据。
- 每个宿主动作参数路径都指向数据。
- 每个重复项来源路径都指向数组。
- 相对路径只出现在重复项子树内部。
