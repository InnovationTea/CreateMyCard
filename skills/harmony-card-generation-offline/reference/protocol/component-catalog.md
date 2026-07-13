# Form 组件目录

这是卡片生成使用的 Form 组件子集。本文只维护组件可用性、必需字段、组件特有属性和通用 `styles`；协议边界以 [`protocol.md`](protocol.md) 为准。

## 读取顺序

- 先查支持范围；组件不在允许列表内就不用。
- 再查字段归属表和组件速查表；表内“必需字段”指 `id` 和 `component` 之外的字段。
- 组件语义字段写顶层；视觉、尺寸、颜色、对齐和裁切写 `styles`。速查表里的 `fontSize`、`fontColor`、`objectFit`、`type`、`color` 等样式名默认指 `styles.xxx`。
- 跨组件尺寸、约束、背景、边框、阴影、显隐、裁剪、无障碍和层级效果查通用字段与通用样式。
- 动态展示值和字符串拼接按 [`data-binding.md`](data-binding.md)；root shell、事件边界、禁用能力和 JSONL 消息顺序按 [`protocol.md`](protocol.md)。

## 支持范围

- 必需 catalog：`"catalogId": "ohos.a2ui.extended.catalog.form"`。
- 允许组件：`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 禁用组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`。
- 不要把 Form 子集之外的 extended 组件或 Basic Catalog 的属性名混入 Form surface。

## 字段归属速查

本节是组件字段归属的权威入口。示例、旧 DSL 或其它文件与本节冲突时，以本节和下方组件速查表为准。

| 类别 | 顶层字段 | `styles` 字段 |
| --- | --- | --- |
| 容器结构 | `children`、`itemMargin`、`space` | `justifyContent`、`alignItems`、`alignContent`、`listDirection`、`scrollBar` |
| `Text` | `content`、`accessibility` | `width`、`height`、`fontSize`、`fontWeight`、`fontColor`、`maxLines`、`minFontSize`、`maxFontSize`、`textAlign`、`textOverflow` |
| `Image` | `src`、`accessibility` | `width`、`height`、`objectFit`、`fillColor`、`borderRadius`、`clip` |
| `Divider` | 无额外必需字段 | `width`、`height`、`strokeWidth`、`vertical`、`color` |
| `Progress` | `value` | `type`、`color`、`strokeWidth`、`width`、`height`、`borderRadius`、`backgroundColor` |
| `Button` | `label`、`enabled`、`onClick`、`accessibility` | `width`、`height`、`fontSize`、`fontWeight`、`fontColor`、`minFontSize`、`maxFontSize`、`backgroundColor`、`borderRadius`、`borderWidth`、`borderColor`、`padding`、`shadow` |
| `Checkbox` | `label`、`value`、`select`、`onClick` | `selectedColor`、`shape` |
| 卡片 shell | `createSurface.surfaceId/catalogId/width/height`、`updateComponents.root` | root 的 `width`、`height`、`aspectRatio`、`padding`、`borderRadius`、`clip`、`backgroundColor`、`backgroundImage`、`backgroundImageSizeWithStyle`、`linearGradient`；`createSurface.width/height` 与 root `width/height` 写 `"matchParent"` |

- 普通 `children` 只写组件 id 字符串数组；模板循环对象只给 `Row`、`Column`、`List.children`，必须包含 `{ "componentId": "...", "path": "/items" }`，可选 `itemVar/indexVar`；`Stack.children` 不使用模板循环。
- 展示值优先用字面量或完整 `{{ ... }}` 表达式；也可使用协议允许的 `{"path":"/..."}` PathBinding 或宿主明确注册的 FunctionCall。
- 图片和背景图只用用户提供或素材库声明的本地/资源路径；资源路径 SVG 受支持；没有真实资源时省略 `Image`，改用合法颜色、`Progress` 或 `Divider`。

## 组件速查表

所有组件对象都写 `id` 和 `component`；下方只列额外字段。

- `Column`：竖向容器；必需 `children`；`children` 为字符串数组或 `{ "componentId": "...", "path": "/items" }`；`itemMargin` 数字 vp；`styles.justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`；`styles.alignItems` 取 `start|center|end`。
- `Row`：横向容器；必需 `children`；`children` 为字符串数组或模板循环对象；`itemMargin` 数字 vp；不写已裁剪的 `wrap`；`styles.justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`；`styles.alignItems` 取 `top|center|bottom`。
- `Stack`：层叠容器，用于光晕、图片背景、叠加内容和进度环；必需 `children`；`children` 为字符串数组；`styles.alignContent` 取 `topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。
- `Text`：文本展示；必需 `content`；`content` 为字符串、数字、完整表达式或 PathBinding；`fontSize` 数字 fp；`fontWeight` 数字 `100..900`，按 100 间隔取值；`fontColor` 取 `#RRGGBB` 或 `#AARRGGBB`；`maxLines`、`minFontSize`、`maxFontSize` 为数字，`minFontSize/maxFontSize` 必须配合 `maxLines` 或布局大小限制才生效；`textOverflow` 只取 `clip|ellipsis`；`textAlign` 取 `start|center|end|justify`。卡片受保护文本不要用 `ellipsis` 或 `clip` 规避布局；不要写已裁剪的 `wordBreak` 或 `decoration`。
- `Image`：图片展示；必需 `src`；`src` 为用户提供或素材库声明的本地/资源路径，也可为完整表达式或 PathBinding 读取已声明资源路径；支持资源路径 SVG，不支持网络 URL 和 base64 内联 SVG data URI；`objectFit` 取 `fill|contain|cover|auto|none|scaleDown|topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd|matrix`；`fillColor` 为图片染色颜色，对 SVG 生效。图片承担主对象或状态识别时必须写明确 `width`、`height` 和 `objectFit`。
- `Divider`：分隔线；无额外必需字段；属性位于 `styles`：`strokeWidth` 为数字或带单位字符串，`vertical` 为 boolean，`color` 为颜色字符串。只用于真实分隔、时间线或强调线，不做装饰堆叠。
- `Progress`：进度条或进度环；必需 `value`，`total` 可选；`value/total` 为数字、完整表达式或 PathBinding；`styles.type` 取 `linear|ring|eclipse|scaleRing|capsule`；`styles.color` 只用纯色字符串或完整表达式，不支持 LinearGradient；`styles.strokeWidth` 数字 vp，默认 4.0，仅 `linear|ring|scaleRing` 生效；可写 `backgroundColor` 表达 track；`ring` 和 `scaleRing` 必须有稳定 `width`、`height`。
- `Button`：语义按钮；必需 `label`；使用 `label` 和 `onClick`，不用 `Button.action`；`label` 为字符串或完整表达式；`enabled` 为 boolean 或完整表达式；`onClick` 为 EventHandler 数组；`styles.fontWeight` 为数字或 `lighter|normal|regular|medium|bold|bolder`；`minFontSize/maxFontSize` 与文本自适应规则相同，必须配合布局限制才生效。CTA 是受保护文本，必须预留文字宽度和内边距；动作能力不明时删除 `onClick` 并改为普通支撑信息。
- `Checkbox`：多选框，只在用户明确要求切换状态时使用；无固定额外必需字段；`label` 为字符串、完整表达式或 PathBinding；`value` 为字符串、完整表达式或 PathBinding；`select` 为 boolean、完整表达式或 PathBinding；`styles.selectedColor` 为颜色字符串；`styles.shape` 取 `circle|rounded_square`；不要写已裁剪的 `group`、`unSelectedColor` 或 `mark`。
- `List`：重复项列表，桌面卡片中谨慎使用；必需 `children`；`children` 为字符串数组或模板循环对象；`space` 数字；`styles.listDirection` 取 `vertical|horizontal`；`styles.scrollBar` 取 `off|auto|on`；不要写已裁剪的 `nestedScroll`。列表只展示短数组摘要，长列表改为下一项、当前项或 `+N`。

## 通用顶层字段

- `id`：组件唯一标识，非模板生成使用稳定语义 ID；不能写表达式。
- `component`：组件类型，必须在允许组件内；不能写表达式。
- `children`：容器组件的子组件引用；普通树为字符串数组，模板循环对象只用于 `Row`、`Column`、`List`。
- `accessibility`：可选无障碍信息；常用 `{"label":"..."}` 静态短文本，也可在字段支持动态数据时使用表达式或 PathBinding。不要为了无障碍复制长段隐私内容或动态隐私字段。
- `onClick`：仅用于已声明事件能力，值为 EventHandler 数组；每个事件只写 1 个 handler，不写 `condition/as/$context`。

## 通用样式

所有 Form 组件都支持通用 `styles`：

- 尺寸与约束：`width`、`height`、`aspectRatio`、`constraintSize`
- 间距与形状：`margin`、`padding`、`borderRadius`
- 边框与表面：`borderWidth`、`borderColor`、`backgroundColor`、`backgroundImage`、`backgroundImageSizeWithStyle`、`linearGradient`
- 布局与效果：`layoutWeight`、`flexShrink`、`shadow`、`visibility`、`clip` boolean

取值说明：

- 尺寸数字默认是 vp。
- 字符串可使用可解析的数值单位，例如 `vp`、`fp`、`%`，以及文档允许时的 `px`；`width/height` 还支持 `matchParent`、`wrapContent`、`fixAtIdealSize`。卡片 root 使用 `matchParent`，普通组件优先使用数值，只有历史修复或宿主明确支持时才保留百分比或自适应枚举。
- `constraintSize` 为对象，必须同时写 `minWidth`、`maxWidth`、`minHeight`、`maxHeight`，用于约束动态文本、图片或弹性区域。
- `margin` / `padding` 可以是数字，也可以是 `{ "left": 0, "right": 0, "top": 0, "bottom": 0 }` 对象；数值仍按 vp 预算。
- `borderRadius`、`borderWidth` 可写数字或方向对象；卡片 root 优先用单个数字，内部小背板按预算使用。
- `createSurface.width/height` 和 root `styles.width/height` 必须写 `"matchParent"`；普通组件的 `width/height` 必须保持数值或可静态推导的约束，并按 `2x2 = 160vp x 160vp`、`2x4 = 320vp x 160vp` 的实际预算规划。
- 颜色使用 `#RRGGBB` 或 `#AARRGGBB`。
- 卡片背景样式放在 root 组件的 `styles` 中；新卡片默认省略 `createSurface.styles`，只有宿主明确要求外层形状/裁切时才可写 `borderRadius`、`clip`。
- `linearGradient` 固定写成对象并包含 `colors`；`direction` 可取 `Left|Top|Right|Bottom|LeftTop|LeftBottom|RightTop|RightBottom|None`，也可写 `angle` 数字和 `repeating` boolean。常用写法为 `{"direction":"RightBottom","colors":[["#RRGGBB",0],["#RRGGBB",1]]}`；`colors` 是嵌套 stop 对数组，不写成扁平数组，颜色可用 `#RRGGBB` 或 `#AARRGGBB`。
- `backgroundImage` 与 `backgroundImageSizeWithStyle` 只用于已声明本地/资源图片；背景图会挤压文字可读性时必须增加真实遮罩组件或改用颜色。
- `shadow` 可写对象 `{ "offsetX": 0, "offsetY": 2, "radius": 4, "color": "#66000000", "fill": false, "type": "color|blur" }`，其中 `radius` 必填；也可用 `outerDefaultXS|outerDefaultSM|outerDefaultMD|outerDefaultLG|outerFloatingSM|outerFloatingMD`。只用于少量内容背板或按钮，不用于多层装饰。
- `visibility` 取 `visible|hidden|none`；只用于必要的条件可见，不用它隐藏未完成设计；复杂条件优先预计算到 DataModel。

## 最小写法

以下示例只用于固定字段位置，不是视觉样式模板：

```json
{"id":"title","component":"Text","content":"{{ ${/title} }}","styles":{"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}}
{"id":"row","component":"Row","children":["title","action"],"itemMargin":8,"styles":{"justifyContent":"spaceBetween","alignItems":"center"}}
{"id":"action","component":"Button","label":"打开","onClick":[{"call":"clickToDeeplink","args":{"bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]}
{"id":"progress","component":"Progress","value":"{{ ${/progress/value} }}","total":"{{ ${/progress/total} }}","styles":{"type":"ring","color":"#A77DFF","strokeWidth":4,"width":72,"height":72}}
```

## 特殊规则

- `children`：普通组件树只写组件 id 字符串数组；模板循环对象只用于 `Row`、`Column`、`List` 的 `children`，对象必须包含 `componentId/path`，可选 `itemVar/indexVar`；`Stack.children` 只用字符串数组。
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地/资源路径；资源路径 SVG 受支持；不支持网络 URL、内联/base64 SVG data URI 或占位图；没有真实资源时省略 `Image`。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等卡片背景字段写在 root 组件或 root 下真实背景组件，不写进 `createSurface.styles`。
- `Button`：CTA 文本是受保护内容，避免窄固定宽度和省略；可点击按钮必须有已声明的 `onClick` EventHandler，动作能力不明时删除点击行为。
- `Checkbox`：如需点击行为，必须使用已声明 event capability；不要虚构 `toggleTodo` 一类切换函数。
- `List`：除非用户请求确实需要重复项，否则优先使用静态紧凑行。
