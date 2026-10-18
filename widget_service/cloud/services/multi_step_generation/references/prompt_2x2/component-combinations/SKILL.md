---
name: phone-widget-2x2-component-combinations
description: 当多个业务组件需要共同表达一组信息或操作时选择并实现合法组合。
---

# 多组件组合

多组件组合只描述业务组件之间的语义关系。具体排列由 2×2 layouts Skill 的 `Card.layout` 与 `Region.variant` 决定，模型不得输出 `Stack` 或 `Grid`。

## 组合候选总表

| 组合信息形态 | 字段结构示例 | 组合 | 选择条件 | 不应选择的情况 |
|---|---|---|---|---|
| 标题中的数量 | `{title, count}` | 标题 + `Badge` | 数量概括下方日程、消息或列表 | 不把同一总数再次生成为强调数值 |
| 2 个占比值 | `{items: [{percent, icon}, {percent, icon}]}` | `ProgressCircle` × 2 | 两个同级对象并列；使用 `wide-two-column-action` | 1 个值改用 `ProgressCircleSingle`；每项还带独立副文本时先判断 `InfoBlock × 2` |
| 3 个占比值 | `{items: [{percent, icon}, ...]}` | `NumericRatioStack` | 恰好三个同级占比值，由 Icon 区分；整个组合算一个内容组件 | 不用于 1、2 或 4 个值；必须显示逐项文本 Label 时不用 |
| 4 个占比值 | `{items: [{percent, icon}, ...]}` | `ProgressCircle` × 4 | 四个同级对象；使用 `wide-quad-content` | 不通过多个 `NumericRatio` 表达；必须显示逐项文本 Label 时不用 |
| 两组紧凑主副文本 | `{groups: [{primaryText, secondaryText}, ...]}` | `InfoBlock` × 2 | 恰好两组可独立理解的信息，每组均有主文本与副文本；使用 `double-blocks` | 只有一组、三组以上或任一组缺少主副文本时不用 |
| 1 个文字 Action | `{action}` | `PillButton` | 标题和必需内容能够与底部文字按钮共同闭合 | 不得仅因提供 Icon 改用 `CircleButton` |
| 1 个 Icon Action | `{action: {icon, ariaLabel}}` | `CircleButton` | 操作仅靠 Icon 即可明确表达，且锚点不会遮挡正文 | 没有语义匹配 Icon、操作需要可见文字或正文无法避让时不用 |
| 2 个 Action | `{actions: [a, b]}` | `PillButton` × 2 | 一个紧凑内容与两个必需操作可共同闭合；使用 `wide-content-two-actions` | 不得混用 `CircleButton`，不得删除其中一个 Action |

## 标题与数量

`Badge` 必须紧跟它修饰的标题，作为同一 Region 中标题后的直属节点。程序生成标题横排及固定间距，模型不使用容器包裹。

当总数用于概括下方内容时，总数只绑定到 `Badge.value`，不再为同一个总数生成 `EmphasizedData`：

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
    items={[{
      value: "周例会",
      dataIds: { value: "calendar.events.0.description" },
    }]}
  />
</Region>
```

## 双信息块

两个 `InfoBlock` 分别放入 `double-blocks` 的固定 Region。每槽只允许一个 `InfoBlock`，组件使用父槽完整宽度；不得传入 width，也不得增加标题或第三个模块。

```jsx
<Card size="2x2" appearance="orb-purple" layout="double-blocks">
  <Region slot="top">
    <InfoBlock
      primaryText="昨夜7小时1分"
      primaryTextTemplate="昨夜{value}"
      secondaryText="午睡0分"
      secondaryTextTemplate="午睡{value}"
      visual={{ type: "icon", icon: "moon_z_fill_1.svg" }}
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
      secondaryText="睡眠｜科学睡眠"
      secondaryTextTemplate="睡眠｜{value}"
      visual={{ type: "icon", icon: "moon_z_fill_1.svg" }}
      dataIds={{
        primaryText: "healthSport.sleepScore",
        secondaryText: "healthSport.sleepTypeDesc",
      }}
    />
  </Region>
</Card>
```

尾部进度环仍属于同一个 InfoBlock，不额外计算为业务模块。单设备剩余电量可使用：

```jsx
<InfoBlock
  primaryText="电量 68"
  primaryTextTemplate="电量 {value}"
  unit="%"
  secondaryText="未充电｜29.0 ℃"
  visual={{ type: "progressCircle", icon: "icon_charge.svg" }}
  dataIds={{
    primaryText: "battery.remainingPercent",
    secondaryText: ["battery.chargingStatusDesc", "battery.temperatureText"],
  }}
/>
```

## 多占比组合

两个同级占比使用 `wide-two-column-action`，两个 `ProgressCircle` 作为标题后的直属内容；可选按钮必须位于最后。四个同级占比使用 `wide-quad-content`，四个 `ProgressCircle` 作为直属内容。程序负责横排、网格、居中和等宽分配。

三个同级占比使用一个 `NumericRatioStack`，不输出三个独立 `NumericRatio`：

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

## 内容与按钮

- 一个文字 Action 使用明确支持按钮的 variant，并将 `PillButton` 作为 Region 最后一个直属节点。
- 两个文字 Action 使用 `wide-content-two-actions`，顺序为一个紧凑内容、两个 `PillButton`。
- 按钮槽与内容的对齐、贴底和间距由程序保证；模型不填写定位或尺寸。
- 同一 Action 只能生成一次；不得用 `PillButton` 与 `CircleButton` 重复表达。
- 如果卡片其他组件已经使用相同 Icon，`PillButton` 内省略重复 Icon，只保留文本。

## 右下锚点操作

`CircleButton` 仅用于 `wide-title-anchor-action`，并且必须作为 Region 的最后一个直属节点。程序固定生成右下操作槽，模型不得填写 position、right、bottom、width 或 height。

```jsx
<Card size="2x2" appearance="solid-blue" layout="single">
  <Region slot="main" variant="wide-title-anchor-action">
    <SingleLineTitle title="天气" />
    <EmphasizedData
      value="26℃"
      dataIds={{ value: "weather.temperatureText" }}
    />
    <SecondaryBody
      items={[
        { value: "多云", dataIds: { value: "weather.condition" } },
        { label: "湿度", value: "68%", dataIds: { value: "weather.humidityText" } },
      ]}
    />
    <CircleButton
      icon="phone_fill.svg"
      ariaLabel="拨打电话"
      appearance="card"
      actionId="contact.callPrimary"
    />
  </Region>
</Card>
```
