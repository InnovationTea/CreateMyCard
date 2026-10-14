---
name: phone-widget-component-combinations-2x2
description: 规定多组件组合在 2×2 中的具体组件形态、合法 variant 与示例；共同组合语义见 component-combinations_common.md。
---

# 2×2 多组件组合

## 1. 组合实现总表

| 类型 | 组合名称 | 本尺寸实现 | 布局 / variant | 本尺寸限制 |
|---|---|---|---|---|
| 标题组合 | 标题与数量 | 标题 + `Badge` | 任一支持标题的 variant | Badge 紧跟标题，共同占用标题位 |
| 主次组合 | 核心与补充 | 标题 + 2 个内容组件 | `wide-title-primary-secondary` | 子节点按标题、核心、补充顺序提交 |
| 主次操作 | 核心、补充与操作 | 标题 + 2 个内容组件 + `PillButton` | `wide-title-primary-secondary-action` | 按钮为最后一个直属节点 |
| 占比组合 | 双占比 | `ProgressCircle × 2` | `wide-two-column-action` | 两项均 `size="sm"`，按钮可选 |
| 占比组合 | 三占比 | 一个 `NumericRatioStack` | 除 `wide-center` 与双环／四环专用 variant 外的普通内容位 | 恰好三项，整体算一个内容组件 |
| 占比组合 | 四占比 | `ProgressCircle × 4` | `wide-quad-content` | 无标题、无 Action |
| 固定模块 | 双信息块 | `InfoBlock × 2` | `double-blocks` | top、bottom 各一个，不加第三模块 |
| 内容操作 | 单内容与操作 | 内容 + `PillButton` | 带单按钮的合法 variant | 按钮为最后一个直属节点 |
| 尺寸专属 | 标题锚点操作 | 标题 + 2 个内容组件 + `CircleButton` | `wide-title-anchor-action` | 必须有匹配 Icon 和完整 `ariaLabel` |
| 操作组合 | 双操作 | 内容 + `PillButton × 2` | `wide-content-two-actions` | 两个按钮均必选，不混用 `CircleButton` |

## 2. 标题与数量实现

```jsx
<Region slot="main" variant="wide-title-primary-secondary">
  <SingleLineTitle title="未来7天日程" />
  <Badge value={1} color="pink" dataIds={{ value: "calendar.eventCount" }} />
  <EventCard
    items={[{
      title: "项目例会",
      time: "14:00",
      dataIds: {
        title: "calendar.events.0.title",
        time: "calendar.events.0.dtStart",
      },
    }]}
  />
  <SecondaryBody
    items={[{ value: "周例会", dataIds: { value: "calendar.events.0.description" } }]}
  />
</Region>
```

## 3. 双信息块实现

```jsx
<Card size="2x2" appearance="orb-purple" layout="double-blocks">
  <Region slot="top">
    <InfoBlock
      primaryText="昨夜7小时1分"
      primaryTextTemplate="昨夜{value}"
      secondaryText="午睡0分"
      secondaryTextTemplate="午睡{value}"
      dataIds={{
        primaryText: "healthSport.nightSleepDurationText",
        secondaryText: "healthSport.totalNapDurationText",
      }}
    />
  </Region>
  <Region slot="bottom">
    <InfoBlock
      primaryText="昨夜82分"
      primaryTextTemplate="昨夜{value}"
      secondaryText="科学睡眠"
      secondaryTextTemplate="类型 {value}"
      dataIds={{
        primaryText: "healthSport.sleepScore",
        secondaryText: "healthSport.sleepTypeDesc",
      }}
    />
  </Region>
</Card>
```

在 2×2 中，两个 `InfoBlock` 占用整张卡的两个固定槽；`double-blocks` 不再承载标题、第三个内容或 Action。

## 4. 占比组合实现

双占比作为 `wide-two-column-action` 标题后的两个直属 `ProgressCircle size="sm"`；四占比作为 `wide-quad-content` 的四个直属 `ProgressCircle`。三占比使用一个 `NumericRatioStack`：

```jsx
<NumericRatioStack
  direction="column"
  appearance="card"
  items={[
    { icon: "earphone_case_16644.svg", value: 80, unit: "%", dataIds: { value: "earbuds.caseBatteryPercent" } },
    { icon: "l_circle_fill.svg", value: 76, unit: "%", dataIds: { value: "earbuds.leftBatteryPercent" } },
    { icon: "r_circle_fill.svg", value: 74, unit: "%", dataIds: { value: "earbuds.rightBatteryPercent" } },
  ]}
/>
```

## 5. 操作组合实现

- 单 `PillButton` 和两个 `PillButton` 都按当前 variant 的直属顺序提交。
- `CircleButton` 仅用于 `wide-title-anchor-action` 且是最后一个直属节点。
