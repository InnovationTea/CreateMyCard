# Form 协议硬约束

本文件是 Form 协议裁决摘要。组件属性查 `component-catalog.md`，绑定细节查 `data-binding.md`，字符串拼接查 `function.md`；当多个文档或示例冲突时，以本文边界规则为准。

## 决策顺序

1. 输出消息固定为 `createSurface` -> `updateComponents` -> `updateDataModel` 三行 JSONL。
2. `createSurface` 只声明 surface；`updateComponents.root` 是组件树入口；root 是唯一卡片 shell。
3. 只用 Form 允许组件、允许事件和允许绑定；禁用能力不因示例出现而放行。
4. 展示值优先 `{ "path": "/..." }` 和 `formatString`；新卡片不使用表达式，遗留修复才允许受限例外。
5. 组件枚举、DataModel、事件能力、图片资源和颜色 token 按对应专项文件校验。

## Surface 树契约

- `version` 固定为 `"v0.9"`；`catalogId` 固定为 `"ohos.a2ui.extended.catalog"`。
- `createSurface` 只写 `surfaceId`、`catalogId`、`width`、`height`；不支持 `theme`。
- `updateComponents` 必须在 `createSurface` 之后，同一 surface 仅发送一次完整组件树。
- `updateComponents.root` 必须引用 `components` 中存在的组件 id。
- root 组件承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和 `backgroundColor` / `linearGradient` / `backgroundImage` 等布局和表面样式。
- `updateDataModel` 只提供运行数据；组件绑定路径必须能从它的 `value` 中解析，模板相对路径除外。
- 不要把 root shell、安全区或内容布局样式只写在 `createSurface.styles` 中。

## Form 裁剪范围

- Form 是 HarmonyOS A2UI 扩展协议的严格子集；不支持 A2UI 原生组件，不新增全量扩展协议之外的组件、属性或语法，不支持多端自适应断点。
- 允许组件只有 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 默认不要使用自定义组件。只有用户或宿主明确说明 catalog 已注册自定义组件时才可使用，最终仍只输出两个代码块，不额外输出宿主假设说明。

禁用：

- 组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`
- 能力/字段：`theme`、`Button.action`、`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`
- 函数/变量：`setDataModel`、`setAttributes`、`navigate`、`scrollTo`、`sendToAssistant`、`$__widthBreakpoint`、`$__colorMode`
- 媒体：网络图片、SVG 图片、`data:image/svg+xml`

## 事件与函数

Form 仅支持通用事件 `onClick`，其值必须是 EventHandler 数组：

```json
"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":{"path":"/data/calendar/items/0/entityId"}}}}]
```

规则：

- 每个 EventHandler 必须有 `call`；`call` 和 `as` 是标识符，不写表达式。
- `call` 优先引用 [`../capability/event-capability/`](../capability/event-capability/) 中已声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 明确函数声明。
- `args` 字段名必须来自对应 event capability 的 `parameters`；跳转类还必须匹配合法 `supportedTargets`。
- `args` 中的 DataModel 参数优先使用 `{"path":"/..."}` 或 `formatString`；模板项可用相对路径；`condition` 使用完整表达式。
- `as` 绑定返回值为当前事件行为链的局部变量。
- 属性级字符串拼接使用原生 `formatString`，写作 `{"call":"formatString","args":{"value":"${/path} 文本"}}`；它是属性绑定值，不是事件函数。其它预定义扩展函数仍禁用。

## 表达式受限例外

新卡片不要使用表达式。修复遗留 DSL 时，优先改写为 `{path}`、`formatString` 或 `updateDataModel` 预计算展示字段；只有无法等价改写且用户要求保留行为时，才保留表达式。表达式只在 `updateComponents` 中生效，写成完整字符串：

```json
"content":"{{ $__dataModel.meeting.title }}"
```

规则：

- 一个字符串中只能有一对 `{{ ... }}`；不支持嵌套表达式。
- DataModel 可用点路径 `$__dataModel.user.name`，也可用 JSON Pointer 片段 `${/user/name}`；新卡片优先预计算展示字段，不为拼接退回表达式。
- `id`、`component`、对象 key、EventHandler `call`、EventHandler `as`、`updateDataModel.path`、模板 `children.path` 和整个 `styles` 对象不支持表达式。
- 表达式内字符串使用单引号；内置函数仅使用 `size()`。
- 表达式总长度不超过 2048 字符，括号嵌套不超过 20 层。
- 求值失败返回空字符串，不应依赖失败态做逻辑。

## DataModel、模板和媒体

- `updateDataModel.path` 使用 JSON Pointer，例如 `/`、`/meeting/title`。
- 组件动态值优先原生绑定：单值 `{"path":"/meeting/title"}`，拼接 `{"call":"formatString","args":{"value":"${/meeting/title}"}}`。
- 模板循环仅用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`。
- 模板 `children.path` 指向数组；模板项内相对路径解析到当前数组项，绝对路径解析到根；不使用 `$item`、`$index`、`itemVar`、`indexVar`。
- `Image.src` 和 `styles.backgroundImage` 只使用本地/资源图片路径，不支持网络 URL、SVG 或 base64 SVG。
- 没有真实本地资源时，使用渐变、半透明块、文字字形、`Progress` 或 `Divider` 增强视觉。

## 样式位置

- 对齐类属性放入 `styles`：`Row.styles.justifyContent`、`Row.styles.alignItems`、`Column.styles.justifyContent`、`Column.styles.alignItems`、`Stack.styles.alignContent`、`List.styles.listDirection`、`List.styles.scrollBar`、`List.styles.nestedScroll`。
- `Row.itemMargin`、`Column.itemMargin`、`List.space`、`Row.wrap` 是组件属性。
