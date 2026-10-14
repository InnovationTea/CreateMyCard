# HarmonyOS Design Token（Skill 运行时版）

> 鸿蒙系统官方 Design Token 完整目录 · 涵盖 Light 浅色模式和 Dark 深色模式。分为**基础 Token**（原子层）和**语义 Token**（别名层）两层架构。
>
> **本文件角色：** Skill 运行时 token 真理源，供生成阶段查询 token 定义和值。

## 关于 Light / Dark 模式的基本原理

鸿蒙 token 体系下，Light/Dark 的差异主要来自**基础 Token 的值翻转**，语义 Token（别名）的**映射目标在大部分情况下保持不变**（比如 `font_primary` 在两种模式下都是 `primary90`，只是 `primary` 本身从黑变白）。

**核心翻转规则：**

| 基础 Token | Light | Dark |
|---|---|---|
| `primary` | `#000000`（黑） | `#FFFFFF`（白） |
| `container` | `#000000`（黑） | `#FFFFFF`（白） |
| `on_primary` | `#FFFFFF`（白） | `#FFFFFF`（白，不翻转） |

所以 `primary90` 在 Light 下是 `#E5000000`（90% 黑），在 Dark 下是 `#E5FFFFFF`（90% 白）。语义别名 `font_primary` 始终映射到 `primary90`，但具体 RGB 值随模式翻转。

---

## 1. 颜色（Color）

### 1.1 基础 Token — 品牌色（Brand）

品牌蓝：Light `#FF0A59F7` / Dark `#317AF7`（Dark 略浅，保证在深背景上的对比度）

| Token | 描述 | Light 值 | Dark 值 |
|---|---|---|---|
| `brand` | 品牌色基础 | `#FF0A59F7` | `#317AF7` |
| `brand_font` | 文本品牌色 | `#FF0A59F7` | `#5291FF` |
| `brand100` | 品牌色 100% 不透明度 | `#FF0A59F7` | `#FF317AF7` |
| `brand90` | 品牌色 90% 不透明度 | `#E50A59F7` | `#E5317AF7` |
| `brand80` | 品牌色 80% 不透明度 | `#CC0A59F7` | `#CC317AF7` |
| `brand70` | 品牌色 70% 不透明度 | `#B20A59F7` | `#B2317AF7` |
| `brand60` | 品牌色 60% 不透明度 | `#990A59F7` | `#99317AF7` |
| `brand50` | 品牌色 50% 不透明度 | `#7F0A59F7` | `#7F317AF7` |
| `brand40` | 品牌色 40% 不透明度 | `#660A59F7` | `#66317AF7` |
| `brand30` | 品牌色 30% 不透明度 | `#4D0A59F7` | `#4D317AF7` |
| `brand20` | 品牌色 20% 不透明度 | `#330A59F7` | `#33317AF7` |
| `brand15` | 品牌色 15% 不透明度 | `#260A59F7` | `#26317AF7` |
| `brand10` | 品牌色 10% 不透明度 | `#190A59F7` | `#19317AF7` |
| `brand5` | 品牌色 5% 不透明度 | `#0C0A59F7` | `#0C317AF7` |

> 注：Dark 下 `brand_font` (`#5291FF`) 比 `brand` (`#317AF7`) 更浅，专门用于文字场景提升可读性。`font_emphasize` 在 Dark 下映射到 `brand_font` 而非 `brand100`。

### 1.2 基础 Token — 前景色（Primary）

前景色基础值在两种模式下**完全翻转**：

| Token | Light 值 | Dark 值 |
|---|---|---|
| `primary` | `#000000` | `#FFFFFF` |
| `primary100` | `#FF000000` | `#FFFFFFFF` |
| `primary90` | `#E5000000` | `#E5FFFFFF` |
| `primary80` | `#CC000000` | `#CCFFFFFF` |
| `primary70` | `#B2000000` | `#B2FFFFFF` |
| `primary60` | `#99000000` | `#99FFFFFF` |
| `primary50` | `#7F000000` | `#7FFFFFFF` |
| `primary40` | `#66000000` | `#66FFFFFF` |
| `primary30` | `#4D000000` | `#4DFFFFFF` |
| `primary20` | `#33000000` | `#33FFFFFF` |
| `primary15` | `#26000000` | `#26FFFFFF` |
| `primary10` | `#19000000` | `#19FFFFFF` |
| `primary5` | `#0C000000` | `#0CFFFFFF` |

**使用说明：** 用于界面核心文本、图标的颜色。Light 下文字为不同 alpha 的黑色，Dark 下为不同 alpha 的白色。

### 1.3 基础 Token — 前景反色（On Primary）

**两种模式下值完全相同**（反色 = 白色，深浅模式下都适用于强调色 / 品牌色 / 沉浸内容之上的文字）：

| Token | Light 值 | Dark 值 |
|---|---|---|
| `on_primary` | `#FFFFFF` | `#FFFFFF` |
| `on_primary100` | `#FFFFFFFF` | `#FFFFFFFF` |
| `on_primary90` | `#E5FFFFFF` | `#E5FFFFFF` |
| `on_primary80` | `#CCFFFFFF` | `#CCFFFFFF` |
| `on_primary70` | `#B2FFFFFF` | `#B2FFFFFF` |
| `on_primary60` | `#99FFFFFF` | `#99FFFFFF` |
| `on_primary50` | `#7FFFFFFF` | `#7FFFFFFF` |
| `on_primary40` | `#66FFFFFF` | `#66FFFFFF` |
| `on_primary30` | `#4DFFFFFF` | `#4DFFFFFF` |
| `on_primary20` | `#33FFFFFF` | `#33FFFFFF` |
| `on_primary15` | `#26FFFFFF` | `#26FFFFFF` |
| `on_primary10` | `#19FFFFFF` | `#19FFFFFF` |
| `on_primary5` | `#0CFFFFFF` | `#0CFFFFFF` |

### 1.4 基础 Token — 背景色（Container）

背景基础值在两种模式下**完全翻转**：

| Token | Light 值 | Dark 值 |
|---|---|---|
| `container` | `#000000` | `#FFFFFF` |
| `container100` | `#FF000000` | `#FFFFFFFF` |
| `container90` | `#E5000000` | `#E5FFFFFF` |
| `container80` | `#CC000000` | `#CCFFFFFF` |
| `container70` | `#B2000000` | `#B2FFFFFF` |
| `container60` | `#99000000` | `#99FFFFFF` |
| `container50` | `#7F000000` | `#7FFFFFFF` |
| `container40` | `#66000000` | `#66FFFFFF` |
| `container30` | `#4D000000` | `#4DFFFFFF` |
| `container20` | `#33000000` | `#33FFFFFF` |
| `container15` | `#26000000` | `#26FFFFFF` |
| `container10` | `#19000000` | `#19FFFFFF` |
| `container5` | `#0C000000` | `#0CFFFFFF` |

**使用说明：** 用于组件或卡片容器的背景色。在 Light 下是黑色系（搭配白色界面做蒙层 / 半透明叠加），Dark 下是白色系。

### 1.5 基础 Token — 功能色

| Token | 描述 | Light 值 | Dark 值 |
|---|---|---|---|
| `warning` | 警告色 | `#E84026` | `#D94838`（略柔）|
| `alert` | 警示色 | `#ED6F21` | `#DB6B42`（略柔）|
| `confirm` | 通讯色 | `#64BB5C` | `#5BA854`（略深）|
| `black` | 系统默认黑（不随深浅变化） | `#000000` | `#000000` |
| `white` | 系统默认白（不随深浅变化） | `#FFFFFF` | `#FFFFFF` |

### 1.6 基础 Token — 灰阶色

**Light / Dark 下完全翻转** — Light 用浅灰作为界面背景，Dark 用深色：

| Token | 描述 | Light 值 | Dark 值 |
|---|---|---|---|
| `gray_01` | 灰阶色 01 | `#F1F3F5` | `#000000` |
| `gray_02` | 灰阶色 02 | `#E5E5EA` | `#202224` |
| `gray_03` | 灰阶色 03 | `#D1D1D6` | `#2E3033` |
| `gray_04` | 灰阶色 04 | `#C7C7CC` | `#46484D` |

### 1.7 基础 Token — 系统多彩色（高饱和度）

Dark 下整体**降饱和 + 调柔**，保证在深背景上不刺眼：

| Token | Light 值 | Dark 值 |
|---|---|---|
| `multi_color_01` | `#564AF7` | `#5F58C7` |
| `multi_color_02` | `#46B1E3` | `#4796C4` |
| `multi_color_03` | `#61CFBE` | `#5AADA0` |
| `multi_color_04` | `#64BB5C` | `#5BA854` |
| `multi_color_05` | `#A5D61D` | `#86AD53` |
| `multi_color_06` | `#AC49F5` | `#8C55C2` |
| `multi_color_07` | `#E64566` | `#D64966` |
| `multi_color_08` | `#E84026` | `#D94838` |
| `multi_color_09` | `#ED6F21` | `#DB6B42` |
| `multi_color_10` | `#F9A01E` | `#E08C3A` |
| `multi_color_11` | `#F7CE00` | `#D1A738` |

> 注：`multi_color_08 = warning`，值在各自模式下相同。UX《生成式卡片规则》标签规范使用 `multi_color_08` 命名（系统多彩色语义），忠于原文。

### 1.8 基础 Token — 系统多彩色辅助（低饱和度）

| Token | Light 值 | Dark 值 |
|---|---|---|
| `multi_color_aux_01` | `#8981F7` | `#5550A6` |
| `multi_color_aux_02` | `#86C5E3` | `#467794` |
| `multi_color_aux_03` | `#92D6CC` | `#4C7A73` |
| `multi_color_aux_04` | `#92C48D` | `#5C8059` |
| `multi_color_aux_05` | `#BDDB69` | `#6B8052` |
| `multi_color_aux_06` | `#C386F0` | `#634794` |
| `multi_color_aux_07` | `#E67C92` | `#A14A5C` |
| `multi_color_aux_08` | `#E87361` | `#9C554B` |
| `multi_color_aux_09` | `#ED955F` | `#9E644F` |
| `multi_color_aux_10` | `#F9BC64` | `#9E7349` |
| `multi_color_aux_11` | `#F5DC62` | `#997E39` |

### 1.9 语义 Token — 文本色（Font）

| 语义别名 | 描述 | Light 映射 | Dark 映射 |
|---|---|---|---|
| `font_primary` | 一级文本色 | `primary90` → `#E5000000` | `primary90` → `#E5FFFFFF` |
| `font_secondary` | 二级文本色 | `primary60` → `#99000000` | `primary60` → `#99FFFFFF` |
| `font_tertiary` | 三级文本色 | `primary40` → `#66000000` | `primary40` → `#66FFFFFF` |
| `font_fourth` | 四级文本色 | `primary20` → `#33000000` | `primary20` → `#33FFFFFF` |
| `font_emphasize` | 文本高亮色 | `brand100` → `#FF0A59F7` | `brand_font` → `#5291FF` |
| `font_on_primary` | 一级文本反色 | `on_primary100` → `#FFFFFFFF` | `on_primary100` → `#FFFFFFFF` |
| `font_on_secondary` | 二级文本反色 | `on_primary60` → `#99FFFFFF` | `on_primary60` → `#99FFFFFF` |
| `font_on_tertiary` | 三级文本反色 | `on_primary40` → `#66FFFFFF` | `on_primary40` → `#66FFFFFF` |
| `font_on_fourth` | 四级文本反色 | `on_primary20` → `#33FFFFFF` | `on_primary20` → `#33FFFFFF` |

> 📌 `font_emphasize` 的映射目标在 Dark 下从 `brand100` 改为 `brand_font`（更浅的蓝），确保文字在深背景上的可读性。

### 1.10 语义 Token — 图标色（Icon）

| 语义别名 | 描述 | Light 映射 | Dark 映射 |
|---|---|---|---|
| `icon_primary` | 一级图标 | `primary90` → `#E5000000` | `primary90` → `#E5FFFFFF` |
| `icon_secondary` | 二级图标 | `primary60` → `#99000000` | `primary60` → `#99FFFFFF` |
| `icon_tertiary` | 三级图标 | `primary40` → `#66000000` | `primary40` → `#66FFFFFF` |
| `icon_fourth` | 四级图标 | `primary20` → `#33000000` | `primary20` → `#33FFFFFF` |
| `icon_emphasize` | 图标高亮色 | `brand100` → `#FF0A59F7` | `brand_font` → `#5291FF` |
| `icon_sub_emphasize` | 图标高亮辅助 | `brand40` → `#660A59F7` | `brand40` → `#66317AF7` |
| `icon_on_primary` | 一级图标反色 | `on_primary100` → `#FFFFFFFF` | `on_primary100` → `#FFFFFFFF` |
| `icon_on_secondary` | 二级图标反色 | `on_primary60` → `#99FFFFFF` | `on_primary60` → `#99FFFFFF` |
| `icon_on_tertiary` | 三级图标反色 | `on_primary40` → `#66FFFFFF` | `on_primary40` → `#66FFFFFF` |
| `icon_on_fourth` | 四级图标反色 | `on_primary20` → `#33FFFFFF` | `on_primary20` → `#33FFFFFF` |

### 1.11 语义 Token — 背景色（Background · 实色）

**Light 下映射到浅色，Dark 下映射到深色**：

| 语义别名 | Light 映射 | Dark 映射 |
|---|---|---|
| `background_primary` | `white` → `#FFFFFF` | `black` → `#000000` |
| `background_secondary` | `gray_01` → `#F1F3F5` | `gray_01` → `#000000` |
| `background_tertiary` | `gray_02` → `#E5E5EA` | `gray_02` → `#202224` |
| `background_fourth` | `gray_03` → `#D1D1D6` | `gray_03` → `#2E3033` |
| `background_emphasize` | `brand100` → `#FF0A59F7` | `brand100` → `#FF317AF7` |

### 1.12 语义 Token — 组件通用背景色（Comp Background）

**多处 Light/Dark 映射不同**——这是 Dark 模式适配的关键位置：

| 语义别名 | Light 映射 | Dark 映射 |
|---|---|---|
| `comp_background_primary` | `white` → `#FFFFFF` | `gray_02` → `#202224` |
| `comp_background_secondary` | `container10` → `#19000000` | `container10` → `#19FFFFFF` |
| `comp_background_tertiary` | `container5` → `#0C000000` | `container10` → `#19FFFFFF` |
| `comp_background_list_card` | `on_primary100` → `#FFFFFFFF` | `on_primary10` → `#19FFFFFF` |
| `comp_background_primary_contrary` | `white` → `#FFFFFF` | 直接值 → `#E5E5E5` |
| `comp_background_primary_contrary_secondary` | 直接值 → `#FFFFFF` | 直接值 → `#666666` |
| `comp_background_emphasize` | `brand100` → `#FF0A59F7` | `brand100` → `#FF317AF7` |
| `comp_emphasize_secondary` | `brand20` → `#330A59F7` | `brand20` → `#33317AF7` |
| `comp_emphasize_tertiary` | `brand10` → `#190A59F7` | `brand10` → `#19317AF7` |
| `comp_background_gray` | `gray_01` → `#F1F3F5` | `gray_01` → `#000000` |
| `comp_background_gray_secondary` | 直接值 → `#F1F3F5` | 直接值 → `#202224` |
| `comp_background_model_sheet` | 直接值 → `#F1F3F5` | 直接值 → `#202224` |
| `comp_foreground_primary` | `black` → `#000000` | `white` → `#FFFFFF` |
| `comp_common_contrary` | `white` → `#FFFFFF` | `black` → `#000000` |

> **重点说明 · `comp_background_tertiary`（UX 规范图标背板使用）：**
> - Light: `container5` = 5% 黑 (`#0C000000`)
> - Dark: `container10` = 10% 白 (`#19FFFFFF`)
>
> Dark 下提升到 10% alpha 是为了保证背板在深背景上足够可见——5% 白在 Dark 下几乎不可见。

### 1.13 语义 Token — 分割线 / 交互态

| 语义别名 | Light 映射 | Dark 映射 |
|---|---|---|
| `comp_divider` | `container20` → `#33000000` | `container20` → `#33FFFFFF` |
| `interactive_focus` | `brand100` → `#FF0A59F7` | `brand100` → `#FF317AF7` |
| `interactive_hover` | `container5` → `#0C000000` | `container10` → `#19FFFFFF` |
| `interactive_pressed` | `container10` → `#19000000` | `container15` → `#26FFFFFF` |
| `interctive_select` | `brand20` → `#330A59F7` | `brand20` → `#33317AF7` |
| `interactive_click` | `container10` → `#19000000` | `container15` → `#26FFFFFF` |

> 📌 交互态在 Dark 下整体 alpha 上调一档（5% → 10%、10% → 15%），保证可见性。

### 1.14 语义 Token — 其他

| 语义别名 | 描述 | Light 值 | Dark 值 |
|---|---|---|---|
| `border` | 控件描边色 | `#26FFFFFF` | `#26FFFFFF` |
| `fg_color_unchecked` | CheckBox / Radio 初始背景 | `#33FFFFFF` | `#33000000` · 翻转 |

---

## 2. 不透明度和蒙层（Alpha & Mask）

### 2.1 基础 Token — 不透明度（两模式通用）

| Token | 值 |
|---|---|
| `alpha_90` | 0.9 |
| `alpha_66` | 0.6 |
| `alpha_40` | 0.4 |
| `alpha_20` | 0.2 |
| `alpha_10` | 0.1 |
| `alpha_05` | 0.05 |

### 2.2 语义 Token — 信息层级不透明度（两模式通用）

| 语义别名 | 值 | 说明 |
|---|---|---|
| `alpha_primary` | 0.9 | 信息层级 · 一级 |
| `alpha_secondary` | 0.6 | 信息层级 · 二级 |
| `alpha_tertiary` | 0.4 | 信息层级 · 三级 |
| `alpha_fourth` | 0.2 | 信息层级 · 四级 |
| `alpha_fifth` | 0.1 | 信息层级 · 五级 |
| `alpha_sixth` | 0.05 | 信息层级 · 六级 |
| `alpha_disable` | 0.4 | 禁用状态 |
| `interactive_disable` | 0.4 | 交互归一（禁用） |

### 2.3 语义 Token — 蒙层色（Mask · 两模式通用）

蒙层始终用黑色（在浮层场景下始终压暗，无论底层模式）：

| 语义别名 | 值（8 位 ARGB） | 说明 |
|---|---|---|
| `mask_primary` | `#CC000000` | 80% 黑 · 一级蒙层 |
| `mask_secondary` | `#99000000` | 60% 黑 · 二级蒙层 |
| `mask_tertiary` | `#66000000` | 40% 黑 · 三级蒙层 |
| `mask_fourth` | `#33000000` | 20% 黑 · 四级蒙层 |
| `mask_fifth` | `#19000000` | 10% 黑 · 五级蒙层 |
| `mask_sixth` | `#0C000000` | 5% 黑 · 六级蒙层 |

---

## 3. 圆角（Corner Radius · 两模式通用）

### 3.1 基础 Token

| Token | 值（vp） | 场景示例 |
|---|---|---|
| `corner_radius_none` | 0 | 无圆角 |
| `corner_radius_level1` | 2 | — |
| `corner_radius_level2` | 4 | 标签、Card_Name 图标 |
| `corner_radius_level3` | 6 | — |
| `corner_radius_level4` | 8 | 宫格项（≤ 96vp）|
| `corner_radius_level5` | 10 | — |
| `corner_radius_level6` | 12 | 列表图片、宫格项（> 96vp）、应用图标 |
| `corner_radius_level7` | 14 | — |
| `corner_radius_level8` | 16 | 卡片最外层容器 |
| `corner_radius_level9` | 18 | Toast 圆角 |
| `corner_radius_level10` | 20 | Tips、大 Button、普通卡片、输入框、Menu |
| `corner_radius_level11` | 22 | — |
| `corner_radius_level12` | 24 | 图标背板（48×48）|
| `corner_radius_level16` | 32 | — |

---

## 4. 边距 / 间距（Padding · 两模式通用）

### 4.1 基础 Token

| Token | 值（vp） | UX 规范使用场景 |
|---|---|---|
| `padding_level0` | 0 | — |
| `padding_level1` | 2 | 列表行间距 · 宫格内元素内部横向间距起点 |
| `padding_level2` | 4 | Card_Name 文本-箭头 · 宫格文本间距 · 标签左右内边距 |
| `padding_level3` | 6 | — |
| `padding_level4` | 8 | Card_Name 图标-名称 · 排序数字-中间 · 列表上下安全边距 · 宫格图文 · 右侧图标之间 |
| `padding_level5` | 10 | — |
| `padding_level6` | 12 | Card_Name 左右 · CARD_CONTENT 左右 · 列表项左/中/右 · OnAPP 安全边距 |
| `padding_level7` | 14 | — |
| `padding_level8` | 16 | — |
| `padding_level9` | 18 | — |
| `padding_level10` | 20 | — |
| `padding_level11` | 22 | — |
| `padding_level12` | 24 | APP 场景左右安全边距 |

---

## 5. 描边（Border / Outline · 两模式通用）

### 5.1 基础 Token — 内描边

| Token | 值 | 说明 |
|---|---|---|
| `border_none` | 0vp | 无描边 |
| `border_extra_small` | 0.5px | 超小描边 |
| `border_small` | 1px | 小描边 |
| `border_medium` | 2px | 中描边 |
| `border_larger` | 1vp | 大描边（标签 1vp 内描边）|
| `border_extra_larger` | 2vp | 超大描边 |

### 5.2 基础 Token — 外描边

| Token | 值 |
|---|---|
| `outline_none` | 0vp |
| `outline_extra_small` | 0.5px |
| `outline_small` | 1px |
| `outline_medium` | 2px |
| `outline_larger` | 1vp |
| `outline_extra_larger` | 2vp |

---

## 6. 文本（Typography · 两模式通用）

### 6.1 语义 Token — 字号（fp 为单位）

| Token | 值（fp） | 描述 / 使用场景 |
|---|---|---|
| `Display_L` | 56 | 标题 · 大号展示 |
| `Display_M` | 48 | 标题 · 中号展示 |
| `Display_S` | 38 | 标题 · 小号展示 |
| `Title_L` | 30 | 标题 |
| `Title_M` | 24 | 标题栏文本 |
| `Title_S` | 20 | 半模态标题、弹出框标题、滑动选择器选中文本 |
| `Subtitle_L` | 18 | 普通内容子标题、菜单标题 |
| `Subtitle_M` | 16 | 标题栏辅助文本、大按钮文本、列表文本、菜单选项、气泡主标题 |
| `Subtitle_S` | 14 | 小按钮文本、分段按钮、列表子标题、文本选择菜单、普通副标题、页签文本 |
| `Body_L` | 16 | 按钮文本、输入框文本（UX 规范：列表样式 1/2/3 第一行）|
| `Body_M` | 14 | Toast 文本、勾选文本、弹出框正文（UX 规范：列表副文本、可操作文本）|
| `Body_S` | 12 | 图标按钮文本、状态按钮文本、Chips 文本（UX 规范：Card_Name 应用名称、宫格标题）|
| `Caption_L` | 12 | 辅助文本（UX 规范：Card_Name 右侧文本、宫格辅助文本、宫格样式 3 文本）|
| `Caption_M` | 10 | 底部页签文本、工具栏文本、索引条文本（UX 规范：标签文字）|

### 6.2 语义 Token — 字重

| Token | 值 |
|---|---|
| `font_weight_regular` | 400 |
| `font_weight_medium` | 500 |
| `font_weight_bold` | 700 |

### 6.3 语义 Token — 对齐

| Token | 值 |
|---|---|
| `alignment_start` | Start |
| `alignment_center` | Center |
| `alignment_end` | End |
| `alignment_justify` | JUSTIFY |

---

## 7. 通用尺寸（Size · 两模式通用）

### 7.1 基础 Token — 阶梯尺寸

按 2vp 间隔递增，从 0 到 100vp。

| Token | 值（vp） | Token | 值（vp） | Token | 值（vp） |
|---|---|---|---|---|---|
| `size_level0` | 0 | `size_level17` | 34 | `size_level34` | 68 |
| `size_level1` | 2 | `size_level18` | 36 | `size_level35` | 70 |
| `size_level2` | 4 | `size_level19` | 38 | `size_level36` | 72 |
| `size_level3` | 6 | `size_level20` | 40 | `size_level37` | 74 |
| `size_level4` | 8 | `size_level21` | 42 | `size_level38` | 76 |
| `size_level5` | 10 | `size_level22` | 44 | `size_level39` | 78 |
| `size_level6` | 12 | `size_level23` | 46 | `size_level40` | 80 |
| `size_level7` | 14 | `size_level24` | 48 | `size_level41` | 82 |
| `size_level8` | 16 | `size_level25` | 50 | `size_level42` | 84 |
| `size_level9` | 18 | `size_level26` | 52 | `size_level43` | 86 |
| `size_level10` | 20 | `size_level27` | 54 | `size_level44` | 88 |
| `size_level11` | 22 | `size_level28` | 56 | `size_level45` | 90 |
| `size_level12` | 24 | `size_level29` | 58 | `size_level46` | 92 |
| `size_level13` | 26 | `size_level30` | 60 | `size_level47` | 94 |
| `size_level14` | 28 | `size_level31` | 62 | `size_level48` | 96 |
| `size_level15` | 30 | `size_level32` | 64 | `size_level49` | 98 |
| `size_level16` | 32 | `size_level33` | 66 | `size_level50` | 100 |

---

## 8. 材质（Material · Light / Dark 差异较大）

### 8.1 基础 Token

| Token | Light 参数 | Dark 参数 |
|---|---|---|
| `COMPONENT_ULTRA_THIN` | Radius:120 饱和度:1.1 亮度:1.2 蒙层:`#19FFFFFF` | Radius:200 饱和度:1 亮度:1 蒙层:`#19000000` |
| `COMPONENT_THIN` | Radius:80 饱和度:1.4 亮度:1.2 蒙层:`#66FFFFFF` | Radius:200 饱和度:1 亮度:1 蒙层:`#33000000` |
| `COMPONENT_REGULAR` | Radius:120 饱和度:1.6 亮度:1.2 蒙层:`#99FFFFFF` | Radius:200 饱和度:1 亮度:1 蒙层:`#66000000` |
| `COMPONENT_THICK` | Radius:80 饱和度:1.8 亮度:1 蒙层:`#CCF1F3F5` | Radius:80 饱和度:1.3 亮度:1 蒙层:`#66000000` |
| `COMPONENT_ULTRA_THICK` | Radius:80 饱和度:1.9 亮度:1 蒙层:`#E5FFFFFF` | Radius:80 饱和度:1.5 亮度:1 蒙层:`#E52E3033` |

> 材质效果一般用于弹窗、模态、浮层等需要模糊底层的场景，界面常规元素通常不使用。Light 蒙层用白色提亮，Dark 蒙层用黑色压暗。

---

## 9. 阴影（Shadow · 两模式通用）

### 9.1 基础 Token — 外阴影

| Token | Radius | X | Y | 颜色 |
|---|---|---|---|---|
| `OUTER_DEFAULT_XS` | 8 | 0 | 4 | `#19000000` |
| `OUTER_DEFAULT_SM` | 16 | 0 | 10 | `#19000000` |
| `OUTER_DEFAULT_MD` | 60 | 0 | 10 | `#33000000` |
| `OUTER_DEFAULT_LG` | 120 | 0 | 20 | `#33000000` |
| `OUTER_FLOATING_SM` | 160 | 0 | 20 | `#33000000` |
| `OUTER_FLOATING_MD` | 160 | 0 | 20 | `#66000000` |

---

## 10. Light / Dark 快速对比（关键变化总结）

对于 UI 开发者快速参考——以下 token 在 Light/Dark 下**值不一样**，需要两套处理：

| 类别 | Token | 变化类型 |
|---|---|---|
| **基础色翻转** | `primary*` / `container*` | 黑 ↔ 白 |
| **基础色翻转** | `gray_01` ~ `gray_04` | 浅灰 ↔ 深灰/黑 |
| **品牌色微调** | `brand` / `brand100` ~ `brand5` | `#0A59F7` 底 ↔ `#317AF7` 底（所有带 alpha 的值都跟着变）|
| **品牌文字微调** | `brand_font` | `#0A59F7` ↔ `#5291FF` |
| **功能色微调** | `warning` / `alert` / `confirm` | 饱和高 ↔ 调柔 |
| **多彩色微调** | `multi_color_*` | Dark 下整体降饱和 |
| **语义映射变化** | `font_emphasize` / `icon_emphasize` | `brand100`(#FF0A59F7) ↔ `brand_font`(#5291FF) |
| **品牌 alpha 系列跟随 brand 变** | `icon_sub_emphasize`(brand40) · `comp_emphasize_secondary`(brand20) · `comp_emphasize_tertiary`(brand10) · `interctive_select`(brand20) · `background_emphasize`(brand100) · `comp_background_emphasize`(brand100) · `interactive_focus`(brand100) | 同 brand 基础色，Light 蓝底 ↔ Dark 浅蓝底 |
| **语义映射变化** | `background_primary` | `white` ↔ `black` |
| **语义映射变化** | `comp_background_primary` | `white` ↔ `gray_02` |
| **语义映射变化** | `comp_background_tertiary` | `container5` ↔ `container10` |
| **语义映射变化** | `comp_background_list_card` | `on_primary100` ↔ `on_primary10` |
| **语义映射变化** | `comp_foreground_primary` | `black` ↔ `white` |
| **语义映射变化** | `comp_common_contrary` | `white` ↔ `black` |
| **交互态 alpha 升级** | `interactive_hover` | 5% ↔ 10% |
| **交互态 alpha 升级** | `interactive_pressed` / `click` | 10% ↔ 15% |
| **翻转** | `fg_color_unchecked` | `#33FFFFFF` ↔ `#33000000` |
| **翻转** | `comp_background_model_sheet` / `comp_background_gray_secondary` | `#F1F3F5` ↔ `#202224` |
| **材质蒙层** | `COMPONENT_*` | 白色系蒙层 ↔ 黑色系蒙层 |

以下 token 在 Light/Dark 下**值完全相同**：
- `on_primary*`（始终是白色系 alpha）
- `black` / `white`（固定色）
- `alpha_*` 系列
- `mask_*` 系列（始终黑色 alpha 蒙层）
- `corner_radius_*` / `padding_*` / `border_*` / `size_*`（非颜色 token）
- 所有字号 / 字重 token
- `OUTER_*` 阴影


---
