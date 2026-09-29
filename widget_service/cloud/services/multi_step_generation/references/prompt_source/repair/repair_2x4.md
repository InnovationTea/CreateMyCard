---
name: phone-widget-repair-2x4
description: 规定 2×4 固定槽、必需 Action 和语义 layout／variant 迁移；共同修复顺序见 repair_common.md。
---

# 2×4 校验反馈修复

## 1. 必需 Action 缺失

缺少必需 Action 时，优先在原信息分区中改用能承载该 Action 的 variant。不能成立时，再使用 `main-right-double` 或 `four-blocks` 的固定操作槽。

当 `main-right-double` 有两个必需 Action 时，先按 Action 的真实作用对象分配：如果一个 Action 直接服务 `main` 内容，优先使用 `wide-title-content-action` 或 `wide-title-primary-secondary-action`，并将该 Action 作为 `main` Region 最后的 `PillButton`。若另一个 Action 与一项侧边信息组成混合固定槽，必须使用 `side-top` 的 `InfoBlock` 和 `side-bottom` 的 `CardButton`；不得上下互换。若侧边不需要信息模块，也可以使用两个 `CardButton`。只有 `main` 无法使用合法 Action variant 且侧边槽不足时，才更换父布局。

## 2. 双 Action 固定槽迁移

当 `main-right-double` 主区中的 `PillButton` 与内容发生间距或重叠错误，任务恰好有两个必需 Action，且两个 Action 共同服务主内容或整卡时，可移除主区的 Action variant，将两个 Action 分别迁移为 `side-top`、`side-bottom` 的 `CardButton`。迁移后不得改变 Action 作用对象；否则更换主区 variant 或父布局。采用双 `CardButton` 时，主区改用对应的无 Action variant，不保留主区 `PillButton`，也不保留或虚构 `InfoBlock` 占据固定操作槽。

## 3. 固定槽检查

`Card.layout`／`Region.variant` 必须与内容关系一致；固定双槽、四槽都要按各自合同填满。混合固定双槽只允许上方 `InfoBlock`、下方 `CardButton`。
