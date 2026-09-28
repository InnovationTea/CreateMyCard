# 鸿蒙风格设计规范（A2UI / Extended DSL）

本文件是样式详规入口。逻辑协议、交互上送、NDJSON 时序以 `SKILL.md` 与 protocol 文档为准，本文件仅定义样式层。

## 1. 规范来源与适用范围

### 1.1 运行时样式来源

1. `reference/design/design_token.md`
2. `reference/design/harmony_ui_components_a2ui.md`
3. `reference/design/harmony_card_spec.md`（仅 Card Mode 强约束）

### 1.2 双模式口径

- **Card Mode（JSON 输入）**：必须遵循卡片结构/布局/媒体比例约束。
- **UI Mode（Markdown / Query）**：遵循 token + 组件样式，`card_spec` 仅借鉴。

### 1.3 运行时禁用项

- 不把 `待UX确认`、冲突双值、留空值直接喂给模型。
- 不新增协议未定义字段来“补齐”视觉。

---

## 2. 样式表达总则

- 优先语义 token，不优先旧 hex 常量。
- 尺寸与间距遵循 4vp 网格（默认 8/12，避免大间距叠加）。
- 只使用 `Extended.*` 和协议定义的 `styles` 字段。
- 文档中的示例值用于“稳定默认”，若与规范冲突，以来源文档为准。

---

## 3. 样式速查（运行时默认）

> 下表用于快速决策，不替代上游权威矩阵。

| 类型 | 语义 token（优先） | 说明 |
|---|---|---|
| 主文本 | `font_primary` | 正文、标题主层级 |
| 次文本 | `font_secondary` | 副标题、说明 |
| 弱文本 | `font_tertiary` / `font_fourth` | 辅助、禁用 |
| 强调文本/图标 | `font_emphasize` / `icon_emphasize` | 可品牌覆盖 |
| 容器底 | `comp_background_primary` / `comp_background_list_card` | 场景选用 |
| 弱底 | `comp_background_tertiary` | 普通按钮、弱容器 |
| 强调底 | `background_emphasize` / `comp_background_emphasize` | CTA、选中 |
| 分割线 | `comp_divider` | Divider / 行分隔 |
| 交互叠加 | `interactive_hover` / `interactive_pressed` / `interactive_focus` | 视觉反馈语义 |
| 功能色 | `warning` / `alert` / `confirm` | 警示/提醒/成功 |

---

## 4. 组件样式决策（保持 skill 稳定结构）

### 4.1 Button

- 子样式只从规范已收敛集合选择（普通/强调/警告/文本/小/图标）。
- 列表项右侧优先小按钮；卡片宫格样式 3 图文+按钮优先普通按钮。
- 不额外发明 `loading` 字段。

### 4.2 TextInput

- 支持框型/线型/计数器三类样式口径；由场景明确选择。
- `text` 绑定规则不在本文件定义，严格遵守 `SKILL.md §0`。

### 4.3 Divider

- 优先留白分组，必要时再用 `Extended.Divider`。
- 线色使用 `comp_divider` 语义，不沿用旧固定 `#E5E5E5`。

### 4.4 List / Grid / Media（Card Mode）

- List / Grid 的结构与比例按 `reference/design/harmony_card_spec.md` 强约束。
- 不满足媒体条件时按降级策略处理，不硬套 grid。

### 4.5 非一等组件（Part C）

- 仅按 `composed` / `degradable` / `gap` 处理。
- 不输出不存在的 `Extended.*` 组件名或样式字段。

---

## 5. 品牌色覆盖

- 仅允许整组 token overlay，不允许单组件任意改色。
- 可覆盖范围以 `reference/design/harmony_ui_components_a2ui.md` 的品牌 token 清单为准。
- Dark 模式需保证可读性；无法可靠派生时保留默认 token 值。

---

## 6. 保留的稳定布局经验（继续沿用）

- 媒体列表行：外层 `[left_group, action]` + `spaceBetween`；内层 `[thumb, text]` + `space:8`。
- 多列榜单/表格：显式列宽（`constraintSize` 或可控 `layoutWeight`），避免末列被压缩成省略号。
- chip 用 `Extended.Text + border/padding`，不在 stretch 列里用会拉满的容器充当标签。
- 对话卡密度默认 8/12 档，避免 `padding+space+margin` 大值叠加。

---

## 7. 与示例文件关系

- 可复制片段见：`reference/design/quick-snippets.md`
- 交互策略见：`reference/design/interaction-design.md`
- 本文件不定义 NDJSON 输出顺序、事件载荷、提交流程。
