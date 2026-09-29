---
name: phone-widget-components-2x4
description: 规定 2×4 专属组件的选择条件、真实 Props、绑定能力、容量和单组件示例；共享组件见 components_common.md。
---

# 2×4 专属组件

2×4 除共享组件外，还可以使用以下专属组件。具体可用 Region 与 variant 由 Layouts 定义。

## 1. 专属组件总表

| 类型 | 名称 | 内容结构 | 适用场景 | 容量与约束 |
|---|---|---|---|---|
| 整宽明细 | `TopTextBottomValue` | 三组标签—数值—单位 | `top-bottom` 的三项数值明细 | 恰好三组；仅 `details` |
| 整宽明细 | `TextBlock` | 2–4 组并列标签—参数 | `top-bottom` 的同级属性明细 | 2–4 项；仅 `details` |
| 固定操作 | `CardButton` | 文案 + 可选 Icon | 固定半卡操作槽 | 1 个 Action；只进入固定槽 |

## 2. 共享组件的 2×4 适配

### 2.1 `InfoBlock`

只进入 `main-right-double` 的 `side-top`／`side-bottom` 固定槽或 `four-blocks` 的四个固定槽；不得进入 compact／wide 内容区。两个 `InfoBlock` 构成双信息块时，必须分别完整表达两组真实主辅信息。

### 2.2 进度与比较组件

2×4 只使用单色浅背景，因此 `ProgressLine2` 与 `H_BarChart` 固定使用 `mode="light"`。`ProgressCircleSingle` 进入任一 compact／wide 内容 variant 时固定使用 `size="compact"`。

## 3. 专属文本组件

### 3.1 `TopTextBottomValue`

#### 选择条件

仅作为 `top-bottom` 的 `details` Region 直属组件，用于恰好三组“标签—数值—单位”指标；禁止进入其他父布局或 compact/wide 内容槽。

#### 组件属性

| Prop | JSX 类型 | 生成规则 |
|---|---|---|
| `items` | `Array<{ key?, label, value, unit, dataIds? }>` | 必选，恰好 3 项 |
| `items[].label` | `string` | 必选，静态标签 |
| `items[].value` | `string \| number` | 必选；动态值必须绑定 |
| `items[].unit` | `string` | 必选，静态单位 |
| `items[].dataIds` | `{ value?: string }` | 只绑定同项 value |

#### 槽位与容量

组件占满 `details` 父模块，固定高 68vp；内容总宽度放不下时该组件无效，不依赖省略号通过。

#### 示例

```jsx
<TopTextBottomValue
  items={[
    { label: "最高", value: 28, unit: "℃", dataIds: { value: "weather.high" } },
    { label: "最低", value: 19, unit: "℃", dataIds: { value: "weather.low" } },
    { label: "湿度", value: 62, unit: "%", dataIds: { value: "weather.humidity" } },
  ]}
/>
```

#### 注意事项

每项只绑定 `value`；标签和单位保持静态。不得把同一字段同时放入主体和明细。

### 3.2 `TextBlock`

#### 选择条件

用于 `top-bottom.details`，并列展示 2–4 个同级文本或完整格式化值。每项自带背板，适合属性摘要。它只承担主体之后的同级明细，不代替事件、标题数量、进度、占比或比较组件。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `items` | `Array<{ key?, label, parameter, dataIds? }>` | 必选，2–4 项 | 每项 `parameter` |
| `items[].label` | `string` | 必选，静态 | 不绑定 |
| `items[].parameter` | `string \| number` | 必选 | `items[].dataIds.parameter` |

#### 槽位与容量

属于整宽高密度明细，只进入 `top-bottom.details`。支持 2–4 个短属性；标签和值都应简短并能独立理解。

#### 示例

```jsx
<TextBlock
  items={[
    { label: "湿度", parameter: "46%", dataIds: { parameter: "greenhouse.humidityText" } },
    { label: "光照", parameter: "充足", dataIds: { parameter: "greenhouse.lightStatus" } },
    { label: "土壤", parameter: "偏干", dataIds: { parameter: "greenhouse.soilStatus" } },
  ]}
/>
```

#### 注意事项

超过 4 项或长文本较多时会溢出。需要纵向标签—参数结构时使用 `TableText`。

## 4. 专属操作组件

### 4.1 `CardButton`

#### 选择条件

用于 `main-right-double` 或 `four-blocks` 的固定操作槽。`main-right-double` 只有一个 Action 时，该按钮进入 `side-bottom`，`side-top` 必须同时存在一组真实 `InfoBlock`。

#### 组件属性

| Prop | 类型 | 要求 | 可绑定字段 |
|---|---|---|---|
| `text` | `string` | 必选，简短操作文案 | 不绑定 |
| `icon` | `string` | 可选，来自当前资源候选 | 不绑定 |
| `actionId` | `string` | 启用状态必选 | 原样引用一个 `actions[].id` |

#### 槽位与容量

属于固定操作模块，只进入 `main-right-double` 或 `four-blocks` 的固定槽。每槽一个，不传布局属性。

#### 示例

```jsx
<CardButton text="查看周报" actionId="report.openWeekly" />
```

#### 注意事项

`CardButton` 不使用 `appearance`、`variant` 或 `color`。没有合适 Icon 时省略，组件仍可正常显示。

## 5. 选择检查

1. 专属组件的 Props、数据绑定和最小容量符合本文件合同。
2. 组件进入 Layouts 明确允许的 Region 与 variant。
3. 不用专属组件重复表达共享组件已经展示的同一事实。
