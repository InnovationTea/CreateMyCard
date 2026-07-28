# Form 组件目录

这是卡片生成使用的 Form 组件子集。本文维护组件可用性、必需字段、组件特有属性、通用 `styles` 及详细属性规格；协议边界以 [`protocol.md`](protocol.md) 为准。

## 读取顺序

- 先查支持范围；组件不在允许列表内就不用。
- 再查字段归属表和组件速查表；表内"必需字段"指 `id` 和 `component` 之外的字段。
- 组件语义字段写顶层；视觉、尺寸、颜色、对齐和裁切写 `styles`。速查表里的 `fontSize`、`fontColor`、`objectFit`、`type`、`color` 等样式名默认指 `styles.xxx`。
- 跨组件尺寸、约束、背景、边框、阴影、显隐、裁剪、无障碍和层级效果查通用字段与通用样式。
- 各组件详细的属性表、样式表和事件支持参见下文逐组件章节。
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
- 图片和背景图只用用户提供或素材库声明的本地 SVG/PNG 资源路径；没有真实资源时省略 `Image`，改用合法颜色、`Progress` 或 `Divider`。

## 组件速查表

所有组件对象都写 `id` 和 `component`；下方只列额外字段。

- `Column`：竖向容器；必需 `children`；`children` 为字符串数组或 `{ "componentId": "...", "path": "/items" }`；`itemMargin` 数字 vp；`styles.justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`，**卡片中推荐 `center`**；`styles.alignItems` 取 `start|center|end`，**卡片中推荐 `center`**。
- `Row`：横向容器；必需 `children`；`children` 为字符串数组或模板循环对象；`itemMargin` 数字 vp；不写已裁剪的 `wrap`；`styles.justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`，**卡片中推荐 `center`**；`styles.alignItems` 取 `top|center|bottom`，**卡片中推荐 `center`**。
- `Stack`：层叠容器，用于光晕、图片背景、叠加内容和进度环；必需 `children`；`children` 为字符串数组；`styles.alignContent` 取 `topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。
- `Text`：文本展示；必需 `content`；`content` 为字符串、数字、完整表达式或 PathBinding；`fontSize` 数字 fp；`fontWeight` 数字 `100..900`，按 100 间隔取值；`fontColor` 取 `#RRGGBB` 或 `#AARRGGBB`；`maxLines`、`minFontSize`、`maxFontSize` 为数字，`minFontSize/maxFontSize` 必须配合 `maxLines` 或布局大小限制才生效；`textOverflow` 只取 `clip|ellipsis`；`textAlign` 取 `start|center|end|justify`。卡片受保护文本不要用 `ellipsis` 或 `clip` 规避布局；不要写已裁剪的 `wordBreak` 或 `decoration`。
- `Image`：图片展示；必需 `src`；`src` 为用户提供或素材库声明的本地 SVG/PNG 路径，也可为完整表达式或 PathBinding 读取已声明资源路径；不支持网络 URL 和 base64 内联图片；`objectFit` 取 `fill|contain|cover|auto|none|scaleDown|topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd|matrix`。图片承担主对象或状态识别时必须写明确 `width`、`height` 和 `objectFit`。
- `Divider`：分隔线；无额外必需字段；属性位于 `styles`：`strokeWidth` 为数字或带单位字符串，`vertical` 为 boolean，`color` 为颜色字符串。只用于真实分隔、时间线或强调线，不做装饰堆叠。
- `Progress`：进度条或进度环；必需 `value`，`total` 可选；`value/total` 为数字、完整表达式或 PathBinding；`styles.type` 取 `linear|ring|eclipse|scaleRing|capsule`；`styles.color` 只用纯色字符串或完整表达式，不支持 LinearGradient；`styles.strokeWidth` 数字 vp，默认 4.0，仅 `linear|ring|scaleRing` 生效；可写 `backgroundColor` 表达 track；`ring` 和 `scaleRing` 必须有稳定 `width`、`height`。
- `Button`：语义按钮；必需 `label`；使用 `label` 和 `onClick`，不用 `Button.action`；`label` 为字符串或完整表达式；`enabled` 为 boolean 或完整表达式；`onClick` 为 EventHandler 数组；`styles.fontWeight` 为数字或 `lighter|normal|regular|medium|bold|bolder`；`minFontSize/maxFontSize` 与文本自适应规则相同，必须配合布局限制才生效。CTA 是受保护文本，必须预留文字宽度和内边距；动作能力不明时删除 `onClick` 并改为普通支撑信息。
- `Checkbox`：多选框，只在用户明确要求切换状态时使用；无固定额外必需字段；`label` 为字符串、完整表达式或 PathBinding；`value` 为字符串、完整表达式或 PathBinding；`select` 为 boolean、完整表达式或 PathBinding；`styles.selectedColor` 为颜色字符串；`styles.shape` 取 `circle|rounded_square`；不要写已裁剪的 `group`、`unSelectedColor` 或 `mark`。
- `List`：重复项列表，桌面卡片中谨慎使用；必需 `children`；`children` 为字符串数组或模板循环对象；`space` 数字；`styles.listDirection` 取 `vertical|horizontal`；`styles.scrollBar` 取 `off|auto|on`；不要写已裁剪的 `nestedScroll`。列表只展示短数组摘要，长列表改为下一项、当前项或 `+N`。

## 通用顶层字段

- `id`：必选，surface 范围内唯一的组件 ID；不能写表达式。
- `component`：必选，组件类型名，必须在允许组件内；不能写表达式。
- `children`：容器组件的子组件引用；普通树为字符串数组，模板循环对象只用于 `Row`、`Column`、`List`。
- `accessibility`：可选，无障碍属性。常用 `{"label":"..."}` 静态短文本，也可在字段支持动态数据时使用表达式或 PathBinding。不要为了无障碍复制长段隐私内容或动态隐私字段。
- `onClick`：仅用于已声明事件能力，值为 EventHandler 数组；每个事件只写 1 个 handler，不写 `condition/as/$context`。

## 通用样式

组件如无特殊说明则均支持以下通用样式。所有样式写在组件的 `styles` 对象内。

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `width` | 设置组件宽度 | 数值 `[0, inf)` 默认单位 vp；字符串 `数值+单位`（单位 `fp`/`vp`/`%`）；枚举值 `matchParent`（自适应父组件内容区，不含 padding/border）、`wrapContent`（自适应子组件，受父组件约束）、`fixAtIdealSize`（自适应子组件，不受父组件约束） | 否 | 是 | `"width": 100` 或 `"width": "100vp"` |
| `height` | 设置组件高度 | 同 `width` | 否 | 是 | `"height": "100vp"` |
| `constraintSize` | 约束尺寸范围 | 对象 `{minWidth, maxWidth, minHeight, maxHeight}`，四个属性均必选，类型为数值或字符串（同 width/height 取值规则） | 否 | 否（对象自身不可整体绑定，子字段可单独绑定） | `"constraintSize": { "minWidth": 10, "maxWidth": 100, "minHeight": 10, "maxHeight": 100 }` |
| `aspectRatio` | 宽高比 `width/height` | 数字，默认值 1.0。仅设 width+aspectRatio→height=width/aspectRatio；仅设 height+aspectRatio→width=height\*aspectRatio；同时设三者→height 不生效。constraintSize 优先级高于 aspectRatio | 否 | 是 | `"aspectRatio": 1.5` |
| `margin` | 外间距 | 数值 `[0, inf)` 默认单位 vp（统一四边）；对象 `{top, right, bottom, left}` 四属性均可选，取值数值或字符串（单位 `fp`/`vp`/`%`） | 否 | 是 | `"margin": { "left": 4, "top": "4vp" }` |
| `padding` | 内边距 | 同 `margin` | 否 | 是 | `"padding": { "left": 8, "top": "8vp" }` |
| `borderRadius` | 四边角半径 | 数值 `[0, inf)` 默认单位 vp（统一四角）；对象 `{topLeft, topRight, bottomLeft, bottomRight}` 四属性均可选 | 否 | 是 | `"borderRadius": 8` |
| `borderWidth` | 边框宽度 | 数值 `[0, inf)` 默认单位 vp；字符串 `数值+单位`（`fp`/`vp`/`%`） | 否 | 是 | `"borderWidth": 1` |
| `borderColor` | 边框颜色 | `#AARRGGBB` 或 `#RRGGBB` 字符串 | 否 | 是 | `"borderColor": "#FF000000"` |
| `backgroundColor` | 背景颜色 | `#AARRGGBB` 或 `#RRGGBB` 字符串 | 否 | 是 | `"backgroundColor": "#00FF0000"` |
| `backgroundImage` | 背景图片路径 | 字符串，本地图片路径，不支持网络 URL | 否 | 是 | `"backgroundImage": "/resources/bg.png"` |
| `backgroundImageSizeWithStyle` | 背景图片尺寸模式 | 枚举字符串或对象 `{width, height}`（两属性均必选，数值或字符串）。枚举值：`cover`（保持比例填满）、`contain`（保持比例完整显示）、`auto`（保持原比例）、`fill`（拉伸填满）。默认值 `auto` | 否 | 是 | `"backgroundImageSizeWithStyle": "contain"` |
| `linearGradient` | 线性渐变 | 对象 `{angle, direction, colors, repeating}`。`angle`：可选数值，起始角度，默认 180；`direction`：可选枚举 `Left\|Top\|Right\|Bottom\|LeftTop\|LeftBottom\|RightTop\|RightBottom\|None`，默认 `None`；`colors`：必选，数组 `[[ResourceColor, number]]`，指定渐变色及其百分比位置，默认 `[]`；`repeating`：可选布尔，颜色重复着色，默认 `false` | 否 | 否（对象自身不可整体绑定，子字段可单独绑定） | `"linearGradient": { "angle": 90, "colors": [["#ff0000", 0.0], ["#0000ff", 1.0]] }` |
| `shadow` | 阴影效果 | 对象 `{offsetX, offsetY, radius, color, fill, type}` 或枚举字符串。对象字段：`offsetX`（可选数值，X 偏移，默认 0vp）；`offsetY`（可选数值，Y 偏移，默认 0vp）；`radius`（**必选**数值 `[0, +∞)` vp）；`color`（可选，默认黑色）；`fill`（可选布尔，默认 `false`）；`type`（可选枚举 `color\|blur`，默认 `color`）。枚举值：`outerDefaultXS\|outerDefaultSM\|outerDefaultMD\|outerDefaultLG\|outerFloatingSM\|outerFloatingMD` | 否 | 是 | `"shadow": { "offsetX": 2, "offsetY": 2, "radius": 4, "color": "#66000000" }` |
| `layoutWeight` | 布局权重 | 数值，仅当父节点为 Row/Column 时生效，默认 1 | 否 | 是 | `"layoutWeight": 2` |
| `flexShrink` | 压缩比例 | 数值 `[0, 1]`，默认 1。父容器主轴空间不足时按比例压缩 | 否 | 是 | `"flexShrink": 1` |
| `visibility` | 是否可见 | 枚举字符串：`visible`（可见）、`hidden`（不可见但占位）、`none`（不可见也不占位） | 否 | 是 | `"visibility": "visible"` |
| `clip` | 是否根据父组件边界裁切 | 布尔值，默认 `false` | 否 | 是 | `"clip": true` |

**取值说明：**

- 尺寸数字默认是 vp。
- 字符串可使用可解析的数值单位，例如 `vp`、`fp`、`%`，以及文档允许时的 `px`；`width/height` 还支持 `matchParent`、`wrapContent`、`fixAtIdealSize`。卡片 root 使用 `matchParent`，普通组件优先使用数值，只有历史修复或宿主明确支持时才保留百分比或自适应枚举。
- `constraintSize` 必须同时写 `minWidth`、`maxWidth`、`minHeight`、`maxHeight`，用于约束动态文本、图片或弹性区域。
- `margin` / `padding` 可以是数字，也可以是 `{ "left": 0, "right": 0, "top": 0, "bottom": 0 }` 对象；数值仍按 vp 预算。
- `borderRadius`、`borderWidth` 可写数字或方向对象；卡片 root 必须使用单个数字 `18`，内部小背板等普通组件仍按预算使用其它合法圆角。
- `createSurface.width/height` 和 root `styles.width/height` 必须写 `"matchParent"`；普通组件的 `width/height` 必须保持数值或可静态推导的约束，并按 `2x2 = 160vp x 160vp`、`2x4 = 320vp x 160vp` 的实际预算规划。
- 颜色使用 `#RRGGBB` 或 `#AARRGGBB`。
- 卡片背景样式放在 root 组件的 `styles` 中；新卡片默认省略 `createSurface.styles`，只有宿主明确要求外层形状/裁切时才可写 `borderRadius`、`clip`。
- `linearGradient` 固定写成对象并包含 `colors`；常用写法为 `{"direction":"RightBottom","colors":[["#RRGGBB",0],["#RRGGBB",1]]}`；`colors` 是嵌套 stop 对数组，不写成扁平数组。
- `shadow` 只用于少量内容背板或按钮，`radius` 必填，不用于多层装饰。
- `visibility` 只用于必要的条件可见，不用它隐藏未完成设计；复杂条件优先预计算到 DataModel。

## 通用事件

组件如无特殊说明均支持以下通用事件。每个事件值为 EventHandler 数组，**Form 约束：每事件仅 1 个 handler**，不支持 `condition`、`as`、`$context`。

| 事件类型 | 适用组件 | 触发条件 | 事件上下文数据 |
|----------|----------|----------|----------------|
| `onClick` | 所有组件 | 用户点击组件 | 无 |

EventHandler 结构：

| 字段 | 必选 | 说明 |
|------|------|------|
| `call` | 是 | 调用函数名（预定义函数或扩展函数） |
| `args` | 否 | 执行函数时的参数，参数值可为静态值、表达式字符串 `"{{ ... }}"` 或嵌套对象 |

```json
{
  "onClick": [
    {
      "call": "clickToDeeplink",
      "args": {
        "bundleName": "com.huawei.hmos.settings",
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "uri": "battery"
      }
    }
  ]
}
```

---

## 展示组件

### Text

用于显示普通文本内容，支持字体、颜色、样式等设置。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `content` | string，默认值 `''` | **是** | 是 | 要显示的文本内容 |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `fontSize` | 字体大小 | 数字，单位 fp，默认 16fp | 否 | 是 | `"fontSize": 18` |
| `fontWeight` | 字体粗细 | 数字 `[100, 900]`，步长 100，默认 400 | 否 | 是 | `"fontWeight": 700` |
| `fontColor` | 字体颜色 | `#RRGGBB` 或 `#AARRGGBB` 字符串 | 否 | 是 | `"fontColor": "#333333"` |
| `textAlign` | 水平对齐 | 枚举：`start`（首部对齐）、`center`（居中）、`end`（尾部对齐）、`justify`（双端对齐）。默认 `start` | 否 | 是 | `"textAlign": "center"` |
| `maxLines` | 最大行数 | 数字 `[0, inf)`，默认不限制 | 否 | 是 | `"maxLines": 2` |
| `textOverflow` | 文本超长显示方式 | 枚举：`clip`（按最大行截断）、`ellipsis`（省略号代替）。默认 `clip`。需配合 `maxLines` 使用 | 否 | 是 | `"textOverflow": "ellipsis"` |
| `maxFontSize` | 文本最大显示大小 | 数字，单位 fp。需配合 `minFontSize` 及 `maxLines` 或布局大小限制使用，单独设置不生效。≤0 或 <minFontSize 时自适应不生效 | 否 | 是 | `"maxFontSize": 24` |
| `minFontSize` | 文本最小显示大小 | 数字，单位 fp。需配合 `maxFontSize` 及 `maxLines` 或布局大小限制使用，单独设置不生效。≤0 时自适应不生效 | 否 | 是 | `"minFontSize": 12` |

支持[通用事件](#通用事件)。

---

### Image

用于展示图片，支持本地或资源图片。不支持网络图片路径。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `src` | string | **是** | 是 | 图片数据源（素材库声明的本地 SVG/PNG 路径）；**不支持** base64 内联图片和网络 URL |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `objectFit` | 图片填充效果 | 枚举，默认 `cover`。取值：`fill`（拉伸填满）、`contain`（保持比例完整显示）、`cover`（保持比例裁切填满）、`auto`（适当缩放保持比例）、`none`（保持原有尺寸）、`scaleDown`（保持比例缩小或不变）、`topStart`/`top`/`topEnd`/`start`/`center`/`end`/`bottomStart`/`bottom`/`bottomEnd`（各对齐位置保持原有尺寸）、`matrix`（配合 imageMatrix 自定义位置） | 否 | 是 | `"objectFit": "contain"` |
| `fillColor` | 图片染色颜色 | SVG 可按设计需要使用；PNG 和其它位图通常省略 | 否 | 是 | `"fillColor": "#FFFF0000"` |

支持[通用事件](#通用事件)。

---

### Divider

分割线组件，用于在视觉上分隔不同内容区域。无组件特有顶层属性，所有可配置项均为样式。

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `strokeWidth` | 分割线宽度 | 数值或字符串，默认 1px。非法值按默认值处理。数值 `[0, inf)` 默认单位 vp | 否 | 是 | `"strokeWidth": 1` |
| `vertical` | 分割线方向 | 布尔值，默认 `false`（`false`=水平，`true`=垂直） | 否 | 是 | `"vertical": false` |
| `color` | 分割线颜色 | `#RRGGBB` 或 `#AARRGGBB` 字符串。默认：浅色模式 `#33000000`，深色模式 `#33FFFFFF` | 否 | 是 | `"color": "#E0E0E0"` |

支持[通用事件](#通用事件)。

---

### Progress

进度条组件，用于显示任务完成进度或加载状态。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `value` | number `[0, total]`，默认 0 | **是** | 是 | 当前进度值 |
| `total` | number `[0, 2147483647]`，负数按 100 处理 | 否 | 是 | 进度总长 |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `type` | 进度条类型 | 枚举，默认 `linear`。`linear`（线性）、`ring`（环形无刻度）、`eclipse`（圆形月相样式）、`scaleRing`（环形有刻度）、`capsule`（胶囊样式，高度>宽度时自适应垂直） | 否 | 是 | `"type": "ring"` |
| `color` | 进度条前景色 | `#RRGGBB` 或 `#AARRGGBB` 字符串（仅纯色，**不支持 LinearGradient 渐变**）。默认：浅色模式 `#FF0A59F7`，深色模式 `#FF317AF7` | 否 | 是 | `"color": "#007AFF"` |
| `strokeWidth` | 进度条宽度 | 数字，单位 vp，默认 4.0vp。仅 `linear`/`ring`/`scaleRing` 时生效；`eclipse`/`capsule` 不生效 | 否 | 是 | `"strokeWidth": 4` |

支持[通用事件](#通用事件)。

---

## 交互组件

### Button

按钮组件，响应用户点击操作，常用于触发事件。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `label` | string | **是** | 是 | 按钮中的文本 |
| `enabled` | boolean，默认 `true` | 否 | 是 | 按钮是否可点击 |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `fontColor` | 按钮文本颜色 | `#RRGGBB` 或 `#AARRGGBB` 字符串 | 否 | 是 | `"fontColor": "#FFAAFF"` |
| `fontSize` | 字体大小 | 数字，单位 fp，默认 16fp | 否 | 是 | `"fontSize": 16` |
| `fontWeight` | 字体粗细 | 数字（默认 500）或枚举：`lighter`(100)、`normal`(400)、`regular`(400)、`medium`(500)、`bold`(700)、`bolder`(900) | 否 | 是 | `"fontWeight": 600` |
| `maxFontSize` | 文本最大显示大小 | 数字，单位 fp。需配合 `minFontSize` 及 `maxLines` 或布局大小限制使用。≤0 或 <minFontSize 时自适应不生效 | 否 | 是 | `"maxFontSize": 20` |
| `minFontSize` | 文本最小显示大小 | 数字，单位 fp。需配合 `maxFontSize` 或布局大小限制使用。≤0 时自适应不生效 | 否 | 是 | `"minFontSize": 12` |

支持[通用事件](#通用事件)。

> CTA 文本是受保护内容，避免窄固定宽度和省略；可点击按钮必须有已声明的 `onClick` EventHandler，动作能力不明时删除点击行为，改为普通支撑信息。

---

### Checkbox

多选框组件，通常用于某选项的打开或关闭。只在用户明确要求切换状态时使用。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `label` | string，默认 `""` | 否 | 是 | 复选框旁的显示文本 |
| `value` | string，默认 `""` | 否 | 是 | 当前多选框的标识，不绘制显示 |
| `select` | boolean，默认 `false` | 否 | 是 | 多选框选中状态 |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `selectedColor` | 选中状态颜色 | `#RRGGBB` 或 `#AARRGGBB` 字符串 | 否 | 是 | `"selectedColor": "#FFAAFF"` |
| `shape` | 组件形状 | 枚举，默认 `circle`。`circle`（圆形）、`rounded_square`（圆角方形） | 否 | 是 | `"shape": "circle"` |

支持[通用事件](#通用事件)。

> 不要写已裁剪的 `group`、`unSelectedColor` 或 `mark`。如需点击行为，必须使用已声明 event capability；不要虚构切换函数。

---

## 布局组件

> **对齐原则：优先居中。** 卡片为小尺寸展示场景，布局对齐应优先使用 `center`（居中），避免 `start`/`end`（靠左/靠右）或 `top`/`bottom`（顶部/底部）等偏置对齐，除非用户明确要求边侧布局。居中布局在多种卡片尺寸下视觉更均衡。

以下组件支持通过 `children` 属性的模板模式动态生成子组件，模板机制概述参见 [`protocol.md`](protocol.md) 子组件模板章节。

### Column

垂直方向线性布局，将子组件沿垂直方向排列。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `children` | `string[]` 或 `{ componentId, path[, itemVar][, indexVar] }` | 否 | 否 | 子组件 ID 列表或模板对象 |
| `itemMargin` | number，默认 8vp | 否 | 是 | 纵向布局元素垂直方向间距。为负数或 `justifyContent` 为 `spaceBetween`/`spaceAround`/`spaceEvenly` 时不生效。非法值按默认值处理。单位 vp |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `justifyContent` | 垂直方向对齐格式 | 枚举，默认 `start`。`start`（首端对齐）、`center`（居中）、`end`（尾部对齐）、`spaceBetween`（均匀分布，首尾贴边）、`spaceAround`（均匀分布，首尾半间距）、`spaceEvenly`（均匀分布，间距全相等）。**卡片中推荐 `center`** | 否 | 是 | `"justifyContent": "center"` |
| `alignItems` | 水平方向对齐格式 | 枚举，默认 `start`。`start`（起始端）、`center`（居中）、`end`（尾端）。**卡片中推荐 `center`** | 否 | 是 | `"alignItems": "center"` |

支持[通用事件](#通用事件)。

---

### Row

水平方向线性布局，将子组件沿水平方向排列。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `children` | `string[]` 或 `{ componentId, path[, itemVar][, indexVar] }` | 否 | 否 | 子组件 ID 列表或模板对象 |
| `itemMargin` | number，默认 16vp | 否 | 是 | 横向布局元素水平方向间距。为负数或 `justifyContent` 为 `spaceBetween`/`spaceAround`/`spaceEvenly` 时不生效。非法值按默认值处理。单位 vp |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `justifyContent` | 水平方向对齐格式 | 枚举，默认 `start`。取值同 Column。**卡片中推荐 `center`** | 否 | 是 | `"justifyContent": "center"` |
| `alignItems` | 垂直方向对齐格式 | 枚举，默认 `center`。`top`（顶部对齐）、`center`（居中）、`bottom`（底部对齐）。**卡片中推荐 `center`** | 否 | 是 | `"alignItems": "center"` |

支持[通用事件](#通用事件)。

> 不写已裁剪的 `wrap`。

---

### List

列表组件，高效展示滚动列表项，支持大量数据。桌面卡片中谨慎使用。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `children` | `string[]` 或 `{ componentId, path[, itemVar][, indexVar] }` | 否 | 否 | 子组件 ID 列表或模板对象 |
| `space` | number，默认 0 | 否 | 是 | 子组件主轴方向间隔，单位 vp。负数或 ≥List 内容区长度时按默认值。space 小于分割线宽度时取分割线宽度。子组件 visibility=None 时 space 仍生效 |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `listDirection` | 列表排列方向 | 枚举，默认 `vertical`。`vertical`（纵向）、`horizontal`（横向） | 否 | 是 | `"listDirection": "vertical"` |
| `scrollBar` | 滚动条状态 | 枚举，默认 `auto`。`off`（不显示）、`auto`（按需显示，触摸后 2s 消失）、`on`（常驻显示） | 否 | 是 | `"scrollBar": "auto"` |

支持[通用事件](#通用事件)。

> 不要写已裁剪的 `nestedScroll`。列表只展示短数组摘要，长列表改为下一项、当前项或 `+N`。

---

### Stack

堆叠布局，子组件按顺序叠放，后添加的在上层。

**属性**

| 属性 | 类型 | 必选 | 支持动态数据类型 | 说明 |
|------|------|------|------|------|
| `children` | `string[]` | 否 | 否 | 子组件 ID 列表。**不支持模板循环** |

**样式**

| 样式名 | 说明 | 类型 | 必选 | 支持动态数据类型 | 使用示例 |
|--------|------|------|------|------|----------|
| `alignContent` | 子组件对齐方式 | 枚举，默认 `center`。`topStart`（顶部起始端）、`top`（顶部横向居中）、`topEnd`（顶部尾端）、`start`（起始端纵向居中）、`center`（横向纵向居中）、`end`（尾端纵向居中）、`bottomStart`（底部起始端）、`bottom`（底部横向居中）、`bottomEnd`（底部尾端） | 否 | 是 | `"alignContent": "center"` |

支持[通用事件](#通用事件)。

---

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
- `Image.src` 和 `styles.backgroundImage` 只使用用户提供或素材库声明的本地 SVG/PNG 路径；不支持网络 URL、内联/base64 图片或占位图；没有真实资源时省略 `Image`。
- `backgroundColor`、`linearGradient`、`backgroundImage` 等卡片背景字段写在 root 组件或 root 下真实背景组件，不写进 `createSurface.styles`。
- `Button`：CTA 文本是受保护内容，避免窄固定宽度和省略；可点击按钮必须有已声明的 `onClick` EventHandler，动作能力不明时删除点击行为。
- `Checkbox`：如需点击行为，必须使用已声明 event capability；不要虚构 `toggleTodo` 一类切换函数。
- `List`：除非用户请求确实需要重复项，否则优先使用静态紧凑行。
