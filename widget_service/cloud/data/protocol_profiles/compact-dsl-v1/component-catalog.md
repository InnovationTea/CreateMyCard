# Compact DSL Form 组件目录

本文是 `a2ui-form-rom6.0-v1` 组件目录的 Compact DSL 等价版本。组件语义、适用场景、
视觉属性和限制不变，只把 A2UI 组件对象改写为 tuple 行，并把 `styles` 平铺到 props；不要输出
`style` 或 `styles` 包装层。

## 支持范围

- 必需 catalog：`"catalogId": "ohos.genui.compact.catalog"`。
- 允许组件：`Text`、`Image`、`Divider`、`Progress`、`Button`、`Checkbox`、`Row`、`Column`、`List`、`Stack`。
- 禁用组件：`TextInput`、`Toggle`、`Radio`、`CheckboxGroup`、`Select`、`NavContainer`、
  `Tabs`、`TabContent`、`Web`、`Grid`、`If`。
- 不把通用 Compact DSL catalog 的额外组件或交互能力混入 Form 卡片。

## 字段映射

| A2UI Form | Compact DSL |
| --- | --- |
| `id`、`component` | tuple 第 1、2 段 |
| 顶层语义字段 | tuple 第 3 段 props 的同名字段 |
| `styles.xxx` | tuple 第 3 段 props 的 `xxx` |
| `children` | 容器 tuple 第 4 段 |
| `Row.itemMargin` / `Column.itemMargin` | `space` |
| `List.space` | `space` |
| `Button.onClick[0]` | `Button.action.functionCall` |
| 完整 DataModel 表达式 | `{"path":"/..."}` 加数据行 |

- 普通 children 只写组件 id 字符串数组；Compact DSL v1 不输出模板 children 对象。
- A2UI 的结构和样式字段在 Compact props 中处于同一层，但字段含义和取值范围不变。
- 展示值只用字面量或 path 绑定，不使用 `{{ ... }}`、`formatString` 或路径文本拼接。

## 组件速查

- `Column`：竖向容器；必须有 children；`space` 为数字 vp；`justifyContent` 取
  `start|center|end|spaceAround|spaceBetween|spaceEvenly`；`alignItems` 取
  `start|center|end`。
- `Row`：横向容器；必须有 children；`space` 为数字 vp；`wrap` 取 `noWrap|wrap`；
  `justifyContent` 取 `start|center|end|spaceAround|spaceBetween|spaceEvenly`；
  `alignItems` 取 `top|center|bottom`。
- `Stack`：层叠容器，用于图片背景、叠加内容和进度环；必须有 children；
  `alignContent` 取 `topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd`。
- `Text`：文本展示；必须有 `content`；`fontSize` 为数字 fp；`fontWeight` 为
  `100..900`；`fontColor` 取 `#RRGGBB` 或 `#AARRGGBB`；`maxLines`、`minFontSize`、
  `maxFontSize` 为数字；`textOverflow` 取 `none|clip|ellipsis|marquee`；`textAlign` 取
  `start|center|end|justify`；`wordBreak` 取 `normal|breakAll|breakWord|hyphenation`。
  生成的受保护文本必须在 `width × maxLines` 内完整显示，不使用 `ellipsis`、`clip` 或
  `marquee` 隐藏内容。
- `Image`：图片展示；必须有 `src` 和明确的数字宽高；默认使用 `objectFit:contain`，只有明确
  需要裁剪时才使用其它值；`objectFit` 取
  `fill|contain|cover|auto|none|scaleDown|topStart|top|topEnd|start|center|end|bottomStart|bottom|bottomEnd|matrix`；
  `aspectRatio` 为数字。
- `Divider`：分隔线；无额外必需字段；`strokeWidth` 为数字或带单位字符串，
  `vertical` 为 boolean，`color` 为颜色字符串。
- `Progress`：进度条或进度环；必须有 `value` 和 `total`，可为数字或 path 绑定；
  `type` 取 `linear|ring|eclipse|scaleRing|capsule`；`color` 为颜色或 path 绑定。
- `Button`：语义按钮；必须有非空 `label`；`enabled` 可为 boolean 或 path 绑定；
  需要点击时使用与 event candidate 完全匹配的 `action.functionCall`；`fontWeight` 为数字或
  `normal|regular|medium|bold|bolder`。明确设置高度时不得小于 `24`，明确设置宽度时必须能
  完整容纳 label 和总计 `16` 的左右安全空间。
- `Checkbox`：只在用户明确要求切换状态时使用；无固定额外必需字段；`label`、`value`、
  `group` 可为字符串或 path 绑定；`select` 可为 boolean 或 path 绑定；`selectedColor`、
  `unSelectedColor` 为颜色；`shape` 取 `circle|rounded_square`；`mark` 为
  `{strokeColor,size,strokeWidth}`。
- `List`：重复项列表，桌面卡片中谨慎使用；必须有静态 children；`space` 为数字；
  `listDirection` 取 `vertical|horizontal`；`scrollBar` 取 `off|auto|on`；默认避免嵌套滚动。

## 通用视觉属性

所有允许组件均沿用 Form 通用视觉属性，并直接写在 props：

- 尺寸与约束：`width`、`height`、`constraintSize`
- 间距与形状：`margin`、`padding`、`borderRadius`
- 边框与表面：`borderWidth`、`borderColor`、`backgroundColor`、`backgroundImage`、
  `backgroundImageSizeWithStyle`、`linearGradient`
- 布局与效果：`layoutWeight`、`flexShrink`、`shadow`、`visibility`、`clip`

取值说明：

- 尺寸数字默认是 vp；字符串只在需要单位时使用 `vp`、`fp`、`%` 或允许的 `px`。
- 颜色使用 `#RRGGBB` 或 `#AARRGGBB`。
- 字体必须使用工具3的阶梯：`10、12、14、16、18、20、32、40`。
- padding、margin 和 space 使用工具3的阶梯：`0、2、4、6、8、10、12、14、16`；
  超出阶梯作为排版风险提示。
- 卡片背景放在 root props；2x2 root 默认 `borderRadius:18`、`clip:true`、`padding:12`，
  2x4 root 默认 `borderRadius:22`、`clip:true`、`padding:12`。
- root 为 Column 时，末段底部空隙通常保持 `8-14`，不得超过 `16`。
- `linearGradient` 必须包含 `direction` 与嵌套 stop 对数组 `colors`，例如
  `{"direction":"RightBottom","colors":[["#RRGGBB",0],["#RRGGBB",1]]}`。

## 最小写法

以下示例只说明字段位置，不是新的视觉模板：

```text
["root","Column",{"width":"matchParent","height":140,"padding":12,"borderRadius":18,"clip":true,"space":8,"linearGradient":{"direction":"RightBottom","colors":[["#FF3B4A54",0],["#FF202326",1]]}},["row"]]
["row","Row",{"width":116,"justifyContent":"spaceBetween","alignItems":"center","space":8},["title","action"]]
["title","Text",{"content":{"path":"/title"},"fontSize":16,"fontWeight":700,"fontColor":"#FFFFFFFF","maxLines":1}]
["/title","日程提醒"]
["action","Button",{"label":"打开","enabled":true,"action":{"functionCall":{"call":"clickToDeeplink","args":{"uri":"..."}}}}]
```

## 特殊规则

- `Image.src` 和 `backgroundImage` 只使用用户提供或素材库声明的本地资源路径；不支持网络
  URL、内联/base64 SVG、未声明 SVG 或占位图；没有真实资源时省略 `Image`。
- CTA 文本是受保护内容，避免窄固定宽度和省略；动作能力不明时删除点击行为。
- `Checkbox` 不自动引入通用 Compact 表单提交语义，也不虚构切换函数。
- `List` 仅在用户请求确实需要重复项时使用；2x2/2x4 卡片优先使用紧凑静态行。
