# Form 组件目录

这是卡片生成使用的 Form 组件子集。组件与属性规则以本文档和 [`protocol.md`](protocol.md) 为准。

## 必需 Catalog

使用：

```json
"catalogId": "ohos.a2ui.extended.catalog"
```

不要把 Form 子集之外的 extended 组件或 Basic Catalog 的属性名混入 Form surface。

## 支持组件

Form 支持 10 个扩展组件：

`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`

不要使用 `TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、`Tabs`、`TabContent`、`Web`、`Grid`、`If`。

## 高频组件

### Column

竖向容器。

```json
{"id":"col","component":"Column","children":["a","b"],"itemMargin":8,"styles":{"justifyContent":"spaceBetween","alignItems":"start"}}
```

- `children`：字符串数组或 `{ "componentId": "...", "path": "/items" }`
- `itemMargin`：数字，vp
- `styles.justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`
- `styles.alignItems`：`start|center|end`

### Row

横向容器。

```json
{"id":"row","component":"Row","children":["a","b"],"itemMargin":8,"wrap":"noWrap","styles":{"justifyContent":"spaceBetween","alignItems":"center"}}
```

- `children`：字符串数组或模板循环对象
- `itemMargin`：数字，vp
- `wrap`：`noWrap|wrap`
- `styles.justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`
- `styles.alignItems`：`top|center|bottom`

### Stack

层叠容器。用于光晕、图片背景、叠加内容、进度环。

```json
{"id":"stack","component":"Stack","children":["bg","content"],"styles":{"alignContent":"center"}}
```

- `children`：字符串数组
- `styles.alignContent`：`topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`

### Text

文本展示。必需字段是 `content`。

```json
{"id":"title","component":"Text","content":{"path":"/title"},"styles":{"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"none"}}
```

常用样式：

- `fontSize`：数字，fp
- `fontWeight`：数字 `100..900`
- `fontColor`：`#RRGGBB` 或 `#AARRGGBB`
- `maxLines`：数字
- `minFontSize`、`maxFontSize`：数字
- `textOverflow`：`none|clip|ellipsis|marquee`
- `textAlign`：`start|center|end|justify`
- `wordBreak`：`normal|breakAll|breakWord|hyphenation`
- `decoration`：文本装饰对象

### Image

图片展示。必需字段是 `src`。

```json
{"id":"img","component":"Image","src":{"path":"/asset/image"},"styles":{"width":"100%","height":"100%","objectFit":"cover"}}
```

规则：

- `src` 只使用本地/资源路径，不支持网络 URL。
- 不支持 SVG，包括 base64 SVG。
- 没有真实资源时省略 `Image`。

常用样式：

- `objectFit`：`fill|contain|cover|auto|none|scaleDown|topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd|matrix`
- `aspectRatio`：数字

### Divider

分隔线。属性位于 `styles`。

```json
{"id":"line","component":"Divider","styles":{"vertical":true,"strokeWidth":3,"color":"#73FFFFFF","height":28}}
```

样式：

- `strokeWidth`：数字或带单位字符串
- `vertical`：boolean
- `color`：颜色字符串

### Progress

进度条/进度环。

```json
{"id":"progress","component":"Progress","value":{"path":"/progress/value"},"total":{"path":"/progress/total"},"styles":{"type":"ring","color":"#A77DFF","width":72,"height":72}}
```

- `value`：数字或 `{"path":"/..."}`
- `total`：数字或 `{"path":"/..."}`，必选
- `styles.type`：`linear|ring|eclipse|scaleRing|capsule`
- `styles.color`：颜色字符串

### Button

语义按钮。使用 `label` 和 `onClick`，不要使用 `Button.action`。

```json
{"id":"btn","component":"Button","label":{"path":"/action/label"},"onClick":[{"call":"openDetail","args":{"targetId":{"path":"/action/targetId"}}}]}
```

- `label`：字符串、`{"path":"/..."}` 或 `formatString`
- `enabled`：boolean 或 `{"path":"/..."}`
- `onClick`：EventHandler 数组
- `styles.fontWeight`：数字或 `normal|regular|medium|bold|bolder`
- CTA 文本是受保护内容，避免窄固定宽度和省略。

### Checkbox

多选框。服务卡片中谨慎使用，通常只在用户明确要求切换状态时使用。

```json
{"id":"done","component":"Checkbox","label":{"path":"/todo/label"},"select":{"path":"/todo/done"},"onClick":[{"call":"toggleTodo","args":{"id":{"path":"/todo/id"}}}]}
```

- `label`：字符串、`{"path":"/..."}` 或 `formatString`
- `value`：字符串或 `{"path":"/..."}`
- `group`：字符串或 `{"path":"/..."}`
- `select`：boolean 或 `{"path":"/..."}`
- `styles.selectedColor` / `styles.unSelectedColor`：颜色字符串
- `styles.shape`：`circle|rounded_square`
- `styles.mark`：`{ strokeColor, size, strokeWidth }`

### List

桌面卡片中谨慎使用。除非用户请求确实需要重复项，否则优先使用静态紧凑行。

```json
{"id":"list","component":"List","children":{"componentId":"itemTpl","path":"/items"},"space":6,"styles":{"listDirection":"vertical","scrollBar":"off"}}
```

- `children`：字符串数组或模板循环对象
- `space`：数字
- `styles.listDirection`：`vertical|horizontal`
- `styles.scrollBar`：`off|auto|on`
- `styles.nestedScroll`：按协议枚举使用；卡片默认避免嵌套滚动

## 通用样式

所有 Form 组件都支持通用 `styles`：

- `width`、`height`
- `constraintSize`
- `margin`、`padding`
- `borderRadius`
- `borderWidth`、`borderColor`
- `backgroundColor`
- `backgroundImage`、`backgroundImageSizeWithStyle`
- `linearGradient`
- `layoutWeight`、`flexShrink`
- `shadow`
- `visibility`
- `clip` boolean

取值说明：

- 尺寸数字默认是 vp。
- 字符串可使用 `vp`、`fp`、`%`，以及文档允许时的 `px`。
- 颜色使用 `#RRGGBB` 或 `#AARRGGBB`。
- `backgroundImage` 只使用本地/资源路径，不支持网络 URL。
- `linearGradient.colors` 使用 `["#RRGGBB", stop]` 对。
