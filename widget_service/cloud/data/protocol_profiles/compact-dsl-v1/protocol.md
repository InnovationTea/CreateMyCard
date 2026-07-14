# Compact DSL Protocol v1

- `version`："v1"
- `format`："compact-dsl"
- `catalogId`："ohos.genui.compact.catalog"

## 输出边界

`genui` 只包含裸 NDJSON，不带 Markdown 围栏、解释文字或外层 JSON 对象。

协议只有两种行：

```text
["<componentId>","<Type>",{<props>},["<childId>",...]]
["/<path>",<value>]
```

- 每个物理行必须是一个完整 JSON 数组。
- `Row`、`Column`、`List`、`Stack`、`Grid` 必须带 children；其他组件禁止带 children。
- 第一行必须创建 `root`，类型只能是 `Column` 或 `Stack`，且 props 包含 `"width":"matchParent"`。
- 父组件先于子组件创建；除 root 外，每个组件必须先出现在更早父组件的 children 中。
- props 直接写组件属性，禁止使用旧 A2UI 的 `styles` 包装层。
- 禁止输出 `createSurface`、`updateComponents`、`updateDataModel`。

## 组件选择

默认优先使用核心展示组件。表单组件仅用于明确的输入或选择场景，`Grid` 仅用于明确宫格，`Web` 仅用于明确网页嵌入。
