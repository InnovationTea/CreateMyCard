---
name: phone-widget-core-2x2
description: 规定 2×2 独有的 Card 属性与背景能力；共享绑定和资源规则见 core_common.md。
---

# 2×2 生成补充协议

## Card

| Prop | 2×2 规则 |
|---|---|
| `size` | 必选，固定为 `"2x2"` |
| `appearance` | 必选；可使用五种 `solid-*`，并可按场景使用 `orb-orange`、`orb-blue`、`orb-purple`、`orb-green` |
| `layout` | 必选，使用当前尺寸 layouts 文件声明的父布局 |

融球背景只用于 2×2，是共享单色场景色之外的可选替代：选用融球背景时，运动、赛事、倒计时、卡路里或热量使用 `orb-orange`；天气、出行、办公或系统使用 `orb-blue`；睡眠、冥想或晚安使用 `orb-purple`；充电使用 `orb-green`。
