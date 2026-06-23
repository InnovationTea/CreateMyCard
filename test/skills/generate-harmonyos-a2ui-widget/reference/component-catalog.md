# 桌面卡片组件目录

这是本地 GenUI extended 组件参考的精简子集。用于卡片生成；只有当某个组件此处未覆盖时，才加载完整本地文档。

## 必需 Catalog

使用：

```json
"catalogId": "ohos.a2ui.extended.catalog"
```

不要把 Basic Catalog 的属性名混入这个 surface。

## 高频组件

### Column

竖向容器。

```json
{"id":"col","component":"Column","children":["a","b"],"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"start"}
```

- `children`：字符串数组或 `{ "componentId": "...", "path": "/items" }`
- `itemMargin`：数字，vp
- `justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`
- `alignItems`：`start|center|end`

### Row

横向容器。

```json
{"id":"row","component":"Row","children":["a","b"],"itemMargin":8,"justifyContent":"spaceBetween","alignItems":"center"}
```

- `children`：字符串数组或重复项绑定对象
- `itemMargin`：数字，vp
- `justifyContent`：`start|center|end|spaceAround|spaceBetween|spaceEvenly`
- `alignItems`：`top|center|bottom`
- `wrap`：`noWrap|wrap`

### Stack

层叠容器。用于光晕、图片背景、叠加内容、进度环。

```json
{"id":"stack","component":"Stack","children":["bg","content"],"alignContent":"center"}
```

- `children`：字符串数组
- `alignContent`：`topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`

### Text

文本展示。必需字段是 `content`。

```json
{"id":"title","component":"Text","content":{"path":"/title"},"styles":{"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1,"textOverflow":"none"}}
```

常用样式：

- `fontSize`：数字，fp
- `fontWeight`：`Text` 使用数字 `100..900`
- `fontColor`：`#RRGGBB` 或 `#AARRGGBB`
- `maxLines`：数字
- `minFontSize`、`maxFontSize`：数字
- `textOverflow`：`none|clip|ellipsis|marquee`
- `textAlign`：`start|center|end|justify`
- `wordBreak`：`normal|breakAll|breakWord|hyphenation`

### Image

图片展示。必需字段是 `src`。

```json
{"id":"img","component":"Image","src":{"path":"/asset/image"},"styles":{"width":"100%","height":"100%","objectFit":"cover"}}
```

常用样式：

- `objectFit`：`fill|contain|cover|auto|none|scaleDown|topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd|matrix`
- `aspectRatio`：数字

### Divider

分隔线。Extended 属性位于 `styles`。

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

- `value`：数字或绑定
- `total`：数字或绑定
- `styles.type`：`linear|ring|eclipse|scaleRing|capsule`
- `styles.color`：颜色字符串

### Button

语义按钮。使用 `label`，不要使用 child text。

```json
{"id":"btn","component":"Button","label":"打开","action":{"event":{"name":"openDetail"}}}
```

- `label`：字符串或绑定
- `enabled`：boolean 或绑定
- `action`：`{ "event": { "name": "...", "context": {...} } }` 或 `{ "functionCall": { "call": "...", "args": {...} } }`
- `styles.fontWeight`：数字或 `normal|regular|medium|bold|bolder`
- 如果同时存在 `action` 和 `onClick`，`action` 优先。

### If

条件虚拟节点。

```json
{"id":"adaptive","component":"If","condition":"{{ $__widthBreakpoint == 'sm' }}","childrenIf":["narrow"],"childrenElse":["wide"]}
```

- `condition`：完整 `{{ ... }}` 表达式
- `childrenIf` / `childrenElse`：字符串数组
- 不要给 `If` 设置 styles 或 accessibility。

### List 和 Grid

桌面卡片中谨慎使用。除非用户请求确实需要重复项，否则优先使用静态紧凑行。

List：

```json
{"id":"list","component":"List","children":{"componentId":"itemTpl","path":"/items"},"space":6,"listDirection":"vertical","scrollBar":"off"}
```

Grid：

```json
{"id":"grid","component":"Grid","children":["a","b"],"columnsTemplate":"1fr 1fr","columnsGap":8,"rowsGap":8}
```

## 通用样式

除虚拟 `If` 外，所有 extended 组件都支持通用 `styles`：

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
- 颜色使用 `#RRGGBB` 或 `#AARRGGBB`。GenUI 将 `#RRGGBB` 的 alpha 视为不透明。
- `linearGradient.colors` 可使用 `["#RRGGBB", stop]` 对。

## 支持的组件名

Extended catalog 包含：

`Text`、`Image`、`Divider`、`Progress`、`Button`、`TextInput`、`Select`、`Toggle`、`Radio`、`Checkbox`、`CheckboxGroup`、`Row`、`Column`、`List`、`Stack`、`Grid`、`Tabs`、`TabContent`、`Navigation`/`NavContainer`、`Web`、`If`。

桌面卡片默认使用上面的高频子集。
