---
name: phone-widget-components-2x2
description: 规定共享组件在 2×2 中的容量与可用区域，以及 CircleButton 的选择条件和真实 Props；共享组件合同见 components_common.md。
---

# 2×2 组件规范

## 1. 组件容量与可用区域

| 组件 | 2×2 适配 |
|---|---|
| `DataDisplay` | 只进入 `wide-center`；最大宽 126vp、高 114vp |
| `InfoBlock` | 只进入 `double-blocks` 的 `top`／`bottom` 固定槽；每槽 134 × 63vp |
| `ProgressCircleSingle` | 普通 variant 使用默认规格；不进入 `wide-content-two-actions` 的 38vp 内容槽（紧凑规格仍至少占 44vp） |
| `ProgressCircle` | 两项并列时使用 `wide-two-column-action`，两项均为 `size="sm"`；四项使用 `wide-quad-content` |
| `NumericRatioStack` | 恰好三个同级占比时作为一个内容组件；一项、两项或四项不用 |
| `EventCard` | 使用父槽完整宽度但最大不超过 116vp；`items` 最多两条 |
| `PillButton` | 只进入 layouts 明确提供的底部操作槽，默认 126 × 36vp |

## 2. 两个同级占比

两个同级占比必须使用两个 `ProgressCircle size="sm"`，并作为 `wide-two-column-action` 的直属内容；不得用 `NumericRatioStack`、文本或容器替代。

```jsx
<Region slot="main" variant="wide-two-column-action">
  <SingleLineTitle title="设备电量" />
  <ProgressCircle icon="phone_fill.svg" externalText="68%" size="sm" appearance="card" ariaLabel="手机电量68%" />
  <ProgressCircle icon="watch_fill.svg" externalText="52%" size="sm" appearance="card" ariaLabel="手表电量52%" />
</Region>
```

## 3. 2×2 专属组件：CircleButton

只显示 Icon、不显示文字的圆形按钮，只用于 `wide-title-anchor-action` 的右下锚点操作。

| Prop | JSX 类型 | 生成规则 |
|---|---|---|
| `icon` | `string` | 必选，逐字使用当前输入的语义匹配资源 |
| `ariaLabel` | `string` | 必选，写完整操作名称 |
| `appearance` | `"card"` | 生成 Card 必选 |
| `disabled` | `boolean` | 可选 |
| `actionId` | `string` | 启用状态必选，逐字引用真实 Action ID |

只生成表中列出的 Prop，不生成 `variant`、`color`、`position`、`right`、`bottom`、`width` 或 `height`。定位由语义布局负责；按钮占用 40 × 40vp 锚点槽。
