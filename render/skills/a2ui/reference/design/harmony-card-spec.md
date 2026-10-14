# HarmonyOS 生成式卡片设计规范

> 供 Skill 运行时使用的卡片规范，聚焦可执行的卡片布局与样式规则。

> **A2UI 组件 JSON：** 文中 JSON 代码块表示 `updateComponents.components[]` **单项**的字段形态：`component` 为协议组件名，其余业务字段与 `styles` **平铺在顶层**（与 `reference/protocol/extended-ui-schema.md` 一致）。列表/宫格随数据重复时，为每条数据生成独立 `id` 的兄弟组件并写入 `children`；勿将下列占位 `id` 当作可复制的 NDJSON 整流。

# Part A · Design Tokens

## A1 · Color 颜色

> UX 规范中使用的所有颜色别名，按语义分类。所有值来自鸿蒙 FA 系列官方 token，Light/Dark 全量。

### A1.1 文字颜色（Text）

| 别名 | Light | Dark | 使用位置 |
|---|---|---|---|
| `font_primary` | `#E5000000` | `#E5FFFFFF` | Card_Name 应用名称 · 列表样式 1/2/3 第一行 · 宫格样式 2 标题、样式 3 文本 · 标签 Light 组合 2、Dark 文本 |
| `font_secondary` | `#99000000` | `#99FFFFFF` | Card_Name 右侧文本 · 列表样式 2 第二行、样式 3 第二三行 · 可操作文本+箭头 · 排序数字 NO.4+ |
| `font_tertiary` | `#66000000` | `#66FFFFFF` | 宫格样式 2 辅助文本 |

### A1.2 图标颜色（Icon）

| 别名 | Light | Dark | 使用位置 |
|---|---|---|---|
| `icon_primary` | `#E5000000` | `#E5FFFFFF` | 右侧可操作图标 |
| `icon_secondary` | `#99000000` | `#99FFFFFF` | 左侧图标（含背板）的图标色 |
| `icon_tertiary` | `#66000000` | `#66FFFFFF` | Card_Name 右箭头 |
| `icon_fourth` | `#33000000` | `#33FFFFFF` | 可操作文本+箭头的箭头色 |

### A1.3 背景 / 容器颜色

| 别名 | Light | Dark | 使用位置 |
|---|---|---|---|
| `comp_background_list_card` | `#FFFFFFFF` | `#19FFFFFF` | 卡片最外层底板材质 |
| `comp_background_tertiary` | `#0C000000` | `#19FFFFFF` | 左侧图标背板 · 右侧可操作图标背板 |

### A1.4 标签专用色

| 别名 | Light 值 | Dark 值 | 使用位置 |
|---|---|---|---|
| `multi_color_08` | `#E84026` | `#D94838` | 标签 Light 组合 1 的描边+文本（鸿蒙色板 palette8，Dark 下略柔化）|
| `container40` | `#66000000` | `#66FFFFFF` | 标签 Light 组合 2 的描边（40% alpha）|
| `container20` | `#33000000` | `#33FFFFFF` | 标签 Dark 面性填充背景（20% alpha）|

### A1.5 色板速查（SVG 预览，Light 模式）

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="180" viewBox="0 0 600 180">
  <!-- 文字色 -->
  <rect x="10" y="10" width="60" height="60" rx="8" fill="#E5000000"/>
  <text x="40" y="85" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#666">font_primary</text>
  <text x="40" y="98" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#999">#E5000000</text>
  <rect x="80" y="10" width="60" height="60" rx="8" fill="#99000000"/>
  <text x="110" y="85" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#666">font_secondary</text>
  <text x="110" y="98" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#999">#99000000</text>
  <rect x="150" y="10" width="60" height="60" rx="8" fill="#66000000"/>
  <text x="180" y="85" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#666">font_tertiary</text>
  <text x="180" y="98" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#999">#66000000</text>
  <rect x="220" y="10" width="60" height="60" rx="8" fill="#33000000"/>
  <text x="250" y="85" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#666">icon_fourth</text>
  <text x="250" y="98" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#999">#33000000</text>
  <!-- 背景 -->
  <rect x="290" y="10" width="60" height="60" rx="8" fill="#0C000000"/>
  <text x="320" y="85" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#666">comp_bg_tertiary</text>
  <text x="320" y="98" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#999">#0C000000</text>
  <!-- 标签色 -->
  <rect x="360" y="10" width="60" height="60" rx="8" fill="#E84026"/>
  <text x="390" y="85" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#666">multi_color_08</text>
  <text x="390" y="98" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#999">#E84026</text>

  <!-- 层级示意 -->
  <text x="10" y="130" font-family="sans-serif" font-size="11" font-weight="600" fill="#333">文字层级视觉</text>
  <text x="10" y="152" font-family="sans-serif" font-size="14" font-weight="500" fill="#E5000000">一级文本 · primary</text>
  <text x="160" y="152" font-family="sans-serif" font-size="14" fill="#99000000">二级 · secondary</text>
  <text x="290" y="152" font-family="sans-serif" font-size="14" fill="#66000000">三级 · tertiary</text>
  <text x="10" y="170" font-family="sans-serif" font-size="10" fill="#999">用透明度区分层级，alpha 90% / 60% / 40%</text>
</svg>
```

---

## A2 · Typography 字号 / 字重

> UX 规范中使用的字号别名 + 字重，与鸿蒙系统官方字号 token 对齐。

### A2.1 字号（Font Size）

| 别名 | vp | 使用位置 |
|---|---|---|
| `Body_L` | **16** | 列表样式 1/2/3 第一行 |
| `Body_M` | **14** | 列表样式 2 第二行、样式 3 第二三行 · 可操作文本+箭头 |
| `Body_S` | **12** | Card_Name 应用名称 · 宫格样式 2 标题 |
| `Caption_L` | **12** | Card_Name 右侧文本 · 宫格样式 2 辅助文本 · 宫格样式 3 文本 |
| `Caption_M` | **10** | 标签文字 |

> `Body_S` 和 `Caption_L` 底层 vp 值相同（都是 12），UX 规范在语义上用两个名字区分"正文小字"和"辅助说明文字"。

### A2.2 字重（Font Weight）

| 别名 | 数值 | 官方 Token | 使用位置 |
|---|---|---|---|
| `regular` | 400 | `font_weight_regular` | 默认字重（所有副文本、辅助文本、Card_Name 应用名称、右侧文本、箭头等） |
| `Medium` | 500 | `font_weight_medium` | 列表样式 1/2/3 第一行 · 宫格样式 2 标题 · 标签文字 |
| `Bold` | 700 | `font_weight_bold` | 宫格样式 3 文本 |

### A2.3 行高（Line Height）

⚠️ UX 规范未涉及行高。如需使用，可选鸿蒙系统值：

| Token | 倍数 | 使用场景 |
|---|---|---|
| `ohos_id_text_line_space_s` ○ | 1.1× | 单行标题、紧凑文本 |
| `ohos_id_text_line_space_l` ○ | 1.4× | 多行段落、长文本 |

### A2.4 字号视觉对照

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="180" viewBox="0 0 600 180">
  <text x="10" y="30" font-family="sans-serif" font-size="16" font-weight="500" fill="#E5000000">Body_L · 16vp Medium — 列表主标题</text>
  <text x="10" y="58" font-family="sans-serif" font-size="14" fill="#99000000">Body_M · 14vp regular — 列表副标题、可操作文本</text>
  <text x="10" y="84" font-family="sans-serif" font-size="12" fill="#E5000000">Body_S · 12vp regular — Card_Name 应用名称</text>
  <text x="10" y="108" font-family="sans-serif" font-size="12" fill="#99000000">Caption_L · 12vp regular — Card_Name 右侧文本</text>
  <text x="10" y="130" font-family="sans-serif" font-size="10" font-weight="500" fill="#E5000000">Caption_M · 10vp Medium — 标签文字</text>

  <line x1="10" y1="146" x2="590" y2="146" stroke="#33000000" stroke-width="0.5"/>
  <text x="10" y="164" font-family="sans-serif" font-size="10" fill="#999">字号按视觉层级递减：16 → 14 → 12 → 10</text>
</svg>
```

---

## A3 · Spacing 间距

> UX 规范中出现的所有间距值，全部为 4 的倍数（符合鸿蒙 4vp 网格系统）。

| vp | 使用位置 |
|---|---|
| **2** | 列表样式 2/3 文本行间距 · 宫格内元素内部横向间距起点 |
| **4** | Card_Name 文本-箭头 · 宫格样式 2 标题-辅助文本 · 宫格样式 3 图片/文本/Button 间距 · 标签左右安全边距 |
| **8** | Card_Name 图标-名称、左右区域间 · 列表排序数字-中间元素 · 列表样式 1/2/3 上下安全边距 · 宫格图片-文本 · 右侧可操作图标之间 · 宫格横向间距（可选） |
| **12** | Card_Name 左右间距、应用名称到右边距（无右侧） · CARD_CONTENT 左右间距 · 列表项左/中/右元素间 · 宫格横向间距（可选） · OnAPP 场景安全边距 |
| **24** | APP 场景左右安全边距 |

### A3.1 间距视觉

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="120" viewBox="0 0 600 120">
  <!-- 2vp -->
  <rect x="10" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <rect x="52" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <text x="60" y="56" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">2vp</text>
  <!-- 4vp -->
  <rect x="110" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <rect x="154" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <text x="160" y="56" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">4vp</text>
  <!-- 8vp -->
  <rect x="210" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <rect x="258" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <text x="265" y="56" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">8vp</text>
  <!-- 12vp -->
  <rect x="320" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <rect x="372" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <text x="380" y="56" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">12vp</text>
  <!-- 24vp -->
  <rect x="430" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <rect x="494" y="20" width="40" height="20" fill="#E5000000" opacity="0.2"/>
  <text x="505" y="56" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">24vp</text>

  <text x="10" y="90" font-family="sans-serif" font-size="10" fill="#999">所有间距值均为 4 的倍数（4vp 网格系统），2vp 仅用于文本行间距</text>
  <text x="10" y="108" font-family="sans-serif" font-size="10" fill="#999">安全边距：OnAPP 12vp · APP 24vp</text>
</svg>
```

---

## A4 · Corner Radius 圆角

> UX 规范中出现的所有圆角值，按使用位置归类。

| vp | 使用位置 |
|---|---|
| **4** | Card_Name 应用图标 · 标签 |
| **8** | 宫格项（宽度 ≤ 96vp） |
| **12** | 列表左侧应用图标 / 1:1 图片 / 竖向特殊比例图片 · 宫格项（宽度 > 96vp） · 宫格样式 3 图片 |
| **16** | 卡片最外层容器（对应 `corner_radius_level8`） |
| **24** | 列表左侧图标背板（48×48） |

### A4.1 ⚠️ 规范未明确的圆角

| 位置 | 推测值 | 说明 |
|---|---|---|
| 右侧可操作图标背板（40×40） | 20vp 或 24vp | ⚠️ 规范未明确 |
| 列表右侧小 Button（28vp 高） | 14vp（= 高度 / 2） | ⚠️ 规范未明确；推测为胶囊形 |

### A4.2 圆角视觉

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="110" viewBox="0 0 600 110">
  <rect x="10" y="20" width="56" height="56" rx="4" fill="#0C000000"/>
  <text x="38" y="92" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">r4 · 标签、Card_Name 图标</text>

  <rect x="170" y="20" width="56" height="56" rx="8" fill="#0C000000"/>
  <text x="198" y="92" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">r8 · 宫格项（≤96vp）</text>

  <rect x="330" y="20" width="56" height="56" rx="12" fill="#0C000000"/>
  <text x="358" y="92" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">r12 · 列表图片、宫格项（>96vp）</text>

  <rect x="490" y="20" width="56" height="56" rx="24" fill="#0C000000"/>
  <text x="518" y="92" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">r24 · 图标背板（48×48）</text>
</svg>
```

---

## A5 · Token 使用速查

本节列出本规范实际使用的 design token 子集，按类型归纳，便于快速索引。完整 token 定义参见 `reference/design/harmony-design-token.md`。

### A5.1 颜色（Light / Dark 双列）

| 别名 | 映射 | Light 值 | Dark 值 | 使用位置 |
|---|---|---|---|---|
| `font_primary` | `primary90` | `#E5000000`（90% 黑） | `#E5FFFFFF`（90% 白） | 列表第一行、Card_Name 应用名称、宫格标题、标签组合 2 文字、面性标签文字 |
| `font_secondary` | `primary60` | `#99000000`（60% 黑） | `#99FFFFFF`（60% 白） | 列表副文本、Card_Name 右侧文本、排序数字 NO.4+、可操作文本 |
| `font_tertiary` | `primary40` | `#66000000`（40% 黑） | `#66FFFFFF`（40% 白） | 宫格样式 2 辅助文本 |
| `icon_primary` | `primary90` | `#E5000000`（90% 黑） | `#E5FFFFFF`（90% 白） | 右侧可操作图标 |
| `icon_secondary` | `primary60` | `#99000000`（60% 黑） | `#99FFFFFF`（60% 白） | 左侧图标（含背板） |
| `icon_tertiary` | `primary40` | `#66000000`（40% 黑） | `#66FFFFFF`（40% 白） | Card_Name 右箭头 |
| `icon_fourth` | `primary20` | `#33000000`（20% 黑） | `#33FFFFFF`（20% 白） | 可操作文本+箭头 · 箭头 |
| `comp_background_list_card` | 模式差异 | `on_primary100` = `#FFFFFFFF` | `on_primary10` = `#19FFFFFF` | 卡片最外层底板 |
| `comp_background_tertiary` | 模式差异 | `container5` = `#0C000000`（5% 黑） | `container10` = `#19FFFFFF`（10% 白） | 图标背板 |
| `multi_color_08` | — | `#E84026` | `#D94838` | 标签 Light 组合 1 描边 + 文本（Dark 下一般用面性标签，不直接用此色） |
| `container40` | — | `#66000000` | `#66FFFFFF` | 标签 Light 组合 2 描边 |
| `container20` | — | `#33000000` | `#33FFFFFF` | 标签 Dark 面性背景（Dark 下 20% 白，正是面性标签需要的浅色填充） |

### A5.2 字号

| 别名 | 值（fp） | 使用位置 |
|---|---|---|
| `Body_L` | 16 | 列表样式 1/2/3 第一行 |
| `Body_M` | 14 | 列表副文本、可操作文本 |
| `Body_S` | 12 | Card_Name 应用名称、宫格样式 2 标题 |
| `Caption_L` | 12 | Card_Name 右侧文本、宫格样式 2 辅助文本、宫格样式 3 文本 |
| `Caption_M` | 10 | 标签文字 |

### A5.3 字重

| 别名 | 值 | 使用位置 |
|---|---|---|
| `font_weight_regular` | 400 | 默认 |
| `font_weight_medium` | 500 | 列表主标题、宫格标题、标签文字 |
| `font_weight_bold` | 700 | 宫格样式 3 文本 |

### A5.4 尺寸关键值对照

| 场景 | 值 | Token |
|---|---|---|
| 标签高度 | 16vp | `size_level8` |
| Card_Name 应用图标 | 20vp | `size_level10` |
| Card_Name 右箭头 | 20vp | `size_level10` |
| 列表图标 | 24vp | `size_level12` |
| 列表小按钮高度 | 28vp | `size_level14` |
| Card_Name 高度 | 40vp | `size_level20` |
| 右侧图标背板 | 40vp | `size_level20` |
| 列表最小高度（样式 1）| 48vp | `size_level24` |
| 宫格样式 3 图片、左侧图标背板 | 48vp | `size_level24` |
| 列表应用图标 / 1:1 图片 / 竖向图最大宽 | 56vp | `size_level28` |
| 列表最小高度（样式 2）| 64vp | `size_level32` |
| 标签最大宽度 | 68vp | `size_level34` |
| 列表最小高度（样式 3）| 80vp | `size_level40` |
| 宫格项分界宽度 | 96vp | `size_level48` |

### A5.5 圆角 / 间距

详见 A3（间距）/ A4（圆角）章节。

---

# Part B · 基础组件

> UX 规范中明确涉及的 6 类组件。所有规格来自规范原文及配图。
>
> **每个组件的结构：** 一句话描述 → 子变体（带业务语境 label）→ SVG 预览 → 规格表 → A2UI 实现

## B1 · Button 卡片场景按钮

> **A2UI 原语：** `Extended.Button`（Direct）
> 列表项右侧可操作按钮采用 **小按钮（Small Button）** 子样式，高度固定 28vp。宫格样式 3「图片 + 文字 + Button」采用 **普通按钮**子样式。

### 卡片场景使用要点

UX《生成式卡片规则》对列表项右侧 Button 的核心约束是 **高度 28vp**——这是卡片列表紧凑空间下的尺寸要求，对应通用组件库 Button 的"**小按钮**"子样式。宫格样式 3 的图文+Button 组合使用通用组件库 Button 的"**普通按钮**"子样式。

- 列表项右侧的 Button 使用**小按钮**（28vp）
- 宫格样式 3「图片 + 文字 + Button」中的 Button 使用 `reference/design/harmony-ui-components-a2ui.md` B1.1 **普通按钮**子样式
- Card_Name 右侧不使用 Button（用 Arrow Trailing，见 B6）
- 宫格样式 3 中，Button 位于图文下方，宫格项在卡片内等距分布

### B1.1 Small Button — 列表项右侧（normal 态）

> 完整规格（含全部样式变体 + 全状态）见 `reference/design/harmony-ui-components-a2ui.md` B1.5。本章节列出卡片列表场景下最常用的"小按钮 normal 态"作为 spec 速查。

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="40" viewBox="0 0 200 40">
  <rect x="1" y="6" width="80" height="28" rx="14" ry="14" fill="#0C000000" stroke="none"/>
  <text x="41" y="25" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="500" fill="#FF0A59F7">立即购买</text>
  <text x="100" y="18" font-family="sans-serif" font-size="10" fill="#99000000">高 28vp · 圆角 14</text>
  <text x="100" y="32" font-family="sans-serif" font-size="10" fill="#99000000">字号 14 · 字重 500 · 主色文字</text>
</svg>
```

| 属性 | 控件 Token | 语义 / 基础 Token | Light 值 | Dark 值 |
|---|---|---|---|---|
| 高度 | container_height | — | 28 | 28 |
| 宽度 | container_width | — | Max-448 | Max-448 |
| 圆角 | container_shape | `corner_radius_level7` / `corner_radius_level10` | 14 ⚠️ | 20 ⚠️ |
| 左右 padding | padding_left/right | `padding_level4` | 8 | 8 |
| 上下 padding | padding_top/bottom | `padding_level2` | 4 | 4 |
| 字号 | font_size | `Body_M` | 14 | 14 |
| 字重 | font_weight | `font_weight_medium` | 500 | 500 |
| 文字色 | font_color | `font_emphasize` | `#FF0A59F7` | `#FF5291FF` |
| 背景色 | container_color | `comp_background_tertiary` | `#0C000000` | `#19FFFFFF` |
| 文字对齐 | font_alignment | `alignment_center` | Center | Center |

> ⚠️ 圆角 Light/Dark 不一致：Light=14（= 高度/2，胶囊形），Dark=20。可能为官方原文错误，详见 `reference/design/harmony-ui-components-a2ui.md` B1.5 注释。

### B1.2 Normal Button — 宫格样式 3（normal 态）

> 完整规格见 `reference/design/harmony-ui-components-a2ui.md` B1.1。本章节列出卡片宫格样式 3「图片 + 文字 + Button」使用的"普通按钮 normal 态"作为 spec 速查。

| 属性 | 控件 Token | 语义 / 基础 Token | Light 值 | Dark 值 |
|---|---|---|---|---|
| 高度 | container_height | — | 40 | 40 |
| 宽度 | container_width | — | Max-448 | Max-448 |
| 圆角 | container_shape | `corner_radius_level10` | 20 | 20 |
| 左右 padding | padding_left/right | `padding_level8` | 16 | 16 |
| 上下 padding | padding_top/bottom | `padding_level4` | 8 | 8 |
| 字号 | font_size | `Body_L` | 16 | 16 |
| 字重 | font_weight | `font_weight_medium` | 500 | 500 |
| 文字色 | font_color | `font_emphasize` | `#FF0A59F7` | `#FF5291FF` |
| 背景色 | container_color | `comp_background_tertiary` | `#0C000000` | `#19FFFFFF` |
| 文字对齐 | font_alignment | `alignment_center` | Center | Center |

### 其他子样式与状态

通用组件库 Button 控件包含 6 个样式变体（普通 / 强调 / 警告 / 文本 / 小 / 图标）和 6 种交互状态（normal / hover / pressed / focus / disabled / loading）。卡片场景下：

- 列表项右侧以**小按钮**为主用样式（高度 28vp）
- 宫格样式 3「图片 + 文字 + Button」使用**普通按钮**子样式
- 其他样式变体（强调按钮 / 警告按钮等）在卡片场景**未由 UX 明确**——若业务需要使用，参考 `reference/design/harmony-ui-components-a2ui.md` B1.1-B1.6 的完整规格
- 交互状态在卡片内的视觉处理 UX 未明确，但可参考 `reference/design/harmony-ui-components-a2ui.md` B1.5 的 hover/pressed/focus/disabled/loading 标准规格

### A2UI 实现

**原语：** `Extended.Button`（Direct）

**Props：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `label` | string | 按钮文本 ✅ |
| `enabled` | boolean | 是否可点击，对应 Normal/Disabled |

**JSON 示例：**

```json
{
  "styles": {
    "height": 28,
    "borderRadius": 14,
    "backgroundColor": "#0C000000",
    "padding": {
      "left": 8,
      "right": 8,
      "top": 4,
      "bottom": 4
    },
    "fontSize": 14,
    "fontWeight": 500
  },
  "component": "Extended.Button",
  "label": "立即购买",
  "enabled": true
}
```

> 注：上例采用 Light 值。Dark 模式工程层应通过语义 token 引用自动切换（如背景色绑定 `comp_background_tertiary` → Dark 自动取 `#19FFFFFF`）。

**🔴 实现 Gap：**
1. `Extended.Button` **fontColor 协议待确认** — UX 规范层面 font_color 绑定 `font_emphasize`（Light `#FF0A59F7` / Dark `#FF5291FF`），但 A2UI 当前节选未列出 Button 可用 `fontColor`。需工程确认协议是否补充；确认前不要伪造字段。

---

## B2 · Tag 标签

> **A2UI 原语：** `Extended.Text`（Composed — 靠 `borderWidth` + `padding` + `backgroundColor` 合成，A2UI 无 Tag 组件）
> Light 模式为线性标签（描边）· Dark 模式为面性标签（填充）· 排序标签为特殊类型 · 固定 16vp 高

### B2.1 线性标签（Linear Label）— Light 模式主样式

#### 组合 1 — 营销属性（描边与文本同色）

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">
  <rect x="1" y="12" width="78" height="16" rx="4" ry="4" fill="none" stroke="#E84026" stroke-width="1"/>
  <text x="40" y="24" text-anchor="middle" font-family="sans-serif" font-size="10" font-weight="500" fill="#E84026">1070人收藏</text>
</svg>
```

| 项 | Token | 值 |
|---|---|---|
| 描边颜色 | `multi_color_08` | Light `#E84026` / Dark `#D94838` |
| 文本颜色 | `multi_color_08` | Light `#E84026` / Dark `#D94838` |
| 背景 | 透明 | — |

**用途：** 营销、品类强调（"限时"、"热门"、"新品"）

#### 组合 2 — 中性说明（中性描边 + 主文本色）

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">
  <rect x="1" y="12" width="56" height="16" rx="4" ry="4" fill="none" stroke="#66000000" stroke-width="1"/>
  <text x="29" y="24" text-anchor="middle" font-family="sans-serif" font-size="10" font-weight="500" fill="#E5000000">赠积分</text>
</svg>
```

| 项 | Token | 值 |
|---|---|---|
| 描边颜色 | `container40` | Light `#66000000` / Dark `#66FFFFFF`（40% alpha）|
| 文本颜色 | `font_primary` | Light `#E5000000` / Dark `#E5FFFFFF`（90% alpha）|
| 背景 | 透明 | — |

**用途：** 中性说明、功能标注（"赠积分"、"免邮"、"7 天退换"）

### B2.2 面性标签（Facial Label）— Dark 模式唯一样式

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40" viewBox="0 0 160 40">
  <rect width="160" height="40" fill="#2E3033"/>
  <rect x="6" y="12" width="56" height="16" rx="4" ry="4" fill="#33FFFFFF"/>
  <text x="34" y="24" text-anchor="middle" font-family="sans-serif" font-size="10" font-weight="500" fill="#FFFFFF">赠积分</text>
</svg>
```

| 项 | Token | 值 |
|---|---|---|
| 背景颜色 | `container20`（Dark） | `#33FFFFFF`（20% alpha 白）|
| 文本颜色 | `font_primary`(Dark) | `#E5FFFFFF`（90% alpha 白）|
| 描边 | 无 | — |

**适用模式：**
- Dark 模式：所有标签的**唯一**样式（规范原文）
- Light 模式：⚠️ 规范说"多为线性标签"，暗示 Light 下面性标签可作为补充，但何时使用未明确

### B2.3 排序标签（Sorting Tags）⚠️

规范仅在类型列表中列出名字，示意图用数字"1"展示，其余全部待 UX 补充。

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="220" height="50" viewBox="0 0 220 50">
  <rect x="8" y="8" width="32" height="32" rx="4" ry="4" fill="none" stroke="#F9A01E" stroke-dasharray="3 3" stroke-width="1"/>
  <text x="24" y="30" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="600" fill="#333">1</text>
  <text x="55" y="22" font-family="sans-serif" font-size="10" fill="#99000000">排序标签（SORTING TAGS）</text>
  <text x="55" y="36" font-family="sans-serif" font-size="10" fill="#99000000">规格全部 ⚠️</text>
</svg>
```

**🔴 需 UX 明确的策略问题：** 排序标签 vs B3 列表左侧排序数字 —— 是否同一个东西？

### B2.4 通用规格（线性/面性共用）

| 属性 | 值 |
|---|---|
| 高度（固定） | 16vp |
| 左右内边距 | 4vp |
| 最大宽度 | 68vp |
| 字号 | Caption_M（10vp） |
| 字重 | Medium |
| 圆角 | 4vp |
| 描边粗细（内描边） | 1vp |
| 文字上限 | 6 汉字 / 12 英文，超长 "..." 截断 |

### B2.5 布局规则

- **单标签：** 与副文本同行，放在副文本**前**
- **多标签：** 单独成行，放在副文本**下方**

### B2.6 A2UI 实现

**原语：** `Extended.Text`（Composed — A2UI 无 Tag 组件，用 Text + border/padding 合成）

**JSON 示例 — 组合 1（Light 线性，营销）：**

```json
{
  "styles": {
    "height": 16,
    "padding": {
      "left": 4,
      "right": 4
    },
    "constraintSize": {
      "maxWidth": 68
    },
    "borderWidth": 1,
    "borderRadius": 4,
    "borderColor": "#E84026",
    "fontSize": 10,
    "fontWeight": 500,
    "fontColor": "#E84026",
    "textOverflow": "ellipsis",
    "maxLines": 1
  },
  "component": "Extended.Text",
  "content": "1070人收藏"
}
```

**JSON 示例 — Dark 面性：**

```json
{
  "styles": {
    "height": 16,
    "padding": {
      "left": 4,
      "right": 4
    },
    "constraintSize": {
      "maxWidth": 68
    },
    "borderRadius": 4,
    "backgroundColor": "#33FFFFFF",
    "fontSize": 10,
    "fontWeight": 500,
    "fontColor": "#FFFFFF",
    "textOverflow": "ellipsis",
    "maxLines": 1
  },
  "component": "Extended.Text",
  "content": "赠积分"
}
```

**🔴 实现 Gap：**
1. Text 在 16vp 高容器内的垂直居中 — 可能需要外层 Stack 包裹
2. `borderWidth` 是否为内描边（不撑大元素）— 待工程确认

---

## B3 · Sort Number 列表排序数字

> **A2UI 原语：** `Extended.Text`（Composed — 仅使用 `fontColor` 按名次切换）
> 列表项左侧的排名数字 · 榜单 / 排行 / 搜索结果场景 · NO.1-3 用品牌色，NO.4+ 用副文本色

### 榜单示意 — 前三名高亮

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="40" viewBox="0 0 300 40">
  <text x="10" y="27" font-family="sans-serif" font-size="20" font-weight="500" fill="#FF0A59F7">1</text>
  <text x="50" y="27" font-family="sans-serif" font-size="20" font-weight="500" fill="#FF0A59F7">2</text>
  <text x="90" y="27" font-family="sans-serif" font-size="20" font-weight="500" fill="#FF0A59F7">3</text>
  <text x="130" y="27" font-family="sans-serif" font-size="20" font-weight="500" fill="#99000000">4</text>
  <text x="170" y="27" font-family="sans-serif" font-size="20" font-weight="500" fill="#99000000">5</text>
  <text x="210" y="18" font-family="sans-serif" font-size="10" fill="#99000000">前 3 品牌色</text>
  <text x="210" y="32" font-family="sans-serif" font-size="10" fill="#99000000">4+ font_secondary</text>
</svg>
```

### 规格

| 属性 | 值 |
|---|---|
| 元素尺寸 | 20 × 24vp |
| 与中间元素间距 | 8vp（比其他左侧类型的通用 12vp 更紧凑） |

### 颜色规则

| 名次 | 颜色 | 说明 |
|---|---|---|
| NO.1 – NO.3 | "可自定义品牌色" | ✅ 规范；⚠️ 具体取值来源未明确 |
| NO.4 及之后 | `font_secondary` (`#99000000`) | ✅ |

### 使用约束

- **仅用于列表项左侧**
- 同一列表内所有列表项结构需保持一致
- 与中间元素间距 **8vp**（不是通用 12vp）——这是排序数字的专属规则

### A2UI 实现

**原语：** `Extended.Text`（Composed）

**JSON 示例 — NO.1（品牌色）：**

```json
{
  "styles": {
    "width": 20,
    "height": 24,
    "fontColor": "#FF0A59F7",
    "fontSize": 20,
    "fontWeight": 500,
    "textAlign": "center"
  },
  "component": "Extended.Text",
  "content": "1"
}
```

**JSON 示例 — NO.4（次要色）：**

```json
{
  "styles": {
    "width": 20,
    "height": 24,
    "fontColor": "#99000000",
    "fontSize": 20,
    "fontWeight": 500,
    "textAlign": "center"
  },
  "component": "Extended.Text",
  "content": "4"
}
```

> ⚠️ 字号 20fp 是按元素尺寸推测；"可自定义品牌色"取值来源待 UX 明确。

---

## B4 · Icon with Background 图标+背板

> **A2UI 原语：** `Extended.Stack` + `Extended.Image`（Composed — Stack 作背板，Image 作图标内容）
> 圆形背板包裹图标 · 左侧图标（48vp）/ 右侧可操作图标（40vp）两种尺寸 · 颜色层级不同

### B4.1 左侧图标 — 列表项左侧

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="70" viewBox="0 0 300 70">
  <rect x="6" y="6" width="48" height="48" rx="24" ry="24" fill="#0C000000"/>
  <circle cx="30" cy="30" r="10" fill="none" stroke="#99000000" stroke-width="2"/>
  <line x1="37" y1="37" x2="42" y2="42" stroke="#99000000" stroke-width="2" stroke-linecap="round"/>
  <text x="75" y="22" font-family="sans-serif" font-size="11" fill="#E5000000">背板 48×48vp · 圆角 24vp</text>
  <text x="75" y="40" font-family="sans-serif" font-size="10" fill="#99000000">图标 24×24vp · icon_secondary</text>
  <text x="75" y="55" font-family="sans-serif" font-size="10" fill="#99000000">背板 comp_background_tertiary</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 背板尺寸 | 48 × 48vp |
| 背板圆角 | 24vp（胶囊形） |
| 图标尺寸 | 24 × 24vp |
| 背板颜色 | `comp_background_tertiary` (`#0C000000`) |
| 图标颜色 | `icon_secondary` (`#99000000`) |

**典型场景：** 分类图标、默认头像、服务入口图标

### B4.2 右侧可操作图标 — 列表项右侧

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="70" viewBox="0 0 300 70">
  <rect x="6" y="14" width="40" height="40" rx="20" ry="20" fill="#0C000000"/>
  <circle cx="26" cy="34" r="8" fill="none" stroke="#E5000000" stroke-width="2"/>
  <rect x="54" y="14" width="40" height="40" rx="20" ry="20" fill="#0C000000"/>
  <path d="M 68 28 L 80 40 M 80 28 L 68 40" stroke="#E5000000" stroke-width="2" stroke-linecap="round"/>
  <text x="110" y="22" font-family="sans-serif" font-size="11" fill="#E5000000">背板 40×40vp</text>
  <text x="110" y="38" font-family="sans-serif" font-size="10" fill="#99000000">图标 24×24vp · icon_primary</text>
  <text x="110" y="53" font-family="sans-serif" font-size="10" fill="#99000000">最多 2 个 · 间距 8vp</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 背板尺寸 | 40 × 40vp |
| 背板圆角 | ⚠️ 规范未明确（推测 20 或 24vp） |
| 图标尺寸 | 24 × 24vp |
| 背板颜色 | `comp_background_tertiary` (`#0C000000`) |
| 图标颜色 | `icon_primary` (`#E5000000`) |
| 数量上限 | 2 |
| 图标之间间距 | 8vp |

### B4.3 差异小结

| 维度 | 左侧 | 右侧 |
|---|---|---|
| 背板尺寸 | 48 | 40 |
| 图标颜色语义 | `icon_secondary`（信息展示） | `icon_primary`（可操作） |
| 数量 | 1 | 1-2 |
| 圆角 | 24vp ✅ | ⚠️ 待确认 |

### B4.4 A2UI 实现

**原语：** `Extended.Stack` + `Extended.Image`（Composed）

**JSON — 左侧图标（48×48 背板 + 24×24 图标）：**

```json
{
  "styles": {
    "width": 48,
    "height": 48,
    "borderRadius": 24,
    "backgroundColor": "#0C000000",
    "alignContent": "center"
  },
  "component": "Extended.Stack",
  "children": [
    "icon_content_id"
  ]
}
```

子组件 `icon_content_id`：

```json
{
  "id": "icon_content_id",
  "styles": {
    "width": 24,
    "height": 24
  },
  "component": "Extended.Image",
  "src": "<图标资源>"
}
```

**JSON — 右侧双图标（40×40 背板 + 间距 8vp）：**

```json
{
  "styles": {
    "space": 8,
    "alignItems": "center"
  },
  "component": "Extended.Row",
  "children": [
    "icon_bg_1",
    "icon_bg_2"
  ]
}
```

每个 `icon_bg_*` 同左侧结构，但 `width: 40, height: 40, borderRadius: ⚠️`。

**🔴 实现 Gap：**
1. **Image 无图标着色字段** — `Extended.Image` 没有 tintColor，`icon_secondary`/`icon_primary` 色值无法通过样式设置。方案 A：素材层做多套；方案 B：工程有未列出的 tint 能力；方案 C：改用矢量图标组件。**阻塞级，必须和工程对齐。**
2. Stack + Image 重复出现 — skill prompt 层封装为复合模板。

---

## B5 · Image 图片

> **A2UI 原语：** `Extended.Image`（Direct）
> 列表左侧图片 · Card_Name 应用图标 · 宫格图片 · 共 5 种使用场景，尺寸和圆角各不相同

### B5.1 场景 1 — 列表左侧应用图标 / 1:1 图片

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="70" viewBox="0 0 280 70">
  <rect x="6" y="6" width="56" height="56" rx="12" ry="12" fill="#0C000000"/>
  <rect x="20" y="20" width="28" height="28" rx="6" ry="6" fill="#FF0A59F7" opacity="0.4"/>
  <text x="80" y="22" font-family="sans-serif" font-size="11" fill="#E5000000">56 × 56vp · 圆角 12vp</text>
  <text x="80" y="40" font-family="sans-serif" font-size="10" fill="#99000000">应用图标 / 1:1 图片</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 尺寸 | 56 × 56vp |
| 圆角 | 12vp |

### B5.2 场景 2 — 列表左侧竖向特殊比例图片

| 属性 | 值 |
|---|---|
| 宽度（最大） | 56vp |
| 高度 | 自适应（高度 > 宽度） |
| 圆角 | 12vp |

**典型场景：** 电影海报、书籍封面、短视频竖封面

### B5.3 场景 3 — Card_Name 应用图标

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="40" viewBox="0 0 280 40">
  <rect x="6" y="10" width="20" height="20" rx="4" ry="4" fill="#FF0A59F7"/>
  <text x="36" y="18" font-family="sans-serif" font-size="11" fill="#E5000000">20 × 20vp · 圆角 4vp</text>
  <text x="36" y="32" font-family="sans-serif" font-size="10" fill="#99000000">位于 Card_Name 最左</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 尺寸 | 20 × 20vp |
| 圆角 | 4vp |

### B5.4 场景 4 — 宫格样式 3 固定图片

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="70" viewBox="0 0 280 70">
  <rect x="6" y="11" width="48" height="48" rx="12" ry="12" fill="#0C000000"/>
  <rect x="20" y="25" width="20" height="20" rx="4" ry="4" fill="#64BB5C" opacity="0.5"/>
  <text x="70" y="22" font-family="sans-serif" font-size="11" fill="#E5000000">48 × 48vp（固定）</text>
  <text x="70" y="38" font-family="sans-serif" font-size="10" fill="#99000000">圆角 12vp · 不随宫格宽度自适应</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 尺寸（固定） | 48 × 48vp |
| 圆角 | 12vp |

**约束：** 与宫格样式 1/2 不同，样式 3 的图片尺寸**固定**，宫格项宽度变化不影响图片尺寸。

### B5.5 场景 5 — 宫格样式 1 / 2 图片

| 属性 | 值 |
|---|---|
| 比例（样式 1 纯图片） | 1:1 / 3:4 / 4:3 / 9:16 |
| 比例（样式 2 图文） | 跟随样式 1 的比例规则 |
| 圆角（宫格项宽度 ≤ 96vp） | 8vp |
| 圆角（宫格项宽度 > 96vp） | 12vp |

### B5.6 加载状态 ⚠️

| 状态 | 规则 |
|---|---|
| 加载中 | ⚠️ 骨架屏 / spinner？ |
| 加载失败 | ⚠️ 占位图？文字提示？ |
| 图片源为空 | ⚠️ 跳过？默认图？降级为图标背板？ |

### B5.7 A2UI 实现

**原语：** `Extended.Image`（Direct）

**JSON — 场景 1（列表左侧 56×56）：**

```json
{
  "styles": {
    "width": 56,
    "height": 56,
    "borderRadius": 12,
    "objectFit": "cover"
  },
  "component": "Extended.Image",
  "src": "<图片 URL>"
}
```

**JSON — 场景 5（宫格 1:1 自适应）：**

```json
{
  "styles": {
    "width": "matchParent",
    "aspectRatio": 1,
    "borderRadius": 8,
    "objectFit": "cover"
  },
  "component": "Extended.Image",
  "src": "<图片 URL>"
}
```

> `aspectRatio` 取值：1（1:1）/ 0.75（3:4）/ 1.333（4:3）/ 0.5625（9:16）

**🔴 实现 Gap：** Image 加载中 / 失败占位 — A2UI 未列出 placeholder 字段，可能需要 Stack + If 条件分支 workaround。

---

## B6 · Arrow Trailing 可操作文本+箭头

> **A2UI 原语：** `Extended.Row` + `Extended.Text` + `Extended.Image`（Composed — Row 控制文本-箭头间距 4vp）
> 点击跳转的视觉提示 · 列表项右侧 / Card_Name 右侧两种场景 · 箭头尺寸和颜色层级不同

### B6.1 场景 1 — 列表项右侧（扁形箭头）

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="40" viewBox="0 0 300 40">
  <text x="6" y="25" font-family="sans-serif" font-size="14" fill="#99000000">查看全部</text>
  <path d="M 80 14 L 86 20 L 80 26" fill="none" stroke="#33000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="110" y="18" font-family="sans-serif" font-size="10" fill="#99000000">箭头 12×24vp（扁形）</text>
  <text x="110" y="32" font-family="sans-serif" font-size="10" fill="#99000000">间距 4vp · icon_fourth</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 箭头尺寸 | 12 × 24vp（扁形） |
| 文本-箭头间距 | 4vp |
| 文本字号 | Body_M（14vp） |
| 文本字重 | regular |
| 文本颜色 | `font_secondary` (`#99000000`) |
| 箭头颜色 | `icon_fourth` (`#33000000`，最淡级) |

**典型用法：** "查看全部"、"更多"、"下一步"

### B6.2 场景 2 — Card_Name 右侧（等比箭头）

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="40" viewBox="0 0 300 40">
  <text x="6" y="25" font-family="sans-serif" font-size="12" fill="#99000000">进入详情</text>
  <path d="M 66 14 L 74 20 L 66 26" fill="none" stroke="#66000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="95" y="18" font-family="sans-serif" font-size="10" fill="#99000000">箭头 20vp · ic_public_arrow_right</text>
  <text x="95" y="32" font-family="sans-serif" font-size="10" fill="#99000000">间距 4vp · icon_tertiary</text>
</svg>
```

| 属性 | 值 |
|---|---|
| 箭头图标（指定 ID） | `ic_public_arrow_right` |
| 箭头尺寸 | 20vp |
| 文本-箭头间距 | 4vp |
| 文本字号 | Caption_L（12vp） |
| 文本字重 | regular |
| 文本颜色 | `font_secondary` (`#99000000`) |
| 箭头颜色 | `icon_tertiary` (`#66000000`) |

### B6.3 差异小结

| 维度 | 列表项右侧 | Card_Name 右侧 |
|---|---|---|
| 箭头尺寸 | 12×24vp（扁） | 20vp（等比） |
| 箭头颜色 | `icon_fourth`（最淡） | `icon_tertiary` |
| 文本字号 | Body_M（14vp） | Caption_L（12vp） |
| 图标 ID | ⚠️ 未指定 | `ic_public_arrow_right` |

### B6.4 A2UI 实现

**原语：** `Extended.Row` + `Extended.Text` + `Extended.Image`（Composed）

**JSON — 场景 1（列表项右侧）：**

```json
{
  "styles": {
    "space": 4,
    "alignItems": "center"
  },
  "component": "Extended.Row",
  "children": [
    "arrow_text",
    "arrow_icon"
  ]
}
```

```json
{
  "id": "arrow_text",
  "styles": {
    "fontSize": 14,
    "fontWeight": 400,
    "fontColor": "#99000000"
  },
  "component": "Extended.Text",
  "content": "查看全部"
}
```

```json
{
  "id": "arrow_icon",
  "styles": {
    "width": 12,
    "height": 24
  },
  "component": "Extended.Image",
  "src": "<扁形箭头素材>"
}
```

**🔴 实现 Gap：**
1. Image 无着色字段（同 B4） — `icon_tertiary` / `icon_fourth` 色值无法通过样式设置
2. `ic_public_arrow_right` 能否作为 Image `src` — 工程需确认是否支持鸿蒙系统资源 ID

---

# Part C · 卡片布局规范

> UX《生成式卡片规则》原文第 2 节的完整复刻。说明卡片骨架、Card_Name、CARD_CONTENT_LIST、CARD_CONTENT_GRID、场景差异。组件规格已在 Part B 展开，本 Part 聚焦"组件间如何组合成卡片"。

## C1 · 卡片整体结构

### C1.1 统一包裹要求

卡片内所有 UI 元素由一个**统一的最外层视觉容器**清晰包裹。

### C1.2 两大区域

```
卡片（SPEC_CARD_STRUCTURE_AND_APPEARANCE）
 ├── Card_Name（顶部，卡片名称区域，可选）
 └── CARD_CONTENT（底部，内容区域，必选）
        ├── CARD_CONTENT_LIST（列表布局）
        └── CARD_CONTENT_GRID（宫格布局）
```

Card_Name 是否出现由数据推理：若输入数据带有明确应用、服务、品牌或技能来源，则显示 Card_Name；若没有具体来源，则省略 Card_Name，卡片直接展示 CARD_CONTENT。

### C1.3 最大宽度（场景差异）

| 场景 | 左右安全边距 | 最大宽度 |
|---|---|---|
| OnAPP（小艺对话内嵌） | 12vp + 12vp | 对话面板宽度 − 24vp |
| APP | 24vp + 24vp | 对话面板宽度 − 48vp |

### C1.4 容器材质与待确认项

| 项 | 状态 |
|---|---|
| 最外层容器背景色 / 底板材质 | `comp_background_list_card`（Light `#FFFFFFFF` / Dark `#19FFFFFF`） |
| 最外层容器阴影 | ⚠️ |
| 最外层容器边框 | ⚠️ |
| Card_Name 与 CARD_CONTENT 之间的垂直间距 | ⚠️ |

---

## C2 · Card_Name 区域

> 手机设备 > 小艺对话出现的卡片，若显示卡片名称时适用。Card_Name **非必需**：当输入数据中存在明确的应用来源、服务来源、品牌/技能名称等可识别来源时生成；没有具体来源时不生成 Card_Name，卡片直接由 `CARD_CONTENT` 起始。

### C2.1 布局

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="90" viewBox="0 0 600 90">
  <!-- 外容器 -->
  <rect x="10" y="10" width="540" height="40" rx="4" ry="4" fill="none" stroke="#99000000" stroke-dasharray="2 2" stroke-width="0.5"/>
  <!-- 应用图标 -->
  <rect x="22" y="20" width="20" height="20" rx="4" ry="4" fill="#FF0A59F7"/>
  <!-- 应用名称 -->
  <text x="50" y="34" font-family="sans-serif" font-size="12" fill="#E5000000">服务名称</text>
  <!-- 右侧文本 -->
  <text x="470" y="34" text-anchor="end" font-family="sans-serif" font-size="12" fill="#99000000">右侧文本</text>
  <!-- 右箭头 -->
  <path d="M 480 26 L 488 30 L 480 34" fill="none" stroke="#66000000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- 间距标注 -->
  <text x="12" y="68" font-family="sans-serif" font-size="10" fill="#E84026">12</text>
  <text x="44" y="68" font-family="sans-serif" font-size="10" fill="#E84026">20</text>
  <text x="68" y="68" font-family="sans-serif" font-size="10" fill="#E84026">8</text>
  <text x="466" y="68" font-family="sans-serif" font-size="10" fill="#E84026">8</text>
  <text x="490" y="68" font-family="sans-serif" font-size="10" fill="#E84026">4</text>
  <text x="515" y="68" font-family="sans-serif" font-size="10" fill="#E84026">12</text>

  <text x="10" y="84" font-family="sans-serif" font-size="10" fill="#999">Card_Name 高度 40vp · 左右间距 12vp · 图标 20vp · 图标-名称 8vp · 左右区域 8vp · 文本-箭头 4vp</text>
</svg>
```

### C2.2 区域划分

| 区域 | 内容 | 条件 |
|---|---|---|
| 左侧元素 | 应用图标 + 应用名称 | Card_Name 存在时必选；Card_Name 本身由数据来源决定是否生成 |
| 右侧元素 | 文本 + 右箭头图标 | 需要卡片跳转时必选，否则隐藏 |

### C2.3 尺寸与间距

| 项 | 值 |
|---|---|
| Card_Name 高度 | 40vp |
| 左右间距 | 12vp |
| 应用图标与应用名称间距 | 8vp |
| 文本与右箭头图标间距 | 4vp |
| 左侧区域与右侧区域间距（两者都存在时） | 8vp |
| 应用名称到卡片右间距（无右侧区域时） | 12vp |

### C2.4 元素规格

**左侧元素：**

| 元素 | 尺寸 | 圆角 | 字号 | 字重 | 颜色 |
|---|---|---|---|---|---|
| 应用图标 | 20 × 20vp | 4vp | — | — | — |
| 应用名称 | — | — | Body_S（12vp） | regular | `font_primary` (`#E5000000`) |

**右侧元素：**

| 元素 | 尺寸 | 字号 | 字重 | 颜色 |
|---|---|---|---|---|
| 文本 | — | Caption_L（12vp） | regular | `font_secondary` (`#99000000`) |
| 右箭头图标（`ic_public_arrow_right`） | 20vp | — | regular | `icon_tertiary` (`#66000000`) |

### C2.5 组件引用

- 应用图标 → Part B · B5 Image 场景 3
- 右侧文本 + 箭头 → Part B · B6 Arrow Trailing 场景 2

### C2.6 A2UI 结构

仅当 Card_Name 存在时生成以下结构；无明确应用/服务来源时，不生成 `card_name` 节点，也不要为空占位。

```json
{
  "styles": {
    "height": 40,
    "padding": {
      "left": 12,
      "right": 12
    },
    "justifyContent": "spaceBetween",
    "alignItems": "center"
  },
  "component": "Extended.Row",
  "children": [
    "card_name_left",
    "card_name_right"
  ]
}
```

左侧 `Extended.Row` 包含图标 + 应用名称（`space: 8`）；右侧 `Extended.Row` 包含文本 + 箭头（`space: 4`）。

---

## C3 · CARD_CONTENT 内容区域

### C3.1 两种布局类型

| 布局 ID | 适用场景 |
|---|---|
| `CARD_CONTENT_LIST` | 纵向连续、多行呈现同类数据（列表项 ≥ 1，相同宽度） |
| `CARD_CONTENT_GRID` | 横向 + 纵向多行同类数据（宫格项 ≥ 1，同宽同高），**必须包含图片或视频封面** |

### C3.2 容器尺寸

| 项 | 值 |
|---|---|
| CARD_CONTENT 高度 | 自适应 |
| CARD_CONTENT_LIST 列表项数目 | ≤ 4 |
| CARD_CONTENT 左右内边距 | 12vp |
| 最大宽度 | 336vp |

### C3.3 结构一致性约束

- 同一列表内，所有列表项结构必须统一
- 同一宫格内，所有宫格项必须同宽同高

### C3.4 A2UI 容器

```json
{
  "styles": {
    "padding": {
      "left": 12,
      "right": 12
    },
    "constraintSize": {
      "maxWidth": 336
    }
  },
  "component": "Extended.Column",
  "children": [
    "list_or_grid_container"
  ]
}
```

---

## C4 · CARD_CONTENT_LIST 列表布局

> 列表项（CARD_CONTENT_LIST_ITEM）左/中/右三段式结构 · 列表项数目 ≤ 4 · 结构必须统一

### C4.1 列表项整体布局

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="90" viewBox="0 0 600 90">
  <!-- 左侧 -->
  <rect x="12" y="12" width="56" height="56" rx="12" ry="12" fill="#0C000000"/>
  <text x="40" y="45" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">左侧</text>

  <!-- 中间 -->
  <rect x="80" y="20" width="340" height="18" fill="#E5000000" opacity="0.1"/>
  <rect x="80" y="42" width="260" height="14" fill="#99000000" opacity="0.1"/>
  <text x="250" y="72" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">中间元素（可多行）</text>

  <!-- 右侧 -->
  <rect x="470" y="22" width="60" height="28" rx="14" ry="14" fill="#FF0A59F7" opacity="0.3"/>
  <text x="500" y="72" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">右侧</text>

  <!-- 间距标注 -->
  <text x="70" y="86" font-family="sans-serif" font-size="10" fill="#E84026">12</text>
  <text x="425" y="86" font-family="sans-serif" font-size="10" fill="#E84026">12</text>
</svg>
```

**间距规则：**
- 一般情况各元素间隔 **12vp**
- 左侧元素为**排序数字**时，与中间元素间隔 **8vp**

**结构一致性：** 同一列表内所有列表项结构必须统一。

**中间区扩展：** 中间元素可与标签混排，标签排列见 Part B · B2.5。

### C4.2 左侧元素（5 种类型）

| 类型 | 尺寸 | 圆角 | 颜色 | 引用组件 |
|---|---|---|---|---|
| 排序数字 | 20 × 24vp | — | NO.1-3：品牌色；NO.4+：`font_secondary` | B3 |
| 图标（含背板） | 背板 48×48 / 图标 24×24 | 背板 24 | 背板 `comp_background_tertiary` / 图标 `icon_secondary` | B4（左侧） |
| 应用图标 | 56 × 56vp | 12vp | — | B5 场景 1 |
| 1:1 图片 | 56 × 56vp | 12vp | — | B5 场景 1 |
| 竖向特殊比例图片 | 宽度最大 56vp | 12vp | — | B5 场景 2 |

### C4.3 中间元素（3 种样式）

#### 样式 1 · 单行列表

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="60" viewBox="0 0 600 60">
  <rect x="10" y="10" width="580" height="48" fill="#F5F5F5" opacity="0.3"/>
  <text x="20" y="42" font-family="sans-serif" font-size="16" font-weight="500" fill="#E5000000">单行列表</text>
  <text x="10" y="10" font-family="sans-serif" font-size="9" fill="#E84026">最小 48vp · 上下安全边距 8vp</text>
</svg>
```

| 项 | 值 |
|---|---|
| 最小高度 | 48vp |
| 上下安全边距 | 8vp |
| 第一行 | Body_L（16vp）/ Medium / `font_primary` |

#### 样式 2 · 双行列表

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="74" viewBox="0 0 600 74">
  <rect x="10" y="5" width="580" height="64" fill="#F5F5F5" opacity="0.3"/>
  <text x="20" y="30" font-family="sans-serif" font-size="16" font-weight="500" fill="#E5000000">双行列表</text>
  <text x="20" y="54" font-family="sans-serif" font-size="14" fill="#99000000">辅助文本</text>
  <text x="10" y="5" font-family="sans-serif" font-size="9" fill="#E84026">最小 64vp · 行间距 2vp · 上下安全边距 8vp</text>
</svg>
```

| 项 | 值 |
|---|---|
| 最小高度 | 64vp |
| 上下安全边距 | 8vp |
| 两行文本间隔 | 2vp |
| 第一行 | Body_L（16vp）/ Medium / `font_primary` |
| 第二行 | Body_M（14vp）/ regular / `font_secondary` |

#### 样式 3 · 多行列表

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="90" viewBox="0 0 600 90">
  <rect x="10" y="5" width="580" height="80" fill="#F5F5F5" opacity="0.3"/>
  <text x="20" y="28" font-family="sans-serif" font-size="16" font-weight="500" fill="#E5000000">多行列表</text>
  <text x="20" y="50" font-family="sans-serif" font-size="14" fill="#99000000">辅助文本</text>
  <text x="20" y="72" font-family="sans-serif" font-size="14" fill="#99000000">辅助文本</text>
  <text x="10" y="5" font-family="sans-serif" font-size="9" fill="#E84026">最小 80vp · 行间距 2vp · 上下安全边距 8vp</text>
</svg>
```

| 项 | 值 |
|---|---|
| 最小高度 | 80vp |
| 上下安全边距 | 8vp |
| 文本之间间隔 | 2vp |
| 第一行 | Body_L（16vp）/ Medium / `font_primary` |
| 第二、三行 | Body_M（14vp）/ regular / `font_secondary` |

### C4.4 右侧元素（3 种样式）

#### 样式 1 · 可操作 Button

引用 Part B · B1 Button（高度 28vp）

#### 样式 1 · 可操作图标（最多 2 个）

引用 Part B · B4 右侧可操作图标（40×40 背板 + 24×24 图标 + 间距 8vp）

#### 样式 2 · 可操作文本 + 箭头

引用 Part B · B6 场景 1（箭头 12×24vp / 间距 4vp / Body_M / `font_secondary` / `icon_fourth`）

### C4.5 A2UI 实现

**容器：** `Extended.List`（推荐）或 `Extended.Column`

```json
{
  "component": "Extended.List",
  "styles": {
    "listDirection": "vertical",
    "scrollBar": "off",
    "space": 0
  },
  "children": ["list_item_0", "list_item_1"]
}
```

> 多条数据时扩展为更多 `list_item_*` 的 `id`，或通过 JSON 绑定与多条 `updateComponents` 对齐；`children` 仅为结构占位。

**单个列表项：** `Extended.Row`（左/中/右三段）

```json
{
  "id": "list_item_0",
  "component": "Extended.Row",
  "styles": {
    "space": 12,
    "alignItems": "center"
  },
  "children": [
    "item_leading",
    "item_middle",
    "item_trailing"
  ]
}
```

**中间元素：** `Extended.Column`（多行文本）

```json
{
  "id": "item_middle",
  "styles": {
    "space": 2,
    "flexShrink": 1
  },
  "component": "Extended.Column",
  "children": [
    "title_text",
    "subtitle_text"
  ]
}
```

### C4.6 List vs Column 的选择

| 原语 | 优点 | 推荐场景 |
|---|---|---|
| `Extended.List` | 语义贴合、支持未来横划扩展 | 3-4 项或未来可能扩展 |
| `Extended.Column` | 使用简单 | 1-2 项稳定场景 |

**默认推荐 `Extended.List`。**

---

## C5 · CARD_CONTENT_GRID 宫格布局

> 宫格项（同宽同高）· **必须包含图片或视频封面** · 强调图片/视频的场景（电影海报、视频封面、图库、壁纸）

### C5.1 布局规则

- 强调图片场景优先
- 横向连续布局超过容器宽度 → **支持手势横划**，此时纵向不排列
- 纵向连续布局 → 不同行横向数目需一致，横向**不支持**横划
- **硬约束：** 同类数据必须包含图片或视频封面，否则降级为列表

### C5.2 间距与圆角

**横向间距：** 视觉上 **8vp 或 12vp** 等效宽度；宽松场景遵循 **4vp 网格规律**（4 + 4n）

**区块内元素内部横向间距：** 视觉上以 **2vp 或 4vp** 为起点

**圆角（按宫格项宽度）：**

| 宫格项宽度 | 圆角 |
|---|---|
| ≤ 96vp | 8vp |
| > 96vp | 12vp |

### C5.3 四种样式

#### 样式 1 · 纯图片

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="140" viewBox="0 0 300 140">
  <rect x="10" y="10" width="80" height="80" rx="8" ry="8" fill="#0C000000"/>
  <rect x="100" y="10" width="80" height="80" rx="8" ry="8" fill="#0C000000"/>
  <rect x="190" y="10" width="80" height="80" rx="8" ry="8" fill="#0C000000"/>
  <text x="140" y="120" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">样式 1 · 纯图片</text>
  <text x="140" y="134" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#99000000">常用比例 1:1 / 3:4 / 4:3 / 9:16</text>
</svg>
```

**比例：** 1:1 / 3:4 / 4:3 / 9:16（常用）

#### 样式 2 · 图片 + 文字

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="180" viewBox="0 0 300 180">
  <rect x="10" y="10" width="80" height="80" rx="8" ry="8" fill="#0C000000"/>
  <text x="10" y="108" font-family="sans-serif" font-size="11" font-weight="500" fill="#E5000000">标题文本</text>
  <text x="10" y="126" font-family="sans-serif" font-size="10" fill="#66000000">辅助文本</text>

  <rect x="100" y="10" width="80" height="80" rx="8" ry="8" fill="#0C000000"/>
  <text x="100" y="108" font-family="sans-serif" font-size="11" font-weight="500" fill="#E5000000">标题文本</text>
  <text x="100" y="126" font-family="sans-serif" font-size="10" fill="#66000000">辅助文本</text>

  <rect x="190" y="10" width="80" height="80" rx="8" ry="8" fill="#0C000000"/>
  <text x="190" y="108" font-family="sans-serif" font-size="11" font-weight="500" fill="#E5000000">标题文本</text>
  <text x="190" y="126" font-family="sans-serif" font-size="10" fill="#66000000">辅助文本</text>

  <text x="140" y="156" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">图文间距 8vp · 标题-辅助 4vp</text>
  <text x="140" y="172" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">标题最多 2 行，超长截断</text>
</svg>
```

**布局：** 宫格项上下布局，文本在图片下方，支持换行，最多 2 行，超长 "..." 截断。文本分为标题文本（必选）和辅助文本。

**尺寸：**
- 图片与文本间隔 8vp
- 标题文本与辅助文本间隔 4vp

**文本样式：**

| 文本 | 字号 | 字重 | 颜色 |
|---|---|---|---|
| 标题文本 | Body_S（12vp） | Medium | `font_primary` (`#E5000000`) |
| 辅助文本 | Caption_L（12vp） | regular | `font_tertiary` (`#66000000`) |

#### 样式 3 · 图片 + 文字 + Button

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="190" viewBox="0 0 300 190">
  <g transform="translate(20,0)">
    <rect x="0" y="10" width="48" height="48" rx="12" ry="12" fill="#0C000000"/>
    <text x="0" y="76" font-family="sans-serif" font-size="11" font-weight="700" fill="#E5000000">文本</text>
    <rect x="0" y="88" width="64" height="40" rx="20" ry="20" fill="#0C000000"/>
    <text x="32" y="113" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#FF0A59F7">Button</text>
  </g>
  <g transform="translate(90,0)">
    <rect x="0" y="10" width="48" height="48" rx="12" ry="12" fill="#0C000000"/>
    <text x="0" y="76" font-family="sans-serif" font-size="11" font-weight="700" fill="#E5000000">文本</text>
    <rect x="0" y="88" width="64" height="40" rx="20" ry="20" fill="#0C000000"/>
    <text x="32" y="113" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#FF0A59F7">Button</text>
  </g>
  <g transform="translate(160,0)">
    <rect x="0" y="10" width="48" height="48" rx="12" ry="12" fill="#0C000000"/>
    <text x="0" y="76" font-family="sans-serif" font-size="11" font-weight="700" fill="#E5000000">文本</text>
    <rect x="0" y="88" width="64" height="40" rx="20" ry="20" fill="#0C000000"/>
    <text x="32" y="113" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#FF0A59F7">Button</text>
  </g>

  <text x="130" y="148" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">图片 48×48 固定 · Button 普通按钮 40vp 高 · 元素间距 4vp</text>
  <text x="130" y="164" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">文本不支持换行 · 宫格项在卡片内等距分布</text>
</svg>
```

**布局：** 宫格项上下布局，Button 在最下方。文本**不支持换行**，超长 "..." 截断。宫格项在卡片宽度内等距分布。

**尺寸：**
- 图片、文本、Button 之间间距 4vp
- 图片尺寸固定 48 × 48vp，圆角 12vp（见 Part B · B5 场景 4）
- Button 使用 `reference/design/harmony-ui-components-a2ui.md` B1.1 **普通按钮**子样式（不是 B1.5 小按钮）
- 普通按钮 normal：高度 40vp，圆角 20vp，左右 padding 16vp，上下 padding 8vp；背景 `comp_background_tertiary`（Light `#0C000000` / Dark `#19FFFFFF`）

**文本样式：**

| 文本 | 字号 | 字重 | 颜色 |
|---|---|---|---|
| 文本 | Caption_L（12vp） | **Bold** (`font_weight_bold` = 700) | `font_primary` (`#E5000000`) |

#### 样式 4 · 视频

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="360" height="150" viewBox="0 0 360 150">
  <rect x="10" y="10" width="150" height="84" rx="12" ry="12" fill="#0C000000"/>
  <path d="M 72 42 L 72 62 L 92 52 Z" fill="#FFFFFFFF"/>
  <text x="85" y="118" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">16:9</text>

  <rect x="190" y="10" width="150" height="64" rx="12" ry="12" fill="#0C000000"/>
  <path d="M 252 32 L 252 52 L 272 42 Z" fill="#FFFFFFFF"/>
  <text x="265" y="118" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#99000000">21:9</text>

  <text x="180" y="140" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#E84026">视频比例固定为 16:9 或 21:9</text>
</svg>
```

**比例：** 16:9 / 21:9。

**布局：** 视频作为宫格项主视觉，可展示视频封面；需要播放入口时可在封面上叠加播放图标。

**A2UI 表达：**
- 视频封面使用 `Extended.Image`，通过 `aspectRatio: 1.778`（16:9）或 `aspectRatio: 2.333`（21:9）表达比例，`objectFit: "cover"`
- 播放图标可用 `Extended.Stack` + `Extended.Image` 叠加在封面中心
- 若需要真正播放视频，A2UI v0.9 当前节选未提供 `Extended.Video`；生成时仅表达封面与点击入口，播放能力交由业务跳转或工程能力承接

### C5.4 A2UI 实现

**容器：** `Extended.Grid`（纵向）或 `Extended.List`（横向横划）

**纵向宫格：**

```json
{
  "component": "Extended.Grid",
  "styles": {
    "columnsTemplate": "1fr 1fr 1fr",
    "columnsGap": 8,
    "rowsGap": 8
  },
  "children": ["grid_item_0", "grid_item_1", "grid_item_2"]
}
```

> 宫格项随数据增减时扩展 `children` 中的 `id` 列表。

**横划宫格（横向超出容器）：**

```json
{
  "component": "Extended.List",
  "styles": {
    "listDirection": "horizontal",
    "scrollBar": "off",
    "space": 8
  },
  "children": ["grid_item_0", "grid_item_1"]
}
```

**宫格项模板 — 样式 2 图文：**

```json
{
  "id": "grid_item_template",
  "styles": {
    "space": 8
  },
  "component": "Extended.Column",
  "children": [
    "image",
    "texts"
  ]
}
```

子组件 `texts`（标题+辅助，间距 4vp）：

```json
{
  "id": "texts",
  "styles": {
    "space": 4
  },
  "component": "Extended.Column",
  "children": [
    "title",
    "caption"
  ]
}
```

### C5.5 宫格列数建议

⚠️ UX 规范未明确推荐列数。agent 可根据图片比例选择：

| 列数 | `columnsTemplate` | 典型宽度（336 容器内） | 圆角 |
|---|---|---|---|
| 1 列 | `"1fr"` | ≈ 336vp | 12vp |
| 2 列 | `"1fr 1fr"` | ≈ 160vp | 12vp |
| 3 列 | `"1fr 1fr 1fr"` | ≈ 104vp | 12vp |
| 4 列 | `"1fr 1fr 1fr 1fr"` | ≈ 76vp | 8vp |
| 5 列 | `"1fr 1fr 1fr 1fr 1fr"` | ≈ 60vp | 8vp |

1:1 图片倾向 3-4 列；3:4 / 9:16 竖图倾向 2-3 列；16:9 / 21:9 视频倾向 1-2 列或横划。

---

## C6 · 完整卡片骨架 JSON 示例

以"Card_Name + CARD_CONTENT_LIST + 双行列表 + 右侧 Button"为例：

```json
{
  "styles": {
    "borderRadius": 16,
    "backgroundColor": "#FFFFFFFF"
  },
  "component": "Extended.Stack",
  "children": [
    "card_name",
    "card_content"
  ]
}
```

```json
{
  "id": "card_name",
  "styles": {
    "height": 40,
    "padding": {
      "left": 12,
      "right": 12
    },
    "justifyContent": "spaceBetween",
    "alignItems": "center"
  },
  "component": "Extended.Row",
  "children": [
    "card_name_left",
    "card_name_right"
  ]
}
```

```json
{
  "id": "card_content",
  "styles": {
    "padding": {
      "left": 12,
      "right": 12
    },
    "constraintSize": {
      "maxWidth": 336
    }
  },
  "component": "Extended.Column",
  "children": [
    "list_container"
  ]
}
```

```json
{
  "id": "list_container",
  "component": "Extended.List",
  "styles": {
    "listDirection": "vertical",
    "scrollBar": "off"
  },
  "children": ["list_item_0", "list_item_1"]
}
```

> 列表行数随数据变化时增加 `list_item_*`；与 `path` / `updateDataModel` 的配合见 `SKILL.md` §0、`schema.md`。

```json
{
  "id": "list_item_0",
  "component": "Extended.Row",
  "styles": {
    "space": 12,
    "alignItems": "center"
  },
  "children": [
    "leading_image",
    "middle_texts",
    "trailing_button"
  ]
}
```
