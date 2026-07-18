# Form 协议硬约束

本文件是 Form 协议裁决摘要。组件属性查 `component-catalog.md`，绑定和表达式查 `data-binding.md`；当多个文档或示例冲突时，以本文边界规则为准。

## 决策顺序

1. 输出消息固定为 `createSurface` -> `updateComponents` -> `updateDataModel` 三行 JSONL。
2. `createSurface` 只声明 surface；`updateComponents.root` 是组件树入口；root 是唯一卡片 shell。
3. 只用 Form 允许组件、允许事件和允许绑定；禁用能力不因示例出现而放行。
4. 动态值遵循最终 Form DSL：优先用完整 `{{ ... }}` 表达式；也允许协议声明的 `{"path":"/..."}` PathBinding 和宿主明确注册的 FunctionCall。
5. 组件枚举、DataModel、事件能力、图片资源和颜色 token 按对应专项文件校验。

## Surface 树契约

- `version` 固定为 `"v0.9"`；`catalogId` 固定为 `"ohos.a2ui.extended.catalog.form"`。
- `createSurface` 默认只写 `surfaceId`、`catalogId`、`width`、`height`；`width/height` 必须写 `"matchParent"`，实际布局预算由 CardSpec/profile 尺寸决定。新卡片不要为了同步 root 圆角而写 `createSurface.styles`。若宿主明确需要外层形状和裁切控制，`createSurface.styles` 只允许 `borderRadius`、`clip`；不支持 `theme`。
- `updateComponents` 必须在 `createSurface` 之后，同一 surface 仅发送一次完整组件树。
- `updateComponents.root` 必须引用 `components` 中存在的组件 id。
- root 组件是唯一卡片 shell，承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和 `backgroundColor` / `linearGradient` / `backgroundImage` 等布局和表面样式；root `width/height` 必须写 `"matchParent"`，内部组件按 `2x2 = 160vp x 160vp`、`2x4 = 320vp x 160vp` 的实际预算落数值。背景也可由 root 下的真实背景组件承载。
- 三行消息的 `surfaceId` 必须一致；最小骨架是 `{"version":"v0.9","createSurface":{"surfaceId":"card",...}}`、`{"version":"v0.9","updateComponents":{"surfaceId":"card","root":"root","components":[...]}}`、`{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{...}}}`。
- `updateDataModel` 只提供运行数据；新卡片默认 `path: "/"` 并一次初始化所有 UI 表达式会访问的根结构和加载态；表达式引用必须能从 `value` 中解析，模板项相对表达式除外。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等背景样式必须写在 `root.styles`，或由 root 下的真实背景组件承载，不能放进 `createSurface.styles`。
- 原因：root 组件默认有不透明白色背景，会遮挡 surface 层背景，导致运行时显示默认白底或白屏。
- root shell、安全区和内容布局样式也要写在 root；普通组件使用数值宽高或可静态推导的约束。新卡片默认省略 `createSurface.styles`，只有宿主明确要求时才作为外层裁切/形状辅助，不替代 root shell。

## Form 裁剪范围

- Form 是 HarmonyOS A2UI 扩展协议的严格子集；不支持 A2UI 原生组件，不新增全量扩展协议之外的组件、属性或语法，不支持多端自适应断点。
- 允许组件只有 `Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 默认不要使用自定义组件。只有用户或宿主明确说明 catalog 已注册自定义组件时才可使用，最终仍只输出两个代码块，不额外输出宿主假设说明。

禁用：

- 组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`
- 能力/字段：`theme`、`Button.action`、`onAppear`、`onChange`、`onSelect`、`onReachStart`、`onReachEnd`
- 函数/变量：`setDataModel`、`setAttributes`、`navigate`、`scrollTo`、`sendToAssistant`、`$__widthBreakpoint`、`$__colorMode`
- 媒体：网络图片、内联/base64 SVG data URI、未声明资源路径、`data:image/svg+xml`

## 事件与函数

Form 仅支持通用事件 `onClick`，其值必须是 EventHandler 数组：

```json
"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/items/0/entityId} }}"}}}]
```

规则：

- 每个 EventHandler 必须有 `call`；`call` 是标识符，不写表达式。
- `call` 优先引用 [`../capability/event-capability/`](../capability/event-capability/) 中已声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 明确函数声明。
- `args` 字段名必须来自对应 event capability 的 `parameters`；跳转类还必须匹配合法 `supportedTargets`。
- `args` 中的 DataModel 参数使用完整表达式；模板项字段用相对表达式，例如 `"{{ ${entityId} }}"`；静态固定目标直接写 JSON 值。
- 每个事件只写 1 个 handler；Form 不支持 `condition`、`as` 和 `$context` 事件上下文。
- 属性级字符串拼接也使用完整表达式，写作 `"{{ ${/path} + ' 文本' }}"`。其它预定义扩展函数仍禁用。

## 表达式边界

新生成优先用完整 `{{ ... }}` 表达式读取 DataModel；修复或评审时也接受协议声明的 PathBinding 和宿主注册的 FunctionCall。所有动态展示、样式动态值和事件参数都必须落在组件/样式 schema 允许动态数据的位置。

规则：

- 一个字符串中只能有一对 `{{ ... }}`；不支持嵌套表达式。
- DataModel 可用 JSON Pointer 片段 `${/user/name}`，也可用点路径 `$__dataModel.user.name`；同一卡片优先统一用 `${/json/pointer}`。
- 模板项内可用 `$item/$index`，也可通过 `children.itemVar/indexVar` 自定义变量名；本 Skill 仍兼容 `${field}` 解析到当前数组项字段，`${/rootField}` 解析到根 DataModel。
- `id`、`component`、对象 key、EventHandler `call`、`updateDataModel.path`、CardSpec `writeResultTo`、模板 `children.path` 和整个 `styles` 对象不支持表达式。
- 表达式内字符串使用单引号；内置函数仅使用 `size()`。
- 表达式总长度不超过 2048 字符，括号嵌套不超过 20 层。
- 求值失败返回空字符串，不应依赖失败态做逻辑。
- 修复已有 DSL 时，合法 PathBinding 可以保留；未声明的函数绑定先改写为完整表达式或预计算字段；结构 JSON Pointer 字段不改。

## DataModel、模板和媒体

- `updateDataModel.path` 使用 JSON Pointer，例如 `/`、`/meeting/title`。
- 组件动态值使用完整表达式：单值 `"{{ ${/meeting/title} }}"`，拼接 `"{{ ${/meeting/title} + ' 开始' }}"`。
- 模板循环仅用于 `Row`、`Column`、`List` 的 `children`，模板对象必须包含 `componentId` 和 `path`，可选 `itemVar`、`indexVar`。
- 模板 `children.path` 指向数组；模板项内可用 `$item/$index` 或自定义变量名，绝对 `${/field}` 解析到根。
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；资源路径 SVG 受支持；不支持网络 URL、内联/base64 SVG data URI。
- 没有真实本地资源时，只使用渐变、半透明块、文字字形、`Progress` 或 `Divider` 承载场景表面、状态或分隔。

## 样式位置

- 对齐类属性放入 `styles`：`Row.styles.justifyContent`、`Row.styles.alignItems`、`Column.styles.justifyContent`、`Column.styles.alignItems`、`Stack.styles.alignContent`、`List.styles.listDirection`、`List.styles.scrollBar`。
- `Row.itemMargin`、`Column.itemMargin`、`List.space` 是组件属性；不要写已裁剪的 `Row.wrap` 或 `List.styles.nestedScroll`。
