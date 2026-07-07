# Form 协议硬约束

本文件是 Form 协议裁决摘要。组件属性查 `component-catalog.md`，绑定和字符串拼接查 `data-binding.md`；当多个文档或示例冲突时，以本文边界规则为准。

## 决策顺序

1. 输出消息固定为 `createSurface` -> `updateComponents` -> `updateDataModel` 三行 JSONL。
2. `createSurface` 只声明 surface；`updateComponents.root` 是组件树入口；root 是唯一卡片 shell。
3. 只用 Form 允许组件、允许事件和允许绑定；禁用能力不因示例出现而放行。
4. 展示值只用 `{ "path": "/..." }` 和 `formatString`；本版本不输出 `{{ ... }}` 表达式。
5. 组件枚举、DataModel、事件能力、图片资源和颜色 token 按对应专项文件校验。

## Surface 树契约

- `version` 固定为 `"v0.9"`；`catalogId` 固定为 `"ohos.a2ui.extended.catalog"`。
- `createSurface` 默认只写 `surfaceId`、`catalogId`、`width`、`height`；新卡片不要为了同步 root 圆角而写 `createSurface.styles`。若宿主明确需要外层形状和裁切控制，`createSurface.styles` 只允许 `borderRadius`、`clip`；不支持 `theme`。
- `updateComponents` 必须在 `createSurface` 之后，同一 surface 仅发送一次完整组件树。
- `updateComponents.root` 必须引用 `components` 中存在的组件 id。
- root 组件是唯一卡片 shell，承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和 `backgroundColor` / `linearGradient` / `backgroundImage` 等布局和表面样式；背景也可由 root 下的真实背景组件承载。
- 三行消息的 `surfaceId` 必须一致；最小骨架是 `{"version":"v0.9","createSurface":{"surfaceId":"card",...}}`、`{"version":"v0.9","updateComponents":{"surfaceId":"card","root":"root","components":[...]}}`、`{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{...}}}`。
- `updateDataModel` 只提供运行数据；新卡片默认 `path: "/"` 并一次初始化所有 UI 绝对绑定路径的根结构和加载态；组件绑定路径必须能从 `value` 中解析，模板相对路径除外。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等背景样式必须写在 `root.styles`，或由 root 下的真实背景组件承载，不能放进 `createSurface.styles`。
- 原因：root 组件默认有不透明白色背景，会遮挡 surface 层背景，导致运行时显示默认白底或白屏。
- root shell、安全区和内容布局样式也要写在 root；新卡片默认省略 `createSurface.styles`，只有宿主明确要求时才作为外层裁切/形状辅助，不替代 root shell。

## Form 裁剪范围

- Form 是 HarmonyOS A2UI 扩展协议的严格子集；不支持 A2UI 原生组件，不新增全量扩展协议之外的组件、属性或语法，不支持多端自适应断点。
- 允许组件只有 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 默认不要使用自定义组件。只有用户或宿主明确说明 catalog 已注册自定义组件时才可使用，最终仍只输出两个代码块，不额外输出宿主假设说明。

禁用：

- 组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`
- 能力/字段：`theme`、`Button.action`、`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`
- 函数/变量：`setDataModel`、`setAttributes`、`navigate`、`scrollTo`、`sendToAssistant`、`$__widthBreakpoint`、`$__colorMode`
- 媒体：网络图片、内联/base64 SVG、未声明 SVG、`data:image/svg+xml`

## 事件与函数

Form 仅支持通用事件 `onClick`，其值必须是 EventHandler 数组：

```json
"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":{"path":"/data/calendar/items/0/entityId"}}}}]
```

规则：

- 每个 EventHandler 必须有 `call`；`call` 和 `as` 是标识符，不写表达式。
- `call` 优先引用 [`../capability/event-capability/`](../capability/event-capability/) 中已声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 明确函数声明。
- `args` 字段名必须来自对应 event capability 的 `parameters`；跳转类还必须匹配合法 `supportedTargets`。
- `args` 中的 DataModel 参数使用 `{"path":"/..."}` 或 `formatString`；模板项可用相对路径。本版本默认不生成 `condition`，需要条件分支时优先简化事件或拆成静态目标。
- `as` 绑定返回值为当前事件行为链的局部变量。
- 属性级字符串拼接使用原生 `formatString`，写作 `{"call":"formatString","args":{"value":"${/path} 文本"}}`；它是属性绑定值，不是事件函数。其它预定义扩展函数仍禁用。

## 路径表达边界

本版本不输出 `{{ ... }}` 表达式。所有动态展示、样式动态值和事件参数都使用静态 JSON 值、`{"path":"/..."}`、模板项相对 `{"path":"field"}` 或 `formatString`。

规则：

- 需要条件、运算、日期、货币或复杂格式化时，先在 `updateDataModel.value` 中放入预计算展示字段，再用路径读取。
- `id`、`component`、对象 key、EventHandler `call`、EventHandler `as`、`updateDataModel.path`、模板 `children.path` 和整个 `styles` 对象都不能写表达式。
- 修复已有 DSL 时，看到 `{{ ... }}` 先尝试改写为路径绑定、`formatString` 或预计算字段；无法等价改写时收敛设计或说明能力边界。

## DataModel、模板和媒体

- `updateDataModel.path` 使用 JSON Pointer，例如 `/`、`/meeting/title`。
- 组件动态值使用路径表达：单值 `{"path":"/meeting/title"}`，拼接 `{"call":"formatString","args":{"value":"${/meeting/title}"}}`。
- 模板循环仅用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`。
- 模板 `children.path` 指向数组；模板项内相对路径解析到当前数组项，绝对路径解析到根；不使用 `$item`、`$index`、`itemVar`、`indexVar`。
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；不支持网络 URL、内联/base64 SVG 或未声明 SVG。
- 没有真实本地资源时，只使用渐变、半透明块、文字字形、`Progress` 或 `Divider` 承载场景表面、状态或分隔。

## 样式位置

- 对齐类属性放入 `styles`：`Row.styles.justifyContent`、`Row.styles.alignItems`、`Column.styles.justifyContent`、`Column.styles.alignItems`、`Stack.styles.alignContent`、`List.styles.listDirection`、`List.styles.scrollBar`、`List.styles.nestedScroll`。
- `Row.itemMargin`、`Column.itemMargin`、`List.space`、`Row.wrap` 是组件属性。
