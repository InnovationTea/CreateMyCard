# Form 组件目录

这是卡片生成使用的 Form 组件子集。本文只维护组件可用性、必需字段、组件特有属性和通用 `styles`；协议边界以 [`protocol.md`](protocol.md) 为准。

## 读取顺序

- 先查支持范围；组件不在允许列表内就不用。
- 再查组件速查表；表内“必需字段”指 `id` 和 `component` 之外的字段。
- 组件语义字段写顶层；视觉、尺寸、颜色、对齐和裁切写 `styles`。速查表里的 `fontSize`、`fontColor`、`objectFit`、`type`、`color` 等样式名默认指 `styles.xxx`。
- 跨组件尺寸、背景、边框、阴影、显隐和裁剪查通用样式。
- 动态展示值和字符串拼接按 [`data-binding.md`](data-binding.md)；root shell、事件边界、禁用能力和 JSONL 消息顺序按 [`protocol.md`](protocol.md)。

## 支持范围

- 必需 catalog：`"catalogId": "ohos.a2ui.extended.catalog"`。
- 允许组件：`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 禁用组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`。
- 不要把 Form 子集之外的 extended 组件或 Basic Catalog 的属性名混入 Form surface。

## 字段归属速查

本节是组件字段归属的权威入口。示例、旧 DSL 或其它文件与本节冲突时，以本节和下方组件速查表为准。

| 类别 | 顶层字段 | `styles` 字段 |
| --- | --- | --- |
| 容器结构 | `children`、`itemMargin`、`wrap`、`space` | `justifyContent`、`alignItems`、`alignContent`、`listDirection`、`scrollBar` |
| `Text` | `content` | `fontSize`、`fontWeight`、`fontColor`、`maxLines`、`textAlign`、`textOverflow` |
| `Image` | `src` | `width`、`height`、`objectFit`、`aspectRatio` |
| `Progress` | `value`、`total` | `type`、`color`、`width`、`height` |
| `Button` | `label`、`enabled`、`onClick` | `fontSize`、`fontWeight`、`fontColor`、`backgroundColor`、`borderRadius` |
| `Checkbox` | `label`、`value`、`group`、`select`、`onClick` | `selectedColor`、`unSelectedColor`、`shape`、`mark` |
| 卡片 shell | `createSurface.surfaceId/catalogId/width/height`、`updateComponents.root` | root 的 `width`、`height`、`padding`、`borderRadius`、`clip`、`backgroundColor`、`linearGradient` |

- 普通 `children` 只写组件 id 字符串数组；模板循环对象只给 `Row`、`Column`、`List.children`，形态固定为 `{ "componentId": "...", "path": "/items" }`；`Stack.children` 不使用模板循环。
- 展示值只用字面量或完整 `{{ ... }}` 表达式；不要用 `{"path":"/..."}` 或 `formatString` 做组件值绑定。
- 图片和背景图只用用户提供或素材库声明的本地/资源路径；没有真实资源时省略 `Image`，改用合法颜色、`Progress` 或 `Divider`。

## 组件速查表

所有组件对象都写 `id` 和 `component`；下方只列额外字段。

- `Column`：竖向容器；必需 `children`；`children` 为字符串数组或 `{ "componentId": "...", "path": "/items" }`；`itemMargin` 数字 vp；`styles.justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`；`styles.alignItems` 取 `start|center|end`。
- `Row`：横向容器；必需 `children`；`children` 为字符串数组或模板循环对象；`itemMargin` 数字 vp；`wrap` 取 `noWrap|wrap`；`styles.justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`；`styles.alignItems` 取 `top|center|bottom`。
- `Stack`：层叠容器，用于光晕、图片背景、叠加内容和进度环；必需 `children`；`children` 为字符串数组；`styles.alignContent` 取 `topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。
- `Text`：文本展示；必需 `content`；`fontSize` 数字 fp；`fontWeight` 数字 `100..900`；`fontColor` 取 `#RRGGBB` 或 `#AARRGGBB`；`maxLines`、`minFontSize`、`maxFontSize` 为数字；`textOverflow` 取 `none|clip|ellipsis|marquee`；`textAlign` 取 `start|center|end|justify`；`wordBreak` 取 `normal|breakAll|breakWord|hyphenation`；`decoration` 为文本装饰对象。
- `Image`：图片展示；必需 `src`；`objectFit` 取 `fill|contain|cover|auto|none|scaleDown|topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd|matrix`；`aspectRatio` 为数字。
- `Divider`：分隔线；无额外必需字段；属性位于 `styles`：`strokeWidth` 为数字或带单位字符串，`vertical` 为 boolean，`color` 为颜色字符串。
- `Progress`：进度条或进度环；必需 `total`；`value` 为数字或完整表达式；`total` 同规则且必选；`styles.type` 取 `linear|ring|eclipse|scaleRing|capsule`；`styles.color` 为颜色字符串或完整表达式。
- `Button`：语义按钮；必需 `label`；使用 `label` 和 `onClick`，不用 `Button.action`；`label` 为字符串或完整表达式；`enabled` 为 boolean 或完整表达式；`onClick` 为 EventHandler 数组；`styles.fontWeight` 为数字或 `normal|regular|medium|bold|bolder`。
- `Checkbox`：多选框，只在用户明确要求切换状态时使用；无固定额外必需字段；`label` 为字符串或完整表达式；`value` / `group` 为字符串或完整表达式；`select` 为 boolean 或完整表达式；`styles.selectedColor` / `styles.unSelectedColor` 为颜色字符串；`styles.shape` 取 `circle|rounded_square`；`styles.mark` 为 `{ strokeColor, size, strokeWidth }`。
- `List`：重复项列表，桌面卡片中谨慎使用；必需 `children`；`children` 为字符串数组或模板循环对象；`space` 数字；`styles.listDirection` 取 `vertical|horizontal`；`styles.scrollBar` 取 `off|auto|on`；`styles.nestedScroll` 按协议枚举使用，卡片默认避免嵌套滚动。

## 通用样式

所有 Form 组件都支持通用 `styles`：

- 尺寸与约束：`width`、`height`、`constraintSize`
- 间距与形状：`margin`、`padding`、`borderRadius`
- 边框与表面：`borderWidth`、`borderColor`、`backgroundColor`、`backgroundImage`、`backgroundImageSizeWithStyle`、`linearGradient`
- 布局与效果：`layoutWeight`、`flexShrink`、`shadow`、`visibility`、`clip` boolean

取值说明：

- 尺寸数字默认是 vp。
- 字符串可使用 `vp`、`fp`、`%`，以及文档允许时的 `px`。
- `"matchParent"` 只允许用于 `createSurface.width/height` 和 root `styles.width/height`，用于外围卡片填满端侧父布局；普通组件的 `width/height` 必须保持数值或可静态推导的约束。
- 颜色使用 `#RRGGBB` 或 `#AARRGGBB`。
- 卡片背景样式放在 root 组件的 `styles` 中；新卡片默认省略 `createSurface.styles`，只有宿主明确要求外层形状/裁切时才可写 `borderRadius`、`clip`。
- `linearGradient` 固定写成对象并包含 `direction` 与 `colors`，例如 `{"direction":"RightBottom","colors":[["#RRGGBB",0],["#RRGGBB",1]]}`；`colors` 是嵌套 stop 对数组，不写成扁平数组，颜色可用 `#RRGGBB` 或 `#AARRGGBB`。

## 最小写法

以下示例只用于固定字段位置，不是视觉样式模板：

```json
{"id":"title","component":"Text","content":"{{ ${/title} }}","styles":{"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}}
{"id":"row","component":"Row","children":["title","action"],"itemMargin":8,"styles":{"justifyContent":"spaceBetween","alignItems":"center"}}
{"id":"action","component":"Button","label":"打开","onClick":[{"call":"clickToDeeplink","args":{"bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}
{"id":"progress","component":"Progress","value":"{{ ${/progress/value} }}","total":"{{ ${/progress/total} }}","styles":{"type":"ring","color":"#A77DFF","width":72,"height":72}}
```

## 特殊规则

- `children`：普通组件树只写组件 id 字符串数组；模板循环对象只用于 `Row`、`Column`、`List` 的 `children`，对象只能包含 `componentId` 和 `path`；`Stack.children` 只用字符串数组。
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；不支持网络 URL、内联/base64 SVG、未声明 SVG 或占位图；没有真实资源时省略 `Image`。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等卡片背景字段写在 root 组件或 root 下真实背景组件，不写进 `createSurface.styles`。
- `Button`：CTA 文本是受保护内容，避免窄固定宽度和省略；可点击按钮必须有已声明的 `onClick` EventHandler，动作能力不明时删除点击行为。
- `Checkbox`：如需点击行为，必须使用已声明 event capability；不要虚构 `toggleTodo` 一类切换函数。
- `List`：除非用户请求确实需要重复项，否则优先使用静态紧凑行。
