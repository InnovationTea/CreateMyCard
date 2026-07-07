# Form 协议硬约束

本文件是 Form 协议裁决摘要。组件属性查 `component-catalog.md`，绑定和表达式查 `data-binding.md`；当多个文档或示例冲突时，以本文边界规则为准。

## 决策顺序

1. 输出消息固定为 `createSurface` -> `updateComponents` -> `updateDataModel` 三行 JSONL。
2. `createSurface` 只声明 surface；`updateComponents.root` 是组件树入口；root 是唯一卡片 shell。
3. 只用 Form 允许组件、允许事件和允许绑定；禁用能力不因示例出现而放行。
4. 动态值只用完整 `{{ ... }}` 表达式；不使用 `{"path":"/..."}` 或 `formatString` 做值绑定。
5. 组件枚举、DataModel、事件能力、图片资源和颜色 token 按对应专项文件校验。

## Surface 树契约

- `version` 固定为 `"v0.9"`；`catalogId` 固定为 `"ohos.a2ui.extended.catalog"`。
- `createSurface` 默认只写 `surfaceId`、`catalogId`、`width`、`height`；`width/height` 默认写 `"matchParent"`，用于外围卡片填满端侧父布局，校验仍按 CardSpec/profile 基准尺寸解析。新卡片不要为了同步 root 圆角而写 `createSurface.styles`。若宿主明确需要外层形状和裁切控制，`createSurface.styles` 只允许 `borderRadius`、`clip`；不支持 `theme`。
- `updateComponents` 必须在 `createSurface` 之后，同一 surface 仅发送一次完整组件树。
- `updateComponents.root` 必须引用 `components` 中存在的组件 id。
- root 组件是唯一卡片 shell，承载 `width`、`height`、`padding`、`borderRadius`、`clip` 和 `backgroundColor` / `linearGradient` / `backgroundImage` 等布局和表面样式；root `width/height` 默认写 `"matchParent"`，只表示外围 shell 填满父布局。背景也可由 root 下的真实背景组件承载。
- 三行消息的 `surfaceId` 必须一致；最小骨架是 `{"version":"v0.9","createSurface":{"surfaceId":"card",...}}`、`{"version":"v0.9","updateComponents":{"surfaceId":"card","root":"root","components":[...]}}`、`{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{...}}}`。
- `updateDataModel` 只提供运行数据；新卡片默认 `path: "/"` 并一次初始化所有 UI 表达式会访问的根结构和加载态；表达式引用必须能从 `value` 中解析，模板项相对表达式除外。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等背景样式必须写在 `root.styles`，或由 root 下的真实背景组件承载，不能放进 `createSurface.styles`。
- 原因：root 组件默认有不透明白色背景，会遮挡 surface 层背景，导致运行时显示默认白底或白屏。
- root shell、安全区和内容布局样式也要写在 root；除 `createSurface.width/height` 与 root `styles.width/height` 外，普通组件不得使用 `"matchParent"`。新卡片默认省略 `createSurface.styles`，只有宿主明确要求时才作为外层裁切/形状辅助，不替代 root shell。

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
"onClick":[{"call":"clickToIntent","args":{"intentName":"ViewCalendarEvent","params":{"entityId":"{{ ${/data/calendar/items/0/entityId} }}"}}}]
```

规则：

- 每个 EventHandler 必须有 `call`；`call` 和 `as` 是标识符，不写表达式。
- `call` 优先引用 [`../capability/event-capability/`](../capability/event-capability/) 中已声明的 `functionCall`；未声明时不要使用，除非用户同时提供宿主 catalog 明确函数声明。
- `args` 字段名必须来自对应 event capability 的 `parameters`；跳转类还必须匹配合法 `supportedTargets`。
- `args` 中的 DataModel 参数使用完整表达式；模板项字段用相对表达式，例如 `"{{ ${entityId} }}"`；静态固定目标直接写 JSON 值。
- `condition` 使用完整表达式；`as` 绑定返回值为当前事件行为链的局部变量。
- 属性级字符串拼接也使用完整表达式，写作 `"{{ ${/path} + ' 文本' }}"`。其它预定义扩展函数仍禁用。

## 表达式边界

本版本只用完整 `{{ ... }}` 表达式读取 DataModel。所有动态展示、样式动态值和事件参数都使用静态 JSON 值或完整表达式。

规则：

- 一个字符串中只能有一对 `{{ ... }}`；不支持嵌套表达式。
- DataModel 可用 JSON Pointer 片段 `${/user/name}`，也可用点路径 `$__dataModel.user.name`；同一卡片优先统一用 `${/json/pointer}`。
- 模板项内 `${field}` 解析到当前数组项字段，`${/rootField}` 解析到根 DataModel。
- `id`、`component`、对象 key、EventHandler `call`、EventHandler `as`、`updateDataModel.path`、CardSpec `writeResultTo`、模板 `children.path` 和整个 `styles` 对象不支持表达式。
- 表达式内字符串使用单引号；内置函数仅使用 `size()`。
- 表达式总长度不超过 2048 字符，括号嵌套不超过 20 层。
- 求值失败返回空字符串，不应依赖失败态做逻辑。
- 修复已有 DSL 时，看到 `{"path":...}` 或 `formatString` 值绑定先改写为完整表达式；结构 JSON Pointer 字段不改。

## DataModel、模板和媒体

- `updateDataModel.path` 使用 JSON Pointer，例如 `/`、`/meeting/title`。
- 组件动态值使用完整表达式：单值 `"{{ ${/meeting/title} }}"`，拼接 `"{{ ${/meeting/title} + ' 开始' }}"`。
- 模板循环仅用于 `Row`、`Column`、`List` 的 `children`，模板对象只有 `componentId` 和 `path`。
- 模板 `children.path` 指向数组；模板项内用 `${field}` 读取当前项字段，绝对 `${/field}` 解析到根；不使用 `$item`、`$index`、`itemVar`、`indexVar`。
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；不支持网络 URL、内联/base64 SVG 或未声明 SVG。
- 没有真实本地资源时，只使用渐变、半透明块、文字字形、`Progress` 或 `Divider` 承载场景表面、状态或分隔。

## 样式位置

- 对齐类属性放入 `styles`：`Row.styles.justifyContent`、`Row.styles.alignItems`、`Column.styles.justifyContent`、`Column.styles.alignItems`、`Stack.styles.alignContent`、`List.styles.listDirection`、`List.styles.scrollBar`、`List.styles.nestedScroll`。
- `Row.itemMargin`、`Column.itemMargin`、`List.space`、`Row.wrap` 是组件属性。
