# HarmonyOS A2UI 组件生成规范

> 面向 Skill 运行时的大模型组件生成手册，只保留可直接写入 A2UI DSL 的样式与状态规则。

## 1. 生成原则

- normal 静态样式必须写入 DSL。
- selected / checked / isOn / tabIndex / selected / value 这类业务状态必须保留。
- 本生成版只收录可直接写入 DSL 的 normal 静态样式和业务状态字段。
- 未在本文出现的状态/字段，不作为生成依据。
- `action.event` / `action.functionCall` 只在用户明确需要业务交互时生成。
- A2UI 字段必须能在 `reference/protocol/extended-ui-schema.md` 找到；如果鸿蒙规格需要但协议未列出，标为 Gap / 协议待确认，不伪造字段。
- 标注为“待 UX 确认 / 规范留空 / Gap / 协议待确认”的字段仅用于人工审阅，不得直接生成到 NDJSON。

## 1.1 样式属性可变性

生成时按三层读取每个组件：

| 层级 | 生成含义 | 约束 |
|---|---|---|
| 组件的基本元素 | 判断组件由哪些必选/可选元素构成，例如文本、图片、图标、左/中/右区域、children | 可选元素必须由输入数据、业务意图或场景规范触发 |
| 可变属性的可选样式 | 从本文已收敛的子样式、尺寸枚举、颜色语义、字号/字重组合、业务状态中选择；品牌色 overlay 另按下节处理 | 非品牌色可变项已收敛到本文；未在本文列出的组件变体不开放额外样式变化，只能使用本文已定稿的固定矩阵 |
| 不可变属性的默认样式 | 已定稿的高度、padding、圆角、字号、字重、普通文本色、普通背景色等 | 按矩阵固定写入，不随输入自由变化 |

来源口径：卡片场景的结构选择、Card_Name 条件、列表 / 宫格样式、卡片内 Button / Tag / 图标背板 / Arrow Trailing / 图片比例 / 视频比例，已收敛到本文；生成时以本文为准。token 最终值以 `reference/design/harmony-design-token.md` 为准。

执行顺序：

1. 先确定组件基本元素和组合结构。
2. 再选择允许的可变样式，例如子样式、业务状态、图片比例或品牌 token overlay。
3. 最后写入不可变默认样式值。

不要把“可变”理解为任意 CSS；未出现在本文或 `harmony-design-token.md` 的样式值不生成。

## 1.2 品牌色覆盖

默认情况下，本文所有颜色值都是固定规范值。只有存在可靠品牌色来源时，才允许整体覆盖品牌语义 Token 族。

可靠品牌色来源包括：

- 输入显式提供 `brandColor` / `brandToken` 等可用色值。
- 输入可推理出明确品牌主体，且 Skill / 工程上下文提供对应品牌色映射表。

若只能识别品牌主体但没有可靠色值，不凭常识编写 hex，继续使用默认 Harmony 品牌 Token 或标记品牌色缺失。

| 可覆盖 Token | 影响范围 |
|---|---|
| `brand` / `brand100` / `brand60` / `brand40` / `brand20` / `brand10` | 品牌基础色及透明度阶梯 |
| `brand_font` | Dark 模式强调文本/图标可读色 |
| `font_emphasize` / `icon_emphasize` / `icon_sub_emphasize` | 品牌强调文本、图标、链接、选中图标 |
| `background_emphasize` / `comp_background_emphasize` | 强调按钮、进度前景、选中背景、active 背景 |
| `comp_emphasize_secondary` / `comp_emphasize_tertiary` | 品牌弱背景 |
| `interactive_focus` / `interctive_select` | 焦点描边、选择态叠加 |

生成要求：

- 必须作为一组品牌 token overlay 生效，不允许只改某个组件或某个字段。
- 未绑定品牌语义 Token 的颜色不随品牌色变化。
- Dark 模式强调文本/图标应使用可读的品牌文字色；无法可靠派生 `brand_font` 时保留 `reference/design/harmony-design-token.md` 默认值，不要直接套用不可读的背景品牌色。

## 3. 交互口径（简）

- 本文聚焦样式与结构，不展开事件清单、触发条件和事件载荷。
- 组件交互仅在业务明确需要时配置 `action.event` / `action.functionCall`。
- 不为补齐交互而新增协议未定义事件。

## 4. 公共样式字段

| 字段 | 用途 |
|---|---|
| `width` / `height` / `constraintSize` | 尺寸 |
| `padding` / `margin` / `space` | 间距 |
| `backgroundColor` | 背景 |
| `borderRadius` | 圆角 |
| `borderWidth` / `borderColor` | 描边 |
| `flexShrink` | 布局压缩 |
| `layoutWeight` | 剩余空间 |
| `clip` | 裁切 |

默认不生成：`shadow` / `backgroundImage` / `visibility` / `fontScaleMode` / `minFontScale` / `maxFontScale` / `maxFontSize`。**例外：** `SKILL.md` 的 **Mode A 媒体审计** 或 **Thematic imagery** 要求时，允许在容器 `styles` 中使用 `backgroundImage`（或配合 `Extended.Image`），且须遵守 `extended-ui-schema.md` 的单层背景等约束。`wordBreak` / `decoration` 只在 source 组件映射或输入明确需要时生成。

---

# B1 · Button

**A2UI 原语：** `Extended.Button`
**属性：** `label` / `enabled`
**交互（简）：** 按业务需要配置 `action.event` / `action.functionCall`（常见点击）。

## 生成约束

- 基本元素：`label` 必选；`enabled` 和 `action.event` / `action.functionCall` 按业务需要生成。
- 非品牌色可变项：卡片场景只采用本文已收敛的两类按钮选择：列表项右侧用小按钮；宫格样式 3 图文+Button 用普通按钮。
- 固定样式：每个子样式的高度、padding、圆角、字号、字重、默认背景/文字色按下表固定；不因 query 自由变化。
- 品牌色：仅绑定品牌语义 Token 的字段可按品牌色 overlay 整组替换。
- Gap：Button 文本色字段见协议待确认；不写不存在的 `loading` 字段。

## normal / selected 属性矩阵

| 子样式 | height | width | padding | backgroundColor Light | backgroundColor Dark | borderRadius Light | borderRadius Dark | fontSize | fontWeight | textAlign | fontColor Light | fontColor Dark | iconSize | iconColor Light | iconColor Dark | 业务态 / 备注 |
|---|---:|---|---|---|---|---:|---:|---:|---:|---|---|---|---:|---|---|---|
| 普通按钮 | 40 | Max-448 | `{left:16,right:16,top:8,bottom:8}` | `#0C000000` | `#19FFFFFF` | 20 | 20 | 16 | 500 | center | `#FF0A59F7` | `#FF5291FF` | - | - | - | Button 文本色字段见 Gap |
| 强调按钮 | 40 | Max-448 | `{left:16,right:16,top:8,bottom:8}` | `#FF0A59F7` | 规范留空 | 20 | 20 | 16 | 500 | center | `#FFFFFFFF` | `#FFFFFFFF` | - | - | - | Button 文本色字段见 Gap |
| 警告按钮 | 40 | Max-448 | `{left:16,right:16,top:8,bottom:8}` | `#0C000000` | `#19FFFFFF` | 20 | 20 | 16 | 500 | center | `#E84026` | `#D94838` | - | - | - | Button 文本色字段见 Gap |
| 文本按钮 | 40 | Max-448 | `{left:16,right:16,top:8,bottom:8}` | 无 | 无 | 20 | 20 | 16 | 500 | center | `#FF0A59F7` | `#FF5291FF` | - | - | - | Button 文本色字段见 Gap |
| 小按钮 | 28 | Max-448 | `{left:8,right:8,top:4,bottom:4}` | `#0C000000` | `#19FFFFFF` | 14 | 20 | 14 | 500 | center | `#FF0A59F7` | `#FF5291FF` | - | - | - | Dark 圆角待 UX 确认；Button 文本色字段见 Gap |
| 图标按钮 normal | 48 | 48 | `{left:12,right:12,top:12,bottom:12}` | `#0C000000` | `#19FFFFFF` | 圆形 | 圆形 | - | - | - | - | - | 24 | `#E5000000` | `#E5FFFFFF` | - |
| 图标按钮 selected | 48 | 48 | `{left:12,right:12,top:12,bottom:12}` | `#FF0A59F7` | 规范留空 | 圆形 | 圆形 | - | - | - | - | - | 24 | 规范留空 | 规范留空 | `selected` |

## A2UI 映射

| 鸿蒙规格 | A2UI 字段 |
|---|---|
| 字号 | `fontSize` |
| 字重 | `fontWeight` |
| 容器色 | `backgroundColor` |
| 圆角 | `borderRadius` |
| 尺寸 | `width` / `height` |
| 内边距 | `padding` |
| 业务禁用 | `enabled` |

**Gap：** Button 文本色 `fontColor` 协议待确认；Button 无内置 `loading` 字段。

---

# B2 · Select

**A2UI 原语：** `Extended.Select`
**属性：** `options` / `selected` / `value`
**交互（简）：** 按业务需要配置 `action.event` / `action.functionCall`（选择变化等）。

## 生成约束

- 基本元素：`options`、`selected`、`value` 来自输入数据或数据绑定。
- 非品牌色可变项：无额外卡片场景样式；除选中值外不开放额外样式变化。
- 固定样式：普通 / 小尺寸选择按钮的尺寸、padding、圆角、字号、图标尺寸和颜色按下表固定。
- 品牌色：仅 focus 等品牌语义 Token 可按 overlay 规则替换。

## 容器矩阵

| 子样式 | height | constraintSize.minWidth | paddingTop | paddingBottom | backgroundColor Light | backgroundColor Dark | borderRadius |
|---|---:|---:|---:|---:|---|---|---:|
| 普通选择按钮 | 40 | 68 | 8 | 8 | `#0C000000` | `#19FFFFFF` | 20 |
| 小尺寸选择按钮 | 28 | 56 | - | - | `#0C000000` | `#19FFFFFF` | 14 |

## 文本矩阵

| 子样式 | font.size Light | font.size Dark | font.weight | fontColor Light | fontColor Dark | textAlign | paddingLeft | paddingRight | paddingTop | paddingBottom | textIconSpace Light | textIconSpace Dark |
|---|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 普通选择按钮 | 16 | 16 | 500 | `#E5000000` | `#E5FFFFFF` | left | 16 | - | - | - | 2 | 8 |
| 小尺寸选择按钮 | 14 | 12 | 500 | `#E5000000` | `#E5FFFFFF` | left | - | 12 | 4 | 4 | 8 | 8 |

## 图标矩阵

| 子样式 | width | height | iconColor Light | iconColor Dark | paddingTop | paddingRight | paddingBottom |
|---|---:|---:|---|---|---:|---:|---:|
| 普通选择按钮 | 24 | 24 | `#E5000000` | `#E5FFFFFF` | 8 | 8 | 8 |
| 小尺寸选择按钮 | 24 | 24 | `#E5000000` | `#E5FFFFFF` | 4 | 12 | 4 |

## A2UI 映射

`font.size` / `font.weight` / `fontColor` / `backgroundColor` / `borderRadius` / `height` / `width` / `padding` / `selectedOptionBgColor` / `selectedOptionFontColor` / `optionBgColor` / `optionFontColor` / `menuBackgroundColor` / `optionWidth` / `optionHeight` / `space` / `arrowPosition`

---

# B3 · Text

**A2UI 原语：** `Extended.Text`
**属性：** `content`
**交互（简）：** 默认用于展示，按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：`content` 来自输入数据或数据绑定。
- 非品牌色可变项：卡片文本层级只从本文已收敛层级选择，例如列表第一行、第二/三行、宫格标题/辅助文本、宫格样式 3 文本。
- 固定样式：字号、字重、颜色必须来自本文矩阵、`harmony-design-token.md` 或本文明确层级；不自由组合新文本层级。
- 品牌色：普通文本层级不随品牌色变化；只有绑定品牌语义 Token 的强调文本可 overlay。
- Gap：不写不存在的 `lineHeight`。

## normal 矩阵

| fontSize | fontWeight | fontColor Light | fontColor Dark | textAlign | font_word_space | font_image_margin_vertical | lineHeightSource | 备注 |
|---:|---:|---|---|---|---:|---|---|---|
| 16 | 400 | `#E5000000` (`font_primary`) | `#99FFFFFF` (`font_secondary`) | start | 0 | 8vp | 1.1 | 生成时按信息层级选择 `font_primary` / `font_secondary` / `font_tertiary` / `font_fourth`；A2UI 无原生 `lineHeight` |

## A2UI 映射

`fontSize` / `fontColor` / `fontWeight` / `textAlign` / `textOverflow` / `maxLines` / `decoration` / `wordBreak` / `backgroundColor` / `borderRadius` / `borderWidth` / `borderColor` / `width` / `height` / `padding`

**Gap：** `lineHeight` / 字间距。

---

# B4 · Divider

**A2UI 原语：** `Extended.Divider`
**交互（简）：** 通常不绑交互；仅在业务需要时配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：分隔条或分隔线，仅在布局需要分隔时生成。
- 非品牌色可变项：无额外卡片场景样式；只能选 Splitters / Divider。
- 固定样式：strokeWidth 和颜色按下表固定。
- 品牌色：无品牌色覆盖。

| 子样式 | strokeWidth | color Light | color Dark | vertical |
|---|---:|---|---|---|
| Splitters 分隔条 | 8 | `#0C000000` | `#19FFFFFF` | 按场景 |
| Divider 分割线 | 1 | `#33000000` | `#33FFFFFF` | 按场景 |

## A2UI 映射

`strokeWidth` / `color` / `vertical` / `width` / `margin` / `padding`

---

# B5 · Progress

**A2UI 原语：** `Extended.Progress`
**属性：** `value` / `total`
**交互（简）：** 进度变化由数据模型驱动；按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：`value` / `total` 来自业务数据；LoadingProgress 可无明确进度值。
- 非品牌色可变项：无额外卡片场景样式；除进度数值外不开放额外样式变化。
- 固定样式：类型、容器、轨道、圆角和颜色按下表固定；Dark 留空处不补值。
- 品牌色：进度前景等品牌语义 Token 可按 overlay 规则替换。
- Gap：独立轨道色和 LoadingProgress 精确对应见 Gap。

| 子样式 | type | containerHeight | containerSize Light | containerSize Dark | trackHeight | trackRadius | trackColor Light | trackColor Dark | progressColor Light | progressColor Dark | partSize | 备注 |
|---|---|---:|---:|---|---:|---:|---|---|---|---|---|---|
| LinearProgress | linear | 24 | - | - | 4 | 2 | `#19000000` | 规范留空 | `#FF0A59F7` | `#FF317AF7` | - | Dark 轨道色不臆造 |
| Eclipse Progress | eclipse | - | 24 | 规范留空 | - | - | - | - | - | - | `20x20`; 色 Light `#19000000` / Dark 留空 | - |
| LoadingProgress | ring（降级） | - | - | - | - | - | - | - | `#99000000` | `#99FFFFFF` | - | 与 A2UI ring 非完全等价 |

## A2UI 映射

`color` / `type` / `width` / `height` / `backgroundColor` / `borderRadius`

**Gap：** 独立轨道色；LoadingProgress 与 A2UI ring 的精确对应。

---

# B6 · TextInput

**A2UI 原语：** `Extended.TextInput`
**属性：** `text` / `placeholder` / `enabled` / `maxLength` / `type`
**交互（简）：** 按业务需要配置输入相关 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：输入文本、placeholder、enabled、maxLength、type 来自业务数据；字符计数器用组合结构。
- 非品牌色可变项：无额外卡片场景样式；除输入值、错误/禁用等业务状态外不开放额外样式变化。
- 固定样式：框型、线型、字符计数器的尺寸、padding、圆角、字号、字重和颜色按下表固定。
- 品牌色：光标和 focus 等品牌语义 Token 可按 overlay 规则替换。
- Gap：字符计数器无原生组件。

## 共用 token

| 用途 | Light | Dark | A2UI 字段 / 备注 |
|---|---|---|---|
| placeholder | `#99000000` | `#99FFFFFF` | `placeholderColor` |
| 输入文字 | `#E5000000` | `#E5FFFFFF` | `fontColor` |
| 禁用文字 | `#66000000` | `#66FFFFFF` | `enabled: false` 时的 `fontColor` |
| 光标 | `#FF0A59F7` | `#FF5291FF` | `caretColor` |
| warning/error | `#E84026` | `#D94838` | 错误文本、描边、下划线 |
| 线型初始分割线 | `#33000000` | `#33FFFFFF` | `underlineColor.normal` |

## 框型输入框矩阵

| 状态 | height | panelHeight | paddingLeft | paddingRight | backgroundColor Light | backgroundColor Dark | borderRadius | fontSize | fontWeight | textAlign | fontColor Light | fontColor Dark | caretColor Light | caretColor Dark | borderWidth | borderColor Light | borderColor Dark | warningFontSize Light | warningFontSize Dark | enabled |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---|---|---|---:|---|---|---:|---:|---|
| 初始 | 56 | 40 | 16 | 16 | `#0C000000` | `#19FFFFFF` | 20 | 16 | 400 | start | placeholder 色 | placeholder 色 | - | - | - | - | - | - | - | - |
| 激活/输入 | - | - | - | - | - | - | - | - | - | - | `#E5000000` | `#E5FFFFFF` | `#FF0A59F7` | `#FF5291FF` | - | - | - | - | - | - |
| 错误 | - | - | - | - | - | - | - | - | - | - | `#E84026` | `#D94838` | - | - | 1 | `#E84026` | `#D94838` | 10 | 12 | - |
| 不可用 | - | - | - | - | - | - | - | - | - | - | `#66000000` | `#66FFFFFF` | - | - | - | - | - | - | - | false |

## 线型输入框矩阵

| 状态 | height | innerHeight | showUnderline | underlineColor Light | underlineColor Dark | fontColor Light | fontColor Dark | warningFontSize Light | warningFontSize Dark | warningFontWeight | textAlign | enabled | 备注 |
|---|---:|---:|---|---|---|---|---|---:|---:|---:|---|---|---|
| 初始 | 56 | 48 | true | `#33000000` | `#33FFFFFF` | placeholder 色 | placeholder 色 | - | - | - | start | - | - |
| 激活 | - | - | true | `#7F000000` | `#7FFFFFFF` | - | - | - | - | - | - | - | - |
| 输入 | - | - | true | `#7F000000` | `#7FFFFFFF` | `#E5000000` | `#E5FFFFFF` | - | - | - | - | - | 按 `primary50` 定稿值归一 |
| 错误 | - | - | true | `#E84026` | `#D94838` | `#E84026` | `#D94838` | 10 | 10 | 500 | start | - | - |
| 不可用 | - | - | true | - | - | `#66000000` | `#66FFFFFF` | - | - | - | - | false | - |

## 字符计数器矩阵

| 部位 | backgroundColor Light | backgroundColor Dark | borderRadius | paddingLeft | paddingRight | paddingTop | paddingBottom | fontSize | fontColor Light | fontColor Dark | fontWeight | textAlign | borderWidth | borderColor Light | borderColor Dark | 备注 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---:|---|---|---|
| 背板 | `#0C000000` | `#19FFFFFF` | 16 | - | - | - | - | - | - | - | - | - | - | - | - | - |
| 正文 | - | - | - | 16 | 16 | 8 | 8 | 16 | `#99000000` | `#99FFFFFF` | 400 | Start | - | - | - | - |
| 计数文本 | - | - | - | 16 | 16 | 0 | 8 | 10 | `#66000000` | `#66FFFFFF` | 500 | End | - | - | - | - |
| 错误态 | `#0C000000` | `#19FFFFFF` | 16 | - | - | - | - | - | `#E84026` | `#D94838` | - | - | 1 | `#E84026` | `#D94838` | 组合实现 |

## 右侧图标矩阵

| 子样式 | clearIconSize | eyeIconSize | backgroundSize | backgroundRadius Light | backgroundRadius Dark | paddingRight | paddingTop | paddingBottom |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 框型 | 16 | 20 | 32 | 16 | 32 | Light 4 / Dark 2 | Light 4 / Dark 2 | Light 4 / Dark 2 |
| 线型 | 16 | 20 | 32 | 16 | 16 | 0 | 8 | 8 |

## A2UI 映射

`placeholderColor` / `fontSize` / `fontColor` / `fontWeight` / `textAlign` / `caretColor` / `selectedBackgroundColor` / `showUnderline` / `underlineColor` / `cancelButton` / `type` / `maxLength` / `maxLines` / `wordBreak` / `backgroundColor` / `borderRadius` / `borderWidth` / `borderColor` / `width` / `height` / `padding`

**Gap：** 字符计数器无原生组件，使用 Stack + TextInput + Text。

---

# B7 · Checkbox

**A2UI 原语：** `Extended.Checkbox`
**属性：** `group` / `select`
**交互（简）：** 按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：`group` 和 `select` 来自业务数据。
- 非品牌色可变项：无额外卡片场景样式；除 `select` 业务状态外不开放额外样式变化。
- 固定样式：尺寸、圆角、选中背景、未选描边、mark 按下表固定；待确认项不补值。
- 品牌色：选中背景等品牌语义 Token 可按 overlay 规则替换。

| 状态 | select | width | height | containerSize | borderRadius | borderWidth | shape | selectedColor Light | selectedColor Dark | unselectedBorderA Light | unselectedBorderA Dark | unselectedBorderB Light | unselectedBorderB Dark | markColor | 备注 |
|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|---|
| Unselected enabled | false | 20 | 20 | 24 | 10 | 2px | circle / rounded_square | - | - | 规范留空 | `#33FFFFFF` | `#66000000` | `#66FFFFFF` | - | source 并列两组描边；具体采用待 UX 确认 |
| Selected enabled | true | 20 | 20 | 24 | 10 | - | circle / rounded_square | `#FF0A59F7` | 规范留空 | - | - | - | - | 规范留空 | - |

## A2UI 映射

`selectedColor` / `unselectedColor` / `mark` / `shape` / `width` / `height` / `borderRadius` / `select`

---

# B8 · CheckboxGroup

**A2UI 原语：** `Extended.CheckboxGroup`
**属性：** `group` / `selectAll`
**交互（简）：** 按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：`group`、`selectAll`、文本标签或文本链接来自业务数据。
- 非品牌色可变项：无额外卡片场景样式；除勾选业务状态外不开放额外样式变化。
- 固定样式：勾选框组合 / 文本链接的高度、圆角、字号、字重、颜色、间距按下表固定。
- 品牌色：文本链接和选中态品牌语义 Token 可按 overlay 规则替换。

| 子样式 | height | borderRadius Light | borderRadius Dark | fontSize | fontWeight | fontColor Light | fontColor Dark | textAlign | space | decoration | 备注 |
|---|---:|---:|---:|---:|---:|---|---|---|---:|---|---|
| 勾选框组合 | 48 | 8 | 12 | 14 | 400 | `#E5000000` | `#E5FFFFFF` | start | 12 | - | 文本用子 `Extended.Text` |
| 文本链接 | - | - | - | - | - | `#FF0A59F7` | `#FF5291FF` | - | - | underline | 用 `Extended.Text.decoration` 表达 |

## A2UI 映射

`selectedColor` / `unselectedColor` / `mark` / `checkboxShape` / `height` / `borderRadius` / `selectAll`

---

# B9 · Toggle / Switch

**A2UI 原语：** `Extended.Toggle`
**属性：** `isOn` / `enabled`
**交互（简）：** 按业务需要配置 `action.event` / `action.functionCall`；切换状态以业务数据为主。

## 生成约束

- 基本元素：`isOn` / `enabled` 来自业务数据。
- 非品牌色可变项：无额外卡片场景样式；除 `isOn` 业务状态外不开放额外样式变化。
- 固定样式：轨道尺寸、圆角、开启/关闭背景、圆点尺寸/颜色按下表固定。
- 品牌色：开启态品牌语义 Token 可按 overlay 规则替换。
- Gap：圆点描边和 padding 不生成。

| 部位 | width | height | borderRadius | selectedColor Light | selectedColor Dark | unSelectedColor Light | unSelectedColor Dark | switchPointColor Light | switchPointColor Dark | blockSize | 备注 |
|---|---:|---:|---:|---|---|---|---|---|---|---:|---|
| 开启轨道 | 36 | 20 | 18 | `#FF0A59F7` | 规范留空 | - | - | - | - | - | - |
| 关闭轨道 | 36 | 20 | 18 | - | - | `#19000000` | 规范留空 | - | - | - | - |
| 圆点 | - | - | - | - | - | - | - | 规范留空 | `#E5E5E5` | 16 | 圆点描边、padding 为 Gap |

## A2UI 映射

`selectedColor` / `unSelectedColor` / `switchPointColor` / `width` / `height` / `borderRadius` / `isOn`

**协议字段名：** `unSelectedColor`（中间 `S` 大写）以 `reference/protocol/extended-ui-schema.md` 为准；勿与 Checkbox / CheckboxGroup 的 `unselectedColor` 混淆。

**Gap：** 圆点描边、圆点 padding。

---

# B10 · Bottom Tab

**A2UI 原语：** `Extended.Tabs` + `Extended.TabContent`
**属性：** 底部默认 `barPosition: "end"`；左侧布局用 `barPosition: "start"`；其他属性 `vertical` / `scrollable` / `tabIndex` / `children`
**交互（简）：** Tabs / TabContent 按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：Tabs 容器和 TabContent 子项；`tabIndex` 来自业务状态。
- 非品牌色可变项：无额外卡片场景样式；除 `tabIndex` 外不开放额外样式变化。
- 固定样式：上下结构 / 左侧布局 / 左右布局的尺寸、padding、字号、图标尺寸和颜色按下表固定。
- 品牌色：选中态文本/图标品牌语义 Token 可按 overlay 规则替换。
- Gap：多色图标层用资源自带颜色。

## 布局矩阵

| 布局变体 | barPosition | vertical | height | width | paddingLeft | paddingRight | paddingAll | backgroundColor | borderRadius | blurRadius | dividerWidth | dividerColor Light | dividerColor Dark | fontSize | fontWeight | iconSize | fontIconSpace |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|---:|---:|---:|---:|
| 上下结构 | end | false | 48 | - | 4 | 4 | - | `comp_background_gray`（L/D 留空） | 8 | 80 | 1px | `#33000000` | `#33FFFFFF` | 10 | 500 | 24 | 2 |
| 左侧布局 | start | true | - | 96 | 4 | 4 | - | - | - | 80 | 1px | `#33000000` | `#33FFFFFF` | 同上下 | 同上下 | 同上下 | 4 |
| 左右布局 | end | false | 40 | - | - | - | 8 | - | - | 80 | 1px | `#33000000` | `#33FFFFFF` | 12 | 500 | 同上下 | 8 |

## 文本色矩阵

| 状态 | fontColor Light | fontColor Dark |
|---|---|---|
| off | `#99000000` | `#99FFFFFF` |
| on | `#FF0A59F7` | `#FF5291FF` |

## 图标色矩阵（上下结构）

| 色层 | Light | Dark |
|---|---|---|
| off | `#33000000` | `#33FFFFFF` |
| off01 | `#3F000000` | `#3F000000` |
| off02 | `#66000000` | `#66FFFFFF` |
| on | `#FF0A59F7` | `#FF5291FF` |
| on01 | `#CCFFFFFF` | `#CCFFFFFF` |
| on02 | `#990A59F7` | `#99317AF7` |

## A2UI 映射

Tabs：`barPosition` / `vertical` / `scrollable` / `tabIndex` / `backgroundColor` / `borderRadius` / `width` / `height`
TabContent：`selectColor` / `unselectedColor` / `defaultBackgroundColor` / `selectBackgroundColor` / `defaultBorderColor` / `selectBorderColor` / `fontSize` / `fontWeight` / `iconSize` / `space` / `padding`

**协议唯一来源：** **`Extended.Tabs` / `Extended.TabContent`** 的 JSON 字段名以 [`reference/protocol/extended-ui-schema.md`](../protocol/extended-ui-schema.md) 为准。**`Extended.Radio`** 使用 **`indicatorType`**。

**Gap：** 多色图标层用 SVG/图片资源自带颜色。

---

# B11 · SubTab

**A2UI 原语：** `Extended.Tabs` + `Extended.TabContent`
**关键属性：** `tabType: "capsule"`；其余 `tabIndex` / `children` / `scrollable` / `barPosition` 同 B10
**交互（简）：** 与 Tabs 口径一致，按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：Tabs/TabContent，文本，可选右侧图标、数字、小图标或图片；`tabIndex` 来自业务状态。
- 非品牌色可变项：无额外卡片场景样式；除 `tabIndex` 外不开放额外样式变化。
- 固定样式：普通子页签 / 右侧图标 / 组合型的高度、padding、圆角、字号、字重和颜色按下表固定。
- 品牌色：选中态背景等品牌语义 Token 可按 overlay 规则替换。

## 普通子页签矩阵

| 状态 | height | paddingLeft | paddingRight | paddingTop | paddingBottom | containerSpace | backgroundColor Light | backgroundColor Dark | borderRadius | fontSize | fontWeight Light | fontWeight Dark | fontColor Light | fontColor Dark | selectBackgroundColor Light | selectBackgroundColor Dark | selectColor |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|---|---|---|---|
| normal | 36 | 16 | 16 | 8 | 8 | 8 | `#0C000000` | `#19FFFFFF` | 18 | 16 | 400 | 500 | `#99000000` | `#99FFFFFF` | - | - | - |
| selected | 36 | 16 | 16 | 8 | 8 | 8 | - | - | 18 | 16 | 500 | 500 | - | - | `#FF0A59F7` | 规范留空 | `#FFFFFFFF` |

## 右侧图标矩阵

| containerIconSize Light | containerIconSize Dark | backgroundColor Light | backgroundColor Dark | iconSize Light | iconSize Dark | iconColor Light | iconColor Dark |
|---|---|---|---|---|---|---|---|
| 36x36 | 规范留空 | `#0C000000` | 规范留空 | 24x24 | 规范留空 | `#E5000000` | 规范留空 |

## 组合型矩阵

| 部位 | fontSize | fontWeight | color Light | color Dark | activeColor Light | activeColor Dark | size | spacing |
|---|---:|---:|---|---|---|---|---:|---:|
| 数字 | 12 | 400 | `#99000000` | `#99FFFFFF` | `#99FFFFFF` | `#99FFFFFF` | - | 2 |
| 图标 | - | - | `icon_secondary` | `icon_secondary` | `icon_on_primary` 规范留空 | `icon_on_primary` 规范留空 | 16 | 6 |
| 图片 | - | - | - | - | - | - | - | 左右 padding 16 |

## A2UI 映射

`tabType` / `defaultBackgroundColor` / `selectBackgroundColor` / `unselectedColor` / `selectColor` / `fontSize` / `fontWeight` / `iconSize` / `title` / `icon` / `selectedSrc` / `width` / `height` / `padding`

---

# B12 · List

**A2UI 原语：** `Extended.List`
**属性：** `children` / `space`
**交互（简）：** 列表滚动/点击交互按业务需要配置 `action.event` / `action.functionCall`。
**注意：** 通用 List 规格用于设置页/通用列表；生成式卡片列表尺寸以本节已收敛规则为准。

## 生成约束

- 基本元素：List 容器 + 列表项 Row；列表项按左 / 中 / 右三段组合，`children` 可绑定数据路径。
- 非品牌色可变项：卡片场景只从本文已收敛结构选择：列表左/中/右元素、单/双/多行文本、右侧 Button/图标/文本箭头、宫格纯图片/图文/图文+Button/视频；纯图片/图文常用比例为 1:1 / 3:4 / 4:3 / 9:16，视频比例仅 16:9 / 21:9。
- 固定样式：通用 List 按下表固定；卡片场景尺寸、间距、图片和文本层级以本节已收敛规则优先。
- 品牌色：排序数字 NO.1-3、badge、选中态等品牌语义 Token 可按 overlay 规则替换。
- Gap：List 分割线用 Divider 组合；图片加载/失败占位不补造。

## 容器矩阵

| height | width | marginLeft | marginRight | borderRadius | backgroundColor | dividerWidth Light | dividerWidth Dark | dividerColor Light | dividerColor Dark | scrollBar |
|---:|---:|---:|---:|---:|---|---|---|---|---|---|
| 56 | 328 | 16 | 16 | 20 | `comp_background_list_card`（L/D 留空） | 1px | 0.5px | `#33000000` | `#33FFFFFF` | 卡片/紧凑列表默认 `off` |

## 左侧元素矩阵

| 类型 | size | width | height | marginLeft Light | marginLeft Dark | spacingRight | paddingLeft | paddingTop | paddingBottom | borderRadius | backgroundColor Light | backgroundColor Dark | color Light | color Dark | fontSize Light | fontSize Dark |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| 小红点 | 8 | - | - | 8 | 12 | 12 | - | - | - | - | `#FF0A59F7` | 规范留空 | - | - | - | - |
| 文字角标 | - | 16 | 16 | 8 | 12 | - | - | - | - | - | `#E84026` | `#D94838` | `font_on_primary` | `font_on_primary` | 10 | 12 |
| 小图标 | 16 | - | - | 8 | 12 | 12 | - | - | - | - | - | - | `#99000000` | `#E5FFFFFF` | - | - |
| 系统图标 | 24 | - | - | 12 | 12 | 16 | - | - | - | - | - | - | `#99000000` | `#E5FFFFFF` | - | - |
| 图片 | 48 | - | - | - | - | 16 | 8 | 8 | 8 | 8 | - | - | - | - | - | - |

## 左侧开关矩阵

| trackWidth | trackHeight | borderRadius | unSelectedColor Light | unSelectedColor Dark | selectedColor Light | selectedColor Dark | switchPointWidth | switchPointHeight | switchPointColor Light | switchPointColor Dark | containerSize | marginLeft Light | marginLeft Dark | spacingRight |
|---:|---:|---:|---|---|---|---|---:|---:|---|---|---:|---:|---:|---:|
| 36 | 20 | 10 | `#19000000` | 规范留空 | `#FF0A59F7` | `#FF317AF7` | 16 | 16 | `#FFFFFF` | 规范留空 | 48 | 2 | 6 | 8 |

## 中间元素矩阵

| 类型 | fontSize | fontWeight | fontColor Light | fontColor Dark | marginLeft Light | marginLeft Dark | marginRight Light | marginRight Dark | spacingTop Light | spacingTop Dark | symbolSize | symbolColor | iconHotspotHeight | iconHotspotWidth | iconSpacingHorizontal |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 单行标题 | 16 | 500 | `#E5000000` | `#E5FFFFFF` | 8 | 12 | 8 | 12 | - | - | - | - | - | - | - |
| 双行副标题 | 14 | 400 | `#99000000` | `#99FFFFFF` | 12 | 12 | 12 | 12 | 2 | 2 | - | - | - | - | - |
| 三行文本 | 14 | 400 | `#99000000` | `#99FFFFFF` | 12 | 12 | 12 | 12 | 2 | 0 | - | - | - | - | - |
| 左侧 symbol | - | - | - | - | - | - | - | - | - | - | 16 | tertiary | - | - | 8（right） |
| 右侧 symbol | - | - | - | - | - | - | - | - | - | - | - | - | 40 | 32 | 8 |

## 右侧元素矩阵

| 类型 | width | height | size | paddingLeft | paddingRight | paddingTop | paddingBottom | borderRadius | borderWidth | backgroundColor Light | backgroundColor Dark | color Light | color Dark | fontSize | fontWeight | marginRight Light | marginRight Dark | spacing / 备注 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---|
| RightText | - | - | - | 8 | 8 | - | - | - | - | - | - | `#99000000` | `#99FFFFFF` | 14 | 400 | - | - | - |
| 右侧图片 | - | - | 48 | 16 | 8 | 8 | 8 | 8 | - | - | - | - | - | - | - | - | - | - |
| Loading Progress | - | - | 24 | 12 | 8 | - | - | - | - | - | - | tertiary | tertiary | - | - | - | - | - |
| 右侧 Checkbox selected | - | - | 20 | - | - | - | - | 10 | - | `#FF0A59F7` | 规范留空 | - | - | - | - | - | - | mark 14; `select: true` |
| 右侧 Checkbox unselected | - | - | - | - | - | - | - | - | 2px | `#33FFFFFF` | `#33000000` | border `#33000000` | border `#33FFFFFF` | - | - | - | - | source 字面 |
| 右侧 Switch | 36 | 20 | - | - | - | - | - | 18 | - | active `#FF0A59F7`; default `#19000000` | active 规范留空; default 规范留空 | block 规范留空 | block `#E5E5E5` | - | - | - | - | block 16; block padding 2; shadow `OUTER_DEFAULT_XS` |
| 右箭头 | 12 | Light 24 / Dark 20 | - | - | - | - | - | - | - | - | - | `#FF0A59F7` | `#FF5291FF` | - | - | 8 | 12 | spacingLeft 8; badge spacing 4; badge marginLeft 8; text spacing 4; text marginLeft 8 |
| Spinner | 96 | 40 | - | font Light 8 / Dark 12 | arrow Light 0 / Dark 4 | - | - | - | - | - | - | arrow `#66000000`; text `#E5000000` | arrow `#66FFFFFF`; text `#E5FFFFFF` | 14 | 400 | - | - | title spacing left 16; font-arrow spacing 0 |
| RightIcon | - | - | 24 | Light 8 / Dark 12 | - | - | - | - | - | - | - | - | - | - | - | - | - | hotspot Light 40 / Dark 48; spacingHorizontal 24 |

## A2UI 映射

List：`listDirection` / `scrollBar` / `nestedScroll` / `space` / `backgroundColor` / `borderRadius` / `width` / `height` / `margin` / `padding`
列表项：`Extended.Row` + 左/中/右组合；中间列用 `layoutWeight: 1`。

**Gap：** List 无原生分割线字段，插入 `Extended.Divider`。

---

# B13 · Radio

**A2UI 原语：** `Extended.Radio`
**属性：** `value` / `checked` / `group` / `indicatorType`
**交互（简）：** 按业务需要配置 `action.event` / `action.functionCall`。

## 生成约束

- 基本元素：`value`、`checked`、`group`、`indicatorType` 来自业务数据或明确输入。
- 非品牌色可变项：无额外卡片场景样式；除 `checked` 和明确输入的 `indicatorType` 外不开放额外样式变化。
- 固定样式：尺寸、圆角、选中背景、未选描边按下表固定；待确认项不补值。
- 品牌色：选中背景等品牌语义 Token 可按 overlay 规则替换。

| 状态 | checked | width | height | containerSize | borderRadius | borderWidth | checkedBackgroundColor Light | checkedBackgroundColor Dark | uncheckedBorderColor (outer) Light | uncheckedBorderColor (outer) Dark | uncheckedBorderColor (alt) Light | uncheckedBorderColor (alt) Dark | indicatorColor | indicatorType |
|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|---|---|
| Unselected enabled | false | 20 | 20 | 24 | 10 | 2px | - | - | 规范留空 | `#33FFFFFF` | `#66000000` | `#66FFFFFF` | - | 按输入显式写，未指定标记待确认 |
| Selected enabled | true | 20 | 20 | 24 | 10 | - | `#FF0A59F7` | 规范留空 | - | - | - | - | 规范留空 | 按输入显式写，未指定标记待确认 |

## A2UI 映射

`checkedBackgroundColor` / `uncheckedBorderColor` / `indicatorColor` / `indicatorType` / `checked` / `width` / `height` / `borderRadius`。未选中态在 source 中存在两组描边取值（outer / alt）；A2UI 固定使用单字段 `uncheckedBorderColor`，按场景显式取其一，未指定时标记待确认。

---

# 常用组合

## Tag

用 `Extended.Text` 合成。Tag 仅作为组合配方；如果需要严格追溯，以完整 source 对应章节为准。

生成约束：

- 基本元素：Tag 文本必选，内容来自输入数据。
- 非品牌色可变项：卡片场景已收敛到本文的 Tag 场景；Light 可选线性营销/中性标签，Dark 使用面性标签；排序标签规格不足，不生成确定样式。
- 固定样式：高度、padding、最大宽、圆角、字号、字重、截断规则按下表固定。
- 品牌色：Tag 默认不按品牌色自由变色；只有绑定品牌语义 Token 的场景才可 overlay。

| 字段 | 值 |
|---|---|
| `height` | 16 |
| `padding.left/right` | 4 |
| `constraintSize.maxWidth` | 68 |
| `borderRadius` | 4 |
| `fontSize` | 10 |
| `fontWeight` | 500 |
| `textOverflow` | `ellipsis` |
| `maxLines` | 1 |

| 类型 | borderWidth | borderColor | backgroundColor | fontColor |
|---|---|---|---|---|
| Light 线性标签 | 1 | 按 token | 不写 | 按 token |
| Dark 面性标签 | 不写 | 不写 | `container20` | `font_primary` |

## 图标背板

生成约束：

- 基本元素：背板 `Stack` + 内部图标 `Image`。
- 非品牌色可变项：卡片场景已收敛到本文图标背板场景；左侧图标背板为 48×48，右侧可操作图标背板为 40×40，右侧数量最多 2 个。
- 固定样式：背板颜色、图标尺寸、左/右位置的尺寸和间距按下表固定。
- 品牌色：普通图标背板不随品牌色变化。
- Gap：A2UI Image 无 `tintColor`，图标颜色需资源侧处理。

| 场景 | 背板 width | 背板 height | 背板 radius | 背板 backgroundColor | 图标 width | 图标 height | 图标色 | 间距 |
|---|---:|---:|---:|---|---:|---:|---|---|
| 列表项左侧图标背板 | 48 | 48 | 24 | `comp_background_tertiary` | 24 | 24 | `icon_secondary` | 与中间区 12vp |
| 列表项右侧可操作图标背板 | 40 | 40 | 待 UX 确认（20 或 24） | `comp_background_tertiary` | 24 | 24 | `icon_primary` | 图标之间 8vp，最多 2 个 |

```text
Extended.Stack
  styles: width / height / borderRadius / backgroundColor / alignContent: "center" / clip: true
  children:
    Extended.Image
      styles: width / height / objectFit: "contain"
```

## Arrow Trailing

生成约束：

- 基本元素：文本 + 箭头图标，外层 Row 控制 4vp 间距。
- 非品牌色可变项：卡片场景已收敛到本文的 Arrow Trailing 场景；列表项右侧使用 12×24 扁形箭头，Card_Name 右侧使用 20vp 等比箭头。
- 固定样式：文本字号/字重/颜色、箭头尺寸/颜色、间距按下表固定。
- 品牌色：Arrow Trailing 默认不随品牌色变化。
- Gap：Image 无着色字段；系统图标 ID 能否作为 `src` 待工程确认。

| 场景 | Text fontSize | Text fontWeight | Text fontColor | Arrow width | Arrow height | Arrow color | Row space |
|---|---:|---:|---|---:|---:|---|---:|
| 列表项右侧 | 14 | 400 | `font_secondary` | 12 | 24 | `icon_fourth` | 4 |
| Card_Name 右侧 | 12 | 400 | `font_secondary` | 20 | 20 | `icon_tertiary` | 4 |

```text
Extended.Row
  styles: space: 4, alignItems: "center"
  children:
    Extended.Text
    Extended.Image
```

## List Item

生成约束：

- 基本元素：Row + leading / middle / trailing；同一列表内结构必须一致。
- 非品牌色可变项：只从本文已收敛的左/中/右元素类型中选择；排序数字、图片类型、右侧 Button/图标/文本箭头按本文。
- 固定样式：列表项高度、上下安全边距、文本层级、元素间距和左/右元素尺寸按下表固定。
- 品牌色：排序数字 NO.1-3 可按品牌 token overlay；NO.4+ 使用 `font_secondary`。

| 区域 | 可选项 | 固定样式 |
|---|---|---|
| 列表项整体 | 单行 / 双行 / 多行 | 最小高度 48 / 64 / 80；上下安全边距 8；一般左右区域间距 12 |
| 左侧 | 排序数字 | 20×24；NO.1-3 品牌色，NO.4+ `font_secondary`；与中间区间距 8 |
| 左侧 | 图标背板 | 背板 48×48 / radius 24；图标 24×24；`comp_background_tertiary` |
| 左侧 | 应用图标 / 1:1 图片 | 56×56；radius 12 |
| 左侧 | 竖向特殊比例图片 | 宽度最大 56；radius 12 |
| 中间 | 单行标题 | 16 / 500 / `font_primary` |
| 中间 | 双行副标题 | 第二行 14 / 400 / `font_secondary`；两行间距 2 |
| 中间 | 三行文本 | 第二、三行 14 / 400 / `font_secondary`；文本间距 2 |
| 右侧 | 小按钮 | 使用 Button 小按钮，height 28 |
| 右侧 | 可操作图标 | 背板 40×40；图标 24×24；图标之间 8；最多 2 个 |
| 右侧 | 文本 + 箭头 | Text 14 / 400 / `font_secondary`；Arrow 12×24 / `icon_fourth`；间距 4 |

```text
Extended.Row
  children:
    leading
    Extended.Column(layoutWeight: 1, flexShrink: 1)
    trailing
```

## Loading Button

A2UI Button 无内置 loading：
- 用 `enabled: false`
- 用 `Row + Progress + Text` 或自定义 loading 图标组合
- 不写不存在的 `loading` 字段

## 补充组件组合配方

以下配方只包含可稳定组合或可降级生成的组件。字段合法性以 `reference/protocol/extended-ui-schema.md` 为准；不要生成 `Extended.Menu` / `Extended.Slider` / `Extended.QRCode` / `Extended.TextClock` 等不存在的一等原语。

生成约束：

- Part C 组件默认没有额外卡片场景可变样式；除品牌色 overlay、业务状态和值以外，不开放额外样式变化。
- 只能从下表已有组合配方和本文已列子样式中选择；不可生成不存在的一等原语。

| 组件 | 生成策略 | A2UI 结构 | 关键样式值 | 业务状态 |
|---|---|---|---|---|
| 状态按钮 / Toggle | `Button` 或 `Text/Row` 组合 | `Extended.Button`；或 `Row/Text` + `action.event` | height 40; padding 8/4; background `comp_background_tertiary`; radius 14; fontSize 14 | active 时切换背景 / 文本色 |
| Chips | `Row + Text + Image?` | `Extended.Row` 容器 + `Extended.Text` + 可选图标 | 页签 height 36/radius 18 or 16; 筛选 height 28/radius 14; fontSize 14/16; normal bg `comp_background_tertiary`; selected bg `comp_background_emphasize` | selected / activated |
| SubHeader | `Row/Column + Text + trailing` | 左侧标题/副标题 + 右侧文本/箭头/按钮/图标 | height 48 or 64; padding left/right 16; title 16/500/`font_primary`; subtitle 14/`font_secondary` | 右侧操作用 listener |
| Counter | `Row + icon button + Text + icon button` | 两侧 `Stack/Image` 或 `Button`，中间 `Text` | 列表型 height 48; digit 16/500; icon 20; iconBg 32/radius16; bg `comp_background_tertiary` | onClick 增减并更新数据 |
| Rating | `Row + Image[]` | 一排星形资源图片 | iconSize 28; active `multi_color_11`; normal `comp_background_secondary` | value 控制 active 数量 |
| SegmentedButton | `Tabs` 或 `Row + Text[]` | 单选优先 `Extended.Tabs`；多选用 Row 组合 | height 40; radius 20; container `comp_background_tertiary`; item fontSize 14/weight 500; selected bg `comp_background_primary_contrary` 或 `comp_background_emphasize` | 单选 index / 多选集合 |
| Swiper Indicator | `Row + Stack/Text` | dot 指示器、数字指示器或左右箭头 | dot 6/8; active 6x12; spacing 8/10; containerHeight 32; arrow hotarea 32 | currentIndex 控制 active |
| TextClock | `Text` 降级 | `Extended.Text` | fontSize 16; fontWeight 500; fontColor `font_primary`; align center | 只能展示输入时间字符串 |

# 不生成清单

除非用户明确要求或业务状态必须表达，否则不要生成：

- CSS 伪类
- 不存在的 `tintColor`
- 不存在的 Button `loading`
- 不存在的 Text `lineHeight`
- 不存在的补充组件一等原语（如 `Extended.Slider` / `Extended.QRCode`）
- A2UI optional 字段的默认值
