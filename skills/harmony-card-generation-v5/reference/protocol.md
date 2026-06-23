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
    "call": "clickToIntent",
    "args": {
      "intentName": "ViewCalendarEvent",
      "params": {
        "entityId": "{{ $__dataModel.calendar.primaryEntityId }}"
      }
    }
  }
]
```

规则：

- 事件值必须是 EventHandler 数组。
- 每个 EventHandler 必须有 `call`。
- `args`、`condition` 可使用完整表达式。
- `as` 绑定返回值为当前事件行为链的局部变量。
- `call` 和 `as` 是标识符，不写表达式。
- `call` 优先引用 `reference/event-capability/click-event.md` 已声明的 `functionCall`；只有用户或宿主明确提供其它自定义函数时，才作为宿主假设使用。

## 表达式

表达式只在 `updateComponents` 中生效，写成完整字符串：

```json
"content": "{{ $__dataModel.meeting.title }}"
```

规则：

- 一个字符串中只能有一对 `{{ ... }}`。
- 不支持嵌套表达式。
- `id`、`component`、对象 key、EventHandler `call`、EventHandler `as` 不支持表达式。
- 表达式内字符串使用单引号。
- 内置函数仅使用 `size()`。
- 表达式总长度不超过 2048 字符，括号嵌套不超过 20 层。
- 求值失败返回空字符串，不应依赖失败态做逻辑。

## DataModel 与模板

- `updateDataModel.path` 使用 JSON Pointer，例如 `/`、`/meeting/title`。
- 组件动态值默认用表达式读取 DataModel，例如 `$__dataModel.meeting.title`。
- 表达式中也可用 `${/json/pointer}` 引用 DataModel。
- 模板循环仅用于 `Row`、`Column`、`List` 的 `children` 对象：

```json
"children": {
  "path": "/items",
  "componentId": "itemTpl",
  "itemVar": "item",
  "indexVar": "index"
}
```

模板变量：

- 默认 `$item`、`$index`
- 自定义变量名不带 `$`，引用时加 `$`
- 变量名必须匹配 `^[a-zA-Z_][a-zA-Z0-9_]*$`
- 嵌套模板中，外层变量需要通过自定义 `itemVar` 避免被内层 `$item` 遮蔽

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
