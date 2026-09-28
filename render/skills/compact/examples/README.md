# Examples index（compact / 极简 GenUI）

本目录示例帮助 Agent 在 **Mode A / Mode B** 下类比稳定 UI 形状。输出均为 **极简 GenUI JSONL**（`createSurface` + 每组件一行 `updateComponent`；需要时 `updateDataModel` / `deleteSurface`），不是完整协议信封文。

## Mode A — Render / Present（已有内容 → UI）

### Dialog Card / Compact Card

- `cards/card-audio-list.md`：媒体列表行
- `cards/card-medal-leaderboard.md`：奖牌榜密表
- `cards/card-calendar-almanac.md`：日历 / 宜忌

### Form / Flow

- `flows/form.md`：登录 / 注册 / 订座
- `flows/list.md`：单外框列表 + 轻分组
- `flows/modal.md`：确认 / 危险操作（**Card** 分区，无 `Extended.If`）
- `flows/booking-flow.md`：多步流程（每步可新 `createSurface` 或续传，见文内说明）

### Capabilities

- `capabilities/streaming.md`：骨架 + 续传 **updateComponent**
- `capabilities/multi-surface.md`：多 `surfaceId` 与 `deleteSurface`

### Markdown / JSON 输入

- `inputs/markdown-input/article-landing.md`
- `inputs/json-input/product-compact-card.md`

## Mode B — UI-first streaming

先 **createSurface** + 根与子节点，再按行追加；见 `capabilities/streaming.md`。

## 与 A2UI 示例的关系

`skills/a2ui/examples` 提供 **布局与信息架构**；本目录给出 **极简行** 的平行实现。下游脚本可将极简行映射为完整 A2UI，映射细节不在本 skill 范围内。
