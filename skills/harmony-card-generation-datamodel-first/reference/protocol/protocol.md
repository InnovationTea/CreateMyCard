# Form 协议硬约束

本文件是卡片生成使用的 Form 协议裁决摘要。组件属性查 `component-catalog.md`，绑定细节查 `data-binding.md`，字符串拼接查 `function.md`；当多个文档或示例冲突时，以本文件的边界规则为准。

## 先决策

- 先定输出消息：`createSurface`、`updateComponents`、`updateDataModel` 三行 JSONL，顺序固定。
- 再定 surface/root：`createSurface` 只声明 surface；`updateComponents.root` 是组件树入口；root 是唯一卡片 shell。
- 再定协议范围：只用允许组件和允许事件，禁用能力不因示例出现而放行。
- 再定绑定方式：展示值优先完整表达式 `{{ ... }}`，`{ "path": "/..." }` 和 `formatString` 只做兜底。
- 最后查专项文档：组件枚举、DataModel、事件能力、图片资源和颜色 token 都按对应文件校验。

## Surface 树契约

- `createSurface` 只创建 surface，并声明 `surfaceId`、`catalogId`、`width`、`height`。
- `updateComponents.root` 是组件树入口，必须引用 `components` 中存在的组件 id。
- root 组件是唯一卡片 shell，承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和 `backgroundColor` / `linearGradient` / `backgroundImage` 等布局和表面样式。
- `updateDataModel` 只提供运行数据；组件表达式引用和原生绑定路径必须能从它的 `value` 中解析，模板相对路径除外。
- 不要把 root shell、安全区或内容布局样式只写在 `createSurface.styles` 中。

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

默认不要使用自定义组件。只有用户或宿主明确说明 catalog 已注册自定义组件时，才可使用；最终仍只输出两个代码块，不额外输出宿主假设说明。

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
        "entityId": "{{ ${/data/calendar/items/0/entityId} }}"
      }
    }
  }
]
```

规则：

- 事件值必须是 EventHandler 数组。
- 每个 EventHandler 必须有 `call`。
- `args` 中的 DataModel 参数优先使用完整表达式；模板项相对字段或端侧要求对象绑定时使用 `{"path":"/..."}` 或 `formatString`；`condition` 使用完整表达式。
- `as` 绑定返回值为当前事件行为链的局部变量。
- `call` 和 `as` 是标识符，不写表达式。
- `call` 优先引用 [`../capability/event-capability/`](../capability/event-capability/) 中已声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 中的明确函数声明。
- 属性级字符串拼接优先使用完整表达式；原生 `formatString`（`{"call":"formatString","args":{"value":"...${/path}..."}}`）只作兜底。它是属性绑定值，不是事件函数，与上面 EventHandler 的 `call` 不同。其它预定义扩展函数仍禁用。

## 表达式（优先）

表达式是组件展示值的优先方式。表达式只在 `updateComponents` 中生效，写成完整字符串：

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
- 组件动态展示值优先用表达式：单值用 `"{{ $__dataModel.meeting.title }}"`，字符串拼接用 `"{{ $__dataModel.meeting.title + '开始' }}"`。
- 原生 `{"path":"/meeting/title"}` 和 `{"call":"formatString","args":{"value":"${/meeting/title}"}}` 是兜底方式，仅在表达式不适合、模板相对路径、双向绑定或端侧要求对象绑定时使用（见 data-binding.md / function.md）。
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
- 拼接当前项字段时可用 `formatString`，路径支持相对/绝对。
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
