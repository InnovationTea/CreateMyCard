---
name: phone-widget-repair-2x2
description: 规定 2×2 专属组件错误和语义 layout／variant 迁移；共同修复顺序见 repair_common.md。
---

# 2×2 校验反馈修复

- `CircleButton` 没有可用 Icon 或 Action 需要显示文字时，把 `wide-title-anchor-action` 改成带底部 `PillButton` 的合法 variant；不得把 `PillButton` 塞进圆形槽。
- `double-blocks` 必须同时保留两个 `InfoBlock`。任一组缺少主副文本、存在 Action 或需要第三个模块时，改用 `single` 和相符 variant。
