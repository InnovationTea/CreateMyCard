# Form 协议硬约束

本文件是卡片生成使用的 Form 协议摘要，只保留生成卡片时必须记住的约束。

## 核心常量

- `version`: `"v0.9"`
- `catalogId`: `"ohos.a2ui.extended.catalog"`
- 输出格式：JSONL，每行一个消息 object。
- 默认输出顺序：`createSurface` -> `updateComponents` -> `updateDataModel`。
- `updateComponents` 必须在 `createSurface` 之后，同一 surface 仅发送一次完整组件树。
- `createSurface` 不支持 `theme` 字段。

## Form 裁剪范围

Form 是 HarmonyOS A2UI 扩展协议的严格子集：

- 不支持 A2UI 原生组件。
- 使用 extended catalog，并只使用 Form 子集声明的扩展组件。
- 不新增全量扩展协议之外的组件、属性或语法。
- 不支持多端自适应断点。

## 允许组件

只使用以下 10 个组件：

`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`

默认不要使用自定义组件。只有用户或宿主明确说明 catalog 已注册自定义组件时，才可使用，并在最终说明中标记该宿主假设。

## 排除能力

不要使用：

- `TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`
- `theme`
- `Button.action`
- `onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`
- 预定义扩展函数，例如 `setDataModel`、`setAttributes`、`navigate`、`scrollTo`、`sendToAssistant`
- `$__widthBreakpoint`、`$__colorMode`
- 网络图片、SVG 图片、`data:image/svg+xml`

## 事件与函数

Form 仅支持通用事件 `onClick`。

```json
"onClick": [
  {
    "call": "openDetail",
    "args": {
      "targetId": {"path": "/action/targetId"}
    }
  }
]
```

规则：

- 事件值必须是 EventHandler 数组。
- 每个 EventHandler 必须有 `call`。
- `args` 中的 DataModel 参数使用 `{"path":"/..."}` 或 `formatString`；不要生成 `condition` 表达式，复杂条件应预计算到 DataModel 或简化交互。
- `as` 绑定返回值为当前事件行为链的局部变量。
- `call` 和 `as` 是标识符，不写表达式。
- `call` 优先引用 `reference/event-capability/` 中已声明的 `functionCall`；未声明时只能引用宿主 catalog 已声明的自定义函数，或明确声明为宿主假设。
- 属性级字符串拼接使用原生 `formatString`（`{"call":"formatString","args":{"value":"...${/path}..."}}`）；它是属性绑定值，不是事件函数，与上面 EventHandler 的 `call` 不同。其它预定义扩展函数仍禁用。

## 表达式（禁用）

Form 协议历史上可能支持 `{{ ... }}` 表达式，但本 skill 生成结果禁用表达式。所有动态展示都应使用原生 `{path}` 绑定、`formatString` 拼接，或预先写入 `updateDataModel` 的展示字段。无法表达时简化设计，不退回表达式。

```json
"content": {"path": "/meeting/title"}
```

规则：

- 不生成 `{{ ... }}`。
- 不使用 `$__dataModel`、`${/json/pointer}` 表达式语法、`size()` 或 `$context` 表达式。
- 不在 `id`、`component`、对象 key、EventHandler `call`、EventHandler `as` 或任何组件属性中使用表达式。
- 条件文案、格式化值和多值运算优先在 `updateDataModel` 中预计算为展示字符串。

## DataModel 与模板

- `updateDataModel.path` 使用 JSON Pointer，例如 `/`、`/meeting/title`。
- 组件动态值优先用原生绑定：单值用 `{"path":"/meeting/title"}`，字符串拼接用 `{"call":"formatString","args":{"value":"${/meeting/title}"}}`（见 data-binding.md / function.md）。
- 不使用表达式读取 DataModel；原生绑定无法表达时，改用 `formatString`、预计算展示字段或简化布局。
- 模板循环仅用于 `Row`、`Column`、`List` 的 `children` 对象，模板对象只有 `componentId` 和 `path`：

```json
"children": {
  "path": "/items",
  "componentId": "itemTpl"
}
```

模板项内取值：

- 相对路径（不以 `/` 开头）解析到当前数组项，例如 `{"path":"name"}`。
- 绝对路径（以 `/` 开头）仍解析到根 DataModel。
- 拼接用 `formatString`，路径支持相对/绝对。
- 不使用 `$item`、`$index`、`itemVar`、`indexVar` 变量机制。

## 媒体

- `Image.src` 是本地/资源图片路径，不支持网络 URL。
- `styles.backgroundImage` 也是本地图片路径，不支持网络 URL。
- `Image` 不支持 SVG，包括 base64 SVG。
- 没有真实本地资源时，使用渐变、半透明块、文字字形、`Progress`、`Divider` 增强视觉。

## 样式位置

布局对齐类属性按协议放入 `styles`：

- `Row.styles.justifyContent`
- `Row.styles.alignItems`
- `Column.styles.justifyContent`
- `Column.styles.alignItems`
- `Stack.styles.alignContent`
- `List.styles.listDirection`
- `List.styles.scrollBar`
- `List.styles.nestedScroll`

`Row.itemMargin`、`Column.itemMargin`、`List.space`、`Row.wrap` 是组件属性。
