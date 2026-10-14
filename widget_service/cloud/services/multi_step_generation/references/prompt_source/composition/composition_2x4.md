---
name: phone-widget-composition-2x4
description: 规定共享编排流程在 2×4 中的槽位兼容性、父布局路由与容量例外；共同收敛流程见 composition_common.md。
---

# 2×4 卡片生成编排

## 1. 组件、组合与语义槽位兼容矩阵

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 标题槽 | 标题单元 | 单个标题组件，或“标题与数量”组件组合 | `top-bottom.title` 及所有带标题的 `Region.variant` | 一个标题位只放一个标题单元；组合中的 `Badge` 紧跟标题 |
| 内容槽 | 紧凑通用内容 | 布局规范的“紧凑内容”组件集合 | 所有 `compact-*` 通用内容位 | 每个内容位只放 1 个集合内组件；连续内容只在实际高度能闭合时进入 |
| 内容槽 | 宽通用内容 | 布局规范的“宽内容”组件集合 | `wide-center`、`wide-title-content*`、`wide-title-primary-secondary*` 的通用内容位 | 每个内容位只放 1 个集合内组件；不放 `TextBlock`、`InfoBlock` 或普通 `ProgressCircle` |
| 专用内容 | 核心居中 | `DataDisplay` | 仅 `compact-center` 或 `wide-center` | 作为唯一内容组件；不与标题、明细或 Action 共用该内容区 |
| 高密度内容 | 整宽并列明细 | `TextBlock` 或 `TopTextBottomValue` | 只进入 `top-bottom.details` | 不进入 compact／wide 内容区变体；按字段结构选择其一 |
| 高密度内容 | 三占比 | `NumericRatioStack` | 3 个同维度占比 | 作为 1 个紧凑内容或宽内容组件进入通用内容位 |
| 专用变体 | 双占比 | `ProgressCircle × 2` | 2 个同级占比 | 只进入 `wide-title-double-progress` |
| 固定模块槽 | 双信息块 | `InfoBlock × 2` | 2 组同级主辅信息 | 只进入 `main-right-double` 的两个右槽；左侧仍需真实主内容 |
| 专用变体 | 四占比 | `ProgressCircle × 4` | 4 个同级占比 | 只进入 `wide-quad-progress` |
| 固定模块槽 | 紧凑信息 | `InfoBlock` | `main-right-double` 右槽或 `four-blocks` | 每槽恰好 1 个；不再套内容区变体 |
| 固定模块槽 | 操作 | `CardButton` | `main-right-double` 右槽或 `four-blocks` | 每槽恰好 1 个；不用 `PillButton` 代替 |
| 内容区操作位 | 直属操作 | `PillButton` | 名称包含 `action` 的内容区变体 | 恰好 1 个直属 Action；不进入固定模块槽 |

## 2. 2×4 路由与容量例外

- `top-bottom` 不提供 Action 槽；含 Action 的任务不选用。其 `details` 恰好放一个 `TextBlock` 或 `TopTextBottomValue`。
- `split-panels` 遵守布局规范对 compact／wide 变体的限制。
- `main-right-double` 的右侧必须填满两个固定槽，只允许双 `CardButton`、双 `InfoBlock`、或上 `InfoBlock` + 下 `CardButton`。
- `four-blocks` 必须填满 4 个固定槽，每槽一个 `InfoBlock` 或 `CardButton`。
- 一条短事件、两项短 `TableText` 或双项短 `H_BarChart` 可进入能闭合的紧凑单内容位；两条事件、较多表格项和三项柱图使用宽内容区。
