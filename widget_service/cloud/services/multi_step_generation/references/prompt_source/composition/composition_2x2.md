---
name: phone-widget-composition-2x2
description: 规定共享编排流程在 2×2 中的 Action 路由、固定槽与容量例外；共同收敛流程见 composition_common.md。
---

# 2×2 卡片生成编排

## 1. Action 选择

- 标题与必需内容完整呈现后，只要还能容纳底部操作槽，就优先使用有文字的 `PillButton`。
- 只有底部操作槽无法闭合、右下锚点可以安全避让正文，且操作仅靠 Icon 可明确表达时，才使用 `CircleButton`；完整操作名写入 `ariaLabel`。
- 两个 Action 全部使用 `PillButton` 和 `wide-content-two-actions`，禁止混用 `CircleButton`。
- `double-blocks` 没有 Action 槽；存在 Action 时改选 `single` 和能承载它的 variant。

## 2. 2×2 容量例外

- 两个 `InfoBlock` 只有在两组都具备主副文本并能分别放入 134 × 63vp 固定槽时成立。
- `wide-center` 的 DataDisplay 进入 126 × 126vp 安全内容区居中。
- `wide-content-two-actions` 的内容必须使用紧凑规格。
