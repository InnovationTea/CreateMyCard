# 鸿蒙风格 DESIGN.md（极简 GenUI）

本文件是给 Agent 读取的「设计语言上下文」，用于生成**鸿蒙风格**的高端精致 UI，并在 **updateComponent** 行中输出 **Card** / **Row** / **Column** / **Text** / **Button** / **Input** / … 的平面 props（见 `reference/protocol/extended-ui-schema.md`）。

> 完整细节与可复制片段见：`reference/design/harmony-style.md`、`reference/design/quick-snippets.md`。

---

## 1. 视觉主题与气质

- **高端、克制、信息层级清晰**：靠 `Text` 的 `fontSize` / `fontWeight` / `fontColor` 建立层次，而不是堆叠重阴影。
- **对话卡片偏紧密度**：默认取偏小档 **gap / padding / space**（**6–12**），避免「松、空」。
- **内容优先**：图片与数据是主角；**Card** 只负责分组与承载。

---

## 2. 色板与语义角色

### 2.1 核心色

- **主色 / 强调 / 链接文字**：`#0A59F7`（主按钮底、链接型 **Text** `fontColor`）
- **卡片底**：`#FFFFFF`
- **页面浅底 / 根容器**：`#F1F3F5`
- **分割线 / 弱描边**：`#E5E5E5`（用于 **Card** `strokeColor` 等）

### 2.2 文本灰阶（Light）

- **一级文字**：`#000000`（`Text` `fontColor`）
- **二级文字**：`#666666`
- **三级文字**：`#999999`

### 2.3 语义色

- **警告 / 错误**：`#E84026`
- **成功点缀**：`#2E7D32`（如「宜」标签文字）

---

## 3. 字体与排版层级

映射到 **`Text`** 的 `fontSize` / `fontWeight` / `fontColor`（**不要**用 `fill` 给文字上色；`fill` 属于 **Card** 背景）。

- **展示**：38–56（每卡 ≤ 1 处）
- **强调**：14 / 16 / 18
- **正文**：12–16
- **提示**：10–12

字重：标题 / 主数字倾向 **`"500"`–`"600"`**；正文 **`"400"`**。

**省略**：需要截断时设置 `maxLines` + `textOverflow`: `"ellipsis"`，并保证有 `width` 或容器约束；长正文默认不要随意 ellipsis。

---

## 4. 圆角体系

- **外层 Card**：`radius`: **20**
- **按钮**：`borderRadius`: **20**（大）/ **14**（小）
- **小标签 / chip 容器**：`radius`: **4**（用小 **Card** 包 **Text**，不要用 20 圆角做 chip）

---

## 5. 间距与网格

- **4px 网格**：优先 **4 / 8 / 12 / 16**；页面级少量 **20–24**。
- **对话卡片**：**Card** `padding` 默认 **12**；**Card** `gap` 与 **Column**/**Row** 的 `space` 多用 **8–12**。

---

## 6. 组件风格约定（compact props）

### 6.1 `Card`

- `radius`: **20**；`padding`: **12**（或 **16** 强调块）
- `fill`: `"#FFFFFF"` 或 `"#F1F3F5"`；沉浸式可用 **单行字符串** 写完整 `linear-gradient(...)`（字符串内不换行）
- `width`: `"matchParent"` 于 root 与主要 section
- `layout`: `"vertical"` 默认；需要左右双面板时用 `"horizontal"` 包两个子 **Card**

### 6.2 `Button`

- 主按钮：`backgroundColor`: `"#0A59F7"`，`label` 短而可读，`borderRadius`: **20** 或 **14**
- 次按钮：浅灰底或描边策略由宿主渲染；避免两颗完全同权的实心主按钮
- 需要打开链接时设置 **`openUrl`**（绝对 `http`/`https`）

### 6.3 `Input`

- 字段分组放在 **Column** `space` **8–12** 内；`label` / `name` / `placeholder` / `type` 见 schema

### 6.4 `Text`

- 数据密、对比行：尽量为每个 **Text** 显式设置 **`fontColor`**，同列同 token，避免依赖宿主默认色

---

## 7. Do & Don't

### Do

- 媒体行：**外层 Row** `[左组, 按钮]` + `spaceBetween`；**内层 Row** `[Image, Column]` + `space` **8**
- 榜单：**外层 Row 两子组**（左：排名+国家列组，右：奖牌列组），组内 `space` 小、组间 `spaceBetween` 拉大间隙
- 标签：小圆角 **Card** 包单行 **Text**，或 **Text** + `padding` + `borderWidth` + `borderRadius`（注意不要被 `stretch` 拉成全宽线框）

### Don't

- 把封面 + 文案 + 按钮 **三个** 直接并排塞进同一 **Row** 再指望测量稳定
- 在同一 **Card** 内堆叠 **超大 padding + 超大 gap + 大 margin**
- 用 **`fill`** 修改 **Text** 颜色（应使用 **`fontColor`**）

---

## 8. 响应与可读性

- 主要容器 `width`: `"matchParent"`
- KPI 行用 **Row** `justifyContent`: `"spaceBetween"` 拉满横向空间
- 字号不要低于 **10**

---
